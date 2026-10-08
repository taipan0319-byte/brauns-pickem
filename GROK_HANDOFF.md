# Handoff for Grok — Brauns family NFL pool model

Read this first. It is self-contained. Everything it cites is public in this repository and on the dashboard.

- Repository: https://github.com/taipan0319-byte/brauns-pickem (public, branch `main`)
- Raw file base: https://raw.githubusercontent.com/taipan0319-byte/brauns-pickem/main/
- Dashboard (no login): https://taipan0319-byte.github.io/brauns-pickem/
- Live data behind the dashboard: https://taipan0319-byte.github.io/brauns-pickem/data.json

## What this is

Ryan Brauns is in a seven-person family NFL straight-up pick'em on CBS Sports (one point per correct winner,
every game including playoffs, bragging rights only). Two AIs have built and audited a system whose single
objective is **Ryan's probability of finishing first**, not his expected number of correct picks. Claude builds
and runs it. ChatGPT reviews it with read-only access. You are being brought in as a third reviewer, mainly to
vet outside claims (see the first task below) and to audit what exists.

Ground truth about the problem, established by testing and recorded in `DECISIONS.md`:

1. **The market cannot be beaten on win probability with public data.** The no-vig consensus moneyline over
   4,842 games (2007–2025) is calibrated: 66.85% straight up, Brier 0.2094. Nine challengers were tested
   chronologically out of sample and every one lost: Elo, rest, division, weather, QB change, injuries,
   EPA efficiency, underdog ranking, and a dedicated underdog-only model ("Engine C"). Injuries in coin-flip
   games point the wrong way (the side missing its QB won more often, 36 of 62). Details: D2, D19, D20, D26.
2. **So the only edge in a pool is positional.** Pick differently from the room when it is cheap and when the
   standings make variance valuable. That is Engine B.
3. **Realized luck masquerades as skill constantly.** Our replay found "take the dog whenever the favorite is
   under 52%" worth +5.7 points of P(first) on real 2015–2025 results and −0.4 when outcomes are drawn from
   the market instead: the sub-52% dogs happened to win 53% against 49% priced over 134 games. One standard
   error. This is the trap you are being asked to help us avoid.

## The system

- **Engine A** (`v01_picks.py`, `engine_a.py`): win probability = no-vig consensus moneyline from nflverse's
  `games.csv`. Nothing else. Logs every prediction before kickoff to `predictions_log.csv`.
- **Engine B** (`engine_b.py`): Monte Carlo over the rest of the season, 20,000 simulations, common random
  numbers. Each game's winner drawn from Engine A; each of the six opponents' picks drawn from a fitted
  tendency (`family.json`: dog rate by band — toss-up <55%, close 55–62%, other ≥62% — plus a team lean for
  four of them); standings carried forward; ties split. For every game this week it compares P(first) with
  the favorite against P(first) with the underdog, closest games first, and recommends whichever is higher.
  Robustness: HIGH >3× Monte Carlo noise, MEDIUM 1–3×, LOW inside noise; LOW resolves to the favorite (D27).
- **Family model**: prior from 2024–2025 weekly scores (`fit_from_scores.py`), updated every week from
  revealed picks (`pool_picks.csv`, read off CBS screenshots after each game locks) with band-specific
  shrinkage (D21). `NONE` means no entry, never a pick.
- **Production rule in force**: the favorite in every game, playoffs included, unless Engine B flags a
  HIGH or MEDIUM underdog. Through Week 5 2026 it has flagged none.
- **Pipeline**: GitHub Actions refreshes lines, reruns both engines, appends logs, rebuilds the dashboard
  (Thursday, Sunday ×3, Monday, Tuesday rollover, plus a Refresh button on the dashboard).

Validation already done, all public:

- `backtest_market.py`, `backtest_dogs.py`, `test_injuries.py`, `test_market_biases.py`, `engine_c.py`:
  the challenger tests above. Outputs in `dashboard/*.txt`.
- `backtest_engine_b.py` (U7, D27): replays 2015–2025 week by week against real results with simulated
  opponents, plus a calibrated control and two adversarial opponent models ChatGPT requested (a correlated
  room via Gaussian copula at rho 0.2/0.5/0.8, and the six dog-rate profiles shuffled among people).
  Result: the current rule is worth +1 to +2 points of P(first) over pure chalk if the family model is
  roughly right, about zero if badly wrong, never negative in any cell. Outputs:
  `dashboard/backtest_engine_b_output.txt`, `..._calibrated.txt`, `..._adversarial.txt`,
  `..._adversarial_calibrated.txt`.
- ChatGPT's independent validation V1–V7 (`CHATGPT_TO_CLAUDE.md`) passed with four refinements, all
  implemented (D21–D25).

State as of Week 5 2026: standings Nolan 43, Ryan 41, Sheila 40, Casey 39, Sue 37, Kaleigh 37, Molly 34.
Ryan's modeled P(first) ≈ 52%.

## Files

| File | What |
|---|---|
| `DECISIONS.md` | The authoritative record: D1–D27 plus the unresolved list. Read this before anything else. |
| `COLLAB_README.md` | How the ChatGPT collaboration works; same rules apply to you. |
| `CHATGPT_TO_CLAUDE.md`, `CLAUDE_TO_CHATGPT.md` | The review correspondence, newest block at the top. |
| `GROK_TO_CLAUDE.md`, `CLAUDE_TO_GROK.md` | Your channel. See "How to write back". |
| `engine_b.py`, `family.json`, `standings.json`, `pool_picks.csv` | Production strategy engine and its inputs. |
| `engine_b_log.csv`, `predictions_log.csv` | Append-only logs, every row timestamped before kickoff. |
| `backtest_engine_b.py` and `dashboard/backtest_engine_b_*.txt` | The replay harness and its four outputs. |
| `CRITIQUE.md`, `RESPONSE.md`, `VALIDATION_HANDOFF.md` | Long-form history; reference only. |

## Rules of engagement

1. **Out of sample or it does not exist.** A claim about picking winners needs a chronological, pre-registered
   test. Pick flips and log-loss against the market line are the measures; straight-up accuracy over a small
   sample is not evidence of anything.
2. **Two rounds per disagreement, maximum.** Round 1: argument or reproduction. Round 2: response. Then it
   goes into `DECISIONS.md` as settled or unresolved with the conservative choice in force. Ryan can reopen.
3. **No production change without a decision entry** and a test it survived.
4. **Separate luck from structure.** Any gain on real results must be checked against a calibrated control
   (outcomes drawn from the market). We have the harness; ask Claude to run it.
5. Roster is exactly seven. `R C B` on the CBS standings is Ryan's late father's historical entry; it is
   excluded from everything and is not an alias for anyone.
6. Family members are real people identified by first name in a public repo. Keep it to picks and rates.

## First task: vet an outside model

Ryan has seen an Instagram account claiming an AI-built NFL model (Claude plus ChatGPT) that is "doing very
well". You can read Instagram; Claude cannot. Please extract and report, as data, not impressions:

1. **The record.** Every pick you can find with its date, the game, the side, and the result. Were picks posted
   before kickoff with visible timestamps? How many games in total?
2. **Against what?** Straight-up winners, against the spread, or moneyline profit? For each pick, what was the
   closing line? A model that picks favorites straight up will show 65–70% and that is the market, not skill.
3. **Window.** When does the record start? Is there an earlier period that is not shown?
4. **Method, as described.** What inputs does it claim to use? Anything we have already tested (injuries,
   rest, weather, EPA, "sharp money", public betting percentages) is in the list above with its result.
5. **Your verdict**, in this form: picks N, straight-up X%, market-expected Y% on the same games, difference in
   standard errors. Anything inside two standard errors on under 300 games is noise; say so.

If the record is good enough to matter, name the specific input you think carries the signal, and Claude will
run it through the same chronological out-of-sample harness as the nine challengers. That is how it earns a
place, not by its win rate.

## How to write back

You can read this repository directly. If you can push to GitHub with credentials Ryan gives you, write only
to `GROK_TO_CLAUDE.md` (newest block at the top, dated, headed `## YYYY-MM-DD — Block N: title`) and nothing
else; Claude is the only writer of production files. If you cannot push, give Ryan a compact block in that
format and he pastes it; Claude inserts it verbatim. Claude answers in `CLAUDE_TO_GROK.md`. Keep blocks
short: numbers, sources, and what you want run.
