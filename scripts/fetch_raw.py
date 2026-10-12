"""Download the raw source documents that build_data.py parses."""
import json, os, urllib.request, urllib.parse, time
RAW = os.environ.get('RAW', 'raw'); os.makedirs(RAW, exist_ok=True)
UA = {'User-Agent': 'PA-Politics-data/1.0 (https://github.com/sicpoe-wq/pa-politics-data; sicpoe@gmail.com)'}
def get(url, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(5 * (i + 1))
open(f'{RAW}/legislators-current.json', 'wb').write(get('https://unitedstates.github.io/congress-legislators/legislators-current.json'))
open(f'{RAW}/pa.csv', 'wb').write(get('https://data.openstates.org/people/current/pa.csv'))
PAGES = ['2026_United_States_House_of_Representatives_elections_in_Pennsylvania', '2026_Pennsylvania_gubernatorial_election',
         '2026_Pennsylvania_Senate_election', '2026_Pennsylvania_House_of_Representatives_election', 'Pennsylvania_State_Senate',
         'Pennsylvania_House_of_Representatives', 'Supreme_Court_of_Pennsylvania', 'Governor_of_Pennsylvania', 'Lieutenant_Governor_of_Pennsylvania',
         'Pennsylvania_Attorney_General', 'Pennsylvania_Auditor_General', 'Pennsylvania_Treasurer']
for p in PAGES:
    b = get(f'https://en.wikipedia.org/w/api.php?action=parse&page={p}&prop=wikitext|revid&format=json&formatversion=2&redirects=1')
    if 'error' in json.loads(b): raise SystemExit(f'Wikipedia page missing: {p}')
    open(f'{RAW}/wiki_{p}.json', 'wb').write(b)
titles = 'Josh_Shapiro|Austin_Davis_(politician)|Dave_Sunday|Timothy_DeFoor|Stacy_Garrity|Debra_Todd|Christine_Donohue|Kevin_Dougherty_(judge)|David_Wecht|Sallie_Mundy|Kevin_Brobson|Daniel_McCaffery'
open(f'{RAW}/wiki_images.json', 'wb').write(get('https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&piprop=thumbnail&pithumbsize=300&redirects=1&format=json&formatversion=2&titles=' + titles))
print('raw ok')
