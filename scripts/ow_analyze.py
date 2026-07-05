# -*- coding: utf-8 -*-
"""
守望先锋数据分析 (通用版，读取 ow_pull.py 的输出)
用法: python ow_analyze.py --in data.json
输出: report.txt + hero_stats.csv + map_stats.csv
免责: 仅供学习交流使用，使用者自负风险。data.json 含个人对战数据，勿公开分享。
"""
import argparse, json, collections, math, csv, sys

def HN(g, heroes): return heroes.get(g, {}).get("name", g)
def MN(g, maps): return maps.get(g, {}).get("name", g)
def MM(g, maps): return maps.get(g, {}).get("mode", "")

def pb(v, wf):
    n = len(v)
    if n < 3: return 0
    mx = sum(v)/n; mw = sum(wf)/n
    num = sum((v[i]-mx)*(wf[i]-mw) for i in range(n))
    dx = math.sqrt(sum((x-mx)**2 for x in v)); dy = math.sqrt(sum((y-mw)**2 for y in wf))
    return num/(dx*dy) if dx and dy else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data.json", help="ow_pull.py 输出文件")
    ap.add_argument("--out", default="report.txt", help="报告输出")
    args = ap.parse_args()

    D = json.load(open(args.inp, encoding="utf-8"))
    heroes = D.get("heroes", {}); maps = D.get("maps", {})
    all_matches = []; all_ci = {}; all_details = {}
    for s, d in D.get("data", {}).items():
        for m in d.get("matches", []): m["_season"] = s; all_matches.append(m)
        all_ci[s] = d.get("countInfo", {})
        all_details.update(d.get("details", {}))

    N = len(all_matches)
    if N == 0: print("无对战数据", file=sys.stderr); sys.exit(1)
    W = [m for m in all_matches if m.get("matchRet") == 1]
    L = [m for m in all_matches if m.get("matchRet") == -1]
    WR = len(W)/N*100
    R = []
    def w(*a): R.append(" ".join(str(x) for x in a))

    w(f"=== 守望先锋数据分析 ({N}场, 胜率{WR:.1f}%) ===")
    seasons = sorted(all_ci.keys())
    w(f"赛季: {','.join('S'+s for s in seasons)}")
    for s in seasons:
        ps = all_ci[s].get("presetsSummaryData", {})
        w(f"  S{s}: {ps.get('matchSum','?')}场 胜率{ps.get('winRate','?')}%")

    # 胜负驱动
    wf = [1 if m.get("matchRet") == 1 else 0 for m in all_matches]
    w("\n--- 胜负驱动因子 ---")
    for cn, en in [("击杀","kill"),("助攻","assist"),("死亡","death"),("伤害","heroDamage"),("治疗","cure"),("格挡","resistDamage")]:
        v = [m.get(en, 0) or 0 for m in all_matches]
        wa = sum(m.get(en, 0) or 0 for m in W)/len(W)
        la = sum(m.get(en, 0) or 0 for m in L)/len(L) if L else 0
        r = pb(v, wf)
        w(f"  {cn}: 胜场{wa:.1f} 败场{la:.1f} 相关系数{r:+.3f}")

    # 英雄 (countInfo 聚合)
    htag = collections.defaultdict(lambda: [0, 0])
    for s, ci in all_ci.items():
        for h in ci.get("presetsHeroUseSummaryList", []):
            htag[h["heroGuid"]][0] += h["matchSum"]
            htag[h["heroGuid"]][1] += h.get("winSum", 0)
    w("\n--- 英雄胜率 (>=10场) ---")
    rows = []
    for g, v in htag.items():
        if v[0] >= 10:
            wr = v[1]/v[0]*100
            rows.append((HN(g, heroes), v[0], v[1], wr))
    for n, g, wn, wr in sorted(rows, key=lambda x: -x[3]):
        w(f"  {n:<10} {g:>3}场 胜{wn} 胜率{wr:.1f}%")

    # 职责
    rtag = collections.defaultdict(lambda: [0, 0])
    for s, ci in all_ci.items():
        for r in ci.get("guideCountData", []):
            rtag[r["roleType"]][0] += r["matchSum"]
            rtag[r["roleType"]][1] += round(r["matchSum"] * float(r["winRate"]) / 100)
    w("\n--- 职责 ---")
    for rt, v in sorted(rtag.items(), key=lambda x: -x[1][0]):
        w(f"  {rt:<6} {v[0]:>3}场 胜率{v[1]/v[0]*100:.1f}%")

    # 地图
    ms = collections.defaultdict(lambda: [0, 0])
    for m in all_matches:
        ms[MN(m["mapGuid"], maps)][0] += 1
        if m.get("matchRet") == 1: ms[MN(m["mapGuid"], maps)][1] += 1
    w("\n--- 地图胜率 (>=3场) ---")
    for n, v in sorted(((k, v) for k, v in ms.items() if v[0] >= 3), key=lambda x: -x[1][0]):
        w(f"  {n:<14} {v[0]:>2}场 胜率{v[1]/v[0]*100:.1f}%")

    # 队友 (from details, 用 matchRet 判胜)
    if all_details:
        mate = collections.defaultdict(lambda: [0, 0])
        for m in all_matches:
            d = all_details.get(m["matchId"])
            if not d: continue
            won = m.get("matchRet") == 1
            for t in d.get("teammateList", []):
                if str(t.get("bnetId")) == str(D.get("data", {}).get(list(D["data"])[0], {}).get("roleId", "")): continue
                n = t.get("name", "?"); mate[n][0] += 1
                if won: mate[n][1] += 1
        w(f"\n--- 队友协同 (基于{len(all_details)}场详情, >=5场) ---")
        for n, v in sorted((x for x in mate.items() if x[1][0] >= 5), key=lambda x: -x[1][1]/x[1][0]):
            w(f"  {n:<22} {v[0]:>3}场 胜率{v[1]/v[0]*100:.1f}%")

    open(args.out, "w", encoding="utf-8").write("\n".join(R))
    # CSV
    with open("hero_stats.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f); wr.writerow(["英雄", "场次", "胜", "胜率"])
        for n, g, wn, r in sorted(rows, key=lambda x: -x[1]): wr.writerow([n, g, wn, f"{r:.1f}%"])
    with open("map_stats.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f); wr.writerow(["地图", "场次", "胜", "胜率"])
        for n, v in sorted(ms.items(), key=lambda x: -x[1][0]):
            wr.writerow([n, v[0], v[1], f"{v[1]/v[0]*100:.1f}%"])
    print(f"完成 -> {args.out}, hero_stats.csv, map_stats.csv")

if __name__ == "__main__":
    main()
