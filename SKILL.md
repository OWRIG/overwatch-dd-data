---
name: overwatch-dd-data
description: 获取守望先锋(Overwatch)对战数据，通过网易DD/网易大神 datamsapi 接口。Use when the user wants to fetch Overwatch match history, hero/map stats, or battle data via NetEase DD (网易DD / 网易大神). Triggers on keywords: 守望先锋, overwatch, 网易DD, 战绩, 对战数据, datamsapi, cc.163.com, hero stats, map winrate.
---

# 守望先锋对战数据获取 (NetEase DD / datamsapi)

> Agent 执行前必须先阅读 `AGENT_GUIDE.md`，并以其中的隐私、合规、速率和 git 边界作为默认行为。

通过网易DD客户端的 datamsapi 接口获取守望先锋对战数据（对战历史、英雄/地图统计、单场详情等）。

## 数据流

```
网易DD客户端(WebView2) → datamsapi.ds.163.com/v1/a19ld5tool/* → 本脚本拉取
```

接口鉴权靠 URL 里的 `token` + `roleId`，无需 cookie。`token` 由 DD 绑定战网后下发，可能过期（失效就重新抓一次）。

## 三步流程

### 第1步：抓取 token + roleId（一次性，直到过期）

运行一键环境脚本（装 mitmproxy + CA 证书 + 设系统代理）：

```powershell
# 在本 skill 的 scripts 目录下
.\setup_capture.ps1
```

脚本会：
1. `winget install mitmproxy.mitmproxy`
2. 生成并导入 mitmproxy CA 到 `Cert:\CurrentUser\Root`
3. 启动 mitmdump（带自动提取 addon）监听 `127.0.0.1:8080`
4. 保存原系统代理，把系统代理临时指向 `127.0.0.1:8080`
5. 如果原本已有系统代理，会自动把它作为 mitmproxy 上游代理；也可手动传 `-UpstreamProxy 127.0.0.1:7897`

**然后让用户操作**：完全退出并重开网易DD → 登录 → 进入"守望先锋统计/战绩"页 → 点几下切换英雄/地图/赛季。

addon 会自动检测 `datamsapi.ds.163.com/v1/a19ld5tool/` 请求，从 URL 提取 `token` 和 `roleId`，写入 `scripts/creds.json`。看到控制台打印 `CREDS CAPTURED` 即可。

抓完后还原环境：
```powershell
.\setup_capture.ps1 -Cleanup
```

### 第2步：最近 N 场报告（推荐）

```powershell
python scripts/ow_recent_report.py --limit 1000 --mode leisure --out report.txt
```

参数：
- `--limit` 最近场次数
- `--mode sport|leisure` 竞技/快速
- `--detail` 额外拉每场详情，用于阵容/队友/敌方英雄分析（慢；默认不加）
- `--start-season 23` 从指定赛季往前补足最近场次

输出 `report.txt` + 去标识化缓存 `recent_<limit>_<mode>_sanitized.json`。缓存不保存玩家昵称、bnetId 或 token，但仍属于个人数据产物。

### 第3步：原始数据导出（可选）

```powershell
python scripts/ow_pull.py --season 23 --mode leisure --out data.json
```

参数：
- `--season` 赛季号（不填取最新）
- `--mode sport|leisure` 竞技/快速
- `--out` 输出文件
- `--detail` 额外拉每场详情（含全队/敌方，慢；仅在明确需要时使用）
- `--seasons 21,22,23` 拉多赛季

读取 `scripts/creds.json` 里的 token/roleId。也可用 `--token` `--roleid` 直接传。

### 第4步：通用分析（可选）

`scripts/ow_pull.py` 输出的 JSON 可直接喂给分析脚本。字段说明见下文。

## 接口清单（datamsapi.ds.163.com/v1/a19ld5tool/）

| 路径 | 用途 | 关键参数 |
|---|---|---|
| `queryCountInfo` | 服务端聚合统计（各英雄胜率/场均/每10min、职责统计、最常玩英雄） | roleId, season, gameMode, token |
| `queryMatchList` | 对战历史列表（地图+英雄+比分+KDA+伤害治疗） | roleId, season, gameMode, page, token |
| `queryMatchInfo` | 单场详情（全队10人、英雄playtime、perks、AI点评） | roleId, matchId, instanceType, season, token |
| `queryCard` | 玩家卡片（昵称/level/游戏时长） | roleId, season, token |
| `billboard/getUserHeroBillboard` | 英雄榜单 | roleId, token |
| `bnFriend/getBillboard` | 好友榜单 | season, roleId, mode, token |

固定参数：`server=1`、`dts=2026`（年份）。`gameMode`: `sport`=竞技 `leisure`=快速。`mode`: `SportPreset`/`LeisurePreset`。

**配置（公开，无需鉴权）**：
- `https://s.166.net/config/ds_ow/ow_hero_config.json` — 英雄 heroGuid→名/职责/图标
- `https://s.166.net/config/ds_ow/ow_map_config.json` — 地图 mapGuid→名/模式/图标
- `POST https://inf.ds.163.com/v1/web/gameData/game/season-time/get-by-app-key` body `{"appKey":"ld5"}` — 赛季列表

## 数据字段

`queryMatchList` 每条：`matchId, beginTs(毫秒), mapGuid, heroGuid, roleType(tank/dps/healer), matchRet(1=胜,-1=负), teamScore, opponentScore, kill, assist, death, heroDamage, cure, resistDamage, gameMode, instanceType`。

`queryMatchInfo` 详情：`mapGuid, gameTimeSec, startTime, teamScore, opponentScore, heroList(本局玩过的英雄+时长+statMap), teammateList[], enemyList[]`（每人含 name, bnetId, heroGuid, kill/assist/death/heroDamage/cure/resistDamage/healingTaken/damageTaken/finalHit/perks/friendBnetIds）。

> ⚠️ `matchRet` 是权威胜负标志。**不要**用 `teamScore>opponentScore` 判胜（push/闪点图比分与胜负不一致，会系统性虚高胜率）。

## 注意

- `token` 会过期。失效（接口返回鉴权错误）就重跑第1步。
- 抓详情时**分页温和拉取**（0.3-0.5s 间隔），别把接口搞炸。matchList 每页约12-20条。
- 本方法仅获取**你自己的**数据（token 绑定你的战网）。获取他人数据需对方的 roleId（bnetId）且 token 有效。
- **`creds.json` 含你的私人 token，已被 `.gitignore` 排除，切勿提交或随 skill 分发出去。** 分发时只发 `SKILL.md` + `scripts/`（不含 creds.json 和任何 data.json）。
