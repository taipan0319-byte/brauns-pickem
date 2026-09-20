#!/usr/bin/env python3
"""ENGINE C — Upset Hunter (research harness, never production). ChatGPT Block 6 specification.

Universe: market underdogs, no-vig P(dog) in [LO, HI). Target: dog won. Model: logistic residual on the
market logit plus pregame features, trained ONLY on underdog games from seasons before the test season.
    Upset Edge = P_C(dog wins) - P_market(dog wins)
Development: walk-forward t = 2014..2022 (train < t). HOLDOUT: 2023-2025, trained once on <= 2022, scored once.
Features (all pregame; team efficiency from nflverse stats_team_week, prior weeks only, exponentially
weighted with 4-game half-life, shrunk toward last season's mean with 3 game-equivalents of weight):
  off_pass_epa, off_rush_epa, def_pass_epa_allowed, def_rush_epa_allowed  (dog minus fav where signed)
  protection mismatch = fav def sack rate - dog sack rate suffered ; and the mirror for the dog's rush
  explosive proxy = passing yards per attempt (dog off vs fav def allowed)
  turnover luck = recent turnover margin per game (regression candidate), dog and fav
  plus from backtest_dogs: Elo diff, rest diff, division, cold, wind, QB change, injury diff (D19 weights),
  last-season win% diff, dog at home, early season, public-franchise flags.
Not available in public data, so NOT tested: opening lines / line movement, 4th-down and red-zone rates.
Report: edge quintiles (dev and holdout separately); and the question that matters for a pick'em:
  TOP-K PER WEEK: take the k highest-edge dogs each week whose edge >= threshold; net picks vs
  always-favorite = dog wins - dog losses (each dog pick that loses costs the favorite's point).
Run: python3 engine_c.py  (needs data/games.csv, data/inj/*.csv, data/team/stats_team_week_*.csv)
"""
import csv, glob, math, os
from collections import defaultdict
import numpy as np, engine_a, backtest_dogs
from test_injuries import T
HERE = os.path.dirname(os.path.abspath(__file__))
DEV = list(range(2014, 2023)); HOLD = [2023, 2024, 2025]

def team_stats():
    """(season, week, team) -> dict of per-game raw stats, plus opponent for defensive attribution."""
    rows = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'data', 'team', 'stats_team_week_*.csv'))):
        for r in csv.DictReader(open(f)):
            if r['season_type'] != 'REG': continue
            g = lambda k: float(r[k] or 0)
            att, car = g('attempts'), g('carries'); sk = g('sacks_suffered')
            rows[(int(r['season']), int(r['week']), T(r['team']))] = dict(
                opp=T(r['opponent_team']), pass_epa=g('passing_epa'), rush_epa=g('rushing_epa'), att=att, car=car, sk=sk,
                ypa=g('passing_yards') / att if att else 6.5, sack_rate=sk / (att + sk) if att + sk else 0.07,
                def_sacks=g('def_sacks'), giveaways=g('passing_interceptions') + g('sack_fumbles_lost') + g('rushing_fumbles_lost') + g('receiving_fumbles_lost'),
                takeaways=g('def_interceptions') + g('fumble_recovery_opp'))
    # defensive side: what each team ALLOWED = opponent's offensive line
    for (s, w, t), d in rows.items():
        o = rows.get((s, w, d['opp']))
        d['def_pass_epa'] = o['pass_epa'] if o else 0; d['def_rush_epa'] = o['rush_epa'] if o else 0
        d['def_ypa'] = o['ypa'] if o else 6.5; d['opp_dropbacks'] = (o['att'] + o['sk']) if o else 35
    return rows

KEYS = ['pass_epa', 'rush_epa', 'def_pass_epa', 'def_rush_epa', 'ypa', 'def_ypa', 'sack_rate', 'def_sack_rate', 'to_margin']

def pregame(rows, season, week, team, cache):
    """Shrunk, exponentially weighted pre-game averages for team before (season, week)."""
    k = (season, week, team)
    if k in cache: return cache[k]
    def per_game(d): return dict(pass_epa=d['pass_epa'], rush_epa=d['rush_epa'], def_pass_epa=d['def_pass_epa'], def_rush_epa=d['def_rush_epa'],
                                 ypa=d['ypa'], def_ypa=d['def_ypa'], sack_rate=d['sack_rate'], def_sack_rate=d['def_sacks'] / d['opp_dropbacks'] if d['opp_dropbacks'] else 0.07,
                                 to_margin=d['takeaways'] - d['giveaways'])
    cur = [(w, per_game(rows[(season, w, team)])) for w in range(1, week) if (season, w, team) in rows]
    prev = [per_game(rows[(season - 1, w, team)]) for w in range(1, 19) if (season - 1, w, team) in rows]
    league = dict(pass_epa=0, rush_epa=0, def_pass_epa=0, def_rush_epa=0, ypa=6.8, def_ypa=6.8, sack_rate=0.065, def_sack_rate=0.065, to_margin=0)
    prior = {kk: (np.mean([p[kk] for p in prev]) if prev else league[kk]) for kk in KEYS}
    out = {}
    for kk in KEYS:
        num = 3.0 * prior[kk]; den = 3.0
        for w, p in cur:
            wt = 0.5 ** ((week - w) / 4.0); num += wt * p[kk]; den += wt
        out[kk] = num / den
    cache[k] = out; return out

def build(lo, hi):
    D = backtest_dogs.build_dogs(lo, hi); rows = team_stats(); cache = {}
    games = {(int(r['season']), int(r['week']), r['home_team'], r['away_team']) for r in csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv')))}
    # backtest_dogs rows lack team codes; rebuild them from engine_a.build in the same order
    base = [d for d in engine_a.build(list(csv.DictReader(open(os.path.join(HERE, 'data', 'games.csv'))))) if d['season'] >= 2009]
    idx = {}
    for d in base:
        p = d['p_mkt']; dh = p < 0.5; pd_ = p if dh else 1 - p
        if lo <= pd_ < hi: idx[(d['season'], d['week'], d['home'], d['away'])] = d
    # align: build_dogs filtered the same games in the same order
    keys = list(idx.keys()); assert len(keys) == len(D), (len(keys), len(D))
    for d, k in zip(D, keys):
        s, w, home, away = k; dh = idx[k]['p_mkt'] < 0.5
        dog, fav = (home, away) if dh else (away, home)
        sd, sf = pregame(rows, s, w, T(dog), cache), pregame(rows, s, w, T(fav), cache)
        d['x_off_pass'] = sd['pass_epa'] - sf['pass_epa']; d['x_off_rush'] = sd['rush_epa'] - sf['rush_epa']
        d['x_def_pass'] = sf['def_pass_epa'] - sd['def_pass_epa']   # positive = fav's defense allows more
        d['x_def_rush'] = sf['def_rush_epa'] - sd['def_rush_epa']
        d['x_protect'] = sf['def_sack_rate'] - sd['sack_rate']       # fav rush vs dog protection: negative = dog protects well vs a weak rush
        d['x_rush_vs_fav'] = sd['def_sack_rate'] - sf['sack_rate']   # dog rush vs fav protection
        d['x_explosive'] = sd['ypa'] - sf['def_ypa']; d['x_explosive_fav'] = sf['ypa'] - sd['def_ypa']
        d['x_to_dog'] = sd['to_margin']; d['x_to_fav'] = sf['to_margin']   # high recent margin -> regression candidate
    return D

FEATS = ['elo', 'rest', 'div', 'cold', 'windy', 'qbchg', 'inj', 'prev', 'dog_home', 'early', 'dog_public', 'fav_public',
         'x_off_pass', 'x_off_rush', 'x_def_pass', 'x_def_rush', 'x_protect', 'x_rush_vs_fav', 'x_explosive', 'x_explosive_fav', 'x_to_dog', 'x_to_fav']

def fit_score(train, test, cols, l2=3e-2):
    X = np.array([[1, d['mkt']] + [d[c] for c in cols] for d in train], float); y = np.array([d['y'] for d in train], float)
    mu = X[:, 2:].mean(0); sd = X[:, 2:].std(0) + 1e-9; X[:, 2:] = (X[:, 2:] - mu) / sd
    w = engine_a.fit(X, y, l2=l2)
    out = []
    for d in test:
        x = np.array([1, d['mkt']] + [d[c] for c in cols], float); x[2:] = (x[2:] - mu) / sd
        p = 1 / (1 + math.exp(-float(x @ w))); out.append(dict(season=d['season'], week=d['week'], y=d['y'], p_mkt=d['p_mkt'], p_c=p, edge=p - d['p_mkt']))
    return out, w

def quintiles(res, label):
    by = defaultdict(list)
    for r in res: by[r['season']].append(r)
    B = defaultdict(list)
    for s, lst in by.items():
        lst.sort(key=lambda r: r['edge']); n = len(lst)
        for i, r in enumerate(lst): B[min(5, int(i * 5 / n) + 1)].append(r)
    print(f"\n  {label}: edge quintiles (5 = largest edge), {len(res)} dog games")
    print(f"  {'Q':>2} {'n':>4} {'mkt':>6} {'edge':>6} {'won':>6} {'excess':>7} {'±SE':>5}")
    for b in sorted(B):
        L = B[b]; ex = sum(r['y'] - r['p_mkt'] for r in L); se = math.sqrt(sum(r['p_mkt'] * (1 - r['p_mkt']) for r in L))
        print(f"  {b:>2} {len(L):4} {np.mean([r['p_mkt'] for r in L])*100:5.1f}% {np.mean([r['edge'] for r in L])*100:+5.1f} {np.mean([r['y'] for r in L])*100:5.1f}% {ex:+7.1f} {se:5.1f}")

def topk(res, k, thr, label):
    by = defaultdict(list)
    for r in res: by[(r['season'], r['week'])].append(r)
    picks = []
    for key, lst in by.items():
        lst.sort(key=lambda r: -r['edge']); picks += [r for r in lst[:k] if r['edge'] >= thr]
    if not picks: print(f"  {label}: top-{k}/week, edge >= {thr*100:+.0f}: no qualifying picks"); return
    n = len(picks); wins = sum(r['y'] for r in picks); exp = sum(r['p_mkt'] for r in picks)
    net = wins - (n - wins); se = math.sqrt(sum(4 * r['p_mkt'] * (1 - r['p_mkt']) for r in picks))
    bys = defaultdict(lambda: [0, 0])
    for r in picks: bys[r['season']][0] += 1; bys[r['season']][1] += r['y']
    print(f"  {label}: top-{k}/week, edge >= {thr*100:+.0f} pts: {n} picks, dogs won {wins} ({wins/n*100:.1f}%) vs market-expected {exp:.1f} ({exp/n*100:.1f}%), "
          f"mean edge claimed {np.mean([r['edge'] for r in picks])*100:+.1f}; NET vs always-favorite {net:+d} picks (±{se:.1f}); by season: " +
          " ".join(f"{s}:{v[1]}-{v[0]-v[1]}" for s, v in sorted(bys.items())))

def run(lo, hi):
    D = build(lo, hi)
    print("=" * 110); print(f"ENGINE C universe: dogs priced {int(lo*100)}-{int(hi*100)}%  ({len(D)} games 2009-2025; dogs won {np.mean([d['y'] for d in D])*100:.1f}% vs priced {np.mean([d['p_mkt'] for d in D])*100:.1f}%)")
    dev = []
    for t in DEV:
        r, _ = fit_score([d for d in D if d['season'] < t], [d for d in D if d['season'] == t], FEATS); dev += r
    hold, w = fit_score([d for d in D if d['season'] <= 2022], [d for d in D if d['season'] in HOLD], FEATS)
    print("  holdout-model coefficients (standardized): " + "  ".join(f"{c}={w[i+2]:+.2f}" for i, c in enumerate(FEATS)))
    quintiles(dev, "DEVELOPMENT walk-forward 2014-2022"); quintiles(hold, "HOLDOUT 2023-2025 (trained once on <=2022)")
    print("\n  THE PICK'EM QUESTION: take only the top qualified upset candidate(s) each week")
    for k in (1, 2):
        for thr in (0.03, 0.05, 0.07):
            topk(dev, k, thr, "  dev "); topk(hold, k, thr, "  HOLD")
    # market-disagreement proxy: dogs where several football signals agree (>= 4 of 6 efficiency diffs favor the dog)
    def agree(d): return sum(v > 0 for v in (d['x_off_pass'], d['x_off_rush'], d['x_def_pass'], d['x_def_rush'], -d['x_protect'], d['x_explosive']))
    for lab, sub in (("dev", [d for d in D if d['season'] in DEV]), ("HOLD", [d for d in D if d['season'] in HOLD])):
        S = [d for d in sub if agree(d) >= 5]; 
        if S: print(f"  signal-agreement (>=5 of 6 football signals favor the dog), {lab}: {len(S)} dogs won {np.mean([d['y'] for d in S])*100:.1f}% vs priced {np.mean([d['p_mkt'] for d in S])*100:.1f}%  (net vs favorite {2*sum(d['y'] for d in S)-len(S):+d})")

if __name__ == '__main__':
    run(0.40, 0.50); run(0.35, 0.50); run(0.45, 0.50)
