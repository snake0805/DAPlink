# MyDAPLink_F103 设计与源码改动说明

> 本文只讲**这套东西自己是怎么设计、怎么改的**，帮你看懂「为什么是这几个引脚、
> 改了哪两行代码」。日常使用请看包根目录的 `README.md`。

---

## 1. 设计目标

把一颗 **STM32F103C8T6** 做成**完整功能的 DAPLink 探针**，并且：

1. **不能变砖**——烧完之后，探针芯片自身的 SWD（PA13/PA14）还能用，方便日后重烧；
2. **接线整齐**——目标接口的几根线尽量聚在一起，方便做成排针；
3. **功能完整**——CMSIS-DAP v2 调试 + 可选 MSC 拖拽烧录 + 虚拟串口。

源码基于 ARM 官方 `ARMmbed/DAPLink`（main 分支），只改底层硬件抽象层，上层逻辑不动。

---

## 2. 引脚设计

### 2.1 最终引脚分配

| 功能 | 引脚 | 说明 |
|------|------|------|
| **SWCLK** | **PB6** | 探针输出给目标的 SWD 时钟 |
| **SWDIO** | **PB7** | 双向数据（**单脚双向**，靠方向开关切换 —— 这里有个坑，见 §3.2-b） |
| **nRESET** | **PB8** | 复位目标，低有效 |
| **POWER_EN** | **PB9** | 控制向目标供电（默认不供电） |
| **LED** | PC13 | 板载指示灯，保留不动 |
| USB_CONNECT | PA15 | 芯片 USB 固定脚，不可挪 |

### 2.2 为什么选 PB6 ~ PB9

这颗 F103 上，很多引脚已经被系统自己占用，先划掉：

| 已被占用 | 用途 |
|---|---|
| PA0 ~ PA3 | UART（串口） |
| PA8 | MCO（时钟输出） |
| PA11 ~ PA12 | USB D-/D+ |
| PA13 ~ PA14 | 芯片**自身**的 SWD（用来烧探针/救砖） |
| PA15 | USB_CONNECT |
| PC13 | 板载 LED |
| PB2 | BOOT1 |

排除之后，**PB6 / PB7 / PB8 / PB9 是一整块连续的空闲脚**，正好够 SWCLK/SWDIO/nRESET/POWER_EN 四个功能：

- **连续四脚** → 可以直接焊一排 **4P 排针**，用一条 4P 排线整体对插目标板，接线不会错、也不乱；
- 与固件里其他外设**无任何冲突**；
- 避开了历史上有名的两个坑：
  - **PA15 不能当 nRESET**——它和 `USB_CONNECT` 共用，配置会互相打架，导致探针不枚举；
  - **PB0 不能当 nRESET**——标准 Blue Pill 的 PB0 接着板载 LED1，开漏输出会和 LED 抢线。

### 2.3 nRESET / POWER_EN 的取舍

- **nRESET（PB8）不是永远要接**：多数目标板接 SWCLK/SWDIO/GND 三根线就能用。
  但有些板的 SWD 必须靠复位才能从异常态唤醒——这时接上 PB8→NRST 即可。
- **POWER_EN（PB9）默认输出低 = 不向目标供电**。目标板需要自己单独上电；
  若要由探针供电，可另行控制该脚，或直接把探针的 3.3V 接到目标 VCC。

---

## 3. 源码改动清单

相对官方原版，**只改了 3 个文件**，全在硬件抽象层 `hic_hal/stm32/stm32f103xb/` 里：

### 3.1 `IO_Config.h`

引脚宏改成自己的分配：

```
SWCLK_TCK_PIN  →  PB6
SWDIO_OUT_PIN  →  PB7      // 单脚双向
SWDIO_IN_PIN   →  PB7
nRESET_PIN     →  PB8
POWER_EN_PIN   →  PB9
```

这个文件是**所有引脚定义的唯一来源**，`DAP_config.h` 只是引用它，所以改引脚
**只需动这一个文件**。

### 3.2 `DAP_config.h`

两处改动，都是**拖拽烧录（MSC 虚拟盘）路径**踩出来的。

#### a) DAP 时钟降到 100 kHz

```c
// 原版：5 MHz —— 在杜邦线这种长导线上必挂
// #define DAP_DEFAULT_SWJ_CLOCK 5000000
#define DAP_DEFAULT_SWJ_CLOCK 100000
```

它只决定**探针自己当 SWD 主机**（拖拽烧录）时的默认时钟。上位机
（OpenOCD / pyOCD）是通过 CMSIS-DAP 命令单独指定速度的，**不受这个宏影响**。
实测 1000 kHz 以上必挂、500 kHz 时好时坏、100~250 kHz 稳定，故取 100 kHz。

#### b) 单脚 SWDIO 下的 TMS 驱动方向（★ 拖拽烧录失败的真正根因）

`SWJ_Sequence()`（JTAG→SWD 切换序列、线路复位都靠它）是用
`PIN_SWDIO_TMS_SET/CLR` **逐位**驱动 SWDIO 的。而 `PORT_SWD_SETUP()` 结尾会把
SWDIO 切成**输入**（官方板 `SWDIO_OUT` / `SWDIO_IN` 是**两根脚**，输入输出互不干扰，
所以官方代码没这个问题）。

本板 SWDIO 是**单脚双向**（PB7 同时当 OUT 和 IN），于是：

```
PORT_SWD_SETUP()  → PB7 变输入
SWJ_Sequence()    → 只写 BSRR/BRR，不改方向 → 拉不动线
JTAG2SWD() 失败   → swd_init_debug() 失败 → 拖拽时报 Failed to reset/halt the target MCU
```

修法是**驱动前先恢复推挽输出**：

```c
__STATIC_FORCEINLINE void PIN_SWDIO_TMS_SET(void)
{
    pin_out_init(SWDIO_OUT_PIN_PORT, SWDIO_OUT_PIN_Bit);   // ← 先恢复输出方向
    SWDIO_OUT_PIN_PORT->BSRR = SWDIO_OUT_PIN;
}
__STATIC_FORCEINLINE void PIN_SWDIO_TMS_CLR(void)
{
    pin_out_init(SWDIO_OUT_PIN_PORT, SWDIO_OUT_PIN_Bit);
    SWDIO_OUT_PIN_PORT->BRR = SWDIO_OUT_PIN;
}
```

> **为什么 CMSIS-DAP 路径一直没事**：`DAP_SWD_Sequence()` 在驱动前本来就会先调
> `PIN_SWDIO_OUT_ENABLE()`。只有拖拽路径走的是 `SWJ_Sequence()`，所以只它中招。

### 3.3 `gpio.c`

把 SWJ（Serial Wire/JTAG）配置从「关闭」改成「只关 JTAG、保留 SWD」：

```c
// 原版（危险）：彻底关闭 SWD → 烧完再也无法用 SWD 重烧，变砖
// __HAL_AFIO_REMAP_SWJ_DISABLE();

// 本设计：只关 JTAG，保留 SWD，PA13/PA14 仍可用于救砖
__HAL_AFIO_REMAP_SWJ_NOJTAG();
```

> **为什么必须改**：官方默认用 `SWJ_DISABLE` 且 DAP 的 SWD 输出占着芯片自己的
> PA13/PA14。一旦烧进去，探针芯片自身的 SWD 就被关了——以后想重烧，只能拆下来
> 走串口 ISP，非常麻烦。`SWJ_NOJTAG` 保留 SWD，就避免了这个问题。

### 3.4 上层逻辑一个字没动

`daplink/`、`cmsis-dap/`、`usb/`、`target/`、`family/` 等全部保持官方原样。

这正是 DAPLink **分层 HAL 架构**的价值：**换引脚 / 换时序只需动 `hic_hal`**，
上层的协议、USB、烧录逻辑完全不用碰。

> 反过来说，上面 §3.2-b 那个坑之所以难查 —— 就是因为它在 HAL 里，
> 而报错却出现在上一层（`Failed to reset/halt the target MCU`），
> 中间隔着 `swd_init_debug()` → `target_flash_init()` 好几层。

---

## 4. 构建机制简述

1. **声明式构建**：`projects.yaml` 声明有哪些工程（`stm32f103xb_bl` / `_if` /
   `_stm32f103rb_if`），`records/*.yaml` 描述芯片/板级参数；
2. **progen 生成 Makefile**：`project_generator` 根据声明自动生成 `Makefile`，不手写编译规则；
3. **make 编译**：调用 `arm-none-eabi-gcc` 编译链接；
4. **post_build 打 CRC**：编译后由 `post_build_script_gcc.py` 计算区域 CRC 并写进固件尾部，
   产出最终的 `*_crc.hex`。

> 本机没有系统级 `make`，因此随包附带便携版 `tools/bin/make.exe`，由 `build.sh` 挂到 PATH。
> 又因为 make 阶段调用的是裸 `python`（缺 `intelhex` 会被静默忽略），所以 `build.sh`
> 采用**两段式**：第一段 progen+make，第二段用 `.venv` 的 python 显式再跑一次 post_build，
> 才能产出带 CRC 的 hex。

> ⚠️ **【其他使用者注意】** 上面这段描述的是**作者本机的环境**，你那边不一定相同——
> 例如 Linux/macOS 一般自带系统 `make`，就不需要 `tools/bin/make.exe`；
> 而 `build.sh` 里写死了 `.venv/Scripts/python.exe`（Windows 路径），
> 换到 Linux/macOS 要改成 `.venv/bin/python`。
> **这些只在「想重新编译」时才有关系**：直接用 `out/` 里的现成固件，完全不需要编译。

---

## 5. 想改点东西怎么办

| 想改什么 | 改哪里 |
|---|---|
| 换 SWD/复位/供电引脚 | `IO_Config.h` 里的对应宏 |
| 换 LED 引脚 | `IO_Config.h` 里的 `RUNNING_LED` / `CONNECTED_LED` 等 |
| 增加/裁剪工程 | `projects.yaml` + `records/` |
| 让它保留 JTAG | `gpio.c` 里把 `SWJ_NOJTAG` 换成其他 SWJ 选项 |

改完跑 `./build.sh bl` / `./build.sh if` 重新编译即可（见 `README.md` 第 12 节）。

> ⚠️ **【其他使用者注意】** 上表里的路径是**相对 `src/upstream/` 目录**的，不是相对包根目录，
> 找文件时注意。另外改完必须**重新编译**才生效，而**本精简版不含 `mbed-os/` 和 `.venv/`**——
> 想动源码就得先按 `README.md` 第 12 节把 mbed-os 补回来、把 `.venv` 建起来，否则 `build.sh` 会直接报错退出。
