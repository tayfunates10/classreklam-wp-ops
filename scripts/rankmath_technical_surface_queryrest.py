#!/usr/bin/env python3
import base64,json,os,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def fetch(route='/'):
    u=BASE+'/?'+urllib.parse.urlencode({'rest_route':route})
    for a in range(4):
        time.sleep(4 if a==0 else 12*a)
        req=urllib.request.Request(u,headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'})
        try:
            with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read().decode(errors='replace'))
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace')
            if e.code!=403 or 'imunify360' not in raw.lower(): raise
    raise RuntimeError('WAF did not release')
root=fetch('/')
routes=root.get('routes',{})
targets=['/rankmath/v1/status/getViewData','/rankmath/v1/status/exportSettings','/rankmath/v1/setupWizard/getStepData','/rankmath/v1/updateSettings','/rankmath/v1/searchPage','/rankmath/v1/updateMeta','/rankmath/v1/updateSchemas']
out={}
for t in targets:
    v=routes.get(t)
    if not v: out[t]=None; continue
    eps=[]
    for e in v.get('endpoints',[]):
        args=e.get('args',{}) or {}
        eps.append({'methods':e.get('methods',[]),'args':{k:{'required':vv.get('required',False),'type':vv.get('type'),'default':vv.get('default')} for k,vv in args.items()}})
    out[t]={'methods':v.get('methods',[]),'endpoints':eps}
print(json.dumps(out,ensure_ascii=False,indent=2))
