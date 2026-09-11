# DECISIONS — authoritative record

Entries here survived review. Anything not listed is open. Format: ID, decision, basis, date.

## Settled

- **D1. Engine A production probability = no-vig consensus moneyline.** Basis: 4,842 games
  2007–2025, calibration within 2.4 points in every bucket (`backtest_market.py`). 2026-09-09.
- **D2. No residual football model in production for 2026.** Basis: chronological ablation
  (`engine_a.py`) — Elo, rest, division, weather and QB-change blocks all worsen out-of-sample log
  loss; the model's disagreements with the market win at coin-flip rates. Challenger kept only as a
  test harness. EPA and injury features remain untested (offseason). 2026-09-09.
- **D3. The objective is P(finish first), not expected correct picks.** 2026-09-09.
- **D4. Early-season selective contrarianism can raise P(first).** Claude's original claim that
  dogs only add variance was wrong and is withdrawn. Basis: exact result that one deviation onto a
  q-dog against a fully correlated field gives P(first) = q versus 1/N; simulations in
  `pool_theory.py` and ChatGPT's independent grid agree qualitatively. 2026-09-09.
- **D5. Dog picks in games with a favorite of 55% or more are negative in every scenario tested.**
  The original "Upset Radar" for 60/40 games is retired. 2026-09-09.
- **D6 (revised). Production rule: the no-vig favorite in every game, including coin flips.**
  Basis: with `family.json` fitted to the 2024 weekly scores, Engine B scores every Week 1 dog
  pick negative at HIGH confidence, including the three games under 53%. The earlier 52%
  threshold assumed a chalk-heavy family; the family is not chalk-heavy. Re-evaluated weekly by
  the screen; the rule changes only if the screen says so. 2026-09-09.
- **D7. Roster N = 7:** Ryan, Casey, Sue, Nolan, Sheila, Kaleigh, Molly. R C B (Ryan's late father)
  is excluded from everything and is not an alias for Ryan. 2026-09-09.
- **D8. Engines A and B stay separate; logs are append-only.** 2026-09-09.
- **D9. Preseason narratives, joint-practice reports, Opta and expert picks carry zero model weight.**
  2026-09-09.
- **D10. Pool scoring confirmed: 1 point per correct winner, no confidence points, season-long.**
  Source: Ryan via ChatGPT block 1. 2026-09-09.
- **D11. Bias mapping:** Sheila → CHI, Nolan → CHI, Sue → GB, Kaleigh → GB at strength 0.4 (prior);
  Casey and Molly neutral. Source: Ryan. 2026-09-09.
- **D12 (amended). Historical individual picks are unavailable; weekly scores are.** The scores Ryan
  supplied are the **2024** season (CBS year selector, and confirmed by matching weekly scores to
  the all-favorites score: week 13 family 12–15 vs 2024 favorites 13/16, 2025 favorites 9/16).
  Weeks 5–18 itemized; weeks 1–4 only as a combined total; playoff weeks excluded. Member
  deviation *rates* are estimated from weekly-score variance (`fit_from_scores.py`); individual
  selections are never inferred. 2026-09-09.
- **D14 (final). The family is not Vegas-heavy; all-favorites would have finished 1st in 2024 and
  2nd in 2025.** Data: ChatGPT's 252-row file, 2024 and 2025 weeks 1–18, seven members, reconciled
  cell-for-cell with Claude's screenshot transcription and with CBS season totals once playoff points
  are added. Regular-season totals versus all-favorites:
  2024 (chalk 195): Casey 193, Sue 192, Sheila 182, Nolan 175, Ryan 170, Kaleigh 169, Molly 152.
  2025 (chalk 177): Casey 182, Kaleigh 177, Nolan 174, Sheila 171, Sue 171, Ryan 166, Molly 140.
  Casey's 2025 edge came in weeks 9–18, when favorites under 62% won 23 of 53 close games (43%).
  Fitted close-game underdog rates, recency half-life one season (2024 weighted 0.5), shrunk with six
  pseudo-weeks, flagged zero weeks dropped: Sue 0.23, Sheila 0.30, Casey 0.35, Nolan 0.39, Kaleigh 0.41,
  Molly 0.92; Ryan 0.52. Caveats: nflverse line timing unverified; unpicked games look like dog picks;
  the estimator identifies the level of deviation, not its distribution across bands. 2026-09-09.
- **D15 (confirmed). Screen-name mapping.** The 2025 standings show "Ryan Brau…" as the highlighted
  row and "Nolan Bra…" in 4th; the 2024 rows "Don't Be …" (highlighted) and "ray rice's …" are the same
  people. 2026-09-09.
- **D16. Pick every playoff game.** CBS season totals include weeks 19–22. Casey scored 10 playoff
  points in both 2024 and 2025; Ryan scored 4 and 1; Kaleigh and Nolan 0 in 2025. Picking the
  favorite in all 13 playoff games is worth roughly 8–9 expected points and costs nothing. Engine B
  does not yet simulate playoff weeks; the decision does not depend on it. 2026-09-09.
- **D13. Weekly screen and confidence rule.** `engine_b.py --screen`; LOW confidence resolves to the
  favorite. 2026-09-09.

- **D17. ChatGPT review of Blocks 2–5 (2026-09-10): all approved.** LOW confidence → favorite; the
  score-variance estimator is a heavily shrunk prior only; one-season recency half-life; missed weeks are
  missing data; rationales must be mechanically derived; Games-to-Watch rule (favorite <55%, robustness
  below HIGH, or positive dog delta); recheck triggers (pick flip, ≥1-point probability move, robustness
  change) plus game-day refresh when practical; revealed 2026 picks progressively dominate the priors.
  **v1.1 accepted for production.** No further model debate before play unless an implementation error
  appears. 2026-09-10.
- **D18. Revealed-pick updating.** `pool_picks.csv` holds observed picks (member, game, pick, when
  recorded, note). `engine_b.py --fit` re-estimates each member's dog rate per band as
  (observed dog picks + prior rate × 10) / (observed picks + 10), so ten real picks in a band weigh as
  much as the score-derived prior and more thereafter. A "-" on CBS is recorded as unknown, never as a
  pick or a miss, unless CBS semantics after kickoff confirm a non-entry. 2026-09-10.

- **D19. Injuries stay out of production (option A).** Tested 2026-09-10 (`test_injuries.py`,
  `test_injuries_coinflip.py`, nflverse injury reports 2009–2025 and snap counts 2012–2025). Injury
  reports predict winners on their own (56%), the market absorbs ~80% of that, and the residual is
  tiny and does not live in coin-flip games: with a favorite under 55%, the injury gap has no
  predictive value and QB absences point the wrong way (the side missing its QB won 36 of 62). Weighting
  by player importance (snap share) adds nothing. Two review rounds completed; ChatGPT concurs. The
  injury-adjusted probability may be logged beside the market number for a season-end look, but no
  pick is ever changed by it. 2026-09-10.

- **D20. Underdog ranking backtest: no ranking signal (2026-09-11).** `backtest_dogs.py`. Market underdogs
  priced 40–50% (984 out-of-sample games, 2014–2025) and 45–50% (414), ranked within each season by a
  logistic model of every pregame variable available (Elo, rest, division, cold, wind, QB change, injury
  differential, last-season record, home dog, early season, public-franchise flags), trained only on prior
  seasons. Residual model (market + variables), 40–50% band, quintile the model likes most: dogs won 40.3%
  vs 43.6% priced, excess −6.3 wins; least-liked quintile +6.7. Top decile −2.0 wins (−0.4 SE). 45–50%
  band: top quintile +4.3 wins but bottom quintile +4.8 and deciles alternate sign; top decile −1.1 wins.
  No monotonic gradient in any specification; coefficient signs flip between the two bands. The pregame
  variables cannot identify a subset of 40–50% underdogs that beats its market price. Production unchanged.
  Output: `dashboard/backtest_dogs_output.txt`. 2026-09-11.

## Unresolved (conservative production choice in force)

- **U1. Tie rule.** In force: ties split evenly. Ryan recalls CBS resolves season ties by Super Bowl
  winner and a total-points prediction, which is close to a lottery for modeling purposes; keep
  ties-split until the exact mechanics are verified. Not modeling co-champions.
- **U2. Family deviation rates.** In force: the final pooled 2024+2025 fit (D14, recency half-life one
  season, six pseudo-weeks of shrinkage), now being updated by revealed 2026 picks per D18. Bias
  strength 0.4 remains a prior with no pick-level evidence yet.
- **U5. Early-season market reliability (pre-registered, 2026-09-11).** Ryan's hypothesis: early lines lean on
  last season and are less reliable. Tested 2007–2025: (a) weeks 1–3 favorites priced 65.1% won 62.1%
  (gap −3.0 ± 1.7); week 1 alone −0.4 ± 2.9; weeks 1–3 coin flips (fav <55%) favorites won 46% of 124 vs
  55% later. Weak support, borderline significance, and not present in week 1 itself. (b) Last-season
  record with the market in the model has a POSITIVE coefficient in weeks 1–3, i.e. the market slightly
  under-weights last season rather than over-weighting it; log-loss gain 0.001, pick flips 12–11.
  Production unchanged (post-hoc split, 1.8 SE, injury lesson applies). Pre-registered season-end test:
  do 2026 weeks 1–3 favorites win at their priced rate? Nothing acts on this before then.
- **U6. Public-money / hype hypothesis (tested 2026-09-11, no action).** Does betting emotion leave
  favorites mispriced? 2007–2025: favorites that are "public" franchises (DAL, GB, KC, PIT, CHI, NE, PHI,
  SF, DEN, LV) won 69.0% vs 68.1% priced (+0.9 ± 1.1); primetime favorites +0.8 ± 1.5; no era shows a gap.
  The only trace of public money is the favorite-longshot bias: favorites priced 80%+ win 87% (+2.4 ± 1.4),
  i.e. the public overbets longshots and favorites are slightly UNDER-priced. One marginal cell: when a
  public team is the underdog, the favorite wins 63.4% vs 66.1% priced (−2.7 ± 1.4, 1.9 SE), with no pick
  flips since the favorite still wins 63%. Conclusion: emotion in the market, where measurable, makes
  chalk better, not worse. Logged for a season-end look with U5; production unchanged.
- **U4. Level differences between ChatGPT's simulation grid and Claude's.** Same shape, different
  levels; cause not identified (probability distribution, tie handling, or where opponent
  deviations land). Does not change any decision. Closed unless it starts to matter.
