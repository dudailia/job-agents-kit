# job-agents-kit

**New here? Start with the [setup guide](GUIDE.md)**: what you need, what it costs, and every step from zero.

A kit for a careful, mostly unattended job search on a Mac. While you sleep:

- a research shift (Claude Code) finds firms and postings and plans emails, using only facts you wrote down;
- a checker holds every planned email to your own writing rules;
- a night job saves the emails that are due to Mail's Drafts, inside each region's morning window;
- a read-only email audit lists the emails that need an answer from you.

In the morning you get `MORNING.md`, `TODAY.html` (what to do by hand), `OUTREACH-TRACKER.html` and `needs-reply.html`.
`jev-config/` adds templates and four fixes for [jev-job-search](https://github.com/qbeka/jev-job-search), which fills in
application forms.

## Before you start

- **macOS and Apple Mail only.** Emails are drafted and sent through Mail.app with AppleScript, and the jobs are run by
  macOS launchd. It does not work on Windows, Linux, or with Gmail or Outlook in a browser. You can still use a Gmail or
  Outlook account, as long as it is added to Mail.app on the Mac. The Mac must be on, and you signed in, at night.
- **Prepare mode is the default: nothing is ever sent until you change it.** In prepare mode every due email is only
  saved to Mail's Drafts, for you to read and send yourself. Send mode (`send.mode: "send"` in your settings) sends only
  the emails you marked `"approved": true`. Everything else is still only drafted.
- **Everything about you is yours to fill in.** The kit ships with a fictional example person ("Alex Example").
  Before any real use, write your own settings, facts and never-apply list. If you use jev-job-search, write your own
  `profile.json` too, including the right-to-work and visa answers (`workAuthorization`: where you may work without
  sponsorship, where you will need it, your visa type). Never copy someone else's: forms are answered from these files.
- **Review before you switch anything on.** Read every planned email before you approve it. For jev-job-search,
  rehearse (`--dry`) and read every form answer before any run that submits. Only switch to send mode when nothing you
  read was wrong.

## What it costs

| | Cost |
|---|---|
| The kit itself | Free. Python standard library only, nothing to buy or install with pip. |
| Apple Mail, launchd | Free, part of macOS. |
| Research shift and email triage | Runs on [Claude Code](https://claude.com/claude-code) with a paid Claude plan (Pro or Max; see claude.com/pricing). It refuses to run on an API key, so nothing is billed per call. A nightly research shift uses a large share of a plan's usage limits; Pro may hit them, Max is more comfortable. Without Claude Code, the sender, checker, pages and tracker still work and the audit falls back to keyword triage. |
| jev-job-search (optional) | Free code. Its optional OpenRouter key costs a few cents per search or run. |

## Setup

From a Mac with nothing installed. Each step says what it needs. Commands run in Terminal.

1. **Python and git.** Run `xcode-select --install` and accept (Apple's Command Line Tools: `python3` 3.9 or newer, and
   `git`). If `python3 --version` already works, skip this.
2. **Get the kit.** Clone the repository you were invited to (GitHub shows the URL under the green **Code** button),
   into your home folder:
   ```bash
   git clone <the repository URL> ~/job-agents-kit
   cd ~/job-agents-kit
   ```
3. **Mail.** Open Mail.app and add the account you will send from (Mail > Settings > Accounts). Note its name exactly
   as the list shows it, for example `iCloud` or `Work`.
4. **Your profile.**
   ```bash
   cp profile/settings.example.json profile/settings.json
   cp profile/facts.example.md profile/facts.md
   ```
   Open both in a text editor (`open -e profile/settings.json`). In `settings.json`, replace the example person:
   - `candidate`: your name and email, and `availability` written exactly as your emails must state it.
   - `timezone`: your Mac's time zone (default `Europe/London`).
   - `regions`: where you will write to. Each region has a time zone, a send window (default 08:00 to 08:50 local time)
     and the one work-rights sentence an email there must contain.
   - `mail.account`: the account name from step 3.
   - `writing`: your writing rules.

   In `facts.md`, write the only facts about you that may ever be used, your work rights included. In
   `profile/never-apply.md`, list the employers never to contact (`- Name` per line). Then check:
   ```bash
   python3 -I tools/kit.py --check        # prints the mode (prepare) and any warning
   ```
5. **A first planned email.** Start from the example. For this first try, put **your own address** in `"to"`, so the
   draft is addressed to you:
   ```bash
   cp data/emails.example.json data/emails.json
   open -e data/emails.json               # set "to" to your own address; keep "approved": false
   python3 -I tools/check_msgs.py         # must end with "problems: 0"; fix what it lists
   ```
   The example's sign-off is "Alex Example". Once your own name is in the settings, change the sign-off to your name too,
   or the checker will say so.
6. **A first prepare-mode run.** This saves that one email to Mail's Drafts now, whatever the time. It never sends:
   ```bash
   python3 -I tools/night_send.py --draft-now example-1
   ```
   macOS asks whether Terminal may control **Mail** and **System Events**: click **Allow** (System Settings > Privacy &
   Security > Automation, if you missed it). Mail opens hidden and the draft appears in your account's Drafts. Nothing
   was sent.
7. **The morning pages.**
   ```bash
   python3 -I tools/build_today_focus.py && python3 -I tools/build_tracker.py && python3 -I tools/morning.py
   open TODAY.html
   ```
8. **Claude Code, for the research shift and email triage** (optional, paid plan: see the costs above). Install it from
   [claude.com/claude-code](https://claude.com/claude-code), run `claude` once and sign in with your Claude account (not
   an API key). The research shift reads `research/night-research-prompt.md`.
9. **Schedule the night.** This writes five jobs to `~/Library/LaunchAgents` with your username and folder, and starts
   nothing:
   ```bash
   zsh launchd/install.sh                 # then, when you are ready:
   zsh launchd/install.sh --load
   ```
   The jobs run in your Mac's local time: the night job every 15 minutes, research at 00:40, a postings scan at 04:05,
   the email audit at 05:15 and the morning summary at 07:30. The first night, macOS asks again whether `zsh` may
   control Mail: allow it, or the night job cannot draft. `zsh launchd/install.sh --unload` removes them all.
10. **Applications with jev-job-search** (optional). Follow `jev-config/README.md`: apply the patch, copy the templates
    into its `data/`, and fill in **your own** `profile.json`, including `workAuthorization` and the visa fields. Then
    rehearse with `npx jev apply --dry --count 3` and read every answer before any run that submits.

**Every morning:** read `MORNING.md` and `TODAY.html`. Approve a planned email by setting `"approved": true` in
`data/emails.json`. In prepare mode, send the drafts yourself from Mail, then record each one with
`python3 -I tools/sender.py --mark-sent <id>`, so its follow-up is drafted 7 days later. See [SETUP.md](SETUP.md) for
the safety switches and every file.

## Stop at any time

`touch ~/STOP-AGENTS` stops every job at once (delete the file to resume). `logs/SENDER-PAUSED` and
`logs/MAIL-LOGIN-ERROR` pause sending until you delete them.
