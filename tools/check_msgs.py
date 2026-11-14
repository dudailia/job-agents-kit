# Checks every email in data/emails.json and every note in data/linkedin-notes.json against the writing rules in
# profile/settings.json ("writing", "regions", "candidate") and profile/never-apply.md. Run it after any change to the plan;
# the research shift must reach "problems: 0" before it stops. It fixes nothing: it lists what breaks a rule.
# usage: python3 -I tools/check_msgs.py
import datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K
W, C = K.W, K.C
US_SPELL = [r'\boptimiz', r'\borganiz', r'\bcategoriz', r'\bprioritiz', r'\brecogniz', r'\bspecializ', r'\bnormaliz', r'\bcenter\b',
            r'\bcolor\b', r'\bbehavior', r'\banalyz', r'\bmodeling\b', r'\bfavor', r'\blicense\b', r'\bauthoriz']
UK_SPELL = [r'\boptimis', r'\borganis', r'\bcategoris', r'\bprioritis', r'\brecognis', r'\bspecialis(e|ed|es|ing|ation)', r'\bnormalis', r'\bcentre\b',
            r'\bcolour', r'\bbehaviour', r'\banalys(e|ed|ing)\b', r'\bmodelling\b', r'\bfavour', r'\blicence\b', r'\bauthoris']
INBOX_WORDS = {'opportunities', 'careers', 'career', 'team', 'hello', 'info', 'recruitment', 'hiring', 'jobs', 'talent', 'people', 'hr', 'office', 'contact', 'enquiries'}
SIGN = f"{W['sign_off']}\n{C['name']}" if C['name'] else W['sign_off']
RIGHTS = {r: v.get('work_rights', '') for r, v in K.S['regions'].items() if v.get('work_rights')}

def words(s): return len(re.findall(r"[\w'’.-]+", s.split('\n\n' + W['sign_off'])[0]))

def check_text(t, nm):
    errs = []
    for p in W['banned']:
        if re.search(p, t, re.I): errs.append(f'{nm}: banned /{p}/')
    return errs

def check_email(x):
    errs, b, fu = [], x.get('body', ''), x.get('followup_body', '')
    for k in ('id', 'company', 'to', 'region', 'subject', 'body'):
        if not x.get(k): errs.append(f'missing "{k}"')
    reg = x.get('region', '')
    if reg and reg not in K.S['regions']: errs.append(f'region "{reg}" is not in settings.regions')
    if x.get('to') and not re.match(r'^[^@\s]+@[^@\s]+\.[a-z]{2,}$', x['to'], re.I): errs.append(f'address "{x["to"]}" does not look like an email address')
    if K.blocked(x.get('company', '')): errs.append(f'employer is in never-apply.md ({K.blocked(x["company"])})')
    if x.get('slot'):
        try:
            t = dt.datetime.fromisoformat(x['slot']).replace(tzinfo=K.tz_of(x))
            if not K.slot_ok(t, x): errs.append(f'slot {x["slot"]} is outside the {reg} window or your sender hours, or on a weekend')
        except ValueError: errs.append(f'slot "{x["slot"]}" is not YYYY-MM-DDTHH:MM')
    errs += check_text(b, 'body') + check_text(fu, 'follow-up') + check_text(x.get('subject', ''), 'subject')
    if W.get('max_words') and words(b) > W['max_words']: errs.append(f'{words(b)} words (>{W["max_words"]})')
    if W.get('require_cv_link') and C.get('cv_url') and C['cv_url'] not in b: errs.append('no CV link (candidate.cv_url)')
    if W.get('require_availability') and C.get('availability') and C['availability'] not in b: errs.append('availability (candidate.availability) not stated exactly')
    if RIGHTS.get(reg) and RIGHTS[reg] not in b: errs.append(f'missing the {reg} work-rights sentence')
    for r, s in RIGHTS.items():
        if r != reg and s != RIGHTS.get(reg) and s in b: errs.append(f'wrong region sentence ({r})')
    if W.get('opt_out_line') and W['opt_out_line'] not in b: errs.append('missing the opt-out line (writing.opt_out_line)')
    first = b.split('\n')[0]
    if W.get('salutation_regex') and not re.match(W['salutation_regex'], first): errs.append(f'salutation "{first[:40]}"')
    nm = re.match(r"^Dear ([A-Z][\w'’-]+),$", first)
    if nm and nm.group(1).lower() in INBOX_WORDS: errs.append(f'salutation "{first}" is an inbox word, not a name')
    if nm and x.get('person') and nm.group(1) not in x['person']: errs.append(f'salutation "{first}" does not match the recipient "{x["person"][:40]}"')
    if not b.rstrip().endswith(SIGN): errs.append(f'body does not end with the sign-off "{SIGN}"')
    if fu:
        if not fu.rstrip().endswith(SIGN): errs.append('follow-up does not end with the sign-off')
        if fu.split('\n')[0] != first: errs.append('follow-up salutation differs')
        lines = [l for l in fu.split('\n') if l.strip() and l.strip() not in (W['sign_off'], C['name']) and not re.match(r'^Dear ', l.strip())]
        if len(lines) > W['followup_max_lines']: errs.append(f'follow-up longer than {W["followup_max_lines"]} lines')
        if not x.get('followup_subject'): errs.append('follow-up has no subject')
    sp = K.region(x).get('spelling')
    for p in (US_SPELL if sp == 'UK' else UK_SPELL if sp == 'US' else []):
        if re.search(p, b + ' ' + fu, re.I): errs.append(f"{'US' if sp == 'UK' else 'UK'} spelling /{p}/ in a {sp}-spelling region")
    for a in x.get('attachments', []):
        if not os.path.exists(a): errs.append(f'attachment not found: {a}')
    return errs

def check_note(x):
    errs = check_text(x.get('note', ''), 'note')
    if len(x.get('note', '')) > W['linkedin_note_max']: errs.append(f"note {len(x['note'])} characters (>{W['linkedin_note_max']})")
    if K.blocked(x.get('company', '')): errs.append(f'employer is in never-apply.md ({K.blocked(x["company"])})')
    if not re.match(r'^https://(www\.)?linkedin\.com/in/', x.get('profile_url', '')): errs.append('no verified LinkedIn profile URL')
    return errs

if __name__ == '__main__':
    bad = 0; ids = set()
    for fn, fnc in ((K.EMAILS, check_email), (f'{K.DATA}/linkedin-notes.json', check_note)):
        for x in K.load_json(fn, []):
            e = fnc(x)
            if fnc is check_email:
                if x.get('id') in ids: e.append('duplicate id')
                ids.add(x.get('id'))
            if e: bad += 1; print(f"{os.path.basename(fn)[:8]} {str(x.get('id', ''))[:16]:16} {x.get('company', '')[:24]:24} " + '; '.join(e))
    print('problems:', bad); sys.exit(1 if bad else 0)
