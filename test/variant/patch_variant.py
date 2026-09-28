#!/usr/bin/env python3
"""实验 B — SS0 变体 patcher
用法:
  python patch_variant.py 0x88888808      # 把 SS0 解锁值改为 0x88888808 并 patch 全部落点
  python patch_variant.py --restore       # 恢复原始 (0x88888888)
  python patch_variant.py --show          # 显示当前 patch 状态

patch 落点:
  1. windows-v3.0/tools/unlock40x/unlock40x_v70.c
     - #define VAL_SS0_UNLOCKED + 所有 0x88888888 字面量 (probe/verify/print)
     - own_code_67 的 lui/addi 立即数 (0x88889537/0x88850513)
  2. windows-v3.0/tools/unlock40x/v67_payload.bin (如果包含同款 lui/addi 序列;
     bendy2 blob 的 SS0 写也可能在 blob 里 — 有则 patch, 无则跳过并报告)

编码规则: 对任意 32-bit 值 V, RISC-V 构造 lui hi20 + addi lo12 (signed):
  hi = (V + 0x800) >> 12 ; lo = V - (hi << 12)
  lui  = (hi << 12) | (10 << 7) | 0x37          (rd=a0/x10)
  addi = ((lo & 0xFFF) << 20) | (10 << 15) | (10 << 7) | 0x13
原始值 0x88888888 -> lui 0x88889537 / addi 0x88850513 (已验证)。
"""
import glob
import shutil
import struct
import sys
import os

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "windows-v3.0", "tools", "unlock40x"))
C_FILE = os.path.join(REPO, "unlock40x_v70.c")
BLOB = os.path.join(REPO, "v67_payload.bin")
BAK_C = C_FILE + ".orig"
BAK_BLOB = BLOB + ".orig"
ORIG_VALUE = 0x88888888

# 原始 lui/addi (little-endian 字节序列, rd=a0)
ORIG_LUI = 0x88889537
ORIG_ADDI = 0x88850513


def encode(V: int):
    hi = (V + 0x800) >> 12
    lo = (V & 0xFFF) - 0x1000 if (V & 0xFFF) >= 0x800 else (V & 0xFFF)
    lui = ((hi & 0xFFFFF) << 12) | (10 << 7) | 0x37
    addi = ((lo & 0xFFF) << 20) | (10 << 15) | (10 << 7) | 0x13
    return lui, addi


def sanity():
    l, a = encode(0x88888888)
    assert l == ORIG_LUI and a == ORIG_ADDI, (hex(l), hex(a))
    l, a = encode(0x88888808)
    # 0x88888808: hi=(0x88888808+0x800)>>12=0x88889, lo=0x808(-0x7F8)
    assert l == 0x88889537 and a == 0x80850513, (hex(l), hex(a))
    print("[ok] lui/addi 编码器自检通过")


def find_variant_backups():
    return os.path.exists(BAK_C) or os.path.exists(BAK_BLOB)


def patch(value: int):
    if not find_variant_backups():
        shutil.copy2(C_FILE, BAK_C)
        if os.path.exists(BLOB):
            shutil.copy2(BLOB, BAK_BLOB)
        print("[ok] 已备份原始 .c/.bin (.orig)")
    else:
        print("[i] .orig 备份已存在, 不覆盖")

    lui, addi = encode(value)
    old_hex = f"0x{ORIG_VALUE:08X}"
    new_hex = f"0x{value:08X}"

    # 1) C 文件
    c = open(C_FILE, "r", encoding="utf-8", errors="replace").read()
    n1 = c.count(old_hex) + c.count(f"{ORIG_VALUE:#x}u") * 0
    c = c.replace(f"{ORIG_VALUE:#x}u", f"{value:#x}u")   # 0x88888888u
    c = c.replace(old_hex, new_hex)                       # 0x88888888
    c = c.replace(f"{ORIG_VALUE:#x}", f"{value:#x}")      # 0x88888888 (小写)
    c2 = c.replace(f"{ORIG_LUI:#010x}", f"{lui:#010x}").replace(f"{ORIG_LUI:#x}", f"{lui:#x}")
    c2 = c2.replace(f"{ORIG_ADDI:#010x}", f"{addi:#010x}").replace(f"{ORIG_ADDI:#x}", f"{addi:#x}")
    # 大写变体
    c2 = c2.replace(f"0x{ORIG_LUI:08X}", f"0x{lui:08X}").replace(f"0x{ORIG_ADDI:08X}", f"0x{addi:08X}")
    open(C_FILE, "w", encoding="utf-8").write(c2)
    print(f"[ok] unlock40x_v70.c: SS0 字面量 {old_hex} -> {new_hex} (含 own_code_67 立即数)")

    # 2) blob (hex 搜索 lui/addi 字节序列)
    if os.path.exists(BLOB):
        b = bytearray(open(BLOB, "rb").read())
        pat = struct.pack("<II", ORIG_LUI, ORIG_ADDI)
        pat2 = struct.pack("<I", ORIG_LUI)
        hits = [i for i in range(len(b) - 7) if b[i:i + 4] == pat[:4] and b[i:i + 8] == pat]
        if hits:
            for off in hits:
                b[off:off + 8] = struct.pack("<II", lui, addi)
            open(BLOB, "wb").write(b)
            print(f"[ok] v67_payload.bin: 命中 {len(hits)} 处 SS0 立即数, 已 patch ({[hex(h) for h in hits]})")
        elif b.count(pat2):
            print(f"[!] v67_payload.bin: 找到孤立 lui x{b.count(pat2)} 处 (无配对 addi) — 需人工检查, 未 patch")
        else:
            print("[i] v67_payload.bin: 未含 SS0 立即数序列 — SS0 写来自 C 代码, 无需 patch (预期内)")
    print(f"\n[done] 变体 SS0 = {new_hex} 已就绪。下一步: WSL 构建 EFI -> 引导 -> ss0map read 验证")


def restore():
    if os.path.exists(BAK_C):
        shutil.copy2(BAK_C, C_FILE)
        print("[ok] unlock40x_v70.c 已还原")
    if os.path.exists(BAK_BLOB):
        shutil.copy2(BAK_BLOB, BLOB)
        print("[ok] v67_payload.bin 已还原")
    if not find_variant_backups():
        print("[i] 无备份 (本来就是原始状态)")


def show():
    c = open(C_FILE, "r", encoding="utf-8", errors="replace").read()
    hits = c.count("0x88888888")
    import re
    m = re.search(r"#define VAL_SS0_UNLOCKED\s+(0x[0-9A-Fa-f]+)", c)
    print(f"VAL_SS0_UNLOCKED = {m.group(1) if m else '?'}   (0x88888888 字面量残留 {hits} 处)")
    if find_variant_backups():
        print("当前存在 .orig 备份 = 处于变体态 (restore 可还原)")


if __name__ == "__main__":
    sanity()
    if len(sys.argv) < 2:
        show()
        sys.exit(0)
    a = sys.argv[1]
    if a == "--restore":
        restore()
    elif a == "--show":
        show()
    else:
        v = int(a, 16)
        assert 0 <= v <= 0xFFFFFFFF
        patch(v)
