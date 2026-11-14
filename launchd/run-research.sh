#!/bin/zsh
# launchd com.USERNAME.jobkit-research (00:40): one headless `claude -p` research shift at background priority, killed at
# hours.work_end. Research and planning only: it never touches Mail and never sends (sending is tools/night_send.py's job).
KIT=/Users/USERNAME/job-agents-kit
. "$KIT/launchd/night-gate.sh"
DAY=$(date +%F); LOG=$KIT/logs/night-research-$DAY.log
exec 9>$KIT/logs/research.lock; /usr/bin/lockf -t 0 9 2>/dev/null || { echo "$(date) already running" >> $LOG; exit 0; }
now=$(date +%s); stop=$(date -j -f "%Y-%m-%d %H%M" "$DAY $WORK_END" +%s); left=$(( stop - now ))
[ $left -lt 900 ] && exit 0
# Subscription login ONLY, never an API key or anything billed per call. If the CLI is not on the claude.ai login, don't run.
auth=$(claude auth status 2>/dev/null | tr -d ' \n')
case "$auth" in
  *'"authMethod":"claude.ai"'*'"apiProvider":"firstParty"'*) ;;
  *) echo "=== $(date) NOT RUN: claude is not on the claude.ai subscription login" >> $LOG; exit 0;;
esac
echo "=== $(date) start, $left s budget" >> $LOG
bg claude -p "$(cat $KIT/research/night-research-prompt.md)" \
  --permission-mode acceptEdits \
  --allowedTools "Bash Read Write Edit Glob Grep WebSearch WebFetch" \
  --disallowedTools "Bash(osascript:*) Bash(open:*) Bash(killall:*) Bash(pkill:*) Bash(launchctl:*) Bash(rm:*) Agent mcp__playwright__* mcp__claude-in-chrome__*" \
  --max-budget-usd 25 --no-session-persistence < /dev/null >> $LOG 2>&1 &
pid=$!
# watchdog: kill the shift at hours.work_end or as soon as ~/STOP-AGENTS appears
while kill -0 $pid 2>/dev/null; do
  if [ -e "$HOME/STOP-AGENTS" ] || [ $(date +%s) -ge $stop ]; then kill $pid; echo "=== $(date) stopped by watchdog" >> $LOG; break; fi
  sleep 30
done
wait $pid 2>/dev/null; echo "=== $(date) end" >> $LOG
