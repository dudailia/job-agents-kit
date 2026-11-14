#!/bin/zsh
# launchd com.USERNAME.jobkit-morning (07:30): rebuilds OUTREACH-TRACKER.html, TODAY.html and MORNING.md from the logs.
# Never touches Mail, opens nothing.
KIT=/Users/USERNAME/job-agents-kit; GATE_END=sender
. "$KIT/launchd/night-gate.sh"
bg "$PY" -I tools/build_tracker.py
bg "$PY" -I tools/build_today_focus.py
exec /usr/sbin/taskpolicy -b /usr/bin/nice -n 19 "$PY" -I tools/morning.py
