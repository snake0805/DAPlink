# verify_flash.gdb — MyDAPLink_F103 目标板只读自检脚本
#
# 用途：确认目标板 Flash 里烧的到底是不是你手上那个 elf。
#       全程只读（除了 halt），不会擦写目标板。
#
# ⚠️⚠️ 使用前必改 2 处（下面示例的路径都是作者的，不是你机器上的真实路径）：
#   ① 目标程序 elf    → 换成你自己的，例如 D:/myproj/build/app.elf
#   ② 本脚本的路径    → source 时请写【绝对路径】。
#      注意 GDB 的相对路径是相对「你启动 GDB 时所在的目录」，不是相对脚本所在目录，
#      所以最稳的写法是绝对路径。
#
# 用法（在 arm-none-eabi-gdb 提示符下，整行输入，不要带 "(gdb)" 前缀）：
#     arm-none-eabi-gdb <你的目标程序.elf>              ← 改这里
#     target extended-remote localhost:3333
#     source <本脚本所在目录的绝对路径>/verify_flash.gdb   ← 改这里
#
# 判读：
#   ① 首 8 字节 = SP + Reset，应与你 elf 的入口一致。
#      （下面 [1] 里出现的期望值 20005000 / 0800034d 是【作者当时那个测试程序】的值，
#        你换成自己的程序后必然不同，请以你自己的 elf 为准，不要照抄。）
#   ② 镜像尾不为全 FF，说明有内容
#   ③ compare-sections 若出现 MIS-MATCHED，说明 Flash ≠ elf，需要重新 load

set pagination off
set confirm off

echo \n==== [1] 目标板向量表（前两个字：SP / Reset_Handler） ====\n
monitor halt
x/2wx 0x08000000

echo \n==== [2] 镜像尾部抽样（全 FF 表示该段未烧录） ====\n
echo    ※ 下面的 0x08001204 是作者测试程序的尾部地址，换了你自己的程序请改成本程序接近末尾的地址\n
x/8wx 0x08001204

echo \n==== [3] 当前 PC / SP / LR ====\n
info registers pc sp lr

echo \n==== [4] Flash 与 elf 逐段比对（关键：不允许 MIS-MATCHED） ====\n
compare-sections

echo \n==== [5] 复位到入口，确认能停住 ====\n
monitor reset halt
info registers pc sp

echo \n==== 自检结束，请把以上整段输出贴回 ====\n
