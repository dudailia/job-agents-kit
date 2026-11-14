#!/bin/zsh
# Shared gate for every launchd job in this kit. Sourced first by each run-*.sh:
#  - ~/STOP-AGENTS exists -> exit 0 at once (the kill switch: `touch ~/STOP-AGENTS` stops everything, `rm` resumes).
#  - Runs only from hours.night_start to hours.work_end in your time zone (profile/settings.json). A script that sets
#    GATE_END=sender before sourcing this file may run until hours.sender_end instead (the sender, the email audit and the
#    morning summary).
#  - Every job runs at background priority (taskpolicy -b + nice 19). Nothing comes to the front: no `open`, no app
#    activation; Mail is only ever launched hidden, by tools/night_send.py and tools/email_audit.py.
#  - No API-key billing: API-key and cloud-provider variables are cleared, so `claude` can only use the claude.ai login.
# usage (sourced): . "$KIT/launchd/night-gate.sh" ; then:  bg <command...>
[ -e "$HOME/STOP-AGENTS" ] && exit 0
KIT="${KIT:-/Users/USERNAME/job-agents-kit}"
cd "$KIT" || exit 0
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PY="${PY:-$(command -v python3)}"
eval "$("$PY" -I tools/kit.py --shell)" || exit 0
_end=$WORK_END; [ "${GATE_END:-}" = "sender" ] && _end=$SENDER_END
_t=$(date +%H%M)
if [ "$_t" -lt "$NIGHT_START" ] || [ "$_t" -ge "$_end" ]; then exit 0; fi
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
mkdir -p logs
bg() { /usr/sbin/taskpolicy -b /usr/bin/nice -n 19 "$@"; }
