"""Raw inputs for the 50-state build (Open States CSVs + national Wikipedia pages)."""
import os, sys, json, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__)); from states_meta import STATES
RAW = os.environ.get('RAW', 'raw'); os.makedirs(f'{RAW}/os', exist_ok=True)
UA = {'User-Agent': 'PA-Politics-data/1.0 (https://github.com/sicpoe-wq/pa-politics-data; sicpoe@gmail.com)'}
def get(url, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        except Exception:
            if i == tries - 1: raise
            time.sleep(5 * (i + 1))
fail = []
for st, _, _ in STATES:
    try: open(f'{RAW}/os/{st.lower()}.csv', 'wb').write(get(f'https://data.openstates.org/people/current/{st.lower()}.csv'))
    except Exception as e: fail.append(st)  # keep previous copy if present
for p in ['2026_United_States_House_of_Representatives_elections', '2026_United_States_Senate_elections', '2026_United_States_gubernatorial_elections', 'List_of_current_United_States_governors']:
    b = get(f'https://en.wikipedia.org/w/api.php?action=parse&page={p}&prop=wikitext|revid&format=json&formatversion=2&redirects=1')
    if 'error' in json.loads(b): raise SystemExit('missing ' + p)
    open(f'{RAW}/wiki_{p}.json', 'wb').write(b)
open(f'{RAW}/legislators-social-media.json', 'wb').write(get('https://unitedstates.github.io/congress-legislators/legislators-social-media.json'))
print('raw states ok; Open States failures:', fail)
