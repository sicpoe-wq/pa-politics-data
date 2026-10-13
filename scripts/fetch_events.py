"""Public candidate events -> v1/events.json.
Sources (free, no key):
  * Mobilize public API (api.mobilize.us/v1/events, state=PA): speaking-type events (rallies, town halls,
    meet & greets, forums/debates) sponsored by a candidate's campaign or naming the candidate in the title.
  * Wikipedia "Debates and forums" tables in the 2026 PA election articles (already in RAW).
Links for candidates: Mobilize campaign page, Open States (PA legislators), congress-legislators social media.
Nothing is invented: an event is only attached to a candidate when the source names that candidate."""
import json, os, re, datetime, urllib.request, unicodedata
RAW = os.environ.get('RAW', 'raw') + '/'; OUT = os.environ.get('OUT', 'v1')
UA = {'User-Agent': 'pa-politics-data/1.0 (+https://github.com/sicpoe-wq/pa-politics-data)'}
NOW = datetime.datetime.now(datetime.timezone.utc); PAST_DAYS = 30
seats = json.load(open(f'{OUT}/seats.json'))['seats']
prev = {}
try: prev = json.load(open(f'{OUT}/events.json'))
except Exception: pass
import time, urllib.error
def get(url, t=60):
    for i in range(6):  # Mobilize rate-limits bursts (HTTP 429): pace requests and back off
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read(); time.sleep(1.5); return r
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 5: raise
            time.sleep(min(120, int(e.headers.get('Retry-After') or 0) or 10 * 2 ** i))
def norm(s): return re.sub(r'[^a-z ]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()).split()
SUFFIX = {'jr', 'sr', 'ii', 'iii', 'iv'}
def key(n): w = [x for x in norm(n) if x not in SUFFIX and len(x) > 1]; return (w[0], w[-1]) if w else ('', '')
# candidate index (only seats on the current ballot have candidates)
cands = []  # (seat, cand)
for s in seats:
    for c in s.get('candidates', []): cands.append((s, c))
ck = lambda s, c: f"{s['id']}|{c['name']}"
by_first_last = {}
for s, c in cands: by_first_last.setdefault(key(c['name']), []).append((s, c))
RACE = {'CONGRESSIONAL': 'US House', 'STATE_LEG': 'PA House', 'STATE_SENATE': 'PA Senate', 'GOVERNOR': 'Statewide', 'LT_GOVERNOR': 'Statewide', 'SENATE': 'US Senate'}
def find_cand(name, race=None, district=None):
    hits = by_first_last.get(key(name), [])
    if race: hits = [h for h in hits if h[0]['body'] == RACE.get(race, h[0]['body'])] or hits
    if district and len(hits) > 1: hits = [h for h in hits if str(h[0].get('district')) == str(district)] or hits
    if len(hits) == 1: return hits[0]
    # fall back to last name + same district
    if race and district:
        h2 = [(s, c) for s, c in cands if s['body'] == RACE.get(race) and str(s.get('district')) == str(district) and key(c['name'])[1] == key(name)[1]]
        if len(h2) == 1: return h2[0]
    return None
out, status = {}, []
def add(s, c, ev):
    e = out.setdefault(ck(s, c), {'events': [], 'links': []})
    if not any(x['id'] == ev['id'] for x in e['events']): e['events'].append(ev)
def link(s, c, label, url):
    if not url: return
    e = out.setdefault(ck(s, c), {'events': [], 'links': []})
    if not any(x['url'] == url for x in e['links']): e['links'].append({'label': label, 'url': url})

# ---------- Mobilize ----------
SPEAK_TYPES = {'RALLY', 'TOWN_HALL', 'MEET_GREET'}
SPEAK_RE = re.compile(r"town ?hall|forum|debate|rally|meet (and|&|\+) greet|meet the candidate|meet [A-Z]|conversation with|coffee with|q ?& ?a|speak|candidate night|listening (session|tour)|fireside|roundtable|ice cream social|breakfast with|lunch with|happy hour with|kickoff|kick-off", re.I)
KIND = [(r'watch party|watch the debate', 'Watch party'), (r'pre-?debate', 'Rally'), (r'debate', 'Debate'), (r'forum|candidate night', 'Forum'), (r'town ?hall|listening', 'Town hall'), (r'rally|kick-?off', 'Rally'), (r'meet|greet|coffee|conversation|breakfast|lunch|happy hour|social|fireside|roundtable', 'Meet & greet')]
def kind(title, t):
    for rx, k in KIND:
        if re.search(rx, title, re.I): return k
    return {'RALLY': 'Rally', 'TOWN_HALL': 'Town hall', 'MEET_GREET': 'Meet & greet'}.get(t, 'Public appearance')
try:
    since = int((NOW - datetime.timedelta(days=PAST_DAYS)).timestamp())
    nowts = int(NOW.timestamp()); evs, seen = [], set()
    for q in (f'timeslot_start=gte_{nowts}', f'timeslot_start=gte_{since}&timeslot_end=lt_{nowts}'):
        url = f'https://api.mobilize.us/v1/events?state=PA&{q}&per_page=100'
        while url:
            d = json.loads(get(url))
            for e in d['data']:
                if e['id'] not in seen: seen.add(e['id']); evs.append(e)
            url = d.get('next')
    n_att = 0
    for e in evs:
        if e.get('visibility') != 'PUBLIC' or e.get('address_visibility') == 'PRIVATE' and False: pass
        title = e.get('title') or ''; t = e.get('event_type')
        if not (t in SPEAK_TYPES or (t in ('COMMUNITY', 'MEETING', 'OTHER', 'FUNDRAISER') and SPEAK_RE.search(title))): continue
        if t == 'FUNDRAISER': continue  # ticketed, not a public speaking event
        sp = e.get('sponsor') or {}; who = []
        if sp.get('candidate_name'):
            m = find_cand(sp['candidate_name'], sp.get('race_type'), sp.get('district') or None)
            if m: who.append(m)
        # candidates explicitly named in the title (e.g. "Rally with Josh Shapiro")
        tn = ' ' + ' '.join(norm(title)) + ' '
        for (f, l), hits in by_first_last.items():
            if f and l and f' {f} {l} ' in tn and len(hits) == 1 and hits[0] not in who: who.append(hits[0])
        if not who: continue
        loc = e.get('location') or {}; venue = loc.get('venue') or ''
        private = 'private' in venue.lower() or 'private' in ' '.join(loc.get('address_lines') or []).lower()
        place = None if e.get('is_virtual') else {'venue': None if private else venue or None,
                 'address': None if private else ', '.join(x for x in (loc.get('address_lines') or []) if x) or None,
                 'city': loc.get('locality'), 'note': 'Address shared after RSVP' if private else None}
        for ts in e.get('timeslots', [])[:6]:
            st = datetime.datetime.fromtimestamp(ts['start_date'], datetime.timezone.utc)
            if st < NOW - datetime.timedelta(days=PAST_DAYS): continue
            en = datetime.datetime.fromtimestamp(ts['end_date'], datetime.timezone.utc) if ts.get('end_date') else None
            ev = {'id': f"mob-{e['id']}-{ts['id']}", 'title': title.strip(), 'kind': kind(title, t), 'start': st.isoformat(), 'end': en.isoformat() if en else None,
                  'timeKnown': True, 'virtual': bool(e.get('is_virtual')), 'location': place, 'host': sp.get('name'),
                  'url': e.get('browser_url'), 'source': 'Mobilize', 'role': None}
            for s, c in who: add(s, c, ev); n_att += 1
        for s, c in who:
            if sp.get('candidate_name') and sp.get('event_feed_url') and find_cand(sp['candidate_name'], sp.get('race_type')) == (s, c):
                link(s, c, 'Campaign events (Mobilize)', sp['event_feed_url'])
    # campaign pages for candidates whose org has only non-speaking events
    for e in evs:
        sp = e.get('sponsor') or {}
        if sp.get('candidate_name') and sp.get('event_feed_url'):
            m = find_cand(sp['candidate_name'], sp.get('race_type'), sp.get('district') or None)
            if m: link(*m, 'Campaign events (Mobilize)', sp['event_feed_url'])
    status.append({'source': 'Mobilize public API', 'ok': True, 'events': len(evs), 'attached': n_att})
except Exception as ex:
    status.append({'source': 'Mobilize public API', 'ok': False, 'error': str(ex)[:200]})
    for k, v in prev.get('byCandidate', {}).items():  # keep last good Mobilize data
        for ev in v['events']:
            if ev['source'] == 'Mobilize':
                sid, nm = k.split('|', 1); s = next((x for x in seats if x['id'] == sid), None); c = s and next((x for x in s['candidates'] if x['name'] == nm), None)
                if c: add(s, c, ev)

# ---------- Wikipedia debate / forum tables ----------
def wt(n): return json.load(open(RAW + 'wiki_' + n + '.json'))['parse']['wikitext']
def clean(x):
    x = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', x, flags=re.S); x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    x = re.sub(r'^\s*(scope|style|colspan|rowspan)="[^"]*"\s*(\w+="[^"]*"\s*)*\|', '', x.strip())
    x = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', x); x = re.sub(r'\[https?://\S+ ([^\]]*)\]', r'\1', x)
    x = re.sub(r"'''?|<[^>]+>|\{\{abbr\|([^|}]*)\|[^}]*\}\}", lambda m: m.group(1) or '' if m.lastindex else '', x)
    return re.sub(r'\s+', ' ', x.replace('&nbsp;', ' ')).strip()
MON = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
def pdate(x):
    m = re.search(r'([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})', x)
    return datetime.date(int(m.group(3)), MON[m.group(1).lower()], int(m.group(2))) if m and m.group(1).lower() in MON else None
ROLE = {'P': 'Participant', 'I': 'Invited', 'A': None, 'N': None, 'W': None}
def debate_tables(page, seat_for):
    s = wt(page); n = 0
    heads = [(m.start(), m.group(1).strip()) for m in re.finditer(r'\n=+ *([^=\n]+?) *=+', s)]
    for m in re.finditer(r'\n=+ *Debates?( and forums)? *=+\n', s):
        end = next((p for p, h in heads if p > m.start() + 5), len(s)); sec = s[m.end():end]
        ctx = ' '.join(h for p, h in heads if p < m.start())  # nearest district heading
        dist = re.findall(r'District (\d+)', ctx); seat = seat_for(int(dist[-1]) if dist else None)
        if not seat: continue
        for tb in re.findall(r'\{\|.*?\n\|\}', sec, re.S):
            cap = clean((re.search(r'\|\+([^\n]*)', tb) or [None, ''])[1])
            rows = re.split(r'\n\|-[^\n]*', tb); names = []
            for r in rows:
                cells = [c for c in re.split(r'\n[!|]', '\n' + r.strip()) if c.strip()]
                if r.strip().startswith('!') and cells and all(len(clean(c)) < 30 for c in cells) and not any(re.search(r'No\.|Date|Host|Key', c) for c in cells) and not re.match(r'^\s*!?\s*(scope="row"\s*\|)?\s*\d', r.strip()) and not pdate(clean(r)):
                    nm = [clean(c) for c in cells if clean(c)]
                    if nm: names = nm
            for r in rows:
                cells = [c for c in re.split(r'\n[!|]', '\n' + r.strip()) if c.strip()]
                if len(cells) < 5 or not re.match(r'^\s*!?\s*(scope="row"\s*\|)?\s*\d+', r.strip()): continue
                d = pdate(clean(cells[1]))
                if not d or not names: continue
                if d < (NOW - datetime.timedelta(days=PAST_DAYS)).date(): continue
                host = clean(cells[2]) or None; urls = re.findall(r'https?://[^\s|\]}]+', r)
                marks = [re.sub(r"[^A-Z]", '', re.sub(r'\{\{[^|]*\|', '', c).split('}}')[0]) for c in cells[5:5 + len(names)]]
                for nm, mk in zip(names, marks):
                    role = ROLE.get(mk[:1]) if mk else None
                    if not role: continue
                    hit = [c for c in seat['candidates'] if key(c['name'])[1] == key(nm)[-1] or norm(c['name'])[-1:] == norm(nm)[-1:]]
                    if len(hit) != 1: continue
                    ev = {'id': f"wp-{seat['id']}-{d}-{(host or '')[:20]}", 'title': (f"{m2.group(1)} primary debate/forum" if (m2 := re.search(r'(Democratic|Republican) primary', cap)) else 'Candidate debate') + f" – {seat['title']}",
                          'kind': 'Debate', 'start': d.isoformat(), 'end': None, 'timeKnown': False, 'virtual': False, 'location': None, 'host': host,
                          'url': urls[0] if urls else f"https://en.wikipedia.org/wiki/{page}", 'source': 'Wikipedia', 'sourcePage': f"https://en.wikipedia.org/wiki/{page}", 'role': role}
                    add(seat, hit[0], ev); n += 1
    return n
try:
    sid = {s['id']: s for s in seats}
    n = debate_tables('2026_Pennsylvania_gubernatorial_election', lambda d: sid.get('pa-gov'))
    n += debate_tables('2026_United_States_House_of_Representatives_elections_in_Pennsylvania', lambda d: d and sid.get(f'us-house-{d}'))
    status.append({'source': 'Wikipedia debate & forum tables', 'ok': True, 'attached': n})
except Exception as ex:
    status.append({'source': 'Wikipedia debate & forum tables', 'ok': False, 'error': str(ex)[:200]})

# ---------- links: official/social for incumbents ----------
try:
    soc = {x['id']['bioguide']: x['social'] for x in json.loads(get('https://unitedstates.github.io/congress-legislators/legislators-social-media.json'))}
except Exception: soc = {}
import csv
osr = {}
try:
    for r in csv.DictReader(open(RAW + 'pa.csv')): osr[r['name']] = r
except Exception: pass
for s, c in cands:
    if not c.get('incumbent'): continue
    inc = s['incumbent']
    if inc.get('url'): link(s, c, 'Official page', inc['url'])
    sc = soc.get(inc.get('bioguide') or '', {})
    if sc.get('twitter'): link(s, c, 'X / Twitter', f"https://x.com/{sc['twitter']}")
    if sc.get('facebook'): link(s, c, 'Facebook', f"https://www.facebook.com/{sc['facebook']}")
    r = osr.get(inc['name'])
    if r:
        if r.get('twitter'): link(s, c, 'X / Twitter', f"https://x.com/{r['twitter']}")
        if r.get('facebook'): link(s, c, 'Facebook', f"https://www.facebook.com/{r['facebook']}")
        if r.get('instagram'): link(s, c, 'Instagram', f"https://www.instagram.com/{r['instagram']}")
for v in out.values(): v['events'].sort(key=lambda e: e['start'])
json.dump({'generated': NOW.isoformat(timespec='seconds'), 'pastDays': PAST_DAYS, 'status': status, 'byCandidate': out},
          open(f'{OUT}/events.json', 'w'), separators=(',', ':'))
print(status); print('candidates with events:', sum(1 for v in out.values() if v['events']), 'with links:', sum(1 for v in out.values() if v['links']))
