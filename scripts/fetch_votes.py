"""Build-time prefetch of roll-call votes for PA officeholders (bundled into app; app refreshes live)."""
import json, re, sys, html, urllib.request, concurrent.futures as cf, xml.etree.ElementTree as ET, datetime, os
UA={'User-Agent':'Mozilla/5.0 (Linux; Android 14) PA-Politics/1.0'}
OUT='/workspace/pa-politics/data/votes'
def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code==404: return 404,b''
        except Exception as e: pass
    return 0,b''
def t(el,path):
    x=el.find(path); return (x.text or '').strip() if x is not None and x.text else ''

def house_roll(year,n):
    st,b=get(f'https://clerk.house.gov/evs/{year}/roll{n:03d}.xml')
    if st!=200 or not b.startswith(b'<?xml'): return None
    r=ET.fromstring(b); m=r.find('vote-metadata')
    d=datetime.datetime.strptime(t(m,'action-date'),'%d-%b-%Y').date().isoformat()
    votes={}
    for rv in r.iter('recorded-vote'):
        lg=rv.find('legislator')
        if lg.get('state')=='PA': votes[lg.get('name-id')]=t(rv,'vote')
    tot=m.find('vote-totals/totals-by-vote')
    return {'chamber':'US House','roll':n,'date':d,'bill':t(m,'legis-num'),'question':t(m,'vote-question'),
            'title':t(m,'vote-desc'),'result':t(m,'vote-result'),
            'tally':f"{t(tot,'yea-total')}-{t(tot,'nay-total')}" if tot is not None else '',
            'url':f'https://clerk.house.gov/Votes/{year}{n}','src':f'https://clerk.house.gov/evs/{year}/roll{n:03d}.xml','votes':votes}

def senate_vote(cong,sess,n):
    st,b=get(f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote{cong}{sess}/vote_{cong}_{sess}_{n:05d}.xml')
    if st!=200 or b'<roll_call_vote' not in b: return None
    r=ET.fromstring(b)
    dt=re.sub(r'\s+',' ',t(r,'vote_date')).split(',')
    d=datetime.datetime.strptime(','.join(dt[:2]).strip(),'%B %d, %Y').date().isoformat()
    votes={}
    for mm in r.iter('member'):
        if t(mm,'state')=='PA': votes[t(mm,'lis_member_id')]=t(mm,'vote_cast')
    doc=t(r,'document/document_name') or t(r,'document/document_type')+' '+t(r,'document/document_number')
    return {'chamber':'US Senate','roll':n,'date':d,'bill':doc.strip(),'question':t(r,'question'),
            'title':t(r,'vote_title') or t(r,'vote_document_text'),'result':t(r,'vote_result_text') or t(r,'vote_result'),
            'tally':f"{t(r,'count/yeas')}-{t(r,'count/nays')}",
            'url':f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote{cong}{sess}/vote_{cong}_{sess}_{n:05d}.htm',
            'src':f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote{cong}{sess}/vote_{cong}_{sess}_{n:05d}.xml','votes':votes}

def pa_roll(body,n,sess='2025'):
    url=f'https://www.palegis.us/{body}/roll-calls/summary?sessYr={sess}&sessInd=0&rcNum={n}'
    st,b=get(url)
    if st!=200: return None
    s=b.decode('utf-8','replace')
    return parse_pa(s,body,n,url)

def txt(x): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',x))).strip()
def parse_pa(s,body,n,url):
    def field(label):
        m=re.search(r'>\s*'+label+r'\s*</[^>]+>\s*(.*?)</div>',s,re.S)
        return txt(m.group(1)) if m else ''
    plain=txt(re.sub(r'<script.*?</script>','',s,flags=re.S))
    m=re.search(r'Details for RCS No\. \d+ Vote Date (.*?) Bill (.*?) Action (.*?) Short Title (.*?) Prime Sponsor (.*?) Vote Summary Yea (\d+) Nay (\d+)',plain)
    m2=re.search(r'Details for RCS No\. \d+ Vote Date (.*?) (?:Action|Motion|Description) (.*?) Vote Summary Yea (\d+) Nay (\d+)',plain)
    if m: date,bill,action,title,_,y,nn=m.groups()
    elif m2: date,action,y,nn=m2.groups(); bill='';title=''
    else:
        m3=re.search(r'Details for RCS No\. \d+ Vote Date (.*?) Vote Summary Yea (\d+) Nay (\d+)',plain)
        if not m3: return None
        date,y,nn=m3.groups(); bill=action=title=''
    dm=re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})',date)
    d=datetime.datetime.strptime(dm.group(1),'%b %d, %Y').date().isoformat() if dm else ''
    votes={}
    for blk in re.split(r'class="rc-member d-flex',s)[1:]:
        dist=re.search(r'(?:House|Senate) District&nbsp;(\d+)',blk)
        v=re.search(r'badge text-bg-[a-z-]+" title="([^"]+)"',blk)
        nm=re.search(r"<a href='/(?:house|senate)/members/bio/[^']*'[^>]*>(?:Rep\.|Sen\.)?\s*([^<]+)</a>",blk)
        if dist and v: votes[dist.group(1)]=v.group(1)+'|'+(html.unescape(nm.group(1)).strip() if nm else '')
    ch='PA House' if body=='house' else 'PA Senate'
    bill=re.sub(r'House Bill','HB',re.sub(r'Senate Bill','SB',bill))
    return {'chamber':ch,'roll':n,'date':d,'bill':bill,'question':action.replace(' - opens in a new tab',''),'title':title,
            'result':'','tally':f'{y}-{nn}','url':url,'src':url,'votes':votes}

def pa_latest(body):
    st,b=get(f'https://www.palegis.us/{body}/rss/session/votes')
    nums=[int(x) for x in re.findall(rb'rcNum=(\d+)',b)]
    return max(nums) if nums else 0

def run(name,fn,ns,workers=6):
    res=[]
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(fn,ns):
            if r: res.append(r)
    res.sort(key=lambda r:(r['date'],r['roll']),reverse=True)
    json.dump({'fetched':datetime.datetime.now().isoformat(timespec='seconds'),'votes':res},open(f'{OUT}/{name}.json','w'))
    print(name,len(res),'votes; newest',res[0]['date'] if res else None, flush=True)

if __name__=='__main__':
    which=sys.argv[1:]
    if 'house' in which:
        # find max roll in 2026 by probing
        lo,hi=1,1000
        while lo<hi:
            mid=(lo+hi+1)//2
            st,bb=get(f'https://clerk.house.gov/evs/2026/roll{mid:03d}.xml')
            if st==200 and b'<rollcall-vote' in bb: lo=mid
            else: hi=mid-1
        print('house max roll 2026',lo,flush=True)
        run('us_house',lambda n:house_roll(2026,n),range(lo,0,-1))
    if 'house2025' in which:
        lo,hi=1,1000
        while lo<hi:
            mid=(lo+hi+1)//2
            st,bb=get(f'https://clerk.house.gov/evs/2025/roll{mid:03d}.xml')
            if st==200 and b'<rollcall-vote' in bb: lo=mid
            else: hi=mid-1
        print('house max roll 2025',lo,flush=True)
        run('us_house_2025',lambda n:house_roll(2025,n),range(lo,0,-1))
    if 'senate1' in which:
        st,b=get('https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_1.xml')
        mx=max(int(x) for x in re.findall(rb'<vote_number>(\d+)</vote_number>',b))
        print('senate1 max',mx,flush=True)
        run('us_senate_2025',lambda n:senate_vote(119,1,n),range(mx,0,-1))
    if 'senate' in which:
        st,b=get('https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml')
        mx=max(int(x) for x in re.findall(rb'<vote_number>(\d+)</vote_number>',b))
        print('senate max',mx,flush=True)
        run('us_senate',lambda n:senate_vote(119,2,n),range(mx,0,-1))
    for body in ('house','senate'):
        if 'pa'+body in which:
            mx=pa_latest(body); N=int(os.environ.get('PAN','150'))
            print('pa',body,'max',mx,flush=True)
            run('pa_'+body+'_more',lambda n,b=body:pa_roll(b,n),range(mx,max(0,mx-N),-1),workers=4)
