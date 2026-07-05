# -*- coding: utf-8 -*-
"""
拉取最近 N 场并生成本地胜率报告。

默认只拉 match list；需要阵容/队友/敌方英雄分析时显式加 --detail。
输出的 cache 只保存英雄/地图/胜负等分析字段，不保存玩家昵称、bnetId 或 token。
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

MIN_DELAY = 0.3
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "creds.json")
BASE = "https://datamsapi.ds.163.com/v1/a19ld5tool"
HERO_CFG = "https://s.166.net/config/ds_ow/ow_hero_config.json"
MAP_CFG = "https://s.166.net/config/ds_ow/ow_map_config.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/108.0.0.0 Safari/537.36 app/df_client dfversion/100126"


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def api_get(path, params):
    return http_json(f"{BASE}/{path}?{urllib.parse.urlencode(params)}")


def load_creds():
    if not os.path.exists(CREDS_FILE):
        raise SystemExit("缺少 scripts/creds.json。请先运行 setup_capture.ps1 获取本人会话参数。")
    return json.load(open(CREDS_FILE, encoding="utf-8"))


def load_configs():
    heroes_raw = http_json(HERO_CFG)
    maps_raw = http_json(MAP_CFG)
    heroes = {}
    for h in heroes_raw:
        for key in (h.get("heroGuid"), h.get("id")):
            if key is not None:
                heroes[str(key)] = h
    maps = {str(m.get("guid")): m for m in maps_raw if m.get("guid") is not None}
    return heroes, maps


def pct(wins, total):
    return wins / total * 100 if total else 0.0


def add(counter, key, won):
    if not key:
        return
    counter[key][0] += 1
    if won:
        counter[key][1] += 1


def date_from_ms(ms):
    return dt.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")


def safe_cache_name(limit, mode):
    return f"recent_{limit}_{mode}_sanitized.json"


class Analyzer:
    def __init__(self, heroes, maps):
        self.heroes = heroes
        self.maps = maps

    def hname(self, guid):
        return self.heroes.get(str(guid), {}).get("name") or str(guid)

    def hrole(self, guid):
        return self.heroes.get(str(guid), {}).get("roleType") or "unknown"

    def mname(self, guid):
        return self.maps.get(str(guid), {}).get("name") or str(guid)

    def mmode(self, guid):
        return self.maps.get(str(guid), {}).get("mode") or ""

    def role_sig(self, hero_guids):
        counts = collections.Counter(self.hrole(g) for g in hero_guids if g)
        order = ["tank", "dps", "healer", "support", "unknown"]
        parts = [f"{k}={counts[k]}" for k in order if counts.get(k)]
        parts.extend(f"{k}={counts[k]}" for k in sorted(counts) if k not in order)
        return ", ".join(parts) if parts else "?"

    def sorted_sig(self, names):
        names = [n for n in names if n]
        return " + ".join(sorted(names)) if names else "?"

    def top_bottom(self, counter, min_n, overall, labeler, top_n):
        rows = []
        for key, (n, w) in counter.items():
            if n >= min_n:
                wr = pct(w, n)
                rows.append((wr - overall, wr, n, w, labeler(key)))
        rows.sort(key=lambda x: (x[0], x[2]), reverse=True)
        return rows[:top_n], list(reversed(rows[-top_n:]))

    def section(self, lines, title, counter, min_n, overall, labeler=lambda x: x, top_n=10):
        top, bottom = self.top_bottom(counter, min_n, overall, labeler, top_n)
        lines.append(f"## {title}：高于整体胜率")
        if not top:
            lines.append("  样本不足")
        for lift, wr, n, w, label in top:
            lines.append(f"  {label}: {n}场 {w}胜 胜率{wr:.1f}% ({lift:+.1f}pp)")
        lines.append("")
        lines.append(f"## {title}：低于整体胜率")
        if not bottom:
            lines.append("  样本不足")
        for lift, wr, n, w, label in bottom:
            lines.append(f"  {label}: {n}场 {w}胜 胜率{wr:.1f}% ({lift:+.1f}pp)")
        lines.append("")


def common_params(creds, token, roleid):
    return {
        "token": token,
        "roleId": roleid,
        "dts": creds.get("dts", "2026"),
        "server": creds.get("server", "1"),
    }


def pull_recent(creds, args):
    token = args.token or creds.get("token")
    roleid = args.roleid or creds.get("roleId")
    if not token or not roleid:
        raise SystemExit("缺少 token/roleId。请先抓取凭据，或传 --token/--roleid。")

    base_params = common_params(creds, token, roleid)
    matches, seen = [], set()
    for season in range(args.start_season, 0, -1):
        page, season_added = 1, 0
        while len(matches) < args.limit:
            params = dict(base_params, season=str(season), gameMode=args.mode, page=page)
            try:
                batch = api_get("queryMatchList", params).get("data") or []
            except Exception as exc:
                log(f"S{season} p{page} 列表失败: {type(exc).__name__}: {exc}")
                break
            if not batch:
                break
            new_count = 0
            for m in batch:
                mid = str(m.get("matchId"))
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                matches.append({
                    "matchId": mid,
                    "season": str(season),
                    "beginTs": m.get("beginTs"),
                    "mapGuid": m.get("mapGuid"),
                    "heroGuid": m.get("heroGuid"),
                    "roleType": m.get("roleType"),
                    "matchRet": m.get("matchRet"),
                    "teamScore": m.get("teamScore"),
                    "opponentScore": m.get("opponentScore"),
                    "kill": m.get("kill"),
                    "assist": m.get("assist"),
                    "death": m.get("death"),
                    "heroDamage": m.get("heroDamage"),
                    "cure": m.get("cure"),
                    "resistDamage": m.get("resistDamage"),
                    "instanceType": m.get("instanceType"),
                })
                season_added += 1
                new_count += 1
                if len(matches) >= args.limit:
                    break
            if page == 1 or page % 10 == 0:
                log(f"S{season} p{page}: +{new_count}, total={len(matches)}")
            if len(batch) < 12 or new_count == 0:
                break
            page += 1
            time.sleep(args.delay)
        if season_added:
            log(f"S{season} 累计加入 {season_added} 场")
        if len(matches) >= args.limit:
            break

    matches.sort(key=lambda m: int(m.get("beginTs") or 0), reverse=True)
    return matches[:args.limit], base_params


def pull_details(matches, base_params, args, cache):
    details = {}
    for i, match in enumerate(matches, 1):
        mid = match["matchId"]
        if mid in cache:
            details[mid] = cache[mid]
        else:
            params = dict(
                base_params,
                matchId=mid,
                instanceType=match.get("instanceType") or "IT_UNRANKED",
                season=match.get("season"),
            )
            try:
                data = api_get("queryMatchInfo", params).get("data") or {}
                details[mid] = {
                    "teamHeroes": [p.get("heroGuid") for p in (data.get("teammateList") or []) if p.get("heroGuid")],
                    "enemyHeroes": [p.get("heroGuid") for p in (data.get("enemyList") or []) if p.get("heroGuid")],
                    "ownPlayedHeroes": [h.get("heroId") or h.get("heroGuid") for h in (data.get("heroList") or []) if h.get("heroId") or h.get("heroGuid")],
                    "gameTimeSec": data.get("gameTimeSec"),
                }
            except Exception as exc:
                details[mid] = {"error": f"{type(exc).__name__}: {exc}"}
            time.sleep(args.delay)
        if i % 25 == 0 or i == len(matches):
            write_cache(args.cache, matches, details)
            ok = sum(1 for d in details.values() if not d.get("error"))
            log(f"详情进度 {i}/{len(matches)}，可用 {ok}")
    return details


def write_cache(path, matches, details):
    json.dump({"matches": matches, "details": details}, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def load_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        return (json.load(open(path, encoding="utf-8")).get("details") or {})
    except Exception:
        return {}


def build_report(matches, details, analyzer):
    total = len(matches)
    wins = sum(1 for m in matches if m.get("matchRet") == 1)
    losses = sum(1 for m in matches if m.get("matchRet") == -1)
    draws = total - wins - losses
    overall = pct(wins, total)
    valid_details = {k: v for k, v in details.items() if v and not v.get("error")}

    map_c = collections.defaultdict(lambda: [0, 0])
    map_mode_c = collections.defaultdict(lambda: [0, 0])
    own_hero_c = collections.defaultdict(lambda: [0, 0])
    own_role_c = collections.defaultdict(lambda: [0, 0])
    hero_map_c = collections.defaultdict(lambda: [0, 0])
    team_role_c = collections.defaultdict(lambda: [0, 0])
    enemy_role_c = collections.defaultdict(lambda: [0, 0])
    team_comp_c = collections.defaultdict(lambda: [0, 0])
    enemy_comp_c = collections.defaultdict(lambda: [0, 0])
    ally_presence_c = collections.defaultdict(lambda: [0, 0])
    enemy_presence_c = collections.defaultdict(lambda: [0, 0])
    own_ally_pair_c = collections.defaultdict(lambda: [0, 0])
    own_enemy_pair_c = collections.defaultdict(lambda: [0, 0])

    for m in matches:
        won = m.get("matchRet") == 1
        hero = str(m.get("heroGuid")) if m.get("heroGuid") is not None else None
        map_guid = str(m.get("mapGuid")) if m.get("mapGuid") is not None else None
        add(map_c, map_guid, won)
        add(map_mode_c, analyzer.mmode(map_guid), won)
        add(own_hero_c, hero, won)
        add(own_role_c, m.get("roleType") or analyzer.hrole(hero), won)
        add(hero_map_c, (hero, map_guid), won)

        detail = valid_details.get(m["matchId"])
        if not detail:
            continue
        team = [str(x) for x in detail.get("teamHeroes") or [] if x]
        enemy = [str(x) for x in detail.get("enemyHeroes") or [] if x]
        add(team_role_c, analyzer.role_sig(team), won)
        add(enemy_role_c, analyzer.role_sig(enemy), won)
        add(team_comp_c, analyzer.sorted_sig(analyzer.hname(x) for x in team), won)
        add(enemy_comp_c, analyzer.sorted_sig(analyzer.hname(x) for x in enemy), won)
        allies = list(team)
        if hero in allies:
            allies.remove(hero)
        for ally in set(allies):
            add(ally_presence_c, ally, won)
            add(own_ally_pair_c, (hero, ally), won)
        for enemy_hero in set(enemy):
            add(enemy_presence_c, enemy_hero, won)
            add(own_enemy_pair_c, (hero, enemy_hero), won)

    lines = [
        f"# 最近 {total} 场{('快速' if total else '')}分析",
        "",
        f"- 时间范围: {date_from_ms(matches[-1]['beginTs'])} 至 {date_from_ms(matches[0]['beginTs'])}",
        f"- 总战绩: {wins}胜 {losses}负 {draws}平/其他，胜率 {overall:.1f}%",
        f"- 详情可用: {len(valid_details)}/{total} 场，用于阵容相关分析",
        "- 胜负判断: 使用 `matchRet`，没有用比分推断",
        "",
    ]

    analyzer.section(lines, "地图（>=10场）", map_c, 10, overall, lambda k: f"{analyzer.mname(k)} [{analyzer.mmode(k)}]")
    analyzer.section(lines, "地图模式（>=20场）", map_mode_c, 20, overall, lambda k: k or "?", 8)
    analyzer.section(lines, "你使用的英雄（>=10场）", own_hero_c, 10, overall, analyzer.hname)
    analyzer.section(lines, "职责（>=20场）", own_role_c, 20, overall, lambda k: k or "?", 8)
    analyzer.section(lines, "英雄 x 地图（>=5场）", hero_map_c, 5, overall, lambda k: f"{analyzer.hname(k[0])} @ {analyzer.mname(k[1])}", 12)

    if valid_details:
        analyzer.section(lines, "本方角色结构（>=10场）", team_role_c, 10, overall, lambda k: k, 8)
        analyzer.section(lines, "敌方角色结构（>=10场）", enemy_role_c, 10, overall, lambda k: k, 8)
        analyzer.section(lines, "队友英雄出现时（不含你自己，>=10场）", ally_presence_c, 10, overall, analyzer.hname)
        analyzer.section(lines, "敌方英雄出现时（>=10场）", enemy_presence_c, 10, overall, analyzer.hname)
        analyzer.section(lines, "你的英雄 + 队友英雄（>=8场）", own_ally_pair_c, 8, overall, lambda k: f"{analyzer.hname(k[0])} + {analyzer.hname(k[1])}", 12)
        analyzer.section(lines, "你的英雄 vs 敌方英雄（>=8场）", own_enemy_pair_c, 8, overall, lambda k: f"{analyzer.hname(k[0])} vs {analyzer.hname(k[1])}", 12)
        analyzer.section(lines, "精确本方五英雄阵容（>=3场）", team_comp_c, 3, overall, lambda k: k, 10)
        analyzer.section(lines, "精确敌方五英雄阵容（>=3场）", enemy_comp_c, 3, overall, lambda k: k, 10)

    lines.append("## 样本量最大的项目")
    for title, counter, labeler in [
        ("地图", map_c, lambda k: f"{analyzer.mname(k)} [{analyzer.mmode(k)}]"),
        ("你的英雄", own_hero_c, analyzer.hname),
        ("队友英雄出现", ally_presence_c, analyzer.hname),
        ("敌方英雄出现", enemy_presence_c, analyzer.hname),
    ]:
        rows = sorted(((n, w, labeler(k)) for k, (n, w) in counter.items()), reverse=True)[:10]
        if not rows:
            continue
        lines.append(f"### {title}")
        for n, w, label in rows:
            lines.append(f"  {label}: {n}场 {w}胜 胜率{pct(w, n):.1f}%")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="拉取最近 N 场并生成本地胜率报告")
    ap.add_argument("--limit", type=int, default=1000, help="最近场次数")
    ap.add_argument("--mode", default="leisure", choices=["sport", "leisure"], help="sport=竞技 leisure=快速")
    ap.add_argument("--start-season", type=int, default=23, help="从该赛季往前补足最近场次")
    ap.add_argument("--detail", action="store_true", help="拉单场详情以分析阵容/队友/敌方英雄")
    ap.add_argument("--delay", type=float, default=0.4, help=f"请求间隔秒，硬性下限{MIN_DELAY}s")
    ap.add_argument("--out", default="report.txt", help="报告输出文件")
    ap.add_argument("--cache", default=None, help="去标识化缓存 JSON，默认 recent_<limit>_<mode>_sanitized.json")
    ap.add_argument("--token", help="datamsapi token (不填则读 scripts/creds.json)")
    ap.add_argument("--roleid", help="roleId/bnetId (不填则读 scripts/creds.json)")
    args = ap.parse_args()

    if args.delay < MIN_DELAY:
        log(f"[warn] delay={args.delay}s 低于下限{MIN_DELAY}s，已提升到 {MIN_DELAY}s")
        args.delay = MIN_DELAY
    if args.limit <= 0:
        raise SystemExit("--limit 必须大于 0")
    if not args.cache:
        args.cache = safe_cache_name(args.limit, args.mode)

    creds = load_creds()
    heroes, maps = load_configs()
    analyzer = Analyzer(heroes, maps)
    matches, base_params = pull_recent(creds, args)
    if not matches:
        raise SystemExit("没有拉到比赛列表")
    log(f"列表完成: {len(matches)} 场, {date_from_ms(matches[-1]['beginTs'])} 到 {date_from_ms(matches[0]['beginTs'])}")

    details = {}
    if args.detail:
        details = pull_details(matches, base_params, args, load_cache(args.cache))
    write_cache(args.cache, matches, details)

    report = build_report(matches, details, analyzer)
    open(args.out, "w", encoding="utf-8").write(report)
    print(f"完成 -> {args.out}")
    print(f"缓存 -> {args.cache}")
    print("[安全提示] cache/report 仍属于个人数据产物，默认不要公开分享。")


if __name__ == "__main__":
    main()
