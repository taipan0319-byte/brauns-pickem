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
USER_DOG_THRESHOLD = 0.52   # default future-week policy for the user
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

def evaluate(games, family, standings, user, sims, seed, this_week_mask):
    """Returns (base P(first), final P(first), deltas dict, user_fav picks, P_opp, noise estimate)."""
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
    half = sims // 2
    def p_first(uf, sl=slice(None)):
        us = user_pts + (uf[None, :] == fav_wins[sl]).sum(1); osc = opp_scores[sl]
        best = np.maximum(us, osc.max(1)); ntop = (osc == best[:, None]).sum(1) + (us == best)
        return np.where(us == best, 1.0 / ntop, 0.0).mean()
    user_fav = pfav >= USER_DOG_THRESHOLD
    base = p_first(user_fav)
    idx = np.where(this_week_mask)[0]; deltas, noise = {}, {}
    for _ in range(2):
        for i in idx:
            u1 = user_fav.copy(); u1[i] = True; u0 = user_fav.copy(); u0[i] = False
            d = p_first(u0) - p_first(u1)
            d1 = p_first(u0, slice(0, half)) - p_first(u1, slice(0, half))
            d2 = p_first(u0, slice(half, None)) - p_first(u1, slice(half, None))
            deltas[i] = d; noise[i] = abs(d1 - d2) / 2 + 1e-4
            user_fav[i] = d <= 0
    return base, p_first(user_fav), deltas, user_fav, P_opp, pfav, fav_team, fav_home, noise

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
    games = [g for g in load_games(a.games_file) if int(g["season"]) == a.season and g["game_type"] == "REG"
             and int(g["week"]) >= a.week and g["result"] == ""]
    games.sort(key=lambda g: (int(g["week"]), g["gameday"]))
    mask = np.array([int(g["week"]) == a.week for g in games]); idx = np.where(mask)[0]
    seed = a.season * 100 + a.week
    scenarios = [("as-modeled", family)]
    if a.screen: scenarios += [("chalkier x0.5", scale_family(family, 0.5)), ("wilder x2", scale_family(family, 2.0))]
    res = {name: evaluate(games, fam, standings, a.user, a.sims, seed, mask) for name, fam in scenarios}
    base, final, deltas, user_fav, P_opp, pfav, fav_team, fav_home, noise = res["as-modeled"]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"ENGINE B  {a.season} week {a.week}  user={a.user}  N={len(family)+1}  sims={a.sims}  tie rule={TIE_RULE}")
    print(f"opponents: {', '.join(m['name'] for m in family)}   standings: {standings or 'none (week 1)'}")
    print(f"P(first) if all favorites this week: {base:.3f}   with recommended picks: {final:.3f}\n")
    hdr = f"{'game':10} {'market fav':>10} {'P(fav)':>7} {'family on fav':>13} {'dP(first) if dog':>16}  {'pick':5}"
    if a.screen: hdr += "  confidence"
    print(hdr); out = []
    for i in idx:
        g = games[i]; dog = g["away_team"] if fav_home[i] else g["home_team"]
        d = deltas[i]; conf = ""
        if a.screen:
            ds = [res[n][2][i] for n, _ in scenarios]; agree = all(x > 0 for x in ds) or all(x <= 0 for x in ds)
            if not agree or abs(d) <= noise[i]: conf = "LOW"; pick = fav_team[i]
            elif abs(d) > 3 * noise[i]: conf = "HIGH"; pick = dog if d > 0 else fav_team[i]
            else: conf = "MEDIUM"; pick = dog if d > 0 else fav_team[i]
        else:
            pick = dog if user_fav[i] == False else fav_team[i]
        line = f"{g['away_team']+'@'+g['home_team']:10} {fav_team[i]:>10} {pfav[i]:7.3f} {P_opp[i].mean():13.2f} {d:+16.4f}  {pick:5}"
        if a.screen: line += f"  {conf}"
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
        if not g or r["member"] not in counts: continue
        p = home_prob(g); pf = max(p, 1 - p); fav = g["home_team"] if p >= 0.5 else g["away_team"]
        c = counts[r["member"]][band(pf)]; c[0] += 1; c[1] += (r["pick"] != fav)
    prior_n = 10.0
    for m in family:
        for b in ("tossup", "close", "other"):
            n, d = counts[m["name"]][b]; prior = m["dog_rate"][b]
            m["dog_rate"][b] = round((d + prior * prior_n) / (n + prior_n), 3)
    json.dump(family, open(a.family, "w"), indent=1)
    print("family.json updated with shrinkage (prior weight = 10 picks per band)")

if __name__ == "__main__":
    main()
