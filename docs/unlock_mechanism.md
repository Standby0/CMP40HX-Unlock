# SS0 解锁机制：已证实结论

> 对象：CMP 40HX（TU106）。技术依据：V67 canary exploit（Jon Pry, DOI 10.5281/zenodo.20916112）。
> 方法：boot 期 EFI 固件 MMIO dump（实验固件，作者本地档案）+ SS0 值逐变体 boot 验证 + 宿主端算力基准（FP16 HGEMM，`test/bench/bench_torch.py`）。
> 本文只收录经实验证实或交叉验证的结论；逐次实验记录存于作者本地档案，未入库。

## 1. 寄存器族与解锁链

- fuse-shadow 寄存器族（BAR0）：PLM `0x409650`、SS0 `0x409664`、SS0_RD `0x409668`、SS1 `0x40966C`。SS0 = FECS fuse-override 影子寄存器，8 个 nibble 对应 8 个算术单元的速率码；SS0_RD 为 9 字段的实际节流回读。
- 官方解锁链：ESP 固件内嵌的 v67 payload blob 在 GPU-L3 执行寄存器写入，每次开机把 SS0 置 `0x88888888`（全速覆盖），写影像穿透 TDR/FLR（always-on island）。

## 2. render-mask ROP 表（payload blob 内机制）

- 位置：blob 末部 `0xF940–0xF9FC`，交替 (VALUE, ADDR) 写记录序列；`0xCBD` 反复出现 = ROP slide gadget。SS0 记录为 14-dword 模板：`[cbd][1f89][0][0][VALUE][cbd][10aa][cbd][7d34][0][0][ADDR][cbd][1f89]`，VALUE@+0x10、ADDR@+0x2C。
- 裸立即数 `0x88888888` 位于 blob @`0xF988`——lui/addi 模式扫描的盲区，SS0 变体必须按记录 patch（工具已实现全落点）。
- ROP 消费起点在 blob `0xf8f8` 之后：向前部滑板海插入克隆记录不会被执行；**PLM 槽位记录的 VALUE 写不落地，SS0 槽位 VALUE 可任意改且必执行**（witness 记录实证）。
- 交叉验证：GA102 开源仓 `cmp90_fillv67` 同尺寸、同区域、同格式。

## 3. SS0 nibble 单元映射（7 个变体逐一 boot 实证）

| 字段 | 语义 | 关键证据 |
|---|---|---|
| **n1**（SS0 bits[7:4]；回读对应 SS0_RD field[1] bits[3:5]） | **DLSS NN 执行单元**（INT8/FP16-accum 类，GA100 映射假设对应 FMLA16），**双态门控**：0–7 全部坍缩到 fuse 节流档（速率码 2/3，开机动态），仅 8 = 全速 | n1=0 时 SS0_RD field[1]=3、DLSS 帧率下降、零 wedge；最小覆盖（仅 n1=8）时 DLSS 提速但触发 wedge |
| **n2** | PyTorch FP16(FP32-accum) 吞吐门 | n2=8 恒 52T；n1=8 + n2=1 组合下 FP16 跌至 1.10T（速率悬殊致调度病态） |
| **n4** | 非 Tensor 路径 | n4=6 算力无损（52.29T）且可存活 |
| n0/n3/n5–7 | override 无效（读 0 = 全速） | 各变体间行为无差异 |

速率码非线性：8=全速、9=1/16；0–7 为 fuse 枚举域（在 n1 上无中间档）。SS0_RD(0x409668) **诚实回读**实际节流（n1 ↔ RD field[1] 已 boot 校准）；SS1 不在 payload ROP 表内（其值来自宿主写，可存活）。

## 4. 写路径限制（为何变体只能 boot-time 注入）

- 运行态（PLM=0xFFFFFF8F）下宿主 PL0 直写 SS0 被静默丢弃（特权位仅 GPU-L3 可写）；CSB 别名 `0x8238xx` 读出 priv-gated；FUSE_SS 影子（`0x8207d4`）经 GPU-L3 写即挂死 CSB/SEC2。
- GSP-RM 固件（gsp_tu10x.bin，30MB RV64）静态扫描：RM 只消费 SS0_RD（9 字段拆解器 + 单字段 getter），不引用 PLM/0x820xxx/0x8238xx；SS0_RD 本就诚实反映 override——"让 RM 知情"没有落点。
- 综合结论：SS0 的任何写入路径都收敛到 payload ROP 表（boot-time）；值域收窄与"RM 知情"两条修复路线均被实验终结。

## 5. 实用产出

| SS0 值 | 效果 |
|---|---|
| `0x88888888`（官方） | Tensor 全速（FP16 ~52T）+ PCIe Gen2；DLSS 会话概率性触发 GSP-RM wedge（根因见 `dlss_wedge_rootcause.md`） |
| `0x88868808`（V5，本研究产出） | n2=8 保持全速吞吐、n1=0 回落 fuse 节流：对任意 DLSS 模型档稳定（已含 Transformer 档实证），**但 n1 回出厂速率 = 解锁的 DLSS 收益归零——实测 DLSS-on 帧率不升反降（锁定态签名，低于原生）**。它不是"DLSS 安全档"：仅在"DLSS 无法关闭且必须避免死锁"时作为防死锁档使用；其核心价值是根因定位的最强佐证（单 nibble 差异决定 wedge 与否）。CNN 档游戏同样无需此值 |

> 注意：n1 双态门控（fuse 节流 / 全速，无中间档）意味着在本硬件上 **"DLSS 快"与"DLSS 稳"不可兼得**——全速 × Transformer 概率性死锁，fuse 速率下 DLSS 为净负收益。两者兼得的唯一路径是把负载降到 CNN 模型族（见 `dlss_wedge_rootcause.md`）。

## 6. 工具与落地路径

- `test/variant/patch_variant.py`：SS0 全落点 patcher——把 §5 任一值写入 C 与 blob 后，用仓库自带 `windows-v3.0/tools/unlock40x/build_v70.sh`（MSYS2 gnu-efi 流程）构建 EFI，替换 ESP 两处即完成部署
- 宿主侧寄存器读取：随 release 分发的 `40HXCheck.exe`（SS0 / Gen2 状态）
