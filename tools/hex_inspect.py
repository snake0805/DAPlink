#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hex_inspect.py — MyDAPLink_F103 固件自检工具

作用：把一个 Intel HEX 文件"看穿"——告诉你它到底覆盖了哪些地址、
     开头是不是合法向量表、结尾有没有 post_build 写入的 CRC。
     不依赖任何第三方库，纯标准库。

用法：
    python hex_inspect.py <file.hex> [file2.hex ...]

输出项：
    - 记录类型直方图（00 数据 / 01 结束 / 02 段地址 / 04 线性地址 ...）
    - 实占地址区间与总字节数
    - 区间内的空洞（未烧录区域）
    - 前 8 字节 → 解析出初始 SP 与 Reset_Handler
    - 末 4 字节 → 解析出 CRC32（post_build 追加）
"""
import sys
import binascii
from collections import defaultdict

_KIND = {
    0x00: "DATA",
    0x01: "EOF",
    0x02: "EXT_SEG",
    0x03: "START_SEG",
    0x04: "EXT_LIN",
    0x05: "START_LIN",
}


def _load(path):
    """把一个 HEX 文件读进 dict[addr]=byte，并返回统计信息。"""
    cells = {}
    hist = defaultdict(int)
    upper = 0                 # 线性/段基址
    lo = hi = None
    payload_total = 0
    notes = []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for idx, raw_line in enumerate(fh, 1):
            s = raw_line.strip()
            if not s:
                continue
            if s[0] != ":":
                notes.append("第 %d 行无 ':' 前缀，跳过" % idx)
                continue
            try:
                blob = binascii.unhexlify(s[1:])
            except binascii.Error:
                notes.append("第 %d 行十六进制非法" % idx)
                continue

            n = blob[0]
            off = (blob[1] << 8) | blob[2]
            kind = blob[3]
            body = blob[4:4 + n]
            chk = blob[4 + n]

            # 校验：所有字节求和后低 8 位应为 0
            if (sum(blob[:4 + n]) + chk) & 0xFF:
                notes.append("第 %d 行校验和不对" % idx)

            hist[kind] += 1

            if kind == 0x00:
                base = upper + off
                for k, v in enumerate(body):
                    cells[base + k] = v
                payload_total += n
                lo = base if lo is None else min(lo, base)
                hi = (base + n - 1) if hi is None else max(hi, base + n - 1)
            elif kind == 0x02:
                upper = ((body[0] << 8) | body[1]) << 4
            elif kind == 0x04:
                upper = ((body[0] << 8) | body[1]) << 16
            elif kind in (0x01, 0x03, 0x05):
                pass
            else:
                notes.append("第 %d 行是未知记录类型 0x%02X" % (idx, kind))

    return dict(cells=cells, hist=dict(hist), lo=lo, hi=hi,
                payload=payload_total, notes=notes)


def _holes(cells, lo, hi):
    out, start = [], None
    for a in range(lo, hi + 1):
        if a in cells:
            if start is not None:
                out.append((start, a - 1))
                start = None
        else:
            if start is None:
                start = a
    if start is not None:
        out.append((start, hi))
    return out


def inspect(path):
    r = _load(path)
    print("=" * 66)
    print(" 文件 : %s" % path)

    if not r["cells"]:
        print(" (空文件 / 无数据记录)")
        for w in r["notes"]:
            print("  ! " + w)
        return

    cells, lo, hi = r["cells"], r["lo"], r["hi"]
    span = hi - lo + 1

    print(" 记录 : " + "  ".join(
        "%s×%d" % (_KIND.get(k, hex(k)), v) for k, v in sorted(r["hist"].items())))
    print(" 区间 : 0x%08X – 0x%08X   (跨度 %d B / 0x%X)" % (lo, hi, span, span))
    print(" 数据 : 记录累计 %d B，去重后实占 %d B" % (r["payload"], len(cells)))

    hs = _holes(cells, lo, hi)
    if hs:
        head = ", ".join("0x%08X–0x%08X" % h for h in hs[:4])
        print(" 空洞 : %d 处  例如 %s" % (len(hs), head))
    else:
        print(" 空洞 : 无，区间连续")

    head8 = bytes(cells.get(lo + i, 0xFF) for i in range(8))
    sp = int.from_bytes(head8[:4], "little")
    pc = int.from_bytes(head8[4:8], "little")
    print(" 首8B : %s" % " ".join("%02X" % b for b in head8))
    print("        SP=0x%08X  Reset=0x%08X%s" % (
        sp, pc, "   ← Reset 的 bit0=1 表示 Thumb 模式，正常" if pc & 1 else "  ← 警告: bit0=0"))

    tail4 = bytes(cells.get(hi - 3 + i, 0xFF) for i in range(4))
    print(" 末4B : %s" % " ".join("%02X" % b for b in tail4))
    print("        CRC=0x%08X  (post_build 追加的 region CRC32)" % int.from_bytes(tail4, "little"))

    for w in r["notes"][:5]:
        print("  ! " + w)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        inspect(p)
