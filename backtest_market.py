#!/usr/bin/env python3
"""Reproduce the market-calibration numbers in CRITIQUE.md section 2.

    python3 backtest_market.py [--games-file games.csv] [--start 2007] [--end 2025]

Universe: nflverse games.csv, game_type == REG, completed, non-tie, both moneylines present.
Baseline picker: spread favorite (home team on a pick'em). Probability: no-vig moneyline.
"""
import argparse, csv, io, math, urllib.request
from collections import defaultdict

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def american_to_prob(ml):
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def novig(a, h):
    pa, ph = american_to_prob(a), american_to_prob(h)
    return pa / (pa + ph), ph / (pa + ph)

def compute(rows, start=2007, end=2025):
    """Return the calibration statistics as a dict (used by the dashboard builder)."""
    n = fav_ok = 0; brier = ll = 0.0
    cal = defaultdict(lambda: [0, 0, 0.0]); per_season = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["game_type"] != "REG" or r["result"] in ("", "0"): continue
        if not (r["away_moneyline"] and r["home_moneyline"] and r["spread_line"]): continue
        s = int(r["season"])
        if not (start <= s <= end): continue
        home_win = float(r["result"]) > 0
        pick_home = float(r["spread_line"]) >= 0
        pa, ph = novig(r["away_moneyline"], r["home_moneyline"])
        n += 1; fav_ok += (pick_home == home_win)
        per_season[s][0] += 1; per_season[s][1] += (pick_home == home_win)
        pfav = max(pa, ph); fav_won = (ph >= pa) == home_win
        b = min(int(pfav * 100 // 5 * 5), 90); cal[b][0] += 1; cal[b][1] += fav_won; cal[b][2] += pfav
        brier += (ph - home_win) ** 2; ll -= math.log(ph if home_win else pa)
    return dict(games=n, seasons=[start, end], accuracy=fav_ok / n, brier=brier / n, logloss=ll / n,
                se_272=math.sqrt(.67 * .33 / 272),
                calibration=[dict(bucket=f"{b}-{b+5 if b<90 else 100}", n=cal[b][0], mean_pred=cal[b][2]/cal[b][0],
                                  actual=cal[b][1]/cal[b][0]) for b in sorted(cal)],
                per_season=[dict(season=s_, n=v[0], accuracy=v[1]/v[0]) for s_, v in sorted(per_season.items())])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-file"); ap.add_argument("--start", type=int, default=2007)
    ap.add_argument("--end", type=int, default=2025)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.games_file, newline=""))) if a.games_file else \
           list(csv.DictReader(io.StringIO(urllib.request.urlopen(URL).read().decode())))
    n = fav_ok = 0; brier = ll = 0.0
    cal = defaultdict(lambda: [0, 0, 0.0]); per_season = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["game_type"] != "REG" or r["result"] in ("", "0"): continue
        if not (r["away_moneyline"] and r["home_moneyline"] and r["spread_line"]): continue
        s = int(r["season"])
        if not (a.start <= s <= a.end): continue
        home_win = float(r["result"]) > 0
        sp = float(r["spread_line"]); pick_home = sp >= 0
        pa, ph = novig(r["away_moneyline"], r["home_moneyline"])
        n += 1; fav_ok += (pick_home == home_win)
        per_season[s][0] += 1; per_season[s][1] += (pick_home == home_win)
        pfav = max(pa, ph); fav_won = (ph >= pa) == home_win
        b = min(int(pfav * 100 // 5 * 5), 90); cal[b][0] += 1; cal[b][1] += fav_won; cal[b][2] += pfav
        brier += (ph - home_win) ** 2; ll -= math.log(ph if home_win else pa)
    print(f"games {n}  spread-favorite SU accuracy {fav_ok/n:.4f}  Brier {brier/n:.4f}  logloss {ll/n:.4f}")
    print("season-accuracy SE at 67%% over 272 games: %.3f" % math.sqrt(.67 * .33 / 272))
    print("\nbucket    n   mean_pred  actual  cal_error  (90+ bucket is 90-100)")
    for b in sorted(cal):
        n_, w_, sp_ = cal[b]; print(f"{b:>3}-{b+5 if b<90 else 100:<3} {n_:5d}  {sp_/n_:8.3f}  {w_/n_:6.3f}  {w_/n_-sp_/n_:+8.3f}")
    print("\nseason  n   fav_acc")
    for s in sorted(per_season): print(f"{s}  {per_season[s][0]:3d}  {per_season[s][1]/per_season[s][0]:.3f}")

if __name__ == "__main__":
    main()
