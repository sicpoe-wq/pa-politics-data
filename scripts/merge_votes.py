"""Merge prefetched roll calls into the app bundle. PA votes are compacted: only votes cast by the
*current* seat holder are kept (matched by last name), encoded as Y/N/NV/L, so predecessors' votes are never attributed."""
import json, re, unicodedata
import os
V='work/votes/'; O=os.environ.get('OUT','v1')+'/votes/'
os.makedirs(O,exist_ok=True)
seats={s['id']:s for s in json.load(open(os.environ.get('OUT','v1')+'/seats.json'))['seats']}
def load(n):
    try: return json.load(open(V+n+'.json'))
    except FileNotFoundError: return None
def merge(names,out,compact=None):
    fs=[load(n) for n in names]; fs=[f for f in fs if f]
    seen={}; 
    for f in fs:
        for r in f['votes']: seen[r['src']]=r
    rolls=sorted(seen.values(),key=lambda r:(r['date'],r['roll']),reverse=True)
    dropped=0
    if compact:
        code={'Yea':'Y','Nay':'N','No Vote':'NV','Leave':'L'}
        for r in rolls:
            nv={}
            for d,raw in r['votes'].items():
                v,_,who=raw.partition('|'); s=seats.get(f'{compact}-{d}')
                last=re.sub(r'[^a-z]','',[w for w in s['incumbent']['name'].split() if not re.match(r'^(jr\.?|sr\.?|ii|iii|iv)$',w,re.I)][-1].lower())
                whon=re.sub(r'[^a-z ]','',unicodedata.normalize('NFKD',who).lower())
                if who and last not in whon: dropped+=1; continue
                nv[d]=code.get(v,v)
            r['votes']=nv
    fetched=min(f['fetched'] for f in fs)
    json.dump({'fetched':fetched,'votes':rolls},open(O+out+'.json','w'),separators=(',',':'))
    print(out,len(rolls),rolls[-1]['date'],'→',rolls[0]['date'],'dropped predecessor votes:',dropped)
merge(['us_house'],'us_house')
merge(['us_senate'],'us_senate')
merge(['pa_house'],'pa_house','pa-house')
merge(['pa_senate'],'pa_senate','pa-sen')
