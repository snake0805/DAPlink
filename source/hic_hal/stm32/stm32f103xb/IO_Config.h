/**
 * @file    IO_Config.h
 * @brief
 *
 * DAPLink Interface Firmware
 * Copyright (c) 2009-2016, ARM Limited, All Rights Reserved
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef __IO_CONFIG_H__
#define __IO_CONFIG_H__

#include "stm32f1xx.h"
#include "compiler.h"
#include "daplink.h"

COMPILER_ASSERT( DAPLINK_HIC_ID == DAPLINK_HIC_ID_STM32F103XB );

// USB control pin
#define USB_CONNECT_PORT_ENABLE()  __HAL_RCC_GPIOA_CLK_ENABLE()
#define USB_CONNECT_PORT_DISABLE() __HAL_RCC_GPIOA_CLK_DISABLE()
#define USB_CONNECT_PORT           GPIOA
#define USB_CONNECT_PIN            GPIO_PIN_15
#define USB_CONNECT_ON()           ( USB_CONNECT_PORT->BSRR = USB_CONNECT_PIN )
#define USB_CONNECT_OFF()          ( USB_CONNECT_PORT->BRR = USB_CONNECT_PIN )

// Connected LED
#define CONNECTED_LED_PORT    GPIOC
#define CONNECTED_LED_PIN     GPIO_PIN_13
#define CONNECTED_LED_PIN_Bit 13

// When bootloader, disable the target port(not used)
// 【MyDAPLink】POWER_EN 由复现包的 PB15 迁到 PB9（PB15 空出，PB 口左侧留一组连续脚）
#define POWER_EN_PIN_PORT GPIOB
#define POWER_EN_PIN      GPIO_PIN_9
#define POWER_EN_Bit      9

// ============================================================================
//  【MyDAPLink_F103】SWD 目标接口引脚分配
//  本版本刻意与 DAPLINK_F103_复现包（PB13/PB14/PB12/PB15）完全不同，
//  选用连续的一块 PB6~PB9，便于用一条 4P 排线整体对插，接线更整齐。
//
//   功能        本版本     复现包    说明
//   ----------  --------  --------  ------------------------------------------
//   SWCLK       PB6       PB13      输出推挽，接目标 SWCLK
//   SWDIO       PB7       PB14      单脚双向，接目标 SWDIO
//   nRESET      PB8       PB12      开漏+上拉，接目标 NRST（可选）
//   POWER_EN    PB9       PB15      目标供电使能（可选）
//
//  选脚依据：PA0~PA3=UART、PA8=MCO、PA11~PA15=USB、PC13=板载 LED，
//  其余 PB6~PB9 在本固件中完全空闲，且不落任何板载外设，无冲突。
// ============================================================================

// nRESET 输出：接目标板 NRST，开漏 + 内部上拉，低有效复位
// 用 PB8 —— 空闲脚，无板载外设占用。
//
// 【踩坑记录（沿用自复现包的教训，勿踩）】：
//1) PA15：与 USB_CONNECT_PIN 共用。gpio_init() 先把 PA15 配成推挽输出
//    (USB 用)，随后又配成开漏+上拉 (nRESET 用)；而 USBD_Connect(FALSE)
//    会用 USB_CONNECT_OFF() 把 PA15 强推挽拉低，DAP_reset() 读的
//    DAP_config.h:399 ((nRESET_PIN_PORT->IDR >> nRESET_PIN_Bit) & 1)
//    因此读到随机翻转电平，USB 状态机与复位逻辑互相打架，
//    实测探针直接不枚举 (VID_0000&PID_0002 设备描述符请求失败)。
// 2) PB0 ：标准 Blue Pill 的 PB0 接板载 LED1，开漏输出与 LED 及目标
//    NRST 上拉打架，接目标即掉线 (D 盘消失 / CMSIS-DAP 找不到)。
// PB8 无上述任何冲突。
#define nRESET_PIN_PORT GPIOB
#define nRESET_PIN      GPIO_PIN_8
#define nRESET_PIN_Bit  8

// SWD 调试接口（迁到 PB 口，释放 PA13/PA14 给芯片自身 SWD 救砖用）
#define SWCLK_TCK_PIN_PORT GPIOB
#define SWCLK_TCK_PIN      GPIO_PIN_6
#define SWCLK_TCK_PIN_Bit  6

// SWDIO 双向：输出与输入同脚(PB7)，靠 OUT_ENABLE/OUT_DISABLE 切方向
#define SWDIO_OUT_PIN_PORT GPIOB
#define SWDIO_OUT_PIN      GPIO_PIN_7
#define SWDIO_OUT_PIN_Bit  7

#define SWDIO_IN_PIN_PORT GPIOB
#define SWDIO_IN_PIN      GPIO_PIN_7
#define SWDIO_IN_PIN_Bit  7

// TODO LEDs 用户控制LED
// USB status LED
#define RUNNING_LED_PORT GPIOC
#define RUNNING_LED_PIN  GPIO_PIN_13
#define RUNNING_LED_Bit  13

#define PIN_HID_LED_PORT GPIOC
#define PIN_HID_LED      GPIO_PIN_13
#define PIN_HID_LED_Bit  13

#define PIN_CDC_LED_PORT GPIOC
#define PIN_CDC_LED      GPIO_PIN_13
#define PIN_CDC_LED_Bit  13

#define PIN_MSC_LED_PORT GPIOC
#define PIN_MSC_LED      GPIO_PIN_13
#define PIN_MSC_LED_Bit  13


#endif
