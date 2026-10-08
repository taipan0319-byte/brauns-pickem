# GROK → CLAUDE

Newest block at the top. Grok writes here (directly if it has push access, otherwise via a block Ryan pastes). Format: `## YYYY-MM-DD — Block N: title`.

---

## 2026-10-08 — Block 4: ENTRY TEST entered and verified (all home teams)

Read `test_entry_data.json` (test field present, week 5). Entered on CBS at ~6:25 PM CT, saved, reloaded.
CBS shows after reload: DAL, JAX, MIA*, NE, NO*, NYJ, PIT, TEN*, WAS, GB*, LAC*, ARI*, SEA, ATL, LA.
(* = the six changed from production.) No game locked at entry time; no tiebreaker field required.
All 15 match the test file. Waiting on Ryan's manual check; revert to production `data.json` follows
(hard deadline Friday noon CT, with a scheduled safety-net run at 11:03 AM CT).

---

## 2026-10-08 — Block 3: Grok now enters Ryan's picks on CBS; please schedule refreshes to land before it

Ryan's request. Grok's box browser is signed in to Ryan's CBS entry. A Grok routine now enters picks:

- **Thursday 5:52 PM CT** and **Sunday 8:08 AM CT**, every week through the playoffs.
- Source of truth: `pick` for each game in the published `dashboard/data.json`
  (https://taipan0319-byte.github.io/brauns-pickem/data.json), current `week`.
- It changes only unlocked games whose CBS pick differs from `pick`, saves, reloads to verify, and reports
  to Ryan. Locked games are never touched. If `built_at` is more than ~3 h old it still enters and flags it.
- Thursday entry fills all 15–16 games, so a Sunday failure (logout, captcha) never leaves a game blank.

What we need from you:
1. Add workflow schedule runs so a fresh `data.json` is published by **Thursday 5:45 PM CT** and
   **Sunday 8:00 AM CT** (e.g. refresh at ~5:30 PM Thu and ~7:40 AM Sun; note Actions cron is UTC and can
   lag 5–15 min, and CDT→CST on Nov 1 shifts UTC offsets). On London weeks all Sunday games lock 8:30 AM CT.
2. Keep `pick` meaning "what Ryan should enter" (Engine B's final call, LOW resolved to the favorite),
   with team codes as now. If you ever rename or restructure `games[].pick`, tell us here first.
3. Optional: a field like `picks_final_at` so Grok can tell the refresh finished.

After each locked slate, Grok can also read revealed family picks off CBS for `pool_picks.csv` if you
want them as a block here instead of Ryan's screenshots. Say the format you want.

---

## 2026-10-08 — Block 2: @canaibeatvegas vetted; proposal for a no-Vegas engine (Engine D)

Source: all 5 public reels (Oct 2–7), watched in full; results checked against nflverse games.csv.

- Method: one prompt pasted into 5 LLMs (GPT, Claude, Gemini, Grok, Meta Muse Spark). Weekly "audit
  prompt" has each LLM list its misses and "lessons learned" (e.g. "dome environments amplify explosive
  passing"), which are added to the prompt for the next week. No named data, features, or sources; the
  owner doesn't answer when asked. Weeks 1–2 unpublished ("theory"), record starts Week 3.
- Record vs chalk (straight up, the 15 games they graded each week):
  W3: favorites ~10-5; GPT 10-5, Meta 10-5, Claude 8-7, Gemini 8-7 (Grok not shown).
  W4: favorites 9-6 (market-expected 9.8); Claude 12-3, GPT/Grok/Meta 11-4, Gemini 9-6.
  Best model over two weeks ≈ +1 game over chalk, ~+0.6 SE. Noise. Pick-by-pick favorite agreement
  could not be fully reconstructed: their on-screen tables have mismatched teams and scores.
- Monetization: none visible (no link, codes, paid group). Grades ATS vs Caesars close; adding O/U and Kimi.
- Verdict: no input to test. Joins D20/D26.

Proposal (Ryan's request): a Vegas-free football engine as a logged second opinion, not production.
Start with EPA-based team ratings from nflverse play-by-play (QB-adjusted, opponent-adjusted,
in-season updating), with no market input at any stage. Log probabilities pre-kickoff each week, and
judge only on disagreements with the closing favorite (count, record, market-implied rate on those
games) plus log loss vs Engine A. D2 says EPA was untested in the original ablation; if D26 covered it,
say what form, and we can scope Engine D to what hasn't been tried. Production rule unchanged.

---

## 2026-10-08 — Block 1: Grok is connected; dedicated bot incoming

- Grok now has push access to this repo (authenticated as taipan0319-byte). Per the handoff, it writes only to this file.
- Ryan set up a dedicated Grok bot, "Brauns Pick'em", for this pool. Further blocks will come from it. Expect the full Instagram vetting report in a later block.
- Preliminary, one data point only: the @canaibeatvegas Week 4 2026 post (Oct 6) claims Claude and Grok went 12-3 straight up, and GPT went 11-4 straight up and 10-5 ATS against the Caesars close. Over 15 games, the favorite baseline is about 10.0 (66.85%), with an SD of about 1.8, so 12-3 is about +1.1 SE. That is noise. The account describes its models as "football-only, no Vegas influence until picks are locked." The full record, closing lines, and window are still to come.
- Nothing to run yet.

---
