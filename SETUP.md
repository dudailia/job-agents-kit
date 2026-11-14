# Reference

The setup steps are in [README.md](README.md#setup). This page is for later: the daily routine, the safety switches,
and what every file is.

## Every morning

1. Read `MORNING.md` (what the night did) and `TODAY.html` (what to do by hand, in your order).
2. `needs-reply.html` lists the emails where someone asked you for something and you have not answered.
3. Read each planned email in TODAY.html under "Emails to approve". If it is right, set `"approved": true` for its id in
   `data/emails.json`; if not, fix it, or set `"hold"` to a reason.
4. Prepare mode (the default): the night job saved the due emails to Mail's Drafts. Send the ones you want yourself, then
   record each with `python3 -I tools/sender.py --mark-sent <id>` so its follow-up is drafted on time.
5. Send mode: only when every email and form answer you reviewed was right, set `send.mode` to `"send"` in
   `profile/settings.json`. Approved emails then go out by themselves. Unapproved ones are still only drafted.

## Safety switches

| What | How |
|---|---|
| Stop every job now | `touch ~/STOP-AGENTS` (delete it to resume) |
| Pause sending only | `echo why > logs/SENDER-PAUSED` (delete it to resume). The night job writes it itself when a message is stuck in the Outbox |
| After a Mail login error | sign in to Mail again, then delete `logs/MAIL-LOGIN-ERROR` |
| Never send | keep `send.mode` at `"prepare"` |
| Remove the schedule | `zsh launchd/install.sh --unload` |

Always on: Mail is only launched hidden and never brought to the front. Every send or draft is on a weekday inside the
region's window and your sender hours, under the daily cap and a few minutes apart. Never to an employer in
`profile/never-apply.md`, never twice to one address. A reply cancels the follow-up. No draft is ever deleted. The
research shift runs only on a claude.ai subscription login, never an API key, and uses only `profile/facts.md`.

## Files

| Path | What |
|---|---|
| `profile/settings.json` | everything about you and your rules (from `settings.example.json`; not committed) |
| `profile/facts.md` | the only facts that may be used about you (from `facts.example.md`; not committed) |
| `profile/never-apply.md` | employers never to contact, one `- Name` per line |
| `data/emails.json` | the email plan (format: `data/emails.example.json`) |
| `data/today.json` | by-hand items for TODAY.html (format: `data/today.example.json`) |
| `data/linkedin-notes.json`, `data/applications-log.csv`, `data/watch.json`, `data/cover-letters/`, `data/research/` | written by you or the research shift |
| `tools/night_send.py` | the night job: drafts (prepare) or sends (send, approved only); `--draft-now <id>`, `--dry` |
| `tools/sender.py` | Mail scripts, outreach log, reply check; `--due`, `--mark-sent <id>` |
| `tools/fu_rules.py` | follow-up rules after replies (out of office, apply on our site, polite no) |
| `tools/check_msgs.py` | holds every planned email and note to your writing rules |
| `tools/email_audit.py` | read-only audit of Mail: needs-reply.html |
| `tools/build_today.py`, `tools/build_today_focus.py` | TODAY-all.html and TODAY.html |
| `tools/build_tracker.py`, `tools/morning.py` | OUTREACH-TRACKER.html and MORNING.md |
| `tools/scan_postings.py` | read-only scan of public job-board APIs |
| `tools/kit.py` | settings loader and shared safety checks; `--check` |
| `research/night-research-prompt.md` | the research shift's instructions |
| `launchd/` | job templates (`USERNAME` is filled in by `install.sh`) and the runners |
| `jev-config/` | templates and `jev-fixes.patch` for jev-job-search |
| `logs/`, `needs-me.md`, the `.html` pages, `MORNING.md` | generated; not committed |
