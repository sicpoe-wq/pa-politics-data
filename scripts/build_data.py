import json, csv, re, sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikiparse import *
R = os.environ.get('RAW', 'raw') + '/'
OUTF = os.environ.get('OUT', 'v1') + '/seats.json'
TODAY_D = datetime.date.fromisoformat(os.environ['TODAY']) if os.environ.get('TODAY') else datetime.date.today()
TODAY = TODAY_D.isoformat()
def general_date(y):
    d = datetime.date(y, 11, 1)
    while d.weekday() != 0: d += datetime.timedelta(1)
    return (d + datetime.timedelta(1)).isoformat()   # Tuesday after the first Monday in November
def third_tuesday_jan(y):
    d = datetime.date(y, 1, 1)
    while d.weekday() != 1: d += datetime.timedelta(1)
    return (d + datetime.timedelta(14)).isoformat()
def next_term_end(first_end_year, period, month, day):
    y = first_end_year
    while datetime.date(y, month, day) < TODAY_D: y += period
    return datetime.date(y, month, day).isoformat()
CYCLE = int(general_date(TODAY_D.year)[:4]) if TODAY_D.year % 2 == 0 else TODAY_D.year + 1
WP = 'https://en.wikipedia.org/wiki/'
def wt(name): return json.load(open(R + 'wiki_' + name + '.json'))['parse']['wikitext']
def src(name, url): return {'name': name, 'url': url, 'retrieved': TODAY}
def pnorm(p):
    p = (p or '').replace('Pennsylvania ', '').replace('Democrat', 'Democratic').replace('Democraticic', 'Democratic').strip()
    return {'Forward Independent': 'Forward', '': 'Unknown'}.get(p, p)
def strip_inc(n): return re.sub(r'\s*\((?:incumbent|i)\)\s*', '', n).strip()

S_CL = src('unitedstates/congress-legislators (current members)', 'https://unitedstates.github.io/congress-legislators/legislators-current.json')
S_OS = src('Open States PA legislators bulk CSV', 'https://data.openstates.org/people/current/pa.csv')
S_HOUSE26 = src('Wikipedia: 2026 U.S. House elections in Pennsylvania', WP + '2026_United_States_House_of_Representatives_elections_in_Pennsylvania')
S_GOV26 = src('Wikipedia: 2026 Pennsylvania gubernatorial election', WP + '2026_Pennsylvania_gubernatorial_election')
S_SEN26 = src('Wikipedia: 2026 Pennsylvania Senate election', WP + '2026_Pennsylvania_Senate_election')
S_PAH26 = src('Wikipedia: 2026 Pennsylvania House of Representatives election', WP + '2026_Pennsylvania_House_of_Representatives_election')
S_PASEN = src('Wikipedia: Pennsylvania State Senate (member list)', WP + 'Pennsylvania_State_Senate')
S_PAHOUSE = src('Wikipedia: Pennsylvania House of Representatives (member list)', WP + 'Pennsylvania_House_of_Representatives')
S_SCOPA = src('Wikipedia: Supreme Court of Pennsylvania (current members)', WP + 'Supreme_Court_of_Pennsylvania')
S_US28 = src('Wikipedia: 2028 U.S. Senate elections (Pennsylvania section)', WP + '2028_United_States_Senate_elections#Pennsylvania')
S_US30 = src('Wikipedia: 2030 U.S. Senate elections (Pennsylvania section)', WP + '2030_United_States_Senate_elections#Pennsylvania')
S_CONST = src('Pennsylvania Constitution Art. II §2 (legislative terms begin Dec 1)', 'https://www.palegis.us/statutes/constitution')
GEN26 = '2026-11-03'   # the cycle the bundled Wikipedia candidate pages describe
_g = general_date(TODAY_D.year)
NEXT_GENERAL = _g if TODAY_D.year % 2 == 0 and _g >= TODAY else general_date(TODAY_D.year + (1 if TODAY_D.year % 2 else 2))
seats = []

# ---------- US Congress ----------
cl = json.load(open(R + 'legislators-current.json'))
pa = [m for m in cl if m['terms'][-1]['state'] == 'PA']
house_gen = {}
w = wt('2026_United_States_House_of_Representatives_elections_in_Pennsylvania')
for name, body in sections(w)[:17]:
    d = int(name.split()[-1]); subs = dict(sections(body, 3))
    boxes = election_boxes(subs.get('General election', ''))
    house_gen[d] = boxes[-1][1] if boxes else None
def photo_us(b): return f'https://unitedstates.github.io/images/congress/225x275/{b}.jpg'
for m in sorted(pa, key=lambda m: (m['terms'][-1]['type'], m['terms'][-1].get('district') or 0)):
    t = m['terms'][-1]; nm = m['name'].get('official_full') or (m['name']['first'] + ' ' + m['name']['last'])
    inc = {'name': nm, 'party': 'Democratic' if t['party']=='Democrat' else t['party'], 'photo': photo_us(m['id']['bioguide']), 'bioguide': m['id']['bioguide'],
           'lis': m['id'].get('lis'), 'since': m['terms'][0]['start'][:4], 'url': t.get('url'), 'phone': t.get('phone'), 'office': t.get('address')}
    if t['type'] == 'sen':
        cls = t.get('class'); ne = general_date(int(t['end'][:4]) - 1)
        seats.append({'id': f'us-sen-{cls}', 'level': 'Federal', 'body': 'US Senate', 'title': f'U.S. Senator (Class {"I"*cls if cls<4 else cls})',
            'district': None, 'incumbent': inc, 'termEnds': t['end'], 'nextElection': ne, 'upIn2026': False,
            'candidates': [], 'candidatesStatus': 'not-yet',
            'notes': [f'Next regular election {ne[:4]}. Declared candidates are not tracked yet (none listed on Wikipedia as of the last data update).'],
            'sources': [S_CL, S_US28 if ne.startswith('2028') else S_US30], 'map': None})
    else:
        d = t['district']; g = house_gen.get(d)
        ne = general_date(int(t['end'][:4]) - 1); up = ne == GEN26
        cands = [{'name': strip_inc(n), 'party': pnorm(p), 'incumbent': '(incumbent)' in n} for n, p in (g or [])] if up else []
        notes = []
        if up and not any(c['incumbent'] for c in cands): notes.append(f'Incumbent {nm} is not on the November 2026 general-election ballot (open seat).')
        if up and d == 7: notes.append('Andrew Tupone was disqualified from the ballot as a Green Party candidate (upheld by the PA Supreme Court) and has said he will run a write-in campaign.')
        seats.append({'id': f'us-house-{d}', 'level': 'Federal', 'body': 'US House', 'title': f"U.S. Representative, PA-{d}", 'district': d,
            'incumbent': inc, 'termEnds': t['end'], 'nextElection': ne, 'upIn2026': up, 'candidates': cands,
            'candidatesStatus': ('verified' if cands else 'unknown') if up else 'not-yet', 'notes': notes, 'sources': [S_CL, S_HOUSE26], 'map': {'layer': 'congress', 'district': d}})

# ---------- Statewide ----------
gov_imgs = {p['title']: p.get('thumbnail', {}).get('source') for p in json.load(open(R + 'wiki_images.json'))['query']['pages']}
def wimg(t): u = gov_imgs.get(t); return u.split('?')[0] if u else None
S_G = lambda pg: src('Wikipedia: ' + pg.replace('_', ' '), WP + pg)
KNOWN_PARTY = {'Josh Shapiro': 'Democratic', 'Austin Davis': 'Democratic', 'Dave Sunday': 'Republican', 'Timothy DeFoor': 'Republican', 'Stacy Garrity': 'Republican'}
def infobox_incumbent(pg):
    m = re.search(r'\|\s*incumbent\s*=\s*(.*)', wt(pg)); return clean(m.group(1)) if m else None
def gov_tickets():
    w = wt('2026_Pennsylvania_gubernatorial_election'); b = dict(sections(w))['General election']
    box = b[b.index('{{Election box begin'):]
    out = []
    for name, inner in top_templates(box):
        if not name.lower().startswith('election box candidate'): continue
        f = tpl_fields(inner); c = f.get('candidate', '')
        m = re.match(r'\{\{ubl\|(.*)\}\}$', c.strip(), re.S)
        parts = [clean(x) for x in re.split(r'\|(?![^\[]*\])', m.group(1))] if m else [clean(c)]
        out.append((parts, pnorm(party_name(f.get('party', '')))))
    if len(out) < 2: raise SystemExit('could not parse 2026 gubernatorial general-election box')
    return out
T = gov_tickets()
gov_c = [{'name': strip_inc(p[0]), 'party': pt, 'incumbent': '(incumbent)' in p[0], 'note': f'Running mate: {strip_inc(p[1])}' if len(p) > 1 else None} for p, pt in T]
ltg_c = [{'name': strip_inc(p[1]), 'party': pt, 'incumbent': '(incumbent)' in p[1], 'note': f'Running mate of {strip_inc(p[0])}'} for p, pt in T if len(p) > 1]
GOV_END = next_term_end(2027, 4, 1, 19) if TODAY_D < datetime.date(2027, 1, 20) else third_tuesday_jan(int(next_term_end(2031, 4, 1, 20)[:4]))
ROW_END = '2029-01-16' if TODAY_D <= datetime.date(2029, 1, 16) else third_tuesday_jan(int(next_term_end(2033, 4, 1, 20)[:4]))
def sw(sid, title, pg, img_title, since, end, cands, notes):
    nm = infobox_incumbent(pg) or '(unknown)'
    ne = general_date(int(end[:4]) - 1); up = ne == GEN26
    return (sid, title, nm, KNOWN_PARTY.get(nm, 'Unknown'), since if nm in KNOWN_PARTY else None, end, ne, up, cands if up else [], pg, img_title if nm in KNOWN_PARTY else nm, notes if up else [])
statewide = [
 sw('gov', 'Governor', 'Governor_of_Pennsylvania', 'Josh Shapiro', '2023', GOV_END, gov_c,
    ['Green Party candidate Tony Dastra was removed from the ballot (PA DOS withdrawal listing) and is running as a write-in.', 'Governor and Lt. Governor are elected on a joint ticket in the general election.']),
 sw('ltgov', 'Lieutenant Governor', 'Lieutenant_Governor_of_Pennsylvania', 'Austin Davis (politician)', '2023', GOV_END, ltg_c, ['Green Party Lt. Gov. candidate Craig Bolton was disqualified.']),
 sw('ag', 'Attorney General', 'Pennsylvania_Attorney_General', 'Dave Sunday', '2025', ROW_END, [], []),
 sw('auditor', 'Auditor General', 'Pennsylvania_Auditor_General', 'Timothy DeFoor', '2021', ROW_END, [], []),
 sw('treasurer', 'State Treasurer', 'Pennsylvania_Treasurer', 'Stacy Garrity', '2021', ROW_END, [], ['Garrity is the 2026 Republican nominee for Governor.'] if TODAY_D < datetime.date(2026, 11, 4) else []),
]
for sid, title, nm, party, since, end, ne, up, cands, pg, img, notes in statewide:
    srcs = [S_G(pg)] + ([S_GOV26] if up else [])
    seats.append({'id': 'pa-' + sid, 'level': 'Statewide', 'body': 'Statewide', 'title': title, 'district': None,
        'incumbent': {'name': nm, 'party': party, 'photo': wimg(img), 'since': since},
        'termEnds': end, 'termEndsNote': 'Term ends the third Tuesday of January (PA Const. Art. IV)', 'nextElection': ne, 'upIn2026': up,
        'candidates': cands, 'candidatesStatus': 'verified' if up else 'not-yet',
        'notes': notes + ([] if up else [f'Next election {ne[:4]}; candidates not yet declared/tracked.']), 'sources': srcs, 'map': None})

# ---------- PA Supreme Court ----------
w = wt('Supreme_Court_of_Pennsylvania'); i = w.find('Current members'); tbl = w[w.find('{|', i): w.find('\n|}', i) + 3]
for r in wikitable_rows(tbl):
    if len(r) < 6 or 'sortname' not in r[0]: continue
    nm = sortname(r[0].replace('{{sortname', '{{#invoke:sort|name'))
    chief = 'Chief Justice' in r[0]
    start = re.search(r'dts\|(\d{4})', r[2]); term = clean(r[3]); ret = clean(r[4]); party = clean(cellval(r[5]))
    seats.append({'id': 'scopa-' + re.sub(r'[^a-z]', '', nm.lower()), 'level': 'Statewide', 'body': 'PA Supreme Court',
        'title': 'Chief Justice, PA Supreme Court' if chief else 'Justice, PA Supreme Court', 'district': None,
        'incumbent': {'name': nm, 'party': party, 'photo': None, 'since': start.group(1) if start else None},
        'termEnds': term, 'termEndsNote': f'Current 10-year term ends {term} (per Wikipedia); justices face yes/no retention elections. Mandatory retirement year: {ret}.',
        'nextElection': None, 'upIn2026': False, 'candidates': [], 'candidatesStatus': 'not-applicable',
        'notes': ['No PA Supreme Court seats are on the November 2026 ballot (judicial elections are held in odd years).'],
        'sources': [S_SCOPA], 'map': None})

# ---------- PA General Assembly ----------
rows = list(csv.DictReader(open(R + 'pa.csv')))
osd = {(r['current_chamber'], int(r['current_district'])): r for r in rows}
def county_map(pagejson, tmpl):
    w = wt(pagejson); b = dict(sections(w))['Membership']; t = b[b.find('{|'): b.find('\n|}') + 3]; out = {}
    for r in wikitable_rows(t):
        if r and clean(r[0]).isdigit() and len(r) >= 5: out[int(clean(r[0]))] = clean(r[4]).replace('\n', ' ')
    return out
sen_cty = county_map('Pennsylvania_State_Senate', 0); house_cty = county_map('Pennsylvania_House_of_Representatives', 0)
def races(pg):
    return {int(r['race']): r for r in inline_races2(dict(sections(wt(pg)))['General election'])}
sen26 = races('2026_Pennsylvania_Senate_election'); house26 = races('2026_Pennsylvania_House_of_Representatives_election')
def leg_seat(ch, d):
    o = osd[(ch, d)]; upper = ch == 'upper'
    inc = {'name': o['name'], 'party': o['current_party'], 'photo': o['image'] or None, 'email': o['email'] or None,
           'phone': o['capitol_voice'] or None, 'url': (o['links'].split(';')[0] if o['links'] else None), 'openstates': o['id']}
    race = (sen26 if upper else house26).get(d)
    cands = []; notes = []
    if race:
        for n, p in race['cands']:
            cands.append({'name': strip_inc(n), 'party': pnorm(p), 'incumbent': strip_inc(n).split()[-1] == race['incumbent'].split()[-1] and race['status'].startswith('Running')})
        st = race['status']
        if not st.startswith('Running'): notes.append(f'Incumbent status: {st}.')
        if not upper and d == 2:
            cands = [{'name': 'Bob Merski', 'party': 'Democratic/Republican', 'incumbent': True, 'note': 'Cross-nominated: won the Republican nomination via write-in votes'}]
        if len(cands) == 1: notes.append('Unopposed on the general-election ballot (per Wikipedia).')
        if upper and d == 26: notes.append('Republican nominee Alfe Goodwin withdrew and was replaced on the ballot by Gail Scott.')
        if upper and d == 46: notes.append('Democratic nominee Evan James Snyder withdrew after the primary.')
    end = next_term_end(2026, 2, 11, 30) if not upper else next_term_end(2026 if d % 2 == 0 else 2028, 4, 11, 30)
    ne = general_date(int(end[:4]))
    up = race is not None and ne == GEN26
    if not up: cands = []; notes = []
    seat = {'id': f'pa-{"sen" if upper else "house"}-{d}', 'level': 'State Senate' if upper else 'State House',
        'body': 'PA Senate' if upper else 'PA House', 'title': f'PA State {"Senator" if upper else "Representative"}, District {d}', 'district': d,
        'counties': (sen_cty if upper else house_cty).get(d), 'incumbent': inc,
        'termEnds': end, 'termEndsNote': 'Legislative terms begin December 1 after the election (PA Const. Art. II §2).',
        'nextElection': ne, 'upIn2026': up, 'candidates': cands,
        'candidatesStatus': 'verified' if up and cands else ('unknown' if up else 'not-yet'), 'notes': notes,
        'sources': [S_OS, (S_PASEN if upper else S_PAHOUSE)] + ([S_SEN26 if upper else S_PAH26] if up else []) + [S_CONST],
        'map': {'layer': 'senate' if upper else 'house', 'district': d}}
    if not up and upper and d % 2 == 1 and ne == '2028-11-07': seat['notes'].append('Odd-numbered Senate districts were elected in 2024; next election 2028.')
    return seat
for d in range(1, 51): seats.append(leg_seat('upper', d))
for d in range(1, 204): seats.append(leg_seat('lower', d))
# ---------- Officeholder-elect from certified PA DOS results ----------
try:
    res = json.load(open(os.environ.get('OUT', 'v1') + '/results.json'))
    for e in res.get('elections', []):
        if e['type'] not in ('general', 'special') or not e.get('official'): continue
        for r in e.get('races', []):
            st = next((x for x in seats if x['id'] == r['seat']), None)
            if not st or not r.get('leader') or e['date'] != st['nextElection']: continue
            w = r['candidates'][0]
            st['elect'] = {'name': w['name'], 'party': w['party'], 'election': e['name'], 'electionKey': e['key'], 'certified': True,
                           'takesOffice': (datetime.date.fromisoformat(st['termEnds']) + datetime.timedelta(days=1 if st['termEnds'][5:7] == '11' else 0)).isoformat() if re.match(r'^\d{4}-\d{2}-\d{2}$', st['termEnds'] or '') else None,
                           'source': 'PA Department of State official returns'}
except FileNotFoundError:
    pass
out = {'generated': TODAY, 'nextGeneralElection': NEXT_GENERAL, 'candidateCycle': GEN26, 'seats': seats}
json.dump(out, open(OUTF, 'w'), separators=(',', ':'))
from collections import Counter
print(len(seats), Counter(s['body'] for s in seats), Counter(s['candidatesStatus'] for s in seats))
