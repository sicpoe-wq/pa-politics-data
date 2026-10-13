"""One-time/occasional: Census 2024 cartographic boundaries -> simplified per-state GeoJSON (v2/states/XX/geo)."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__)); from states_meta import STATES, dkey
SRC = os.environ.get('GEOSRC', '/workspace/geo-src'); OUT = 'v2/states'
MS = ['npx', 'mapshaper']
def run(src, filt, out, pct, fields):
    tmp = '/tmp/_g.json'
    subprocess.run(MS + [src, '-filter', filt, '-simplify', f'{pct}%', 'weighted', 'keep-shapes', '-o', tmp, 'format=geojson', 'precision=0.0001'], check=True, capture_output=True)
    d = json.load(open(tmp)); feats = []
    for f in d['features']:
        p = f['properties']; lab = fields(p)
        if lab is None: continue
        f['properties'] = {'district': dkey(lab), 'label': lab}; feats.append(f)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(out, 'w'), separators=(',', ':'))
    return len(feats), os.path.getsize(out)
for st, name, fips in STATES:
    r = {}
    r['congress'] = run(f'{SRC}/cb_2024_us_cd119_500k.zip', f'STATEFP=="{fips}"', f'{OUT}/{st}/geo/congress.geojson', 15,
                        lambda p: None if p['CD119FP'] == 'ZZ' else str(int(p['CD119FP'])) if p['CD119FP'] not in ('00', '98') else 'AL')
    for ch, c in (('senate', 'sldu'), ('house', 'sldl')):
        z = f'{SRC}/cb_2024_{fips}_{c}_500k.zip'
        if not os.path.exists(z): continue
        r[ch] = run(z, 'true', f'{OUT}/{st}/geo/{ch}.geojson', 15, lambda p, k=('SLDUST' if c == 'sldu' else 'SLDLST'): None if p[k].startswith('ZZ') else p['NAME'])
    print(st, r, flush=True)
