"""50-state build -> v2/states/XX/seats.json (+ votes/us_*.json) and v2/index.json.
PA keeps its full-depth v1 seats (statewide row offices, PA Supreme Court, 2026 legislative candidates).
Sources: congress-legislators, Open States, Wikipedia national 2026 House/Senate/governor articles,
List of current U.S. governors. Missing data is marked unknown/not available, never guessed."""
import csv, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__)); from states_meta import STATES, dkey
RAW = os.environ.get('RAW', 'raw') + '/'; V1 = os.environ.get('OUT', 'v1'); V2 = 'v2'
TODAY = os.environ.get('TODAY') or datetime.date.today().isoformat()
GEN = '2026-11-03'
WP = 'https://en.wikipedia.org/wiki/'
def src(n, u): return {'name': n, 'url': u, 'retrieved': TODAY}
S_CL = src('unitedstates/congress-legislators', 'https://github.com/unitedstates/congress-legislators')
S_OS = src('Open States (current legislators)', 'https://open.pluralpolicy.com/data/')
S_H26 = src('Wikipedia: 2026 U.S. House elections', WP + '2026_United_States_House_of_Representatives_elections')
S_S26 = src('Wikipedia: 2026 U.S. Senate elections', WP + '2026_United_States_Senate_elections')
S_G26 = src('Wikipedia: 2026 U.S. gubernatorial elections', WP + '2026_United_States_gubernatorial_elections')
S_GOV = src('Wikipedia: List of current U.S. governors', WP + 'List_of_current_United_States_governors')
CH = {  # upper, lower chamber names
    'CA': ('State Senate', 'State Assembly'), 'NV': ('State Senate', 'State Assembly'), 'NY': ('State Senate', 'State Assembly'),
    'WI': ('State Senate', 'State Assembly'), 'NJ': ('State Senate', 'General Assembly'), 'MD': ('State Senate', 'House of Delegates'),
    'VA': ('State Senate', 'House of Delegates'), 'WV': ('State Senate', 'House of Delegates'), 'NE': ('Legislature', None)}
def wt(n): return json.load(open(RAW + 'wiki_' + n + '.json'))['parse']['wikitext']
def clean(x):
    x = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', x, flags=re.S); x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    x = re.sub(r'\{\{sortname\|([^|}]*)\|([^|}]*)[^}]*\}\}', r'\1 \2', x)
    x = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', x); x = re.sub(r'\{\{[^{}]*\}\}', '', x)
    x = re.sub(r"'''?|<[^>]+>", '', x); return re.sub(r'\s+', ' ', x.replace('&nbsp;', ' ')).strip()
PARTY = {'Democratic': 'Democratic', 'Republican': 'Republican', 'Libertarian': 'Libertarian', 'Green': 'Green', 'Independent': 'Independent'}
def cand_list(cell):
    out = []
    cell = re.sub(r'(lainlist\s*\|?\s*)\*', r'\1\n*', cell, flags=re.I)
    for line in re.findall(r'\n\s*\*([^\n]+)', '\n' + cell):
        line = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', line, flags=re.S)
        line = re.sub(r'<ref[^>]*>.*$', '', line)  # unterminated ref (multi-line)
        line = re.sub(r'\{\{Party stripe\|[^}]*\}\}', '', line, flags=re.I)
        m = re.match(r'(.*)\(([^()]*)\)\s*$', clean(line))
        if not m: continue
        name, party = m.group(1).strip(), m.group(2).strip()
        if not name or len(name) > 60 or re.search(r'[{}\[\]|=]', name): continue
        out.append({'name': name, 'party': party, 'incumbent': False})
    return out
def rows_of(table): return re.split(r'\n\|-[^\n]*', table)
# ---------- national pages ----------
house = wt('2026_United_States_House_of_Representatives_elections')
H26, REDIS = {}, set()
for m in re.finditer(r'\n==([A-Z][A-Za-z ]+)==\n', house):
    nm = m.group(1).strip(); st = next((s for s, n, _ in STATES if n == nm), None)
    if not st: continue
    end = house.find('\n==', m.end()); sec = house[m.end():end if end > 0 else None]
    if re.search(r'Redistricted from|\(new seat\)', sec): REDIS.add(st)
    cur = None
    for r in rows_of(sec):
        d = re.search(r'\{\{ushr\|' + st + r'\|(\w+)\|', r)
        if d: cur = 'AL' if d.group(1) == 'AL' else str(int(d.group(1)))
        if cur and 'lainlist' in r:
            i = r.lower().find('plainlist'); H26.setdefault(cur and (st, cur), []).extend(cand_list(r[i:]))
def summary_rows(page, anchor):
    s = wt(page); i = s.find(anchor); out = {}
    if i < 0: return out
    tb = s[i:s.find('\n|}', i)]
    for r in rows_of(tb):
        h = re.search(r'\n?!\s*\[\[[^|\]]*\|([^\]]+)\]\]', r)
        if not h: continue
        label = h.group(1).strip(); st = next((s2 for s2, n, _ in STATES if label.startswith(n)), None)
        if not st or 'lainlist' not in r: continue
        j = r.lower().find('plainlist'); out[(st, 'special' if 'special' in label.lower() else 'regular')] = cand_list(r[j:])
    return out
S26 = summary_rows('2026_United_States_Senate_elections', '=== Elections leading to the next Congress ===')
G26 = summary_rows('2026_United_States_gubernatorial_elections', '=== States ===')
gov = {}
gs = wt('List_of_current_United_States_governors')
for r in rows_of(gs[gs.find('|+ Current state governors'):]):
    m = re.search(r'\[\[Governor of ([^|\]]+)\|', r)
    if not m: continue
    st = next((s2 for s2, n, _ in STATES if n == m.group(1).strip()), None)
    if not st: continue
    nm = re.search(r'!\s*scope="row"\s*\|\s*(.+)', r); cells = [c.strip() for c in r.split('\n|')]
    party = next((clean(c) for c in cells if re.search(r'\[\[[^\]]*(Party|party)[^\]]*\|(Democratic|Republican|Independent)', c)), 'Unknown')
    te = next((clean(c) for c in cells if re.match(r'^\d{4}', clean(c))), None)
    ts = re.search(r'\{\{dts\|(\d{4})', r)
    gov[st] = {'name': clean(nm.group(1)) if nm else None, 'party': party, 'termEnd': te, 'since': ts.group(1) if ts else None}
# ---------- congress-legislators ----------
leg = json.load(open(RAW + 'legislators-current.json'))
soc = {x['id']['bioguide']: x.get('social', {}) for x in json.load(open(RAW + 'legislators-social-media.json'))}
def gen_date(y):  # first Tuesday after first Monday in Nov
    d = datetime.date(y, 11, 2)
    while d.weekday() != 1: d += datetime.timedelta(days=1)
    return d.isoformat()
def _fl(n):
    w = [x for x in re.sub(r'[^A-Za-z .-]', '', n).replace('.', ' ').split() if x.lower() not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return (w[0][:3].lower(), w[-1].lower()) if w else ('', '')
def mark_inc(cands, name):
    """flag the incumbent only on an unambiguous first+last match (e.g. two 'Dan Sullivan's on Alaska's ballot -> exact name only)"""
    if not name: return cands
    hits = [c for c in cands if _fl(c['name']) == _fl(name)]
    if len(hits) > 1: hits = [c for c in hits if c['name'] == name]
    for c in hits: c['incumbent'] = True
    return cands
index = []
# national roll-call metadata (shared by all states); per-state files carry only {src: {memberId: vote}}
ALLV = {}
os.makedirs(f'{V2}/national', exist_ok=True)
for f in ('us_house', 'us_senate'):
    try: ALLV[f] = json.load(open(f'work/votes_us/{f}.json'))
    except FileNotFoundError: continue
    json.dump({'fetched': ALLV[f]['fetched'], 'rolls': [{k: v for k, v in r.items() if k != 'votes'} for r in ALLV[f]['votes']]}, open(f'{V2}/national/{f}.json', 'w'), separators=(',', ':'))
for st, sname, fips in STATES:
    seats = []
    if st == 'PA':
        pa = json.load(open(f'{V1}/seats.json'))
        for s in pa['seats']:
            s = dict(s); s['state'] = 'PA'
            s['body'] = {'PA Senate': 'State Senate', 'PA House': 'State House'}.get(s['body'], s['body'])
            if s.get('map'): s['map'] = {**s['map'], 'district': str(s['map']['district'])}
            seats.append(s)
    else:
        mem = [(m, m['terms'][-1]) for m in leg if m['terms'][-1]['state'] == st]
        for m, t in sorted(mem, key=lambda x: (x[1]['type'], x[1].get('district', 0))):
            nm = m['name'].get('official_full') or f"{m['name']['first']} {m['name']['last']}"
            first = min(int(x['start'][:4]) for x in m['terms'] if x['type'] == t['type'])
            inc = {'name': nm, 'party': t['party'], 'photo': f"https://unitedstates.github.io/images/congress/225x275/{m['id']['bioguide']}.jpg",
                   'bioguide': m['id']['bioguide'], 'lis': m['id'].get('lis'), 'since': str(first), 'url': t.get('url'), 'phone': t.get('phone'), 'office': t.get('address')}
            end_y = int(t['end'][:4]); ne = gen_date(end_y - 1) if end_y - 1 >= 2026 else None
            if t['type'] == 'sen':
                special = (st, 'special') in S26 and t['class'] == 3 and end_y != 2027
                up = end_y == 2027 or special
                cands = mark_inc(S26.get((st, 'special' if special else 'regular'), []) if up else [], nm)
                seats.append({'id': f"us-sen-{t['class']}", 'state': st, 'level': 'Federal', 'body': 'US Senate', 'title': f"U.S. Senator (Class {t['class']})", 'district': None,
                              'incumbent': inc, 'termEnds': t['end'], 'nextElection': GEN if up else ne, 'upIn2026': up, 'candidates': cands,
                              'candidatesStatus': 'verified' if cands else ('unknown' if up else 'not-yet'),
                              'notes': (['2026 special election for the remainder of this term.'] if special else []) + ([] if up else [f'Next regular election {ne[:4] if ne else "—"}.']),
                              'sources': [S_CL] + ([S_S26] if up else []), 'map': None})
            else:
                d = 'AL' if t['district'] == 0 else str(t['district'])
                cands = mark_inc(list(H26.get((st, d), [])), nm)
                notes = ['District lines change for 2026 (mid-decade redistricting, per Wikipedia); the map shows the current 119th-Congress lines.'] if st in REDIS else []
                seats.append({'id': f"us-house-{d}", 'state': st, 'level': 'Federal', 'body': 'US House', 'title': f"U.S. Representative, {st}-{d if d == 'AL' else d.zfill(2)}" if d != 'AL' else f'U.S. Representative, {st} at-large',
                              'district': None if d == 'AL' else int(d), 'incumbent': inc, 'termEnds': t['end'], 'nextElection': GEN, 'upIn2026': True,
                              'candidates': cands, 'candidatesStatus': 'verified' if cands else 'unknown', 'notes': notes, 'sources': [S_CL, S_H26],
                              'map': {'layer': 'congress', 'district': dkey(d)}})
        # vacancies: districts on the map with no current member
        try:
            gd = {f['properties']['district'] for f in json.load(open(f'{V2}/states/{st}/geo/congress.geojson'))['features']}
        except Exception: gd = set()
        have = {s['map']['district'] for s in seats if s['body'] == 'US House'}
        for d in sorted(gd - have, key=lambda x: (len(x), x)):
            d2 = 'AL' if d == 'al' else d
            seats.append({'id': f'us-house-{d2}', 'state': st, 'level': 'Federal', 'body': 'US House', 'title': f'U.S. Representative, {st}-{d2.zfill(2)}', 'district': int(d2) if d2.isdigit() else None,
                          'incumbent': {'name': 'Vacant', 'party': 'Vacant'}, 'termEnds': None, 'nextElection': GEN, 'upIn2026': True, 'candidates': list(H26.get((st, d2), [])),
                          'candidatesStatus': 'verified' if H26.get((st, d2)) else 'unknown', 'notes': ['Seat currently vacant (no current member in congress-legislators).'], 'sources': [S_CL, S_H26], 'map': {'layer': 'congress', 'district': d}})
        g = gov.get(st)
        if g and g['name']:
            up = (st, 'regular') in G26; cands = mark_inc(list(G26.get((st, 'regular'), [])), g['name'])
            te = re.match(r'(\d{4})', g['termEnd'] or '')
            seats.append({'id': 'gov', 'state': st, 'level': 'State', 'body': 'Statewide', 'title': 'Governor', 'district': None,
                          'incumbent': {'name': g['name'], 'party': g['party'], 'since': g['since']}, 'termEnds': te.group(1) if te else None,
                          'termEndsNote': f"Term ends {g['termEnd']} (per Wikipedia; exact inauguration date varies by state)." if g['termEnd'] else None,
                          'nextElection': GEN if up else None, 'upIn2026': up, 'candidates': cands, 'candidatesStatus': 'verified' if cands else ('unknown' if up else 'not-yet'),
                          'notes': [] if up else ['No 2026 gubernatorial election in this state.'], 'sources': [S_GOV] + ([S_G26] if up else []), 'map': None})
        # state legislators
        up_name, lo_name = CH.get(st, ('State Senate', 'State House'))
        try: rows = list(csv.DictReader(open(f'{RAW}os/{st.lower()}.csv')))
        except FileNotFoundError: rows = []
        by = {}
        for r in rows: by.setdefault((r['current_chamber'], r['current_district']), []).append(r)
        for (ch, dist), mem2 in sorted(by.items(), key=lambda x: (x[0][0], (len(x[0][1]), x[0][1]))):
            body = 'State Senate' if ch in ('upper', 'legislature') else 'State House'
            cname = up_name if ch in ('upper', 'legislature') else lo_name
            layer = 'senate' if body == 'State Senate' else 'house'
            for i, r in enumerate(sorted(mem2, key=lambda r: r['name'])):
                multi = len(mem2) > 1
                seats.append({'id': f"{'st-sen' if layer == 'senate' else 'st-house'}-{dkey(dist)}{f'-{i + 1}' if multi else ''}", 'state': st, 'level': 'State', 'body': body,
                              'chamberName': cname, 'title': f"{cname} District {dist}" + (f" (seat {i + 1} of {len(mem2)})" if multi else ''),
                              'district': int(dist) if dist.isdigit() else None, 'districtLabel': dist,
                              'incumbent': {'name': r['name'], 'party': r['current_party'] or 'Unknown', 'photo': r['image'] or None, 'email': r['email'] or None,
                                            'phone': r['capitol_voice'] or r['district_voice'] or None, 'url': (r['links'].split(';')[0].strip() or None) if r.get('links') else None, 'openstates': r['id']},
                              'termEnds': None, 'termEndsNote': 'Term end not available in Open States data.', 'nextElection': None, 'upIn2026': False, 'ballotUnknown': True,
                              'candidates': [], 'candidatesStatus': 'unknown', 'notes': ['2026 candidate list not yet available for this state legislature (no structured source).'] + (['Multi-member district.'] if multi else []),
                              'sources': [S_OS], 'map': {'layer': layer, 'district': dkey(dist)}})
    # reconcile map references with the boundary files; unmatched -> no map (with an honest note)
    for layer in ('senate', 'house'):
        try: g = {f['properties']['district'] for f in json.load(open(f'{V2}/states/{st}/geo/{layer}.geojson'))['features']}
        except FileNotFoundError: g = set()
        for x in seats:
            if not x.get('map') or x['map']['layer'] != layer or x['map']['district'] in g: continue
            d0 = x['map']['district']; alt = re.sub(r'[ab]$', '', d0)
            if alt in g: x['map'] = {**x['map'], 'district': alt}; x['notes'].append(f'Sub-district {x.get("districtLabel", d0)}; map shows the whole legislative district {alt}.')
            else:
                x['map'] = None
                x['notes'].append('No Census boundary for this district (e.g. floterial, tribal or at-large seat); not shown on the map.')
    os.makedirs(f'{V2}/states/{st}/votes', exist_ok=True)
    json.dump({'generated': TODAY, 'state': st, 'nextGeneralElection': GEN, 'candidateCycle': GEN, 'seats': seats}, open(f'{V2}/states/{st}/seats.json', 'w'), separators=(',', ':'))
    # per-state congressional votes (current members only)
    ids = {s['incumbent'].get('bioguide') for s in seats if s['body'] == 'US House'} | {s['incumbent'].get('lis') for s in seats if s['body'] == 'US Senate'}
    for f in ('us_house', 'us_senate'):
        allv = ALLV.get(f)
        if not allv: continue
        out = {}
        for r in allv['votes']:
            v = {k[3:]: x for k, x in r['votes'].items() if k[:2] == st and k[3:] in ids}
            if v: out[r['src']] = v
        json.dump({'fetched': allv['fetched'], 'votes': out}, open(f'{V2}/states/{st}/votes/{f}.json', 'w'), separators=(',', ':'))
    geo = [l for l in ('congress', 'senate', 'house') if os.path.exists(f'{V2}/states/{st}/geo/{l}.geojson')]
    up_name, lo_name = CH.get(st, ('State Senate', 'State House'))
    index.append({'code': st, 'name': sname, 'fips': fips, 'chambers': {'upper': up_name, 'lower': lo_name}, 'unicameral': st == 'NE', 'layers': geo,
                  'counts': {b: sum(1 for s in seats if s['body'] == b) for b in ('US Senate', 'US House', 'Statewide', 'State Senate', 'State House', 'PA Supreme Court')},
                  'full': st == 'PA', 'redistricted2026': st in REDIS})
json.dump({'generated': TODAY, 'states': index}, open(f'{V2}/index.json', 'w'), separators=(',', ':'))
print('states built:', len(index), 'redistricted:', sorted(REDIS))
