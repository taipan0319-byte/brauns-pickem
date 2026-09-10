#!/usr/bin/env python3
"""Injury follow-up: (a) does weighting injured players by importance (snap share, nflverse snap counts 2012+)
beat crude position counts? (b) does the injury gap predict winners in COIN-FLIP games (favorite < 55%)?
Needs data/games.csv, data/inj/injuries_YYYY.csv (2012+), data/snaps/snap_counts_YYYY.csv (2012+):
https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_YYYY.csv
Importance = player's mean snap share in prior weeks of the season (else prior season; else 0.25).
Expanding window, train < t, test t, 2015-2025. Results recorded in CLAUDE_TO_CHATGPT.md Block 9."""
import csv, glob, math, re, os
from collections import defaultdict
import numpy as np, engine_a
from test_injuries import W, T
HERE = os.path.dirname(os.path.abspath(__file__))
def nm(s): return re.sub(r"[.'\-]", "", s.lower()).replace(" jr","").replace(" sr","").replace(" iii","").replace(" ii","").strip()
def main():
    hist = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(HERE,'data','snaps','snap_counts_*.csv'))):
        for r in csv.DictReader(open(f)):
            if r['game_type'] == 'REG': hist[(int(r['season']), T(r['team']), nm(r['player']))].append((int(r['week']), max(float(r['offense_pct'] or 0), float(r['defense_pct'] or 0))))
    def importance(season, week, team, name):
        prior = [s for w, s in hist.get((season, team, name), []) if w < week]
        if len(prior) >= 2: return float(np.mean(prior))
        last = [s for w, s in hist.get((season - 1, team, name), [])]
        return float(np.mean(last)) if last else (float(np.mean(prior)) if prior else 0.25)
    last = {}
    for f in sorted(glob.glob(os.path.join(HERE,'data','inj','injuries_20[12][0-9].csv'))):
        for r in csv.DictReader(open(f)):
            if r['game_type'] == 'REG' and 2012 <= int(r['season']) <= 2025: last[(int(r['season']), int(r['week']), T(r['team']), nm(r['full_name']))] = (r['position'], r['report_status'])
    feat = defaultdict(lambda: defaultdict(float))
    for (s, w, t, name), (pos, st) in last.items():
        sev = 1.0 if st == 'Out' else 0.7 if st == 'Doubtful' else 0.3 if st == 'Questionable' else 0
        if not sev: continue
        imp = importance(s, w, t, name); d = feat[(s, w)]
        d[t+'|pos'] += sev * W.get(pos, 0.5); d[t+'|snap'] += sev * imp; d[t+'|snapxpos'] += sev * imp * W.get(pos, 0.5); d[t+'|qb'] += sev * (pos == 'QB') * (imp >= 0.5)
    D = [d for d in engine_a.build(list(csv.DictReader(open(os.path.join(HERE,'data','games.csv'))))) if d['season'] >= 2012]
    for d in D:
        f = feat[(d['season'], d['week'])]
        for k in ('pos', 'snap', 'snapxpos', 'qb'): d['i_'+k] = f[T(d['home'])+'|'+k] - f[T(d['away'])+'|'+k]
    tests = list(range(2015, 2026))
    def run(cols, label, subset=None):
        ll, coefs, n = [], [], 0
        for t in tests:
            tr = [d for d in D if d['season'] < t and (subset is None or subset(d))]; te = [d for d in D if d['season'] == t and (subset is None or subset(d))]
            X = np.array([[1] + [d[c] for c in cols] for d in tr], float); y = np.array([d['y'] for d in tr], float); w = engine_a.fit(X, y, l2=1e-3); coefs.append(w)
            Xe = np.array([[1] + [d[c] for c in cols] for d in te], float); ye = np.array([d['y'] for d in te], float); pe = np.clip(1/(1+np.exp(-Xe@w)), 1e-6, 1-1e-6)
            ll.append(-np.mean(ye*np.log(pe) + (1-ye)*np.log(1-pe))); n += len(te)
        c = np.array(coefs); cons = [(np.sign(c[:, i+1]) == np.sign(c[-1, i+1])).mean() for i in range(len(cols))]
        print(f"{label:36} n={n:4} logloss {np.mean(ll):.4f}  " + "  ".join(f"{cols[i][2:]}={c[-1,i+1]:+.3f} ({cons[i]:.0%} same sign)" for i in range(len(cols))))
    print("All games: which injury measure carries information (no market)?")
    for k in ('pos', 'snap', 'snapxpos', 'qb'): run(['i_'+k], '  ' + k)
    print("All games: residual over the market"); run(['mkt'], '  market only')
    for k in ('pos', 'snap', 'snapxpos', 'qb'): run(['mkt', 'i_'+k], '  market + ' + k)
    cf = lambda d: max(d['p_mkt'], 1-d['p_mkt']) < 0.55
    print("Coin flips only (favorite < 55%)"); run(['mkt'], '  market only', cf)
    for k in ('pos', 'snapxpos', 'qb'): run(['i_'+k], '  ' + k + ' alone', cf); run(['mkt', 'i_'+k], '  market + ' + k, cf)
    S = [d for d in D if d['season'] >= 2015 and cf(d) and d['i_snapxpos'] != 0]
    for lab, sub, key in (("any injury gap", S, 'i_snapxpos'), ("large gap (>=2)", [d for d in S if abs(d['i_snapxpos']) >= 2], 'i_snapxpos'), ("one side's QB out", [d for d in S if d['i_qb'] != 0], 'i_qb')):
        k = sum(1 for d in sub if (d[key] < 0) == (d['y'] == 1)); print(f"  coin flips, {lab}: less-injured side won {k}/{len(sub)} = {k/len(sub):.1%} (±{100*math.sqrt(.25/len(sub)):.1f})")
if __name__ == '__main__': main()
