#!/usr/bin/env python3
"""Regression test for D4 (ChatGPT V4 spec): with every opponent at dog rate 0 and bias 0, equal standings,
Engine B must recommend the underdog in the closest game of the week. Run: python3 test_engine_b_d4.py
Exit 1 on failure. Uses the current season/week from data/games.csv."""
import csv, json, os, sys
import numpy as np, engine_b
HERE = os.path.dirname(os.path.abspath(__file__))
games = engine_b.load_games(os.path.join(HERE, "data", "games.csv"))
season = max(int(g["season"]) for g in games); unplayed = [g for g in games if int(g["season"]) == season and g["game_type"] == "REG" and g["result"] == ""]
week = min(int(g["week"]) for g in unplayed); rem = sorted(unplayed, key=lambda g: (int(g["week"]), g["gameday"]))
mask = np.array([int(g["week"]) == week for g in rem])
fam = [dict(name=m["name"], dog_rate={"tossup": 0.0, "close": 0.0, "other": 0.0}, bias_team=None, bias_strength=0.0) for m in json.load(open(os.path.join(HERE, "family.json")))]
base, final, deltas, user_fav, P_opp, pfav, fav_team, fav_home, noise = engine_b.evaluate(rem, fam, {}, "Ryan", 20000, 7, mask)
idx = np.where(mask)[0]; closest = min(idx, key=lambda i: pfav[i])
print(f"week {week}: fully correlated field, P(first) chalk {base:.3f} -> with recommendations {final:.3f}")
for i in idx: print(f"  {rem[i]['away_team']}@{rem[i]['home_team']:4} fav {pfav[i]*100:5.1f}%  dP(dog) {deltas[i]*100:+6.2f}  {'DOG' if not user_fav[i] else 'fav'}")
ok = (not user_fav[closest]) and deltas[closest] > 0 and final > 1/7
print("PASS: closest game recommends the dog and P(first) exceeds 1/N" if ok else "FAIL: D4 property violated"); sys.exit(0 if ok else 1)
