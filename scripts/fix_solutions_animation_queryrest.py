#!/usr/bin/env python3
import base64,json,os,re,time,urllib.parse,urllib.request,urllib.error

BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
MARK_START='<!-- cr-solutions-animation-v2:start -->'
MARK_END='<!-- cr-solutions-animation-v2:end -->'

CSS='''
<!-- cr-solutions-animation-v2:start -->
<style id="cr-solutions-animation-v2">
/* Single-source final override for the hero word "Çözümleri".
   It intentionally neutralizes the older gradient/pseudo-element animation stack. */
html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
  display: block !important;
  position: relative !important;
  width: 100% !important;
  max-width: 100% !important;
  text-align: left !important;

  background: none !important;
  background-image: none !important;
  background-size: auto !important;
  background-position: initial !important;
  -webkit-background-clip: border-box !important;
  background-clip: border-box !important;

  color: #ed1c24 !important;
  -webkit-text-fill-color: #ed1c24 !important;

  text-shadow:
    0 0 5px rgba(237, 28, 36, 0.26),
    0 0 12px rgba(237, 28, 36, 0.14) !important;

  animation: cr-solutions-color-v2 5.6s cubic-bezier(0.42, 0, 0.58, 1) infinite !important;
  overflow: visible !important;
  will-change: color, -webkit-text-fill-color, text-shadow !important;
}

html body section#cr-hero h1.cr-heading span.cr-heading-line2::before,
html body section#cr-hero h1.cr-heading span.cr-heading-line2::after {
  content: none !important;
  display: none !important;
  opacity: 0 !important;
  animation: none !important;
  background: none !important;
}

@keyframes cr-solutions-color-v2 {
  0%, 18%, 82%, 100% {
    color: #ed1c24;
    -webkit-text-fill-color: #ed1c24;
    text-shadow:
      0 0 5px rgba(237, 28, 36, 0.26),
      0 0 12px rgba(237, 28, 36, 0.14);
  }
  40% {
    color: #ff7378;
    -webkit-text-fill-color: #ff7378;
    text-shadow:
      0 0 5px rgba(255, 115, 120, 0.18),
      0 0 10px rgba(255, 255, 255, 0.08);
  }
  50% {
    color: #ffffff;
    -webkit-text-fill-color: #ffffff;
    text-shadow:
      0 0 5px rgba(255, 255, 255, 0.22),
      0 0 10px rgba(255, 255, 255, 0.10);
  }
  60% {
    color: #ff7378;
    -webkit-text-fill-color: #ff7378;
    text-shadow:
      0 0 5px rgba(255, 115, 120, 0.18),
      0 0 10px rgba(255, 255, 255, 0.08);
  }
}

@media (prefers-reduced-motion: reduce) {
  html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
    animation: none !important;
    color: #ed1c24 !important;
    -webkit-text-fill-color: #ed1c24 !important;
    text-shadow: none !important;
    will-change: auto !important;
  }
}
</style>
<!-- cr-solutions-animation-v2:end -->
'''

def request(method,route,params=None,payload=None,retries=5):
    q={'rest_route':route}
    if params: q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q)
    data=None
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    last=''
    for i in range(retries):
        try:
            req=urllib.request.Request(url,data=data,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=45) as r:
                raw=r.read().decode(errors='replace')
                return r.status,json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace'); last=f'{e.code}: {raw[:900]}'
            if e.code==403 and i<retries-1:
                time.sleep(8*(i+1)); continue
            raise RuntimeError(last)
    raise RuntimeError(last)

code,page=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,modified,content'})
raw=page['content']['raw']
# Idempotent: replace any previous v2 override instead of stacking copies.
raw=re.sub(re.escape(MARK_START)+r'.*?'+re.escape(MARK_END), '', raw, flags=re.S)
raw=raw.rstrip()+"\n\n"+CSS+"\n"
code,updated=request('POST','/wp/v2/pages/6',payload={'content':raw})
if code not in (200,201): raise RuntimeError(f'homepage update failed {code}')
# Verify authoritative WordPress content.
code,verify=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,modified,content'})
vraw=verify['content']['raw']
checks={
  'v2_marker_count':vraw.count(MARK_START),
  'v2_keyframe_present':'@keyframes cr-solutions-color-v2' in vraw,
  'v2_animation_present':'animation: cr-solutions-color-v2 5.6s' in vraw,
  'pseudo_disabled':'span.cr-heading-line2::after' in vraw and 'content: none !important' in vraw,
  'reduced_motion_present':'prefers-reduced-motion: reduce' in vraw,
}
print(json.dumps({'status':'success','modified':verify.get('modified'),'checks':checks},ensure_ascii=False,indent=2))
