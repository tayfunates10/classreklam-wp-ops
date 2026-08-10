#!/usr/bin/env python3
import base64,json,os,re,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def url(path):
    p=urllib.parse.urlsplit(path); route=p.path
    if route.startswith('/wp-json'): route=route[len('/wp-json'):]
    u=BASE+'/?rest_route='+urllib.parse.quote(route,safe='/')
    if p.query: u+='&'+p.query
    return u

def one(method,path,payload=None):
    data=None; headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(url(path),data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode(errors='replace')
            try: return r.status,json.loads(raw) if raw else {}
            except: return r.status,{'raw':raw[:1200]}
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try: body=json.loads(raw)
        except: body={'raw':raw[:1200]}
        return e.code,body

def request(method,path,payload=None):
    time.sleep(2.5)
    for attempt in range(3):
        code,body=one(method,path,payload)
        txt=json.dumps(body,ensure_ascii=False).lower() if isinstance(body,(dict,list)) else str(body).lower()
        if code!=403 or 'imunify360' not in txt: return code,body
        time.sleep(10*(attempt+1))
    return code,body

def ensure(code,body,label):
    if code not in (200,201): raise RuntimeError(f'{label}: HTTP {code} {body}')

def fix_page(page_id,h1):
    code,p=request('GET',f'/wp-json/wp/v2/pages/{page_id}?context=edit&_fields=id,slug,content,title,modified')
    ensure(code,p,f'get page {page_id}')
    raw=p.get('content',{}).get('raw','')
    if re.search(r'<h1\b',raw,re.I): return {'id':page_id,'status':'already-has-h1'}
    block=f'<!-- wp:heading {{"level":1}} -->\n<h1 class="wp-block-heading">{h1}</h1>\n<!-- /wp:heading -->\n'
    code,b=request('POST',f'/wp-json/wp/v2/pages/{page_id}',{'content':block+raw})
    ensure(code,b,f'update page {page_id}')
    return {'id':page_id,'status':'h1-added','h1':h1}

items=[
 (18,'İletişim'),
 (1132,'Edremit Tabela'),
 (1134,'Edremit Totem Tabela'),
 (1136,'Edremit Dijital Baskı'),
 (1138,'Edremit Araç Giydirme'),
 (1140,'Edremit Cam Giydirme'),
 (1142,'Edremit Kutu Harf Tabela'),
]
print(json.dumps({'status':'success','pages':[fix_page(i,h) for i,h in items]},ensure_ascii=False,indent=2))
