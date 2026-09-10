# Brauns family NFL pick'em

Market-based picks (Engine A), a pool-strategy optimizer that maximizes the probability of finishing
first in a seven-person straight-up pool (Engine B), and a weekly dashboard.

**Dashboard:** https://taipan0319-byte.github.io/brauns-pickem/

Start with `COLLAB_README.md` (how it runs, weekly routine, data entry) and `DECISIONS.md` (what is
settled and why). Long-form analysis: `CRITIQUE.md`, `RESPONSE.md`.

Refresh a week by hand: `python3 refresh.py` (auto-detects the week) or trigger the
"Refresh week and publish dashboard" workflow in the Actions tab. The workflow also runs on a schedule
(Sunday 8 am CT, Thursday and Monday 3 pm CT), appends to the audit logs, and republishes the page.
