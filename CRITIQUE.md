# Critique of the ChatGPT "NFL Family Pool Prediction Engine" handoff

Reviewed September 9, 2026. Labels used throughout: **FACT** (verified today against a source or
computed from data), **HYPOTHESIS** (plausible, untested), **ASSUMPTION** (a judgment call).

## 0. Bottom line

1. **The handoff spends 90% of its length on the part of the problem that has ~0% of the edge.**
   The betting market's no-vig moneyline is already an almost perfectly calibrated win
   probability (FACT, section 2). No public model beats the closing line at straight-up
   accuracy by a margin you could detect in one season. Building "Data Golf for the NFL" is a
   fine hobby, but it will not decide this pool.
2. **The pool game theory is backwards.** In a 1-point-per-correct-pick pool, every underdog
   pick has an expected cost of (P(fav) − P(dog)) picks. "Differentiation" is not a benefit;
   it is variance you buy at that price. Variance is worth buying only when you are behind late
   in the season. Weekly "selective contrarianism" from Week 1 is the same mistake the handoff
   accuses Nolan of making, with more spreadsheet.
3. **Most of the adjustment layers double-count the market.** QB, injuries, weather, rest,
   travel, home field, line movement, and "independent models" like Opta are all already inside
   the closing price. Adding them again as point adjustments is the single most common way
   amateur models get worse than the market.
4. **The NE@SEA analysis is directionally fine but decorative.** It moved the number 3 points
   and changed nothing. The game is **tonight** (Wednesday, 8:20 pm ET), which the handoff
   never states. Pick Seattle.
5. **v0.1 is: pick every no-vig favorite, home team in a dead heat, log everything.** It is
   implemented in `v01_picks.py` and runs in five seconds. Everything else is offseason work.

## 1. Fact check of the handoff's claims (all verified today)

| Claim in handoff | Status |
|---|---|
| Seattle beat New England in Super Bowl LX | FACT, 29–13, Feb 8 2026 |
| A.J. Brown added to New England | FACT, traded from PHI for a 2028 1st + 2027 5th |
| Romeo Doubs added | FACT, signed as UFA March 12 2026, WR2 behind Brown |
| TreVeyon Henderson ruled out | FACT, ankle, missed all three practices; Stevenson starts |
| Market movement toward New England | FACT, opened SEA −4.5 in May, now −3 / −3.5 depending on book; ML roughly SEA −180/−185, NE +150/+160 |
| Opta gives Seattle 61% | FACT |
| Seattle secondary concerns | PARTLY. Riq Woolen (to PHI) and Coby Bryant (to CHI) left in the offseason; Ty Okada out; a practice-squad DB was activated. I could not confirm the status of Witherspoon or Love for tonight; treat as unverified. |
| Patriots withheld starters in preseason | Not verified by me; plausible, low value either way |
| Joint-practice reporting favorable to NE offense | Not verifiable and not quantifiable. Should carry zero weight (section 10). |
| Game date | The handoff says "Week 1" without a kickoff time. **The game is Wednesday Sept 9, 8:20 pm ET.** The Thursday slot is SF@LA (in Melbourne, Friday local). Picks lock tonight. |

Consensus no-vig probability from the numbers above: SEA 60–62%, NE 38–40%. The handoff's
"market low-60s" is right.

## 2. The core statistical problem: the prior is already the answer

I pulled nflverse's `games.csv` (7,548 games, 1999–2026) and evaluated the no-vig moneyline on
every regular-season game with a moneyline from 2007 through 2025 (5,051 games, ties dropped).

| Metric | Value |
|---|---|
| Spread favorite straight-up accuracy | 66.5% |
| No-vig moneyline Brier score | 0.211 |
| Log loss | 0.609 |
| Std error of season accuracy (272 games) | ±2.9 points |

Calibration of the no-vig favorite probability (bucket → actual favorite win rate):

| Market favorite | n | Actually won |
|---|---|---|
| 50–55% | 642 | 53.1% |
| 55–60% | 876 | 56.3% |
| 60–65% | 930 | 59.5% |
| 65–70% | 751 | 67.4% |
| 70–75% | 718 | 73.4% |
| 75–80% | 546 | 78.8% |
| 80–85% | 327 | 82.9% |
| 85–90% | 213 | 89.7% |

That is as calibrated as any public model gets. What it means for the design:

- **FACT:** The 60/40 games the handoff wants to attack are exactly where favorites win ~59.5%.
  The market is not systematically overrating favorites in that band.
- **FACT:** With a standard error of ±2.9 points per season, you cannot tell a 66% model from
  a 68% model in a season. You cannot tell it in three seasons. Nobody in this pool, Sue
  included, has a measurable skill sample (section 13).
- **HYPOTHESIS (strong, literature-backed):** A residual model on top of the closing line will
  find no feature with reliable out-of-sample value. nfelo, FiveThirtyEight Elo and academic
  studies all land at or slightly below Vegas straight-up. The right test is explicit: regress
  game outcome on logit(market probability) plus your feature, chronologically out of sample,
  and keep the feature only if its coefficient is stable and nonzero. Expect almost all to fail.
- **ASSUMPTION:** The realistic ceiling for an independent model is +0 to +1 correct picks per
  season over pure favorites. Design the project around that, not around "Data Golf".

The handoff's stated goal, "distinguish carefully between predicting games, identifying
mispriced dogs, and optimizing against the pool," is right. Its allocation of effort is wrong:
item 1 is solved for free, item 2 is nearly impossible, and item 3 is where the handoff is
actually mistaken.

## 3. The pool game theory is backwards

Format check first (**ASSUMPTION** until you confirm): CBS straight-up pick'em, 1 point per
correct pick, season-long cumulative standings, a Monday-night-total tiebreaker, ~6 members.
If any of that is wrong (weekly prizes, confidence points), the strategy below changes and you
should tell me.

Under that format:

- Expected points from picking the favorite: P(fav). From picking the dog: 1 − P(fav). The
  dog costs you 2·P(fav) − 1 expected points. A 60/40 dog costs 0.20 picks; a 55/45 dog costs
  0.10.
- "Few pool members pick the dog" does not change that cost. It changes the *variance* of your
  standing relative to the field. Variance is good when you are behind and bad when you are
  ahead. It has no value in Week 1 when everyone is tied.
- So the "family pick distribution" input belongs in a **standings-aware end-of-season policy**,
  not in a weekly Upset Radar.

I simulated a 6-person season (272 games, favorite probabilities resampled from 2015–2025 real
lines, 20,000 seasons). You pick every favorite; the other five pick the dog at some rate in
games where the favorite is under 62%.

| Others' dog-pick rate in close games | P(you finish first) | Baseline |
|---|---|---|
| 15% | 22% | 16.7% |
| 30% | 39% | 16.7% |
| 50% | 56% | 16.7% |
| 30%, and you also pick random dogs 30% | 16% | 16.7% |

**FACT (within the sim's assumptions):** every skill-free dog pick you make gives back edge.
The best line in the handoff is "never change a pick because we need an upset." It should be
the whole strategy for weeks 1–14, not a footnote.

**What the family layer should actually be** (section 14): a Monte Carlo of the remaining
schedule, run weekly from ~Week 13 on, that takes current standings and each member's modeled
pick tendency and asks: "given I am X points back with N games left, which dog picks raise my
probability of finishing first?" When you lead, it will tell you to mirror the field. When you
trail, it will tell you which uncorrelated dogs to take. That is the only place contrarianism
has positive value.

## 4. Double-counting and hidden assumptions

1. **Market prior + adjustments for things in the market.** QB, injuries (the Henderson news
   was priced before the handoff was written), weather, rest, travel, home field, coaching:
   all in the close. Adjust only with a *residual* that has been shown to survive the market.
2. **Line movement as an upset factor.** Movement is already incorporated in the *current*
   line. Using "moved toward NE" and the current NE price both is counting the same
   information twice. Movement has predictive value only versus the *opener*, and the fix is
   simply to use the latest line, ideally the close.
3. **Opta as an "independent check."** Opta's model is not independent of the market; it is
   built on the same team-strength inputs and its output tracks Vegas closely. Agreement between
   Opta and Vegas is not two votes. Disagreement between your model and both is one vote
   against you.
4. **"If we cannot explain the disagreement, confidence should fall."** Correct, and the
   operational meaning is: shrink toward the market. Write it as a formula (section 12), not a
   feeling.
5. **±3 point preseason cap.** Unsupported. It is a number chosen to feel careful. The
   evidence base for joint-practice reporting is zero and cannot be backtested. Cap at 0.
6. **"Sue's success is not luck."** With ~6 people over a few seasons, one of them being
   ahead is guaranteed. Section 2's standard error says her edge is undetectable. Track her
   picks anyway (cheap), but the prior should be "noise."
7. **The handoff's own narrative bias.** The NE@SEA writeup lists nine bullet points for the
   dog and six for the favorite, then moves the number toward the dog. That is bullet-counting.
   It is precisely the Nolan failure mode the document warns about.
8. **Upset attractiveness 7/10, confidence 6/10.** Unanchored ordinal scales invite drift. The
   only two numbers that matter are P(win) and the standings-aware pool value.
9. **The pick only matters when it flips.** A probability model that moves SEA from 62% to 59%
   and still picks SEA produced nothing for the pool. Track how often the model *flips* a pick
   and how those flips do. Over a season that is maybe 10–20 games; that is the entire signal.

## 5. Data sources, 2026 status

| Source | Status | Use |
|---|---|---|
| nflverse `games.csv` (Lee Sharpe) | FACT: live, includes 2026 Week 1 lines already; columns for spread, both moneylines, rest days, div_game, roof, surface, temp, wind, starting QB ids, coaches | **Backbone.** Free, one file, has everything v0.1–v0.5 needs |
| nflverse play-by-play / nflreadr | FACT: live; injuries loader works pre-season | EPA features for the residual model, offseason |
| nflverse `load_injuries` (2009+) and snap counts (2012+) | FACT: available | Injury model, offseason |
| SumerSports | FACT: live, team EPA/success/pressure updated Sept 2 2026; free web tables | Nice for reading; not needed for the model (nflverse has the same EPA) |
| Pro Football Reference | Fine | Reference only |
| Opta / theanalyst.com | FACT: publishes weekly win probabilities | Log it as a comparison column, never as an input |
| PFF | Paid; not needed | Skip until a residual feature demands it |
| Sportsbooks | nflverse lines are a single-book snapshot, not consensus, and not the close | For the log, also record the line you see on ESPN/DraftKings at pick time. The Odds API (free tier) if you want multi-book later |
| Beat reporting / joint practices | Not quantifiable | Zero weight |

Note the proxy blocked my direct reads of nflreadr docs, covers.com and theanalyst.com; column
facts above come from the downloaded file itself.

## 6. Features with real evidence (as *residuals* on the market)

- **Home field:** large historically, shrinking since ~2020. Fully in the market. No residual.
- **Rest differential / Thursday / post-bye:** small effects in raw data; nfelo and others find
  little to nothing residual to the line. HYPOTHESIS: zero.
- **QB change (backup starting):** the market reprices within hours; residual is near zero by
  close but can exist at the *opener*. Only exploitable if you pick at the open, which you
  should not.
- **Weather / wind >15 mph:** affects totals far more than sides. HYPOTHESIS: zero for sides.
- **Divisional games, revenge, Super Bowl rematch:** folklore. HYPOTHESIS: zero.
- **Opening-to-close movement:** informative about where the close will be; irrelevant once
  you have the close.
- **Team EPA metrics (offense, defense, pass, rush):** strongly predictive of outcomes on their
  own; almost entirely absorbed once the market is a feature.

The honest summary is that the literature's residual-value list is empty or nearly so. That is
the finding. Test it yourself with the backtest in section 8 and be prepared to accept it.

## 7. Data schema

Keep two tables. Both are append-only CSVs, later SQLite if you like.

**`predictions_log.csv`** (one row per game per time you looked at it; never edited):
`logged_at_utc, season, week, game_id, gameday, away, home, away_ml, home_ml, spread_line,
p_away_novig, p_home_novig, pick, p_pick, source, note` (implemented) plus, when they exist:
`p_model, model_version, p_opta, flip_flag, adj_injury, adj_other, standings_mode`.

**`pool_picks.csv`** (filled after kickoff from the CBS pool page, one row per member per game):
`season, week, game_id, member, pick, entered_at`. Members: you, Sue, Nolan, mom, daughter, others.
Add a `bias_team_involved` flag computed from `away/home in {CHI, GB}`.

Results join from nflverse by `game_id`; no result column is ever hand-entered.

## 8. Backtesting methodology

- Universe: nflverse regular-season games 2007–2025 with moneylines (5,051). Add 2026 as it
  accrues.
- Baseline: no-vig closing moneyline. Report accuracy, Brier, log loss, and *pick-flip
  accuracy* (how the model does on games where it disagrees with the market).
- Splits: strictly chronological. Expanding window: train ≤ season t, test season t+1, for
  t = 2014…2024. Never a random split. Never use a feature computed with data from after
  kickoff (EPA "season averages" must be through the prior week only).
- Feature admission rule: a feature enters Model A only if its coefficient in
  `logit(P) = a·logit(P_market) + b·feature` is the same sign in ≥ 80% of test seasons and the
  pooled log-loss improvement is positive. Report the number of features tried, to keep
  yourself honest about multiple comparisons.
- Report everything with the ±2.9-point season standard error attached.

## 9. Model A and Model B

**Model A (the only one worth building this year):**
`logit(P_home) = a·logit(P_market_home) + Σ b_i·x_i`, fit by logistic regression with L2.
Start with x = {} and add candidates one at a time per section 8. If `a ≈ 1` and all `b ≈ 0`,
that is a result, not a failure.

**Model B:** gradient boosting (LightGBM) on the same rows with the market as a feature and
monotone constraint on `logit(P_market)`. Its sole purpose is to check whether Model A missed a
nonlinear interaction. Require ≥ 0.005 log-loss improvement over Model A across the expanding
window before it touches a pick. ASSUMPTION: it will not clear that bar. Defer to 2027.

## 10. Preseason decay

Recommended: weight 0. If you insist on a preseason term, make it a *prior on team rating* in
an Elo/rating component, not a per-game adjustment: rating_t = w_t·preseason_rating +
(1 − w_t)·in-season_rating with w_t = exp(−k·games_played), k chosen by backtest (nfelo-style
regression to preseason ratings uses roughly a third of the weight gone by Week 4). Whatever the
in-season rating is, the market term still dominates, so this changes almost nothing.

## 11. Injury value

Do not build this for 2026. When you do: value_of_player = (starter EPA/play − replacement
EPA/play) × expected snaps × position multiplier, with QB handled as a separate rating swap. The
market prices announced injuries within hours; the only exploitable window is between the news
and your pick, which is why v0.1 says "pick as late as possible."

## 12. Upset Radar, mathematically

Let `m` = market no-vig dog probability, `q` = your model's dog probability, `k` = shrinkage
in (0, 1] set by the backtest (start at 0.25: you trust 25% of your model's disagreement).
Posterior: `p_dog = m + k·(q − m)` (do it in logit space if you want cleanliness).

Rule for weeks 1–~13: **pick the dog iff p_dog > 0.5.** That is the whole radar. In the
handoff's own example (market 60/40, model 52/48), p_dog = 0.42. Pick the favorite. Their
"extremely interesting" case is a favorite pick in disguise.

Log `q − m` for every game so that at season end you can estimate `k` from the data: if your
disagreements have no predictive value, k → 0 and the radar switches itself off.

## 13. The family layer, separately

- **Weeks 1–13:** mirror the market. Collect everyone's picks weekly (cheap, five minutes on
  the CBS page after kickoff).
- **From ~Week 13:** run the standings simulation each week. Inputs: current standings,
  remaining schedule with market probabilities, each member's estimated pick rule (fit from
  their logged picks: favorite rate in close games, Bears/Packers lean). Output: for each game,
  the change in P(finish first) from taking the dog. Take dogs only where that change is
  positive. It usually will be positive only when you trail by more than the games remaining
  can cover with favorites.
- **Bias flag:** compute from the schedule, use only in the pick-tendency estimates. Never in
  the probability.
- **Sue:** log her picks, compute her dog-pick record versus market. Prior: no skill. Revisit
  in three seasons.

## 14. NE@SEA cross-check

Market 60–62% Seattle; Opta 61%; the handoff 59%. My independent view: I have no information
that is not already in a line that moved a point and a half toward New England over four months
of public discussion about Brown, Maye and Seattle's secondary. Disagreements with the handoff:

- Their 59/41 is not evidence-based; it is the bullet count. Substantively it is harmless
  because it does not flip the pick.
- "Market movement toward New England" is listed as a New England argument after the movement
  already happened. It is not an additional reason.
- Henderson's absence is small for a side (RB replacement cost is low; Stevenson is a
  competent starter). Listed on the right side, over-weighted.
- Seattle secondary losses (Woolen, Bryant) are real offseason facts but were priced in May.

Pick Seattle. Logged probability: 0.600 (nflverse line at log time). Confidence is "the market's."

## 15. v0.1, operating now

`python3 nfl-pool/v01_picks.py --season 2026 --week 1`

- Downloads nflverse games, computes no-vig probabilities, picks the favorite (home in a dead
  heat), appends to `predictions_log.csv` with a timestamp. Rows are never rewritten.
- Human steps: enter the picks on CBS as late as the site allows; after kickoff, log the
  family's picks into `pool_picks.csv`.
- Week 1 output tonight: SEA, LA, CHI, CIN, DET, BUF, BAL, JAX, PIT, TEN, LAC, LV, MIN, PHI,
  DAL, KC. Note that BUF@HOU, NYJ@TEN and GB@MIN are near coin flips; re-run before Sunday
  because those can flip on line movement.
- Offseason 2027 work, in order: (1) fit Model A and estimate `k`; (2) build the standings
  simulator; (3) only then consider EPA/injury residuals.

## Sources consulted

ESPN Week 1 odds and game page; SI, VSiN, NBC Sports and CBS Sports game previews (line
movement: opened SEA −4.5, ML from −195 to −185); patriots.com and NBC injury reports
(Henderson); NFL.com and ESPN (A.J. Brown trade); patriots.com (Doubs); ESPN and PFR (Super
Bowl LX box score); Opta Analyst Week 1 predictions (SEA 61%); Field Gulls (Seattle secondary
depth); nflverse `nfldata/data/games.csv` (all computed statistics); nfelo market-regression
analysis and FiveThirtyEight Elo comparison (models versus the line).

## Addendum (same day): reproducibility scripts and one retraction

`backtest_market.py` reproduces section 2 exactly. `pool_sim.py` reproduces section 3 and adds
two policies I had not run when I wrote sections 3 and 13.

Results, 6 members, 8,000 seasons per cell, others take the dog at rate DEV in games where the
favorite is under 62%:

| User policy | DEV 0.15 | DEV 0.30 | DEV 0.50 |
|---|---|---|---|
| always favorite | 0.224 | 0.383 | 0.564 |
| random dog at rate DEV | 0.170 | 0.159 | 0.167 |
| "skilled" dog, signal knows the winner 10% of the time | 0.335 | 0.387 | 0.535 |
| "skilled" dog, 25% | 0.792 | 0.836 | 0.907 |
| favorite until week 14, then dogs when trailing | 0.176 | 0.324 | 0.496 |

**Retraction.** Section 13 asserted that trailing late in the season makes dog picks
positive-value. The simple version of that policy (take close-game dogs from week 14 when the
deficit exceeds 5% of games remaining) *lowers* P(first) in every cell. The mechanism: a dog
pick gains a relative point with probability ~0.4 and loses one with ~0.6 against a leader on
the favorite, and in a 6-person pool the leader also gives back ground on their own random
deviations, so favorites usually close small gaps on their own. If a standings-aware policy
exists that helps, it is narrower than this heuristic and has to be derived (dynamic program
over deficit × games remaining), not asserted. Until someone does that, the operating rule is
simpler than I first wrote: **pick the favorite in every game, all season.**

**Caveat on the "skilled" rows.** The edge parameter is an oracle that reveals the actual
winner in a fraction of close games. Even 10% is a much bigger edge than any public model has
demonstrated over the closing line. Those rows show what would be required, not what exists.

## Addendum 2: ChatGPT's objection is correct, and it changes the operating rule

Objection: "a 40% dog costs 0.20 expected points, but in a winner-take-all contest with
correlated opponent picks it does not follow that it lowers P(first)." Tested with
`pool_sim.py --crossover` (6 members, user takes the dog only when the favorite is below a
threshold; others take dogs at rate DEV in games with the favorite under 62%):

| Others' DEV | never | fav <50.5% (~5 dogs/yr) | <52% (~13) | <55% (~37) | <58% (~67) |
|---|---|---|---|---|---|
| 0.00 | 0.167 | 0.435 | 0.432 | 0.361 | 0.224 |
| 0.02 | 0.081 | 0.267 | 0.312 | 0.288 | 0.186 |
| 0.05 | 0.114 | 0.221 | 0.278 | 0.258 | 0.164 |
| 0.10 | 0.172 | 0.231 | 0.261 | 0.239 | 0.145 |
| 0.15 | 0.218 | 0.258 | 0.267 | 0.237 | 0.144 |
| 0.30 | 0.380 | 0.386 | 0.382 | 0.284 | 0.152 |

What this says:

1. **I was wrong that dog picks only add variance.** Against a field that mostly mirrors the
   market, taking the dog in the handful of near-coin-flip games (favorite under ~52%) raises
   P(first) substantially, and it is never worse than always-favorite in any row. The expected
   cost of a 48% dog is 0.04 points; the differentiation value against a correlated field is
   far larger than that.
2. **The value collapses as the field's own deviation rate rises.** By DEV 0.30 the policies
   are indistinguishable. Heavy dog-picking (favorite under 58%) is worse than always-favorite
   everywhere. Section 3's "random dog" result stands: skill-free contrarianism in 60/40 games
   still loses. The mispricing hunt was aimed at the wrong games; the game-theory value is in
   the 50/50s, where mispricing is irrelevant.
3. **The decision variable is the family's actual deviation rate in close games**, which
   nobody has measured. That makes `pool_picks.csv` the most valuable dataset in this project.
4. **Caveat that cuts against the dog rows.** The simulation lets others deviate uniformly
   across close games. Real people deviate in the *same* coin-flip games (they are the games
   everyone perceives as toss-ups), and Bears/Packers fandom concentrates further. Correlated
   deviation in the same games shrinks the differentiation value. ChatGPT's simulation should
   model that explicitly; mine does not.

Revised operating rule for 2026, replacing "favorite every game": **favorite in every game
where the no-vig favorite is 52% or higher; in games under 52%, take the dog unless the logged
family picks show the family already splits those games.** Week 1 candidates by that rule:
BUF@HOU (favorite 51.7%), GB@MIN (52.2%, borderline), NYJ@TEN (52.6%, no).
