#!/usr/bin/env python3
import base64,json,os,time,urllib.parse,urllib.request,urllib.error,re
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/138 Safari/537.36'
SERVICES=[('Edremit Tabela','/edremit-tabela/'),('Totem Tabela','/totem-tabela/'),('Dijital Baskı','/dijital-baski/'),('Araç Giydirme','/arac-giydirme/'),('Cam Giydirme','/cam-giydirme/'),('Kutu Harf Tabela','/kutu-harf-tabela/')]
TARGET={p for _,p in SERVICES}

def norm(u):
    try:p=urllib.parse.urlparse(u).path
    except:p=str(u)
    return ('/'+p.lstrip('/')).rstrip('/')+'/'
def req(route,params=None,retries=5):
    q={'rest_route':route};
    if params:q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q)
    h={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    last=''
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=70) as r:
                return r.status,json.loads(r.read().decode(errors='replace'))
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace'); last=f'{e.code}: {raw[:1200]}'
            if e.code==403 and i<retries-1: time.sleep(10*(i+1)); continue
            return e.code,{'error':last}
        except Exception as e:
            last=repr(e)
            if i<retries-1: time.sleep(6*(i+1)); continue
            raise
    raise RuntimeError(last)

out={}
c,items=req('/wp/v2/menu-items',{'context':'edit','per_page':'100'})
out['menu_http']=c
remaining=[]
if isinstance(items,list):
    for it in items:
        t=it.get('title',{}); t=(t.get('raw') or t.get('rendered') or '') if isinstance(t,dict) else str(t)
        p=norm(it.get('url',''))
        if p in TARGET or t in {n for n,_ in SERVICES}: remaining.append({'id':it.get('id'),'title':t,'path':p})
out['remaining_service_menu_items']=remaining

c,w=req('/wp/v2/widgets/block-61',{'context':'edit'})
out['widget_http']=c
raw=None
if isinstance(w,dict):
    inst=w.get('instance') or {}; raw=inst.get('raw') if isinstance(inst,dict) else None
    if isinstance(raw,dict): raw=raw.get('content')
if not isinstance(raw,str): raw=''
out['widget_raw_excerpt']=raw[:12000]
hrefs=re.findall(r'href=["\']([^"\']+)["\']',raw,re.I)
out['footer_target_paths']=sorted({norm(x) for x in hrefs if norm(x) in TARGET})
out['footer_text_checks']={name:(name in raw) for name,_ in SERVICES}
out['success']=(c==200 and len(remaining)==0 and set(out['footer_target_paths'])==TARGET and all(out['footer_text_checks'].values()))
print(json.dumps(out,ensure_ascii=False,indent=2))
