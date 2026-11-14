# Job search agents: setup guide

A kit that finds companies, drafts personal emails and job applications, and tracks replies, for a job search in any city or country you choose. It runs on your own Mac.

It works in **prepare mode**: every email is saved to your Mail Drafts and you send it yourself. Nothing goes out on its own.

## What you need

| Item | Cost | Notes |
| --- | --- | --- |
| A Mac with the Mail app | Free | macOS only. Keep it plugged in and awake on nights it runs |
| Python 3.9+ and git | Free | Come with Apple's Command Line Tools (step 1) |
| Your personal email account in Mail | Free | Never your work account |
| Your CV as a PDF | | The version you want employers to see |
| Claude Code with a paid Claude plan (Pro or Max) | Plan price | Only for the overnight research (step 5). See claude.com/pricing |
| An OpenRouter key | A few cents per run | Only if you use the form-filling tool JEV (step 7) |

Set aside about an hour for steps 1 to 4.

## What's in the kit

| Part | What it does |
| --- | --- |
| Email planner and sender | Turns each email you approve into a Mail draft at your send time; drafts a follow-up 7 days after you mark one sent |
| Message checker | Checks every email against your facts, never-apply list and writing rules before it can be drafted |
| Morning pages | MORNING.md (summary), TODAY.html (drafts to review), the tracker |
| Email audit | Reads your inbox and lists who you owe a reply. Read-only |
| Postings scan | Checks company job boards for new roles |
| Research shift | Overnight, finds new companies in your regions and writes drafts (needs Claude Code) |

## Step 1: get the kit

1. Open Terminal. Run `xcode-select --install` and accept. If `python3 --version` already prints 3.9 or higher, skip this.
2. Download the kit into your home folder:
   ```
   git clone https://github.com/dudailia/job-agents-kit.git ~/job-agents-kit
   cd ~/job-agents-kit
   ```
   If you were sent a ZIP instead, unzip it, rename the folder to `job-agents-kit`, move it to your home folder, and run `cd ~/job-agents-kit`.

Every command below runs in Terminal, inside `~/job-agents-kit`.

## Step 2: Mail and your profile

1. **Mail.** Open Mail and add the account you'll send from (Mail, Settings, Accounts). Note its name exactly as the list shows it, for example iCloud or Gmail.
2. **Copy the templates:**
   ```
   cp profile/settings.example.json profile/settings.json
   cp profile/facts.example.md profile/facts.md
   ```
3. **Fill in settings.json** (`open -e profile/settings.json`):

| Setting | What to put | Example |
| --- | --- | --- |
| `candidate` | Your name, email, and availability exactly as emails should state it | "available from March 2027, one month's notice" |
| `timezone` | Your Mac's time zone | `Europe/London`, `America/New_York` |
| `regions` | Each place you'll write to: time zone, send window, and the exact work-rights sentence for it | London, 08:00 to 08:50, "I have the right to work in the UK" (only if true) |
| `mail.account` | The account name from item 1 | `Gmail` |
| `writing` | Your writing rules | British spelling, plain, no buzzwords |

4. **Fill in facts.md** with the only facts about you that may ever be used: jobs with dates, education, skills, links, work rights. Nothing outside this file can appear in an email.
5. **Fill in profile/never-apply.md**, one employer per line (`- Name`). Put your current employer first.
6. **Check it:** `python3 -I tools/kit.py --check` prints the mode (prepare) and any warning. Fix every warning.

Stuck on a field? Use prompt A at the end of this guide.

## Step 3: first test email

1. Make a first email from the example:
   ```
   cp data/emails.example.json data/emails.json
   open -e data/emails.json
   ```
   Set `"to"` to **your own address**, keep `"approved": false`, and change the sign-off from "Alex Example" to your name.
2. Check it: `python3 -I tools/check_msgs.py` must end with "problems: 0".
3. Draft it now: `python3 -I tools/night_send.py --draft-now example-1`
4. macOS asks whether Terminal may control **Mail** and **System Events**. Click **Allow** (or System Settings, Privacy & Security, Automation).
5. Open Mail, go to Drafts. The email is there, addressed to you. Nothing was sent.

## Step 4: morning pages and daily routine

Build the pages once by hand:

```
python3 -I tools/build_today_focus.py && python3 -I tools/build_tracker.py && python3 -I tools/morning.py
open TODAY.html
```

Once the night is scheduled (step 6), they rebuild at 07:30. Your 20 to 30 minutes a day:

- Read MORNING.md.
- Answer anything overdue in the email audit list.
- Read the new drafts in TODAY.html. Approve one by setting `"approved": true` for it in `data/emails.json`. Leave out any you wouldn't send yourself.
- Open Mail's Drafts, check each approved draft, and send it yourself.
- Record each one sent: `python3 -I tools/sender.py --mark-sent <id>`. Its follow-up is drafted 7 days later.
- Send 10 to 15 LinkedIn notes from TODAY.html by hand.

## Step 5: overnight research (Claude Code)

1. Install Claude Code from claude.com/claude-code.
2. In `~/job-agents-kit`, run `claude` once and sign in with your Claude account (a paid plan, not an API key).
3. Use prompt B below to point the research at your cities, roles and sources.

It only uses company sites and the job boards companies run themselves (Ashby, Greenhouse, Lever, Workable, careers pages), so links are live and emails reach a person.

All Claude Code windows share your plan's usage limit. Close the ones you aren't using before bed.

## Step 6: schedule the night

```
zsh launchd/install.sh            # writes five jobs, starts nothing
zsh launchd/install.sh --load     # when you're ready
zsh launchd/install.sh --unload   # removes them all
```

| Time (your Mac's time zone) | Job |
| --- | --- |
| Every 15 minutes, inside each region's send window | Drafts approved emails and due follow-ups |
| 00:40 | Research shift |
| 04:05 | Postings scan |
| 05:15 | Email audit |
| 07:30 | Morning pages |

The first night, macOS asks whether `zsh` may control Mail. Allow it.

## Step 7: job application forms with JEV (optional)

JEV is a separate open-source tool that fills online application forms. Set it up only after steps 1 to 6 work.

1. `git clone https://github.com/qbeka/jev-job-search.git ~/jev-job-search`
2. Follow `jev-config/README.md` in the kit: apply the patch, copy the templates into JEV's `data/` folder, and fill in **your own** `profile.json`, including `workAuthorization` and the visa fields.
3. Rehearse: `npx jev apply --dry --count 3`. Read every answer on every form before any run that submits.

Before approving a form, check the job's location, the right-to-work and sponsorship answers, the salary, and that no marketing or talent-pool box is ticked. JEV can't solve CAPTCHAs or read some portals (Workday, SuccessFactors); do those by hand.

## Safety rules

- **Prepare mode by default.** Emails become drafts you send yourself; JEV waits for your approval on each form.
- **Kill switch.** `touch ~/STOP-AGENTS` stops every job. `rm ~/STOP-AGENTS` resumes. `logs/SENDER-PAUSED` and `logs/MAIL-LOGIN-ERROR` pause drafting until you delete them.
- **No invented facts.** Every claim must come from `facts.md`.
- **Work rights word for word.** Emails use exactly the sentence you set for each region.
- **Never-apply is employer-wide.** A listed company is skipped wherever it appears.
- **Keep it away from your employer.** Personal laptop, personal email, and on LinkedIn set job-seeking to recruiters only.
- **Stay human.** Short, personal, one-to-one emails to addresses companies publish. No bought lists. Check your country's rules on email outreach (in the UK, the ICO's guidance).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Night run stopped early | Usage limit. Close idle Claude Code windows; it resumes after the reset |
| Drafts stuck, "SIGN IN TO MAIL AGAIN" | Sign your account in again in Mail settings, clear the Outbox, delete `logs/MAIL-LOGIN-ERROR` |
| Mail pops up during the day | Ask Claude Code which job opens Mail outside the send window and fix it |
| A form answer is wrong | Fix it in your profile, then ask JEV to delete the saved answer it reused |
| Email audit lists newsletters | Tell Claude Code which emails and ask it to fix the rule |
| Nothing ran overnight | The Mac slept, or `~/STOP-AGENTS` exists |

## Prompts for Claude Code

Run `cd ~/job-agents-kit` then `claude`, and paste the one you need.

**A. Help me fill in my profile**
```
Read README.md and SETUP.md. Interview me one group at a time to fill profile/settings.json, profile/facts.md and profile/never-apply.md: name and email, availability and notice period, time zone, the regions I'll write to (time zone, send window, exact work-rights sentence for each), Mail account name, writing rules, then my facts (jobs with dates, education, skills, links) and employers never to contact, my current employer first. Never fill a gap with a guess; ask me. Then run python3 -I tools/kit.py --check and fix any warning with me.
```

**B. Point the research at my search**
```
Fill research/night-research-prompt.md from profile/settings.json and profile/facts.md: my regions and cities, role titles and seniority, and sources (company careers pages, Ashby, Greenhouse, Lever, Workable; portfolios of investors active in my regions; recent funding rounds there). No aggregators. Skip every employer in profile/never-apply.md. Keep prepare mode. Show me three sample drafts and run tools/check_msgs.py on them before anything is scheduled.
```

**C. Add another city or country**
```
Add a region for [city, country] to profile/settings.json: its time zone, a 08:00 to 08:50 local send window, and ask me for the exact work-rights sentence for it. Update research/night-research-prompt.md to include it, then run python3 -I tools/kit.py --check.
```

**D. Something broke**
```
This failed: [paste the error]. Read README.md and SETUP.md, find the cause, and fix it without sending anything, without touching my Mail beyond reading, and without changing my profile files unless I agree.
```
