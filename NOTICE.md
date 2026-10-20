MyDAPLink_F103
==============

把一块 STM32F103C8T6（Blue Pill）变成一台完整的 DAPLink 调试探针 / 烧录器。

本仓库是一个**板级移植版本**，基于 ARM 官方 DAPLink 固件，仅修改了硬件抽象层
（HAL）的 3 个文件，协议栈、USB 描述符、拖拽烧录逻辑均为上游原样。


上游项目
--------
ARMmbed/DAPLink — https://github.com/ARMmbed/DAPLink
许可：Apache License 2.0（完整文本见 `src/upstream/LICENSE`）

本仓库同样以 Apache-2.0 发布。上游的版权与许可声明随源码一并保留。


相对上游的修改（3 个文件，全部位于 hic_hal 层）
------------------------------------------------
1. `src/upstream/source/hic_hal/stm32/stm32f103xb/IO_Config.h`
   - SWD 引脚映射为 PB6(SWCLK) / PB7(SWDIO) / PB8(nRESET)
   - POWER_EN = PB9，LED = PC13
   - 附选脚依据与引脚复用冲突说明

2. `src/upstream/source/hic_hal/stm32/stm32f103xb/gpio.c`
   - 保留 SWD 引脚复用（`SWJ_NOJTAG`），避免探针自身引脚被关掉而变砖
   - nRESET 配置为开漏输出 + 上拉

3. `src/upstream/source/hic_hal/stm32/stm32f103xb/DAP_config.h`
   - `DAP_DEFAULT_SWJ_CLOCK`：5 MHz → 100 kHz
     （适配长杜邦线下的信号完整性；只影响拖拽烧录路径，
       上位机仍可通过 `DAP_SWJ_Clock` 自行下发速度）
   - `PIN_SWDIO_TMS_SET/CLR`：驱动前先 `pin_out_init()` 切回推挽输出
     （本板 SWDIO 为**单脚双向**，不切方向时 JTAG→SWD 切换序列会失败）


为什么只改这 3 个文件
----------------------
DAPLink 的分层做得比较彻底：引脚与时钟全部收敛在 `hic_hal`，
换板子只需动这一层。上层的协议、USB、烧录逻辑一行都不用碰。


固件说明
--------
| 文件 | 烧录地址 | 用途 |
|---|---|---|
| `out/MyDAPLink_BL.hex` | `0x08000000` | Bootloader，负责向量表校验与跳转、提供维护盘 |
| `out/MyDAPLink_IF_MSC.hex` | `0x0800C000` | 接口固件，**带虚拟 U 盘**（拖拽烧录） |
| `out/MyDAPLink_IF.hex` | `0x0800C000` | 接口固件，通用版（无虚拟盘） |

IF 两个版本二选一。详细使用方法见 `README.md` 与 `doc/`。
