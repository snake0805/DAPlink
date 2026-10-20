#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
isp_rescue.py — MyDAPLink_F103 串口 ISP 救砖工具

什么时候用它：
    探针固件刷坏（掉线、不枚举、SWD 被关）之后，唯一能救回来的手段。
    原理是让 STM32 进入芯片内建的 **系统 Bootloader**（AN3155 / AN2606），
    从 USART1(PA9=TX / PA10=RX) 把固件重新灌进去。

进入系统 Bootloader 的步骤：
    1) 目标 F103 的 BOOT0 接高（3V3），BOOT1/PB2 接低（GND）
    2) 复位（或重新上电）
    3) 用 USB-TTL 把 PA9/PA10 接到电脑
    4) 跑本脚本

⚠️ 协议关键点（否则永远握手不上）：
    - 串口必须是 **8E1**（8 数据位 + 偶校验 + 1 停止位），115200
    - 先发一个 0x7F 做自动波特率同步
    - 之后每条命令都发 命令字节 + 其按位取反，等 1 个 ACK(0x79)

用法：
    python isp_rescue.py <firmware.bin> [COM口] [偏移可选]
    例：python isp_rescue.py out/MyDAPLink_BL.bin COM3

⚠️⚠️ 使用前必改 2 处：
    1) COM3 —— 这是【作者电脑上】的串口号，不是通用的，必须换成你自己的。
       Windows 查看方法：设备管理器 →「端口 (COM 和 LPT)」；
       或命令行执行 `mode`、或 `python -m serial.tools.list_ports -v`。
       不传第二个参数时脚本会用下面的 DEFAULT_PORT，所以请把它也改掉。
    2) 固件路径 —— 例子 `out/MyDAPLink_BL.bin` 是【相对路径】，
       请在包根目录下执行；或在任意目录下直接写绝对路径。

依赖：
    pip install pyserial
"""
import sys
import time

try:
    import serial
except ImportError:
    print("缺少 pyserial，请先: pip install pyserial")
    sys.exit(2)

ACK = 0x79
NACK = 0x1F
SYNC = 0x7F
DEFAULT_PORT = "COM3"   # ⚠️ 改成你电脑上 USB-TTL 的 COM 口（如 "COM7"）；不改会报找不到串口
DEFAULT_BAUD = 115200


def _wait_ack(ser, timeout=3.0, tag=""):
    ser.timeout = timeout
    b = ser.read(1)
    if b == bytes([ACK]):
        return True
    if b == bytes([NACK]):
        print("   [%s] 收到 NACK" % tag)
    elif b:
        print("   [%s] 收到意外字节 0x%02X" % (tag, b[0]))
    else:
        print("   [%s] 超时" % tag)
    return False


def _cmd(ser, code):
    """发命令 + 补码，收 ACK"""
    ser.write(bytes([code, code ^ 0xFF]))
    return _wait_ack(ser, tag="cmd 0x%02X" % code)


def _addr(ser, value):
    """发 4 字节大端地址 + 异或校验，收 ACK"""
    a = [(value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF]
    ser.write(bytes(a + [a[0] ^ a[1] ^ a[2] ^ a[3]]))
    return _wait_ack(ser, tag="addr 0x%08X" % value)


def _sync(ser, tries=60):
    """发 0x7F 直到 bootloader 应答（等待用户复位板子）"""
    for i in range(tries):
        ser.reset_input_buffer()
        ser.write(bytes([SYNC]))
        ser.timeout = 0.5
        r = ser.read(1)
        if r == bytes([ACK]):
            return "ok"
        if r == bytes([NACK]):
            return "already"      # 已在命令模式
        time.sleep(1.0)
        if i and i % 5 == 0:
            print("   ... 等待复位 (%d/%d)" % (i, tries))
    return None


def burn(bin_path, port, baud=DEFAULT_BAUD, base=0x08000000, block=256):
    with open(bin_path, "rb") as f:
        fw = f.read()

    print("固件 : %s" % bin_path)
    print("大小 : %d 字节 (0x%X)" % (len(fw), len(fw)))
    print("串口 : %s @ %d 8E1" % (port, baud))
    print("基址 : 0x%08X" % base)
    print("-" * 50)

    ser = serial.Serial(port, baud, timeout=3.0,
                        bytesize=8, parity=serial.PARITY_EVEN, stopbits=1)

    print("[1/6] 同步握手（若卡住请先复位目标板）...")
    st = _sync(ser)
    if st is None:
        print("✗ 握手失败：检查 BOOT0=高、串口 8E1、PA9/PA10 是否接反")
        return 1
    print("   ✓ 就绪%s" % ("（原已在命令模式）" if st == "already" else ""))

    print("[2/6] 读产品 ID (GET 0x02)...")
    if not _cmd(ser, 0x02):
        return 1
    nb = ser.read(1)
    if nb:
        body = ser.read(nb[0] + 1)
        if len(body) >= 2:
            print("   ✓ PID = 0x%04X" % ((body[0] << 8) | body[1]))

    print("[3/6] 全片擦除 (ERASE 0x43)...")
    if not _cmd(ser, 0x43):
        return 1
    ser.write(b"\xFF\x00")
    if not _wait_ack(ser, timeout=25.0, tag="erase"):
        print("✗ 擦除失败/超时")
        return 1
    print("   ✓ 已擦除")

    print("[4/6] 写入 (WRITE 0x31)...")
    off, addr = 0, base
    while off < len(fw):
        piece = fw[off:off + block]
        n = len(piece)
        pad = (n + 3) & ~3
        if not _cmd(ser, 0x31):
            print("✗ WRITE 命令失败 @ 0x%08X" % addr)
            return 1
        if not _addr(ser, addr):
            return 1
        buf = bytearray([pad - 1])
        cks = pad - 1
        for byte in piece:
            buf.append(byte)
            cks ^= byte
        for _ in range(n, pad):
            buf.append(0xFF)
            cks ^= 0xFF
        buf.append(cks & 0xFF)
        ser.write(bytes(buf))
        if not _wait_ack(ser, timeout=5.0, tag="write %dB" % n):
            print("✗ 写失败 @ 0x%08X" % addr)
            return 1
        off += n
        addr += n
        if off % (block * 4) == 0 or off == len(fw):
            print("   ... %d/%d" % (off, len(fw)))
    print("   ✓ 写入完成")

    print("[5/6] 回读校验前 256 字节 (READ 0x11)...")
    if not _cmd(ser, 0x11):
        return 1
    if not _addr(ser, base):
        return 1
    ser.write(bytes([0xFF, 0x00]))
    if not _wait_ack(ser, tag="read len"):
        return 1
    rb = ser.read(256)
    if len(rb) == 256 and rb == fw[:256]:
        print("   ✓ 一致")
    else:
        print("   ! 不一致（读回 %d 字节）—— 请复核" % len(rb))

    print("[6/6] 跳转运行 (GO 0x%08X)..." % base)
    if not _cmd(ser, 0x21):
        return 1
    if not _addr(ser, base):
        return 1

    ser.close()
    print("-" * 50)
    print("✓ 完成。把 BOOT0 接回 GND 后重新上电。")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORT
    base = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x08000000
    return burn(path, port, base=base)


if __name__ == "__main__":
    sys.exit(main())
