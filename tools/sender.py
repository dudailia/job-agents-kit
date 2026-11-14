# The sender's building blocks, used by tools/night_send.py (the launchd job that actually sends or drafts):
#  - AppleScripts that send or save a draft through Mail invisibly (the compose window is never shown and is closed after),
#    count a subject in the Outbox, and list the Inbox. Mail is never activated; tools/night_send.py launches it hidden.
#  - the outreach log (data/outreach-log.csv), the daily cap and the gap between sends,
#  - the reply check: a reply from the recipient's domain cancels the follow-up, is written to the top of needs-me.md with a
#    suggested answer (never sent), and an out-of-office or "apply on our site" reply moves or cancels the follow-up.
# It never answers, moves or deletes any received mail, and it never deletes a draft.
# usage: python3 -I tools/sender.py --due              list what is due now (reads files only, never touches Mail)
#        python3 -I tools/sender.py --mark-sent <id> ["YYYY-MM-DD HH:MM"]
#            record that you sent an email by hand from Drafts (prepare mode), so its follow-up gets scheduled
import csv, datetime as dt, fcntl, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
import fu_rules as FR

D = K.ROOT; LOG = f'{K.LOGS}/sender.log'; OUT = K.OUTLOG; STATE = f'{K.LOGS}/sender-state.json'; RSTATE = FR.RSTATE
COLS = ['date', 'company', 'person', 'email', 'source_url', 'subject', 'language', 'kind', 'status']
DAILY_MAX, GAP_MIN, FOLLOW_DAYS = K.S['send']['daily_max'], K.S['send']['gap_minutes'], K.S['send']['follow_up_days']
ACCOUNT = K.S['mail']['account']; FROM = K.sender_line()
CALL = re.compile(r'\b(call|chat|meet|meeting|talk|zoom|teams|google meet|calendly|interview|schedule|slot)\b', re.I)
AUTO = re.compile(r"automatic reply|auto[- ]?reply|out of (the )?office|\bOOO\b|currently on (holiday|vacation|leave)|will not be forwarded|"
                  r"ticket (number|#|id)|this is an automated|we.ve received your|we have received your|we.ve got your message|"
                  r"request (has been )?received|has been received|zendesk|freshdesk|helpdesk|support team will|do not reply", re.I)
# the reply's own text, without the quoted original (our own email mentions a call, which made a decline look like a call offer)
QUOTE = re.compile(r'\n\s*(?:>|-{2,}\s*Original|From:|Sent:|Van:|Verzonden:|Von:|Gesendet:|De:|Envoy|On .{0,120}wrote:|\S.{0,80} schrieb|Le .{0,80}a écrit)', re.I)
DECLINE = re.compile(r"unfortunately|no room|not (able|in a position)|no (open|current) (positions?|roles?|vacanc(y|ies)|internships?)( for interns)?|"
                     r"no (internship|intern) (positions?|places?|openings?)|not (currently )?(hiring|offer)|don.t (have|offer)|do not (have|offer)", re.I)
OOO = re.compile(r"out of (the )?office|\bOOO\b|on (holiday|vacation|leave|annual leave)|currently away|away from the office|back on|return(ing)? on|abwesen|urlaub", re.I)
def own_text(body): return QUOTE.split('\n' + body, 1)[0]

def log(s):
    line = f"{K.now():%F %T} {s}"; print(line, flush=True); open(LOG, 'a').write(line + '\n')

# argv: to, subject, body, from, then attachment paths. visible:false + close keep every window hidden.
SEND = '''on run argv
set toAddr to item 1 of argv
set subj to item 2 of argv
set bod to item 3 of argv
set fromAddr to item 4 of argv
tell application "Mail"
set m to make new outgoing message with properties {subject:subj, content:bod, visible:false}
if fromAddr is not "" then set sender of m to fromAddr
tell m to make new to recipient at end of to recipients with properties {address:toAddr}
if (count of argv) > 4 then
  repeat with i from 5 to count of argv
    tell content of m to make new attachment with properties {file name:((POSIX file (item i of argv)) as alias)} at after the last paragraph
  end repeat
  delay 5
end if
send m
try
close (every window whose name is subj) saving no
end try
end tell
return "sent"
end run'''
# argv: to, subject, body, from, account, drafts mailbox, then attachment paths. A draft with the same subject is never saved twice.
SAVE = '''on run argv
set toAddr to item 1 of argv
set subj to item 2 of argv
set bod to item 3 of argv
set fromAddr to item 4 of argv
set acc to item 5 of argv
set dbox to item 6 of argv
tell application "Mail"
set mb to mailbox dbox of account acc
if (count of (messages of mb whose subject is subj)) > 0 then return "exists"
set m to make new outgoing message with properties {subject:subj, content:bod, visible:false}
if fromAddr is not "" then set sender of m to fromAddr
tell m to make new to recipient at end of to recipients with properties {address:toAddr}
if (count of argv) > 6 then
  repeat with i from 7 to count of argv
    tell content of m to make new attachment with properties {file name:((POSIX file (item i of argv)) as alias)} at after the last paragraph
  end repeat
  delay 5
end if
save m
delay 4  -- without the pause, closing the hidden window can drop the draft
try
close (every window whose name is subj) saving yes
end try
end tell
return "saved"
end run'''
OUTBOX = '''on run argv
tell application "Mail"
set n to 0
repeat with mb in (every mailbox whose name is "Outbox")
  set n to n + (count (messages of mb whose subject is (item 1 of argv)))
end repeat
try
  set n to n + (count (messages of outbox whose subject is (item 1 of argv)))
end try
return n
end tell
end run'''
# argv: account, inbox mailbox. One line per message: id, sender, subject, date (the newest 80).
INBOX = '''on run argv
set acc to item 1 of argv
set ibox to item 2 of argv
tell application "Mail"
check for new mail for account acc
delay 5
set mb to mailbox ibox of account acc
set k to count of messages of mb
if k > 80 then set k to 80
if k = 0 then return ""
set ss to subject of messages 1 thru k of mb
set ff to sender of messages 1 thru k of mb
set dd to date received of messages 1 thru k of mb
set ii to message id of messages 1 thru k of mb
set out to ""
repeat with i from 1 to k
  set d to item i of dd
  set out to out & (item i of ii) & tab & (item i of ff) & tab & (item i of ss) & tab & ((year of d) as text) & "-" & text -2 thru -1 of ("0" & ((month of d as integer) as text)) & "-" & text -2 thru -1 of ("0" & ((day of d) as text)) & " " & (time string of d) & linefeed
end repeat
return out
end tell
end run'''
BODY = '''on run argv
set acc to item 1 of argv
set ibox to item 2 of argv
set i to (item 3 of argv) as integer
set mid to item 4 of argv
tell application "Mail"
set mb to mailbox ibox of account acc
set n to count of messages of mb
set a to i - 3
if a < 1 then set a to 1
set b to i + 5
if b > n then set b to n
repeat with j from a to b
  set m to message j of mb
  if (message id of m) is mid then return content of m
end repeat
return "(could not re-find the message)"
end tell
end run'''

def osa(script, *args, timeout=180):
    """Runs one AppleScript against Mail with the frontmost app given back afterwards. tools/night_send.py replaces this with
    its own wrapper that refuses to relaunch Mail."""
    try: front = subprocess.run(['osascript', '-e', K.FRONT], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: front = ''
    try: r = subprocess.run(['osascript', '-', *args], input=script, capture_output=True, text=True, timeout=timeout)
    finally: subprocess.run(['osascript', '-', front], input=K.RESTORE, capture_output=True, text=True, timeout=30)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()

def send(to, subj, body, attachments=()):  # one real send
    return osa(SEND, to, subj, body, FROM, *attachments)
def draft(to, subj, body, attachments=()):  # one draft in Mail's Drafts, never sent
    return osa(SAVE, to, subj, body, FROM, ACCOUNT, K.S['mail']['drafts'], *attachments)
def body_of(i, mid): return osa(BODY, ACCOUNT, K.S['mail']['inbox'], str(i), mid.replace('"', ''), timeout=120)

# ---- the outreach log ----
def is_sent(r): return r['status'] == 'sent'
def is_done(r, x=None):
    # A draft counts as done, except for an email you approved in send mode: that one is sent even if a draft was saved before.
    ok = ('sent', 'replied: follow-up skipped') if (K.MODE == 'send' and x is not None and x.get('approved')) else ('sent', 'drafted', 'replied: follow-up skipped')
    return r['status'] in ok
def rows():
    if not os.path.exists(OUT): return []
    return list(csv.DictReader(open(OUT, encoding='utf-8')))
def outlog(x, kind, status, when=None):
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new: w.writerow(COLS)
        w.writerow([f"{when or K.now():%F %H:%M}", x['company'], x.get('person', ''), x['to'], x.get('source_url', ''),
                    x['subject'] if kind == 'email' else x.get('followup_subject', ''), x.get('lang', 'en'), kind, status])
def stamp(r): return dt.datetime.strptime(r['date'][:16], '%Y-%m-%d %H:%M').replace(tzinfo=K.TZ)
def sent_today():
    d = f"{K.now():%F}"
    return sum(1 for r in rows() if r['date'].startswith(d) and is_sent(r))
def last_send():
    ts = [stamp(r) for r in rows() if is_sent(r)]
    return max(ts) if ts else None
def company_done(x, kind):  # sent or drafted, per person
    return any(r['company'] == x['company'] and r['email'].lower() == x['to'].lower() and r['kind'] == kind and is_done(r, x) for r in rows())
def company_sent(x, kind):
    return any(r['company'] == x['company'] and r['email'].lower() == x['to'].lower() and r['kind'] == kind and is_sent(r) for r in rows())
def first_sent_at(x):
    t = [stamp(r) for r in rows() if r['company'] == x['company'] and r['email'].lower() == x['to'].lower() and r['kind'] == 'email' and is_sent(r)]
    return t[0] if t else None
def addr_done(addr):
    return any(r['email'].lower() == addr.lower() and r['kind'] == 'email' and is_sent(r) for r in rows())
def domains(x):
    return {x['to'].split('@')[1].lower()} | {d.lower() for d in x.get('domains', [])}

def needs_top(text):
    p = K.NEEDS; s = open(p, encoding='utf-8').read() if os.path.exists(p) else '# Needs you\n\n## Replies\n'
    hdr = '## Replies\n'
    s = s.replace(hdr, hdr + text, 1) if hdr in s else s + '\n' + hdr + text
    open(p, 'w', encoding='utf-8').write(s)

def suggested(x, call, decline=False):
    """A suggested answer for needs-me.md (never sent), from settings.replies; with nothing set, a neutral placeholder."""
    R = K.S['replies']; lang = x.get('lang', 'en'); kind = 'decline' if decline else ('call' if call else 'reply')
    t = (R.get(lang) or {}).get(kind) or (R.get('en') or {}).get(kind) or {
        'decline': 'Thank you for getting back to me, and for letting me know.\n\n{sign_off}\n{name}',
        'call': 'Thank you for getting back to me. I would be glad to talk. [times that suit you]\n\n{sign_off}\n{name}',
        'reply': 'Thank you for getting back to me. [answer]\n\n{sign_off}\n{name}'}[kind]
    return K.fill(t)

def check_replies(E, state):
    sent = {x['id']: x for x in E if company_sent(x, 'email')}
    W = f'{K.DATA}/watch.json'  # firms you applied to another way ([{company, domains, lang, note}]): their mail is surfaced the same way
    for w in K.load_json(W, []):
        sent.setdefault('watch-' + w['company'], {'id': 'watch-' + w['company'], 'company': w['company'], 'person': '', 'to': '@' + w['domains'][0],
                        'domains': w['domains'], 'lang': w.get('lang', 'en'), 'source_url': '', 'subject': w.get('note', 'application'), 'followup_subject': ''})
    if not sent: return
    try: raw = osa(INBOX, ACCOUNT, K.S['mail']['inbox'], timeout=240)
    except Exception as e: log(f'reply check failed: {e}'); return
    seen = set(state.setdefault('seen', []))
    me = re.escape(K.C['name']) if K.C['name'] else None
    for i, row in enumerate(raw.splitlines(), 1):
        p = row.split('\t')
        if len(p) < 4: continue
        mid, frm, subj, when = p[:4]
        if mid in seen: continue
        m = re.search(r'@([A-Za-z0-9.-]+)', frm); dom = m.group(1).lower() if m else ''
        for x in sent.values():
            if not (dom and any(dom == d or dom.endswith('.' + d) for d in domains(x))): continue
            seen.add(mid)
            try: body = body_of(i, mid)
            except Exception as e: body = f'(could not read body: {e})'
            auto = bool(AUTO.search(subj + ' ' + body[:1500])) or 'noreply' in frm.lower().replace('-', '')
            mine = own_text(body)[:4000]
            ob = (x.get('body') or '')[:60]  # our own email quoted without a 'wrote:' line (helpdesk style) is cut off too
            if ob and ob in mine: mine = mine[:mine.index(ob)]
            if me: mine = re.split(r'\n[^\n]*' + me + r'\s*\n\s*\d{1,2} \w{3,9} 20\d\d', mine, 1)[0]
            decline = (not auto) and bool(DECLINE.search(mine))  # an auto-reply is never a polite no
            call = (not auto) and (not decline) and bool(CALL.search(mine))
            if not auto:  # a real reply: no follow-up to anyone at that firm (an auto-reply doesn't count)
                state.setdefault('replied', []).extend(y['id'] for y in sent.values() if y['company'] == x['company'])
            firm = [y for y in sent.values() if y['company'] == x['company'] and not y['id'].startswith('watch-')]
            redirect = bool(FR.REDIRECT.search(mine)); ooo = auto and bool(OOO.search(subj + ' ' + mine[:2000]))
            try:
                if redirect:  # "apply via our site": no follow-up, and a by-hand item
                    for y in firm: state.setdefault('no_fu', {})[y['id']] = f'apply via their site ({when})'
                    needs_top(f"\n- 🧭 **{x['company']}** says to apply through its own site (\"{subj[:90]}\", {when}). Follow-up cancelled.\n")
                elif ooo:  # out of office: the follow-up moves to the day after the return date
                    ret = FR.parse_return(mine)
                    for y in firm:
                        if not ret or company_done(y, 'followup'): continue
                        t = FR.place(E, y, ret + dt.timedelta(days=1))
                        if t: state.setdefault('fu_at', {})[y['id']] = t.isoformat(timespec='minutes')
                    needs_top(f"\n- 🏖 **{x['company']}**: out of office" + (f" until {ret:%a %d %b}; follow-up moved to " +
                              ', '.join(state.get('fu_at', {}).get(y['id'], '?')[:16] for y in firm) if ret else
                              ' with no return date I could read; follow-up unchanged') + f" (\"{subj[:80]}\", {when}).\n")
                elif decline and not call:  # polite no: no follow-up, and a short thank-you saved to Drafts by the night job (never sent)
                    to = (re.search(r'<([^>]+)>', frm) or re.search(r'(\S+@\S+)', frm)).group(1)
                    rsub = subj if re.match(r'^(re|aw|antw)\s*:', subj, re.I) else 'Re: ' + subj
                    state.setdefault('declines', []).append(x['id'])
                    if FR.queue_draft(mid, x['company'], to, re.sub(r'^(RE|AW|Antw):', 'Re:', rsub), FR.thank_you(x.get('lang', 'en'), frm)):
                        needs_top(f"\n- ✉️ Thank-you draft for **{x['company']}** queued; the night job saves it to Drafts (not sent).\n")
            except Exception as e: log(f'reply rules failed for {x["company"]}: {e}')
            if call:
                state.setdefault('calls', []).append({'id': x['id'], 'company': x['company'], 'from': frm, 'subject': subj, 'when': when, 'body': body[:4000]})
            tag = 'auto-reply' if auto else ('URGENT: offers a call' if call else ('decline' if decline else 'reply'))
            if not x['id'].startswith('watch-'): outlog(x, 'reply', f'{tag}: {subj[:80]}')
            if not auto:
                q = '\n'.join('> ' + l for l in body.strip().splitlines()[:80])
                needs_top(f"\n### {'🔴 URGENT: ' if call else ''}{x['company']}: {frm}, \"{subj}\", received {when}\n"
                          + (f"Your email: \"{x['subject']}\" to {x['to']}" if not x['id'].startswith('watch-') else f"Re: {x['subject']}")
                          + f"\n\n{q}\n\n**Suggested reply (not sent):**\n\n" + '\n'.join('> ' + l for l in suggested(x, call, decline).splitlines()) + '\n')
            log(f'REPLY {tag} {x["company"]} {frm} "{subj}"')
            try:  # one line per reply for OUTREACH-TRACKER.html (their own text only, first 240 characters)
                with open(f'{K.LOGS}/replies-log.jsonl', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'logged': f'{K.now():%F %H:%M}', 'id': x['id'], 'company': x['company'], 'to': x.get('to', ''), 'from': frm,
                                        'subject': subj, 'when': when, 'tag': tag, 'text': re.sub(r'\s+', ' ', mine).strip()[:240]}, ensure_ascii=False) + '\n')
            except Exception as e: log(f'replies-log failed: {e}')
            break
    state['seen'] = sorted(seen)

def locked_replies(E):
    """Runs one inbox check under a file lock and returns the shared reply state (seen, replied, calls, declines)."""
    with open(f'{K.LOGS}/replies.lock', 'w') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        rs = K.load_json(RSTATE, {})
        check_replies(E, rs)
        K.save_json(RSTATE, rs)
        return rs

def replied_ids(): return set(K.load_json(RSTATE, {}).get('replied', []))

def due(E, now=None):
    """(time, kind, email) for every first email and follow-up whose time has come. Reads files only. A first email is due
    only once you approved it ("approved": true): an unapproved one is never drafted or sent, it waits for you."""
    now = now or K.now(); out = []
    NO_FU, FU_AT = FR.overrides()
    for x in E:
        if not x.get('slot'): continue
        t = dt.datetime.fromisoformat(x['slot']).replace(tzinfo=K.tz_of(x))
        if not company_done(x, 'email') and not x.get('hold'):
            if t <= now and x.get('approved'): out.append((t, 'email', x))
        elif company_sent(x, 'email') and not company_done(x, 'followup') and x['id'] not in NO_FU and x.get('followup_body'):
            t0 = first_sent_at(x)
            if x['id'] in FU_AT: fu = FU_AT[x['id']]  # moved after an out-of-office reply
            else:
                fu = K.holiday_shift(t0 + dt.timedelta(days=FOLLOW_DAYS), x)
                for _ in range(10):  # weekend -> next weekday, same time
                    if K.slot_ok(fu, x): break
                    fu += dt.timedelta(days=1)
                if not K.slot_ok(fu, x):  # first email sent outside the window: the earliest valid time from day N
                    fu = FR.place(E, x, K.holiday_shift(t0 + dt.timedelta(days=FOLLOW_DAYS), x).astimezone(K.tz_of(x)).date()) or fu
            if fu <= now: out.append((fu, 'followup', x))
    return sorted(out, key=lambda z: z[0])

if __name__ == '__main__':
    E = K.emails()
    if '--mark-sent' in sys.argv:
        i = sys.argv.index('--mark-sent'); xid = sys.argv[i + 1]
        when = dt.datetime.strptime(sys.argv[i + 2], '%Y-%m-%d %H:%M').replace(tzinfo=K.TZ) if len(sys.argv) > i + 2 else K.now()
        x = next((y for y in E if y['id'] == xid), None)
        if not x: sys.exit(f'no email with id {xid} in {K.EMAILS}')
        outlog(x, 'email', 'sent', when); print(f'recorded: {x["company"]} <{x["to"]}> sent {when:%F %H:%M}; its follow-up is now scheduled')
    else:
        for t, kind, x in due(E):
            print(f'{t:%F %H:%M} {kind:8} {x["company"]} <{x["to"]}>  ({"sent" if K.MODE == "send" else "drafted"} on the next run)')
        wait = [x for x in E if not x.get('approved') and not x.get('hold') and not company_done(x, 'email')]
        if wait: print(f'{len(wait)} planned email(s) wait for your approval (set "approved": true): ' + ', '.join(x['id'] for x in wait))
