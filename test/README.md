# 研究工具（test/）

实验/研究工具脚本。脚本内的游戏/仓库路径均可参数化或自脚本位置推导；PowerShell 脚本为 ASCII 编码（PS 5.1 兼容）。

## variant/ — SS0 变体 patcher（V5 值落地工具）

| 脚本 | 用途 |
|---|---|
| `patch_variant.py` | SS0 值全落点 patch：`python patch_variant.py <hex>` 同步修改 C 全部直写点与 payload blob ROP 记录（`0x88888888` 裸立即数位于 lui/addi 模式扫描盲区，须按记录 patch）；`--restore` / `--show`。仓库路径自脚本位置推导 |

> `.orig` 基线被仓库 gitignore（与仓库内文件恒等）：首次使用 `cp windows-v3.0/tools/unlock40x/unlock40x_v70.c{,.orig}`、`cp windows-v3.0/tools/unlock40x/v67_payload.bin{,.orig}`。
> patch 完成后用仓库自带 `windows-v3.0/tools/unlock40x/build_v70.sh`（MSYS2 gnu-efi 流程，PE 格式 libefi.a）构建 EFI，替换 ESP `\EFI\40HX\40HXUNLK.EFI` 与 `\EFI\boot\bootx64.efi` 两处即完成部署。

## dlss/ — DLSS 模型族研究（配套 `docs/dlss_wedge_rootcause.md`）

| 脚本 | 用途 |
|---|---|
| `ngx_indicator.ps1` | 开/关 NGX 屏幕指示器（默认开 `ShowDlssIndicator=1024`，`-Off` 恢复；需管理员）；游戏内直接读 Render Preset / DLL 版本，改后需重启游戏 |
| `dlss_swap.ps1` | 通用 DLSS DLL 置换（进程检查 + 自动备份 + md5 校验）：`-GameDll <路径> -Source <新DLL>` |
| `dlss_ver_scan.ps1` | 扫描指定游戏目录的 DLSS/Streamline DLL 版本：`-Games '路径1','路径2'` |

## gsp/ — GSP-RM 静态分析

| 脚本 | 用途 |
|---|---|
| `e4_gsp_scan.py` | 对 GSP 固件（RV64）做常量 / lui+addi 对 / 字符串扫描，定位 RM 消费 SS0_RD 的代码面 |

## bench/ — 算力基准

| 脚本 | 用途 |
|---|---|
| `bench_torch.py` | FP16/FP32 GEMM 算力基准（本机判据：解锁 ~52T / 锁定 ~8T） |

## 采集方法速查

- GPU 5s 采样：`nvidia-smi dmon -s puc -d 5 -o TD -f soak.log`（wedge 死亡签名：sm 钉死高位 + mem→0 + 时钟崩塌）
- WER 查询（不需要管理员）：`Get-WinEvent -FilterHashtable @{LogName='Application';Id=1001}`，XML 中 `P1=141`、`P8=768_1`

> 单机测试数据不入库：对第三方不构成可验证证据，结论关键数值已内嵌 docs 表格；本地取证按上述方法自行采集。
