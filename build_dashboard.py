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
    latest = {r["game_id"]: r for r in blog if r["logged_at_utc"] == runs[-1]} if runs else {}
    prev = {r["game_id"]: r for r in blog if r["logged_at_utc"] == runs[-2]} if len(runs) > 1 else {}
    alog = read_csv(os.path.join(HERE, "predictions_log.csv"))
    a_latest = {}
    for r in alog:
        if int(r["season"]) == a.season and int(r["week"]) == a.week: a_latest[r["game_id"]] = r  # file is chronological
    picks = read_csv(os.path.join(HERE, "pool_picks.csv"))
    ryan_pick = {r["game_id"]: r["pick"] for r in picks if r["member"] == "Ryan"}

    week_games = sorted([g for g in games if int(g["season"]) == a.season and int(g["week"]) == a.week and g["game_type"] in ("REG","WC","DIV","CON","SB")],
                        key=lambda g: (g["gameday"], g["gametime"]))
    out_games, changes = [], []
    for g in week_games:
        r = latest.get(g["game_id"]); wd, tm, iso = ct_kickoff(g)
        row = dict(game_id=g["game_id"], away=g["away_team"], home=g["home_team"], weekday=wd, kickoff_ct=tm, kickoff_iso=iso,
                   result=(None if g["result"] == "" else float(g["result"])), away_score=g["away_score"] or None, home_score=g["home_score"] or None,
                   ryan_pick=ryan_pick.get(g["game_id"]))
        if r:
            dog = g["away_team"] if r["fav"] == g["home_team"] else g["home_team"]
            row.update(fav=r["fav"], dog=dog, p_fav=float(r["p_fav"]), pick=r["recommendation"], confidence=r["confidence"],
                       family_fav_rate=float(r["family_fav_rate"]), dP_dog=float(r["dP_first_dog"]), mc_noise=float(r["mc_noise"]),
                       logged_at=r["logged_at_utc"], rationale=rationale(r, dog), engine_a_pick=a_latest.get(g["game_id"], {}).get("pick"),
                       spread=a_latest.get(g["game_id"], {}).get("spread_line"), ml=(a_latest.get(g["game_id"], {}).get("away_ml"), a_latest.get(g["game_id"], {}).get("home_ml")))
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
    p_first = float(next(iter(latest.values()))["p_first_final"]) if latest else None
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

    fam = json.load(open(os.path.join(HERE, "family.json")))
    remaining = sum(1 for g in games if int(g["season"]) == a.season and g["game_type"] == "REG" and g["result"] == "")
    calib = backtest_market.compute(games)
    ea = json.load(open(os.path.join(D, "engine_a_results.json"))) if os.path.exists(os.path.join(D, "engine_a_results.json")) else None
    audit = [dict(logged_at=r["logged_at_utc"], season=int(r["season"]), week=int(r["week"]), game_id=r["game_id"], fav=r["fav"], p_fav=float(r["p_fav"]),
                  recommendation=r["recommendation"], dP_dog=float(r["dP_first_dog"]), confidence=r["confidence"], p_first=float(r["p_first_final"]),
                  ryan_pick=ryan_pick.get(r["game_id"]),
                  winner=(gid[r["game_id"]]["home_team"] if float(gid[r["game_id"]]["result"]) > 0 else gid[r["game_id"]]["away_team"]) if r["game_id"] in gid and gid[r["game_id"]]["result"] not in ("", "0") else None)
             for r in season_b]
    data = dict(season=a.season, week=a.week, built_at=now, model_refreshed_at=(runs[-1] if runs else None), market_asof=market_asof,
                p_first=p_first, games=out_games, changes_since_previous_refresh=changes, previous_refresh=(runs[-2] if len(runs) > 1 else None),
                standings=standings, games_remaining=remaining, family=fam, family_fit=ff, scoreboard=sb, history=hist,
                engine_a=dict(calibration=calib, ablation=ea), audit=audit,
                decisions=dict(production_rule="No-vig market favorite in every game, regular season and playoffs (D6, D16).",
                               tie_rule="Ties split evenly (U1 approximation).", threshold=None))
    json.dump(data, open(os.path.join(D, "data.json"), "w"), indent=1)
    tpl = open(os.path.join(D, "template.html")).read()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    open(os.path.join(D, "index.html"), "w").write(html)
    print(f"dashboard built: {len(out_games)} games, P(first)={p_first}, model {runs[-1] if runs else None}, market {market_asof}")

if __name__ == "__main__":
    main()
