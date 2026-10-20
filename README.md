# MyDAPLink_F103 — 一个自己做的 DAPLink 烧录器

> 一块 **STM32F103C8T6**（Blue Pill）烧进 **两个固件**，就变成一台完整的
> **DAPLink 调试探针**，可以给别的 ARM Cortex-M 芯片**烧录 / 调试**。
>
> 源码取自 ARM 官方 `ARMmbed/DAPLink`（Apache-2.0），引脚分配、包结构、工具脚本、
> 文档全部自己设计。本机已用 Arm GNU Toolchain 12.2 编译通过，产出 3 个可烧固件。

> 📦 **这是「精简版」**（30 MB）。作者本机另有一个完整的开发版（806 MB，在**作者机器**的 `E:\MyDAPLink_F103\`，
> 这个路径只是为了说明差异，**你的电脑上不会有这个文件夹**）。两者**固件完全相同**。本版为便于**使用 / 拷贝 / 存档**，移除了下面这些「重新编译时才需要」的东西：
>
> | 已移除 | 大小 | 影响 |
> |---|---|---|
> | `src/upstream/mbed-os/` | 491 MB | 编译依赖库。**不影响烧固件**；要重新编译需先补回（见第 12 节） |
> | `src/upstream/projectfiles/` | 143 MB | 编译中间产物（`.o`、生成的 Makefile），可再生成 |
> | `.venv/` | 140 MB | Python 构建环境，可再建 |
> | `src/upstream/.git/` | 3.8 MB | 源码版本库，可再 init |
>
> **保留且完整**：`out/`（3 个可烧固件）、`README.md`、`doc/`、`tools/`、`rescue/`、
> `src/upstream/source/`（全部源码，含改好的 `IO_Config.h` / `gpio.c`）。
>
> **只用来烧固件的话，直接看第 4 节即可，本版开箱即用。**

---

> ## ⚠️ 拿到这个包的其他人请注意
>
> 这个包是**可搬移**的——整个文件夹拷到任意盘符、任意目录都能用，**但下面这几处必须改成你自己的**：
>
> | 要改什么 | 出现在哪 | 改成什么 |
> |---|---|---|
> | `E:\MyDAPLink_F103\` | 本文件顶部说明、`doc/` 里的说明 | 那是**作者本机**的完整版路径，你没有这个文件夹，忽略即可 |
> | `COM3` | 第 10 节救砖命令、`rescue/isp_rescue.py` | 你电脑上 USB-TTL 实际占用的 COM 口 |
> | `E:/LEDTEST.elf` | `tools/verify_flash.gdb` | 你自己目标程序的 `.elf` 路径 |
> | `<你的目标程序.elf>` | 第 7.1 节 GDB 命令、第 7.1 节 `arm-none-eabi-gdb` | 你自己的 `.elf` 路径 |
> | `source tools/verify_flash.gdb` | 第 7.1 节 | 建议换成**绝对路径**（原因见该处备注） |
>
> **两个需要你自己装的前提**（包里不含、也不便随包分发）：
> - `openocd`、`arm-none-eabi-gdb` —— 装好后必须**加入 PATH**，自检：`openocd --version` 能打印版本号；
> - 只有在**想重新编译**时才需要 `arm-none-eabi-gcc`、Python、GNU make，而且**必须先按第 12 节把 mbed-os 补回来**（本精简版已移除）。
>
> **还有一条最省事的规矩**：手册里所有 `out/xxx.hex`、`tools/xxx`、`rescue/xxx` 都是**相对路径**，
> 请先 `cd` 到本包根目录再执行命令，否则会报 `No such file or directory`。

---

## 目录

1. [这是什么](#1-这是什么)
2. [你需要准备什么](#2-你需要准备什么)
3. [包结构](#3-包结构)
4. [第一步：把固件烧进探针芯片](#4-第一步把固件烧进探针芯片)
5. [第二步：验证探针是否就绪](#5-第二步验证探针是否就绪)
6. [第三步：把探针接到目标板](#6-第三步把探针接到目标板)
7. [第四步：用探针烧录 / 调试目标板](#7-第四步用探针烧录--调试目标板)
8. [日常使用：升级、切 Bootloader、拖拽烧录](#8-日常使用升级切-bootloader拖拽烧录)
9. [常见问题排查](#9-常见问题排查)
10. [刷坏了怎么救（串口 ISP）](#10-刷坏了怎么救串口-isp)
11. [固件清单与校验值](#11-固件清单与校验值)
12. [自己重新编译（可选）](#12-自己重新编译可选)
13. [它能烧哪些芯片？为什么有的 ARM 不支持](#13-它能烧哪些芯片为什么有的-arm-不支持)

---

## 1. 这是什么

把一颗普通的 STM32F103 变成「**电脑 ⟷ 目标芯片**之间的桥」：

```
   电脑 (OpenOCD / pyOCD / Keil)          目标板 (任意 ARM Cortex-M)
        │                                        │
        │ USB (CMSIS-DAP v2)                     │ SWD (2 线)
        ▼                                        ▼
   ┌──────────────────────────────────────────────────┐
   │            STM32F103C8T6 探针                     │
   │   固件 = Bootloader(BL) + Interface(IF)           │
   └──────────────────────────────────────────────────┘
```

变成探针后，它通过 USB 向电脑暴露这几样东西：

| USB 接口 | 用途 |
|---|---|
| **CMSIS-DAP v2** | 调试/烧录主通道，给 OpenOCD、pyOCD、Keil、IAR 用 |
| **CDC (虚拟串口)** | 多出一个 COM 口，可当串口调试用 |
| **MSC (大容量存储)** | 多出一个「U 盘」，把 hex/bin 拖进去即可烧录（**需用 MSC 版固件**） |
| **HID** | 部分免驱场景 |

底层向目标芯片走的是 **SWD** 协议（SWCLK + SWDIO 两根信号线）。

---

## 2. 你需要准备什么

| 物品 | 说明 |
|---|---|
| **探针芯片** | 一块 **STM32F103C8T6**，而且 Flash 必须是 **128KB**（多数 Blue Pill 是 128KB，少数是 64KB——64KB 装不下，见下方验证方法） |
| **烧探针用的调试器** | 一个 **ST-Link**（或 J-Link，甚至另一块 DAPLink）——首刷 BL、以及「IF 挂不出盘」时才用；日常升级 IF 可走维护盘，不必接（什么时候必须用它，见 **§8.5**） |
| **杜邦线** | 建议 **短一些（<15cm）**，SWD 对线长敏感 |
| **目标板** | 任意要调试的 **ARM Cortex-M** 芯片（STM32、GD32、NRF、LPC……）—— 完整支持范围与限制见 **§13** |
| **电脑软件** | `openocd`、`arm-none-eabi-gdb`（可选 pyOCD、Keil、IAR） |

**先确认你的 F103 是 128KB**（用 ST-Link 读一下，或看芯片丝印/已知板型）：

```bash
# 用 ST-Link + st-info 查容量
st-info --probe
# 看 "flash:" 一行，应为 128k（0x20000）。64k 的板子无法使用本固件。
```

> ⚠️ **【其他使用者注意】** `st-info` 属于 `stlink-tools`，需要你自己安装。没装的话，也可以直接用第 4 节的方式烧一次看结果，或看芯片丝印/已知板型。

> ⚠️ **【其他使用者注意】** 本手册所有命令都假定 `openocd`、`arm-none-eabi-gdb`、`st-flash` 已经装好并且**在 PATH 里**。
> 动手前先自检一句：`openocd --version` —— 能打印版本号才继续。
> （Windows 上 `openocd` 可以从 xPack 或 ST 官网获取；`arm-none-eabi-gdb` 随 Arm GNU Toolchain 一起安装。）

---

## 3. 包结构

```
MyDAPLink_F103/
├── README.md                 # 本文档
├── build.sh                  # 重新编译用（./build.sh bl | if | if-rb）
├── out/                      # ★ 编译好的固件，拿去烧的就是这里
│   ├── MyDAPLink_BL.hex / .bin        # Bootloader   → 0x08000000
│   ├── MyDAPLink_IF.hex / .bin        # Interface    → 0x0800C000（通用版，无U盘）
│   ├── MyDAPLink_IF_MSC.hex / .bin    # Interface    → 0x0800C000（带虚拟U盘）
│   └── magic/START_BL.ACT             # 魔数文件，拖进U盘可切回 Bootloader
├── tools/
│   ├── hex_inspect.py        # Intel HEX 解析器（看穿地址 / 向量表 / CRC）
│   ├── verify_flash.gdb      # GDB 只读自检脚本（比对 Flash 与 elf）
│   └── bin/make.exe          # 便携版 GNU Make 4.4.1（本机无系统 make 时用）
├── rescue/
│   └── isp_rescue.py         # 串口 ISP 救砖脚本（AN3155，8E1 偶校验）
├── doc/
│   ├── BUILD_REPORT.md       # 编译实测报告
│   ├── DESIGN.md             # 引脚设计与源码改动说明
│   └── MyDAPLink_使用手册.html  # 本文的网页版（更好读）
└── src/
    └── upstream/             # DAPLink 官方源码（source/ 完整，含改好的引脚）
        ├── projects.yaml     # 工程声明
        ├── records/          # 板级 / 芯片级配置
        ├── mbed-os.lib       # 依赖指针（指向 mbed-os 的 commit；精简版未含实体）
        └── source/hic_hal/stm32/stm32f103xb/
            ├── IO_Config.h   # ★ 引脚定义（PB6/PB7/PB8/PB9）
            └── gpio.c        # ★ SWJ 设置（保留自身 SWD，防变砖）
```

> 注：精简版不含 `mbed-os/`、`projectfiles/`、`.venv/`、`.git/` —— 这些只在**重新编译**时用到。

---

## 4. 第一步：把固件烧进探针芯片

> 此刻它还只是一块**普通 F103**，必须用**外部调试器**（ST-Link）来烧。
> 要烧的是 `out/` 里两个文件：**先 BL，后 IF**。

### 4.1 接线（ST-Link → 探针芯片）

| ST-Link | 探针 F103 |
|---|---|
| SWCLK | PA14 |
| SWDIO | PA13 |
| GND | GND |
| 3.3V | 3.3V |

### 4.2 烧录（三种方式任选其一）

**方式 A：OpenOCD（推荐，以下命令已实测通过）**

> ⚠️ **【其他使用者注意】** 下面命令里的 `out/MyDAPLink_BL.hex` 是**相对路径**，请先 `cd` 到本包根目录，
> 或改成固件的绝对路径（例如 `D:/MyDAPLink_F103_精简版/out/MyDAPLink_BL.hex`）。
> 另外 `-f interface/stlink.cfg` 是针对 **ST-Link** 的；若你用的是 J-Link 或别的 CMSIS-DAP 调试器，要换成对应的 interface 配置文件。

```bash
# 注意：hex 文件「自带地址」，命令里不要再写地址！
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
  -c "init; reset halt" \
  -c "flash write_image erase out/MyDAPLink_BL.hex" \
  -c "flash write_image erase out/MyDAPLink_IF.hex" \
  -c "reset halt" \
  -c "verify_image out/MyDAPLink_BL.hex" \
  -c "verify_image out/MyDAPLink_IF.hex" \
  -c "reset run; shutdown"
```

> ⚠️ **必看的坑（已实际踩过）**：对 `.hex` 文件**千万不要再传地址**。
> 若写成 `flash write_image erase out/MyDAPLink_BL.hex 0x08000000`，OpenOCD 会把 `0x08000000`
> 当成「偏移量」**再叠加一次**到 hex 自带地址上，地址翻倍成 `0x10000000`，于是报
> `no flash bank found for address 0x10000000` 且 `wrote 0 bytes`——**一个字节都没写进去**，
> 可日志前面却照旧打印 `** Programming Finished **`，极容易误以为烧成功了。
>
> **成功时应看到**：`wrote 48128 bytes`（BL）、`wrote 80896 bytes`（IF），
> 以及两行 `verified 48128 bytes` / `verified 80896 bytes`。

**方式 B：st-flash**

```bash
# 推荐用 .bin（内容就是该区域，需显式给起始地址）
st-flash --reset write out/MyDAPLink_BL.bin 0x08000000
st-flash --reset write out/MyDAPLink_IF.bin 0x0800C000

# 也可直接用 .hex（st-flash 会读取 hex 内部地址，无需再给地址）
# st-flash --reset write out/MyDAPLink_BL.hex
# st-flash --reset write out/MyDAPLink_IF.hex
```

**方式 C：STM32CubeProgrammer（图形界面）**

1. 连接 ST-Link → 选 `STM32F103C8`；
2. 打开 `out/MyDAPLink_BL.hex` → 烧录（地址一般自动填 `0x08000000`）；
3. 再打开 `out/MyDAPLink_IF.hex` → 确认起始地址是 `0x0800C000` → 烧录。

> **MSC 版提醒**：如果你想要「拖拽 U 盘烧录」，把第二步的 `MyDAPLink_IF.hex`
> 换成 `MyDAPLink_IF_MSC.hex`（地址同样 `0x0800C000`）。两者只能选一个烧。

### 4.3 烧完做什么

- **拔掉 ST-Link**；
- 把探针芯片的 **USB 口插到电脑**（Blue Pill 上是 PA11/PA12 那个 USB 口）；
- 进入下一步验证。

---

## 5. 第二步：验证探针是否就绪

插入 USB 后，Windows 里应该**多出这些设备**。打开设备管理器，或跑：

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*VID_0D28*' } |
  Format-Table Status, FriendlyName, InstanceId -AutoSize
```

**期望看到**（`Status` 全部为 `OK`）：

| FriendlyName | 说明 |
|---|---|
| USB Composite Device | 复合设备总入口 |
| CMSIS-DAP v2 | 调试通道 ✅ 关键 |
| USB 串行设备 (COMx) | 虚拟串口 |
| USB 输入设备 | HID |
| （若烧了 MSC 版）可移动磁盘 | 虚拟 U 盘 |

再用 OpenOCD「空连」一次，确认探针本身活着（**此时目标板先不接**）：

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "adapter speed 100"
```

**探针正常时**应看到：

```
Info : CMSIS-DAP: FW Version = 2.1.0
Info : CMSIS-DAP: Interface ready
Info : clock speed 100 kHz
```

这时因为**目标板没接**，后面会报 `cannot read IDR` 之类的错——**这是正常的**，说明探针已经就绪、在等目标板。按 `Ctrl+C` 退出即可。

---

## 6. 第三步：把探针接到目标板

探针的 SWD 目标接口在本设计里固定在 **PB6 ~ PB9**（连续四脚，可做一排 4P 排针整体对插）。

### 6.1 引脚对照

| # | 探针 | 目标板 | 作用 | 必接？ |
|---|------|--------|------|--------|
| 1 | **PB6** | SWCLK（STM32 上是 PA14） | 时钟 | ✅ 必接 |
| 2 | **PB7** | SWDIO（STM32 上是 PA13） | 数据（单脚双向） | ✅ 必接 |
| 3 | **GND** | GND | 共地 | ✅ 必接 |
| 4 | **PB8** | NRST | 复位 | ⚠️ 见下 |
| 5 | 3.3V | VCC | 供电 | ⚠️ 见下 |
| — | **PB9** | — | POWER_EN（本设计的可控供电） | ❌ 默认不用 |

### 6.2 两个必须注意的点

> ⚠️ **① 供电**：`PB9 = POWER_EN` **默认输出低**，即探针**不向目标板供电**。
> 目标板必须**自己单独上电**（插自己的 USB 或接独立 3.3V 电源）。
> 你也可以把探针的 `3.3V` 接到目标板 `VCC` 给它供电，但要确认电流够。

> ⚠️ **② NRST 通常不是必需的**：大多数板子接 3 根线（PB6/PB7/GND）就能用。
> 只有个别目标板需要补上 PB8→NRST 才能进调试态。

### 6.3 SWD 速度：从 500 kHz 起，不要一上来就 1 MHz ★实测坑

这是本设计**实测踩过的最大的坑**，优先级最高：

| SWD 速度 | 实测结果 |
|---|---|
| 2000 / 1000 kHz | ❌ `Failed to read memory at 0xe000ed00`（DP 握手成功、AP 读不到） |
| 500 kHz | ⚠️ 时好时坏，不可靠 |
| **250 kHz** | ✅ 稳定成功 |
| **100 kHz** | ✅ 稳定成功 |

**为什么会这样**：杜邦线较长、接触电阻大、无端接时，SWD 波形在高速下会失真。
而 DP 握手只是简单一问一答、容忍度高；AP 读内存是连续多字节传输、对信号完整性要求高得多。
于是表现为「**DP 通、AP 不通**」——看起来像接线或固件问题，其实是速度问题。

**做法**：

- OpenOCD 一律用 `-c "adapter speed 100"` 起步（最稳），确认通了再往上试 250 / 500。
- 换用更短的杜邦线（< 15 cm）或直接焊接排线，可显著提高可用速度。
- 出现 `Failed to read memory at 0xe000ed00` 时，**先降速**，不要先去怀疑接线或固件。

**判断"真的连上了"的唯一标志**（要看到这两行）：

```
Info : [stm32f1x.cpu] target has 6 breakpoints, 4 watchpoints
Info : [stm32f1x.cpu] Examination succeed
```

---

## 7. 第四步：用探针烧录 / 调试目标板

探针就绪、接线完成后，就可以真正干活了。下面按常用工具分几种用法。

### 7.1 用 OpenOCD + GDB（通用，推荐）

**终端 1 — 起 OpenOCD 服务（保持运行，别关）**

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "adapter speed 100"
```

**判断成功**：出现下面这两行，说明**目标板被真正识别**了：

```
Info : [stm32f1x.cpu] target has 6 breakpoints, 4 watchpoints   ← 关键行
Info : [stm32f1x.cpu] Examination succeed
```

> 如果只看到 `starting gdb server on 3333`，但前面是 `Examination failed`
> 或 `Failed to read memory`，说明目标板还没真正连上：
> **先把速度降到 100 kHz 重试**（见 §6.3），仍不行再去查接线。

**终端 2 — 开 GDB**

```bash
arm-none-eabi-gdb <你的目标程序.elf>
```

> ⚠️ **【其他使用者注意】** `<你的目标程序.elf>` 换成你自己的文件路径（路径含空格要加引号）。
> 这是**你自己要烧的目标程序，不在本包里**。终端 2 可以在任意目录启动，但下一段的
> `source tools/verify_flash.gdb` 是相对路径，要么先 `cd` 到包根目录，要么改成绝对路径。

进入 GDB 后逐行敲：

```
target extended-remote localhost:3333
monitor reset halt
load                    # 把 elf 烧进目标板 Flash
compare-sections        # 比对 Flash 与 elf 是否一致（自检）
continue                # 跑起来
```

> **注意**：GDB 里不要粘贴带 `(gdb)` 前缀或 `#` 注释的行，会报
> `Undefined command`。要么一行行敲，要么用 `source 脚本.gdb`。

**用包里的自检脚本**（快捷）：

```
(gdb) target extended-remote localhost:3333
(gdb) source tools/verify_flash.gdb
```

它会重置暂停、读向量表、比对 Flash 与 elf，只读、不改。

### 7.2 用 pyOCD（Python 生态）

```bash
pyocd list                                   # 确认探针在内
pyocd flash -t stm32f103c8 <你的.hex>        # 烧录
pyocd commander -t stm32f103c8               # 进交互调试
```

### 7.3 用 Keil MDK / IAR

- Keil：`Options → Debug` 选 **CMSIS-DAP Debugger** → 能识别到探针即可下载调试；
- IAR：`Project → Options → Debugger` 选 **CMSIS DAP**。

### 7.4 拖拽烧录（仅 MSC 版固件）

如果你烧的是 `MyDAPLink_IF_MSC.hex`，插上探针会多出一个**可移动磁盘**：

1. 打开那个「U 盘」；
2. 把目标的 `.hex` / `.bin` **拖进去**；
3. 探针自动烧录，完成后自动重新枚举。

> 拖拽烧录是**离线**的（探针自己完成，不经过电脑上的工具）。
>
> 为什么有的版本没有这个盘、以及怎么切换 —— 见 **§8.4**。

---

## 8. 日常使用：升级、切 Bootloader、拖拽烧录

### 8.1 只升级 IF（最常见）

**BL 只烧一次**，之后升级功能只需换 IF：

```bash
# 用 .bin 时给地址
st-flash --reset write out/MyDAPLink_IF.bin 0x0800C000
# 用 .hex 时不要给地址（自带）
# st-flash --reset write out/MyDAPLink_IF.hex
```

**免 ST-Link 的做法**（仅当当前 IF 带虚拟盘时可用）：先把 `out/magic/START_BL.ACT` 拖进
`DAPLINK` 盘 → 探针重启成 `MAINTENANCE` 维护盘 → 再把新 IF 的 hex 拖进这个维护盘。
**注意是两步**：直接把 IF 的 hex 丢进 `DAPLINK` 盘会被当成「烧给目标板」的固件。
哪种情况仍然必须用 ST-Link，见 **§8.5**。

### 8.2 切回 Bootloader（magic 文件）

`out/magic/START_BL.ACT` 是给 **MSC 版**用的：把它拖进虚拟 U 盘，探针会重启进入
BL 模式，方便后续升级/恢复。它的内容就是两个字节 `BL`。

（这就是 §8.1 里「免 ST-Link 更新 IF」的第一步。什么时候必须回到 ST-Link，见 **§8.5**。）

### 8.3 Flash 布局（128KB 片）

| 区域 | 起始地址 | 大小 |
|---|---|---|
| Bootloader (BL) | `0x08000000` | 0xBC00 (48128 B) |
| Interface (IF) | `0x0800C000` | 0x13C00 (80896 B) |
| Config (用户) | `0x0801FC00` | 0x400 |

### 8.4 虚拟 U 盘（MSC）什么条件才会出现 ★

**一句话：不是所有 IF 固件都带虚拟盘 —— 只有「内嵌了目标 flash 算法」的那一版才会出现。**

| 固件 | 对应工程 | 内嵌 flash 算法 | 插上电脑有虚拟 U 盘吗 |
|---|---|---|---|
| `MyDAPLink_IF.hex` | `stm32f103xb_if` | ❌ 无（all-family） | **没有** |
| `MyDAPLink_IF_MSC.hex` | `stm32f103xb_stm32f103rb_if` | ✅ 有（STM32F103） | **有** |

**为什么**（官方机制）：DAPLink 官方文档 `docs/USERS-GUIDE.md` 写明，MSD / 拖拽功能是
「构建里包含目标 flash 算法」时**自动启用**的；而那些 all-family 构建本身没有绑定具体目标，
就**不带 MSD 盘** —— 它仍然能用 CMSIS-DAP 协议给任意芯片烧录 / 调试，只是没有那个拖拽盘。

对照本包两个工程的声明（`src/upstream/projects.yaml`）：

```yaml
stm32f103xb_if:                       # → MyDAPLink_IF.hex
    - *module_if
    - records/family/all_family.yaml  # 只有各家 target_reset_*.c，无 flash 算法
    - records/usb/usb-bulk.yaml

stm32f103xb_stm32f103rb_if:           # → MyDAPLink_IF_MSC.hex
    - *module_if
    - records/board/stm32f103rb.yaml  # → 引入 stm32f103rb 的 flash 算法
```

- `records/family/all_family.yaml` 里只有各家的 `target_reset_*.c`（复位辅助代码），**一条 flash 算法都没有**；
- `source/family/st/stm32f103rb/target.c` 里有
  `.flash_regions[0].flash_algo = (program_target_t *)&flash;`（配 `flash_blob.c`），
  **内嵌了 STM32F103 的烧录算法** → MSD 自动挂出。

> 注意：**不是**「通用版把 MSC 代码裁掉了」。两个 IF 版本**都**编了 MSC 的 USB 端点
> （`module_if` 里本身就含 `records/usb/usb-msc.yaml`，定义 `MSC_ENDPOINT` → `USBD_MSC_ENABLE=1`），
> 差别只在「有没有内嵌目标 flash 算法」这一条。

**容量**：两版 IF 的 `.bin` 都是 80896 B（占用同一块 ROM 区 `0x0800C000`），
**虚拟盘不额外占 Flash**，128 KB 的片放得下（BL + IF ≈ 123 KB）。

**怎么切换**：若当前芯片里是通用版 IF（**没有虚拟盘**，所以维护盘这条路走不通），
想换成 MSC 版 —— 必须用外部调试器把 IF 区擦掉重烧（**BL 不用动**）：

```bash
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
  -c "init; reset halt" \
  -c "flash write_image erase out/MyDAPLink_IF_MSC.hex" \
  -c "reset run; shutdown"
```

> 这就是 §8.5 表格里的第 3 行：**换「有没有盘」本身就是需要 ST-Link 的场合之一**。
> 但只要有一次盘在手（比如已经是 MSC 版），之后无论换哪个 IF 都能靠维护盘完成。

**拖进去的文件分别是什么**：

| 拖入的文件 | 效果 |
|---|---|
| 目标的 `.hex` / `.bin` | 烧到**目标芯片**（不是探针自己）；成功变成一个完成页面，失败生成 `FAIL.TXT` |
| `out/magic/START_BL.ACT` | 探针**自己**重启进 BL，等待升级 IF |
| `msd_off.act` / `msd_on.act` | 关掉 / 开回虚拟盘 |
| `page_on.act` / `page_off.act` | 临时允许页编程+扇区擦除 / 恢复 |

（`.act` 命令全集见官方 `docs/MSD_COMMANDS.md`。）

> ⚠️ **限制**：虚拟盘**只认它内嵌算法的那个目标系列**（本包这版是 STM32F103）。
> 要烧别的芯片（Nordic、Freescale 等），请走 **CMSIS-DAP 调试口**（OpenOCD / pyOCD）——
> 那是通用协议，芯片无关，任何 ARM Cortex-M 都能烧。
> 完整的支持范围、以及「为什么有的 ARM 不支持」，见 **§13**。

### 8.5 什么时候还需要 ST-Link？★

把「烧录」分成四种，答案完全不一样：

| 你要烧的东西 | 需要外部调试器吗 | 怎么做 |
|---|---|---|
| **目标板固件**（LEDTEST 之类） | ❌ 不需要 | 探针的 CMSIS-DAP 口（OpenOCD / pyOCD），或 MSC 版拖拽虚拟盘 |
| **探针的 IF**（当前 IF 带虚拟盘） | ❌ 不需要 | 拖 `START_BL.ACT` 进 `DAPLINK` 盘 → 变成 `MAINTENANCE` 盘 → 拖新 IF hex |
| **探针的 IF**（当前 IF 不带虚拟盘，如通用版） | ✅ 需要 | 外部调试器（或另一块 DAPLink） |
| **探针的 BL**（首刷 / 换 BL / 救砖） | ✅ 需要 | 外部调试器；最坏还有串口 ISP（§10） |

> 一句话：**日常迭代（改时钟、改引脚、换 target 工程 → 重编 IF）已经可以彻底拔掉 ST-Link；
> 只有动 BL、或者 IF 卡死到挂不出盘，才需要它。**

**为什么维护盘救不了 BL**（源码级三条硬证据）：

1. **维护盘只映射 IF 那一段。** `source/board/stm32f103xb_bl.c:42-43`：

   ```c
   .flash_regions[0].start = 0x08000000 + KB(48),   // 0x0800C000
   .flash_regions[0].end   = 0x08000000 + KB(128),  // 0x08020000
   ```

   BL 自己那 48 KB（`0x08000000–0x0800C000`）**根本不在维护盘映射的地址范围里**。

2. **官方的「BL 自更新」机制本构建没启用。** `bootloader_update.c:39-41`：

   ```c
   #if !defined(DAPLINK_BOOTLOADER_UPDATE)
       #define DAPLINK_BOOTLOADER_UPDATE  0
   #endif
   ```

   该宏**全树只有这一处出现**，没有任何工程定义它 → 内嵌镜像 `image_size = 0`，
   `bootloader_check_and_update()` 退化成空操作。

3. **就算启用了也没地方放。** BL 镜像 48128 B，而 IF 区只有 `0x13C00 = 80896 B`，
   实测占用 `text 61952 + data 18944 = 80896 B` —— **恰好占满、零余量**，塞不进 48 KB 的 BL。

**那「不用 ST-Link」的边界在哪？** 关键在于有没有办法让探针停在维护盘。
BL 的跳出条件（`main_bootloader.c:275-278`）是**四个条件全真**才跳进 IF：

```c
if (!reset_button_pressed()                        // 本板无专用复位键，恒为 false
        && g_board_info.target_cfg
        && validate_bin_nvic(IF 起始地址)           // IF 的向量表有效…
        && !config_ram_get_initial_hold_in_bl()) { // …且没有被要求「停在 BL」
    /* 跳进 IF */
}
/* 否则留在 BL，挂出 MAINTENANCE 盘 */
```

于是只有三种局面：

| 局面 | 能进维护盘吗 | 结果 |
|---|---|---|
| IF 正常，且带虚拟盘 | ✅ | 拖 `START_BL.ACT` 置 hold-in-bl 标志 → 重启后停在维护盘 |
| IF 被擦掉 / 向量表非法 | ✅ | 重启**自动**停在维护盘 —— **IF 刷坏也能自救** |
| IF 能跳转但卡死在 USB 初始化前 | ❌ | 既没有盘、又进不了维护盘 → 只能上外部调试器 |

（第三行最容易踩：引脚配错、时钟配错导致 IF 跑飞时，虚拟盘根本不会出现，
这时维护盘也帮不了你。好在 USB 没起来的 IF 一般也不会破坏 BL。）

**而且「外部调试器」不必非是 ST-Link。** 任何能当 SWD 主机的都行 ——
**第二块 DAPLink 探针**最顺手（正好是「用 DAPLink 修 DAPLink」）：
接本探针的 `PB6(SWCLK) / PB7(SWDIO) / PB8(nRESET) / GND`，OpenOCD 换成
`-f interface/cmsis-dap.cfg` 即可。这条路一直通，是因为 `gpio.c` 里特意用了
`__HAL_AFIO_REMAP_SWJ_NOJTAG()` 保留探针芯片自己的 SWD 口
（官方默认 `SWJ_DISABLE` 会把探针自己的 PA13/PA14 关掉，那才真的会变砖）。
最坏的情况还有**串口 ISP**（BOOT0=1 + PA9/PA10），见 §10。

---

## 9. 常见问题排查

| 现象 | 原因 / 解决 |
|---|---|
| **`cannot read IDR`** | DP 层都不通。最常见：① 目标板没上电；② SWDIO(PB7) 接触不良/接反；③ SWCLK/SWDIO 接反。重新插紧、换短线、确认 PB6→SWCLK、PB7→SWDIO |
| **`Failed to read memory at 0xe000ed00`** | DP 通、AP 不通。按顺序查：① **把 SWD 速度降到 100~250 kHz**（最常见，见 §6.3）；② 另接上 PB8→NRST；③ 另有调试器占着同一 SWD 线（把 ST-Link 从目标板拔掉）；④ 目标板供电不足 |
| **`cmd_info failed`** | 探针 USB 掉了。重插探针 USB（USB 松了/被碰断电） |
| **插上探针没反应** | 检查是否只烧了 BL 没烧 IF；或 BL/IF 地址烧错（BL=0x08000000，IF=0x0800C000）；或 USB 口没插 PA11/PA12 那个 |
| **没有虚拟 U 盘** | 你烧的是**通用版 IF**（`MyDAPLink_IF.hex`）。想要 U 盘请烧 `MyDAPLink_IF_MSC.hex` —— 原理与切换方法见 **§8.4** |
| **虚拟串口没有 COM 号** | 装一下 CMSIS-DAP 驱动 / 换 USB 口 |
| **GDB `errno 10061`** | 终端 1 的 OpenOCD 没在跑或没起来。先起 OpenOCD，再连 GDB |
| **GDB `Target not examined yet`** | 目标板没被识别（同 `Failed to read memory` 那一行原因） |

**排查口诀**：先分「探针自己的问题」还是「目标板的问题」——
探针看 USB 设备是否 `OK`；目标板看 OpenOCD 有没有 `Examination succeed` 那行。

**顺序很重要**：遇到连不上，**先降速到 100 kHz 再试一次**，再去看接线。
本设计实测「1000 kHz 必挂、100 kHz 必通」，降速常常一步解决，比反复查线快得多。

---

## 10. 刷坏了怎么救（串口 ISP）

探针固件若刷坏导致 **SWD 被关**，就用 F103 芯片内建的**系统 Bootloader（串口 ISP，AN3155）**救：

1. **BOOT0 接高、BOOT1 接低**，然后复位（进入系统存储器启动）；
2. USB-TTL 接线：**TX→PA10**、**RX→PA9**、GND 共地（**注意收发交叉**）；
3. 跑脚本烧回 BL：

   ```bash
   python rescue/isp_rescue.py out/MyDAPLink_BL.bin COM3
   ```

   > ⚠️ **【其他使用者注意】** 最后的 `COM3` 要换成**你自己电脑上 USB-TTL 的 COM 口**
   > （Windows：设备管理器 →「端口(COM 和 LPT)」，或命令行 `mode` 查看）。
   > 填错会报找不到串口，或一直卡在握手。`out/MyDAPLink_BL.bin` 是相对路径，请先 `cd` 到包根目录。

   > ⚠️ 串口参数必须是 **115200, 8E1（偶校验）**——这是 STM32 ISP 的固定要求，
   > 脚本已内置；用别的工具时也别改成 8N1。

4. 烧回 BL 后，**BOOT0 接回 GND**，重新上电，再按第 4 节补烧 IF。

---

## 11. 固件清单与校验值

`out/` 里三个固件均为本机编译产出（非下载）：

| 固件 | 烧录地址 | 地址范围 | 大小 | 区域 CRC32 |
|---|---|---|---|---|
| `MyDAPLink_BL.hex` | `0x08000000` | `0x08000000–0x0800BBFF` | 48128 B | `0x3E08754F` |
| `MyDAPLink_IF.hex` | `0x0800C000` | `0x0800C000–0x0801FBFF` | 80896 B | `0x9115E7D9` |
| `MyDAPLink_IF_MSC.hex` | `0x0800C000` | `0x0800C000–0x0801FBFF` | 80896 B | `0xC805F60C` |

> `MyDAPLink_IF` 与 `MyDAPLink_IF_MSC` **二选一**：前者通用（无虚拟盘），后者带**虚拟 U 盘**。
> 为什么、以及怎么切换，见 **§8.4**。
>
> 固件内嵌的 **Build ID** 为 `mydaplink-v1.0-g9064ad6`（本版）—— 它由 `src/upstream` 的 git tag 生成，
> 重编译时会随你自己的 tag / commit 变化；在虚拟 U 盘的 `details.txt` 里能看到这一行。

**自己核对某个 hex**（看地址范围 / 向量表 / CRC）：

```bash
python tools/hex_inspect.py out/MyDAPLink_BL.hex out/MyDAPLink_IF.hex
```

> ⚠️ **【其他使用者注意】** `tools/hex_inspect.py` 是相对路径，请在**包根目录**下执行；
> 只要系统里有 Python 3 就能跑，**不需要装任何第三方库**。

详细编译统计见 `doc/BUILD_REPORT.md`。

---

## 12. 自己重新编译（可选）

> 只有想改引脚 / 改功能时才需要。日常使用直接烧 `out/` 里现成固件即可。

> ⚠️ **精简版需先补回 mbed-os**：本版已移除 `src/upstream/mbed-os/`，重新编译前要先拉回来：
>
> ```bash
> cd src/upstream
> curl -L -o mbed-os.tar.gz \
>   https://codeload.github.com/ARMmbed/mbed-os/tar.gz/bf6f2c3c6434a6de9eb9511feffa5948b3d1f20f
> mkdir -p mbed-os && tar xzf mbed-os.tar.gz --strip-components=1 -C mbed-os && rm mbed-os.tar.gz
> cd ../..
> ```
>
> （commit `bf6f2c3c` 记录在 `src/upstream/mbed-os.lib` 里，约 491 MB。）

**前置**：`arm-none-eabi-gcc` 在 PATH；`.venv` 已装依赖；`src/upstream` 是 git 仓库；
**GNU make** 在 PATH（本机原无 make，已随包附带 `tools/bin/make.exe`，`build.sh` 自动挂上）。

> ⚠️ **【其他使用者注意】** 上面这句描述的是**作者本机的环境**，你的机器不会自动具备，需要自己准备：
>
> | 前置 | 你要做什么 |
> |---|---|
> | `arm-none-eabi-gcc` | 装 Arm GNU Toolchain，把 `bin` 目录加进 PATH（建议 12.2 rel1 或更新） |
> | `.venv` | **本精简版没有**，按下面「一次性环境准备」自己建；`build.sh` 里写死了 `.venv/Scripts/python.exe`，请保持同名同位置 |
> | `src/upstream` 是 git 仓库 | **本精简版没有 `.git`**，按下面命令自己 `git init` 并打一个 tag（版本头靠它生成，名字自取） |
> | `mbed-os/` | **本精简版已移除**，必须先按本节开头的命令拉回来，否则编译必失败 |
> | `tools/bin/make.exe` | 已随包附带（Windows 便携版）。若你在 Linux/macOS，改用系统 `make` 并删掉这个目录即可 |
> | 路径 | `build.sh` 用 `$PKG_ROOT` 自动定位，**不需要改**；命令里的 `./build.sh` 请在包根目录执行 |

```bash
# 一次性环境准备
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r src/upstream/requirements.txt
cd src/upstream && git init && git add -A && git commit -m init \
  && git tag -a mydaplink-v1.0 -m "MyDAPLink_F103 v1.0" && cd ../..
# tag 名字随便起，它只影响固件里 Build ID 显示的那串版本号

# 编译（三选一或多跑几次）
./build.sh bl          # → out/MyDAPLink_BL.hex       (0x08000000 起)
./build.sh if          # → out/MyDAPLink_IF.hex       (0x0800C000 起，通用版)
./build.sh if-rb       # → out/MyDAPLink_IF_MSC.hex   (0x0800C000 起，带U盘版)
```

产物生成在 `src/upstream/projectfiles/make_gcc_arm/<工程>/build/`，
`build.sh` 已自动带 CRC 打包（post_build）。

**改引脚**：只改 `IO_Config.h`（`SWCLK_TCK_PIN` / `SWDIO_*_PIN` / `nRESET_PIN` /
`POWER_EN_PIN`），保持 `gpio.c` 里的 `SWJ_NOJTAG`（**不要**改回 `SWJ_DISABLE`，
否则烧完自身 SWD 就没了、会变砖）。详见 `doc/DESIGN.md`。

---

## 13. 它能烧哪些芯片？为什么有的 ARM 不支持

> 这是拿到探针后最常问的问题。先记住一个核心认知：
> **DAPLink 固件本身「不认识」任何芯片**，它只做一件事 —— 把上位机（OpenOCD / pyOCD / Keil）
> 发来的 SWD / JTAG 数据包搬到目标的调试口。所以「能烧什么」不是探针单方面决定的。

### 13.1 三条使用路径，覆盖范围完全不同

| 使用方式 | 谁决定「能烧什么」 | 覆盖范围 |
|---|---|---|
| **CMSIS-DAP 探针**<br>（OpenOCD / pyOCD / Keil / IAR） | 上位机的器件库 | **几乎任何带 SWD / JTAG 的 ARM 芯片** |
| **拖拽 U 盘（MSC）** | 固件里**内嵌的那一份** flash 算法 | **只有 STM32F103**（原理见 §8.4） |
| **重新编译 IF** | 换掉内嵌算法 | 本包已预置 10 种目标（见 §13.5） |

### 13.2 原生支持的系列

| 档位 | 内核 | 典型芯片 |
|---|---|---|
| **原生支持**<br>（SWD 直连） | Cortex-M0 / M0+ | STM32F0·G0·L0、GD32E23x、nRF51、RP2040 |
| | Cortex-M3 | STM32F1·F2·L1、GD32F1·F3、LPC17xx、Kinetis K |
| | Cortex-M4 | STM32F3·F4·L4·G4、GD32F4、nRF52、SAM D5x |
| | Cortex-M7 | STM32F7·H7、i.MX RT、SAM V7x / S7x |
| | Cortex-M23 / M33（含 TrustZone） | STM32L5·U5、nRF91、RA4、M2351 |
| | Cortex-M35P / M55 / M85 | STM32N6、Alif Ensemble |
| **有条件支持** | Cortex-R4 / R5 / R7 / R8 | TMS570 等 —— 有 CoreSight，多走 JTAG，OpenOCD 支持部分型号 |
| | Cortex-A5 / A7 / A9 / A53… | 有 CoreSight，但多核选核 + MMU，pyOCD 不支持、OpenOCD 覆盖有限 |
| **不支持** | ARM7TDMI / ARM9 / ARM11 | LPC21xx、AT91SAM7 / 9、S3C2440（原因见 §13.3 ①） |
| | 非 ARM | AVR、8051、PIC、MSP430、RISC-V、PowerPC（MPC57xx） |

### 13.3 为什么有的 ARM 不支持：三道门

```
目标芯片
  │
  ├─ ① 有 CoreSight DAP 吗？ ──否──▶ ✗ 用不了（ARM7 / 9 / 11）
  │         │ 是
  ├─ ② 调试口没被锁死吗？ ────否──▶ ✗ 用不了（引脚熔断 / RDP Level 2）
  │         │ 是
  ├─ ③ 上位机有器件配置吗？ ──否──▶ △ 能调试，但不能烧 flash
  │         │ 是
  └────────▶ ✅ 烧录 + 调试都行
```

**① 没有 CoreSight DAP —— 最根本的分水岭**

Cortex 全系（M / R / A）内核对自带 CoreSight 调试访问端口，SWD 和 JTAG-DP 都从这个
「总入口」进出，所以一条线就能通吃。

而 ARM7TDMI / ARM9 / ARM11（ARMv4 / v5 / v6 那一代）**那时还没有 CoreSight**：它们要接进
CoreSight 系统，必须额外挂一颗 `ARMJTAG-DP` 再加一个 **JTAG-AP（JTAG Access Port）**——
也就是说，它们不是「带 DAP 的核」，而是「挂在 DAP 后面的一串 JTAG 端口」。
DAPLink 只实现了常规的 DPACC / APACC 路径（AHB-AP / APB-AP），既没做 JTAG-AP 的扫描链，
也没有 SWD 通道。

一句话：**「是 ARM 内核」≠「有 CoreSight」**。

**② 调试口被锁死 —— 芯片自己的状态**

- SWD 引脚被复用成普通 GPIO，或出厂就熔断（部分低成本 MCU 会这么干）；
- 烧到了 **RDP（读保护）Level 2** → 永久锁死，DP 直接拒绝访问；
- 芯片处于 secure 生命周期状态（Secure Debug 未解锁）。

这类情况探针再通用也连不上，**不是烧录器的问题**。

**③ 上位机没有这颗芯片的器件配置 —— 最常被误判成「不支持」**

DAPLink 官方说明（daplink.io）：

> 如果你的 IDE 里找不到要调的器件，你**仍然可以调试**（选对 ARM CPU 架构即可），
> **但不能烧写 flash**。

因为「烧 flash」需要三样东西，全都写在上位机的 target 配置里
（OpenOCD 的 `target/xxx.cfg`、pyOCD 的 pack）：

| 需要什么 | 作用 |
|---|---|
| memory map | 哪段地址是 flash、多大 |
| flash 算法 | 怎么擦、怎么编程、页大小多少 |
| 复位策略 | 用软复位还是硬复位 |

所以新出的或小众的芯片，常见情况是「探针连得上、就是没人写算法」——
**这一档不是不能用，是能力受限**：调试、读内存、跑 GDB 都行，只是写不进 flash。

### 13.4 怎么自己判断一颗芯片能不能烧

1. **看内核**：是 Cortex-M 吗？是 → 基本能烧（再看第 2、3 步）。
2. **查上位机**：`openocd` 的 `scripts/target/` 下有没有对应的 `.cfg`？有 → 直接能用。
3. **都没有**：退一步，只要它是 Cortex-M，先按 ARM CPU 架构连上去**调试**是可行的；
   想烧 flash，需要自己补一份 target 配置 + flash 算法，或改用厂商官方工具。

**举例（Infineon Traveo II `CYT4BB`，汽车 MCU）**：内核是 2× Cortex-M7 + 1× Cortex-M0+，

- ① 有 CoreSight ✅
- ② 数据手册写明 "Flash programming through SWD/JTAG interface"，调试口开放 ✅
- ③ Infineon 在 ModusToolbox 里提供了 OpenOCD 的 `infineon/cytxbb.cfg` 与 CMSIS-FLM 算法 ✅

→ **结论：能用**，把 interface 换成 `cmsis-dap.cfg` 即可。注意它是**三核**，调试时要选核。

> 反过来说，这颗芯片恰恰证明：**支不支持跟品牌、跟车规无关，只看内核与协议**。

### 13.5 关于拖拽 U 盘的特殊说明

- U 盘**只认固件里内嵌的那一个目标系列**（本包 = STM32F103）。
- 想让 U 盘支持别的芯片，只能**重新编译 IF**（见 §12），换上那个芯片的 flash 算法 ——
  **探针硬件不用动**。
- 本包源码里已经准备好 10 个目标工程（`src/upstream/projects.yaml`）：

| 工程名 | 目标芯片 |
|---|---|
| `stm32f103xb_stm32f072rb_if` | STM32F072RB |
| `stm32f103xb_stm32f103rb_if` | STM32F103RB（= 本包 `MyDAPLink_IF_MSC.hex`） |
| `stm32f103xb_stm32f207zg_if` | STM32F207ZG |
| `stm32f103xb_stm32f334r8_if` | STM32F334R8 |
| `stm32f103xb_stm32f401re_if` | STM32F401RE |
| `stm32f103xb_stm32f411re_if` | STM32F411RE |
| `stm32f103xb_stm32f429zi_if` | STM32F429ZI |
| `stm32f103xb_stm32f746zg_if` | STM32F746ZG |
| `stm32f103xb_stm32l476rg_if` | STM32L476RG |
| `stm32f103xb_ublox_evk_odin_w2_if` | u-blox EVK-ODIN-W2 |

```bash
./build.sh stm32f103xb_stm32f401re_if   # 举例：编出支持 F401RE 拖拽烧录的 IF
```

> ⚠️ **实测口径**：本包**实测通过的只有 STM32F103**（烧录 LEDTEST + `compare-sections` 6 段全 match）。
> 上面表格里的其他系列属于**协议架构决定的能力范围**，不是逐颗芯片验证过的清单。
> 真要烧某颗芯片前，先确认 `openocd` 里有没有它的 `.cfg`。
