"""Official PA Department of State election returns -> v1/results.json.
Source: electionreturns.pa.gov Report Center API (GetElectionList / GetFilterData / GenerateReport CSV).
County rows are summed per office/district/party/candidate. Nothing is estimated: a race appears only if PA DOS reports it."""
import csv, io, json, os, re, sys, urllib.request, datetime
BASE = 'https://www.electionreturns.pa.gov/api/Reports/'
H = {'User-Agent': 'Mozilla/5.0 (PA-Politics data bot; github.com/sicpoe-wq/pa-politics-data)', 'Content-Type': 'application/json'}
OUT = os.environ.get('OUT', 'v1')
def req(url, body=None):
    r = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=H), timeout=180).read()
    if r.lstrip()[:1] == b'<': raise RuntimeError('PA DOS returned HTML (bot protection?)')
    return r
def jget(url):
    j = json.loads(req(url)); return json.loads(j) if isinstance(j, str) else j
OFFICE = {  # PA DOS office name -> (seat id builder)
    'United States Senator': 'ussen', 'Governor': 'pa-gov', 'Lieutenant Governor': 'pa-ltgov', 'Attorney General': 'pa-ag',
    'Auditor General': 'pa-auditor', 'State Treasurer': 'pa-treasurer', 'Representative in Congress': 'us-house',
    'Senator in the General Assembly': 'pa-sen', 'Representative in the General Assembly': 'pa-house',
}
# U.S. Senate class by election year (PA: class 1 = 2024/2030, class 3 = 2022/2028)
USSEN_CLASS = lambda yr: 1 if yr % 6 == 2 else 3
def seat_id(office, district, year):
    k = next((v for o, v in OFFICE.items() if office.strip().lower() == o.lower()), None)
    if not k: return None
    if k == 'ussen': return f'us-sen-{USSEN_CLASS(year)}'
    if k.startswith('pa-') and k in ('pa-gov', 'pa-ltgov', 'pa-ag', 'pa-auditor', 'pa-treasurer'): return k
    m = re.match(r'(\d+)', district or '')
    return f'{k}-{int(m.group(1))}' if m else None
def num(s): return int((s or '0').replace(',', '') or 0)
def title_name(n):
    n = re.sub(r'\s+', ' ', n.strip())
    t = n.title().replace(' Jr', ' Jr.').replace('Jr..', 'Jr.')
    t = re.sub(r"\b(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    return re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group(1).upper(), t)

def elections_wanted(lst, today):
    """2026 general (once PA DOS posts it), 2026 primary, 2024 & 2022 generals, and 2025-26 special elections."""
    out = []
    for e in lst:
        y, t, n = e['ElectionYear'], e['ElectionType'], e['ElectionName']
        if (t == 'G' and y in (2026, 2024, 2022)) or (t == 'P' and y == 2026) or (t == 'S' and y in (2025, 2026) and re.search(r'Legislative|Senatorial|Congress', n, re.I)):
            out.append(e)
    return out

def fetch_election(e):
    eid, st = e['Electionid'], e['ElectionType']
    f = jget(f'{BASE}GetFilterData?electionId={eid}&electionsubtype={st}')
    fd = jget(f'{BASE}GetFilterData?electionId={eid}&electionsubtype={st}&reportType=D')
    offices = [o['OfficeID'] for o in f.get('Table', []) if any(o['OfficeName'].lower() == k.lower() for k in OFFICE)]
    if not offices: return None
    body = {'ElectionID': eid, 'ElectionsubType': st, 'OfficeIds': offices, 'RetOfficeIds': [],
            'PartyIds': [p['PartyID'] for p in f['Table1']], 'DistrictIds': [x['DistrictID'] for x in fd['Table1']],
            'CandidateIds': [c['CandidateID'] for c in f['Table2'] if c['OfficeID'] in offices], 'CountyIds': [], 'ReferendumIds': [],
            'ReferendumDetailIds': [], 'ExportType': 'C', 'ReportType': 'D', 'FileName': 'Report'}
    raw = req(BASE + 'GenerateReport', body).decode('utf-8-sig')
    if raw.startswith('"') and raw.endswith('"') and '\\r\\n' in raw: raw = json.loads(raw)
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows or 'Candidate Name' not in rows[0]: raise RuntimeError(f'unexpected report format for {e["ElectionName"]}')
    races = {}
    for r in rows:
        sid = seat_id(r['Office Name'], r['District Name'], e['ElectionYear'])
        if not sid: continue
        party = r['Party Name'].replace(' Party', '').strip()
        key = (sid, party if st == 'P' else '')
        race = races.setdefault(key, {'seat': sid, 'office': r['Office Name'].strip(), 'district': r['District Name'].strip(), 'party': party if st == 'P' else None, 'cands': {}})
        c = race['cands'].setdefault((r['Candidate Name'].strip(), party), {'name': title_name(r['Candidate Name']), 'party': party, 'votes': 0, 'electionDay': 0, 'mail': 0, 'provisional': 0, 'counties': 0})
        c['votes'] += num(r['Votes']); c['electionDay'] += num(r.get('Election Day Votes')); c['mail'] += num(r.get('Mail Votes')); c['provisional'] += num(r.get('Provisional Votes')); c['counties'] += 1
    out = []
    for race in races.values():
        cands = sorted(race['cands'].values(), key=lambda c: -c['votes']); tot = sum(c['votes'] for c in cands)
        for c in cands: c['pct'] = round(100 * c['votes'] / tot, 2) if tot else 0.0
        leader = cands[0] if cands and cands[0]['votes'] > 0 else None
        tie = len(cands) > 1 and cands[0]['votes'] == cands[1]['votes']
        out.append({'seat': race['seat'], 'office': race['office'], 'district': race['district'], 'party': race['party'], 'total': tot,
                    'candidates': cands, 'leader': None if tie or not leader else leader['name']})
    return out

def main():
    today = datetime.date.today()
    prev = {}
    try: prev = json.load(open(f'{OUT}/results.json'))
    except Exception: pass
    status = {'source': 'PA Department of State – electionreturns.pa.gov', 'ok': True, 'errors': []}
    try:
        lst = jget(BASE + 'GetElectionList')['Table']
    except Exception as ex:
        print('PA DOS unreachable:', ex); status.update(ok=False, errors=[f'election list: {ex}'])
        if prev: prev['status'] = {**status, 'lastSuccess': prev.get('status', {}).get('lastSuccess')}; json.dump(prev, open(f'{OUT}/results.json', 'w'), indent=0)
        return
    prev_el = {e['key']: e for e in prev.get('elections', [])}
    elections = []
    for e in elections_wanted(lst, today):
        key = f"{e['ElectionYear']}-{e['ElectionType']}-{e['Electionid']}"
        meta = {'key': key, 'id': e['Electionid'], 'type': {'G': 'general', 'P': 'primary', 'S': 'special'}[e['ElectionType']], 'name': e['ElectionName'].strip(),
                'date': datetime.datetime.strptime(e['ElectionDate'], '%m/%d/%Y').date().isoformat(),
                'official': e.get('ElectionStatus') == 'O', 'statusCode': e.get('ElectionStatus'),
                'url': 'https://www.electionreturns.pa.gov/'}
        old = prev_el.get(key)
        # Certified elections never change: reuse the previous fetch to stay light on PA DOS.
        if old and old.get('official') and meta['official'] and old.get('races'):
            elections.append(old); continue
        try:
            races = fetch_election(e)
            if races is None: continue
            meta['races'] = races; meta['fetched'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
            elections.append(meta); print('ok', key, meta['name'], len(races), 'races', 'official' if meta['official'] else 'UNOFFICIAL')
        except Exception as ex:
            status['errors'].append(f"{meta['name']}: {ex}"); print('ERR', key, ex)
            if old: elections.append(old)
    elections.sort(key=lambda e: e['date'], reverse=True)
    status['lastSuccess'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    status['ok'] = not status['errors']
    for e in elections:
        for r in e['races']:
            for c in r['candidates']: c['name'] = title_name(c['name'])
            if r.get('leader'): r['leader'] = title_name(r['leader'])
    json.dump({'generated': status['lastSuccess'], 'status': status, 'elections': elections}, open(f'{OUT}/results.json', 'w'), separators=(',', ':'))
if __name__ == '__main__': main()
