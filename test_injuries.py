#!/usr/bin/env python3
"""Residual test: do official injury reports add information beyond the market?  (run: python3 test_injuries.py)
Needs data/games.csv and data/inj/injuries_YYYY.csv from
https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_YYYY.csv (2009+).
Feature: position-weighted sum of Out (1.0) / Doubtful (0.7) / Questionable (0.3) from the final report, home minus away.
Same expanding-window protocol as engine_a.py (train < t, test t, 2014-2025)."""
import csv, glob, os
from collections import defaultdict
import numpy as np, engine_a
HERE = os.path.dirname(os.path.abspath(__file__))
norm = {'STL':'LA','SD':'LAC','OAK':'LV','JAC':'JAX','WSH':'WAS','LAR':'LA'}; T = lambda t: norm.get(t, t)
W = {'QB':4.0,'OL':1.0,'T':1.0,'G':1.0,'C':1.0,'WR':0.8,'RB':0.6,'TE':0.6,'DE':0.8,'DT':0.7,'DL':0.7,'EDGE':0.8,'OLB':0.7,'ILB':0.6,'LB':0.6,'CB':0.8,'S':0.6,'FS':0.6,'SS':0.6,'DB':0.6,'K':0.5,'P':0.2,'LS':0.1,'FB':0.2}

def injury_index():
    last = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'data', 'inj', 'injuries_*.csv'))):
        for r in csv.DictReader(open(f)):
            if r['game_type'] == 'REG': last[(int(r['season']), int(r['week']), T(r['team']), r['gsis_id'] or r['full_name'])] = (r['position'], r['report_status'])
    inj = defaultdict(lambda: defaultdict(float))
    for (s, w, t, _), (pos, st) in last.items():
        inj[(s, w)][t] += W.get(pos, 0.5) * (1.0 if st == 'Out' else 0.7 if st == 'Doubtful' else 0.3 if st == 'Questionable' else 0)
    return inj

def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv')))); data = engine_a.build(rows); inj = injury_index()
    D = [d for d in data if d['season'] >= 2009]
    for d in D: d['inj_w'] = inj[(d['season'], d['week'])].get(T(d['home']), 0) - inj[(d['season'], d['week'])].get(T(d['away']), 0)
    tests = list(range(2014, 2026))
    def run(cols, label):
        ll, acc, coefs, flips, ok, mk = [], [], [], 0, 0, 0
        for t in tests:
            tr = [d for d in D if d['season'] < t]; te = [d for d in D if d['season'] == t]
            X = np.array([[1] + [d[c] for c in cols] for d in tr], float); y = np.array([d['y'] for d in tr], float); w = engine_a.fit(X, y); coefs.append(w)
            for d in te:
                p = 1 / (1 + np.exp(-(w[0] + sum(w[i + 1] * d[c] for i, c in enumerate(cols)))))
                if 'mkt' in cols and (p >= 0.5) != (d['p_mkt'] >= 0.5): flips += 1; ok += ((p >= 0.5) == d['y']); mk += ((d['p_mkt'] >= 0.5) == d['y'])
            Xe = np.array([[1] + [d[c] for c in cols] for d in te], float); ye = np.array([d['y'] for d in te], float)
            pe = np.clip(1 / (1 + np.exp(-Xe @ w)), 1e-6, 1 - 1e-6); ll.append(-np.mean(ye * np.log(pe) + (1 - ye) * np.log(1 - pe))); acc.append(np.mean((pe >= 0.5) == ye))
        c = np.array(coefs); cons = [(np.sign(c[:, i + 1]) == np.sign(c[-1, i + 1])).mean() for i in range(len(cols))]
        print(f"{label:34} logloss {np.mean(ll):.4f}  acc {np.mean(acc):.4f}  " + "  ".join(f"{cols[i]}={c[-1, i+1]:+.3f} ({cons[i]:.0%} same sign)" for i in range(len(cols))) + (f"  | flips vs market {flips} ({flips/len(tests):.1f}/season), model right {ok}, market right {mk}" if flips else ""))
        return ll
    print(f"games 2009-2025 with lines: {len(D)}; SD of injury differential {np.std([d['inj_w'] for d in D]):.2f}\n")
    run(['inj_w'], 'injuries alone (no market)')
    l0 = run(['mkt'], 'M0 market only')
    l1 = run(['mkt', 'inj_w'], 'market + injury differential')
    print(f"seasons where market+injury beat market alone: {sum(a < b for a, b in zip(l1, l0))}/{len(tests)}")

if __name__ == '__main__':
    main()
