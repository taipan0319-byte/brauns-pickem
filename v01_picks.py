#!/usr/bin/env python3
"""v0.1 NFL family-pool picker: market prior only, with an append-only audit log.

Usage:
    python3 v01_picks.py --season 2026 --week 1            # print picks, append to log
    python3 v01_picks.py --season 2026 --week 1 --dry-run  # print only

Rules (deliberately minimal):
  * Pick the no-vig moneyline favorite. If the moneylines are a dead heat, pick the home team.
  * Every pick is appended to predictions_log.csv with a UTC timestamp. Existing rows for the
    same game are never modified or deleted; a re-run adds a new row with a new timestamp, so
    the file is a genuine history of what we believed and when.
  * Lines come from nflverse's games.csv (Lee Sharpe). They are a single-book snapshot, not a
    consensus close; good enough for v0.1, and the log records which numbers were used.
"""
import argparse, csv, datetime as dt, io, os, sys, urllib.request

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "predictions_log.csv")
LOG_FIELDS = ["logged_at_utc", "season", "week", "game_id", "gameday", "away", "home",
              "away_ml", "home_ml", "spread_line", "p_away_novig", "p_home_novig",
              "pick", "p_pick", "source", "note"]

def american_to_prob(ml):
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def novig(away_ml, home_ml):
    pa, ph = american_to_prob(away_ml), american_to_prob(home_ml)
    return pa / (pa + ph), ph / (pa + ph)

def load_games(path=None):
    if path:
        return list(csv.DictReader(open(path, newline="")))
    raw = urllib.request.urlopen(GAMES_URL, timeout=60).read().decode()
    return list(csv.DictReader(io.StringIO(raw)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--games-file", help="local games.csv instead of downloading")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    games = [g for g in load_games(a.games_file)
             if int(g["season"]) == a.season and g["week"] == str(a.week)]
    if not games:
        sys.exit("no games found for that season/week")

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    print(f"{'date':10} {'game':10} {'spread':>7} {'ML(a/h)':>11} {'P(home)':>8}  pick   P(pick)")
    for g in games:
        if not (g["away_moneyline"] and g["home_moneyline"]):
            print(f"{g['gameday']:10} {g['away_team']+'@'+g['home_team']:10}  -- no moneyline yet; pick later --")
            continue
        pa, ph = novig(g["away_moneyline"], g["home_moneyline"])
        if abs(ph - pa) < 1e-9:
            pick, pp, note = g["home_team"], ph, "dead heat; home team by rule"
        elif ph > pa:
            pick, pp, note = g["home_team"], ph, ""
        else:
            pick, pp, note = g["away_team"], pa, ""
        print(f"{g['gameday']:10} {g['away_team']+'@'+g['home_team']:10} {g['spread_line']:>7} "
              f"{g['away_moneyline']+'/'+g['home_moneyline']:>11} {ph:8.3f}  {pick:5} {pp:.3f}")
        out.append(dict(logged_at_utc=now, season=a.season, week=a.week, game_id=g["game_id"],
                        gameday=g["gameday"], away=g["away_team"], home=g["home_team"],
                        away_ml=g["away_moneyline"], home_ml=g["home_moneyline"],
                        spread_line=g["spread_line"], p_away_novig=f"{pa:.4f}",
                        p_home_novig=f"{ph:.4f}", pick=pick, p_pick=f"{pp:.4f}",
                        source="nflverse games.csv", note=note))
    if a.dry_run:
        return
    new_file = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:  # append-only by construction
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(out)
    print(f"\nappended {len(out)} rows to {LOG}")

if __name__ == "__main__":
    main()
