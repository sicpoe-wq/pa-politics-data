"""Seed work/votes_us/{us_house,us_senate}.json with ALL members' votes (keys 'ST:memberid'). Run from the box (senate.gov blocks GitHub runners)."""
import json, re, sys, os, urllib.request, concurrent.futures as cf, xml.etree.ElementTree as ET, datetime
UA = {'User-Agent': 'Mozilla/5.0 (compatible; pa-politics-data/1.0)'}
def get(u):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
        except Exception: pass
    return None
t = lambda el, p: ((el.find(p).text or '').strip() if el.find(p) is not None and el.find(p).text else '')
def house(y, n):
    b = get(f'https://clerk.house.gov/evs/{y}/roll{n:03d}.xml')
    if not b or b'<rollcall-vote' not in b: return None
    r = ET.fromstring(b); m = r.find('vote-metadata'); tot = m.find('vote-totals/totals-by-vote')
    v = {f"{rv.find('legislator').get('state')}:{rv.find('legislator').get('name-id')}": t(rv, 'vote') for rv in r.iter('recorded-vote')}
    return {'chamber': 'US House', 'roll': n, 'date': datetime.datetime.strptime(t(m, 'action-date'), '%d-%b-%Y').date().isoformat(), 'bill': t(m, 'legis-num'),
            'question': t(m, 'vote-question'), 'title': t(m, 'vote-desc'), 'result': t(m, 'vote-result'),
            'tally': f"{t(tot, 'yea-total')}-{t(tot, 'nay-total')}" if tot is not None else '', 'url': f'https://clerk.house.gov/Votes/{y}{n}',
            'src': f'https://clerk.house.gov/evs/{y}/roll{n:03d}.xml', 'votes': v}
def senate(c, s, n):
    base = f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote{c}{s}/vote_{c}_{s}_{n:05d}'
    b = get(base + '.xml')
    if not b or b'<roll_call_vote' not in b: return None
    r = ET.fromstring(b); dt = re.sub(r'\s+', ' ', t(r, 'vote_date')).split(',')
    doc = r.find('document'); cnt = r.find('count')
    v = {f"{t(mm, 'state')}:{t(mm, 'lis_member_id')}": t(mm, 'vote_cast') for mm in r.iter('member')}
    name = t(doc, 'document_name') if doc is not None else ''
    if not name and doc is not None: name = f"{t(doc, 'document_type')} {t(doc, 'document_number')}".strip()
    return {'chamber': 'US Senate', 'roll': n, 'date': datetime.datetime.strptime(','.join(dt[:2]).strip(), '%B %d, %Y').date().isoformat(), 'bill': name,
            'question': t(r, 'question'), 'title': t(r, 'vote_title') or t(r, 'vote_document_text'), 'result': t(r, 'vote_result_text') or t(r, 'vote_result'),
            'tally': f"{t(cnt, 'yeas')}-{t(cnt, 'nays')}" if cnt is not None else '', 'url': base + '.htm', 'src': base + '.xml', 'votes': v}
def batch(fn, args):
    out = []
    with cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(lambda a: fn(*a), args):
            if r: out.append(r)
    return out
os.makedirs('work/votes_us', exist_ok=True)
H = batch(house, [(2025, n) for n in range(1, 420)] + [(2026, n) for n in range(1, 420)])
S = batch(senate, [(119, 1, n) for n in range(1, 720)] + [(119, 2, n) for n in range(1, 400)])
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
for f, rows in (('us_house', H), ('us_senate', S)):
    rows.sort(key=lambda r: (r['date'], r['roll']), reverse=True)
    json.dump({'fetched': now, 'votes': rows}, open(f'work/votes_us/{f}.json', 'w'), separators=(',', ':'))
    print(f, len(rows), os.path.getsize(f'work/votes_us/{f}.json'))
