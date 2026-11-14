#!/bin/zsh
# launchd com.USERNAME.jobkit-night (every 15 minutes): drafts or sends what is due (tools/night_send.py decides; prepare-only
# by default). Runs until hours.sender_end so morning windows (08:00-08:50 local by default) are reached.
KIT=/Users/USERNAME/job-agents-kit; GATE_END=sender
. "$KIT/launchd/night-gate.sh"
/usr/bin/caffeinate -i -t 1000 &!   # keep the Mac from idle-sleeping until the next run (timed, exits by itself)
exec /usr/sbin/taskpolicy -b /usr/bin/nice -n 19 "$PY" -I tools/night_send.py
