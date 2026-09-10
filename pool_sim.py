#!/usr/bin/env python3
"""Family-pool Monte Carlo used in CRITIQUE.md section 3, plus the late-season variance test.

    python3 pool_sim.py [--games-file games.csv] [--members 6] [--seasons 20000]

Assumptions (all of them are attackable; change them and re-run):
  * Game favorite probabilities are resampled from real 2015-2025 no-vig lines (272 per season).
  * Outcomes are independent Bernoulli(p_fav). Members' picks are conditionally independent
    given the game: each 'other' takes the dog with probability DEV in games where the
    favorite is below CLOSE, and the favorite otherwise. No tiebreaker; ties split evenly.
  * The user's 'skill' policy models a real but small edge: in close games the user's signal
    identifies the actual winner with probability EDGE, otherwise it is pure noise.
Policies for the user:
  fav          always the favorite
  random_dog   the dog with probability DEV in close games (skill-free contrarianism)
  skilled_dog  take the dog in close games when a noisy signal says so
  late_var     favorite through week 13; from week 14, take dogs in close games when trailing
               the leader by more than the remaining-games threshold
  dog_below    take the dog whenever the favorite is below --user-thresh (near coin flips only)
Run with --crossover to print P(first) for dog_below thresholds against a sweep of others' DEV.
"""
import argparse, csv, io, random, urllib.request

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def american_to_prob(ml):
    ml = float(ml); return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def load_pf(path):
    rows = list(csv.DictReader(open(path, newline=""))) if path else \
           list(csv.DictReader(io.StringIO(urllib.request.urlopen(URL).read().decode())))
    pf = []
    for r in rows:
        if r["game_type"] == "REG" and r["result"] not in ("", "0") and r["away_moneyline"] and \
           r["home_moneyline"] and 2015 <= int(r["season"]) <= 2025:
            pa, ph = american_to_prob(r["away_moneyline"]), american_to_prob(r["home_moneyline"])
            pf.append(max(pa, ph) / (pa + ph))
    return pf

def season(pf, policy, members, dev, close, edge, gap_per_game, rng):
    games = rng.sample(pf, 272)              # 17 'weeks' of 16 games
    s = [0] * members
    for gi, p in enumerate(games):
        week = gi // 16 + 1; remaining = 272 - gi
        fav_wins = rng.random() < p
        is_close = p < close
        # others
        for m in range(1, members):
            pick_fav = not (is_close and rng.random() < dev)
            s[m] += (pick_fav == fav_wins)
        # user
        if policy == "fav": pick_fav = True
        elif policy == "random_dog": pick_fav = not (is_close and rng.random() < dev)
        elif policy == "skilled_dog":
            if is_close:
                signal_fav = fav_wins if rng.random() < edge else (rng.random() < p)
                pick_fav = signal_fav
            else: pick_fav = True
        elif policy == "dog_below":
            pick_fav = p >= edge          # edge reused as the threshold for this policy
        elif policy == "late_var":
            leader = max(s[1:]); behind = leader - s[0]
            pick_fav = not (week >= 14 and is_close and behind > gap_per_game * remaining)
        s[0] += (pick_fav == fav_wins)
    best = max(s); top = [i for i, x in enumerate(s) if x == best]
    return (1 / len(top)) if 0 in top else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-file"); ap.add_argument("--members", type=int, default=6)
    ap.add_argument("--seasons", type=int, default=20000); ap.add_argument("--close", type=float, default=0.62)
    ap.add_argument("--gap-per-game", type=float, default=0.05, help="late_var trigger: deficit > this x games left")
    ap.add_argument("--crossover", action="store_true")
    a = ap.parse_args()
    pf = load_pf(a.games_file); rng = random.Random(7)
    base = 1 / a.members
    if a.crossover:
        ths = [(0.0, "never"), (0.505, "<50.5%"), (0.52, "<52%"), (0.55, "<55%"), (0.58, "<58%")]
        print("avg dog picks/season by threshold:",
              {l: round(sum(p < t for p in pf) / len(pf) * 272, 1) for t, l in ths if t})
        print(f"\n{'others dev':>10} | " + " | ".join(f"{l:>8}" for _, l in ths))
        for dev in (0.0, 0.01, 0.02, 0.05, 0.10, 0.15, 0.30):
            row = [sum(season(pf, "dog_below", a.members, dev, a.close, t, 0, rng) for _ in range(a.seasons)) / a.seasons for t, _ in ths]
            print(f"{dev:10.2f} | " + " | ".join(f"{v:8.3f}" for v in row))
        return
    print(f"baseline P(first) = {base:.3f}; {a.members} members; {a.seasons} seasons each cell\n")
    print(f"{'user policy':14} {'others dev':>10} {'edge':>5}  P(first)")
    for dev in (0.15, 0.30, 0.50):
        for policy, edge in (("fav", 0), ("random_dog", 0), ("skilled_dog", 0.10), ("skilled_dog", 0.25), ("late_var", 0)):
            w = sum(season(pf, policy, a.members, dev, a.close, edge, a.gap_per_game, rng) for _ in range(a.seasons)) / a.seasons
            print(f"{policy:14} {dev:10.2f} {edge:5.2f}  {w:.3f}")
        print()

if __name__ == "__main__":
    main()
