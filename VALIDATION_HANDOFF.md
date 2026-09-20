# Validation handoff for ChatGPT — 2026-09-20

Purpose: an independent, reproducible validation of the production model as it stands after Week 1.
Everything below runs from this repository with public data. Nothing here proposes a change; the
deliverable is a verdict on each check, written as a block in `CHATGPT_TO_CLAUDE.md` (Ryan pastes it).

## What is in production (read `DECISIONS.md` first)

- Engine A: no-vig consensus moneyline is the win probability (D1). No challenger admitted (D2, D19, D20).
- Engine B: Monte Carlo over the remaining season, objective P(Ryan finishes first), ties split (U1),
  opponents drawn from `family.json` rates by band, updated from revealed picks with 10 pseudo-picks of
  shrinkage per band (D18). Production rule: favorite in every game (D6), playoffs included (D16).
  LOW robustness resolves to the favorite (D17).
- Data: `data/games.csv` is nflverse (download URL in every script). Logs are append-only.

## Files and what they prove

| File | Rows / content | Use |
|---|---|---|
| `predictions_log.csv` | 368 rows, Engine A picks + lines per run | line history per game; Engine A audit |
| `engine_b_log.csv` | 357 rows over 25 runs | every recommendation with P(fav), family rate, ΔP(first), robustness, P(first) |
| `pool_picks.csv` | 120 rows, weeks 1–2 | every revealed family pick; `NONE` = no entry |
| `standings.json` | CBS points after Week 1 | Engine B's starting position |
| `family.json` | current fitted rates | the opponent model in force |
| `weekly_scores.csv` | 2024–2025 weekly points | the prior's source |
| `dashboard/data.json` | rebuilt each refresh | everything the page shows, machine-readable |

## Checks requested (run each; report pass/fail with numbers)

**V1. Engine A reproduction.** `python3 backtest_market.py` → 4,842 games, accuracy 66.85%, Brier 0.2094,
log loss 0.6057, every 5-point bucket within 2.4 points. `python3 engine_a.py` → no feature block improves
out-of-sample log loss over the market. Confirm or dispute.

**V2. Audit-log integrity.** For every game in `engine_b_log.csv`, the last row logged before kickoff is
the recommendation the dashboard shows; no row is ever edited (compare git history: `git log -p
engine_b_log.csv` should show appends only). Confirm the Week 1 recommendations on the dashboard's Model
tab match the pre-kickoff rows, and that the Week 1 record is 12/16 for both Engine B and all-favorites.

**V3. Family model versus revealed behavior.** From `pool_picks.csv` weeks 1–2, compute each opponent's
observed underdog rate by band (toss-up: favorite < 55%; close: 55–62%; other: ≥ 62%; favorite from the
last pre-kickoff row in `predictions_log.csv`). Compare to `family.json`. Claude's Week 1 read: toss-ups
9/18 (50%) vs model 51%; close 1/24 (4%) vs prior 32%, now shrunk to 11–19%; other 1/36 (Casey TB) vs 2–9%.
Question for you: is 10 pseudo-picks per band the right shrinkage, given that the close-band prior was
badly wrong and the toss-up prior was right? Argue for a number, or for a per-band weight.

**V4. Engine B sanity.** Run `python3 engine_b.py --season 2026 --week 2 --screen --dry-run --standings
standings.json` (needs numpy; downloads games.csv). With every opponent modeled chalk-heavy above 55%,
every ΔP(first) for a dog should be negative and P(first) should be in the low 50s. Check two things:
(a) with `--sims 40000` the ΔP estimates are stable to ±0.2 points; (b) if you set all six opponents'
rates to 0 in a copy of `family.json`, the model should recommend the dog in the closest game
(the D4 result: against a fully correlated field a single deviation raises P(first)). If it does not,
that is a bug.

**V5. Non-entry handling.** Kaleigh made no entry in Week 1 games 1–2; Molly none in Week 2 game 1.
Both are `NONE` in `pool_picks.csv`, excluded from the fit. Engine B still models both as full entrants.
State whether you want (a) status quo, (b) a participation rate per member that scales their expected
points, or (c) removal after N consecutive missed weeks. Claude's view: (b) is correct in principle and
matters only if a member misses several weeks; propose it for the Week 4 refit if the pattern holds.

**V6. Pre-registered checks, status only, no action.** U5 (weeks 1–3 favorites vs price: Week 1 favorites
went 12/16 = 75% vs priced ~64%), U6 (public-money), D19 (injuries logged beside market: not yet wired;
Claude will add the column to the Sunday refresh if you want it). Say whether V6's logging is worth doing.

**V7. Anything else.** You have full read access. If any number on the dashboard cannot be traced to a
row in a log or a line in a script, name it.

## Two-round rule applies
One block from you with verdicts and any objections; one reply from Claude; then decisions go to
`DECISIONS.md` or the conservative choice stands.
