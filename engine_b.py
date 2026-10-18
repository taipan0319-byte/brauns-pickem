#!/usr/bin/env python3
"""ENGINE B: family-pool optimizer. Chooses picks to maximize P(finish first), not expected score.

    python3 engine_b.py --season 2026 --week 1 [--standings standings.json] [--family family.json]
                        [--sims 20000] [--games-file games.csv] [--dry-run] [--screen]

Inputs
  games.csv (nflverse)   remaining schedule; win probabilities from no-vig moneylines where present,
                         else from the spread, else 0.57 for the home team.
  family.json            opponent pick model, one entry per opponent:
                           {"name": "Sue", "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02},
                            "bias_team": "GB", "bias_strength": 0.4}
                         dog_rate = P(picks the underdog) by favorite-probability band
                         (tossup: fav<55%, close: 55-62%, other: >=62%). bias_strength = P(picks the
                         bias team regardless of the line) when that team plays.
  standings.json         {"Ryan": 12, "Sue": 13, ...} points so far (omit in week 1).
Method
  Monte Carlo with common random numbers over the remaining season. For every game this week, compare
  P(first) when the user picks the favorite vs the dog, holding the other current-week picks at the
  current policy; two coordinate passes so multiple deviations are evaluated jointly. Future-week user
  picks follow the default rule (dog only when favorite < USER_DOG_THRESHOLD).
  --screen  runs the same evaluation under three family scenarios (family.json as given, a chalk-heavier
  version, a deviation-heavier version) and reports a confidence grade for each recommendation:
    HIGH   all scenarios agree and |dP| exceeds 3x Monte Carlo noise
    MEDIUM all scenarios agree
    LOW    scenarios disagree, or dP is within noise  -> the favorite is used
  Recommendations are appended to engine_b_log.csv (append-only) with a timestamp.
Roster note: R C B is a historical entry (Ryan's late father). Never include it as an opponent.
Everything in family.json is a prior until pool_picks.csv or fit_from_scores.py provides estimates.
"""
import argparse, csv, datetime as dt, io, json, math, os, urllib.request
import numpy as np

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
HERE = os.path.dirname(os.path.abspath(__file__))
USER_DOG_THRESHOLD = 0.50   # D6: the user takes the favorite in every future game; the current week is evaluated explicitly
TIE_RULE = "split"          # U1 in DECISIONS.md: ties split evenly (approximates a tiebreaker lottery)
DEFAULT_FAMILY = [
 {"name": "Casey",   "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": None,  "bias_strength": 0.0},
 {"name": "Sue",     "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": "GB",  "bias_strength": 0.4},
 {"name": "Nolan",   "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": "CHI", "bias_strength": 0.4},
 {"name": "Sheila",  "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": "CHI", "bias_strength": 0.4},
 {"name": "Kaleigh", "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": "GB",  "bias_strength": 0.4},
 {"name": "Molly",   "dog_rate": {"tossup": 0.15, "close": 0.07, "other": 0.02}, "bias_team": None,  "bias_strength": 0.0},
]

def american_to_prob(ml):
    ml = float(ml); return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def home_prob(g):
    if g["away_moneyline"] and g["home_moneyline"]:
        pa, ph = american_to_prob(g["away_moneyline"]), american_to_prob(g["home_moneyline"])
        return ph / (pa + ph)
    if g["spread_line"]:
        return 1 / (1 + math.exp(-float(g["spread_line"]) / 13.5 * 1.6))
    return 0.57

def load_games(path):
    return list(csv.DictReader(open(path, newline=""))) if path else \
           list(csv.DictReader(io.StringIO(urllib.request.urlopen(URL).read().decode())))

def band(pfav): return "tossup" if pfav < 0.55 else "close" if pfav < 0.62 else "other"

def opponent_pick_fav_prob(member, g, pfav, fav_team):
    base = 1 - member["dog_rate"][band(pfav)]
    bt = member.get("bias_team")
    if bt and bt in (g["home_team"], g["away_team"]):
        s = member.get("bias_strength", 0.0)
        return s * (1.0 if fav_team == bt else 0.0) + (1 - s) * base
    return base

def scale_family(family, k):
    """Multiply every dog rate by k (capped at 0.9); bias unchanged."""
    return [dict(m, dog_rate={b: min(0.9, r * k) for b, r in m["dog_rate"].items()}) for m in family]

JOINT_K = 10   # D30: enumerate all 2^K pick combinations over the K closest games this week (ChatGPT Block 7, test 1)

def evaluate(games, family, standings, user, sims, seed, this_week_mask, fixed_picks=None):
    """Returns (base P(first), final P(first), deltas dict, user_fav picks, P_opp, pfav, fav_team, fav_home, noise).

    Search: (1) coordinate search, closest games first (D4/D27); (2) joint enumeration of every combination over the
    K closest searchable games on the first half of the simulations; (3) the candidates {all-favorite, coordinate
    result, best joint combination} are scored on the SECOND half, which the enumeration never saw, and the best
    one is kept (D30). For games in the kept deviation set, `deltas` holds the SET's gain over all-favorites and
    `noise` the set's noise, both from the confirmation half; for other games, the single-toggle delta at the
    final picks. `fixed_picks`: {index: True/False} for locked games (user takes favorite True/False), excluded
    from the search but still simulated."""
    G, N = len(games), len(family)
    ph = np.array([home_prob(g) for g in games]); pfav = np.maximum(ph, 1 - ph); fav_home = ph >= 0.5
    fav_team = [g["home_team"] if fh else g["away_team"] for g, fh in zip(games, fav_home)]
    P_opp = np.array([[opponent_pick_fav_prob(m, g, pf, ft) for m in family] for g, pf, ft in zip(games, pfav, fav_team)])
    rng = np.random.default_rng(seed)
    fav_wins = rng.random((sims, G)) < pfav[None, :]
    opp_fav = rng.random((sims, G, N)) < P_opp[None, :, :]
    opp_pts = np.array([standings.get(m["name"], 0) for m in family], float)
    user_pts = float(standings.get(user, 0))
    opp_scores = opp_pts[None, :] + (opp_fav == fav_wins[:, :, None]).sum(1)
    omax = opp_scores.max(1); ntop_o = (opp_scores == omax[:, None]).sum(1); tie_val = 1.0 / (ntop_o + 1)
    half = sims // 2; A, B = slice(0, half), slice(half, None)
    def pf_vec(uf, sl=slice(None)):
        us = user_pts + (uf[None, :] == fav_wins[sl]).sum(1)
        return np.where(us > omax[sl], 1.0, np.where(us == omax[sl], tie_val[sl], 0.0))
    def p_first(uf, sl=slice(None)): return pf_vec(uf, sl).mean()
    user_fav = pfav >= USER_DOG_THRESHOLD
    fixed_picks = fixed_picks or {}
    for i, v in fixed_picks.items(): user_fav[i] = bool(v)
    chalk = user_fav.copy()
    base = p_first(chalk)
    idx = [i for i in np.where(this_week_mask)[0] if i not in fixed_picks]
    order = sorted(idx, key=lambda i: pfav[i])
    deltas, noise = {}, {}
    def coordinate(uf):
        for _ in range(2):
            for i in order:
                u1 = uf.copy(); u1[i] = True; u0 = uf.copy(); u0[i] = False
                d = p_first(u0) - p_first(u1); uf[i] = d <= 0
        return uf
    coord = coordinate(user_fav.copy())
    # joint enumeration over the K closest searchable games, scored on half A only
    K = min(JOINT_K, len(order)); joint = coord.copy(); best_val = -1.0
    if K:
        ks = order[:K]; W = fav_wins[A][:, ks]
        rest = coord.copy(); rest_pts = user_pts + (np.delete(rest, ks)[None, :] == np.delete(fav_wins[A], ks, axis=1)).sum(1)
        for c in range(2 ** K):
            pick = np.array([(c >> j) & 1 == 0 for j in range(K)])      # bit set = take the dog
            us = rest_pts + (W == pick[None, :]).sum(1)
            val = np.where(us > omax[A], 1.0, np.where(us == omax[A], tie_val[A], 0.0)).mean()
            if val > best_val + 1e-12: best_val, best_c = val, pick.copy()
        joint = coord.copy(); joint[ks] = best_c
    # confirmation on half B, which the enumeration never saw
    cands = {"chalk": chalk, "coordinate": coord, "joint": joint}
    scoreB = {k: p_first(v, B) for k, v in cands.items()}
    keep = max(scoreB, key=lambda k: (scoreB[k], k == "chalk"))   # ties go to chalk
    user_fav = cands[keep].copy()
    diffB = pf_vec(user_fav, B) - pf_vec(chalk, B); q = len(diffB) // 2
    set_delta = diffB.mean(); set_noise = abs(diffB[:q].mean() - diffB[q:].mean()) / 2 + 1e-4
    dev = [i for i in idx if user_fav[i] != chalk[i]]
    for i in fixed_picks: deltas[i] = 0.0; noise[i] = 1.0          # locked: nothing to decide
    for i in idx:
        if i in dev: deltas[i] = set_delta; noise[i] = set_noise
        else:
            u1 = user_fav.copy(); u1[i] = True; u0 = user_fav.copy(); u0[i] = False
            db = pf_vec(u0, B) - pf_vec(u1, B); deltas[i] = db.mean(); noise[i] = abs(db[:q].mean() - db[q:].mean()) / 2 + 1e-4
    return base, p_first(user_fav), deltas, user_fav, P_opp, pfav, fav_team, fav_home, noise

def live_standings(standings, all_games, season, week):
    """standings.json is written at each weekly close (weeks < `week`). Add points from THIS week's finished games
    using revealed picks in pool_picks.csv, so mid-week P(first) sees Thursday's result (ChatGPT Block 7, finding 1)."""
    out = dict(standings); path = os.path.join(HERE, "pool_picks.csv")
    if not out or not os.path.exists(path): return out
    won = {g["game_id"]: (g["home_team"] if float(g["result"]) > 0 else g["away_team"]) for g in all_games
           if int(g["season"]) == season and int(g["week"]) == week and g["result"] not in ("", "0")}
    seen = set()
    for r in csv.DictReader(open(path, newline="")):
        if r["game_id"] in won and r["pick"] not in ("", "NONE") and r["member"] in out:
            out[r["member"]] = out[r["member"]] + int(r["pick"] == won[r["game_id"]]); seen.add((r["game_id"], r["member"]))
    log = os.path.join(HERE, "engine_b_log.csv")   # the user's own finished games: last logged recommendation until revealed
    if os.path.exists(log) and "Ryan" in out:
        last = {}
        for r in csv.DictReader(open(log, newline="")):
            if int(r["season"]) == season and int(r["week"]) == week: last[r["game_id"]] = r["recommendation"]
        for gid, w in won.items():
            if (gid, "Ryan") not in seen and gid in last: out["Ryan"] = out["Ryan"] + int(last[gid] == w)
    return out

def locked_picks(games, idx, season, week, now=None):
    """{index: user takes favorite?} for this week's games already locked on CBS: kickoff passed, or any Sunday game
    once the first Sunday kickoff has passed (CBS locks the whole Sunday slate then). The held pick is the last
    logged recommendation for that game, else the favorite (ChatGPT Block 7, finding 2)."""
    try:
        from zoneinfo import ZoneInfo; ET = ZoneInfo("America/New_York")
    except Exception: return {}
    now = now or dt.datetime.now(dt.timezone.utc)
    def kick(g):
        try: return dt.datetime.strptime(g["gameday"] + " " + g["gametime"], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        except Exception: return None
    kicks = {i: kick(games[i]) for i in idx}
    sundays = [k for i, k in kicks.items() if k and k.weekday() == 6]
    first_sunday = min(sundays) if sundays else None
    locked = {}
    for i in idx:
        k = kicks[i]
        if k is None: continue
        if now >= k or (first_sunday and k.weekday() == 6 and now >= first_sunday): locked[i] = None
    if not locked: return {}
    last = {}
    log = os.path.join(HERE, "engine_b_log.csv")
    if os.path.exists(log):
        for r in csv.DictReader(open(log, newline="")):
            if int(r["season"]) == season and int(r["week"]) == week: last[r["game_id"]] = r["recommendation"]
    for i in list(locked):
        g = games[i]; ph = home_prob(g); fav = g["home_team"] if ph >= 0.5 else g["away_team"]
        locked[i] = (last.get(g["game_id"], fav) == fav)
    return locked

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--games-file"); ap.add_argument("--family", default=os.path.join(HERE, "family.json"))
    ap.add_argument("--standings"); ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--user", default="Ryan"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--screen", action="store_true", help="v1.0 weekly screen with confidence grades")
    ap.add_argument("--fit", action="store_true", help="update family.json from pool_picks.csv, then exit")
    a = ap.parse_args()
    family = json.load(open(a.family)) if os.path.exists(a.family) else DEFAULT_FAMILY
    if a.fit: return fit_family(a, family)
    standings = json.load(open(a.standings)) if a.standings else {}
    all_games = load_games(a.games_file)
    standings = live_standings(standings, all_games, a.season, a.week)       # D30: add this week's finished games
    games = [g for g in all_games if int(g["season"]) == a.season and g["game_type"] == "REG"
             and int(g["week"]) >= a.week and g["result"] == ""]
    games.sort(key=lambda g: (int(g["week"]), g["gameday"]))
    mask = np.array([int(g["week"]) == a.week for g in games]); idx = np.where(mask)[0]
    fixed = locked_picks(games, idx, a.season, a.week)                         # D30: locked games are not searchable
    seed = a.season * 100 + a.week
    scenarios = [("as-modeled", family)]
    if a.screen: scenarios += [("chalkier x0.5", scale_family(family, 0.5)), ("wilder x2", scale_family(family, 2.0))]
    res = {name: evaluate(games, fam, standings, a.user, a.sims, seed, mask, fixed) for name, fam in scenarios}
    base, final, deltas, user_fav, P_opp, pfav, fav_team, fav_home, noise = res["as-modeled"]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"ENGINE B  {a.season} week {a.week}  user={a.user}  N={len(family)+1}  sims={a.sims}  tie rule={TIE_RULE}")
    print(f"opponents: {', '.join(m['name'] for m in family)}   live standings: {standings or 'none (week 1)'}")
    if fixed: print(f"locked this week (not searchable, pick held): {', '.join(games[i]['away_team']+'@'+games[i]['home_team']+'='+(fav_team[i] if fixed[i] else (games[i]['away_team'] if fav_home[i] else games[i]['home_team'])) for i in fixed)}")
    print(f"P(first) if all favorites this week: {base:.3f}   with recommended picks: {final:.3f}\n")
    hdr = f"{'game':10} {'market fav':>10} {'P(fav)':>7} {'family on fav':>13} {'dP(first) if dog':>16}  {'pick':5}"
    if a.screen: hdr += "  confidence"
    print(hdr); out = []
    for i in idx:
        g = games[i]; dog = g["away_team"] if fav_home[i] else g["home_team"]
        d = deltas[i]; conf = ""; agree = True
        if i in fixed:
            conf = "LOCKED"; pick = fav_team[i] if fixed[i] else dog
        elif a.screen:
            ds = [res[n][2][i] for n, _ in scenarios]; agree = all(x > 0 for x in ds) or all(x <= 0 for x in ds)
            # D27: scenario disagreement no longer vetoes a deviation (U7 replay: the veto left ~1 dog/season and
            # no gain; the noise test alone is +1.8pp P(first) with calibrated outcomes). Disagreement is printed.
            if abs(d) <= noise[i]: conf = "LOW"; pick = fav_team[i]
            elif abs(d) > 3 * noise[i]: conf = "HIGH"; pick = dog if d > 0 else fav_team[i]
            else: conf = "MEDIUM"; pick = dog if d > 0 else fav_team[i]
        else:
            pick = dog if user_fav[i] == False else fav_team[i]
        line = f"{g['away_team']+'@'+g['home_team']:10} {fav_team[i]:>10} {pfav[i]:7.3f} {P_opp[i].mean():13.2f} {d:+16.4f}  {pick:5}"
        if a.screen: line += f"  {conf}" + ("" if agree else "  (scenarios disagree)")
        print(line)
        out.append(dict(logged_at_utc=now, season=a.season, week=a.week, game_id=g["game_id"], fav=fav_team[i],
                        p_fav=f"{pfav[i]:.4f}", family_fav_rate=f"{P_opp[i].mean():.3f}", dP_first_dog=f"{d:+.4f}",
                        mc_noise=f"{noise[i]:.4f}", confidence=conf, recommendation=pick,
                        p_first_base=f"{base:.4f}", p_first_final=f"{final:.4f}",
                        standings=json.dumps(standings) if standings else "", family_model=os.path.basename(a.family)))
    print("\nfamily on fav = modeled share of the six opponents expected to pick the favorite.")
    print("dP(first) = change in Ryan's probability of finishing first from taking the dog, all else at policy.")
    if not a.dry_run:
        log = os.path.join(HERE, "engine_b_log.csv"); new = not os.path.exists(log)
        with open(log, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            if new: w.writeheader()
            w.writerows(out)
        print(f"appended {len(out)} rows to {log}")

def fit_family(a, family):
    """Beta-shrunk dog rates by band from pool_picks.csv (columns: season,week,game_id,member,pick)."""
    picks_path = os.path.join(HERE, "pool_picks.csv")
    if not os.path.exists(picks_path):
        print("no pool_picks.csv yet; family.json left as is"); return
    games = {g["game_id"]: g for g in load_games(a.games_file)}
    counts = {m["name"]: {b: [0, 0] for b in ("tossup", "close", "other")} for m in family}
    for r in csv.DictReader(open(picks_path, newline="")):
        g = games.get(r["game_id"])
        if not g or r["member"] not in counts or r["pick"] in ("", "NONE"): continue   # NONE = no entry, not a pick
        p = home_prob(g); pf = max(p, 1 - p); fav = g["home_team"] if p >= 0.5 else g["away_team"]
        c = counts[r["member"]][band(pf)]; c[0] += 1; c[1] += (r["pick"] != fav)
    PRIOR_N = {"tossup": 10.0, "close": 3.0, "other": 10.0}   # D21: band-specific prior strength
    # D30: team-loyalty strength is estimated, not assumed. In games involving the member's team, the share of picks
    # on that team above what the band rates alone predict identifies s; shrunk toward the 0.4 prior with N=10.
    bias_obs = {m["name"]: [0, 0.0, 0] for m in family}   # [team picks, expected team picks under s=0, games]
    for r in csv.DictReader(open(picks_path, newline="")):
        g = games.get(r["game_id"]); m = next((x for x in family if x["name"] == r["member"]), None)
        if not g or not m or not m.get("bias_team") or r["pick"] in ("", "NONE"): continue
        bt = m["bias_team"]
        if bt not in (g["home_team"], g["away_team"]): continue
        p = home_prob(g); pf = max(p, 1 - p); fav = g["home_team"] if p >= 0.5 else g["away_team"]
        base_fav = 1 - m.get("prior_dog_rate", m["dog_rate"])[band(pf)]
        o = bias_obs[m["name"]]; o[0] += (r["pick"] == bt); o[1] += base_fav if fav == bt else 1 - base_fav; o[2] += 1
    for m in family:
        if m.get("bias_team"):
            k, e, n = bias_obs[m["name"]]
            s_hat = max(0.0, min(1.0, (k - e) / max(n - e, 1e-9))) if n else 0.4
            m["bias_strength"] = round((n * s_hat + 10 * 0.4) / (n + 10), 3); m["bias_observed"] = [n, k, round(e, 2)]
    for m in family:
        for b in ("tossup", "close", "other"):
            n, d = counts[m["name"]][b]; prior = m.get("prior_dog_rate", m["dog_rate"])[b]
            m.setdefault("prior_dog_rate", dict(m["dog_rate"]))            # keep the score-derived prior fixed
            m["dog_rate"][b] = round((d + prior * PRIOR_N[b]) / (n + PRIOR_N[b]), 3)
            m.setdefault("observed", {})[b] = [n, d]
    json.dump(family, open(a.family, "w"), indent=1)
    print("family.json updated: posterior = (observed dogs + prior x N_band) / (observed picks + N_band), N =", PRIOR_N)

if __name__ == "__main__":
    main()
