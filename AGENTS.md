# AGENTS.md — AI 编码助手仓库约定

面向在本仓库工作的 AI 编码助手（CodeBuddy、Claude Code、Codex、Qoder、Trae 等）。
助手的个人状态目录/文件已全部 gitignore（见 `.gitignore` "AI 工具个人状态"段）；本文件是唯一入库的共享规则。

## 仓库概览

- CMP 40HX（TU106）SS0 解锁工具与研究仓。`main` = 产品发布线（`windows-v3.0` 源码）；`exp/*` = 研究分支。
- 研究文档：`docs/unlock_mechanism.md`（SS0 解锁机制）、`docs/dlss_wedge_rootcause.md`（DLSS × wedge 根因与缓解），索引见 `docs/README.md`。
- 研究工具在 `test/`（SS0 变体 patcher / DLSS 判别与置换 / GSP 固件扫描 / 算力基准），使用方法见 `test/README.md`。

## 语言与提交

- 文档、注释、提交信息一律简体中文；提交信息格式 `<type>: <主题>（<关键限定>）`，type 用 test/docs/chore/build/fix 等。
- PowerShell 下提交中文信息用 `git commit -F <UTF-8 无 BOM 文件>`，避免管道编码问题；提交前核对 `git status` 暂存面。
- 未经作者确认不执行 commit / push / 历史改写。

## 代码与脚本

- PowerShell 脚本一律 ASCII only（兼容 Windows PowerShell 5.1 无 BOM 解码，勿依赖 UTF-8 中文注释/字符串）。
- 脚本路径全部参数化或自动定位，不硬编码本机路径（驱动 store、游戏目录等因机器/驱动版本而异）。
- 文档引用的脚本路径必须真实存在，保证每个提交点自洽。

## 研究文档

- `docs/` 只收录已证实或交叉验证的结论；逐次实验记录与单机数据不入库（对第三方不构成可验证证据），关键数值内嵌文档表格。
- 术语约定：GPU 引擎不可恢复的僵死用 "wedge / 引擎级死锁"；面向最终用户的现象描述用"游戏画面卡死"；不用"死机/蓝屏"（易误解为 OS 级崩溃）。

## 不入库清单

- `docs/local/`：未发布草稿（含上游 issue 草稿）
- `temp/`：本地实验档案
- `windows-v3.0/tools/unlock40x/build_v70_elf.sh`：作者本地构建变体（未决定发布）
- `.gitignore` "AI 工具个人状态"段所列目录与文件（`.claude/` `.cursor/` `.trae/` `.codebuddy/` `.qoder/` `.zcode/` `.codex/` `.workbuddy/` `.windsurf/` `.codeium/` `.continue/` `.aider*` `.mcp.json`）
