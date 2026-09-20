#!/usr/bin/env python3
"""Assemble dashboard/data.json from the existing logs and model files, then render dashboard/index.html
from dashboard/template.html by inlining the JSON. PRESENTATION LAYER ONLY: nothing here computes a
probability or a recommendation; every number is read from engine_b_log.csv, predictions_log.csv,
family.json, weekly_scores.csv, dashboard/engine_a_results.json, dashboard/family_fit.json and the
nflverse games file.

    python3 build_dashboard.py --season 2026 --week 1 [--games-file data/games.csv]
"""
import argparse, csv, datetime as dt, json, math, os, io, urllib.request
from collections import defaultdict
import backtest_market

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "dashboard")
MASCOT = {"ARI":"Cardinals","ATL":"Falcons","BAL":"Ravens","BUF":"Bills","CAR":"Panthers","CHI":"Bears","CIN":"Bengals","CLE":"Browns",
          "DAL":"Cowboys","DEN":"Broncos","DET":"Lions","GB":"Packers","HOU":"Texans","IND":"Colts","JAX":"Jaguars","KC":"Chiefs",
          "LA":"Rams","LAC":"Chargers","LV":"Raiders","MIA":"Dolphins","MIN":"Vikings","NE":"Patriots","NO":"Saints","NYG":"Giants",
          "NYJ":"Jets","PHI":"Eagles","PIT":"Steelers","SEA":"Seahawks","SF":"49ers","TB":"Buccaneers","TEN":"Titans","WAS":"Commanders"}
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def read_csv(p): return list(csv.DictReader(open(p, newline=""))) if os.path.exists(p) else []

def load_games(path):
    if path and os.path.exists(path): return read_csv(path), None
    raw = urllib.request.urlopen(URL, timeout=60).read().decode()
    return list(csv.DictReader(io.StringIO(raw))), dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ct_kickoff(g):
    """Return (weekday, 'H:MM AM/PM CT', iso) from gameday + gametime (ET in nflverse)."""
    try:
        t = dt.datetime.strptime(g["gameday"] + " " + g["gametime"], "%Y-%m-%d %H:%M") - dt.timedelta(hours=1)
        return t.strftime("%a").upper(), t.strftime("%-I:%M %p") + " CT", t.strftime("%Y-%m-%dT%H:%M:00-05:00")
    except Exception:
        return g.get("weekday", "")[:3].upper(), "", ""

def injury_adjusted(games_week):
    """D19 diagnostic: market prob adjusted by the frozen residual coefficient (-0.021 per weighted-injury point).
    Never used for a pick. Returns {game_id: p_fav_adjusted} or {} if the season's injury file is absent."""
    try:
        from test_injuries import W, T
        season = games_week[0]["season"]; path = os.path.join(HERE, "data", "inj", f"injuries_{season}.csv")
        if not os.path.exists(path):
            urllib.request.urlretrieve(f"https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv", path)
        wk = games_week[0]["week"]; last = {}
        for r in csv.DictReader(open(path)):
            if r["week"] == wk: last[(T(r["team"]), r["gsis_id"] or r["full_name"])] = (r["position"], r["report_status"])
        inj = defaultdict(float)
        for (t, _), (pos, st) in last.items(): inj[t] += W.get(pos, 0.5) * (1.0 if st == "Out" else 0.7 if st == "Doubtful" else 0.3 if st == "Questionable" else 0)
        out = {}
        for g in games_week:
            if not (g["away_moneyline"] and g["home_moneyline"]): continue
            pa, ph = backtest_market.american_to_prob(g["away_moneyline"]), backtest_market.american_to_prob(g["home_moneyline"]); ph = ph / (pa + ph)
            d = inj[g["home_team"]] - inj[g["away_team"]]; padj = 1 / (1 + math.exp(-(math.log(ph / (1 - ph)) - 0.021 * d)))
            out[g["game_id"]] = padj if ph >= 0.5 else 1 - padj
        return out
    except Exception as e:
        print("injury diagnostic unavailable:", e.__class__.__name__); return {}

def rationale(r, dog):
    fav, p, fam, d, conf = r["fav"], float(r["p_fav"]), float(r["family_fav_rate"]), float(r["dP_first_dog"]), r["confidence"]
    cost = 2 * p - 1
    if r["recommendation"] != fav:
        return (f"STRATEGIC DIFFERENTIATION. Engine B estimates taking {dog} raises P(finish first) by {d*100:+.1f} points: "
                f"only {fam*100:.0f}% of the six opponents are expected on {fav}, and at {p*100:.0f}% the favorite carries "
                f"just {cost:.2f} expected points of cost. Robustness {conf}.")
    if conf == "LOW":
        return (f"{fav} is the market favorite at {p*100:.1f}%. The sign of the pool effect flips between family scenarios "
                f"(or sits inside Monte Carlo noise), so the rule defaults to the favorite.")
    return (f"{fav} is the market favorite at {p*100:.1f}%. Taking {dog} would lower P(finish first) by {abs(d)*100:.1f} points: "
            f"with about {fam*100:.0f}% of the family expected on {fav}, the dog buys little differentiation and costs "
            f"{cost:.2f} expected points.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--games-file", default=os.path.join(HERE, "data", "games.csv"))
    a = ap.parse_args()
    games, fetched = load_games(a.games_file)
    stamp = os.path.join(HERE, "data", "games_fetched_at.txt")
    market_asof = fetched or (open(stamp).read().strip() if os.path.exists(stamp) else None)
    gid = {g["game_id"]: g for g in games}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Engine B log: latest run per game for this week, plus the previous run for change detection
    blog = [r for r in read_csv(os.path.join(HERE, "engine_b_log.csv")) if int(r["season"]) == a.season and int(r["week"]) == a.week]
    runs = sorted({r["logged_at_utc"] for r in blog})
    # A finished game drops out of later Engine B runs (it only simulates unplayed games), so each game keeps
    # the LAST run that included it: for played games that is the standing pre-kickoff recommendation.
    latest = {}
    for r in sorted(blog, key=lambda r: r["logged_at_utc"]): latest[r["game_id"]] = r
    prev = {}
    for gid_, r in latest.items():
        earlier = [x for x in blog if x["game_id"] == gid_ and x["logged_at_utc"] < r["logged_at_utc"]]
        if earlier: prev[gid_] = max(earlier, key=lambda x: x["logged_at_utc"])
    alog = read_csv(os.path.join(HERE, "predictions_log.csv"))
    a_latest = {}
    for r in alog:
        if int(r["season"]) == a.season and int(r["week"]) == a.week: a_latest[r["game_id"]] = r  # file is chronological
    picks = read_csv(os.path.join(HERE, "pool_picks.csv"))
    ryan_pick = {r["game_id"]: r["pick"] for r in picks if r["member"] == "Ryan"}

    # Order like the CBS app: kickoff time first; within a slot, the order recorded from a CBS screenshot
    # (cbs_order.csv) when available, else the NFL schedule id. CBS's within-slot order matches no public id.
    cbs_pos = {r["game_id"]: int(r["position"]) for r in read_csv(os.path.join(HERE, "cbs_order.csv"))
               if int(r["season"]) == a.season and int(r["week"]) == a.week}
    week_games = sorted([g for g in games if int(g["season"]) == a.season and int(g["week"]) == a.week and g["game_type"] in ("REG","WC","DIV","CON","SB")],
                        key=lambda g: (g["gameday"], g["gametime"], cbs_pos.get(g["game_id"], 999), g["old_game_id"]))
    order_source = "CBS app order (recorded from screenshot)" if cbs_pos else "kickoff time, then NFL schedule id (CBS within-slot order not recorded for this week)"
    out_games, changes = [], []
    inj_adj = injury_adjusted(week_games) if week_games else {}
    for g in week_games:
        r = latest.get(g["game_id"]); wd, tm, iso = ct_kickoff(g)
        row = dict(game_id=g["game_id"], away=g["away_team"], home=g["home_team"], away_name=MASCOT.get(g["away_team"], g["away_team"]),
                   home_name=MASCOT.get(g["home_team"], g["home_team"]), weekday=wd, kickoff_ct=tm, kickoff_iso=iso,
                   result=(None if g["result"] == "" else float(g["result"])), away_score=g["away_score"] or None, home_score=g["home_score"] or None,
                   ryan_pick=ryan_pick.get(g["game_id"]))
        if r:
            dog = g["away_team"] if r["fav"] == g["home_team"] else g["home_team"]
            row.update(fav=r["fav"], dog=dog, p_fav=float(r["p_fav"]), pick=r["recommendation"], pick_name=MASCOT.get(r["recommendation"], r["recommendation"]),
                       fav_name=MASCOT.get(r["fav"], r["fav"]), dog_name=MASCOT.get(dog, dog), confidence=r["confidence"],
                       family_fav_rate=float(r["family_fav_rate"]), dP_dog=float(r["dP_first_dog"]), mc_noise=float(r["mc_noise"]),
                       logged_at=r["logged_at_utc"], rationale=rationale(r, dog), engine_a_pick=a_latest.get(g["game_id"], {}).get("pick"),
                       spread=a_latest.get(g["game_id"], {}).get("spread_line"), ml=(a_latest.get(g["game_id"], {}).get("away_ml"), a_latest.get(g["game_id"], {}).get("home_ml")))
            row["p_fav_injury_adj"] = inj_adj.get(g["game_id"])
            row["watch"] = [w for w, c in (("near coin flip", row["p_fav"] < 0.55), ("robustness " + row["confidence"], row["confidence"] != "HIGH"),
                                            ("pool opportunity", row["dP_dog"] > 0)) if c]
            p = prev.get(g["game_id"])
            if p:
                if p["recommendation"] != r["recommendation"]: changes.append(f"{g['away_team']}@{g['home_team']}: pick changed {p['recommendation']} → {r['recommendation']}")
                if abs(float(p["p_fav"]) - float(r["p_fav"])) >= 0.01: changes.append(f"{g['away_team']}@{g['home_team']}: P({r['fav']}) {float(p['p_fav'])*100:.1f}% → {float(r['p_fav'])*100:.1f}%")
                if p["confidence"] != r["confidence"]: changes.append(f"{g['away_team']}@{g['home_team']}: robustness {p['confidence']} → {r['confidence']}")
        else:
            row.update(fav=None, pick=None, confidence=None, rationale="No Engine B output for this game yet. Run the refresh.", watch=["no model output"])
        if row["result"] is not None and row.get("pick"):
            winner = g["home_team"] if row["result"] > 0 else g["away_team"] if row["result"] < 0 else None
            row["winner"] = winner; row["pick_correct"] = (winner == row["pick"]) if winner else None
        out_games.append(row)
    p_first = float(max(latest.values(), key=lambda r: r["logged_at_utc"])["p_first_final"]) if latest else None
    standings = json.load(open(os.path.join(HERE, "standings.json"))) if os.path.exists(os.path.join(HERE, "standings.json")) else None

    # --- scoreboard for the season so far (all completed REG games with a logged recommendation)
    season_b = read_csv(os.path.join(HERE, "engine_b_log.csv")); season_a = read_csv(os.path.join(HERE, "predictions_log.csv"))
    lastB, lastA = {}, {}
    for r in season_b:
        if int(r["season"]) == a.season: lastB[r["game_id"]] = r
    for r in season_a:
        if int(r["season"]) == a.season: lastA[r["game_id"]] = r
    sb = dict(games_scored=0, engine_a_correct=0, engine_b_correct=0, ryan_correct=0, ryan_entered=0)
    for gidk, r in lastB.items():
        g = gid.get(gidk)
        if not g or g["result"] in ("", "0"): continue
        winner = g["home_team"] if float(g["result"]) > 0 else g["away_team"]
        sb["games_scored"] += 1; sb["engine_b_correct"] += (r["recommendation"] == winner)
        ra = lastA.get(gidk); sb["engine_a_correct"] += (ra["pick"] == winner) if ra else (r["fav"] == winner)
        if gidk in ryan_pick: sb["ryan_entered"] += 1; sb["ryan_correct"] += (ryan_pick[gidk] == winner)
    sb["engine_b_value"] = sb["engine_b_correct"] - sb["engine_a_correct"]

    # --- history from weekly_scores.csv (full regular seasons) vs all-favorites
    ws = read_csv(os.path.join(HERE, "weekly_scores.csv")); hist = []
    ff = json.load(open(os.path.join(D, "family_fit.json"))) if os.path.exists(os.path.join(D, "family_fit.json")) else None
    for s in sorted({int(r["season"]) for r in ws}):
        chalk = sum(ff["chalk"][str(s)].values()) if ff and str(s) in ff["chalk"] else None
        tot = defaultdict(int)
        for r in ws:
            if int(r["season"]) == s: tot[r["member"]] += int(r["points"])
        hist.append(dict(season=s, all_favorites=chalk, members=dict(sorted(tot.items(), key=lambda x: -x[1]))))

    # --- season rankings from logged picks + results (CBS standings.json is the authority for totals)
    members = ["Ryan", "Casey", "Sue", "Nolan", "Sheila", "Kaleigh", "Molly"]
    season_games = {g["game_id"]: g for g in games if int(g["season"]) == a.season and g["game_type"] in ("REG","WC","DIV","CON","SB")}
    won = {gid_: (g["home_team"] if float(g["result"]) > 0 else g["away_team"]) for gid_, g in season_games.items() if g["result"] not in ("", "0")}
    weeks_played = sorted({int(season_games[g]["week"]) for g in won})
    wk = {m: defaultdict(int) for m in members}; dogs = {m: [0, 0] for m in members}; missed = {m: 0 for m in members}
    fav_of = {}
    for gid_, g in season_games.items():
        if g["away_moneyline"] and g["home_moneyline"]:
            pa_, ph_ = backtest_market.american_to_prob(g["away_moneyline"]), backtest_market.american_to_prob(g["home_moneyline"]); fav_of[gid_] = g["home_team"] if ph_ >= pa_ else g["away_team"]
        elif g["spread_line"]: fav_of[gid_] = g["home_team"] if float(g["spread_line"]) >= 0 else g["away_team"]
    for r in picks:
        if int(r["season"]) != a.season or r["member"] not in wk or r["game_id"] not in won: continue
        w_ = int(season_games[r["game_id"]]["week"])
        if r["pick"] in ("", "NONE"): missed[r["member"]] += 1; continue
        wk[r["member"]][w_] += (r["pick"] == won[r["game_id"]])
        if fav_of.get(r["game_id"]) and r["pick"] != fav_of[r["game_id"]]:
            dogs[r["member"]][0] += 1; dogs[r["member"]][1] += (r["pick"] == won[r["game_id"]])
    chalk_wk = defaultdict(int); engb_wk = defaultdict(int)
    for gid_, wn in won.items():
        w_ = int(season_games[gid_]["week"])
        if fav_of.get(gid_): chalk_wk[w_] += (fav_of[gid_] == wn)
        if gid_ in lastB: engb_wk[w_] += (lastB[gid_]["recommendation"] == wn)
    rankings = dict(weeks=weeks_played,
                    members=[dict(name=m, weekly={str(w_): wk[m][w_] for w_ in weeks_played}, logged_total=sum(wk[m].values()),
                                  cbs_total=(standings or {}).get(m), dog_picks=dogs[m][0], dog_wins=dogs[m][1], missed=missed[m]) for m in members],
                    all_favorites={str(w_): chalk_wk[w_] for w_ in weeks_played}, engine_b={str(w_): engb_wk[w_] for w_ in weeks_played},
                    games_final=len(won))
    fam = json.load(open(os.path.join(HERE, "family.json")))
    remaining = sum(1 for g in games if int(g["season"]) == a.season and g["game_type"] == "REG" and g["result"] == "")
    calib = backtest_market.compute(games)
    ea = json.load(open(os.path.join(D, "engine_a_results.json"))) if os.path.exists(os.path.join(D, "engine_a_results.json")) else None
    audit = [dict(logged_at=r["logged_at_utc"], season=int(r["season"]), week=int(r["week"]), game_id=r["game_id"], fav=r["fav"], p_fav=float(r["p_fav"]),
                  recommendation=r["recommendation"], dP_dog=float(r["dP_first_dog"]), confidence=r["confidence"], p_first=float(r["p_first_final"]),
                  ryan_pick=ryan_pick.get(r["game_id"]),
                  winner=(gid[r["game_id"]]["home_team"] if float(gid[r["game_id"]]["result"]) > 0 else gid[r["game_id"]]["away_team"]) if r["game_id"] in gid and gid[r["game_id"]]["result"] not in ("", "0") else None)
             for r in season_b]
    data = dict(season=a.season, week=a.week, built_at=now, order_source=order_source, model_refreshed_at=(runs[-1] if runs else None), market_asof=market_asof,
                p_first=p_first, games=out_games, changes_since_previous_refresh=changes, previous_refresh=(runs[-2] if len(runs) > 1 else None),
                standings=standings, games_remaining=remaining, rankings=rankings, family=fam, family_fit=ff, scoreboard=sb, history=hist,
                engine_a=dict(calibration=calib, ablation=ea), audit=audit,
                decisions=dict(production_rule="No-vig market favorite in every game, regular season and playoffs (D6, D16).",
                               tie_rule="Ties split evenly (U1 approximation).", threshold=None))
    if inj_adj:
        lp = os.path.join(HERE, "injury_diagnostic_log.csv"); newf = not os.path.exists(lp)
        with open(lp, "a", newline="") as f:
            w = csv.writer(f)
            if newf: w.writerow(["logged_at_utc", "season", "week", "game_id", "fav", "p_fav_market", "p_fav_injury_adj"])
            for g in out_games:
                if g.get("p_fav_injury_adj") is not None: w.writerow([now, a.season, a.week, g["game_id"], g["fav"], f"{g['p_fav']:.4f}", f"{g['p_fav_injury_adj']:.4f}"])
    json.dump(data, open(os.path.join(D, "data.json"), "w"), indent=1)
    tpl = open(os.path.join(D, "template.html")).read()
    body = tpl.replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    site = "https://taipan0319-byte.github.io/brauns-pickem/"
    picks = ", ".join(g["pick"] for g in out_games if g.get("pick")) or "not yet run"
    desc = f"Week {a.week}, {a.season}: {picks}. Market picks, pool strategy, every prediction logged before kickoff."
    head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0B162A">
<link rel="icon" type="image/png" sizes="512x512" href="{site}icon.png">
<link rel="apple-touch-icon" sizes="512x512" href="{site}icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Brauns Fam Pick'em">
<meta property="og:title" content="Brauns Fam Pick'em · Week {a.week}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{site}">
<meta property="og:image" content="{site}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Brauns Fam Pick'em: a football on a field split between Bears navy and Packers green">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Brauns Fam Pick'em · Week {a.week}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{site}og.png">
</head>
<body>
"""
    open(os.path.join(D, "index.html"), "w").write(head + body + "\n</body>\n</html>\n")
    print(f"dashboard built: {len(out_games)} games, P(first)={p_first}, model {runs[-1] if runs else None}, market {market_asof}")

if __name__ == "__main__":
    main()
