# Follow-up rules for replies. Shared by tools/sender.py (inbox check) and tools/night_send.py (sending), so both agree on
# which follow-ups exist and when they go:
#  - out-of-office reply  -> move the follow-up to the day after the return date (first slot with room under the daily cap)
#  - "apply via our site" -> cancel the follow-up; a by-hand item is flagged in needs-me.md
#  - polite no            -> cancel the follow-up; a short thank-you is queued and saved to Drafts by the night job (never sent)
#  - any human reply      -> never a follow-up
# State: logs/replies-state.json keys 'replied' (list), 'no_fu' {id: reason}, 'fu_at' {id: ISO datetime}, 'declines' (list);
#        logs/reply-drafts.json [{key, company, to, subject, body, status}] (status 'pending' -> 'saved'/'failed: ...').
import csv, datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K

RSTATE, STATE, DRAFTQ = f'{K.LOGS}/replies-state.json', f'{K.LOGS}/sender-state.json', f'{K.LOGS}/reply-drafts.json'
DAY_MAX, GAP_MIN = K.S['send']['daily_max'], K.S['send']['gap_minutes']

REDIRECT = re.compile(r"(apply|applications?)\s+(only\s+)?(via|through|on|at)\s+(our|the)\s+(website|site|careers|career|jobs|portal|page)|"
                      r"only (accept|consider|review) applications (via|through|on)|please (visit|use|check) our (careers|jobs|website)", re.I)
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}

def load(path, default): return K.load_json(path, default)

def overrides():
    rs, st = load(RSTATE, {}), load(STATE, {})
    no = set(rs.get('replied', [])) | set(rs.get('no_fu', {})) | set(st.get('fu_skipped', []))
    return no, {k: dt.datetime.fromisoformat(v) for k, v in rs.get('fu_at', {}).items()}

def parse_return(text, today=None):
    """Latest date mentioned in an out-of-office text (the return date, or the last day away). None if no date."""
    today = today or K.now().date(); found = []
    for d, m, y in re.findall(r'\b(\d{1,2})[./](\d{1,2})[./](20\d\d|\d\d)\b', text):
        try: found.append(dt.date(int(y) + (2000 if len(y) == 2 else 0), int(m), int(d)))
        except ValueError: pass
    for d, mon in re.findall(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', text, re.I):
        try: found.append(dt.date(today.year, MONTHS[mon.lower()], int(d)))
        except ValueError: pass
    for mon, d in re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b', text, re.I):
        try: found.append(dt.date(today.year, MONTHS[mon.lower()], int(d)))
        except ValueError: pass
    found = [f if f >= today - dt.timedelta(days=60) else f.replace(year=f.year + 1) for f in found]
    found = [f for f in found if today - dt.timedelta(days=60) <= f <= today + dt.timedelta(days=120)]
    return max(found) if found else None

def _sent_at():
    out = {}
    if os.path.exists(K.OUTLOG):
        for r in csv.DictReader(open(K.OUTLOG, encoding='utf-8')):
            if r['kind'] == 'email' and r['status'] == 'sent':
                out.setdefault((r['company'], r['email'].lower()), dt.datetime.strptime(r['date'][:16], '%Y-%m-%d %H:%M').replace(tzinfo=K.TZ))
    return out

def plan(E):
    """(first-send time, follow-up time or None) per email id, in your time zone, with every override applied."""
    no, fu_at = overrides(); sent = _sent_at(); out = {}
    for x in E:
        if not x.get('slot') or (x.get('hold') and (x['company'], x['to'].lower()) not in sent): continue
        t = sent.get((x['company'], x['to'].lower())) or dt.datetime.fromisoformat(x['slot']).replace(tzinfo=K.tz_of(x)).astimezone(K.TZ)
        if x['id'] in no or not x.get('followup_body'): f = None
        elif x['id'] in fu_at: f = fu_at[x['id']]
        else:
            f = t + dt.timedelta(days=K.S['send']['follow_up_days'])
            while f.astimezone(K.tz_of(x)).weekday() >= 5: f += dt.timedelta(days=1)
            f = K.holiday_shift(f, x)
        out[x['id']] = (t, f)
    return out

def place(E, x, not_before):
    """Earliest follow-up time on or after `not_before` (a date) for email x: weekday, inside the recipient's window and your
    sender hours, GAP_MIN minutes from every other planned send, and under the daily cap that day."""
    P = plan(E); P.pop(x['id'], None)
    busy = [t for t, f in P.values()] + [f for t, f in P.values() if f]
    tz = K.tz_of(x); a, b = K.window_of(x); day = not_before
    for _ in range(60):
        if day.weekday() < 5:
            t = dt.datetime.combine(day, a, tz)
            while t.time() <= b and t.date() == day:
                if K.slot_ok(t, x) and sum(1 for z in busy if z.astimezone(K.TZ).date() == t.astimezone(K.TZ).date()) < DAY_MAX \
                        and all(abs((t - z).total_seconds()) >= GAP_MIN * 60 for z in busy):
                    return t.astimezone(K.TZ)
                t += dt.timedelta(minutes=1)
        day += dt.timedelta(days=1)
    return None

def first_name(frm):
    n = re.sub(r'<.*?>|".*?"|\|.*', '', frm).strip().strip('"')
    if '@' in n or not n or re.search(r'team|hr|recruit|talent|careers|department', n, re.I): return ''
    parts = n.replace(',', ' ').split()
    return parts[0] if parts else ''

def thank_you(lang, frm):
    """The thank-you after a polite no, from settings.replies.<lang>.thank_you ({their_name} is the sender's first name)."""
    nm = first_name(frm); R = K.S['replies']
    t = (R.get(lang) or {}).get('thank_you') or (R.get('en') or {}).get('thank_you') or \
        'Dear {their_name},\n\nThank you for getting back to me, and for letting me know. If anything opens up, I would be glad to hear from you.\n\n{sign_off}\n{name}'
    return K.fill(t, their_name=nm or 'Hiring Team')

def queue_draft(key, company, to, subject, body):
    q = load(DRAFTQ, [])
    if any(d['key'] == key for d in q): return False
    q.append({'key': key, 'company': company, 'to': to, 'subject': subject, 'body': body, 'status': 'pending', 'queued': f'{K.now():%F %H:%M}'})
    K.save_json(DRAFTQ, q)
    return True
