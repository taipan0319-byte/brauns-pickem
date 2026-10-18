#!/usr/bin/env python3
"""Regression test for D30 (ChatGPT Block 7, test 1): three 60% favorites remain, Nolan leads by three, every
opponent on chalk. Chalk and every one- or two-dog combination give P(first) = 0; all three dogs give exactly
0.5 * 0.4^3 = 3.2% (ties split). A coordinate search from chalk cannot cross the flat region; the joint search
must. Run: python3 test_engine_b_d30.py ; exit 1 on failure."""
import sys, numpy as np, engine_b as eb
family = [dict(m, dog_rate={b: 0 for b in m["dog_rate"]}, bias_strength=0) for m in eb.DEFAULT_FAMILY]
games = [dict(home_team="H", away_team="A", home_moneyline="-150", away_moneyline="150", spread_line="") for _ in range(3)]
st = {m["name"]: -10 for m in family}; st.update(Ryan=0, Nolan=3)
base, final, deltas, user_fav, *_ = eb.evaluate(games, family, st, "Ryan", 100000, 7, np.ones(3, dtype=bool))
exact = 0.5 * 0.4 ** 3
print(f"chalk P(first) {base:.4f}; engine final {final:.4f}; exact optimum {exact:.4f}; picks all dogs: {not user_fav.any()}")
ok = (not user_fav.any()) and abs(final - exact) < 0.004
print("PASS: joint search reaches the three-dog optimum" if ok else "FAIL: D30 property violated"); sys.exit(0 if ok else 1)
