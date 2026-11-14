#!/bin/zsh
# Fills in the launchd templates for this Mac and copies them to ~/Library/LaunchAgents. Nothing is loaded unless you pass
# --load, so nothing runs by itself until you choose to.
# usage: zsh launchd/install.sh            write the filled-in plists and runners, print what to load
#        zsh launchd/install.sh --load     also load them (launchctl bootstrap)
#        zsh launchd/install.sh --unload   unload and remove them
set -e
KIT=$(cd "$(dirname "$0")/.." && pwd); ME=$(id -un); LA="$HOME/Library/LaunchAgents"
[ -f "$KIT/profile/settings.json" ] || { echo "Write profile/settings.json first (SETUP.md, step 2)."; exit 1; }
mkdir -p "$LA" "$KIT/logs" "$KIT/launchd/local"
for f in "$KIT"/launchd/com.USERNAME.jobkit-*.plist; do
  name=$(basename "$f" | sed "s/USERNAME/$ME/")
  if [ "$1" = "--unload" ]; then launchctl bootout "gui/$(id -u)/${name%.plist}" 2>/dev/null || true; rm -f "$LA/$name"; echo "removed $name"; continue; fi
  sed -e "s#/Users/USERNAME/job-agents-kit#$KIT#g" -e "s/USERNAME/$ME/g" -e "s#$KIT/launchd/run-#$KIT/launchd/local/run-#" "$f" > "$LA/$name"
  plutil -lint "$LA/$name" >/dev/null
  echo "wrote $LA/$name"
done
[ "$1" = "--unload" ] && exit 0
for f in "$KIT"/launchd/run-*.sh "$KIT"/launchd/night-gate.sh; do
  sed -e "s#/Users/USERNAME/job-agents-kit#$KIT#g" -e "s/USERNAME/$ME/g" -e "s#\$KIT/launchd/night-gate.sh#\$KIT/launchd/local/night-gate.sh#" "$f" > "$KIT/launchd/local/$(basename "$f")"
done
chmod +x "$KIT"/launchd/local/*.sh
if [ "$1" = "--load" ]; then
  for f in "$LA"/com.$ME.jobkit-*.plist; do launchctl bootstrap "gui/$(id -u)" "$f" 2>/dev/null || launchctl kickstart -k "gui/$(id -u)/$(basename "${f%.plist}")" >/dev/null 2>&1 || true; echo "loaded $(basename "$f")"; done
else
  echo "Not loaded. To start them: zsh launchd/install.sh --load   (kill switch at any time: touch ~/STOP-AGENTS)"
fi
