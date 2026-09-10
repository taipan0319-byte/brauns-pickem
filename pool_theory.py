#!/usr/bin/env python3
"""Expected score vs P(finish first): exact math and vectorized simulations.

    python3 pool_theory.py [--games-file games.csv] [--seasons 20000]

Part 1  Exact results with perfectly correlated opponents (all N-1 opponents pick chalk).
Part 2  Reproduction of ChatGPT's grid: opponents pick the favorite with prob x in EVERY game,
        user takes the k closest-to-50% dogs of the season.
Part 3  Correlated-deviation stress test: the same overall opponent dog rate, spread uniformly
        over close games vs concentrated in the same 'buzz' toss-ups.
"""
import argparse, csv, io, math, urllib.request
import numpy as np

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
    return np.array(pf)

def p_first(user, others):
    """user: (S,) scores; others: (S, N-1). Ties split evenly."""
    best = np.maximum(user, others.max(1))
    n_top = (others == best[:, None]).sum(1) + (user == best)
    return np.where(user == best, 1.0 / n_top, 0.0).mean()

def part1(N=6):
    print("PART 1: exact results, N=%d, all opponents on chalk in every game, ties split\n" % N)
    print("One deviation on a dog with win prob q: P(first) = q  vs  1/N = %.3f on chalk." % (1 / N))
    print("So a single deviation helps iff q > 1/N. That is the counterexample in ChatGPT's section 7, proven.\n")
    print("k deviations, each a q-dog, all opponents on chalk: P(first) = P(Bin(k,q) > k/2) + P(tie)/N")
    print(f"{'q':>5} " + " ".join(f"k={k:<2}" for k in (1, 2, 3, 5, 9, 15)))
    for q in (0.49, 0.47, 0.45, 0.40, 0.35):
        row = []
        for k in (1, 2, 3, 5, 9, 15):
            pw = sum(math.comb(k, j) * q**j * (1 - q)**(k - j) for j in range(k // 2 + 1, k + 1))
            pt = math.comb(k, k // 2) * q**(k // 2) * (1 - q)**(k // 2) if k % 2 == 0 else 0
            row.append(pw + pt / N)
        print(f"{q:5.2f} " + " ".join(f"{v:4.3f}" for v in row))
    print("\nReading: with a perfectly correlated field, ONE deviation in the closest game is optimal;")
    print("more deviations only add negative drift. Any noise in the field changes this (parts 2-3).\n")

def simulate(pf, S, N, rng, user_pick_fav, others_pick_fav):
    """user_pick_fav: (S,G) bool; others_pick_fav: (S,G,N-1) bool. Returns P(first)."""
    G = user_pick_fav.shape[1]
    fav_wins = rng.random((S, G)) < pf[None, :]
    user = (user_pick_fav == fav_wins).sum(1)
    others = (others_pick_fav == fav_wins[:, :, None]).sum(1)
    return p_first(user, others)

def part2(pf_all, S, N, rng):
    print("PART 2: ChatGPT grid. Opponents pick the favorite with prob x in EVERY game (uniform, independent);")
    print("user takes the k closest-to-50%% dogs. N=%d, %d seasons per cell.\n" % (N, S))
    G = 272
    pf = np.sort(rng.choice(pf_all, size=G, replace=True))  # fixed season of lines, sorted closest first
    ks = (0, 1, 2, 4, 8, 16)
    print(f"{'x':>5} | " + " | ".join(f"k={k:<3}" for k in ks))
    for x in (0.995, 0.99, 0.97, 0.95, 0.90, 0.80):
        others = rng.random((S, G, N - 1)) < x
        row = []
        for k in ks:
            user = np.ones((S, G), bool); user[:, :k] = False
            row.append(simulate(pf, S, N, rng, user, others))
        print(f"{x:5.3f} | " + " | ".join(f"{v:5.3f}" for v in row))
    print("\nNote: the user's k dogs are the season's closest lines (mild foresight); opponents' deviations land")
    print("on heavy favorites too, which is expensive for them and inflates the chalk value at low x.\n")

def part3(pf_all, S, N, rng):
    print("PART 3: correlated vs uniform opponent deviations. Opponents only deviate in close games (fav<62%%),")
    print("overall dog rate r in those games held fixed. 'Concentrated': deviations pile into the same buzz")
    print("toss-ups (fav<55%%). User policy: dog when fav < 52%%. N=%d, %d seasons.\n" % (N, S))
    G = 272
    pf = rng.choice(pf_all, size=G, replace=True)
    close = pf < 0.62; tossup = pf < 0.55
    user_fav = np.broadcast_to(pf >= 0.52, (S, G))
    user_chalk = np.ones((S, G), bool)
    print(f"{'r':>5} {'mode':>13} {'chalk':>7} {'dog<52%':>8}")
    for r in (0.05, 0.15, 0.30):
        # uniform
        dev = (rng.random((S, G, N - 1)) < r) & close[None, :, None]
        others_u = ~dev
        # concentrated: buzz flag per game per season; in buzz toss-ups opponents deviate at r_hi, elsewhere r_lo
        b = 0.25
        n_close, n_toss = close.sum(), tossup.sum()
        r_hi = min(0.85, r * n_close / (b * n_toss))       # keep overall rate ~r
        r_lo = max(0.0, (r * n_close - r_hi * b * n_toss) / (n_close - b * n_toss))
        buzz = (rng.random((S, G)) < b) & tossup[None, :]
        rate = np.where(buzz, r_hi, r_lo) * close[None, :]
        dev_c = rng.random((S, G, N - 1)) < rate[:, :, None]
        others_c = ~dev_c
        for mode, oth in (("uniform", others_u), ("concentrated", others_c)):
            pc = simulate(pf, S, N, rng, user_chalk, oth)
            pd = simulate(pf, S, N, rng, user_fav, oth)
            print(f"{r:5.2f} {mode:>13} {pc:7.3f} {pd:8.3f}")
    print()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-file"); ap.add_argument("--seasons", type=int, default=20000)
    ap.add_argument("--members", type=int, default=6)
    a = ap.parse_args()
    rng = np.random.default_rng(3)
    pf = load_pf(a.games_file)
    part1(a.members); part2(pf, a.seasons, a.members, rng); part3(pf, a.seasons, a.members, rng)

if __name__ == "__main__":
    main()
