#!/usr/bin/env python3
"""Market-bias checks behind DECISIONS.md U5 and U6 (run: python3 test_market_biases.py; needs data/games.csv).
1. Early season: do weeks 1-3 favorites win at their priced rate? Is last season's record under/over-weighted?
2. Public money: are 'public' franchises, primetime games, or price bands mispriced?
Calibration gap = actual favorite win rate minus mean priced favorite probability, with a binomial SE."""
import csv, math, os
from collections import defaultdict
import numpy as np, engine_a
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = {'DAL','GB','KC','PIT','CHI','NE','PHI','SF','DEN','LV','OAK'}
def prob(ml): ml = float(ml); return 100/(ml+100) if ml > 0 else -ml/(-ml+100)
def load():
    G = []
    for r in csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv'))):
        if r['game_type'] != 'REG' or r['result'] in ('', '0') or not (r['away_moneyline'] and r['home_moneyline']) or not (2007 <= int(r['season']) <= 2025): continue
        pa, ph = prob(r['away_moneyline']), prob(r['home_moneyline']); ph = ph/(pa+ph)
        G.append(dict(s=int(r['season']), w=int(r['week']), ph=ph, pfav=max(ph, 1-ph), y=int(float(r['result']) > 0), home=r['home_team'], away=r['away_team'],
                      fav=r['home_team'] if ph >= 0.5 else r['away_team'], dog=r['away_team'] if ph >= 0.5 else r['home_team'],
                      fav_win=(float(r['result']) > 0) == (ph >= 0.5), prime=(r['gametime'] >= '19:00') or r['weekday'] in ('Monday', 'Thursday')))
    return G
def line(lab, S):
    n = len(S); pr = np.mean([g['pfav'] for g in S]); ac = np.mean([g['fav_win'] for g in S]); se = math.sqrt(ac*(1-ac)/n)
    print(f"  {lab:44} n={n:4}  priced {pr*100:5.1f}%  won {ac*100:5.1f}%  gap {100*(ac-pr):+5.1f} (±{se*100:.1f})")
def main():
    G = load()
    print("U5. Early-season favorites")
    for lab, lo, hi in (("week 1", 1, 1), ("weeks 1-3", 1, 3), ("weeks 4-9", 4, 9), ("weeks 10-18", 10, 18)): line(lab, [g for g in G if lo <= g['w'] <= hi])
    for lab, lo, hi in (("coin flips, weeks 1-3", 1, 3), ("coin flips, weeks 4-18", 4, 18)): line(lab, [g for g in G if lo <= g['w'] <= hi and g['pfav'] < 0.55])
    wins = defaultdict(lambda: [0, 0])
    for g in G: wins[(g['s'], g['home'])][0] += g['y']; wins[(g['s'], g['home'])][1] += 1; wins[(g['s'], g['away'])][0] += 1-g['y']; wins[(g['s'], g['away'])][1] += 1
    lp = lambda s, t: (wins[(s-1, t)][0]/wins[(s-1, t)][1]) if wins.get((s-1, t), [0, 0])[1] else 0.5
    D = [dict(season=g['s'], y=g['y'], mkt=math.log(g['ph']/(1-g['ph'])), p_mkt=g['ph'], prev=lp(g['s'], g['home'])-lp(g['s'], g['away'])) for g in G if 1 <= g['w'] <= 3 and g['s'] >= 2008]
    for cols, lab in ((['prev'], 'last-season win% diff alone'), (['mkt'], 'market only'), (['mkt', 'prev'], 'market + last-season diff')):
        ll, co = [], []
        for t in range(2014, 2026):
            tr = [d for d in D if d['season'] < t]; te = [d for d in D if d['season'] == t]
            X = np.array([[1]+[d[c] for c in cols] for d in tr], float); y = np.array([d['y'] for d in tr], float); w = engine_a.fit(X, y, l2=1e-3); co.append(w)
            Xe = np.array([[1]+[d[c] for c in cols] for d in te], float); ye = np.array([d['y'] for d in te], float); pe = np.clip(1/(1+np.exp(-Xe@w)), 1e-6, 1-1e-6)
            ll.append(-np.mean(ye*np.log(pe)+(1-ye)*np.log(1-pe)))
        print(f"  weeks 1-3 residual: {lab:30} logloss {np.mean(ll):.4f}  " + "  ".join(f"{cols[i]}={co[-1][i+1]:+.3f}" for i in range(len(cols))))
    print("\nU6. Public money")
    line("favorite is a public franchise", [g for g in G if g['fav'] in PUBLIC]); line("favorite is not", [g for g in G if g['fav'] not in PUBLIC])
    line("public franchise is the underdog", [g for g in G if g['dog'] in PUBLIC])
    line("primetime", [g for g in G if g['prime']]); line("Sunday afternoon", [g for g in G if not g['prime']])
    for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.0)): line(f"favorite priced {int(lo*100)}-{int(hi*100)}%", [g for g in G if lo <= g['pfav'] < hi])
    for a, b in ((2007, 2012), (2013, 2018), (2019, 2025)): line(f"{a}-{b}", [g for g in G if a <= g['s'] <= b])
if __name__ == '__main__': main()
