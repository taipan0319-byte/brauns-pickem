#!/usr/bin/env python3
"""Pre-registered tracker (D29, Grok Block 8): does any family member beat the closing line on their
picks AGAINST the market favorite? Scored at the no-vig closing price of the side taken, decided games only,
ties excluded. Trigger for further testing: z >= 2.0 with n >= 25 against-favorite picks for one member.
Until then nothing changes. Output: dashboard/skill_tracker.txt.    python3 skill_tracker.py"""
import csv, math, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine_b as eb
games = {g['game_id']: g for g in csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv'))) if g['season'] == '2026'}
picks = {}
for r in csv.DictReader(open(os.path.join(HERE, 'pool_picks.csv'))):
    if r['season'] == '2026' and r['pick'] not in ('NONE', ''): picks.setdefault(r['member'], {})[r['game_id']] = r['pick']
def tail(qs, w):
    dp = [1.0]
    for q in qs: dp = [(dp[k] if k < len(dp) else 0) * (1 - q) + (dp[k - 1] if k > 0 else 0) * q for k in range(len(dp) + 1)]
    return sum(dp[w:])
out = [f"Against-favorite skill tracker, 2026, generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%MZ}",
       "Each member's picks against the market favorite, scored at the closing no-vig price of the side taken.",
       "Trigger for a copy-test (D29): z >= 2.0 AND n >= 25 for one member. Nothing acts on this file otherwise.", "",
       f"{'member':8} {'n':>3} {'won':>4} {'expected':>9} {'z':>6} {'P(>=won)':>9}   by week (won/n)"]
for m in ['Nolan', 'Kaleigh', 'Molly', 'Casey', 'Sheila', 'Sue', 'Ryan']:
    qs = []; w = 0; byw = {}
    for gid, p in sorted(picks.get(m, {}).items()):
        g = games[gid]; ph = eb.home_prob(g); fav = g['home_team'] if ph >= 0.5 else g['away_team']
        if p == fav or g['result'] in ('', '0'): continue
        q = 1 - max(ph, 1 - ph); won = p == (g['home_team'] if float(g['result']) > 0 else g['away_team'])
        qs.append(q); w += won; b = byw.setdefault(int(g['week']), [0, 0]); b[0] += won; b[1] += 1
    n = len(qs); exp = sum(qs); var = sum(q * (1 - q) for q in qs); z = (w - exp) / math.sqrt(var) if var else 0.0
    out.append(f"{m:8} {n:3} {w:4} {exp:9.1f} {z:+6.2f} {tail(qs, w):9.3f}   " + " ".join(f"w{k}:{v[0]}/{v[1]}" for k, v in sorted(byw.items())))
out += ["", "Reading: seven members, so the best z among them sits near +1.2 by chance alone with nobody having an edge.",
        "A member at z >= 2 over 25+ picks is still only a candidate; the copy-test runs in backtest_engine_b.py before any pick changes."]
open(os.path.join(HERE, 'dashboard', 'skill_tracker.txt'), 'w').write("\n".join(out) + "\n"); print("\n".join(out))
