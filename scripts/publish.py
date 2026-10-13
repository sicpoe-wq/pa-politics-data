"""Write v1/manifest.json (sha256 + size per file). Run only after tests pass."""
import hashlib, json, os, datetime
OUT = os.environ.get('OUT', 'v1')
files = ['seats.json', 'results.json', 'floor.json', 'events.json', 'votes/us_house.json', 'votes/us_senate.json', 'votes/pa_house.json', 'votes/pa_senate.json']
prev = {}
try: prev = json.load(open(f'{OUT}/manifest.json'))
except Exception: pass
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
m = {'schema': 1, 'generated': now, 'files': {}, 'resultsStatus': json.load(open(f'{OUT}/results.json')).get('status')}
for f in files:
    b = open(f'{OUT}/{f}', 'rb').read(); h = hashlib.sha256(b).hexdigest()
    old = prev.get('files', {}).get(f, {})
    m['files'][f] = {'sha256': h, 'bytes': len(b), 'updated': old.get('updated') if old.get('sha256') == h else now}
json.dump(m, open(f'{OUT}/manifest.json', 'w'), indent=1)
print('manifest ok', {k: v['bytes'] for k, v in m['files'].items()})
