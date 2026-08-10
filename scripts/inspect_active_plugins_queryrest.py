#!/usr/bin/env python3
import base64,json,os,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def get(route,params=None,retries=4):
    q={'rest_route':route}
    if params: q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q)
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=45) as r:
                return r.status,json.loads(r.read().decode(errors='replace'))
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace')
            if e.code==403 and i<retries-1:
                time.sleep(8*(i+1)); continue
            raise RuntimeError(f'HTTP {e.code}: {raw[:1000]}')
code,plugins=get('/wp/v2/plugins',{'status':'active','per_page':100,'_fields':'plugin,status,name,version'})
print(json.dumps({'status':'success','plugins':plugins},ensure_ascii=False,indent=2))
