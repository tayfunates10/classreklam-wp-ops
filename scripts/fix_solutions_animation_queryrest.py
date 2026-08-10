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
/* Truly seamless hero word animation.
   The base text stays red permanently; a white duplicate fades in/out above it.
   Because the base never changes color, there is no iteration-boundary reset flash. */
html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
  display: block !important;
  position: relative !important;
  width: 100% !important;
  max-width: 100% !important;
  text-align: left !important;

  background: none !important;
  background-image: none !important;
  -webkit-background-clip: border-box !important;
  background-clip: border-box !important;

  color: #ed1c24 !important;
  -webkit-text-fill-color: #ed1c24 !important;
  text-shadow:
    0 0 5px rgba(237, 28, 36, 0.26),
    0 0 12px rgba(237, 28, 36, 0.14) !important;

  animation: none !important;
  overflow: visible !important;
  will-change: auto !important;
}

html body section#cr-hero h1.cr-heading span.cr-heading-line2::before {
  content: none !important;
  display: none !important;
  animation: none !important;
}

html body section#cr-hero h1.cr-heading span.cr-heading-line2::after {
  content: attr(data-cr-text) !important;
  display: block !important;
  position: absolute !important;
  inset: 0 auto auto 0 !important;
  width: 100% !important;
  max-width: 100% !important;
  pointer-events: none !important;

  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
  background: none !important;
  background-image: none !important;
  -webkit-background-clip: border-box !important;
  background-clip: border-box !important;
  text-shadow:
    0 0 5px rgba(255,255,255,0.18),
    0 0 10px rgba(255,255,255,0.08) !important;

  opacity: 0 !important;
  animation-name: cr-solutions-white-crossfade !important;
  animation-duration: 6.4s !important;
  animation-timing-function: ease-in-out !important;
  animation-delay: 0s !important;
  animation-iteration-count: infinite !important;
  animation-direction: normal !important;
  animation-fill-mode: both !important;
  animation-play-state: running !important;
  will-change: opacity !important;
}

@keyframes cr-solutions-white-crossfade {
  0%   { opacity: 0; }
  12%  { opacity: 0.06; }
  25%  { opacity: 0.28; }
  40%  { opacity: 0.72; }
  50%  { opacity: 1; }
  60%  { opacity: 0.72; }
  75%  { opacity: 0.28; }
  88%  { opacity: 0.06; }
  100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
    color: #ed1c24 !important;
    -webkit-text-fill-color: #ed1c24 !important;
    text-shadow: none !important;
  }
  html body section#cr-hero h1.cr-heading span.cr-heading-line2::after {
    animation: none !important;
    opacity: 0 !important;
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
# Ensure the animated span exposes its own text to the overlay layer.
raw=re.sub(
    r'<span\s+class=["\']cr-heading-line2["\'](?:\s+data-cr-text=["\'][^"\']*["\'])?\s*>(.*?)</span>',
    lambda m: '<span class="cr-heading-line2" data-cr-text="'+re.sub(r'<[^>]+>','',m.group(1)).strip().replace('"','&quot;')+'">'+m.group(1)+'</span>',
    raw,
    count=1,
    flags=re.S,
)
# Idempotent final override replacement.
raw=re.sub(re.escape(MARK_START)+r'.*?'+re.escape(MARK_END), '', raw, flags=re.S)
raw=raw.rstrip()+"\n\n"+CSS+"\n"
code,updated=request('POST','/wp/v2/pages/6',payload={'content':raw})
if code not in (200,201): raise RuntimeError(f'homepage update failed {code}')
code,verify=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,modified,content'})
vraw=verify['content']['raw']
checks={
  'marker_count':vraw.count(MARK_START),
  'overlay_text_attribute_present':'data-cr-text="Çözümleri"' in vraw or 'data-cr-text="Çözümleri' in vraw,
  'base_animation_disabled':'animation: none !important' in vraw,
  'crossfade_keyframe_present':'@keyframes cr-solutions-white-crossfade' in vraw,
  'white_overlay_present':'content: attr(data-cr-text) !important' in vraw,
  'loop_boundary_same_state':'0%   { opacity: 0; }' in vraw and '100% { opacity: 0; }' in vraw,
  'reduced_motion_present':'prefers-reduced-motion: reduce' in vraw,
}
print(json.dumps({'status':'success','modified':verify.get('modified'),'checks':checks},ensure_ascii=False,indent=2))
