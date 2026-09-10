#!/usr/bin/env python3
"""ENGINE A: NFL win probability. Production = no-vig market. Challenger = market-residual logistic model.

    python3 engine_a.py [--games-file games.csv] [--first-test 2014]

Ablation, strictly chronological (expanding window: train on seasons < t, test on season t):
  M0 market only                         logit(P_home) = a*logit(P_mkt)
  M1 + Elo differential (pre-game, results-only Elo, K=20, HFA=48, 1/3 regression to mean each season)
  M2 + rest differential (home_rest - away_rest, days)
  M3 + divisional game flag
  M4 + weather flags (outdoor & temp<32; outdoor & wind>=15)  [temp/wind in games.csv are observed, i.e.
       mild leakage in the model's favor; if it still adds nothing, it adds nothing]
  M5 + QB-change flag for either team (starter differs from the team's previous game)
All features are computable before kickoff. Fit by Newton's method with tiny L2 (1e-4).
Admission criterion: a block stays only if it improves test log loss vs the previous block in a
clear majority of test seasons AND pooled.
"""
import argparse, csv, io, math, urllib.request
from collections import defaultdict
import numpy as np

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def american_to_prob(ml):
    ml = float(ml); return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def logit(p): return math.log(p / (1 - p))

def build(rows):
    rows = [r for r in rows if r["game_type"] in ("REG", "WC", "DIV", "CON", "SB") and r["result"] != ""]
    rows.sort(key=lambda r: (int(r["season"]), int(r["week"]), r["gameday"]))
    elo = defaultdict(lambda: 1500.0); last_season = {}; last_qb = {}
    out = []
    for r in rows:
        s = int(r["season"]); h, a = r["home_team"], r["away_team"]
        for t in (h, a):
            if last_season.get(t) is not None and last_season[t] != s:
                elo[t] = 1500 + (elo[t] - 1500) * (2 / 3)
            last_season[t] = s
        eh, ea = elo[h], elo[a]
        margin = float(r["result"])
        # features (pre-game)
        feat = None
        if r["game_type"] == "REG" and r["away_moneyline"] and r["home_moneyline"] and margin != 0:
            pa, ph = american_to_prob(r["away_moneyline"]), american_to_prob(r["home_moneyline"])
            ph = ph / (pa + ph)
            outdoor = r["roof"] in ("outdoors", "open")
            temp = float(r["temp"]) if r["temp"] else 60.0
            wind = float(r["wind"]) if r["wind"] else 0.0
            qb_chg = int((h in last_qb and last_qb[h] != r["home_qb_id"]) or
                         (a in last_qb and last_qb[a] != r["away_qb_id"]))
            feat = dict(season=s, y=int(margin > 0), mkt=logit(ph), p_mkt=ph,
                        elo=(eh - ea) / 400.0,
                        rest=(float(r["home_rest"] or 7) - float(r["away_rest"] or 7)) / 7.0,
                        div=int(r["div_game"] == "1"),
                        cold=int(outdoor and temp < 32), windy=int(outdoor and wind >= 15),
                        qbchg=qb_chg)
        # Elo update (after recording pre-game values)
        exp_h = 1 / (1 + 10 ** (-((eh + 48) - ea) / 400))
        res_h = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        mov = math.log(abs(margin) + 1) * 2.2 / ((eh - ea) * 0.001 + 2.2) if margin else 1
        d = 20 * mov * (res_h - exp_h); elo[h] += d; elo[a] -= d
        last_qb[h] = r["home_qb_id"]; last_qb[a] = r["away_qb_id"]
        if feat: out.append(feat)
    return out

def fit(X, y, l2=1e-4):
    w = np.zeros(X.shape[1])
    for _ in range(25):
        p = 1 / (1 + np.exp(-X @ w)); g = X.T @ (p - y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g); w -= step
        if np.abs(step).max() < 1e-8: break
    return w

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-file"); ap.add_argument("--first-test", type=int, default=2014)
    ap.add_argument("--json", help="write results to this JSON file")
    a = ap.parse_args(); results = dict(rows=None, tests=None, raw=None, models=[])
    rows = list(csv.DictReader(open(a.games_file, newline=""))) if a.games_file else \
           list(csv.DictReader(io.StringIO(urllib.request.urlopen(URL).read().decode())))
    data = build(rows)
    blocks = [("M0 market", ["mkt"]), ("M1 +elo", ["mkt", "elo"]), ("M2 +rest", ["mkt", "elo", "rest"]),
              ("M3 +div", ["mkt", "elo", "rest", "div"]), ("M4 +weather", ["mkt", "elo", "rest", "div", "cold", "windy"]),
              ("M5 +qbchg", ["mkt", "elo", "rest", "div", "cold", "windy", "qbchg"])]
    seasons = sorted({d["season"] for d in data}); tests = [s for s in seasons if s >= a.first_test]
    print(f"rows {len(data)}, seasons {seasons[0]}-{seasons[-1]}, test seasons {tests[0]}-{tests[-1]}\n")
    results["rows"] = len(data); results["tests"] = [tests[0], tests[-1]]
    # raw market (no fitted intercept/slope) as the true production baseline
    raw_ll = {s: np.mean([-math.log(d["p_mkt"] if d["y"] else 1 - d["p_mkt"]) for d in data if d["season"] == s]) for s in tests}
    raw_acc = {s: np.mean([(d["p_mkt"] >= 0.5) == d["y"] for d in data if d["season"] == s]) for s in tests}
    print("RAW no-vig market (production baseline): pooled logloss %.4f  accuracy %.4f" %
          (np.mean(list(raw_ll.values())), np.mean(list(raw_acc.values()))))
    results["raw"] = dict(logloss=float(np.mean(list(raw_ll.values()))), accuracy=float(np.mean(list(raw_acc.values()))))
    prev = None; coefs = defaultdict(list)
    print(f"\n{'model':12} {'logloss':>8} {'brier':>7} {'acc':>6} {'flip_n':>6} {'flip_acc':>8} {'better than prev (seasons)':>26}")
    for name, cols in blocks:
        ll, br, acc, flips, flip_ok, wins = [], [], [], 0, 0, 0
        for t in tests:
            tr = [d for d in data if d["season"] < t]; te = [d for d in data if d["season"] == t]
            Xtr = np.array([[1] + [d[c] for c in cols] for d in tr], float); ytr = np.array([d["y"] for d in tr], float)
            Xte = np.array([[1] + [d[c] for c in cols] for d in te], float); yte = np.array([d["y"] for d in te], float)
            w = fit(Xtr, ytr); coefs[name].append(w)
            p = 1 / (1 + np.exp(-Xte @ w)); p = np.clip(p, 1e-6, 1 - 1e-6)
            l = -np.mean(yte * np.log(p) + (1 - yte) * np.log(1 - p)); ll.append(l)
            br.append(np.mean((p - yte) ** 2)); acc.append(np.mean((p >= 0.5) == yte))
            pm = np.array([d["p_mkt"] for d in te]); f = (p >= 0.5) != (pm >= 0.5)
            flips += f.sum(); flip_ok += ((p >= 0.5) == yte)[f].sum()
            if prev is not None and l < prev[t]: wins += 1
        cur = dict(zip(tests, ll))
        results["models"].append(dict(name=name, features=cols, logloss=float(np.mean(ll)), brier=float(np.mean(br)),
                                      accuracy=float(np.mean(acc)), flips=int(flips), flip_acc=(float(flip_ok / flips) if flips else None),
                                      better_than_prev=(f"{wins}/{len(tests)}" if prev is not None else None)))
        print(f"{name:12} {np.mean(ll):8.4f} {np.mean(br):7.4f} {np.mean(acc):6.4f} {flips:6d} "
              f"{(flip_ok / flips if flips else float('nan')):8.3f} {('%d/%d' % (wins, len(tests))) if prev is not None else '-':>26}")
        prev = cur
    print("\ncoefficients in the final fit (train < %d), and sign consistency across test seasons:" % tests[-1])
    for name, cols in blocks:
        W = np.array(coefs[name]); last = W[-1]
        cons = [(np.sign(W[:, i + 1]) == np.sign(last[i + 1])).mean() for i in range(len(cols))]
        print(f"  {name:12} " + "  ".join(f"{c}={last[i+1]:+.3f} ({cons[i]:.0%} same sign)" for i, c in enumerate(cols)))
        for m in results["models"]:
            if m["name"] == name: m["coefficients"] = {c: dict(value=float(last[i+1]), sign_consistency=float(cons[i])) for i, c in enumerate(cols)}
    if a.json:
        import json; json.dump(results, open(a.json, "w"), indent=1); print(f"\nwrote {a.json}")

if __name__ == "__main__":
    main()
