#!/bin/zsh
# launchd com.USERNAME.jobkit-email-audit (05:15): READ-ONLY email audit -> needs-reply.html and counts for MORNING.md and the
# tracker. Never sends, replies, moves, deletes, flags or marks mail. Mail is launched hidden and quit after if this run launched it.
KIT=/Users/USERNAME/job-agents-kit; GATE_END=sender
. "$KIT/launchd/night-gate.sh"
exec /usr/sbin/taskpolicy -b /usr/bin/nice -n 19 "$PY" -I tools/email_audit.py
