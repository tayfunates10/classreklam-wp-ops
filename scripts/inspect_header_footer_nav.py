#!/usr/bin/env python3
import base64,json,os,re,time,urllib.parse,urllib.request,urllib.error
from html.parser import HTMLParser
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/138 Safari/537.36'
TARGETS=['/edremit-tabela/','/totem-tabela/','/dijital-baski/','/arac-giydirme/','/cam-giydirme/','/kutu-harf-tabela/']

def req(method,route=None,params=None,auth=True):
    if route is None:
        url=BASE+'/?navinspect='+str(int(time.time()*1000))
    else:
        q={'rest_route':route}
        if params:q.update(params)
        url=BASE+'/?'+urllib.parse.urlencode(q)
    h={'User-Agent':UA,'Accept':'application/json' if route else 'text/html,*/*'}
    if auth:h['Authorization']=AUTH
    if route:h['Referer']=BASE+'/wp-admin/'
    r=urllib.request.Request(url,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=60) as x:
            raw=x.read().decode(errors='replace')
            return x.status,(json.loads(raw) if route else raw)
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try:b=json.loads(raw)
        except:b={'raw':raw[:1000]}
        return e.code,b

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.links=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); self.stack.append(tag)
        if tag=='a': self.cur={'href':attrs.get('href',''),'text':''}
    def handle_data(self,data):
        if self.cur is not None:self.cur['text']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.cur is not None:
            self.cur['text']=' '.join(self.cur['text'].split()); self.links.append(self.cur); self.cur=None
        if self.stack:
            try:
                i=len(self.stack)-1-self.stack[::-1].index(tag); self.stack=self.stack[:i]
            except ValueError:pass

def extract_region(html,tag):
    m=re.search(rf'<{tag}\b[^>]*>.*?</{tag}>',html,re.I|re.S)
    return m.group(0) if m else ''

out={}
code,root=req('GET','/')
out['root_http']=code
routes=root.get('routes',{}) if isinstance(root,dict) else {}
out['candidate_routes']=sorted([r for r in routes if any(k in r.lower() for k in ['menu','navigation','widget','sidebar','template-part','template'])])

for route in ['/wp/v2/navigation','/wp/v2/menu-items','/wp/v2/widgets','/wp/v2/sidebars','/wp/v2/template-parts','/wp/v2/templates']:
    code,body=req('GET',route,{'context':'edit','per_page':'100'})
    if isinstance(body,list):
        compact=[]
        for x in body[:100]:
            if isinstance(x,dict):
                compact.append({k:x.get(k) for k in ['id','slug','status','title','name','type','area','plugin','rendered'] if k in x})
        out[route]={'http':code,'items':compact}
    else: out[route]={'http':code,'body':body}

code,html=req('GET',None,auth=False)
out['homepage_http']=code
for tag in ['header','footer']:
    region=extract_region(html,tag)
    p=LinkParser(); p.feed(region)
    links=[x for x in p.links if x.get('href')]
    out[tag]={
      'found':bool(region),
      'links':links,
      'target_hits':[x for x in links if any(t in urllib.parse.urlparse(x.get('href','')).path.rstrip('/')+'/' for t in TARGETS)],
      'html_excerpt':re.sub(r'\s+',' ',region)[:12000]
    }
print(json.dumps(out,ensure_ascii=False,indent=2))
