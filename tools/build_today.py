# The TODAY page engine: one page to work through by hand, built only from files, so every text on it is exactly what was
# checked and nothing on it is a new claim. tools/build_today_focus.py uses it to write TODAY.html (only today's by-hand
# items, in your order); run this file alone to write TODAY-all.html (everything, done items included).
# Sections and where they come from:
#   actions   logs/replies-to-send.json, items with "no_reply": true and an "action": things to do by a deadline
#   replies   logs/replies-to-send.json, the other items: draft replies to emails that need you (never sent)
#   review    data/emails.json, planned emails not yet "approved": read each one, then set "approved": true
#   postings  logs/postings-today.json (written by the research shift), with the letter in data/cover-letters/<letter>.txt
#   items     data/today.json "items": anything else you do by hand (applications with an account, portals, CAPTCHAs)
#   linkedin  data/linkedin-notes.json, notes not yet marked "sent"
#   held      data/emails.json, emails on hold, with the reason
# In data/today.json, {name}, {email}, {phone}, {city}, {school}, {availability}, {cv_url} ... are filled from settings.
# usage: python3 -I tools/build_today.py
import html, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
D = K.ROOT; E = html.escape
TITLES = {'actions': 'Actions with a deadline', 'replies': 'Replies to send (drafts, not sent)', 'review': 'Emails to approve',
          'postings': 'New postings to apply to', 'items': 'By hand', 'linkedin': 'LinkedIn notes to send', 'held': 'Held emails'}

def copy(label, text, note=''):
    return (f'<div class="cp"><div class="cph"><span class="lbl">{E(label)}</span><button class="btn" type="button">Copy</button></div>'
            f'{f"<div class=note>{E(note)}</div>" if note else ""}<pre>{E(text)}</pre></div>')
def answers(rows):
    return '<table class="ans">' + ''.join(
        f'<tr><td>{E(q)}</td><td><span class="av">{E(a)}</span>' + (f' <button class="mini" type="button" data-t="{E(a)}">Copy</button>' if c else '') + '</td></tr>'
        for q, a, c in rows) + '</table>'
def steps(*s): return '<ol class="steps">' + ''.join(f'<li>{E(x)}</li>' for x in s) + '</ol>'
def facts(*s): return '<ul class="facts">' + ''.join(f'<li>{E(x)}</li>' for x in s) + '</ul>'
def a(url, text=None): return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(text or url)}</a>'
def item(id_, title, deadline, body, warn=''):
    return (f'<article class="item" id="{E(id_)}"><header><label class="done"><input type="checkbox" data-k="{E(id_)}"> done</label>'
            f'<h3>{E(title)}</h3><div class="dl">{E(deadline)}</div></header>{f"<div class=warn>{E(warn)}</div>" if warn else ""}{body}</article>')
def letter(key):
    p = f'{K.DATA}/cover-letters/{key}.txt'
    return open(p, encoding='utf-8').read().strip() if key and os.path.exists(p) else ''

def sections(include_done=True):
    """{key: (title, [item html, ...])} for every section that has something in it."""
    out = {}
    RTS = K.load_json(f'{K.LOGS}/replies-to-send.json', [])
    out['actions'] = [item(f'act-{k}', f'Action by {z.get("deadline", "?")} · {z.get("from", "")}: {z.get("subject", "")}', z.get('date', ''),
                           f'<p><b>What to do:</b> {E(z.get("want", ""))}</p>' + (f'<p class="note">{E(z["note"])}</p>' if z.get('note') else '')
                           + (f'<p>{a(z["link"], "Open it in Mail")}</p>' if z.get('link') else ''))
                      for k, z in enumerate(sorted([z for z in RTS if z.get('no_reply') and z.get('action')], key=lambda z: z.get('deadline') or ''), 1)]
    out['replies'] = [item(f'rts-{k}', f'{z.get("from", "")}: {z.get("subject", "")}', z.get('date', '') + (f' · deadline {z["deadline"]}' if z.get('deadline') else ''),
                           f'<p><b>What they want:</b> {E(z.get("want", ""))}</p>' + (f'<p class="note">{E(z["note"])}</p>' if z.get('note') else '')
                           + (f'<p>{a(z["link"], "Open it in Mail")}, press <b>Reply</b>, paste the text below, check it, and send it yourself.</p>' if z.get('link') else '')
                           + copy('Reply text', z.get('body', '')))
                      for k, z in enumerate(RTS, 1) if not z.get('no_reply')]
    EM = K.emails()
    out['review'] = [item(f'rev-{x["id"]}', f'{x["company"]}: {x.get("person") or x["to"]}', f'{x.get("region", "")} · goes {x.get("slot", "no slot")} local time',
                          f'<p>To: <code>{E(x["to"])}</code>' + (f' · source: {a(x["source_url"], "where the address is published")}' if x.get('source_url') else '') + '</p>'
                          + copy(f'Subject', x['subject']) + copy('Email', x['body']) + (copy('Follow-up', x['followup_body']) if x.get('followup_body') else '')
                          + f'<p class="note">Read it against your facts. If it is right, set <code>"approved": true</code> for id <code>{E(x["id"])}</code> in data/emails.json; '
                          f'if not, fix it or set <code>"hold"</code> with a reason.</p>',
                          warn=f'Never-apply: {K.blocked(x["company"])}' if K.blocked(x['company']) else '')
                     for x in EM if not x.get('approved') and not x.get('hold')]
    out['postings'] = [item(f'post-{k}', f'{z.get("company", "")}: {z.get("role", "")}, {z.get("where", "")}',
                            ' · '.join(s for s in (f'deadline {z["deadline"]}' if z.get('deadline') else 'rolling', f'fit {z["fit"]}' if z.get('fit') else '') if s),
                            (f'<p class="big">{a(z["url"])}</p>' if z.get('url') else '') + (f'<p>{E(z["why"])}</p>' if z.get('why') else '')
                            + (copy('Cover letter', letter(z.get('letter'))) if letter(z.get('letter')) else ''),
                            warn=(f'By hand: {z["blocker"]}' if z.get('blocker') else '') + (f' Never-apply: {K.blocked(z.get("company", ""))}' if K.blocked(z.get('company', '')) else ''))
                       for k, z in enumerate(K.load_json(f'{K.LOGS}/postings-today.json', []), 1)]
    T = K.load_json(f'{K.DATA}/today.json', {})
    common = [(K.fill(q), K.fill(v), c) for q, v, c in T.get('common_answers', [])]
    its = [z for z in T.get('items', []) if include_done or not z.get('done')]
    out['items'] = [item(z.get('id', f'item-{k}'), K.fill(z.get('title', '')), K.fill(z.get('deadline', '')),
                         (f'<p class="big">{a(z["url"])}</p>' if z.get('url') else '') + (facts(*map(K.fill, z['facts'])) if z.get('facts') else '')
                         + (steps(*map(K.fill, z['steps'])) if z.get('steps') else '')
                         + ''.join(copy(K.fill(l), K.fill(t)) for l, t in z.get('copies', []))
                         + (copy('Cover letter', letter(z['letter'])) if letter(z.get('letter')) else '')
                         + (answers((common if z.get('common') else []) + [(K.fill(q), K.fill(v), c) for q, v, c in z.get('answers', [])]) if z.get('answers') or z.get('common') else ''),
                         warn=K.fill(z.get('warn', '')))
                    for k, z in enumerate(sorted(its, key=lambda z: str(z.get('sort', 'zzzz'))), 1)]
    out['linkedin'] = [item(f'li-{k}', f'{c.get("person", "")}: {c.get("title", "")}, {c.get("company", "")}', f'fit {c.get("fit", "?")}',
                            f'<p>{a(c["profile_url"], "LinkedIn profile")}</p>' + copy(f'Connection note ({len(c.get("note", ""))} characters)', c.get('note', ''))
                            + (copy('Message after they accept', c['message']) if c.get('message') else '')
                            + '<p class="note">After sending, set <code>"sent": "YYYY-MM-DD"</code> for this note in data/linkedin-notes.json.</p>')
                       for k, c in enumerate(sorted([c for c in K.load_json(f'{K.DATA}/linkedin-notes.json', []) if not c.get('sent') and not K.blocked(c.get('company', ''))],
                                                    key=lambda c: -int(c.get('fit') or 0)), 1)]
    out['held'] = [item(f'held-{x["id"]}', f'{x["company"]} <{x["to"]}>', x.get('slot', ''), f'<p><b>Held:</b> {E(x["hold"])}</p>') for x in EM if x.get('hold')]
    return {k: (TITLES[k], v) for k, v in out.items() if v}

STYLE = '''<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e3e1db;--acc:#0b5cad;--accbg:#e8f0fa;--warn:#8a4b00;--warnbg:#fff4e2;--pre:#fafaf8;--ok:#2f7d32}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--card:#1f1f1d;--ink:#ecebe7;--mute:#a3a29c;--line:#34332f;--acc:#7cb4f0;--accbg:#1d2a38;--warn:#f0b56a;--warnbg:#33260f;--pre:#191918;--ok:#7fc883}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
nav{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:6px;flex-wrap:wrap}
nav a{color:var(--acc);text-decoration:none;padding:4px 10px;border-radius:999px;background:var(--accbg);font-size:13px}
main{max-width:920px;margin:0 auto;padding:16px}h1{font-size:24px;margin:12px 0 4px}h2{font-size:19px;margin:36px 0 10px;padding-top:8px;border-top:2px solid var(--ink)}
h3{font-size:16px;margin:0}a{color:var(--acc)}code{font-size:13px}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.item header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-bottom:8px}.item header h3{flex:1 1 300px}
.dl{font-size:13px;color:var(--mute);flex-basis:100%}.done{font-size:12px;color:var(--mute);order:2;cursor:pointer;white-space:nowrap}
.item.isdone{opacity:.55}.item.isdone h3{text-decoration:line-through}
.big{font-size:15px;font-weight:600;word-break:break-all}.note{font-size:13px;color:var(--mute)}
.warn{background:var(--warnbg);color:var(--warn);border-radius:8px;padding:10px 12px;font-size:13.5px;margin:6px 0 10px}
.steps{margin:8px 0 12px;padding-left:22px}.steps li{margin:3px 0}.facts{margin:4px 0 10px;padding-left:20px;font-size:14px}
.cp{border:1px solid var(--line);border-radius:8px;margin:10px 0;background:var(--pre)}
.cph{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.lbl{font-size:12.5px;font-weight:600;color:var(--mute);text-transform:uppercase;letter-spacing:.03em}.cp .note{padding:6px 10px 0}
pre{margin:0;padding:10px 12px;white-space:pre-wrap;word-wrap:break-word;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-height:340px;overflow:auto}
.btn,.mini{font:inherit;cursor:pointer;border:1px solid var(--acc);color:var(--acc);background:var(--card);border-radius:6px}
.btn{font-size:13px;padding:3px 14px}.mini{font-size:11.5px;padding:0 7px;margin-left:4px}.btn.ok,.mini.ok{background:var(--ok);border-color:var(--ok);color:#fff}
.ans{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0}.ans td{border-top:1px solid var(--line);padding:5px 6px;vertical-align:top}
.ans td:first-child{color:var(--mute);width:38%}@media (max-width:600px){.ans td:first-child{width:45%}}
</style>'''
SCRIPT = '''<script>
function cp(t,b){const done=()=>{const o=b.textContent;b.classList.add('ok');b.textContent='Copied';setTimeout(()=>{b.classList.remove('ok');b.textContent=o},1200)};
const fb=()=>{const x=document.createElement('textarea');x.value=t;x.style.position='fixed';x.style.opacity='0';document.body.appendChild(x);x.select();try{document.execCommand('copy');done()}catch(e){}x.remove()};
if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(done,fb)}else fb()}
document.addEventListener('click',e=>{const b=e.target.closest('.btn,.mini');if(!b)return;if(b.classList.contains('btn'))cp(b.closest('.cp').querySelector('pre').textContent,b);else cp(b.dataset.t,b)});
let st={};try{st=JSON.parse(localStorage.getItem('today-done')||'{}')}catch(e){}
document.querySelectorAll('input[data-k]').forEach(c=>{const it=c.closest('.item');c.checked=!!st[c.dataset.k];it.classList.toggle('isdone',c.checked);
c.addEventListener('change',()=>{st[c.dataset.k]=c.checked;it.classList.toggle('isdone',c.checked);try{localStorage.setItem('today-done',JSON.stringify(st))}catch(e){}})});
</script>'''

def render(heading, secs, intro=''):
    nav = ''.join(f'<a href="#s{k}">{k} · {E(t)} ({len(v)})</a>' for k, (t, v) in enumerate(secs, 1))
    body = ''.join(f'<h2 id="s{k}">{k} · {E(t)}</h2>{"".join(v)}' for k, (t, v) in enumerate(secs, 1)) or '<p>Nothing to do by hand today.</p>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(heading)}</title>{STYLE}</head><body><nav>{nav}</nav><main><h1>{E(heading)}</h1>'
            f'<p class="big"><a href="OUTREACH-TRACKER.html">📋 Outreach tracker</a> · <a href="needs-reply.html">✉️ Emails needing you</a></p>'
            f'<p class="note">{E(intro)} Built only from your files; nothing here is a new claim. Ticking “done” is saved in this browser only.</p>'
            f'{body}</main>{SCRIPT}</body></html>')

def write_all():
    secs = sections(include_done=True)
    page = render(f'Everything, {K.now():%a %d %b %Y}', [secs[k] for k in TITLES if k in secs], 'Every section, done items included.')
    open(f'{D}/TODAY-all.html', 'w', encoding='utf-8').write(page)
    return secs

if __name__ == '__main__':
    secs = write_all(); print('TODAY-all.html', {k: len(v) for k, (_, v) in secs.items()})
