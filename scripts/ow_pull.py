# -*- coding: utf-8 -*-
"""
守望先锋对战数据拉取 (网易大神 datamsapi)

================================================================================
⚠️  免责声明 / Disclaimer
--------------------------------------------------------------------------------
本项目仅供学习交流与技术研究所用，不得用于任何商业用途。
使用者需遵守网易DD及暴雪的相关服务条款，自负使用风险。
本工具仅获取绑定本人战网的账号数据，不绕过任何鉴权、不爬取他人隐私数据。

🔒 并发与速率控制（重要！）
--------------------------------------------------------------------------------
- 本脚本为**单线程顺序请求**，不开并发，请勿自行改造成多线程。
- 默认请求间隔 0.4 秒，硬性下限 0.3 秒（低于此值会被强制提升）。
- 请勿短时间内大量拉取，以免给 datamsapi.ds.163.com 服务造成压力。
- 拉取每场详情（--detail）请求数=场次数，上千场时分批进行、间隔拉长。
- 抓 token 用的 mitmproxy 抓完务必还原（setup_capture.ps1 -Cleanup）。
================================================================================

用法:
  python ow_pull.py                          # 默认最新赛季+快速模式
  python ow_pull.py --season 23 --mode leisure
  python ow_pull.py --seasons 21,22,23 --detail --out data.json
  python ow_pull.py --token XXX --roleid YYY # 不用creds.json直接传
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse

# 硬性最小请求间隔（秒），低于此值强制提升，保护对方服务
MIN_DELAY = 0.3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "creds.json")
BASE = "https://datamsapi.ds.163.com/v1/a19ld5tool"
HERO_CFG = "https://s.166.net/config/ds_ow/ow_hero_config.json"
MAP_CFG = "https://s.166.net/config/ds_ow/ow_map_config.json"
SEASON_URL = "https://inf.ds.163.com/v1/web/gameData/game/season-time/get-by-app-key"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/108.0.0.0 Safari/537.36 app/df_client dfversion/100126"

def load_creds():
    if os.path.exists(CREDS_FILE):
        return json.load(open(CREDS_FILE, encoding="utf-8"))
    return {}

def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

def http_post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

def q(d): return urllib.parse.urlencode(d)

def get_seasons():
    try: return http_post_json(SEASON_URL, {"appKey": "ld5"}).get("result", [])
    except Exception as e: print(f"[warn] 赛季查询失败: {e}", file=sys.stderr); return []

def load_configs():
    heroes = {h["heroGuid"]: h for h in http_get(HERO_CFG)}
    maps = {m["guid"]: m for m in http_get(MAP_CFG)}
    return heroes, maps

def match_list(rid, season, mode, page, token, server, dts):
    return http_get(f"{BASE}/queryMatchList?{q({'roleId':rid,'season':season,'gameMode':mode,'page':page,'token':token,'dts':dts,'server':server})}")["data"]

def match_info(rid, mid, itype, season, token, server, dts):
    return http_get(f"{BASE}/queryMatchInfo?{q({'roleId':rid,'matchId':mid,'instanceType':itype or 'IT_UNRANKED','season':season,'token':token,'dts':dts,'server':server})}")["data"]

def count_info(rid, season, mode, token, server, dts):
    return http_get(f"{BASE}/queryCountInfo?{q({'roleId':rid,'season':season,'gameMode':mode,'token':token,'dts':dts,'server':server})}")["data"]

def pull_one(rid, season, mode, token, server, dts, detail=False, delay=0.4):
    ci = count_info(rid, season, mode, token, server, dts)
    matches, seen, page = [], set(), 1
    while True:
        b = match_list(rid, season, mode, page, token, server, dts)
        if not b: break
        new = [m for m in b if m["matchId"] not in seen]
        if not new: break
        for m in new:
            seen.add(m["matchId"]); m["_season"] = season; matches.append(m)
        print(f"  S{season} {mode} p{page}: +{len(new)} (累计{len(matches)})", file=sys.stderr)
        if len(b) < 12: break
        page += 1; time.sleep(delay)
    details = {}
    if detail:
        print(f"  拉取详情 {len(matches)} 场（间隔{delay}s，单线程顺序），请耐心等待...", file=sys.stderr)
        for i, m in enumerate(matches):
            try: details[m["matchId"]] = match_info(rid, m["matchId"], m.get("instanceType"), season, token, server, dts)
            except Exception as e: print(f"  detail err {m['matchId']}: {e}", file=sys.stderr)
            if (i+1) % 50 == 0: print(f"  详情进度 {i+1}/{len(matches)}", file=sys.stderr)
            time.sleep(delay)
    return {"season": season, "mode": mode, "countInfo": ci, "matches": matches, "details": details}

def main():
    ap = argparse.ArgumentParser(description="守望先锋对战数据拉取（单线程，温和速率）")
    ap.add_argument("--token", help="datamsapi token (不填则读 creds.json)")
    ap.add_argument("--roleid", help="roleId/bnetId (不填则读 creds.json)")
    ap.add_argument("--server", default=None)
    ap.add_argument("--dts", default=None)
    ap.add_argument("--season", default=None, help="单赛季号")
    ap.add_argument("--seasons", default=None, help="多赛季，逗号分隔，如 21,22,23")
    ap.add_argument("--mode", default="leisure", choices=["sport", "leisure"], help="sport=竞技 leisure=快速")
    ap.add_argument("--detail", action="store_true", help="拉每场详情(慢，请求数=场次数)")
    ap.add_argument("--out", default="data.json", help="输出文件")
    ap.add_argument("--delay", type=float, default=0.4, help=f"请求间隔秒，硬性下限{MIN_DELAY}s")
    args = ap.parse_args()

    # 强制最小间隔，保护对方服务
    if args.delay < MIN_DELAY:
        print(f"[warn] delay={args.delay}s 低于下限{MIN_DELAY}s，已自动提升到 {MIN_DELAY}s 以保护服务", file=sys.stderr)
        args.delay = MIN_DELAY

    c = load_creds()
    token = args.token or c.get("token")
    rid = args.roleid or c.get("roleId")
    server = args.server or c.get("server", "1")
    dts = args.dts or c.get("dts", "2026")
    if not token or not rid:
        print("错误: 缺少 token/roleId。请先运行 setup_capture.ps1 抓取，或用 --token/--roleid 传入。", file=sys.stderr)
        sys.exit(1)
    print(f"roleId={rid} mode={args.mode} delay={args.delay}s (单线程顺序)", file=sys.stderr)

    seasons = []
    if args.seasons: seasons = [s.strip() for s in args.seasons.split(",")]
    elif args.season: seasons = [args.season]
    else:
        ss = get_seasons(); seasons = [ss[0]["seasonId"]] if ss else ["23"]
    print(f"赛季: {seasons}", file=sys.stderr)

    heroes, maps = load_configs()
    result = {"heroes": heroes, "maps": maps, "data": {}}
    for s in seasons:
        print(f"=== 拉取 S{s} ===", file=sys.stderr)
        result["data"][s] = pull_one(rid, s, args.mode, token, server, dts, args.detail, args.delay)

    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    total = sum(len(d["matches"]) for d in result["data"].values())
    print(f"完成: {total} 场 -> {args.out}", file=sys.stderr)
    print(f"[安全提示] {args.out} 含个人对战数据，勿公开分享；creds.json 勿提交git。", file=sys.stderr)

if __name__ == "__main__":
    main()
