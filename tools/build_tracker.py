# OUTREACH-TRACKER.html: one row per firm or person contacted by any route, rebuilt every morning (launchd/run-morning.sh).
# Reads logs only; never touches Mail.
# Sources: data/outreach-log.csv (emails, drafts, follow-ups, replies), logs/replies-log.jsonl (reply one-liners),
# logs/replies-state.json (declines, cancelled and moved follow-ups), data/linkedin-notes.json (notes; "sent" holds the date
# you sent one), data/applications-log.csv (applications by hand: timestamp, company, role, url, status) and, when
# settings.jev_dir is set, jev-job-search's applications/applied.csv and all.csv.
# usage: python3 -I tools/build_tracker.py
import csv, datetime as dt, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
D = K.ROOT; now = K.now(); today = now.date(); zone = K.S['timezone']
E = lambda s: html.escape(str(s or ''))
def rows(p):
    try: return list(csv.DictReader(open(p, encoding='utf-8', newline='')))
    except Exception: return []
def day(s):
    m = re.search(r'(20\d\d-\d\d-\d\d)(?:[ T](\d\d:\d\d))?', s or '')
    return dt.datetime.fromisoformat(m.group(1) + ' ' + (m.group(2) or '12:00')).replace(tzinfo=K.TZ) if m else None
def weekday_fwd(t):
    while t.weekday() >= 5: t += dt.timedelta(days=1)
    return t

T = []  # tracker rows
def add(when, firm, person, channel, status='waiting', reply='', step='', fu=None, link=''):
    T.append(dict(when=when, firm=firm, person=person, channel=channel, status=status, reply=reply, step=step, fu=fu, link=link))

# ---- 1. emails (data/outreach-log.csv) ----
OL = rows(K.OUTLOG); RS = K.load_json(f'{K.LOGS}/replies-state.json', {}); EM = K.emails()
byto = {x['to'].lower(): x for x in EM if x.get('to')}
RL = []
for l in open(f'{K.LOGS}/replies-log.jsonl', encoding='utf-8') if os.path.exists(f'{K.LOGS}/replies-log.jsonl') else []:
    try: RL.append(json.loads(l))
    except ValueError: pass
text_by_co = {r['company']: r for r in RL}
firms = {}
for r in OL:
    k = (r['company'], (r.get('email') or '').lower())
    f = firms.setdefault(k, {'sent': None, 'drafted': None, 'fu': None, 'replies': [], 'person': r.get('person', '')})
    t = day(r['date'])
    if r['kind'] == 'email' and r['status'] == 'sent' and not f['sent']: f['sent'] = t
    elif r['kind'] == 'email' and r['status'] == 'drafted' and not f['drafted']: f['drafted'] = t
    elif r['kind'] == 'followup' and r['status'] == 'sent': f['fu'] = t
    elif r['kind'] == 'reply': f['replies'].append((t, r['status']))
declined_ids, no_fu, fu_at = set(RS.get('declines', [])), RS.get('no_fu', {}), RS.get('fu_at', {})
replied_ids = set(RS.get('replied', []))
due_today = []
ACK = re.compile(r'request received|ticket|has been received|we received|auto', re.I)  # a helpdesk acknowledgement is not a call offer
for (co, to), f in firms.items():
    if f['drafted'] and not f['sent']:
        add(f['drafted'], co, f['person'] or to, 'Email (draft)', 'draft', '', 'In Mail Drafts: send it yourself, then run sender.py --mark-sent', None, f'mailto:{to}'); continue
    if not f['sent']: continue
    x = byto.get(to, {}); xid = x.get('id', '')
    human = [(t, s) for t, s in f['replies'] if not s.startswith('auto-reply')]
    last = max(f['replies'], key=lambda z: z[0] or now) if f['replies'] else None
    status, step, fu = 'waiting', '', None
    if xid in declined_ids or any(s.startswith('decline') for _, s in human): status, step = 'declined', 'Thank-you draft is in Mail Drafts'
    elif any(s.startswith('URGENT') and not ACK.search(s) for _, s in human): status, step = 'interview', 'They offered a call: answer and book it'
    elif human or xid in replied_ids: status, step = 'replied', 'Read the reply and answer'
    if xid in no_fu and status == 'waiting': step = no_fu[xid][:90]
    if status == 'waiting' and not f['fu'] and xid not in no_fu and x.get('followup_body'):
        fu = dt.datetime.fromisoformat(fu_at[xid]) if xid in fu_at else weekday_fwd(f['sent'] + dt.timedelta(days=K.S['send']['follow_up_days']))
        step = 'Automatic follow-up' if K.MODE == 'send' and x.get('approved') else 'Follow-up saved to Drafts on the day'
        if fu.date() == today: due_today.append((fu, co, to))
    elif status == 'waiting' and f['fu']: step = f'Followed up {f["fu"]:%d %b}; no more automatic emails'
    rl = text_by_co.get(co)
    reply = f'{rl["tag"]}: {rl["text"]}' if rl else (last[1] if last else '')
    if last and last[1].startswith('auto-reply') and status == 'waiting': reply = last[1]
    add(f['sent'], co, f['person'] or to, 'Email', status, reply, step, fu, f'mailto:{to}')

# ---- 2. LinkedIn notes you marked sent (data/linkedin-notes.json, "sent": "YYYY-MM-DD") ----
NOTES = K.load_json(f'{K.DATA}/linkedin-notes.json', [])
for c in NOTES:
    if c.get('sent'): add(day(c['sent']) or now, c.get('company', ''), c.get('person', ''), 'LinkedIn note', link=c.get('profile_url', ''))

# ---- 3. jev-job-search applications (+ responses), when settings.jev_dir is set ----
J = os.path.expanduser(K.S.get('jev_dir') or '')
if J:
    resp = {r.get('Job ID'): (r.get('Response') or '', r.get('Response On') or '') for r in rows(f'{J}/applications/all.csv') if r.get('Response')}
    for r in rows(f'{J}/applications/applied.csv'):
        rs, ro = resp.get(r.get('job_id'), ('', ''))
        st = 'declined' if re.search(r'reject|declin|not moving|unfortunately', rs, re.I) else ('interview' if re.search(r'interview|call|assessment|next step', rs, re.I) else ('replied' if rs else 'waiting'))
        add(day(r.get('applied_on')), r.get('company', ''), r.get('role', ''), 'Application (jev)', st, (f'{ro}: {rs}' if rs else ''), '', None, r.get('job_link', ''))

# ---- 4. applications by hand (data/applications-log.csv) ----
for r in rows(f'{K.DATA}/applications-log.csv'):
    if re.match(r'(applied|submitted|sent)', r.get('status', ''), re.I):
        add(day(r.get('timestamp')), r.get('company', ''), r.get('role', ''), 'Application (by hand)', 'waiting', '', r.get('status', '')[:120], None, r.get('url', ''))

T = [t for t in T if t['when']]
T.sort(key=lambda t: t['when'], reverse=True)

# ---- top: (a) replies needing you, (b) follow-ups due today, (c) by hand in 7 days, (d) best notes still to send ----
dec = {t['firm'] for t in T if t['status'] == 'declined'}
rep = [r for r in RL if r['tag'] not in ('auto-reply', 'decline') and (day(r['logged']) or now) >= now - dt.timedelta(days=3) and r['company'] not in dec]
a_items = [f'<li><b>{E(r["company"])}</b> · {E(r["tag"])} · {E(r["when"])}<br><span class="q">{E(r["text"])}</span></li>' for r in rep]
b_items = [f'<li>{fu:%H:%M} · <b>{E(co)}</b> &lt;{E(to)}&gt;</li>' for fu, co, to in sorted(due_today)]
wk = now - dt.timedelta(days=7)
hand = [t for t in T if t['when'] >= wk and (t['channel'].startswith('LinkedIn') or t['channel'].startswith('Application'))]
li7 = [t for t in hand if t['channel'].startswith('LinkedIn')]
cands = sorted([c for c in NOTES if not c.get('sent') and c.get('profile_url') and not K.blocked(c.get('company', ''))], key=lambda c: -int(c.get('fit') or 0))
d_items = [f'<li><b>{E(c["company"])}</b> (fit {E(c.get("fit", "?"))}): <a href="{E(c["profile_url"])}">{E(c.get("person", ""))}, {E(c.get("title", ""))}</a><pre>{E(c.get("note", ""))}</pre></li>' for c in cands[:10]]

cnt = {s: sum(1 for t in T if t['status'] == s) for s in ('draft', 'waiting', 'replied', 'interview', 'declined')}
warn = '' if li7 or not cands else '<p class="warn">⚠ No LinkedIn notes marked sent in the last 7 days. The best ones are below.</p>'
def cell(t):
    fu = f'{t["fu"]:%a %d %b}' if t['fu'] else ''
    firm = f'<a href="{E(t["link"])}">{E(t["firm"])}</a>' if t['link'].startswith('http') else E(t['firm'])
    return (f'<tr class="{t["status"]}"><td>{t["when"]:%Y-%m-%d}</td><td>{firm}</td><td>{E(t["person"])}</td><td>{E(t["channel"])}</td>'
            f'<td><span class="st {t["status"]}">{t["status"]}</span></td><td class="r">{E(t["reply"][:240])}</td><td>{E(t["step"])}</td><td>{fu}</td></tr>')
try:  # email audit counts (tools/email_audit.py)
    a = json.load(open(f'{K.LOGS}/email-audit-counts.json'))
    AUDIT = (f'<p class="big"><a href="needs-reply.html">✉️ Emails needing you</a>: <b>{a["overdue"]}</b> overdue / <b>{a["new"]}</b> new / '
             f'<b>{a["ignored"]}</b> still ignored (scan {dt.datetime.fromisoformat(a["scan"]):%a %d %b %H:%M})</p>')
except Exception:
    AUDIT = '<p class="mut">Email audit: none yet.</p>'
BANNER = ''.join(f'<p class="banner">⚠️ {E(title)} {E(open(p, encoding="utf-8").read().strip()[:300])} {E(fix)}</p>' for p, title, fix in (
    (K.LOGINF, 'SIGN IN TO MAIL AGAIN.', 'Sending is paused: after signing in, delete logs/MAIL-LOGIN-ERROR.'),
    (K.PAUSE, 'SENDING IS PAUSED.', 'Delete logs/SENDER-PAUSED to resume.')) if os.path.exists(p))
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outreach tracker</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e4e1da;--card:#fff;--acc:#2f5d8a;--ok:#2e7d4f;--warn:#a5521b;--bad:#9b2c2c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--mut:#a3a19b;--line:#33322f;--card:#1f1f1d;--acc:#8cb4dd;--ok:#7cc79a;--warn:#e0a070;--bad:#e08a8a}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px}}main{{max-width:1300px;margin:auto}}
h1{{font-size:22px;margin:4px 0}}h2{{font-size:17px;margin:22px 0 6px}}.mut{{color:var(--mut)}}a{{color:var(--acc)}}
.banner{{background:var(--bad);color:var(--bg);padding:10px 14px;border-radius:8px;font-weight:700;font-size:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}}
.card ul{{padding-left:18px;margin:6px 0}}.q{{color:var(--mut)}}pre{{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);padding:6px;border-radius:6px;font-size:13px}}
.warn{{color:var(--warn);font-weight:600}}table{{border-collapse:collapse;width:100%;font-size:13.5px}}th,td{{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}}
th{{position:sticky;top:0;background:var(--bg)}}.r{{max-width:340px}}.st{{font-weight:600}}.st.replied{{color:var(--acc)}}.st.interview{{color:var(--ok)}}.st.declined{{color:var(--bad)}}.st.draft{{color:var(--warn)}}
input{{font:inherit;padding:6px 8px;width:min(420px,100%);border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}}.tw{{overflow-x:auto}}
</style></head><body><main>
{BANNER}<h1>Outreach tracker</h1><p class="mut">Rebuilt {now:%a %d %b %Y, %H:%M} ({E(zone)}) from the logs. Mode: <b>{K.MODE}</b>. {len(T)} contacts: {cnt["draft"]} drafts, {cnt["waiting"]} waiting, {cnt["replied"]} replied, {cnt["interview"]} interview, {cnt["declined"]} declined. <a href="TODAY.html">TODAY.html</a> · <a href="MORNING.md">MORNING.md</a></p>{AUDIT}
<div class="grid">
<div class="card"><h2>(a) Replies needing you</h2><ul>{"".join(a_items) or "<li>None in the last 3 days.</li>"}</ul></div>
<div class="card"><h2>(b) Follow-ups due today</h2><ul>{"".join(b_items) or "<li>None today.</li>"}</ul></div>
<div class="card"><h2>(c) Contacted by hand in the last 7 days: {len(hand)}</h2><p>LinkedIn notes marked sent: {len(li7)} · applications: {len(hand) - len(li7)}</p>{warn}</div>
</div>
<h2>(d) The best LinkedIn notes still to send</h2><div class="card"><ol>{"".join(d_items) or "<li>None waiting.</li>"}</ol></div>
<h2>Everyone contacted</h2><p><input id="f" placeholder="Filter: firm, person, status, channel…" oninput="flt()"></p>
<div class="tw"><table id="t"><thead><tr><th>Date</th><th>Firm</th><th>Person / role</th><th>Channel</th><th>Status</th><th>Last reply</th><th>Next step</th><th>Follow-up</th></tr></thead>
<tbody>{"".join(cell(t) for t in T)}</tbody></table></div>
<script>function flt(){{const q=document.getElementById('f').value.toLowerCase();for(const r of document.querySelectorAll('#t tbody tr'))r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'}}</script>
</main></body></html>'''
open(f'{D}/OUTREACH-TRACKER.html', 'w', encoding='utf-8').write(page)
print('OUTREACH-TRACKER.html', len(T), 'rows;', cnt, '; replies (a):', len(a_items), '; follow-ups today:', len(b_items), '; by hand 7d:', len(hand), '; notes:', len(d_items))
