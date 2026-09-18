# DHT Analyzer for Saleae Logic 2

A High Level Analyzer (HLA) extension that decodes the **DHT11 / DHT12 / DHT22 (AM2302)**
single-wire temperature & humidity protocol, and prints the result as a bubble directly
on the waveform:

```
START 20.049 ms   →   RESPONSE 210.0 us   →   RH 33.0%  /  T 28.0 C
```

---

## 1. Requirements

* **Saleae Logic 2** (tested on **2.4.46**; requires the Extensions / HLA API)
* Any Saleae device (verified with **Logic 16**)
* Sample rate **≥ 4 MS/s** (narrowest pulse is 27 µs; 10–25 MS/s recommended)
* The **built-in "Simple Parallel"** analyzer is used as an *edge sampler* (see §3 for why)

## 2. Installation

1. Copy the whole **`DHT Analyzer`** folder into the Logic 2 user extension directory:

   | OS | Path |
   |---|---|
   | Windows | `C:\Users\<you>\Documents\Logic\High Level Analyzers\DHT Analyzer\` |
   | macOS | `~/Documents/Logic/High Level Analyzers/DHT Analyzer/` |
   | Linux | `~/Documents/Logic/High Level Analyzers/DHT Analyzer/` |

2. **Restart Logic 2** — analyzers are only loaded at application start.
3. In the right-hand **Extensions** panel, make sure *DHT Analyzer* is enabled.

## 3. Setup (one time per session)

> **Why an extra analyzer is needed:** in Logic 2 an HLA can only take another
> **low-level analyzer** as its input — it cannot be attached to a raw digital channel —
> and there is no built-in "pulse width" analyzer. So we reuse **Simple Parallel** as an
> edge sampler (it emits one frame per clock edge) and the HLA derives pulse widths from
> the time between consecutive edges.
>
> Once both analyzers are added, they **persist across captures inside the session**, so
> this is a one-time job per session.

1. Add **Simple Parallel** (analyzers panel → `+` → *Simple Parallel*):

   | Setting | Value |
   |---|---|
   | Clock Channel | the DHT data line |
   | Clock Edge | **Falling** |
   | D0 | **the same** DHT line |
   | D1 … D15 | `None` |

2. Add **DHT Analyzer** (`+` → *DHT Analyzer*), and set **Input Analyzer = Simple Parallel**.

   ⚠ If the Clock Channel is left unset, Simple Parallel produces no frames and the HLA
   stays **silently empty** (no error, empty data table). If you see edge markers + a green
   check + terminal init lines but no decoded frames — re-check the clock channel.

3. Set the sample rate, trigger on a **falling edge** of that channel, and capture one read.

### Settings (only "Sensor Type" is normally needed)

| Setting | Default | Meaning |
|---|---|---|
| Sensor Type | `DHT11` | `DHT11` / `DHT12` / `DHT22 / AM2302` (different byte layout) |
| Start Interval Min (us) | `0` → **auto 500** | Edges farther apart than this start a new frame |
| Bit Low Width (us) | `0` → **auto 50** | Low time between bits (nominal 50 µs) |
| Bit 1 Threshold (us) | `0` → **auto 40** | High time above this = bit 1 (0≈27 µs, 1≈70 µs) |
| Show Bit Frames | `No` | One bubble per bit — useful when debugging timing |

`0` means *automatic*: Logic 2 initializes numeric settings to `min_value` (this API version
has no default support), so `min_value = 0` is used as the "auto" sentinel.

## 4. Protocol reference

| Phase | Level | Duration |
|---|---|---|
| Host start | LOW | **≥ 18 ms** (20 ms typical) |
| After host release | HIGH | 20–40 µs |
| Sensor response | LOW / HIGH | **80 µs** each |
| Inter-bit gap | LOW | **~50 µs** (constant) |
| Bit `0` | HIGH | 26–28 µs |
| Bit `1` | HIGH | **~70 µs** |

One frame = start + response + **40 bits**:
`humidity integer / humidity decimal / temperature integer / temperature decimal / checksum`
where `checksum = (b0 + b1 + b2 + b3) & 0xFF`.

## 5. Known limitations

* The **last bit (bit 39)** is not measurable — there is no falling edge after it. It is the
  **LSB of the checksum**, so humidity & temperature (bytes 0–3) are still complete, and the
  checksum is compared on its upper 7 bits only (the terminal notes `末位不可测 / LSB
  unmeasurable`).
* If the capture window ends before the last falling edge (≈ **24.1 ms** after the start),
  the plugin emits the reading as soon as **32 bits** are available (bytes 0–3 complete) and
  skips the checksum comparison. Extend the capture to 50–100 ms to get the checksum too.

## 6. Troubleshooting

| Symptom | Check |
|---|---|
| No bubbles at all | Simple Parallel Clock Channel set? Edge = Falling? D0 = same line? |
| Only `START`, no `RESPONSE` | Sample rate too low, or the sensor did not answer (4.7 kΩ pull-up, VCC/GND, wiring) |
| Values look wrong | Wrong Sensor Type (DHT11 = 1 byte, DHT22 = 16-bit / 0.1) |
| Checksum mismatch | Turn on *Show Bit Frames* and inspect pulse widths; adjust *Bit Low Width* / *Bit 1 Threshold* |

The plugin prints to the Logic 2 terminal, e.g.

```
[DHT HLA] 型号=DHT11；阈值 start_min=500us bit_low=50us bit1>40us（自动）
[DHT HLA] raw=21 00 1C 00 (chk~3C / exp 3D, 末位不可测) OK
```

## 7. License

MIT — see [LICENSE](LICENSE).

---
---

# DHT Analyzer for Saleae Logic 2（中文说明）

一个 Logic 2 **高级分析器（HLA）扩展**，用于解码 **DHT11 / DHT12 / DHT22 (AM2302)** 单总线
温湿度协议，并直接在波形上打出气泡：

```
START 20.049 ms   →   RESPONSE 210.0 us   →   RH 33.0%  /  T 28.0 C
```

## 1. 环境要求

* **Saleae Logic 2**（在 **2.4.46** 上验证；需要扩展/HLA API）
* 任意 Saleae 设备（已在 **Logic 16** 上验证）
* 采样率 **≥ 4 MS/s**（最窄脉宽 27 µs，推荐 10–25）
* 需要借助内置的 **Simple Parallel** 作为"边沿采样器"（原因见 §3）

## 2. 安装

1. 把整个 **`DHT Analyzer`** 目录复制到 Logic 2 用户扩展目录：

   | 系统 | 路径 |
   |---|---|
   | Windows | `C:\Users\<你>\Documents\Logic\High Level Analyzers\DHT Analyzer\` |
   | macOS / Linux | `~/Documents/Logic/High Level Analyzers/DHT Analyzer/` |

2. **重启 Logic 2**（分析器只在启动时加载）
3. 右侧 **Extensions** 面板里确认 *DHT Analyzer* 已启用

## 3. 设置（每个会话一次）

> **为什么还要配一个分析器：** Logic 2 的 HLA **输入源只能是底层分析器**，不能直连数字
> 通道；而内置分析器里没有"脉宽解码器"。因此借用 **Simple Parallel** 在**每个时钟沿**产出
> 一帧，HLA 再用相邻沿的时间差还原脉宽。两个分析器加好后，**同一会话内再次采集会保留**，
> 所以只是一次性工作。

1. 添加 **Simple Parallel**：

   | 设置 | 值 |
   |---|---|
   | Clock Channel | DHT 数据线 |
   | Clock Edge | **Falling（下降沿）** |
   | D0 | **同一根** DHT 线 |
   | D1 … D15 | `None` |

2. 添加 **DHT Analyzer**，`Input Analyzer` 选 **Simple Parallel**

   ⚠ 若 Clock Channel 漏选，Simple Parallel 不出帧 → HLA **静默无输出**（不报错、Data 表空）。
   判据：波形有红点 + HLA 绿勾 + 终端有初始化行，但没有解码帧 → 先查时钟通道。

3. 设好采样率，用该通道**下降沿触发**，抓一次读取。

### 设置项（通常只需选 Sensor Type）

| 设置 | 默认 | 含义 |
|---|---|---|
| Sensor Type | `DHT11` | `DHT11` / `DHT12` / `DHT22 / AM2302`（字节格式不同） |
| Start Interval Min (us) | `0` → 自动 **500** | 间隔大于它即判定为新帧起始 |
| Bit Low Width (us) | `0` → 自动 **50** | 位间低电平（标称 50 µs） |
| Bit 1 Threshold (us) | `0` → 自动 **40** | 位高电平超过它判为 1（0≈27 µs，1≈70 µs） |
| Show Bit Frames | `No` | 逐位出气泡，排查时序很有用 |

`0` 表示"自动"：本版本 API 不支持设置默认值，UI 会把数值设置初始化为 `min_value`，
所以把 `min_value` 设为 0 作为"自动"哨兵值。

## 4. 协议时序

| 阶段 | 电平 | 时长 |
|---|---|---|
| 主机起始 | LOW | **≥18 ms**（常见 20 ms） |
| 主机释放后 | HIGH | 20–40 µs |
| 从机响应 | LOW / HIGH | 各 **80 µs** |
| 位间隔 | LOW | **~50 µs**（恒定） |
| 数据位 0 | HIGH | 26–28 µs |
| 数据位 1 | HIGH | **~70 µs** |

一帧 = 起始 + 响应 + **40 位**：`湿度整数/湿度小数/温度整数/温度小数/校验和`，
`校验和 = (b0+b1+b2+b3) & 0xFF`。

## 5. 已知限制

* **bit39 测不到**（其后没有下降沿），它是**校验和的最低位**；湿度/温度（前 4 字节）完整，
  校验只比对高 7 位（终端会注明"末位不可测"）。
* 若捕获窗口在最后一个下降沿（起始后 ≈**24.1 ms**）之前结束，插件收到 **32 位**就先出读数
  （前 4 字节已完整），跳过校验比对；把捕获延长到 50–100 ms 即可拿到校验。

## 6. 排错

| 现象 | 检查 |
|---|---|
| 完全没有气泡 | Simple Parallel 的 Clock Channel 选了吗？Edge=Falling？D0 是否同一根线？ |
| 只有 START 没有 RESPONSE | 采样率过低，或传感器没应答（4.7 kΩ 上拉、VCC/GND、接线） |
| 值明显不对 | 型号选错（DHT11 单字节，DHT22 是 16 位/0.1） |
| 校验失败 | 打开 Show Bit Frames 看脉宽；调 Bit Low Width / Bit 1 Threshold |

## 7. 授权

MIT，见 [LICENSE](LICENSE)。
