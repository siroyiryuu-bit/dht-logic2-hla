# -*- coding: utf-8 -*-
"""
DHT 系列单总线温湿度协议解码器（Saleae Logic 2 · High Level Analyzer）
支持 DHT11 / DHT12 / DHT22(AM2302) —— **选择型号后所有时序阈值自动填入，无需手动设置**

============================== 怎么用（必读）==============================
Logic 2 的 HLA 输入源只能是"另一个底层分析器"，不能直连数字通道。
而 DHT 是"脉宽编码"的单总线协议，内置分析器里没有脉宽解码器 ——
所以这里借用 **Simple Parallel** 当作"边沿采样器"：

  1) 添加 Simple Parallel 分析器，设置：
       · Clock Channel = DHT 数据线所在通道
       · Clock Edge    = Falling（下降沿）
       · D0            = 同一根 DHT 数据线（D1..D15 全部设为 None）
       · 采样率建议 ≥ 4 MS/s（最窄脉宽 27µs，推荐 10~25 MS/s）
  2) 再添加本 HLA（DHT Analyzer），"Input Analyzer" 选刚才那个 Simple Parallel。
  3) 设置里**只需选 Sensor Type**（DHT11 / DHT12 / DHT22-AM2302），
     时序阈值全部按型号自动填入；保留的 3 个数值项默认 0 = 自动，一般不用动。

============================== 关于默认值 ==============================
本版本 Logic 2 的 saleae.analyzers.settings 不支持给设置项指定默认值
（Setting.__init__ 只接受 label；_serialize 不输出 default），
UI 会把数值型设置的初始值填成 min_value。
因此本插件把这三个数值项的 min_value 设为 0，并把 **0 定义为"自动"**：
选中型号后自动套用内置阈值，用户完全不用手动填。

============================== 解码原理 ==============================
Simple Parallel 在每个下降沿产生一帧。DHT 一帧波形的下降沿序列为：
    F1 = 主机拉低（起始）   F2 = 从机响应低   F3..F42 = 40 个数据位的"位间隔低"
相邻下降沿的时间差：
    F1→F2 ≈ 20ms + 80µs      → 帧起始（远超其它间隔，用它做同步）
    F2→F3 ≈ 80 + 80 + 50     → 从机响应（约 210µs）
    F(k)→F(k+1) = 高电平 + 50µs  → 数据位：77µs=0，120µs=1
位值 = (间隔 - 位低电平宽度) 是否大于 "1" 的阈值。
注意：最后一位（bit39）的高电平之后没有下降沿，它是**校验和字节的最低位**，
     无法直接测量；好在前 4 个字节（湿度/温度）是完整的，
     校验比对时忽略最低位即可（结果里会注明）。

调试：Logic 2 的 Terminal 可看到 print() 输出。
"""

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, NumberSetting, ChoicesSetting


class DhtHla(HighLevelAnalyzer):
    """DHT11 / DHT12 / DHT22(AM2302) 单总线协议解码器"""

    # ---------------- 设置项 ----------------
    # 说明：数值项 min_value=0，且 **0 表示"按型号自动"**。
    #      （Logic 2 把数值设置初始化为 min_value，所以默认就是"自动"）
    sensor_type = ChoicesSetting(
        label='Sensor Type',
        choices=('DHT11', 'DHT12', 'DHT22 / AM2302'))
    start_min_us = NumberSetting(
        label='Start Interval Min (us) [0=auto]', min_value=0, max_value=50000)
    bit_low_us = NumberSetting(
        label='Bit Low Width (us) [0=auto]', min_value=0, max_value=200)
    bit_one_us = NumberSetting(
        label='Bit 1 Threshold (us, high) [0=auto]', min_value=0, max_value=200)
    show_bit_frames = ChoicesSetting(
        label='Show Bit Frames', choices=('No', 'Yes'))

    # ---------------- 各型号内置时序（自动套用）----------------
    #   说明：三个值对所有 DHT 变体通用 —— 位间隔低电平标称 50µs，
    #   位高电平 0≈27µs / 1≈70µs（阈值取 40µs）；
    #   start_min 只需满足：大于"最长的非起始间隔"(响应 ≈210µs)，小于起始间隔
    #   （DHT11 ≈20ms、DHT22 ≈1.1ms）→ 取 500µs 对所有型号都成立。
    AUTO = {
        'start_min_us': 500.0,
        'bit_low_us': 50.0,
        'bit_one_us': 40.0,
    }

    # ---------------- 输出帧类型 ----------------
    result_types = {
        'dht_start': {
            'format': 'START  {{data.duration}}'
        },
        'dht_response': {
            'format': 'RESPONSE  {{data.duration}}'
        },
        'dht_data': {
            'format': 'RH {{data.humidity}}%  /  T {{data.temperature}} C'
        },
        'dht_error': {
            'format': 'ERR  {{data.info}}'
        },
        'dht_bit': {
            'format': 'bit{{data.index}}={{data.value}} ({{data.high_us}}us)'
        },
    }

    # ---------------- 初始化 ----------------
    def __init__(self):
        # 生效的阈值：设置项非 0 用设置值，0（默认）用按型号自动值
        self.eff_start_min = self._pick(self.start_min_us, self.AUTO['start_min_us'])
        self.eff_bit_low = self._pick(self.bit_low_us, self.AUTO['bit_low_us'])
        self.eff_bit_one = self._pick(self.bit_one_us, self.AUTO['bit_one_us'])

        self.prev_time = None      # 上一个下降沿时刻
        self.state = 'idle'        # idle -> response -> bits
        self.bits = []             # [(值, 高电平us, 起始时刻, 结束时刻), ...]
        self.bits_start_time = None

        print('[DHT HLA] 型号=%s；阈值 start_min=%.0fus bit_low=%.0fus bit1>%.0fus%s'
              % (self.sensor_type, self.eff_start_min, self.eff_bit_low,
                 self.eff_bit_one,
                 '（自动）' if not self.start_min_us else '（手动）'))

    @staticmethod
    def _pick(value, auto_value):
        """0 或非法值 → 用自动值。"""
        try:
            v = float(value)
        except Exception:
            return auto_value
        return v if v > 0 else auto_value

    # ---------------- 工具 ----------------
    @staticmethod
    def _delta_us(t0, t1):
        """两个 SaleaeTime 之差，单位 µs。"""
        try:
            return float(t1 - t0) * 1e6
        except Exception:
            try:
                return (float(t1) - float(t0)) * 1e6
            except Exception:
                return None

    @staticmethod
    def _fmt(us):
        if us is None:
            return '?'
        if us < 1000.0:
            return '%.1f us' % us
        return '%.3f ms' % (us / 1000.0)

    def _reset(self):
        self.state = 'idle'
        self.bits = []
        self.bits_start_time = None

    # ---------------- 主解码 ----------------
    def decode(self, frame: AnalyzerFrame):
        try:
            return self._decode(frame)
        except Exception as e:      # 不让异常把整个 HLA 弄挂
            print('[DHT HLA] decode exception: %r' % (e,))
            return None

    def _decode(self, frame: AnalyzerFrame):
        t = frame.start_time
        if self.prev_time is None:
            self.prev_time = t
            return None

        dt = self._delta_us(self.prev_time, t)
        t0 = self.prev_time
        self.prev_time = t
        if dt is None:
            return None

        # ---- 超长间隔 = 新的一帧开始 ----
        if dt >= self.eff_start_min:
            out = []
            if self.state == 'bits' and self.bits:
                if len(self.bits) >= 32:
                    # 上一帧读数已完整（只是校验位没采全）→ 照常出读数
                    out.extend(self._finish(t0, len(self.bits) >= 39))
                else:
                    out.append(AnalyzerFrame(
                        'dht_error', self.bits_start_time, t0,
                        {'info': '帧未收满：只收到 %d 个位' % len(self.bits)}))
            self._reset()
            self.state = 'response'
            out.append(AnalyzerFrame('dht_start', t0, t,
                                     {'duration': self._fmt(dt)}))
            return out

        # ---- 起始之后的第一个间隔 = 从机响应 ----
        if self.state == 'response':
            self.state = 'bits'
            self.bits = []
            self.bits_start_time = t
            return [AnalyzerFrame('dht_response', t0, t,
                                  {'duration': self._fmt(dt)})]

        # ---- 数据位 ----
        if self.state == 'bits':
            high = dt - self.eff_bit_low
            bit = 1 if high > self.eff_bit_one else 0
            idx = len(self.bits)                    # 0..38（第 39 位不可测）
            self.bits.append((bit, high, t0, t))

            if self.show_bit_frames == 'Yes':
                return [AnalyzerFrame('dht_bit', t0, t, {
                    'index': idx,
                    'value': bit,
                    'high_us': '%.0f' % high,
                })]

            # 39 个位间隔全部收到 → 出结果（含校验比对）
            if len(self.bits) >= 39:
                result = self._finish(t, True)
                self._reset()
                return result
            # ★ 收满 32 位就先出读数（bit32..39 是校验和，湿度/温度 4 字节已完整）。
            #   实测教训：捕获窗口经常正好在最后一个下降沿（≈起始后 24.1ms）之前结束，
            #   若死等 39 位就永远出不了结果（用户实测：终端只有初始化、没有 raw=）。
            #   位 32 之后的后续沿会因 state 已复位而被忽略，无副作用。
            if len(self.bits) >= 32:
                result = self._finish(t, False)
                self._reset()
                return result

        return None

    # ---------------- 组帧 / 校验 / 读数 ----------------
    def _finish(self, end_time, full):
        """full=True：40 位里的 39 个间隔都收到了（可校验）；False：只有前 32 位（读数有效）。"""
        bits = [b[0] for b in self.bits]
        span_start = self.bits_start_time
        n_bits = len(bits)

        data = []
        for i in range(0, 39, 8):
            byte = 0
            for b in bits[i:i + 8]:
                byte = (byte << 1) | b
            data.append(byte)                        # 前 4 字节完整，第 5 字节只有高 7 位
        while len(data) < 5:
            data.append(0)

        b0, b1, b2, b3 = data[0], data[1], data[2], data[3]
        expected = (b0 + b1 + b2 + b3) & 0xFF

        if full:
            # data[4] 只有 7 个位（bit32..38），它的值 = 校验字节的"高 7 位" = 校验和 >> 1
            recv_top7 = data[4]
            chk_ok = (recv_top7 == (expected >> 1))  # 最低位因无后续下降沿而不可测
        else:
            recv_top7 = None
            chk_ok = None                            # 校验位没采全 → 不比

        # ---- 按型号换算字节 ----
        if self.sensor_type == 'DHT22 / AM2302':
            humidity = float(((b0 << 8) | b1)) * 0.1
            raw_t = float(((b2 & 0x7F) << 8) | b3) * 0.1
            temperature = -raw_t if (b2 & 0x80) else raw_t
        else:                                        # DHT11 / DHT12
            humidity = float(b0) + float(b1) * 0.1
            temperature = float(b2) + float(b3) * 0.1

        if full:
            info = 'raw=%02X %02X %02X %02X (chk~%02X / exp %02X, 末位不可测) %s' % (
                b0, b1, b2, b3, (recv_top7 << 1), expected,
                'OK' if chk_ok else 'BAD')
        else:
            info = 'raw=%02X %02X %02X %02X（捕获只含 %d 位 → 湿度/温度有效，校验未比对）' % (
                b0, b1, b2, b3, n_bits)
        print('[DHT HLA] %s' % info)

        # 校验明确失败才报错；没采全校验位的场合读数仍然有效
        if full and not chk_ok:
            return [AnalyzerFrame('dht_error', span_start, end_time, {
                'info': '校验失败 %s' % info,
            })]
        return [AnalyzerFrame('dht_data', span_start, end_time, {
            'humidity': ('%.1f' % humidity),
            'temperature': ('%.1f' % temperature),
        })]
