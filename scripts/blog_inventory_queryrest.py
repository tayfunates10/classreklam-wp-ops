#!/usr/bin/env python3
import base64,json,os,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def get(route,params=None):
    q={'rest_route':route}
    if params: q.update(params)
    u=BASE+'/?'+urllib.parse.urlencode(q)
    last=None
    for attempt in range(4):
        time.sleep(5 if attempt==0 else 15*attempt)
        req=urllib.request.Request(u,headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'})
        try:
            with urllib.request.urlopen(req,timeout=45) as r:
                return json.loads(r.read().decode(errors='replace'))
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace')
            last=(e.code,raw[:1200])
            if e.code!=403 or 'imunify360' not in raw.lower(): raise
    raise RuntimeError(f'WAF did not release after retries: {last}')

posts=get('/wp/v2/posts',{'context':'edit','per_page':100,'_fields':'id,slug,title,categories,status'})
cats=get('/wp/v2/categories',{'context':'edit','per_page':100,'_fields':'id,name,slug,count'})
print(json.dumps({'posts':[{'id':p['id'],'slug':p['slug'],'title':p.get('title',{}).get('raw') or p.get('title',{}).get('rendered',''),'categories':p.get('categories',[]),'status':p.get('status')} for p in posts],'categories':cats},ensure_ascii=False,indent=2))
