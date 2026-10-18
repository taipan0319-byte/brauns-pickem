# Schedule log

One line per scheduled pre-entry refresh attempted by Claude's own trigger (not GitHub cron).
Format: `UTC fired | who | dispatched? | picks_final_at after | lag from target | note`.

GitHub cron baseline (from the Actions history, 2026-09-10 to 2026-10-06): 19 of 19 scheduled runs late by
3–7 hours; 2 Sunday runs dropped on 2026-09-20. Push/dispatch runs start within ~10 s.

2026-10-11T12:32:39Z | Claude trigger (Sunday) | dispatched yes | 2026-10-11T12:33:24Z | +3.4 min after 7:30 CT | fresh build landed before 8:08 CT | week 5
2026-10-15T22:21:17Z | Claude trigger (Thursday) | dispatched yes | 2026-10-15T22:21:51Z | +1.9 min after 5:20 CT | fresh build landed before 5:52 CT | week 6
2026-10-18T12:35:13Z | Claude trigger (Sunday) | dispatched yes | 2026-10-18T12:35:46Z | +5.8 min after 7:30 CT | fresh build landed before 8:08 CT | week 6
