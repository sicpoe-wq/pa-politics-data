import re
def strip_templates(s):
    out=[];depth=0;i=0
    while i<len(s):
        if s.startswith('{{',i): depth+=1;i+=2;continue
        if s.startswith('}}',i) and depth>0: depth-=1;i+=2;continue
        if depth==0: out.append(s[i])
        i+=1
    return ''.join(out)
def clean(s):
    s=re.sub(r'<ref[^>]*/>','',s); s=re.sub(r'<ref.*?</ref>','',s,flags=re.S)
    s=re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]',r'\1',s)
    s=re.sub(r"'''?",'',s); s=strip_templates(s); s=re.sub(r'<[^>]+>','',s)
    return s.strip()
def party_name(p):
    p=clean(p); p=re.sub(r'\s*\(United States\)|\s*of Pennsylvania|\s*Party','',p).strip()
    return p
def election_boxes(text):
    """yield list of (candidate, party, raw) for each election box"""
    out=[]
    for b in re.finditer(r'\{\{Election box begin.*?\{\{Election box end\}\}',text,re.S|re.I):
        bt=b.group(0); title=re.search(r'title\s*=\s*([^\n|]*)',bt); title=clean(title.group(1)) if title else ''
        cands=[]
        for c in re.finditer(r'\{\{Election box (?:winning )?candidate[^|]*\|(.*?)\n\}\}',bt,re.S|re.I):
            body=c.group(1)
            nm=re.search(r'candidate\s*=\s*(.*)',body); pt=re.search(r'party\s*=\s*(.*)',body)
            if nm: cands.append((clean(nm.group(1)), party_name(pt.group(1)) if pt else ''))
        out.append((title,cands))
    return out
def sections(text,level=2):
    eq='='*level
    parts=re.split(r'\n%s([^=].*?)%s[ \t]*\n'%(eq,eq),'\n'+text)
    return [(parts[i].strip(),parts[i+1]) for i in range(1,len(parts),2)]

def inline_races(text):
    """Parse {{Election box inline incumbent}} + following candidate templates."""
    races=[]; cur=None
    for t in re.finditer(r'\{\{Election box inline (incumbent|candidate[^|]*)\|?(.*?)\n?\}\}(?=\{\{|\n|$)',text,re.S|re.I):
        kind,body=t.group(1).lower(),t.group(2)
        f={}
        for m in re.finditer(r'\|\s*(\w+)\s*=\s*(.*?)(?=\n\s*\||\Z)', '|'+body if not body.startswith('|') else body, re.S):
            f[m.group(1)]=m.group(2).strip()
        if kind=='incumbent':
            cur={'race':clean(f.get('race','')),'inc_party':party_name(f.get('party','')),'incumbent':clean(f.get('incumbent','')),'status':clean(f.get('status','')),'n':f.get('candidates',''),'cands':[]}
            races.append(cur)
        elif cur is not None:
            cur['cands'].append((clean(f.get('candidate','')),party_name(f.get('party',''))))
    return races

def top_templates(text):
    """yield (name, body) for top-level {{...}} templates, balanced."""
    i=0;n=len(text)
    while True:
        i=text.find('{{',i)
        if i<0: return
        depth=0;j=i
        while j<n:
            if text.startswith('{{',j): depth+=1;j+=2;continue
            if text.startswith('}}',j):
                depth-=1;j+=2
                if depth==0: break
                continue
            j+=1
        inner=text[i+2:j-2]
        name=inner.split('|',1)[0].strip()
        yield name, inner
        i=j
def tpl_fields(inner):
    # split on top-level pipes
    parts=[];depth=0;cur='';k=0
    while k<len(inner):
        two=inner[k:k+2]
        if two in('{{','[['): depth+=1;cur+=two;k+=2;continue
        if two in('}}',']]'): depth-=1;cur+=two;k+=2;continue
        if inner[k]=='|' and depth==0: parts.append(cur);cur='';k+=1;continue
        cur+=inner[k];k+=1
    parts.append(cur)
    f={}
    for p in parts[1:]:
        if '=' in p:
            a,b=p.split('=',1); f[a.strip()]=b.strip()
    return f
def inline_races2(text):
    races=[];cur=None
    for name,inner in top_templates(text):
        ln=name.lower()
        if ln.startswith('election box inline incumbent'):
            f=tpl_fields(inner)
            cur={'race':clean(f.get('race','')),'inc_party':party_name(f.get('party','')),'incumbent':clean(f.get('incumbent','')),'status':clean(f.get('status','')),'n':clean(f.get('candidates','')),'cands':[]}
            races.append(cur)
        elif ln.startswith('election box inline candidate') and cur is not None:
            f=tpl_fields(inner)
            cur['cands'].append((clean(f.get('candidate','')),party_name(f.get('party',''))))
    return races

def sortname(cell):
    m=re.search(r'\{\{#invoke:sort\|name\|([^|}]*)\|([^|}]*)(?:\|([^|}]*))?',cell)
    if m: return m.group(3) or (m.group(1)+' '+m.group(2))
    return clean(cell)
def wikitable_rows(tbl):
    rows=[]
    for r in re.split(r'\n\|-[^\n]*',tbl)[1:]:
        cells=[]
        for line in r.strip('\n').split('\n'):
            if line.startswith('|}'): break
            if line.startswith('|') or line.startswith('!'):
                for c in re.split(r'\|\||!!',line[1:]): cells.append(c)
            elif cells: cells[-1]+='\n'+line
        rows.append(cells)
    return rows
def cellval(c):
    # drop style/attr prefix "xxx |value" (single pipe not inside brackets)
    d=0;k=0
    while k<len(c):
        if c[k:k+2] in('{{','[['): d+=1;k+=2;continue
        if c[k:k+2] in('}}',']]'): d-=1;k+=2;continue
        if c[k]=='|' and d==0: return c[k+1:].strip()
        k+=1
    return c.strip()
