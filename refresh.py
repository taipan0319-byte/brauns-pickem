#!/usr/bin/env python3
"""REFRESH WEEK: one command that reruns the existing v1.0 pipeline on fresh data and rebuilds the dashboard.

    python3 refresh.py [--season 2026] [--week 3|auto] [--standings standings.json] [--sims 20000] [--offline]

Steps (each is the existing script, unchanged):
  1. download nflverse games.csv -> data/games.csv, record the fetch time (market data as-of)
     (--offline keeps the existing file and its timestamp; the dashboard will show that age)
  2. v01_picks.py      Engine A picks, appended to predictions_log.csv
  3. engine_b.py --screen   Engine B screen, appended to engine_b_log.csv
  4. build_dashboard.py     dashboard/data.json + dashboard/index.html
If step 1 fails, the previous file is kept and the failure is printed; nothing is invented.
"""
import argparse, datetime as dt, os, subprocess, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="defaults to the current NFL season"); ap.add_argument("--week", default="auto", help="week number, or auto = first week with unplayed games")
    ap.add_argument("--standings"); ap.add_argument("--sims", type=int, default=20000); ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(); os.makedirs(DATA, exist_ok=True); gf = os.path.join(DATA, "games.csv")
    if not a.offline:
        try:
            raw = urllib.request.urlopen(URL, timeout=60).read()
            open(gf, "wb").write(raw)
            open(os.path.join(DATA, "games_fetched_at.txt"), "w").write(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            print("1/4 games.csv downloaded")
        except Exception as e:
            print(f"1/4 DOWNLOAD FAILED ({e}); keeping previous games.csv" + ("" if os.path.exists(gf) else " -- none exists, aborting"))
            if not os.path.exists(gf): sys.exit(1)
    import csv
    season = a.season or (dt.date.today().year if dt.date.today().month >= 8 else dt.date.today().year - 1)
    if a.week == "auto":
        rows = [r for r in csv.DictReader(open(gf, newline="")) if int(r["season"]) == season and r["result"] == ""]
        if not rows: sys.exit(f"no unplayed games found for season {season}")
        a.week = min(int(r["week"]) for r in rows)
    print(f"season {season} week {a.week}")
    py = sys.executable; common = ["--season", str(season), "--week", str(a.week), "--games-file", gf]
    subprocess.run([py, os.path.join(HERE, "v01_picks.py")] + common, check=True); print("2/4 Engine A logged")
    cmd = [py, os.path.join(HERE, "engine_b.py")] + common + ["--screen", "--sims", str(a.sims)]
    if a.standings: cmd += ["--standings", a.standings]
    subprocess.run(cmd, check=True); print("3/4 Engine B logged")
    subprocess.run([py, os.path.join(HERE, "build_dashboard.py")] + common, check=True); print("4/4 dashboard built -> dashboard/index.html")

if __name__ == "__main__":
    main()
