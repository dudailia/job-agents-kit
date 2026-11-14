#!/bin/zsh
# launchd com.USERNAME.jobkit-postings (04:05): read-only scan of public job-board APIs for new postings. Never touches Mail.
KIT=/Users/USERNAME/job-agents-kit
. "$KIT/launchd/night-gate.sh"
exec /usr/sbin/taskpolicy -b /usr/bin/nice -n 19 "$PY" -I tools/scan_postings.py --needs
