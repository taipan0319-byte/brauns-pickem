#!/usr/bin/env python3
"""U7: does Engine B add P(first) over pure chalk, out of sample?

Replays each season week by week against the REAL game results. Opponents are simulated from
family.json (we have no historical picks), so every policy is scored against the same opponent
draws (common random numbers) under three 'truth' scenarios for how the family really behaves.
Engine B sees exactly what it sees in production at each week: remaining schedule, lines,
standings to date, family model. Its recommendation is then graded by what actually happened.

    python3 backtest_engine_b.py --games-file data/games.csv [--seasons 2015-2025] [--reps 150]

Policies (user picks):
  chalk        favorite in every game (D6 production rule when Engine B is quiet)
  prod         Engine B as shipped: 3-scenario screen, HIGH/MEDIUM -> dog, LOW -> favorite
  any_positive Engine B with the confidence filter removed: dog whenever dP(first) > 0
  signif       Engine B, as-modeled scenario only, dog when dP > MC noise
  static_52    dog whenever the favorite is below 52% (no model)
  late_var     chalk through week 13; from week 14 take dogs in <62% games when trailing by > 0.05 x games left
--adversarial (Block 17 round 1, ChatGPT): opponents drawn from models Engine B is not told about —
  a correlated room (latent per-game chalk sentiment shared by all six, Gaussian copula, marginals preserved)
  at rho 0.2 / 0.5 / 0.8, and the six fitted dog-rate profiles shuffled among the people each season.
--calibrated: control with game outcomes drawn from the market instead of real scores.
"""
import argparse, csv, json, os, sys, time
import numpy as np
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine_b as eb

SCEN = [("as-modeled", 1.0), ("chalkier x0.5", 0.5), ("wilder x2", 2.0)]

def season_data(rows, season, family):
    g = [r for r in rows if int(r["season"]) == season and r["game_type"] == "REG" and r["result"] not in ("", "0")]
    g.sort(key=lambda r: (int(r["week"]), r["gameday"]))
    ph = np.array([eb.home_prob(r) for r in g]); pfav = np.maximum(ph, 1 - ph); fav_home = ph >= 0.5
    fav_team = [r["home_team"] if fh else r["away_team"] for r, fh in zip(g, fav_home)]
    home_won = np.array([float(r["result"]) > 0 for r in g]); fav_won = home_won == fav_home
    week = np.array([int(r["week"]) for r in g])
    fams = [eb.scale_family(family, k) for _, k in SCEN]
    P_opp = np.array([[[eb.opponent_pick_fav_prob(m, r, pf, ft) for m in fam] for r, pf, ft in zip(g, pfav, fav_team)] for fam in fams])
    return dict(season=season, pfav=pfav, fav_won=fav_won, week=week, P_opp=P_opp, weeks=sorted(set(week.tolist())),
                names=[m["name"] for m in family], family=family, fav_team=fav_team,
                games_min=[dict(home_team=r["home_team"], away_team=r["away_team"]) for r in g])

def week_cache(sd, w, s, sims, seed):
    """Everything in engine_b.evaluate that does not depend on standings or on this week's user picks."""
    rng = np.random.default_rng(seed)
    iw = np.where(sd["week"] == w)[0]; ifu = np.where(sd["week"] > w)[0]; N = sd["P_opp"].shape[2]
    pf = sd["pfav"][ifu]; Po = sd["P_opp"][s][ifu]
    fw_f = rng.random((sims, len(ifu)), dtype=np.float32) < pf[None, :]
    of_f = rng.random((sims, len(ifu), N), dtype=np.float32) < Po[None, :, :]
    user_future = fw_f.sum(1).astype(np.int32)                      # D6: user takes the favorite in every future game
    opp_future = (of_f == fw_f[:, :, None]).sum(1).astype(np.int32)
    fw_w = rng.random((sims, len(iw)), dtype=np.float32) < sd["pfav"][iw][None, :]
    of_w = rng.random((sims, len(iw), N), dtype=np.float32) < sd["P_opp"][s][iw][None, :, :]
    opp_total = opp_future + (of_w == fw_w[:, :, None]).sum(1).astype(np.int32)
    return dict(iw=iw, fw_w=fw_w, user_future=user_future, opp_total=opp_total)

def fast_eval(c, pfav_w, user_pts, opp_pts):
    """engine_b.evaluate's coordinate search, same math, on the cached draws."""
    osc = c["opp_total"] + opp_pts[None, :].astype(np.int32)
    omax = osc.max(1); ntop = (osc == omax[:, None]).sum(1)
    tie_val = 1.0 / (ntop + 1)
    def pf_vec(us): return np.where(us > omax, 1.0, np.where(us == omax, tie_val, 0.0))
    fw = c["fw_w"]; G = fw.shape[1]; half = fw.shape[0] // 2
    user_fav = pfav_w >= eb.USER_DOG_THRESHOLD
    us = user_pts + c["user_future"] + (user_fav[None, :] == fw).sum(1)
    base = pf_vec(us).mean()
    order = np.argsort(pfav_w, kind="stable"); deltas = np.zeros(G); noise = np.zeros(G)
    for _ in range(2):
        for i in order:
            cur = (user_fav[i] == fw[:, i]); us_fav = us - cur + fw[:, i]; us_dog = us - cur + (~fw[:, i])
            diff = pf_vec(us_dog) - pf_vec(us_fav)
            d = diff.mean(); d1 = diff[:half].mean(); d2 = diff[half:].mean()
            deltas[i] = d; noise[i] = abs(d1 - d2) / 2 + 1e-4
            user_fav[i] = d <= 0; us = us_fav if d <= 0 else us_dog
    return base, pf_vec(us).mean(), deltas, user_fav, noise

def norm_cdf(z):
    try:
        from scipy.special import erf
    except ImportError:
        import math; erf = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf(z / np.sqrt(2.0)))

def draw_opponents(sd, truth, U0, rng):
    """Returns opp_pick_fav (G x N) under a 'truth' Engine B does not know about.
    scen k      : independent picks from scenario k of the family model (common uniforms U0)
    corr rho    : Gaussian copula; a latent per-game chalk sentiment shared by all six, marginals preserved
    perm        : the six fitted dog-rate profiles shuffled among the people each season; team leans stay put"""
    kind, param = truth["kind"], truth.get("param")
    if kind == "scen": return U0 < sd["P_opp"][param]
    if kind == "corr":
        G, N = U0.shape; S = rng.standard_normal(G)
        Z = np.sqrt(param) * S[:, None] + np.sqrt(1 - param) * rng.standard_normal((G, N))
        return norm_cdf(Z) < sd["P_opp"][0]
    if kind == "perm":
        perm = rng.permutation(len(sd["family"]))
        fam = [dict(m, dog_rate=sd["family"][perm[i]]["dog_rate"]) for i, m in enumerate(sd["family"])]
        P = np.array([[eb.opponent_pick_fav_prob(m, g, pf, ft) for m in fam]
                      for g, pf, ft in zip(sd["games_min"], sd["pfav"], sd["fav_team"])])
        return U0 < P
    raise ValueError(kind)

def grade_prod(ds, noise0, d0):
    """Production screen: LOW -> favorite; HIGH/MEDIUM -> dog iff dP > 0."""
    agree = all(x > 0 for x in ds) or all(x <= 0 for x in ds)
    if not agree or abs(d0) <= noise0: return True
    return not (d0 > 0)

def run_season(args):
    sd, reps, sims, truths, calibrated = args; season = sd["season"]; t0 = time.time()
    N = len(sd["names"]); G = len(sd["pfav"]); weeks = sd["weeks"]
    caches = {w: [week_cache(sd, w, s, sims, season * 1000 + w * 10 + s) for s in range(3)] for w in weeks}
    policies = ["chalk", "prod", "any_positive", "signif", "static_52", "late_var"]
    out = {t["name"]: {p: dict(pf=[], dev=0, hit=0, exp=0.0, dev_by_week={}) for p in policies} for t in truths}
    rng = np.random.default_rng(season * 7919)
    for rep in range(reps):
        U = rng.random((G, N))
        fav_won = (rng.random(G) < sd["pfav"]) if calibrated else sd["fav_won"]   # control: outcomes drawn from the market
        for tr in truths:
            t = tr["name"]
            opp_pick_fav = draw_opponents(sd, tr, U, rng); opp_correct = (opp_pick_fav == fav_won[:, None])
            opp_cum = {}; run = np.zeros(N, int)
            for w in weeks:
                opp_cum[w] = run.copy(); run = run + opp_correct[sd["week"] == w].sum(0)
            opp_final = run
            memo = {}
            def ev(w, s, upts):
                k = (w, s, upts)
                if k not in memo: memo[k] = fast_eval(caches[w][s], sd["pfav"][caches[w][s]["iw"]], upts, opp_cum[w])
                return memo[k]
            for p in policies:
                upts = 0; st = out[t][p]
                for w in weeks:
                    iw = np.where(sd["week"] == w)[0]; pf = sd["pfav"][iw]; fav = np.ones(len(iw), bool)
                    if p == "static_52": fav = pf >= 0.52
                    elif p == "late_var":
                        behind = opp_cum[w].max() - upts; remaining = (sd["week"] >= w).sum()
                        if w >= 14 and behind > 0.05 * remaining: fav = pf >= 0.62
                    elif p == "any_positive": fav = ev(w, 0, upts)[3].copy()
                    elif p == "signif":
                        _, _, d, _, nz = ev(w, 0, upts); fav = ~(d > nz)
                    elif p == "prod":
                        r = [ev(w, s, upts) for s in range(3)]
                        fav = np.array([grade_prod([r[s][2][i] for s in range(3)], r[0][4][i], r[0][2][i]) for i in range(len(iw))])
                    won = fav_won[iw]; upts += int((fav == won).sum())
                    nd = int((~fav).sum())
                    if nd:
                        st["dev"] += nd; st["hit"] += int((~fav & ~won).sum()); st["exp"] += float((1 - pf[~fav]).sum())
                        st["dev_by_week"][w] = st["dev_by_week"].get(w, 0) + nd
                best = max(upts, opp_final.max()); ntop = int((opp_final == best).sum()) + (upts == best)
                st["pf"].append(1.0 / ntop if upts == best else 0.0)
    print(f"season {season} done in {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    return season, out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-file"); ap.add_argument("--seasons", default="2015-2025")
    ap.add_argument("--reps", type=int, default=150); ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--family", default=os.path.join(HERE, "family.json")); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--calibrated", action="store_true", help="control: replace real results with draws from the market probabilities")
    ap.add_argument("--adversarial", action="store_true", help="Block 17 round 1: correlated room (rho 0.2/0.5/0.8) and shuffled dog rates")
    a = ap.parse_args()
    lo, hi = map(int, a.seasons.split("-")); seasons = list(range(lo, hi + 1))
    rows = eb.load_games(a.games_file); family = json.load(open(a.family))
    truths = [dict(name=SCEN[k][0], kind="scen", param=k) for k in range(3)]
    if a.adversarial:
        truths = [dict(name="as-modeled", kind="scen", param=0)] + \
                 [dict(name=f"correlated room rho={r}", kind="corr", param=r) for r in (0.2, 0.5, 0.8)] + \
                 [dict(name="dog rates shuffled among people", kind="perm")]
    jobs = [(season_data(rows, s, family), a.reps, a.sims, truths, a.calibrated) for s in seasons]
    with Pool(a.procs) as pool: results = dict(pool.map(run_season, jobs, chunksize=1))
    policies = ["chalk", "prod", "any_positive", "signif", "static_52", "late_var"]
    print(f"U7 Engine B replay {'[CALIBRATED CONTROL: outcomes drawn from market]' if a.calibrated else '[REAL RESULTS]'}  seasons {a.seasons}  reps/season {a.reps}  inner sims {a.sims}  N=7  ties split")
    print("Real game results; opponents simulated from family.json under three truths. Paired vs chalk.\n")
    for tr in truths:
        t = tr["name"]
        print(f"== opponents really behave: {t} ==")
        print(f"{'policy':13}{'P(first)':>9}{'vs chalk':>10}{'SE':>7}{'dogs/season':>12}{'dog hit%':>9}{'exp hit%':>9}{'wk1-9':>7}{'wk10+':>7}")
        chalk = np.concatenate([np.array(results[s][t]["chalk"]["pf"]) for s in seasons])
        for p in policies:
            pf = np.concatenate([np.array(results[s][t][p]["pf"]) for s in seasons])
            diff = pf - chalk; se = diff.std(ddof=1) / np.sqrt(len(diff))
            dev = sum(results[s][t][p]["dev"] for s in seasons); hit = sum(results[s][t][p]["hit"] for s in seasons)
            exp = sum(results[s][t][p]["exp"] for s in seasons); nrs = len(seasons) * a.reps
            early = sum(v for s in seasons for w, v in results[s][t][p]["dev_by_week"].items() if w <= 9)
            print(f"{p:13}{pf.mean():9.4f}{diff.mean():+10.4f}{se:7.4f}{dev/nrs:12.2f}"
                  f"{(100*hit/dev if dev else 0):9.1f}{(100*exp/dev if dev else 0):9.1f}{early/nrs:7.2f}{(dev-early)/nrs:7.2f}")
        print()
    t0 = truths[0]["name"]; print(f"per season, {t0} truth: P(first)")
    print(f"{'season':8}" + "".join(f"{p:>13}" for p in policies))
    for s in seasons:
        print(f"{s:<8}" + "".join(f"{np.mean(results[s][t0][p]['pf']):13.3f}" for p in policies))
    print("\ndog hit% = share of recommended dogs that actually won; exp hit% = what the market said they should win.")

if __name__ == "__main__":
    main()
