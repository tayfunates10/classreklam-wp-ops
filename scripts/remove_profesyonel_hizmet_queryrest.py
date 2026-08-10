#!/usr/bin/env python3
import base64, json, os, time, urllib.error, urllib.parse, urllib.request

BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def req(method, route, payload=None, retries=4):
    parsed=urllib.parse.urlsplit(route)
    q={'rest_route':parsed.path}
    if parsed.query:
        for k,v in urllib.parse.parse_qsl(parsed.query,keep_blank_values=True):
            q[k]=v
    url=BASE+'/?'+urllib.parse.urlencode(q)
    data=None
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    last=None
    for i in range(retries):
        try:
            r=urllib.request.Request(url,data=data,headers=headers,method=method)
            with urllib.request.urlopen(r,timeout=45) as h:
                raw=h.read().decode('utf-8',errors='replace')
                return h.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw=e.read().decode('utf-8',errors='replace')
            last=(e.code,raw[:800])
            if e.code==403 and i<retries-1:
                time.sleep(8*(i+1))
                continue
            raise RuntimeError(f'HTTP {e.code}: {raw[:1200]}')
    raise RuntimeError(str(last))

code,page=req('GET','/wp/v2/pages/6?context=edit')
raw=page.get('content',{}).get('raw','')
before=raw
for v in ('Profesyonel Hizmet','profesyonel hizmet'):
    raw=raw.replace(v,'')
raw=raw.replace('<span class="cr-heading-line2"></span>','')
raw=raw.replace('<span class="cr-heading-line2"> </span>','')
code,body=req('POST','/wp/v2/pages/6',{'content':raw})
if code not in (200,201):
    raise RuntimeError(f'homepage update failed: {code}')
print(json.dumps({
    'status':'success',
    'phrase_present_before':'Profesyonel Hizmet' in before,
    'phrase_present_after':'Profesyonel Hizmet' in raw,
    'content_changed':raw!=before,
    'modified':body.get('modified'),
},ensure_ascii=False,indent=2))
