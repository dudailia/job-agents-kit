# One-shot night run (launchd com.USERNAME.jobkit-night, every 15 minutes). It decides what is due from the files alone,
# and touches Mail only when something is due. Safety rules:
#  - ~/STOP-AGENTS exists -> exit at once, touch nothing.
#  - logs/SENDER-PAUSED or logs/MAIL-LOGIN-ERROR exists -> exit (delete the file to resume).
#  - Mail only inside your sender hours (settings.hours: night_start to sender_end, your time zone).
#  - Each email goes on a weekday, inside its region's window in the recipient's local time (settings.regions, default
#    08:00-08:50), at most send.per_run per run, send.daily_max per day and send.gap_minutes apart.
#  - Never to an employer in profile/never-apply.md, never twice to one address.
#  - PREPARE-ONLY is the default (settings.send.mode = "prepare"): every due email is saved to Mail's Drafts and nothing is
#    sent. In "send" mode only emails with "approved": true are sent; the rest are still only drafted.
#  - No loops and no retries: Mail is launched at most once per run, hidden ("launch", never "activate"); if any Mail call
#    fails, the error is logged and the run exits. A lock stops two runs from overlapping.
#  - Before every Mail call the frontmost app is recorded; afterwards Mail is hidden and that app gets the front back.
#    If this run launched Mail, it quits Mail at the end. No draft is ever deleted.
# usage: python3 -I tools/night_send.py [--dry] [--force-day]
#   --dry        any time of day: launches Mail once (hidden), runs one read-only call, restores focus, quits Mail. Sends and drafts nothing.
#   --force-day  behave as if outside the sender hours (test that nothing touches Mail).
import datetime as dt, fcntl, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
LOG = f'{K.LOGS}/night.log'
DRY, FORCE_DAY = '--dry' in sys.argv, '--force-day' in sys.argv
def log(s): open(LOG, 'a').write(f"{K.now():%F %T} {'[dry] ' if DRY else ''}{s}\n")
def mail_running(): return subprocess.run(['pgrep', '-x', 'Mail'], capture_output=True).returncode == 0

if os.path.exists(K.STOPFILE): log('STOP-AGENTS present: exit'); sys.exit(0)
now = K.now()
if '--draft-now' in sys.argv:  # a first try at any hour: save ONE planned email to Drafts now. Never sends, whatever the mode.
    import subprocess as _sp, sender as S
    xid = sys.argv[sys.argv.index('--draft-now') + 1] if len(sys.argv) > sys.argv.index('--draft-now') + 1 else ''
    x = next((y for y in K.emails() if y.get('id') == xid), None)
    if not x: sys.exit(f'usage: night_send.py --draft-now <id>   (no email with id "{xid}" in {K.EMAILS})')
    if not K.S['mail'].get('account'): sys.exit('set mail.account in profile/settings.json first')
    if K.blocked(x['company']): sys.exit(f"not drafted: {x['company']} is covered by never-apply.md ({K.blocked(x['company'])})")
    import check_msgs
    errs = check_msgs.check_email(x)
    if errs: sys.exit('not drafted, fix these first:\n- ' + '\n- '.join(errs))
    started = _sp.run(['pgrep', '-x', 'Mail'], capture_output=True).returncode != 0
    if started:
        f = _sp.run(['osascript', '-e', K.FRONT], capture_output=True, text=True).stdout.strip()
        _sp.run(['osascript', '-e', 'launch application "Mail"'], capture_output=True, timeout=60); time.sleep(15)
        _sp.run(['osascript', '-', f], input=K.RESTORE, capture_output=True, text=True, timeout=30)
    r = S.draft(x['to'], x['subject'], x['body'], x.get('attachments', []))
    S.outlog(x, 'email', 'drafted'); log(f'DRAFTED (draft-now) email {x["company"]} <{x["to"]}>: {r}')
    print(f'{r}: "{x["subject"]}" to {x["to"]} is in {K.S["mail"]["account"]} > {K.S["mail"]["drafts"]}. Nothing was sent.')
    if started: _sp.run(['osascript', '-e', 'tell application "Mail" to quit'], capture_output=True, timeout=60)
    sys.exit(0)
END = K.S['send'].get('end_date')
if END and now.date() > dt.date.fromisoformat(END): log(f'past send.end_date {END}: outreach finished, Mail not touched'); sys.exit(0)
if FORCE_DAY or (not K.sender_hours(now) and not DRY):  # --dry works at any hour: it only counts drafts
    log(f'outside sender hours{" (forced)" if FORCE_DAY else ""}: Mail not touched; Mail running={mail_running()}'); sys.exit(0)
if os.path.exists(K.PAUSE): log(f'paused ({open(K.PAUSE).read().strip()[:200]}): exit'); sys.exit(0)
if os.path.exists(K.LOGINF): log(f'paused: Mail login error ({open(K.LOGINF).read().strip()[:200]}): exit'); sys.exit(0)
if not K.S['mail'].get('account'): log('mail.account is not set in profile/settings.json: exit'); sys.exit(0)
lockf = open(f'{K.LOGS}/night.lock', 'w')
try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: log('another run is still going: exit'); sys.exit(0)

import sender as S, fu_rules as FR
MAX_PER_RUN, LATE_MAX = K.S['send']['per_run'], dt.timedelta(minutes=K.S['send']['late_minutes'])

# ---- what is due (no Mail needed to decide) ----
E = K.emails(); state = K.load_json(S.STATE, {}); moved = False; todo = []
for t, kind, x in S.due(E, now):  # skip or move without Mail
    why = None
    if now - t > LATE_MAX or not K.slot_ok(now, x): why = 'missed its window'
    elif K.blocked(x['company']): why = f"employer in never-apply.md ({K.blocked(x['company'])})"
    elif kind == 'email' and S.addr_done(x['to']): why = 'address already emailed'
    elif kind == 'email' and x.get('second_of') and x['second_of'] in S.replied_ids(): why = 'the firm replied to the first contact'
    if why:
        log(f'SKIP {kind} {x["company"]}: {why}')
        if kind == 'email' and why == 'missed its window':  # next weekday, same local time
            lt = t.astimezone(K.tz_of(x)) + dt.timedelta(days=1)
            while lt.weekday() >= 5: lt += dt.timedelta(days=1)
            x['slot'] = lt.replace(tzinfo=None).isoformat(timespec='minutes'); moved = True
        elif kind == 'email':
            x['hold'] = why; moved = True; S.outlog(x, kind, f'not sent: {why}')
        else:
            state.setdefault('fu_skipped', []).append(x['id']); S.outlog(x, kind, f'not sent: {why}')
        continue
    todo.append((t, kind, x))
if moved: K.save_json(K.EMAILS, E)
K.save_json(S.STATE, state)
room = max(0, S.DAILY_MAX - S.sent_today()); todo = todo[:min(MAX_PER_RUN, room)]
checks = [c for c in K.S['send'].get('inbox_checks', []) if re.match(r'^\d\d:\d\d$', c)]
inbox_due = any(now.hour == K.hm(c).hour and now.minute // 15 == K.hm(c).minute // 15 for c in checks) \
    or ('before follow-ups' in K.S['send'].get('inbox_checks', []) and any(k == 'followup' for _, k, _ in todo))
drafts_due = [q for q in FR.load(FR.DRAFTQ, []) if q.get('status') == 'pending'][:3]  # thank-you drafts: saved, never sent
if DRY: todo, inbox_due, drafts_due = [], False, []
if not todo and not inbox_due and not drafts_due and not DRY: log(f'nothing due (sent today {S.sent_today()}): Mail not touched'); sys.exit(0)

# Mail login health check before any send (read-only): messages already waiting in the Outbox, or no new mail in the Inbox
# for mail.stale_inbox_hours, or login errors in Mail's own log of the last 20 minutes.
HEALTH = """on run argv
set acc to item 1 of argv
set ibox to item 2 of argv
tell application "Mail"
with timeout of 90 seconds
set ob to 0
try
  set ob to ob + (count of messages of mailbox "Outbox" of account acc)
end try
try
  set ob to ob + (count of messages of outbox)
end try
set ageS to ""
try
  set d to date received of message 1 of mailbox ibox of account acc
  set ageS to ((current date) - d) as integer
end try
return (ob as text) & "|" & ageS
end timeout
end tell
end run"""
AUTH_RX = r'(HTTP|status|code)\W{0,3}401(?![0-9])|unauthori[sz]ed|authenticat\w* (fail|error|required)|invalid_grant|interaction_required|wrong password|password (is )?(incorrect|required)|credentials? (are |is )?(invalid|missing|rejected|expired)|sign[ -]?in (required|again)|reauthenticat|token (expired|revoked)'
def mail_log_check():
    try:
        r = subprocess.run(['/usr/bin/log', 'show', '--style', 'compact', '--last', '20m', '--predicate',
                            'process == "Mail" AND (category BEGINSWITH "EWS" OR category CONTAINS[c] "account" OR category CONTAINS[c] "auth")'],
                           capture_output=True, text=True, timeout=90).stdout.splitlines()
    except Exception as e: return None, f'log check skipped ({e})'
    auth = [l for l in r if re.search(AUTH_RX, l, re.I) and 'EDMessageAuthenticator' not in l and 'ECHeaderAuthentication' not in l]
    fails = sum(1 for l in r if 'failed to connect with error' in l); ok = sum(1 for l in r if 'Receiving:' in l)
    if auth: return f'the Mail log shows login errors ({len(auth)} in 20 min, e.g. "{auth[-1][24:160].strip()}")', ''
    if fails >= 5 and ok == 0: return f'the mail server has not answered for 20 min ({fails} failed connections, no responses)', ''
    return None, f'log: {fails} failed connections, {ok} responses, 0 login errors'
def login_error(why):
    msg = f'{K.now():%a %d %b %H:%M}: {why}.'
    open(K.LOGINF, 'w', encoding='utf-8').write(msg)
    S.needs_top(f"\n- ⚠️ **SIGN IN TO MAIL AGAIN**: {msg} Sending paused; delete `logs/MAIL-LOGIN-ERROR` after signing in.\n")
    try: subprocess.run([sys.executable, '-I', f'{K.ROOT}/tools/build_tracker.py'], capture_output=True, timeout=120)
    except Exception as e: log(f'tracker update failed: {e}')
    log(f'MAIL LOGIN ERROR: {why}; paused (logs/MAIL-LOGIN-ERROR)')

DRAFTCOUNT = """on run argv
tell application "Mail" to count (messages of mailbox (item 2 of argv) of account (item 1 of argv))
end run"""

# ---- Mail session: launched at most once, never relaunched ----
launched = False
def front():
    try: return subprocess.run(['osascript', '-e', K.FRONT], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ''
def call(script, *args, timeout=180):
    if not mail_running(): raise RuntimeError('Mail is not running (not relaunching)')
    f = front()
    try: r = subprocess.run(['osascript', '-', *args], input=script, capture_output=True, text=True, timeout=timeout)
    finally: subprocess.run(['osascript', '-', f], input=K.RESTORE, capture_output=True, text=True, timeout=30)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()
S.osa = call  # the reply check and send/draft helpers in sender.py go through the same no-relaunch wrapper
def finish(code=0):
    if launched and mail_running():
        f = front(); subprocess.run(['osascript', '-e', 'tell application "Mail" to quit'], capture_output=True, timeout=60)
        subprocess.run(['osascript', '-', f], input=K.RESTORE, capture_output=True, text=True, timeout=30)
    log(f'run ended (Mail launched by this run: {launched}; Mail running now: {mail_running()})'); sys.exit(code)

if not mail_running():
    f = front(); subprocess.run(['osascript', '-e', 'launch application "Mail"'], capture_output=True, timeout=60); launched = True
    time.sleep(15)  # one wait, one check: no retry loop
    subprocess.run(['osascript', '-', f], input=K.RESTORE, capture_output=True, text=True, timeout=30)
    if not mail_running(): log('Mail did not start: exit'); finish(1)
try:
    acc = K.S['mail']['account']
    if DRY:
        n = call(DRAFTCOUNT, acc, K.S['mail']['drafts'])
        log(f"dry: Drafts in {acc} = {n}; front app now: {front()}")
        finish(0)
    sending = [z for z in todo if K.MODE == 'send' and z[2].get('approved')]
    if sending and K.S['mail'].get('health_check', True):  # never send into a broken login
        h = call(HEALTH, acc, K.S['mail']['inbox'], timeout=120).split('|'); ob = int(h[0] or 0)
        age = int(h[1]) if len(h) > 1 and h[1].strip().lstrip('-').isdigit() else None
        why, note = mail_log_check()
        if ob: why = f"{ob} message(s) were already waiting in Mail's Outbox before this run (the server is not sending)"
        elif age is not None and age > K.S['mail']['stale_inbox_hours'] * 3600: why = why or f'no new mail has reached the Inbox for {age // 3600} h'
        if why: login_error(why); finish(1)
        log(f"health ok: Outbox 0, newest mail {age // 60 if age is not None else '?'} min old, {note}")
    if inbox_due:
        rs = S.locked_replies(E); log(f"inbox checked: {len(rs.get('seen', []))} seen, {len(rs.get('replied', []))} replied, {len(rs.get('calls', []))} call offers")
    sent = []
    for t, kind, x in todo:
        if kind == 'followup' and x['id'] in FR.overrides()[0]: S.outlog(x, kind, 'replied/cancelled: follow-up skipped'); continue
        subj = x['subject'] if kind == 'email' else x['followup_subject']; body = x['body'] if kind == 'email' else x['followup_body']
        att = x.get('attachments', []) if kind == 'email' else []
        if K.MODE == 'send' and x.get('approved'):
            S.send(x['to'], subj, body, att); S.outlog(x, kind, 'sent'); log(f'SENT {kind} {x["company"]} <{x["to"]}> "{subj}"'); sent.append(subj)
        else:  # prepare-only: a draft in Mail, never sent
            r = S.draft(x['to'], subj, body, att); S.outlog(x, kind, 'drafted')
            log(f'DRAFTED {kind} {x["company"]} <{x["to"]}> "{subj}": {r} ({"prepare mode" if K.MODE == "prepare" else "not approved"})')
        time.sleep(20)
    if drafts_due:  # one try each, logged; a failure is recorded and never retried in this run
        q = FR.load(FR.DRAFTQ, [])
        for d in drafts_due:
            try: r = S.draft(d['to'], d['subject'], d['body']); st = 'saved' if r in ('saved', 'exists') else f'failed: {r}'
            except Exception as e: st = f'failed: {str(e)[:120]}'
            for qq in q:
                if qq['key'] == d['key']: qq['status'] = st; qq['done'] = f'{K.now():%F %H:%M}'
            log(f"reply draft {d['company']} <{d['to']}> \"{d['subject']}\": {st}")
            if st == 'saved': S.needs_top(f"\n- ✅ Thank-you draft for **{d['company']}** is in Drafts, subject \"{d['subject']}\". Not sent: review and send it yourself.\n")
        K.save_json(FR.DRAFTQ, q)
    if sent:
        time.sleep(60)  # one Outbox check for this run's messages
        stuck = [s for s in sent if int(call(S.OUTBOX, s) or 0)]
        if stuck:
            open(K.PAUSE, 'w').write(f'{now:%F %H:%M} still in Outbox: {stuck}')
            S.needs_top(f"\n- ⚠ Still in Mail's Outbox a minute after sending ({now:%F %H:%M}): {stuck}. Sending paused; delete `logs/SENDER-PAUSED` to resume.\n")
            log(f'STUCK in Outbox: {stuck}; paused')
            login_error(f"{len(stuck)} message(s) still in Mail's Outbox a minute after sending")
except Exception as e:
    log(f'ERROR (no retry): {e}')
    finish(1)
finish(0)
