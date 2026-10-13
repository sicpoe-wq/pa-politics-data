"""One national pass over Mobilize's public API (speaking-type events only) -> raw/mobilize.json, grouped later by state."""
import json, os, time, datetime, urllib.request, urllib.error
RAW = os.environ.get('RAW', 'raw'); UA = {'User-Agent': 'pa-politics-data/1.0 (+https://github.com/sicpoe-wq/pa-politics-data)'}
TYPES = ['RALLY', 'TOWN_HALL', 'MEET_GREET', 'COMMUNITY', 'MEETING', 'OTHER']
def get(url):
    for i in range(6):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read(); time.sleep(1.2); return json.loads(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 5: raise
            time.sleep(min(120, int(e.headers.get('Retry-After') or 0) or 10 * 2 ** i))
import sys
sys.path.insert(0, os.path.dirname(__file__)); from states_meta import STATES
now = int(time.time()); since = now - 30 * 86400
WIN = [f'timeslot_start=gte_{now}', f'timeslot_start=gte_{since}&timeslot_end=lt_{now}']
evs, seen, capped = [], set(), []
def pull(q):
    url = f'https://api.mobilize.us/v1/events?{q}&per_page=200'; first = None
    while url:
        d = get(url); first = first if first is not None else d.get('count', 0)
        for e in d['data']:
            if e['id'] not in seen: seen.add(e['id']); evs.append(e)
        url = d.get('next')
    return first or 0
for st, _, _ in STATES:
    for w in WIN:
        allt = '&'.join(f'event_types={t}' for t in TYPES)
        if pull(f'state={st}&{allt}&{w}') >= 1000:  # API caps a query at 1000 results: split by type
            for t in TYPES:
                if pull(f'state={st}&event_types={t}&{w}') >= 1000: capped.append(f'{st}/{t}')
json.dump({'fetched': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'capped': capped, 'events': evs}, open(f'{RAW}/mobilize.json', 'w'))
print('mobilize events:', len(evs), 'capped queries:', capped)
