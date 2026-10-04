# Brauns family NFL pick'em

Market-based picks (Engine A), a pool-strategy optimizer that maximizes the probability of finishing
first in a seven-person straight-up pool (Engine B), and a weekly dashboard.

**Dashboard:** https://taipan0319-byte.github.io/brauns-pickem/

Start with `COLLAB_README.md` (how it runs, weekly routine, data entry) and `DECISIONS.md` (what is
settled and why). Long-form analysis: `CRITIQUE.md`, `RESPONSE.md`.

Pick deadline: CBS locks every remaining Sunday game at the FIRST Sunday kickoff, which is 8:30 AM
Central on London weeks (Week 4 2026 was lost this way). The dashboard header shows the next lock and
raises an EARLY LOCK banner when the first Sunday game is before noon. Finalize picks after the Thursday
refresh; the Sunday 6:23 AM CT refresh is only for last-minute line moves.

Refresh a week by hand: the "Refresh now" button on the dashboard (needs a fine-grained GitHub token
with Actions read/write on this repo, entered once and kept in that browser's local storage only),
`python3 refresh.py` (auto-detects the week), or trigger the
"Refresh week and publish dashboard" workflow in the Actions tab. The workflow also runs on a schedule
(Sunday 8 am CT, Thursday and Monday 3 pm CT), appends to the audit logs, and republishes the page.
