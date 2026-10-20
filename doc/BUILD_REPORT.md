# MyDAPLink_F103 构建实测报告

> 本报告所有数据均为**本机实际编译产出**，非推算。
> 初版构建：2026-10-15 ｜ 当前固件重编：**2026-10-16（`mydaplink-v1.0-g9064ad6`）**
> 工具链：Arm GNU Toolchain **12.2.rel1**（mingw-w64-i686）

---

## 1. 产物清单（`out/`）

| 文件 | 大小 | 用途 |
|------|------|------|
| `MyDAPLink_BL.hex` / `.bin` | 48128 B | **Bootloader**，烧 `0x08000000` |
| `MyDAPLink_IF.hex` / `.bin` | 80896 B | **Interface（通用 target）**，烧 `0x0800C000` |
| `MyDAPLink_IF_MSC.hex` / `.bin` | 80896 B | **Interface（target=F103RB，带虚拟U盘）** |
| `magic/START_BL.ACT` | 2 B（`BL`） | MSC 拖拽切回 Bootloader 的魔数文件 |

> **IF 二选一**：
> - `MyDAPLink_IF` = 通用 target 版，**无 MSC 虚拟盘**；
> - `MyDAPLink_IF_MSC` = 目标板指定 F103RB 版，**有 MSC 虚拟盘**（拖拽烧录）。
> 两者其余功能完全一致。

---

## 2. 编译统计

| 工程 | text | data | bss | 合计(dec) | 内存占用 |
|------|------|------|-----|-----------|----------|
| `stm32f103xb_bl` | 33404 | 14724 | 8822 | **56950** | m_text 100%、m_data 45.29%、m_cfgram 55.47% |
| `stm32f103xb_if` | 61876 | 19020 | 10880 | **91776** | m_text 100%、m_data 56.53%、m_cfgram 55.47% |
| `stm32f103xb_stm32f103rb_if` | — | — | — | — | 同 IF 量级 |

链接期出现 4 条 `_close/_lseek/_read/_write is not implemented` **警告**（newlib nano 桩函数），
以及 `LOAD segment with RWX permissions` 警告——均为**正常现象**，不影响功能。
（这正是 `-Wl,-fatal-warnings` 必须注释掉的原因。）

---

## 3. 固件内部结构核对（`tools/hex_inspect.py` 实测）

### BL — `MyDAPLink_BL.hex`

| 项 | 实测值 |
|----|--------|
| 地址范围 | `0x08000000 – 0x0800BBFF` |
| 跨度 | 48128 B (0xBC00) ✅ 与 `DAPLINK_ROM_BL_SIZE` 吻合 |
| 空洞 | 无，区间连续 |
| 首 8 字节 | `00 4F 00 20 7D 04 00 08` |
| → 初始 SP | `0x20004F00` |
| → Reset_Handler | `0x0800047D`（bit0=1，Thumb，正常） |
| 末 4 字节 CRC | **`0x3E08754F`** |

### IF — `MyDAPLink_IF.hex`

| 项 | 实测值 |
|----|--------|
| 地址范围 | `0x0800C000 – 0x0801FBFF` |
| 跨度 | 80896 B (0x13C00) ✅ 与 `DAPLINK_ROM_IF_SIZE` 吻合 |
| 空洞 | 无，区间连续 |
| 首 8 字节 | `00 4F 00 20 7D C4 00 08` |
| → 初始 SP | `0x20004F00` |
| → Reset_Handler | `0x0800C47D` |
| 末 4 字节 CRC | **`0x9115E7D9`** |

### IF(MSC) — `MyDAPLink_IF_MSC.hex`

| 项 | 实测值 |
|----|--------|
| 地址范围 | `0x0800C000 – 0x0801FBFF`（同 IF） |
| 末 4 字节 CRC | **`0xC805F60C`** |

---

## 4. 引脚与工具链

| 项 | 值 |
|----|----|
| SWCLK / SWDIO / nRESET / POWER_EN | **PB6 / PB7 / PB8 / PB9** |
| LED | PC13（板载） |
| 工具链 | Arm GNU Toolchain 12.2.rel1 |
| BL Reset_Handler | `0x0800047D` |
| IF Reset_Handler | `0x0800C47D` |

> 每个构建的 CRC 都不同（由 post_build 现算现写），上表的 CRC 可作为本次产物的指纹，
> 用来核对 `out/` 里的固件没被替换或损坏。

---

## 5. 环境备忘（★ 作者本机特有，仅供参考）

> ⚠️ **【其他使用者注意】** 下面这张表记录的是**作者编译时那台机器**的环境，**不是你必须具备的条件**。
> 其中 `C:/Tools/ArmGNU/...` 是作者本机的工具链安装路径，你机器上必然不同。
> 把它当成「一张环境对照表」看待，看不懂的项直接忽略。
> 要自己重新编译，请以 `README.md` 第 12 节列出的准备清单为准。

| 项 | 情况 |
|----|------|
| `arm-none-eabi-gcc` | `C:/Tools/ArmGNU/.../12.2.rel1-minw-w64-i686` ✅（**作者本机路径，仅为示例**） |
| **系统 `make`** | ❌ **不存在** → 已随包放便携版 `tools/bin/make.exe`（GNU Make 4.4.1） |
| Python | `.venv`（Python 3.13.14）+ `project_generator 0.11.3`（**本精简版不含 `.venv`**，需自建） |
| mbed-os | `bf6f2c3c...`（解压后约 491 MB；**本精简版已移除**，要重编译须先补回） |
| git 仓库 | `src/upstream` 已 init + commit + `tag mydaplink-v1.0`（**本精简版不含 `.git`**，需自建） |
| 版本头 | `GIT_DESCRIPTION = mydaplink-v1.0-g9064ad6`（由 git tag 生成，没有 `.git` 就编不出来） |

---

## 6. 验证状态与注意事项

### 6.1 已确认（上板实测通过）

**① CMSIS-DAP 探针路径**（2026-10-15）

- ✅ **产物已烧到真机并全链路验证**：探针枚举正常（CMSIS-DAP v2，FW Version 2.1.0）；
  以 **100 kHz** 连接目标板成功（`Examination succeed`、`target has 6 breakpoints, 4 watchpoints`）；
  烧录目标程序 `wrote 4668 bytes` / `verified 4668 bytes`；
  GDB `compare-sections` 六段（`.isr_vector` / `.text` / `.rodata` / `.init_array` / `.fini_array` / `.data`）**全部 matched**。
- ✅ 探针自身 SWD 引脚（PB6~PB9）在实物 Blue Pill 上**无板载外设冲突**。

**② MSC 拖拽烧录路径**（2026-10-16，固件 `mydaplink-v1.0-g9064ad6`）

- ✅ 虚拟盘枚举：卷标 `DAPLINK`、FAT、64 MB；`DETAILS.TXT` 自报
  `Build ID: mydaplink-v1.0-g9064ad6`、`Interface CRC: 0xc805f60c`、`USB Interfaces: MSD, CDC, HID, WebUSB`。
- ✅ 拖 `LEDTEST.hex` → 目标 flash 回读与 `LEDTEST.bin` **前 4668 B 逐字节一致**，尾部保持 `0xFF`；
  目标 PC13 实测以 10 Hz 翻转。**重复两次均一致**。
- ✅ 拖 `ERASE.ACT` → 目标 flash 全片变为 `0xFF`。
- ✅ 免 ST-Link 升级：拖 `START_BL.ACT` → 盘变 `MAINTENANCE`（`Daplink Mode: Bootloader`）→
  拖新 IF 固件 → 自动回 IF 模式，版本号同步更新。

### 6.2 注意事项

- ⚠️ **SWD 速度是最大的坑**：实测 1000 kHz 及以上必挂、500 kHz 时好时坏、**100~250 kHz 稳定**。
  固件内 `DAP_DEFAULT_SWJ_CLOCK` 已下调到 **100 kHz** 以适配杜邦线；
  换更短的杜邦线（<15 cm）可提高可用速度。详见 `README.md` §6.3。
- ⚠️ 拖拽烧录失败时只会在盘里留 `FAIL.TXT`；而 `ERASE.ACT` 擦除失败**完全静默**
  （`vfs_user.c:233` 丢弃了 `erase_target()` 的返回值），排查时需用 OpenOCD 回读确认。
- ⚠️ `POWER_EN`(PB9) 默认输出低 = **不向目标供电**，目标板须单独上电。
- ⚠️ **【其他使用者注意】** 第 5 节「环境备忘」里凡是带路径的项（`C:/Tools/ArmGNU/...`、
  `.venv`、`mbed-os`、`.git`）都是**作者本机的**，你那边不必相同，也不影响你直接使用 `out/` 里的固件。
