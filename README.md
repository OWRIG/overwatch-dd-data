# overwatch-dd-data Skill

这是一个给 AI 编程工具加载的个人 Skill 包，用于在私有、本机环境里辅助导出并分析自己网易 DD / 守望先锋（Overwatch）战绩数据。仓库的核心交付物是 `SKILL.md` / `AGENTS.md`，`scripts/` 只是配套的本地辅助脚本。

> ⚠️ **本 Skill 未获得网易、暴雪或相关权利方授权或背书；`datamsapi` 不是公开承诺的开发者 API。本仓库不是官方 SDK、公共爬虫、数据服务或 API 中转。使用前请确认你理解并接受相关用户协议、账号和法律风险。建议仅作为个人私有 Skill 保存和加载，详见[Skill 定位](#skill-定位)、[合规与风险边界](#合规与风险边界)和[免责声明](#免责声明)。**

---

## 目录

- [工作原理](#工作原理)
- [Skill 定位](#skill-定位)
- [合规与风险边界](#合规与风险边界)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [作为 Skill 使用](#作为-skill-使用)
- [脚本访问的接口](#脚本访问的接口)
- [并发与速率控制](#并发与速率控制)
- [文件结构](#文件结构)
- [安全与隐私](#安全与隐私)
- [免责声明](#免责声明)

## 工作原理

```
网易DD客户端(WebView2)  ──(HTTPS)──▶  datamsapi.ds.163.com/v1/a19ld5tool/*
        │                                          ▲
        │ 本地 HTTPS 调试代理(127.0.0.1:8080)         │
        └──── 识别本人会话里的 token + roleId ───────┘
                                                    │
本地辅助脚本使用本人会话参数请求 ───────▶  拉取数据 ──▶ ow_analyze.py 分析
```

`token` + `roleId` 属于私人会话凭据，只能用于本人账号、本机本地分析。`token` 可能过期；如果接口报鉴权错误，请停止使用旧凭据，并仅在确认自己有权继续访问时重新获取本人会话凭据。

## Skill 定位

- 这是一个**个人私有 Skill**：让 AI 编程工具按说明协助你在本机完成环境检查、数据导出和本地分析。
- `SKILL.md` / `AGENTS.md` 是主要入口；`scripts/` 是辅助脚本，不是对外提供的 SDK、库、命令行产品或 Web 服务。
- 不建议把它发布成“网易 DD 数据接口工具”“守望先锋战绩爬虫”“公共 API 客户端”等形式，也不要做成给他人使用的在线服务。
- 如果你公开分享本仓库，建议只保留 Skill 的研究说明和风险提示，删除私人凭据、原始数据、批量化改动，以及任何会鼓励他人直接复用会话凭据的内容。

## 合规与风险边界

请先读这一节，再决定是否继续：

- 本项目不是官方 SDK、官方 API 文档或授权接口封装，不代表网易、暴雪或任何相关权利方立场。
- 本 Skill 只面向**本人账号、本机、非商业、本地分析**。不要把它做成公开服务、托管面板、API 中转、批量监控、数据集采集器或面向他人的工具。
- 不要截获他人流量，不要收集、购买、交换、共享或使用他人的 `token`、`roleId`、`bnetId` 等凭据或标识。
- `--detail` 会额外包含队友/对手的昵称、ID 和本局数据。除非确有本地分析需要，否则不要抓详情；抓到后也不要公开分享原始数据，发布报告前应匿名化。
- 不要尝试绕过登录、鉴权、风控、加密、验证码、限流或服务方的访问限制。若服务方提示禁止、接口关闭、凭据失效、账号异常，或权利方要求停止/删除，请立即停止使用并配合处理。
- 如果你要公开发布本仓库，建议先删除私人凭据、原始数据、接口细节和可直接运行的抓取说明；更稳妥的方式是保持私有。

## 前置条件

- **Python 3**（脚本只用标准库，无需 pip install）
- **网易 DD 客户端** 并已登录、绑定战网
- Windows（抓包脚本是 PowerShell；mitmproxy 也可手动装 macOS/Linux 版）

## 快速开始

通常你会把本仓库作为 Skill 加载到个人 AI 编程工具里，再让 AI 按本 README 和 `SKILL.md` / `AGENTS.md` 协助操作。下面是需要手动验证或不使用 AI 时的本地流程。

```powershell
cd overwatch-dd-data/scripts

# 1. 确认风险后，在本机临时开启 HTTPS 调试代理
.\setup_capture.ps1
#    然后手动：完全退出并重开网易DD → 登录 → 进守望战绩页点几下
#    看到 "CREDS CAPTURED" 即识别到本人会话参数（自动写入 creds.json）
.\setup_capture.ps1 -Cleanup      # 抓完务必还原系统

# 2. 拉数据（读 creds.json，单线程温和速率；默认不保存队友/敌方详情）
python ow_pull.py --seasons 21,22,23 --out data.json

# 3. 分析
python ow_analyze.py --in data.json
#    → report.txt + hero_stats.csv + map_stats.csv
```

常用参数：
- `--mode sport|leisure` 竞技 / 快速
- `--season 23` 单赛季
- 不加 `--detail` 只拉列表（更推荐；不会额外保存队友/敌方详情）
- `--delay 0.5` 调整请求间隔（硬性下限 0.3s）

## 作为 Skill 使用

本仓库首先是一个 Skill 包，同时提供 `SKILL.md`（opencode/Claude Code 格式）和 `AGENTS.md`（Codex/Qwen/Kimi 通用格式），方便你在**个人私有环境**里调用。不要把含有私人凭据、原始数据或可用于批量访问的修改版公开分发。

| 工具 | 安装位置 | 加载文件 |
|---|---|---|
| **opencode** | `.opencode/skills/overwatch-dd-data/` 或全局 `~/.config/opencode/skills/` | `SKILL.md`（自动发现） |
| **Claude Code** | `~/.claude/skills/overwatch-dd-data/` | `SKILL.md`（自动发现） |
| **Codex (OpenAI)** | 项目根 `AGENTS.md` 里加 `@overwatch-dd-data/AGENTS.md` | `AGENTS.md` |
| **Qwen Code** | 同 Codex | `AGENTS.md` |
| **Kimi Code** | 同 Codex | `AGENTS.md` |

> **隐私提醒**：Skill 只应在你信任的本地/私有 AI 环境里使用。不要让 AI 工具读取、上传或总结 `creds.json`、`data.json`、`report.txt`、`hero_stats.csv`、`map_stats.csv` 里的私人数据，除非你明确知道该工具的数据处理方式并愿意承担风险。

## 脚本访问的接口

以下列表只是为了让使用者知道脚本会访问什么，并不表示这些接口是公开、稳定或授权给第三方使用的 API。如果公开发布本仓库，建议删去本节或将仓库设为私有。

主机 `https://datamsapi.ds.163.com/v1/a19ld5tool/`，脚本实际使用：

| 路径 | 用途 |
|---|---|
| `queryCountInfo` | 服务端聚合统计（各英雄胜率/场均/每10min、职责统计、最常玩英雄） |
| `queryMatchList` | 对战历史列表（地图+英雄+比分+KDA+伤害治疗） |
| `queryMatchInfo` | 单场详情（全队10人、英雄playtime、perks、AI点评） |

公开配置（无需鉴权）：
- `https://s.166.net/config/ds_ow/ow_hero_config.json` — 英雄 heroGuid→名/职责/图标
- `https://s.166.net/config/ds_ow/ow_map_config.json` — 地图 mapGuid→名/模式/图标
- `POST https://inf.ds.163.com/v1/web/gameData/game/season-time/get-by-app-key` body `{"appKey":"ld5"}` — 赛季列表

> ⚠️ `matchRet` 是权威胜负标志。**不要**用 `teamScore>opponentScore` 判胜（push/闪点图比分与胜负不一致，会系统性虚高胜率）。

## 并发与速率控制

**请务必遵守，避免对网易 DD 服务造成压力：**

- ✅ 本脚本为**单线程顺序请求**，不开并发。请勿自行改造成多线程/协程批量请求。
- ✅ 默认请求间隔 **0.4 秒**，硬性下限 **0.3 秒**（`ow_pull.py` 会强制提升低于此值的 `--delay`）。
- ✅ 拉取每场详情（`--detail`）的请求数 = 场次数。上千场时**分批进行**，每批间拉长间隔。
- ✅ 抓 token 用的 mitmproxy 抓完**务必 `setup_capture.ps1 -Cleanup`** 还原，勿长期挂代理。
- ❌ 不要在短时间内反复重跑全量拉取。
- ❌ 不要把本工具用于实时高频监控。
- ❌ 不要把本工具改造成给多人使用的公共服务。

## 文件结构

```
overwatch-dd-data/
├── README.md                # 本文件
├── SKILL.md                 # Skill 主入口（opencode/Claude Code，带 frontmatter）
├── AGENTS.md                # Skill 说明（Codex/Qwen/Kimi 通用）
├── .gitignore               # 排除 creds.json / data.json 等敏感输出
└── scripts/
    ├── setup_capture.ps1    # 一键环境（搭建/还原/检查）
    ├── ow_capture_addon.py  # mitmproxy 插件，识别本人会话参数并写入 creds.json
    ├── ow_pull.py           # 本地数据导出（多赛季+可选详情，单线程温和速率）
    └── ow_analyze.py        # 通用分析（胜负驱动/英雄/地图/职责/队友）
```

## 安全与隐私

- `creds.json`（私人 token）和 `data.json`（对战数据，可能含队友/对手昵称、ID、单局表现）已被 `.gitignore` 排除，**切勿提交 git 或公开分享**。
- token 会过期。接口报鉴权错误时，请停止使用旧凭据；如仍需本地分析，再按上述流程重新获取本人会话参数。
- 默认尽量不加 `--detail`；如果需要发布分析结论，请只发布汇总结果，并先匿名化或删除他人标识。
- 定期删除不再需要的原始数据和凭据。不要把 `creds.json` 发给任何人，也不要贴到 issue、聊天工具或 AI 对话里。

## 免责声明

本项目**仅供个人学习、技术研究与本地数据分析**，不得用于任何商业用途、公开服务或批量采集。

1. 使用者需自行阅读并遵守网易 DD、网易游戏、暴雪、战网及其他相关服务的用户协议、服务条款、隐私政策和适用法律法规。可参考：[网易游戏用户协议](https://unisdk.update.netease.com/html/latest_v31.html)、[Blizzard End User License Agreement](https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement)、[Blizzard Developer API Terms of Use](https://www.blizzard.com/en-us/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use)。
2. 本项目未获得网易、暴雪或相关权利方授权或背书。项目中提到的接口可能是非公开、非稳定、非授权给第三方使用的接口，服务方有权随时变更、关闭、限制或追究滥用行为。
3. 本工具不试图破解密码、伪造账号或绕过服务端鉴权；但本地 HTTPS 调试代理、会话参数提取和自动化请求仍可能被服务条款认定为不被允许的行为。是否使用以及如何使用，由使用者自行判断并承担全部风险。
4. 本工具只应用于本人账号的本地分析。不得用于获取、识别、跟踪、画像、公开或交易他人数据；包含他人标识的数据不得公开传播。
5. 作者不对因使用本项目产生的任何直接或间接后果承担责任，包括但不限于账号限制/封禁、数据丢失、隐私泄露、服务异常、第三方投诉或法律纠纷。
6. 请严格遵守[并发与速率控制](#并发与速率控制)一节，不得对网易 DD 或相关服务造成压力、干扰或破坏。因滥用导致的任何后果由使用者自行承担。
7. 本项目不包含网易或暴雪的专有代码；相关名称、商标、图标、游戏内容和数据权利归各自权利人所有。若权利方认为本项目侵犯权益或要求停止公开，请联系作者删除或下架。

---

*本项目不附明示授权，按"原样"提供。使用即代表你已阅读、理解并接受上述风险与免责声明。*
