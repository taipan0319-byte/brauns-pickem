#!/usr/bin/env python3
"""Engine D (Grok Block 2): a Vegas-FREE football model as a logged second opinion. Research harness only.

Home-win logistic regression on pre-game, prior-weeks-only, exponentially weighted, last-season-shrunk team
efficiency (Engine C's feature pipeline: pass/rush EPA for and against, yards per attempt, sack rates,
turnover margin) plus home field, Elo and rest. NO market input at any stage.

Development: walk-forward t = 2014..2022 (train < t). HOLDOUT: 2023-2025, trained once on <= 2022, scored once.
Judged the way Grok asked: disagreements with the closing favorite (count, record, market-implied rate on
those games), straight-up accuracy, and log loss against Engine A (the market). Plus one residual line:
does adding Engine D's logit to the market logit improve the market out of sample?

    python3 engine_d.py
"""
import csv, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine_a, engine_c
from engine_c import team_stats, pregame, T

DEV = list(range(2014, 2023)); HOLD = [2023, 2024, 2025]
FEATS = ['d_off_pass', 'd_off_rush', 'd_def_pass', 'd_def_rush', 'd_ypa', 'd_def_ypa', 'd_sack', 'd_def_sack', 'd_to', 'elo', 'rest']

def build():
    base = [d for d in engine_a.build(list(csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv'))))) if d['season'] >= 2010]
    rows = team_stats(); cache = {}
    for d in base:
        sh, sa = pregame(rows, d['season'], d['week'], T(d['home']), cache), pregame(rows, d['season'], d['week'], T(d['away']), cache)
        d['d_off_pass'] = sh['pass_epa'] - sa['pass_epa']; d['d_off_rush'] = sh['rush_epa'] - sa['rush_epa']
        d['d_def_pass'] = sa['def_pass_epa'] - sh['def_pass_epa']   # positive = away defense allows more than home defense
        d['d_def_rush'] = sa['def_rush_epa'] - sh['def_rush_epa']
        d['d_ypa'] = sh['ypa'] - sa['ypa']; d['d_def_ypa'] = sa['def_ypa'] - sh['def_ypa']
        d['d_sack'] = sa['sack_rate'] - sh['sack_rate']; d['d_def_sack'] = sh['def_sack_rate'] - sa['def_sack_rate']
        d['d_to'] = sh['to_margin'] - sa['to_margin']
    return base

def fit_score(train, test, cols, l2=3e-2, with_market=False):
    def X_of(rows):
        return np.array([[1] + ([d['mkt']] if with_market else []) + [d[c] for c in cols] for d in rows], float)
    X = X_of(train); y = np.array([d['y'] for d in train], float); k = 2 if with_market else 1
    mu = X[:, k:].mean(0); sd = X[:, k:].std(0) + 1e-9; X[:, k:] = (X[:, k:] - mu) / sd
    w = engine_a.fit(X, y, l2=l2)
    Xt = X_of(test); Xt[:, k:] = (Xt[:, k:] - mu) / sd
    p = 1 / (1 + np.exp(-(Xt @ w)))
    return [dict(d, p_d=float(pi)) for d, pi in zip(test, p)], w

def report(res, label):
    y = np.array([d['y'] for d in res]); pm = np.array([d['p_mkt'] for d in res]); pd_ = np.array([d['p_d'] for d in res])
    ll = lambda p: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    acc_m = float(((pm > 0.5) == y).mean()); acc_d = float(((pd_ > 0.5) == y).mean())
    dis = (pd_ > 0.5) != (pm > 0.5); n = int(dis.sum())
    d_right = int(((pd_[dis] > 0.5) == y[dis]).sum())
    mkt_implied_on_dis = float(np.where(pm[dis] > 0.5, pm[dis], 1 - pm[dis]).mean()) if n else float('nan')   # P(market side wins)
    print(f"\n{label}: {len(res)} games")
    print(f"  straight-up: market {acc_m*100:.1f}%  Engine D {acc_d*100:.1f}%   log loss: market {ll(pm):.4f}  Engine D {ll(pd_):.4f}")
    print(f"  disagreements with the closing favorite: {n} ({n/len(res)*100:.1f}% of games)")
    if n:
        se = math.sqrt(mkt_implied_on_dis * (1 - mkt_implied_on_dis) / n)
        print(f"    Engine D's side won {d_right} of {n} = {d_right/n*100:.1f}%;  market implied Engine D's side at {(1-mkt_implied_on_dis)*100:.1f}%  "
              f"(SE {se*100:.1f} pp, z = {((d_right/n)-(1-mkt_implied_on_dis))/se:+.1f})")
        # by season
        for s in sorted({d['season'] for d in res}):
            m = np.array([d['season'] == s for d in res]) & dis
            if m.sum(): print(f"    {s}: {int(m.sum())} disagreements, Engine D right {int(((pd_[m]>0.5)==y[m]).sum())}")
    return ll(pm), ll(pd_)

def main():
    data = build()
    print("ENGINE D — Vegas-free team-efficiency model (Grok Block 2). Features:", ", ".join(FEATS))
    dev = []
    for t in DEV:
        tr = [d for d in data if d['season'] < t]; te = [d for d in data if d['season'] == t]
        r, _ = fit_score(tr, te, FEATS); dev += r
    report(dev, "DEVELOPMENT walk-forward 2014-2022 (train < t)")
    tr = [d for d in data if d['season'] <= 2022]; te = [d for d in data if d['season'] in HOLD]
    hold, w = fit_score(tr, te, FEATS)
    print("  holdout-model coefficients (standardized): " + "  ".join(f"{c}={w[i+1]:+.2f}" for i, c in enumerate(FEATS)))
    report(hold, "HOLDOUT 2023-2025 (trained once on <=2022)")
    # residual: market + Engine D features, does it beat the market alone?
    resid, w2 = fit_score(tr, te, FEATS, with_market=True)
    y = np.array([d['y'] for d in resid]); pm = np.array([d['p_mkt'] for d in resid]); pr = np.array([d['p_d'] for d in resid])
    ll = lambda p: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    flips = int(((pr > 0.5) != (pm > 0.5)).sum()); fl = (pr > 0.5) != (pm > 0.5)
    print(f"\nRESIDUAL CHECK, holdout: market + Engine D features. log loss market {ll(pm):.4f} -> blended {ll(pr):.4f}; "
          f"pick flips {flips}, flipped side won {int(((pr[fl]>0.5)==y[fl]).sum())} of {flips}")
    print("\nReading rule: Engine D earns a weekly log only if its disagreements beat the market's implied rate on those games by 2 SE in the holdout.")

if __name__ == "__main__":
    main()
