# Response to the revised architecture (delta handoff of September 9, 2026)

Labels: **FACT** = computed here from nflverse data, reproducible with the named script.
**ASSUMPTION** = a modeling choice with no data behind it yet. **HYPOTHESIS** = testable, untested.

Short version: the revised thesis is right. Engine A should be the market and nothing else,
and the numbers below make that stronger than the delta handoff states. On Engine B,
ChatGPT's disagreement with my first game-theory claim is correct, I have proven the
counterexample exactly, and the practical consequence is smaller than either of us implied:
under any plausible family model the Week 1 stakes of a coin-flip dog pick are under one
percentage point of P(first) either way.

## 1. Market calibration, reproduced independently (`backtest_market.py`)

Regular season 2007–2025, both moneylines present, ties dropped: **4,842 games**. (My first
critique quoted 5,051; that run also included 2006's 209 games with moneylines. Both are FACT;
the script now defaults to 2007+.)

| Metric | Value |
|---|---|
| Spread-favorite straight-up accuracy | 66.85% |
| No-vig moneyline Brier | 0.2094 |
| Log loss | 0.6057 |

| Bucket | n | Mean predicted | Actual | Error |
|---|---|---|---|---|
| 50–55 | 620 | 0.526 | 0.534 | +0.008 |
| 55–60 | 842 | 0.575 | 0.564 | −0.010 |
| 60–65 | 890 | 0.625 | 0.601 | −0.024 |
| 65–70 | 719 | 0.676 | 0.680 | +0.004 |
| 70–75 | 693 | 0.726 | 0.736 | +0.010 |
| 75–80 | 527 | 0.774 | 0.787 | +0.013 |
| 80–85 | 307 | 0.822 | 0.840 | +0.019 |
| 85–90 | 199 | 0.872 | 0.905 | +0.032 |
| 90+ | 45 | 0.915 | 0.956 | +0.040 |

The only structure is the familiar favorite-longshot bias: big favorites win slightly *more*
than priced. The 60–65 bucket's −2.4 points is 1.5 standard errors; not exploitable. Nothing
here supports a dog-hunting model.

## 2. The residual challenger, tested (`engine_a.py`)

This is the ablation the delta handoff asked for (sections 16–17), run on the features
available in games.csv. Expanding window, train on seasons before t, test on t, for
t = 2014…2025. All features are computable before kickoff.

| Model | Log loss | Brier | Accuracy | Games where it flips the market pick | Accuracy on those flips |
|---|---|---|---|---|---|
| Raw no-vig market (production) | 0.6116 | — | 66.3% | — | — |
| M0 fitted market | 0.6115 | 0.2119 | 66.4% | 43 | 53.5% |
| M1 + pre-game Elo | 0.6117 | 0.2120 | 66.3% | 45 | 51.1% |
| M2 + rest differential | 0.6124 | 0.2123 | 66.2% | 49 | 46.9% |
| M3 + divisional flag | 0.6124 | 0.2123 | 66.4% | 67 | 52.2% |
| M4 + cold / wind | 0.6128 | 0.2125 | 66.2% | 86 | 48.8% |
| M5 + QB change | 0.6129 | 0.2125 | 66.4% | 89 | 51.7% |

**FACT:** every block makes out-of-sample log loss worse. No block beats the previous one in a
majority of test seasons. The fitted market slope is 1.04 with the market alone and 0.98 with
everything added, meaning the market needs no correction. The games where a challenger
disagrees with the market are decided at coin-flip rates.

A subtlety worth recording: rest, division, and cold all have coefficients with the *same
sign in 100% of test seasons*, yet they never improve prediction. That is what a real but
tiny effect looks like when the market already prices most of it: the coefficient is
estimable, the residual is smaller than the estimation noise. This is the right mental model
for every folklore hypothesis in the original handoff.

Not tested here because games.csv lacks them: rolling EPA, QB EPA, injuries, OL/DL. The
literature says the same thing happens to EPA once the market is in the model. HYPOTHESIS,
strong prior, and it is the next thing to test in the offseason with play-by-play data.
Multiple-testing note: six blocks were tried; zero survived; there is nothing to correct for.

**Decision: Engine A production = raw no-vig consensus moneyline. The challenger is retained as
code and as a test harness, not as a probability source.**

## 3. Expected score vs P(first): resolved (`pool_theory.py` part 1)

ChatGPT's section 7 counterexample is correct and I was wrong to say dogs "only add variance."
The exact statement, N members, ties split evenly, all opponents on the favorite:

- **One deviation** onto a dog with win probability q: P(first) = q, versus 1/N on chalk.
  A single deviation helps whenever q > 1/N. For N = 6 that is q > 0.167, which is why the
  49% example is not close: it raises P(first) from 0.167 to 0.49.
- **k deviations**, each a q-dog: P(first) = P(Binomial(k, q) > k/2) + P(tie)/N.

| q | k=1 | k=2 | k=3 | k=5 | k=9 | k=15 |
|---|---|---|---|---|---|---|
| 0.49 | 0.490 | 0.323 | 0.485 | 0.481 | 0.475 | 0.469 |
| 0.45 | 0.450 | 0.285 | 0.425 | 0.407 | 0.379 | 0.346 |
| 0.40 | 0.400 | 0.240 | 0.352 | 0.317 | 0.267 | 0.213 |

Three consequences. Against a perfectly correlated field, one deviation in the closest game is
optimal; each extra deviation adds negative drift. An even number of deviations is bad because
a split result ties you back into the pack. And the value of deviating is set by q, not by the
market's mispricing: mispricing is irrelevant to Engine B.

The general form, for any opponent behavior: you finish first iff your margin over the best
opponent is positive. Your margin only moves on games where your pick differs from theirs. A
deviation adds drift −(2p − 1) and variance to that margin. Whether that helps depends on where
the max of the opponents' scores sits relative to yours, which depends on their noise. That is
not solvable in closed form for realistic opponents; it is what the simulator is for.

## 4. Reproduction of ChatGPT's grid (`pool_theory.py` part 2)

Opponents pick the favorite with probability x in every game, independently; user takes the
k closest-to-50% dogs of the season; N = 6; 20,000 seasons per cell.

| x | k=0 | k=1 | k=2 | k=4 | k=8 | k=16 |
|---|---|---|---|---|---|---|
| 0.995 | 0.134 | 0.291 | 0.290 | 0.337 | 0.370 | 0.364 |
| 0.99 | 0.183 | 0.273 | 0.301 | 0.336 | 0.362 | 0.356 |
| 0.97 | 0.405 | 0.411 | 0.416 | 0.432 | 0.427 | 0.401 |
| 0.95 | 0.581 | 0.567 | 0.557 | 0.552 | 0.535 | 0.488 |
| 0.90 | 0.822 | 0.816 | 0.807 | 0.798 | 0.771 | 0.710 |

ChatGPT's table (99%: 13 → 24 → 29; 97%: 27 → 32 → 32; 95%: 40 → 40 → 38; 90%: 63 → 58 → 52)
has the same shape: dogs help a lot at 99%, are neutral at 97%, and hurt from 95% down. Its
levels are lower than mine at every x. Without its code I can name the likely causes but not
confirm them: (a) a different favorite-probability distribution (mine resamples 2015–2025
real lines; a flatter distribution lowers chalk's value); (b) tie handling (if ties count as
losses rather than split, chalk's numbers drop sharply at high x); (c) whether opponents'
deviations land on heavy favorites (in this grid they do, which is expensive for them and
inflates chalk's value at 90%). None of these change the conclusion. **The grid is
qualitatively valid and its stated significance holds: early selective contrarianism can raise
P(first).** Its assumptions are the same as mine and equally unmeasured.

## 5. The assumption that matters: correlated deviations (`pool_theory.py` part 3)

Real people do not deviate uniformly; they deviate in the same games, the ones everyone can
see are toss-ups. Same overall opponent dog rate r in close games, spread uniformly versus
concentrated in shared "buzz" toss-ups. User policy: dog when favorite < 52%.

| r | Deviations | Chalk | Dog under 52% |
|---|---|---|---|
| 0.05 | uniform | 0.110 | 0.285 |
| 0.05 | concentrated | 0.238 | 0.326 |
| 0.15 | uniform | 0.224 | 0.278 |
| 0.15 | concentrated | 0.288 | 0.299 |
| 0.30 | uniform | 0.380 | 0.375 |
| 0.30 | concentrated | 0.392 | 0.367 |

Concentration shrinks the dog policy's advantage, as expected, but the policy is still never
materially worse than chalk. **The decision variable is r, the family's dog rate in close
games, and nobody has measured it.** This is why `pool_picks.csv` matters more than any
football feature.

## 6. Is "mirror until Week 13" defensible? No. Replacement rule.

Retracted. The replacement is not a fixed rule but Engine B's per-game comparison of P(first)
under each pick, using the current opponent model and standings. Until family data exists,
the default embedded in Engine B is: **favorite in every game with a no-vig favorite of 52% or
more; below 52%, take whichever side Engine B scores higher.** The 52% line comes from the
crossover tables in CRITIQUE.md addendum 2 and section 5 here; it is where the dog policy is
never worse than chalk across every family assumption tried. HYPOTHESIS: it will move up a
point or two once the family model is fitted, if the family turns out chalk-heavy, and down to
"never" if they deviate at 30% or more in toss-ups.

## 7. Engine B for Week 1 (`engine_b.py`)

Monte Carlo over the remaining 272 games with common random numbers, opponents' picks drawn
from `family.json`, standings from `standings.json` when it exists. For each current-week game
it reports the change in P(first) from taking the dog, evaluated jointly across the week.

Everything in `family.json` is an **ASSUMPTION** I wrote from the handoff's anecdotes (dog rates
by band per member, Bears/Packers lean for the named members). The `--fit` flag replaces those
priors with shrunken estimates from `pool_picks.csv` once it has rows.

Week 1, three family scenarios (P(first) in points, for the dog):

| Game | P(fav) | Chalk-heavy family | Middle | Handoff-anecdote family |
|---|---|---|---|---|
| BUF@HOU | BUF 51.7% | +0.8 | +0.4 | −0.3 |
| NYJ@TEN | TEN 52.6% | +0.6 | +0.0 | −0.4 |
| GB@MIN | MIN 52.2% | +0.9 | −0.2 | −0.2 |
| NE@SEA | SEA 60.0% | −0.9 | −1.3 | −1.4 |
| every other game | ≥ 58% | negative | negative | negative |

Reading: the stakes are under one point of P(first) per game in every scenario, which is why
this decision does not deserve the agonizing the original handoff gave to NE@SEA. Averaged
over the scenarios, HOU is a small positive, NYJ is zero, GB is positive only if the family is
chalk-heavy and negative once Sue and the daughter's Packers lean is in the model, because
that lean makes a GB pick *correlated* with them rather than differentiated.

**Week 1 recommendation: SEA, and the favorite everywhere except BUF@HOU, where HOU is a
marginal take if the line is still under 52% at the Sunday deadline.** If BUF drifts to 53%+
the answer flips back to BUF. Re-run before the deadline.

## 8. Disagreements with the delta handoff, flagged as requested

1. **Section 5, Engine A challenger feature list.** Fine to keep as research, but the ablation
   above already answers the games.csv part of it, negatively. Do not let "still investigating"
   become a reason to nudge probabilities by hand.
2. **Section 12, "Football disagreement."** With the challenger failing, this concept has no
   input. Retire it fully for 2026 rather than keeping a slot for it.
3. **Section 13, "when leading, correlate; when trailing, seek variance."** Directionally
   right but the simple version of the trailing rule *lowered* P(first) in my earlier test
   (CRITIQUE.md addendum 1). Engine B evaluates it numerically rather than applying it as a
   heuristic, which is what section 14 asks for anyway. Do not hard-code the intuition.
4. **Tie handling is not specified and it matters.** If CBS breaks season ties by a tiebreaker
   or a coin flip, "ties split" is the right objective. If the family treats co-leaders as
   co-champions, the objective becomes P(at least tied for first), which favors chalk more
   strongly, because tying the pack is a win. Ryan needs to say which it is.
5. **Pool size.** Six members is assumed throughout. The value of chalk rises with N when
   opponents are noisy and the value of a single deviation falls as 1/N. Confirm N.
6. **Opta and "expert" columns.** Harmless to log; useless as inputs. I would not spend time
   collecting them.

## 9. Files on the branch

| File | Role |
|---|---|
| `v01_picks.py` | Engine A production: no-vig favorite, append-only log |
| `backtest_market.py` | Calibration reproduction |
| `engine_a.py` | Residual challenger and ablation harness |
| `pool_sim.py` | First simulations, crossover table |
| `pool_theory.py` | Exact math, ChatGPT grid reproduction, correlation stress test |
| `engine_b.py`, `family.json` | Pool optimizer and editable opponent model; `--fit` learns from `pool_picks.csv` |
| `CRITIQUE.md` | Original critique with two addenda |

Audit-log discipline: `predictions_log.csv` and `engine_b_log.csv` are append-only with UTC
timestamps; re-runs add rows, never edit them. `pool_picks.csv` columns:
`season, week, game_id, member, pick, entered_at`.
