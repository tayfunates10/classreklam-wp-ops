#!/usr/bin/env python3
import base64,json,os,re,time,urllib.parse,urllib.request,urllib.error
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def get(route,params=None):
    q={'rest_route':route}
    if params: q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q)
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    last=''
    for i in range(5):
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=45) as r:
                return json.loads(r.read().decode(errors='replace'))
        except urllib.error.HTTPError as e:
            last=e.read().decode(errors='replace')[:800]
            if e.code==403 and i<4:
                time.sleep(8*(i+1)); continue
            raise
    raise RuntimeError(last)
page=get('/wp/v2/pages/6',{'context':'edit','_fields':'id,modified,content'})
raw=page['content']['raw']
needle='cr-heading-line2'
pos=raw.find(needle)
contexts=[]
if pos>=0: contexts.append(raw[max(0,pos-2500):min(len(raw),pos+5000)])
# collect relevant style/keyframe/js snippets mentioning heading, gradient, color, animation
patterns=[r'@keyframes[^}]+\{(?:[^{}]|\{[^{}]*\})*\}',r'[^{}]{0,160}cr-heading-line2[^{}]*\{[^{}]*\}',r'[^{}]{0,160}cr-heading[^{}]*\{[^{}]*\}',r'[^;\n]{0,160}(?:animation|background-clip|-webkit-text-fill-color|linear-gradient|color)[^;\n]{0,260}']
found=[]
for pat in patterns:
    for m in re.finditer(pat,raw,re.I|re.S):
        s=re.sub(r'\s+',' ',m.group(0)).strip()
        if s not in found: found.append(s[:3000])
# script snippets that mention heading class/name
for m in re.finditer(r'<script[^>]*>(.*?)</script>',raw,re.I|re.S):
    body=m.group(1)
    if 'cr-heading' in body or 'heading-line2' in body or 'Çözümleri' in body:
        found.append(re.sub(r'\s+',' ',body).strip()[:5000])
print(json.dumps({'modified':page.get('modified'),'heading_contexts':contexts,'relevant_rules':found[:80]},ensure_ascii=False,indent=2))
