# Scans the public job-board APIs (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio, Recruitee) of every board linked in
# data/research/*.csv for new postings whose title matches settings.postings.title (and not .exclude) in a place matching
# settings.postings.places, and lists the ones not seen before (logs/postings-seen.json). Read-only HTTP; no forms, no logins.
# usage: python3 -I tools/scan_postings.py [--needs]   (--needs: also list new postings in needs-me.md; used by the launchd job)
import csv, datetime as dt, glob, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
P = K.S['postings']
if P.get('end_date') and dt.date.today() > dt.date.fromisoformat(P['end_date']) and '--needs' in sys.argv: sys.exit(0)
D = K.ROOT
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
TITLE, NOT, PLACE = re.compile(P['title'], re.I), re.compile(P['exclude'] or r'(?!x)x', re.I), re.compile(P['places'], re.I)

def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return r.read().decode('utf-8', 'ignore')
    except Exception: return None

boards = set()
for p in glob.glob(f'{K.DATA}/research/*.csv'):
    for row in csv.DictReader(open(p, encoding='utf-8')):
        text = ' '.join(v for v in row.values() if isinstance(v, str))
        for m in re.finditer(r'(?:job-boards(?:\.eu)?|boards)\.greenhouse\.io/([\w-]+)', text): boards.add(('gh', m.group(1)))
        for m in re.finditer(r'jobs\.lever\.co/([\w-]+)', text): boards.add(('lever', m.group(1)))
        for m in re.finditer(r'jobs\.ashbyhq\.com/([\w.-]+)', text): boards.add(('ashby', m.group(1)))
        for m in re.finditer(r'jobs\.smartrecruiters\.com/([\w-]+)', text): boards.add(('sr', m.group(1)))
        for m in re.finditer(r'([\w-]+)\.jobs\.personio\.(?:de|com)', text): boards.add(('personio', m.group(1)))
        for m in re.finditer(r'([\w-]+)\.recruitee\.com', text): boards.add(('recruitee', m.group(1)))
        for m in re.finditer(r'apply\.workable\.com/([\w-]+)', text): boards.add(('workable', m.group(1)))
        for m in re.finditer(r'\b([\w-]+)\.workable\.com', text): boards.add(('workable', m.group(1)))
boards -= {('gh', 'embed'), ('sr', 'oneclick-ui'), ('ashby', 'api'), ('workable', 'j'), ('workable', 'api'), ('workable', 'apply'), ('workable', 'www')}
found = []
for kind, b in sorted(boards):
    jobs = []
    if kind == 'gh':
        for host in ('boards-api.greenhouse.io', 'boards-api.eu.greenhouse.io'):
            t = get(f'https://{host}/v1/boards/{b}/jobs')
            if t:
                try: jobs = [(j['title'], j.get('location', {}).get('name', ''), j['absolute_url']) for j in json.loads(t).get('jobs', [])]; break
                except Exception: pass
    elif kind == 'lever':
        t = get(f'https://api.lever.co/v0/postings/{b}?mode=json')
        try: jobs = [(j['text'], j.get('categories', {}).get('location', ''), j['hostedUrl']) for j in json.loads(t or '[]')]
        except Exception: pass
    elif kind == 'ashby':
        t = get(f'https://api.ashbyhq.com/posting-api/job-board/{b}')
        try: jobs = [(j['title'], j.get('location', ''), j['jobUrl']) for j in json.loads(t or '{}').get('jobs', [])]
        except Exception: pass
    elif kind == 'sr':
        t = get(f'https://api.smartrecruiters.com/v1/companies/{b}/postings?limit=100')
        try: jobs = [(j['name'], j.get('location', {}).get('city', ''), f"https://jobs.smartrecruiters.com/{b}/{j['id']}") for j in json.loads(t or '{}').get('content', [])]
        except Exception: pass
    elif kind == 'personio':
        t = get(f'https://{b}.jobs.personio.de/xml')
        if t: jobs = [(re.sub(r'<.*?>', '', n), re.sub(r'<.*?>', '', o), f'https://{b}.jobs.personio.de/job/{i}')
                      for i, n, o in re.findall(r'<id>(\d+)</id>.*?<name>(.*?)</name>.*?<office>(.*?)</office>', t, re.S)]
    elif kind == 'recruitee':
        t = get(f'https://{b}.recruitee.com/api/offers/')
        try: jobs = [(j['title'], j.get('location', ''), j['careers_url']) for j in json.loads(t or '{}').get('offers', [])]
        except Exception: pass
    elif kind == 'workable':
        t = get(f'https://apply.workable.com/api/v1/widget/accounts/{b}')
        try: jobs = [(j['title'], ', '.join(x for x in (j.get('city'), j.get('country'), 'Remote' if j.get('telecommuting') else '') if x),
                      j.get('url') or j.get('shortlink') or f"https://apply.workable.com/{b}/j/{j['shortcode']}") for j in json.loads(t or '{}').get('jobs', [])]
        except Exception: pass
    for title, loc, url in jobs:
        if TITLE.search(title) and not NOT.search(title) and (PLACE.search(loc or '') or PLACE.search(title)):
            found.append({'board': f'{kind}:{b}', 'title': title, 'location': loc, 'url': url})
SEEN = f'{K.LOGS}/postings-seen.json'
seen = set(K.load_json(SEEN, []))
known = open(f'{K.DATA}/applications-log.csv', encoding='utf-8').read() if os.path.exists(f'{K.DATA}/applications-log.csv') else ''
new = [f for f in found if f['url'] not in seen and f['url'] not in known and not K.blocked(f['board'].split(':', 1)[1])]
json.dump(sorted(seen | {f['url'] for f in found}), open(SEEN, 'w'), indent=0)
print(f'{len(boards)} boards, {len(found)} matching postings, {len(new)} new since the last scan')
for f in new: print(f"- {f['title']} | {f['location']} | {f['board']} | {f['url']}")

if '--needs' in sys.argv:
    with open(f'{K.LOGS}/postings-scan.log', 'a') as f: f.write(f"{dt.datetime.now():%F %H:%M} {len(boards)} boards, {len(found)} matching postings, {len(new)} new\n")
    if new:
        p = K.NEEDS; s = open(p, encoding='utf-8').read() if os.path.exists(p) else '# Needs you\n\n## Replies\n'
        hdr = '## New postings from the daily scan (check the fit and apply by hand)\n'
        add = f"\n**{dt.date.today()}**\n" + ''.join(f"- {f['title']} | {f['location']} | {f['url']}\n" for f in new)
        s = s.replace(hdr, hdr + add, 1) if hdr in s else s + '\n' + hdr + add
        open(p, 'w', encoding='utf-8').write(s)
