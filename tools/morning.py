# Builds MORNING.md (launchd com.USERNAME.jobkit-morning, 07:30): what the night did, from the logs only. Never touches Mail.
# usage: python3 -I tools/morning.py
import csv, datetime as dt, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
D = K.ROOT; now = K.now(); today = now.date(); since = dt.datetime.combine(today, dt.time(0, 0), K.TZ); zone = K.S['timezone']
out = [f'# Morning summary, {today:%a %d %b %Y} ({now:%H:%M} {zone})', '',
       f'**Mode:** {K.MODE} ({"emails are saved to Drafts, nothing is sent" if K.MODE == "prepare" else "approved emails are sent, the rest drafted"})',
       f'**Outreach tracker:** [OUTREACH-TRACKER.html](file://{D}/OUTREACH-TRACKER.html) · **By hand today:** [TODAY.html](file://{D}/TODAY.html)', '']
try:  # email audit counts (tools/email_audit.py)
    a = json.load(open(f'{K.LOGS}/email-audit-counts.json'))
    out[4:4] = [f"**Emails needing you:** {a['overdue']} overdue / {a['new']} new / {a['ignored']} still ignored "
                f"(scan {dt.datetime.fromisoformat(a['scan']):%a %H:%M}): [needs-reply.html](file://{D}/needs-reply.html)", '']
except Exception:
    out[4:4] = ['**Emails needing you:** no email audit has run yet', '']
if os.path.exists(K.LOGINF):  # Mail login error found by the night job -> first line
    out[0:0] = ['# ⚠️ SIGN IN TO MAIL AGAIN', '', f"{open(K.LOGINF, encoding='utf-8').read().strip()[:300]} Sending is paused: after signing in to Mail, delete `logs/MAIL-LOGIN-ERROR`.", '']
if os.path.exists(K.PAUSE):
    out[0:0] = ['# ⚠️ SENDING IS PAUSED', '', f"{open(K.PAUSE, encoding='utf-8').read().strip()[:300]}. Delete `logs/SENDER-PAUSED` to resume.", '']

# 1. sends, drafts and follow-ups (data/outreach-log.csv)
rows = []
if os.path.exists(K.OUTLOG):
    for r in csv.DictReader(open(K.OUTLOG, encoding='utf-8')):
        try: t = dt.datetime.strptime(r['date'][:16], '%Y-%m-%d %H:%M').replace(tzinfo=K.TZ)
        except ValueError: continue
        if t >= since - dt.timedelta(hours=1): rows.append((t, r))
for st, label in (('sent', 'Sent'), ('drafted', 'Saved to Drafts (not sent)')):
    got = [(t, r) for t, r in rows if r['status'] == st]
    out += [f'## {label} overnight: {sum(1 for _, r in got if r["kind"] == "email")} first emails, {sum(1 for _, r in got if r["kind"] == "followup")} follow-ups', '']
    out += [f'- {t:%H:%M} {r["kind"]}: {r["company"]} <{r["email"]}>' for t, r in got] or ['- none']
other = [(t, r) for t, r in rows if r['status'] not in ('sent', 'drafted')]
if other: out += ['', '### Skipped, held or replies'] + [f'- {t:%H:%M} {r["kind"]}: {r["company"]}: {r["status"][:140]}' for t, r in other]

# 2. night.log: replies, call offers, errors
log = [l.rstrip() for l in open(f'{K.LOGS}/night.log', encoding='utf-8')] if os.path.exists(f'{K.LOGS}/night.log') else []
log = [l for l in log if l[:10] == f'{today}']
inbox = [l for l in log if 'inbox checked' in l]
errs = [l for l in log if re.search(r'fail|error|exception|could not|timed out', l, re.I)]
out += ['', '## Inbox', f'- last check: {inbox[-1][11:] if inbox else "no inbox check ran"}'] + [f'- {l[11:]}' for l in log if 'REPLY' in l]
out += ['', '## Problems in the night log'] + ([f'- {l[11:]}' for l in errs[-15:]] or ['- none'])

# 3. research shift
rs = f'{K.LOGS}/night-research-{today}.md'
out += ['', '## Research shift (headless)']
if os.path.exists(rs): out += [open(rs, encoding='utf-8').read().strip()]
else:
    lg = f'{K.LOGS}/night-research-{today}.log'
    tail = open(lg, encoding='utf-8').read().strip().splitlines()[-6:] if os.path.exists(lg) else []
    out += ['- no summary file was written'] + [f'  {l[:200]}' for l in tail]

# 4. checker and what is next
try:
    ck = subprocess.run([sys.executable, '-I', f'{D}/tools/check_msgs.py'], capture_output=True, text=True, timeout=300).stdout.strip().splitlines()
    out += ['', '## Checker', f'- {ck[-1] if ck else "no output"}'] + [f'- {l[:200]}' for l in ck[:-1][:10]]
except Exception as e: out += ['', '## Checker', f'- could not run: {e}']
E = K.emails()
def at(x): return dt.datetime.fromisoformat(x['slot']).replace(tzinfo=K.tz_of(x)).astimezone(K.TZ)
pend = [x for x in E if x.get('slot') and not x.get('hold')]
later = sorted([x for x in pend if at(x).date() == today and at(x) >= now], key=at)
out += ['', f'## Still due today: {len(later)}'] + [f"- {at(x):%H:%M} {x['company']} <{x['to']}> ({x.get('region', '')}){'' if x.get('approved') else ', not approved'}" for x in later]
tom = [x for x in pend if at(x).date() == today + dt.timedelta(days=1)]
unapproved = sum(1 for x in pend if not x.get('approved'))
out += ['', f'## Planned for tomorrow ({today + dt.timedelta(days=1):%d %b}): {len(tom)} first emails',
        f'- emails waiting for your approval: {unapproved} (set "approved": true in data/emails.json after reading each one)',
        f'- kill switch: {"~/STOP-AGENTS is PRESENT (nothing runs)" if os.path.exists(K.STOPFILE) else "off"}',
        '- TODAY.html has the items that need you.']
open(f'{D}/MORNING.md', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('MORNING.md', len(out), 'lines')
