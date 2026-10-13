"""Assemble PA extras + national files, then write v2/manifest.json (sha256 per file, per state). Run after tests pass."""
import hashlib, json, os, shutil, datetime, sys
sys.path.insert(0, os.path.dirname(__file__)); from states_meta import STATES
V1, V2 = os.environ.get('OUT', 'v1'), 'v2'
def stage():
    fl = json.load(open(f'{V1}/floor.json'))
    json.dump({'fetched': fl['fetched'], 'sections': [s for s in fl['sections'] if s['key'].startswith('us-')]}, open(f'{V2}/national/floor.json', 'w'), separators=(',', ':'))
    json.dump({'fetched': fl['fetched'], 'sections': [s for s in fl['sections'] if not s['key'].startswith('us-')]}, open(f'{V2}/states/PA/floor.json', 'w'), separators=(',', ':'))
    shutil.copy(f'{V1}/results.json', f'{V2}/states/PA/results.json')
    for f in ('pa_house', 'pa_senate'): shutil.copy(f'{V1}/votes/{f}.json', f'{V2}/states/PA/votes/{f}.json')
    if os.path.exists(f'{V2}/states/PA/events.json'): shutil.copy(f'{V2}/states/PA/events.json', f'{V1}/events.json')  # v1 apps keep working
def manifest():
    prev = {}
    try: prev = json.load(open(f'{V2}/manifest.json'))
    except Exception: pass
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    def entry(path, old):
        b = open(path, 'rb').read(); h = hashlib.sha256(b).hexdigest()
        return {'sha256': h, 'bytes': len(b), 'updated': old.get('updated') if old.get('sha256') == h else now}
    m = {'schema': 2, 'generated': now, 'national': {}, 'states': {}}
    for f in sorted(os.listdir(f'{V2}/national')): m['national'][f] = entry(f'{V2}/national/{f}', prev.get('national', {}).get(f, {}))
    m['national']['../index.json'] = entry(f'{V2}/index.json', prev.get('national', {}).get('../index.json', {}))
    for st, _, _ in STATES:
        d = f'{V2}/states/{st}'; files = {}
        for root, _, fs in os.walk(d):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f), d); files[rel] = entry(os.path.join(root, f), prev.get('states', {}).get(st, {}).get(rel, {}))
        m['states'][st] = dict(sorted(files.items()))
    json.dump(m, open(f'{V2}/manifest.json', 'w'), separators=(',', ':'))
    print('v2 manifest ok:', sum(len(v) for v in m['states'].values()), 'state files')
if __name__ == '__main__':
    (stage if 'stage' in sys.argv else manifest)()
