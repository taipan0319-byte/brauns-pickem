#!/usr/bin/env python3
"""Underdog-ranking backtest. Can pregame football variables rank market underdogs (no-vig 40-50%)
better than the market does?  Run: python3 backtest_dogs.py   (needs data/games.csv and data/inj/*.csv)

Universe: regular-season games 2009-2025 whose underdog has no-vig probability in [lo, hi).
Features (all pregame): pre-game Elo diff (dog-fav), rest diff, divisional, outdoor cold, wind>=15,
QB change for either side, position-weighted injury diff (dog-fav, final report), last-season win% diff,
dog-is-home, early-season (weeks 1-3), 'public franchise' flags for dog/fav.
Models (logistic, L2), trained on dog games from seasons < t, scored on season t, t = 2014..2025:
  RESIDUAL  logit(dog wins) = a*logit(p_mkt) + b.x      -> score = model prob minus market prob
  PURE      logit(dog wins) = b.x (no market)           -> score = model prob
  Benchmarks: rank by market prob alone; rank by Elo diff alone.
Ranking is done WITHIN each test season (so every season contributes equally to each bucket), then pooled.
Reported per bucket: games, mean market prob, actual dog win rate, excess wins = sum(y - p_mkt), and SE.
"""
import csv, glob, math, os, re
from collections import defaultdict
import numpy as np, engine_a
from test_injuries import W, T
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = {'DAL','GB','KC','PIT','CHI','NE','PHI','SF','DEN','LV','OAK'}
TESTS = list(range(2014, 2026))

def injury_index():
    last = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'data', 'inj', 'injuries_*.csv'))):
        for r in csv.DictReader(open(f)):
            if r['game_type'] == 'REG': last[(int(r['season']), int(r['week']), T(r['team']), r['gsis_id'] or r['full_name'])] = (r['position'], r['report_status'])
    inj = defaultdict(lambda: defaultdict(float))
    for (s, w, t, _), (pos, st) in last.items():
        inj[(s, w)][t] += W.get(pos, 0.5) * (1.0 if st == 'Out' else 0.7 if st == 'Doubtful' else 0.3 if st == 'Questionable' else 0)
    return inj

def build_dogs(lo, hi):
    rows = list(csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv'))))
    data = engine_a.build(rows)                      # pre-game elo, rest, div, cold, windy, qbchg, market
    inj = injury_index()
    wins = defaultdict(lambda: [0, 0])
    for d in data:
        wins[(d['season'], d['home'])][0] += d['y']; wins[(d['season'], d['home'])][1] += 1
        wins[(d['season'], d['away'])][0] += 1 - d['y']; wins[(d['season'], d['away'])][1] += 1
    lp = lambda s, t: (wins[(s-1, t)][0] / wins[(s-1, t)][1]) if wins.get((s-1, t), [0, 0])[1] else 0.5
    out = []
    for d in data:
        if d['season'] < 2009: continue
        p_home = d['p_mkt']; dog_home = p_home < 0.5
        p_dog = p_home if dog_home else 1 - p_home
        if not (lo <= p_dog < hi): continue
        sgn = 1 if dog_home else -1                  # convert home-minus-away features into dog-minus-fav
        dog, fav = (d['home'], d['away']) if dog_home else (d['away'], d['home'])
        ii = inj[(d['season'], d['week'])]
        out.append(dict(season=d['season'], week=d['week'], y=int(d['y'] == (1 if dog_home else 0)), p_mkt=p_dog, mkt=math.log(p_dog/(1-p_dog)),
                        elo=sgn*d['elo'], rest=sgn*d['rest'], div=d['div'], cold=d['cold'], windy=d['windy'], qbchg=d['qbchg'],
                        inj=ii.get(T(dog), 0) - ii.get(T(fav), 0), prev=lp(d['season'], dog) - lp(d['season'], fav),
                        dog_home=int(dog_home), early=int(d['week'] <= 3), dog_public=int(dog in PUBLIC), fav_public=int(fav in PUBLIC)))
    return out

FEATS = ['elo', 'rest', 'div', 'cold', 'windy', 'qbchg', 'inj', 'prev', 'dog_home', 'early', 'dog_public', 'fav_public']

def oos_scores(D, cols, with_market):
    """Return list of (season, score, y, p_mkt) for test seasons; score = model prob (minus market prob if with_market)."""
    res = []; coefs = []
    for t in TESTS:
        tr = [d for d in D if d['season'] < t]; te = [d for d in D if d['season'] == t]
        if not te: continue
        c = (['mkt'] if with_market else []) + cols
        X = np.array([[1] + [d[k] for k in c] for d in tr], float); y = np.array([d['y'] for d in tr], float)
        w = engine_a.fit(X, y, l2=1e-2); coefs.append(w)
        for d in te:
            p = 1/(1+math.exp(-(w[0] + sum(w[i+1]*d[k] for i, k in enumerate(c)))))
            res.append((t, p - d['p_mkt'] if with_market else p, d['y'], d['p_mkt']))
    return res, np.array(coefs), c

def bucket_report(res, nb, label):
    # rank within season, assign bucket 1..nb (nb = highest score), pool
    by = defaultdict(list)
    for t, s, y, p in res: by[t].append((s, y, p))
    buckets = defaultdict(list); top_by_season = []
    for t, lst in by.items():
        lst.sort(key=lambda x: x[0]); n = len(lst)
        for i, (s, y, p) in enumerate(lst):
            b = min(nb, int(i * nb / n) + 1); buckets[b].append((y, p))
        top = [x for i, x in enumerate(lst) if int(i*nb/n)+1 == nb]; top_by_season.append(sum(y-p for _, y, p in top))
    print(f"\n{label}  (buckets ranked within season, {nb} = model likes most; {len(res)} out-of-sample dog games)")
    print(f"  {'bucket':6} {'games':>5} {'mkt prob':>8} {'won':>6} {'excess wins':>11} {'±SE':>5}  {'per-game edge':>13}")
    for b in sorted(buckets):
        L = buckets[b]; n = len(L); mp = np.mean([p for _, p in L]); ar = np.mean([y for y, _ in L]); ex = sum(y-p for y, p in L)
        se = math.sqrt(sum(p*(1-p) for _, p in L))
        print(f"  {b:6} {n:5} {mp*100:7.1f}% {ar*100:5.1f}% {ex:+11.1f} {se:5.1f}  {100*(ar-mp):+12.1f} pts")
    pos = sum(1 for x in top_by_season if x > 0)
    print(f"  top bucket beat market expectation in {pos}/{len(top_by_season)} test seasons; top-bucket excess by season: " + " ".join(f"{x:+.1f}" for x in top_by_season))

def run_band(lo, hi):
    D = build_dogs(lo, hi)
    print("=" * 100); print(f"UNDERDOGS PRICED {int(lo*100)}-{int(hi*100)}%: {len(D)} games 2009-2025, {sum(1 for d in D if d['season'] in TESTS)} in test seasons 2014-2025")
    print(f"  overall: dogs won {np.mean([d['y'] for d in D])*100:.1f}% vs priced {np.mean([d['p_mkt'] for d in D])*100:.1f}%")
    # benchmarks
    bench_mkt = [(d['season'], d['p_mkt'], d['y'], d['p_mkt']) for d in D if d['season'] in TESTS]
    bucket_report(bench_mkt, 5, "BENCHMARK: rank by market probability alone")
    bench_elo = [(d['season'], d['elo'], d['y'], d['p_mkt']) for d in D if d['season'] in TESTS]
    bucket_report(bench_elo, 5, "BENCHMARK: rank by pre-game Elo edge alone")
    res, coefs, c = oos_scores(D, FEATS, True)
    cons = [(np.sign(coefs[:, i+1]) == np.sign(coefs[-1, i+1])).mean() for i in range(len(c))]
    print("\n  RESIDUAL model coefficients (last fit) and sign consistency across test seasons:")
    print("   " + "  ".join(f"{k}={coefs[-1, i+1]:+.3f}({cons[i]:.0%})" for i, k in enumerate(c)))
    bucket_report(res, 5, "RESIDUAL model: market + all pregame variables, ranked by (model prob - market prob)")
    bucket_report(res, 10, "RESIDUAL model, deciles")
    res2, coefs2, c2 = oos_scores(D, FEATS, False)
    bucket_report(res2, 5, "PURE model: pregame variables only (no market), ranked by model prob")
    # top-decile detail: is the top 10% materially above market?
    by = defaultdict(list)
    for t, s, y, p in res: by[t].append((s, y, p))
    top = []
    for t, lst in by.items():
        lst.sort(key=lambda x: -x[0]); k = max(1, len(lst)//10); top += lst[:k]
    ex = sum(y-p for _, y, p in top); se = math.sqrt(sum(p*(1-p) for _, _, p in top))
    print(f"\n  TOP DECILE (residual model): {len(top)} games, won {np.mean([y for _, y, _ in top])*100:.1f}% vs priced {np.mean([p for _, _, p in top])*100:.1f}%, excess {ex:+.1f} wins (±{se:.1f}) = {ex/se:+.2f} SE")

if __name__ == '__main__':
    run_band(0.40, 0.50)
    run_band(0.45, 0.50)
