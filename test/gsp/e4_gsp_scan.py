#!/usr/bin/env python3
"""E4: 扫描 gsp_tu10x.bin（GSP-RM, RV64）里 RM 消费的寄存器常量。
三路搜索：
  A) 原始 32 位 LE 常量：落在候选寄存器窗口内的出现位置
  B) RISC-V li 展开的 lui+addi/addiw 立即数对（目标地址 → hi20/lo12 编码）
  C) ASCII 字符串（fuse/speed/ss0/plm/ovr 等模块线索）
用法: python e4_gsp_scan.py [path-to-gsp_bin]
默认自动定位 DriverStore 最新 nv*.inf_amd64_*/gsp_tu10x.bin（兼容官方/修改 INF 安装）；非 Turing 设备请传参指定固件
"""
import struct, sys, re, glob, os, collections

P = sys.argv[1] if len(sys.argv) > 1 else None
if P is None:
    cands = glob.glob(r'C:\Windows\System32\DriverStore\FileRepository\nv*.inf_amd64_*\gsp_tu10x.bin')
    P = max(cands, key=os.path.getmtime) if cands else None
if P is None:
    sys.exit('usage: python e4_gsp_scan.py <path-to-gsp_tu10x.bin>\n'
             '(auto-locate failed: no gsp_tu10x.bin found in DriverStore)')
d = open(P, 'rb').read()
print(f'file: {P}\nsize: {len(d)} (0x{len(d):x})')

# .fwimage 段（RM 实体）
e_shoff, = struct.unpack_from('<Q', d, 0x28)
e_shentsize, e_shnum = struct.unpack_from('<HH', d, 0x3A)
fw_off = fw_size = None
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    name, typ, flags, addr, off, size = struct.unpack_from('<IIQQQQ', d, o)
    if typ == 1 and name == 1:  # .fwimage（第 1 节）
        fw_off, fw_size = off, size
if fw_off is None:
    fw_off, fw_size = 0, len(d)
fw = d[fw_off:fw_off + fw_size]
print(f'.fwimage @0x{fw_off:x} size 0x{fw_size:x} (扫描区)')

# 目标地址集：TU106 已证 0x4096xx + GA102 CSB 别名窗 + GA100 FUSE_SS 家族
KEY = {
    0x00409650: 'PLM(TU106,payload写)',
    0x00409664: 'SS0(TU106,payload写)',
    0x00409668: 'SS0_RD(TU106)',
    0x0040966C: 'SS1(TU106,payload写)',
    0x004096EC: 'payload第三写(0xCBD)',
    0x00823800: 'GA102 PLM页',
    0x00823804: 'GA102 PLM',
    0x00823810: 'GA102 PCIE_FUSE_OVR',
    0x00823814: 'GA102 FEAT_READOUT_0',
    0x0082381C: 'GA102 SS0别名',
    0x00823820: 'GA102 SS1别名',
    0x00823830: 'GA102 GFX_SPEED_SEL',
    0x00820224: 'GA100 FUSE_SS_PLM',
    0x0082059C: 'GA100 FUSE_SS_FFMA',
    0x008207D4: 'GA100 FUSE_SS_FMLA16',
    0x008207D8: 'GA100 FUSE_SS_FMLA32',
    0x008207DC: 'GA100 FUSE_SS_IMLA0',
    0x008207E0: 'GA100 FUSE_SS_IMLA1',
    0x008207E4: 'GA100 FUSE_SS_IMLA2',
    0x008207E8: 'GA100 FUSE_SS_IMLA3',
    0x008207EC: 'GA100 FUSE_SS_IMLA4/DP',
}
WIN = [(0x00409600, 0x00409700, '0x4096xx'),   # TU106 fuse-shadow 邻域
       (0x00820000, 0x00821000, '0x820xxx'),   # fuse 区（GA100 布局）
       (0x00823800, 0x00823900, '0x8238xx')]   # CSB 别名窗（GA102 布局）

# ---- A) 原始 32 位 LE 常量 ----
print('\n== A) raw 32-bit LE constants in windows ==')
hits = collections.defaultdict(list)
n = len(fw) - 4
# 一次线性扫描，把落在窗口里的值记下（比逐值 find 快不了多少，但全窗口可统计）
for i in range(0, n, 4):
    v = fw[i] | (fw[i+1] << 8) | (fw[i+2] << 16) | (fw[i+3] << 24)
    for lo, hi, tag in WIN:
        if lo <= v < hi:
            hits[(v, tag)].append(i)
            break
for (v, tag), offs in sorted(hits.items()):
    mark = f'  <-- {KEY[v]}' if v in KEY else ''
    show = ', '.join(f'0x{o+fw_off:x}' for o in offs[:6])
    more = f' (+{len(offs)-6})' if len(offs) > 6 else ''
    print(f'  0x{v:08x} [{tag}] x{len(offs)} @ {show}{more}{mark}')

# ---- B) RISC-V lui+addi 立即数对 ----
print('\n== B) RISC-V lui+addi/addiw pairs (li expansion) ==')
def lui_enc(A):
    lo = A & 0xFFF
    hi = (A >> 12) & 0xFFFFF
    if lo >= 0x800:
        hi = (hi + 1) & 0xFFFFF
    return hi, lo & 0xFFF

# 建索引：lui 指令 → 位置（30MB 全扫一次）
lui_pos = collections.defaultdict(list)
for i in range(0, len(fw) - 4, 4):
    w = struct.unpack_from('<I', fw, i)[0]
    if (w & 0x7F) == 0x37:  # lui
        lui_pos[(w >> 12) & 0xFFFFF].append(i)
print(f'  lui instructions indexed: {sum(len(v) for v in lui_pos.values())}')

def addi_like(w):
    # addi (0x13) / addiw (0x1B), funct3=0
    op = w & 0x7F
    if op not in (0x13, 0x1B):
        return None
    if ((w >> 12) & 0x7) != 0:
        return None
    imm = (w >> 20) & 0xFFF
    if imm >= 0x800:
        imm -= 0x1000
    return imm

for A, label in KEY.items():
    hi, lo = lui_enc(A)
    positions = lui_pos.get(hi, [])
    found = []
    for p in positions:
        for k in (1, 2, 3):  # lui 后 1-3 条内出现 addi/addiw
            if p + 4*k + 4 > len(fw):
                break
            w2 = struct.unpack_from('<I', fw, p + 4*k)[0]
            imm = addi_like(w2)
            if imm == (lo - 0x1000 if lo >= 0x800 else lo):
                rd_lui = (struct.unpack_from('<I', fw, p)[0] >> 7) & 0x1F
                rd_ad = (w2 >> 7) & 0x1F
                if rd_lui == rd_ad:  # 同寄存器（li 展开）
                    found.append(p)
                    break
    if found:
        show = ', '.join(f'0x{x+fw_off:x}' for x in found[:6])
        more = f' (+{len(found)-6})' if len(found) > 6 else ''
        print(f'  0x{A:08x} {label}: {len(found)} hit(s) @ {show}{more}')

# 无 addi 配对的裸 lui（hi20 命中）——目标可能是寄存器基址 hi 部分
print('\n== B2) bare lui hi20 hits (base-register style) ==')
for A, label in KEY.items():
    hi = (A >> 12) & 0xFFFFF
    np = len(lui_pos.get(hi, []))
    if np:
        print(f'  hi20=0x{hi:05x} (base 0x{hi<<12:08x}, ~{label}): {np}')

# ---- C) 字符串线索 ----
print('\n== C) strings (fuse/speed/ss/plm/ovr/feat) ==')
pat = re.compile(rb'[ -~]{4,}')
seen = set()
for m in pat.finditer(fw):
    s = m.group()
    if re.search(rb'(?i)fuse|speed.?sel|^ss[01]_?|_ss[01]|plm|featsel|feat_|ovr', s):
        t = s.decode('ascii', 'replace')
        if t not in seen:
            seen.add(t)
            if len(seen) <= 80:
                print(f'  @0x{m.start()+fw_off:x}: {t[:100]}')
print(f'(total {len(seen)} unique)')
print('E4_SCAN_DONE')
