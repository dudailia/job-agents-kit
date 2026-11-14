# Shared settings and safety helpers for every tool in this kit. Every value that belongs to one person (name, address,
# time zone, send windows, Mail account, writing rules, employers never to contact) is read from profile/settings.json,
# profile/never-apply.md and profile/facts.md, never written into the code.
# usage: python3 -I tools/kit.py --check     validate profile/settings.json and print warnings
#        python3 -I tools/kit.py --shell     print the gate settings as shell variables (used by launchd/night-gate.sh)
import datetime as dt, json, os, re, sys, zoneinfo

ROOT = os.environ.get('JOBKIT_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE, DATA, LOGS = f'{ROOT}/profile', f'{ROOT}/data', f'{ROOT}/logs'
SETTINGS_FILE = f'{PROFILE}/settings.json'
NEVER_FILE, FACTS_FILE = f'{PROFILE}/never-apply.md', f'{PROFILE}/facts.md'
EMAILS, OUTLOG = f'{DATA}/emails.json', f'{DATA}/outreach-log.csv'
NEEDS = f'{ROOT}/needs-me.md'
# Safety switches. ~/STOP-AGENTS stops every job at once. logs/SENDER-PAUSED stops sending until you delete it (the night job
# writes it when a message is stuck in the Outbox). logs/MAIL-LOGIN-ERROR stops sending until you sign in to Mail again.
STOPFILE = os.path.expanduser('~/STOP-AGENTS')
PAUSE, LOGINF = f'{LOGS}/SENDER-PAUSED', f'{LOGS}/MAIL-LOGIN-ERROR'
os.makedirs(LOGS, exist_ok=True); os.makedirs(DATA, exist_ok=True)

DEFAULTS = {
    'candidate': {'name': '', 'first_name': '', 'email': '', 'phone': '', 'city': '', 'school': '', 'school_portal': '',
                  'program': 'internship', 'availability': '', 'cv_url': '', 'situation': 'a student looking for an internship'},
    'timezone': 'Europe/London',
    'hours': {'night_start': '00:30', 'work_end': '05:00', 'sender_end': '09:00'},
    'send': {'mode': 'prepare', 'daily_max': 20, 'per_run': 3, 'gap_minutes': 4, 'follow_up_days': 7, 'late_minutes': 50,
             'end_date': '', 'inbox_checks': ['06:00', '07:45', 'before follow-ups'], 'holiday': {'from': '', 'to': '', 'resume': ''}},
    'default_window': ['08:00', '08:50'],
    'regions': {},
    'mail': {'account': '', 'from': '', 'inbox': 'Inbox', 'drafts': 'Drafts', 'health_check': True, 'stale_inbox_hours': 12},
    'writing': {'max_words': 170, 'banned': [], 'opt_out_line': '', 'sign_off': 'Kind regards,', 'salutation_regex': r"^Dear .+,$",
                'require_cv_link': True, 'require_availability': True, 'followup_max_lines': 2, 'linkedin_note_max': 300},
    'replies': {},
    'audit': {'mailboxes': ['inbox', 'archive'], 'sent_mailboxes': ['sent items', 'sent messages', 'sent', 'sent mail'],
              'my_addresses': [], 'generic_domains': ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com', 'me.com',
                                                      'proton.me', 'protonmail.com'], 'first_days': 45},
    'postings': {'title': r'intern|placement|off[- ]cycle|trainee', 'exclude': r'thesis|working student', 'places': r'remote', 'end_date': ''},
    'jev_dir': '',
    'today': {'title': 'By hand', 'order': ['actions', 'replies', 'review', 'postings', 'items', 'linkedin', 'held']},
}

def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out

def load_settings(path=SETTINGS_FILE):
    if not os.path.exists(path):
        sys.exit(f'{path} does not exist. Copy profile/settings.example.json to profile/settings.json and fill it in (SETUP.md, step 2).')
    raw = json.load(open(path, encoding='utf-8'))
    return _merge(DEFAULTS, {k: v for k, v in raw.items() if not k.startswith('_')})

S = load_settings()
C, W = S['candidate'], S['writing']
TZ = zoneinfo.ZoneInfo(S['timezone'])
MODE = S['send']['mode'] if S['send']['mode'] in ('prepare', 'send') else 'prepare'  # anything unknown means prepare: nothing is sent

def hm(s): h, m = map(int, s.split(':')); return dt.time(h, m)
NIGHT_START, WORK_END, SENDER_END = hm(S['hours']['night_start']), hm(S['hours']['work_end']), hm(S['hours']['sender_end'])
def now(): return dt.datetime.now(TZ)
def in_hours(t, start, end):  # handles windows that do not cross midnight (the defaults) and ones that do
    t = t.time() if isinstance(t, dt.datetime) else t
    return start <= t < end if start <= end else (t >= start or t < end)
def sender_hours(t=None): return in_hours((t or now()).astimezone(TZ), NIGHT_START, SENDER_END)

# ---- regions and send windows: every send is on a weekday, inside the recipient's local window and the sender's hours ----
def region(x):
    r = x.get('region', '') if isinstance(x, dict) else x
    return S['regions'].get(r, {})
def tz_of(x): return zoneinfo.ZoneInfo((x.get('tz') if isinstance(x, dict) else None) or region(x).get('tz') or S['timezone'])
def window_of(x):
    w = region(x).get('window') or S['default_window']
    return hm(w[0]), hm(w[1])
def slot_ok(t, x):
    lt = t.astimezone(tz_of(x)); a, b = window_of(x)
    return lt.weekday() < 5 and a <= lt.time() <= b and sender_hours(t)
def holiday_shift(f, x):
    h = S['send'].get('holiday') or {}
    if not (h.get('from') and h.get('to') and h.get('resume')): return f
    lt = f.astimezone(tz_of(x))
    if dt.date.fromisoformat(h['from']) <= lt.date() <= dt.date.fromisoformat(h['to']):
        r = dt.date.fromisoformat(h['resume']); f = lt.replace(year=r.year, month=r.month, day=r.day).astimezone(f.tzinfo)
    return f

# ---- never-apply: one employer per line in profile/never-apply.md ("- Name" or "- Name | note"), matched employer-wide ----
def norm_name(s): return re.sub(r'\b(ltd|limited|plc|inc|llc|lda|sa|group|technologies|labs?)\b|[^\w ]', ' ', s.lower()).split()
SUFFIX = {'bank', 'uk', 'us', 'usa', 'europe', 'eu', 'emea', 'international', 'global', 'payments', 'capital', 'markets', 'asset', 'management',
          'investments', 'investment', 'securities', 'holding', 'holdings', 'ag', 'gmbh', 'bv', 'nv', 'sas', 'se', 'corp', 'corporation',
          'company', 'co', 'trading', 'financial', 'finance', 'services', 'partners', 'advisors', 'ventures', 'wealth', 'ab', 'as', 'asa',
          'oy', 'oyj', 'spa', 'srl', 'sl', 'sarl', 'kg', 'pte', 'pty', 'lp', 'llp', 'jsc', 'germany', 'deutschland', 'netherlands', 'france',
          'spain', 'portugal', 'ireland', 'luxembourg', 'london', 'americas', 'asia', 'research', 'technology', 'software', 'ai'}
def never_list(path=NEVER_FILE):
    out = []
    if not os.path.exists(path): return out
    for l in open(path, encoding='utf-8'):
        m = re.match(r'^\s*[-*]\s+(.+)$', l)  # only list lines are names; any other line is explanation
        if not m: continue
        l = m.group(1).split('|')[0].split('\t')[0].strip()
        if l: out.append(l)
    return out
NEVER = never_list()
def blocked(company):
    """The never-apply name that covers this company, or None. Whole names only ("Ramp" does not block "Onramp"), plus generic
    suffix words on either side ("Example Bank UK" is covered by "Example"), and any name in brackets ("Foo (Bar)")."""
    names = [re.sub(r'\s*\(.*?\)\s*', ' ', company)] + re.findall(r'\((.*?)\)', company)
    for listed in NEVER:
        nt = norm_name(listed)
        if not nt: continue
        for toks in (norm_name(x) for x in names):
            if not toks: continue
            if toks == nt or (toks[:len(nt)] == nt and all(t in SUFFIX for t in toks[len(nt):])) \
                    or (toks[-len(nt):] == nt and all(t in SUFFIX for t in toks[:-len(nt)])):
                return listed
    return None

# ---- Mail: never activated, launched hidden, the front app given back after every call ----
FRONT = 'tell application "System Events" to get name of first application process whose frontmost is true'
RESTORE = """on run argv
set f to item 1 of argv
tell application "System Events"
  if f is not "Mail" and (exists process "Mail") then set visible of process "Mail" to false
  if f is not "" and f is not "Mail" then
    try
      set frontmost of process f to true
    end try
  end if
end tell
end run"""
def sender_line():
    return S['mail'].get('from') or (f"{C['name']} <{C['email']}>" if C['email'] else '')

def load_json(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def save_json(p, v):
    json.dump(v, open(p + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(p + '.tmp', p)
def emails(): return load_json(EMAILS, [])
def fill(template, **extra):  # {name}, {first_name}, {sign_off}, {availability}... from settings; unknown keys stay as written
    vals = {**C, 'sign_off': W['sign_off'], **extra}
    return re.sub(r'\{(\w+)\}', lambda m: str(vals.get(m.group(1), m.group(0))), template)

def check():
    warn = []
    for k in ('name', 'email'):
        if not C.get(k): warn.append(f'candidate.{k} is empty')
    if not S['mail'].get('account'): warn.append('mail.account is empty: set it to the name of your account in Mail (Mail > Settings > Accounts)')
    if not S['regions']: warn.append('no regions: every email needs a "region" that is listed in settings.regions')
    for name, r in S['regions'].items():
        try: tz = zoneinfo.ZoneInfo(r.get('tz', ''))
        except Exception: warn.append(f'region {name}: unknown time zone "{r.get("tz")}"'); continue
        a, b = window_of(name); day = now().date(); ok = False
        t = dt.datetime.combine(day, a, tz)
        while t.time() <= b:
            if sender_hours(t): ok = True; break
            t += dt.timedelta(minutes=5)
            if t.date() != day: break
        if not ok: warn.append(f'region {name}: its window {a:%H:%M}-{b:%H:%M} {r["tz"]} never falls inside your sender hours '
                               f'({NIGHT_START:%H:%M}-{SENDER_END:%H:%M} {S["timezone"]}), so nothing to it would ever go')
    print(f'settings: {SETTINGS_FILE}\nmode: {MODE} ({"approved emails are saved to Mail Drafts, nothing is sent" if MODE == "prepare" else "approved emails are sent"}; unapproved ones wait)')
    print(f'never-apply: {len(NEVER)} names; regions: {", ".join(S["regions"]) or "none"}')
    print('\n'.join(f'warning: {w}' for w in warn) or 'no warnings')
    return not warn

if __name__ == '__main__':
    if '--shell' in sys.argv:
        print(f"export TZ={S['timezone']}; NIGHT_START={NIGHT_START:%H%M}; WORK_END={WORK_END:%H%M}; SENDER_END={SENDER_END:%H%M}")
    else:
        sys.exit(0 if check() else 1)
