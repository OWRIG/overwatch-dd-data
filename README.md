# overwatch-dd-data

获取守望先锋（Overwatch）对战数据（对战历史、英雄/地图统计、单场详情等），通过网易 DD 客户端的 datamsapi 接口。自带 mitmproxy 自动抓 token、数据拉取、分析三件套，可在 opencode / Claude Code / Codex / Qwen Code / Kimi Code 等 AI 编程工具中作为 skill 消费。

> ⚠️ **本项目仅供学习交流使用，详见下方[免责声明](#免责声明)。**

---

## 目录

- [工作原理](#工作原理)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [各 AI 工具安装方式](#各-ai-工具安装方式)
- [接口清单](#接口清单)
- [并发与速率控制](#并发与速率控制)
- [文件结构](#文件结构)
- [安全](#安全)
- [免责声明](#免责声明)

## 工作原理

```
网易DD客户端(WebView2)  ──(HTTPS)──▶  datamsapi.ds.163.com/v1/a19ld5tool/*
        │                                          ▲
        │ mitmproxy 中间人(本地8080)                 │
        └──── 抓 URL 里的 token + roleId ────────────┘
                                                    │
本脚本(ow_pull.py) 带 token 直接请求 ──────▶  拉取数据 ──▶ ow_analyze.py 分析
```

接口鉴权靠 URL 里的 `token` + `roleId`，无需 cookie。`token` 由 DD 绑定战网后下发，可能过期（失效就重新抓一次）。

## 前置条件

- **Python 3**（脚本只用标准库，无需 pip install）
- **网易 DD 客户端** 并已登录、绑定战网
- Windows（抓包脚本是 PowerShell；mitmproxy 也可手动装 macOS/Linux 版）

## 快速开始

```powershell
cd overwatch-dd-data/scripts

# 1. 装 mitmproxy + CA 证书 + 设系统代理，启动监听
.\setup_capture.ps1
#    然后手动：完全退出并重开网易DD → 登录 → 进守望战绩页点几下
#    看到 "CREDS CAPTURED" 即抓到 token(自动写入 creds.json)
.\setup_capture.ps1 -Cleanup      # 抓完务必还原系统

# 2. 拉数据（读 creds.json，单线程温和速率）
python ow_pull.py --seasons 21,22,23 --detail --out data.json

# 3. 分析
python ow_analyze.py --in data.json
#    → report.txt + hero_stats.csv + map_stats.csv
```

常用参数：
- `--mode sport|leisure` 竞技 / 快速
- `--season 23` 单赛季
- 不加 `--detail` 只拉列表（快，无队友/敌方数据）
- `--delay 0.5` 调整请求间隔（硬性下限 0.3s）

## 各 AI 工具安装方式

本仓库同时提供 `SKILL.md`（opencode/Claude Code 格式）和 `AGENTS.md`（Codex/Qwen/Kimi 通用格式），内容一致。

| 工具 | 安装位置 | 加载文件 |
|---|---|---|
| **opencode** | `.opencode/skills/overwatch-dd-data/` 或全局 `~/.config/opencode/skills/` | `SKILL.md`（自动发现） |
| **Claude Code** | `~/.claude/skills/overwatch-dd-data/` | `SKILL.md`（自动发现） |
| **Codex (OpenAI)** | 项目根 `AGENTS.md` 里加 `@overwatch-dd-data/AGENTS.md` | `AGENTS.md` |
| **Qwen Code** | 同 Codex | `AGENTS.md` |
| **Kimi Code** | 同 Codex | `AGENTS.md` |

> **通用做法**：把整个 `overwatch-dd-data` 文件夹放进项目，在项目根的 `AGENTS.md` 加一行 `@overwatch-dd-data/AGENTS.md`，上述工具基本都能识别。然后对 AI 说"帮我拉守望先锋对战数据"即可触发。

## 接口清单

主机 `https://datamsapi.ds.163.com/v1/a19ld5tool/`：

| 路径 | 用途 |
|---|---|
| `queryCountInfo` | 服务端聚合统计（各英雄胜率/场均/每10min、职责统计、最常玩英雄） |
| `queryMatchList` | 对战历史列表（地图+英雄+比分+KDA+伤害治疗） |
| `queryMatchInfo` | 单场详情（全队10人、英雄playtime、perks、AI点评） |
| `queryCard` | 玩家卡片（昵称/level/游戏时长） |
| `billboard/getUserHeroBillboard` | 英雄榜单 |

公开配置（无需鉴权）：
- `https://s.166.net/config/ds_ow/ow_hero_config.json` — 英雄 heroGuid→名/职责/图标
- `https://s.166.net/config/ds_ow/ow_map_config.json` — 地图 mapGuid→名/模式/图标
- `POST https://inf.ds.163.com/v1/web/gameData/game/season-time/get-by-app-key` body `{"appKey":"ld5"}` — 赛季列表

> ⚠️ `matchRet` 是权威胜负标志。**不要**用 `teamScore>opponentScore` 判胜（push/闪点图比分与胜负不一致，会系统性虚高胜率）。

## 并发与速率控制

**请务必遵守，不要把网易 DD 的服务弄挂了：**

- ✅ 本脚本为**单线程顺序请求**，不开并发。请勿自行改造成多线程/协程批量请求。
- ✅ 默认请求间隔 **0.4 秒**，硬性下限 **0.3 秒**（`ow_pull.py` 会强制提升低于此值的 `--delay`）。
- ✅ 拉取每场详情（`--detail`）的请求数 = 场次数。上千场时**分批进行**，每批间拉长间隔。
- ✅ 抓 token 用的 mitmproxy 抓完**务必 `setup_capture.ps1 -Cleanup`** 还原，勿长期挂代理。
- ❌ 不要在短时间内反复重跑全量拉取。
- ❌ 不要把本工具用于实时高频监控。

## 文件结构

```
overwatch-dd-data/
├── README.md                # 本文件
├── SKILL.md                 # opencode/Claude Code 说明书（带 frontmatter）
├── AGENTS.md                # Codex/Qwen/Kimi 通用说明书
├── .gitignore               # 排除 creds.json / data.json 等敏感输出
└── scripts/
    ├── setup_capture.ps1    # 一键环境（搭建/还原/检查）
    ├── ow_capture_addon.py  # mitmproxy 插件，自动提取 token 写入 creds.json
    ├── ow_pull.py           # 数据拉取（多赛季+详情，单线程温和速率）
    └── ow_analyze.py        # 通用分析（胜负驱动/英雄/地图/职责/队友）
```

## 安全

- `creds.json`（你的私人 token）和 `data.json`（对战数据，含队友游戏记录）已被 `.gitignore` 排除，**切勿提交 git 或公开分享**。
- token 会过期，接口报鉴权错误就重跑抓取步骤。
- 本方法只获取**绑定本人战网**的账号数据。

## 免责声明

本项目**仅供学习交流与技术研究所用**，不得用于任何商业用途。

1. 使用者需**遵守网易DD、暴雪及各相关服务的用户协议与服务条款**。本项目不对接口可用性做任何保证，服务方有权随时变更或关闭接口。
2. 本工具仅获取**绑定使用者本人战网的账号数据**，不绕过任何鉴权机制、不爬取他人隐私数据。请勿用于获取他人数据或任何侵犯他人隐私的用途。
3. **使用者自负全部使用风险**。作者不对因使用本工具而产生的任何直接或间接后果（包括但不限于账号封禁、数据丢失、服务异常）承担责任。
4. 请严格遵守[并发与速率控制](#并发与速率控制)一节，**不得对网易DD服务造成压力或破坏**。因滥用导致的任何后果由使用者自行承担。
5. 本项目不包含任何网易或暴雪的专有代码或数据，所有商标版权归 respective 所有者。
6. 如本项目侵犯了任何方的权益，请联系作者删除。

---

*本项目不附明示授权，按"原样"提供。使用即代表你已阅读并同意上述免责声明。*
