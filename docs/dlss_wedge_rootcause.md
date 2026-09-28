# DLSS 模型族 × GSP-RM wedge 根因（指示器实证 + A-B-A 反转 + 覆盖干预验证）

> 环境：B450 + 5600G（核显亮机）+ CMP 40HX（TU106，伪装 RTX 2070，无头）；驱动 581.94（修改 INF，GSP 强依赖）。
> 前置：`unlock_mechanism.md`（n1 = DLSS NN 执行单元，fuse 出厂节流、SS0=0x88888888 强制全速）。
> 本文只收录已证实结论与必要证据；逐会话记录存于作者本地档案，未入库。

## 0. 结论（TL;DR）

1. **触发规律二值化（全部屏幕级实证）**：DLSS 超分运行 **Transformer 族 preset（J/K）** 时概率性触发 GSP-RM 引擎级 wedge；运行 **CNN 族 preset（A–F）** 时零触发。与游戏引擎、图形 API、DLSS DLL 版本无关。
2. **因果经双重干预验证**：①A-B-A 文件置换（Endfield 310.5.2 ↔ 3.7.20）；②驱动侧 DLSS 覆盖（见 §3）——Transformer 档 **7/7 wedge**（潜伏期 95 秒–40 分钟，含原生 60 帧条件），CNN 档全部干净（Endfield 覆盖态为**原生 60 帧**多会话）。
3. **实用缓解（最终方案）= 驱动侧 DLSS 覆盖**：全局开启 `DLSS - Enable DLL Override` 后，generic（非白名单）应用也在运行时改载驱动 store 的 DLSS（本机实测 310.9.0）并按 `Forced Preset Letter` 强制 preset（letter 未被游戏尊重时回退 CNN 档 A）——**游戏文件零改动，启动器校验/反作弊无感知**。Endfield 与 NTE 均已用此路径稳定运行于 CNN 档。
4. **机制**：Turing 无 FP8，官方实测第一代 Transformer 耗时约为 CNN 的 2 倍——RTX 2060 SUPER（与 40HX 同为 TU106）官方指南数据：1440p 1.01 → 2.02 ms（每帧 +1.0 ms）、4K 2.18 → 4.60 ms。这约一倍的张量负载增量把被强制全速的 n1 推过稳定性阈值。数据来源：官方 DLSS Programming Guide **310.1.0–310.4.0 历史版本**（310.5.0 起该表改为 Preset 维度并移除 Turing 中端行，故为历史快照；同表 2080 Ti 为 2.78×@4K）。
5. **CNN 逃生通道现状**：官方 310.6.0 曾将 Preset E/F 标记 deprecated，但最新 SDK（310.9.0）中 CNN 档 A 仍存活且可被覆盖路径选用——通道比文档时间线显示的更耐用，但长期趋势仍是收窄。

## 1. 触发矩阵（NGX 屏幕指示器读数）

指示器开启方式：注册表 `HKLM\SOFTWARE\NVIDIA Corporation\Global\NGXCore`，DWORD `ShowDlssIndicator = 1024 (0x400)`（低值无效）；游戏内左下角显示 Render Preset 字母、DLL 版本、内部/输出分辨率。脚本：`test/dlss/ngx_indicator.ps1`。

| 游戏 | 状态 | DLL | Preset | 模型族 | wedge |
|---|---|---|---|---|---|
| Endfield | 原生 | 310.5.2 | K | 一代 Transformer | **7/7**（95s–40min） |
| Endfield | 驱动覆盖 | 310.9.0 | A | CNN | **0**（多会话，原生 60 帧） |
| NTE | 原生 | 310.5.0 | K | 一代 Transformer | 偶发（含 09-26 20:11 一例） |
| NTE | 驱动覆盖 | 310.9.0 | A | CNN | **0**（累计会话干净） |
| WuWa | 原生 | 310.5.0 | F | CNN | 0 |
| WuWa | 驱动覆盖 | 310.9.0 | E | CNN | 0 |
| DF | 原生 | 3.1.1（老 CNN SDK） | — | CNN | 0 |

注：
- 游戏全名 Endfield = Arknights: Endfield、NTE = Neverness to Everness、WuWa = Wuthering Waves、DF = Delta Force。
- 原生分辨率由 DLSS 档位控制，非游戏固有属性，不列入比较；Autoexposure、图形 API（VK/D3D12）差异判定为非因子；**总 SM 占用率亦非判别量**（NTE 94–98% > Endfield 79–83%，结局却是偶发 vs 7/7——判别量是 n1 专属占空比，常规计数器不可见）。
- 09-27 05:03 的 NTE 事件为**显示驱动重置**（dwm.exe 两次崩溃，无 141/WATCHDOG/nvlddmkm 事件；重置后设备存活渲染 ~35 秒再静默退出），非本 wedge 签名，不计入统计；同游戏 CNN 会话显存 fb 常态 ~6GB（峰值 6.3GB / 8GB），"爆显存"嫌疑被削弱。
- 已发售游戏（WuWa/DF）pin 在 CNN 档、新游戏（Endfield/NTE）默认 K 档——与"新游戏问题概率大"的观察吻合。

### Preset ↔ 模型族映射（依据官方 DLSS Programming Guide 修订史）

**A–F = CNN 族**（F 面向 UltraPerf/DLAA）；G/H/I 保留；**J/K = 第一代 Transformer**（K 于 310.2.0 新增）；**L/M = 第二代 Transformer**（310.5.0 新增）。官方执行时间/显存表将 E,F 与 J,K/L,M 分列且数值差异巨大，与矩阵观测一致。

## 2. A-B-A 反转实验（文件置换路径）

同一游戏、同一内容、同一分辨率、同一 DLL 槽位，唯一变量 = 模型族（K ↔ E）。

**A 侧（3.7.20 → 回切 310.5.2）**：进游戏约 60 秒后 wedge。客观证据链：

| 证据 | 值 |
|---|---|
| dmon 死亡签名（5s 粒度） | sm 钉死高位 + mem→0 + pclk/mclk 崩塌（历史同款指纹） |
| WER | LiveKernelEvent **P1=141、P8=768_1**，18 条同秒爆发 |
| 转储 | WATCHDOG 内核 dump（与历史 wedge 同桶） |

**B 侧（换回 3.7.20，Preset E）**：初期会话干净；该 CNN 分支的完整验证随后由**驱动覆盖路径**接管（§3）——同一模型族分支以零文件改动的方式获得多会话**原生 60 帧**干净记录。

## 3. 干预路径：否定、排除与最终方案

**文件置换路线（对强校验游戏不可行，记录在案）**：NTE 启动器每次启动都在资源校验阶段（NGX 初始化之前）还原被替换的 DLL，且会主动清除只读属性（`attrib +R` 对抗 2 分钟内失效）。

**驱动侧覆盖路线（最终可行；两轮假阴性排除后打通）**：

- 机制：覆盖由**进程内 NGX 运行时读取驱动 profile 设置**实现；NVIDIA App 的白名单只控制 UI 入口，不限制驱动机制本身。指示器中的 "UE4 generic plugin" 字符串是 NVIDIA DLSS SDK 内置的遗留常量（DLL 内可检索），不是引擎版本声明，也不构成覆盖障碍。
- 首轮阴性的三个混杂（记录供复现者避坑）：①设在 per-game profile——**generic-plugin 类应用须设全局 profile**；②强制 Preset A——310.4.0 起从文档移除，310.5.x 可能拒收（CNN 权重仍在：WuWa 310.5.0 原生即渲染 F）；③**`DLSS - Enable DLL Override` 主开关为 Off**——决定性原因，preset 强制属于 DLL Override 通路，主开关关闭则 letter 永远不被读取。
- **可用配方**（NVIDIA Profile Inspector，全局 profile）：`DLSS - Enable DLL Override = On` + `Forced Preset Letter = 某 CNN 档` → Apply → 游戏运行时改载驱动 store DLSS（本机实测 310.9.0），游戏文件零改动。
- 覆盖行为细节：版本覆盖对三游戏全部生效；letter 强制仅 WuWa 尊重（已多次复测确认 E），NTE/Endfield 回退 A——机制未定（候选：游戏主动传 preset hint 时优先级更高）；A/E 同为 CNN 族，对本 wedge 问题等价。

**非缓解确认**：锁帧不是有效缓解——RTSS 45 cap（n1 平均占空比减半至 NTE 存活区间）下 Endfield 22 分钟即 wedge，潜伏期未延长 → **平均占空比不是频率差异的解释变量**，频率机制指向管线级调用模式差异（未定，见 §6）。

## 4. 实用建议

1. **首选：全局 DLL Override + CNN preset 强制**（§3 配方）——两问题游戏已验证；游戏更新/启动器校验均不影响；整体回退 = 开关切 Off。
2. 备选：无启动器强校验的游戏用 3.7.20 置换（Transformer 引入前最后公开发布版：3.8/3.9/3.10.0 从未作为 SDK 发布存在，Transformer 首见于 3.10.1.0）；置换游戏每次更新后校验在位版本（`test/dlss/dlss_ver_scan.ps1`）。
3. 不可置换且不开覆盖时：Transformer 档游戏**不建议开启 DLSS**（原生 / FSR3 / XeSS 替代）。V5（SS0=`0x88868808`，`unlock_mechanism.md` §5）仅作为"DLSS 无法关闭且必须避免死锁"的防死锁档（DLSS 帧率低于原生，净负收益），不应作为面向用户的缓解方案。
4. 判别任意游戏实际模型族：`ShowDlssIndicator`，2 秒读屏。

## 5. 面向上游的要点

对本仓库（解锁工具）：

1. 工具文档/README 披露风险：SS0 全速解锁下 DLSS × Transformer 档概率性引擎级死锁；给出判别方法（`ShowDlssIndicator`）与缓解路径（§3 配方 / CNN 档游戏 / 关 DLSS）。
2. 可选：支持 SS0 解锁值参数化（render-mask 表可配置），便于后续实验与特殊场景。

对 NVIDIA（超出本仓库范围，作为 issue 背景与转达事项）：

3. 官方 310.6.0 已将 CNN 档（E/F）标记 deprecated——覆盖路径目前仍可用（310.9.0 的 A 档存活），请为旧架构保留 CNN 档或提供官方旧模型回退。
4. n1 双态门控下"快而稳的 DLSS"不存在固件值解，根因（fuse 节流单元被 SS0 全速 × Transformer ~2× 负载）需在驱动/工具层正视。

## 6. 局限

- 覆盖态的累计时长仍在增长中（截至本文：Endfield/NTE 多会话干净；NTE 基线为偶发，其 CNN 侧结论随累计时长增强）。
- 频率差异（Endfield 7/7 vs NTE 偶发，同为 K 档）的机制**未定**：平均占空比干预（45 fps cap，占空比减半）未延长潜伏期 → 指向管线级调用模式差异或单次 eval 成本差异，现有用户态仪器不可分。
- 单卡单机；模型族判定 = 官方文档映射 + 指示器读数交叉，未做抓帧级验证。
- 结论 scope = 解锁态（SS0=0x88888888 类）的 40HX 系统：官方锁定驱动下 n1 本就处于 fuse 速率、不发生本 wedge，不存在向锁定态外推的问题。

## 7. 证据与复现

本文表格已内嵌关键数值（指示器读数、WER P1/P8、dmon 死亡签名、DLL md5、官方耗时数据）。单机原始数据不入库——对第三方不构成可验证证据；复现与本地取证方法见 `test/README.md`（指示器开关、置换/回切、版本扫描、dmon/WER 采集方法）。
