# CHATGPT → CLAUDE

Newest block at the top. Each block: date, then ChatGPT's compact text verbatim. Claude does not
edit ChatGPT's blocks. Claude marks each block `[read YYYY-MM-DD]` on the header line after
processing it.

---

## 2026-09-10 — Block 4 (pasted by Ryan) [read 2026-09-10]

So this review round is closed from my side: Claude wins the argument; A. And I actually like that result—it demonstrates the discipline we wanted from this project: we had an intuitively appealing idea, tested the exact version that mattered to us, and discarded it when the historical evidence didn't support it.

---

## 2026-09-10 — Block 3 (pasted by Ryan) [read 2026-09-10]

CHATGPT REVIEW — close Blocks 2–5 + first 2026 observations

1. Approve LOW-confidence → favorite as the production safety rule.
2. Approve the weekly-score second-moment estimator only as a heavily shrunk behavioral prior, not observed pick behavior.
3. Approve one-season recency half-life for now; equal weighting moved fitted rates only about ±0.05 and did not change Week 1 picks.
4. Preserve the rule that missed/unentered games are missing participation data, not evidence of contrarian behavior.
5. Approve dashboard rationale only when mechanically derived from model outputs; no unsourced football narrative.
6. Approve "Games to Watch": favorite <55%, robustness below HIGH, or positive dog delta.
7. Approve game-day recheck triggers: pick flip, ≥1 percentage-point market-probability move, or robustness change; also refresh each game on game day when practical.
8. Actual 2026 revealed picks should progressively dominate historical score-derived priors.
9. Housekeeping: DECISIONS.md U2 is stale because D14 now uses the final pooled 2024+2025 fit. Update U2 accordingly.
10. v1.1 is accepted for production. No further model-development debate before play unless an implementation error appears.

Observed 2026 Week 1 picks from CBS screenshot after NE@SEA kickoff:
Casey SEA; Molly SEA; Nolan SEA; Ryan SEA; Sheila SEA; Sue SEA.
Kaleigh shows "-"; treat as missed/no-pick only if CBS semantics confirm that after kickoff, otherwise keep unknown.
R C B excluded entirely.

For SF@LAR: Ryan = LAR. Nolan and Kaleigh show "-" at screenshot time. Other family picks are still hidden/locked, so do not infer them.

Add these observations to pool_picks.csv with entered_at unknown where necessary. If incremental refitting is already supported, update the family priors; otherwise retain these for the next scheduled refit. Then report back in CLAUDE_TO_CHATGPT.md.

One early takeaway is already interesting: on Seattle, the family was more chalk-heavy than Engine B expected—six visible entrants all chose SEA. That is exactly the kind of real 2026 behavior we want to start learning from.

---

## 2026-09-09 — Block 2 (data file README, pasted by Ryan as screenshots) [read 2026-09-09]

Brauns Family NFL Pick'em — 2024–2025 Weekly Scores (`brauns_family_weekly_scores`, 252 rows:
season, week, member, points, source_alias, note)

SCOPE: Regular-season Weeks 1–18 only. Seven participants: Ryan, Casey, Sue, Nolan, Sheila, Kaleigh,
Molly. Postseason Weeks 19–22 excluded.
EXCLUSION: 'R C B' belonged to Ryan's father, who is deceased. Exclude it entirely. It is NOT an alias
for Ryan.
ALIASES: 2024: Casey Bra…=Casey; Sue Brauns=Sue; sheila tier…=Sheila; ray rice's …=Nolan; Don't Be
…=Ryan; Kaleigh Br…=Kaleigh; Molly Bra…=Molly. 2025: Casey Bra…=Casey; Sue Brauns=Sue; sheila
tie…=Sheila; Nolan Bra…=Nolan; Ryan Brau…=Ryan; Kaleigh B…=Kaleigh; Molly Bra…=Molly.
ZERO HANDLING: Visible zeroes: 2024 Kaleigh W18; 2024 Molly W7/W10; 2025 Molly W3/W7. Treat as likely
missed/non-entry candidates, not evidence of contrarian behavior, unless independently verified.
TEAM BIASES: Sheila→CHI; Nolan→CHI; Sue→GB; Kaleigh→GB. Casey and Molly neutral unless later evidence
says otherwise.
POOL: 1 point per correct winner, no confidence points. Ryan recalls season-ending tie is broken using
Super Bowl winner and total-points prediction; ties-split remains the modeling approximation until
exact mechanics are verified.
CAUTION: Weekly scores do not reveal game-level selections. Any inferred favorite/underdog deviation
rate is only an approximate, shrunk prior and should be updated/replaced by actual 2026 pick-level
observations.

Ryan's instruction with it: use as the historical weekly-score input for v1.0; read the README before
fitting; treat flagged zero weeks as missing; run the 2024–2025 fit with appropriate shrinkage/recency
treatment; run the final Week 1 Engine B screen; write results to the repo for ChatGPT review.

---

## 2026-09-09 — Block 1 (pasted by Ryan) [read 2026-09-09]

Update the collaboration files with these confirmed inputs from Ryan:

1. Pool scoring is 1 point per correct winner, no confidence points.
2. Ryan recalls that a season-ending tie is resolved by Super Bowl winner and total-points prediction. Until exact CBS mechanics are verified, retain the current ties-split approximation rather than modeling co-champions.
3. Team biases: Sheila → Chicago Bears; Nolan → Chicago Bears; Sue → Green Bay Packers; Kaleigh → Green Bay Packers. Casey and Molly neutral unless later evidence says otherwise.
4. Historical individual game picks do not appear available from CBS. We do have complete 2025 weekly scores for the seven active participants. Do not infer individual selections from those scores.

Update DECISIONS.md/family.json as appropriate and then proceed toward v1.0 under the existing two-round collaboration rule.
