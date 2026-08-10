#!/usr/bin/env python3
import base64, json, os, re, time, urllib.parse, urllib.request, urllib.error

BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
OLD_START='<!-- cr-solutions-animation-v2:start -->'
OLD_END='<!-- cr-solutions-animation-v2:end -->'
START='<!-- cr-solutions-animation-js-v4:start -->'
END='<!-- cr-solutions-animation-js-v4:end -->'

BLOCK=r'''
<!-- cr-solutions-animation-js-v4:start -->
<style id="cr-solutions-animation-js-v4">
html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
  position: relative !important;
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  text-align: left !important;
  background: none !important;
  background-image: none !important;
  -webkit-background-clip: border-box !important;
  background-clip: border-box !important;
  color: #ed1c24 !important;
  -webkit-text-fill-color: #ed1c24 !important;
  text-shadow: 0 0 5px rgba(237,28,36,.26), 0 0 12px rgba(237,28,36,.14) !important;
  animation: none !important;
  animation-name: none !important;
  animation-duration: 0s !important;
  animation-delay: 0s !important;
  animation-iteration-count: 1 !important;
  animation-direction: normal !important;
  animation-fill-mode: none !important;
  animation-play-state: paused !important;
  animation-timing-function: linear !important;
  overflow: visible !important;
  will-change: auto !important;
  --cr-solutions-opacity: .06;
}
html body section#cr-hero h1.cr-heading span.cr-heading-line2::before {
  content: none !important;
  display: none !important;
  animation: none !important;
}
html body section#cr-hero h1.cr-heading span.cr-heading-line2::after {
  content: attr(data-cr-text) !important;
  position: absolute !important;
  inset: 0 auto auto 0 !important;
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  pointer-events: none !important;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  background: none !important;
  background-image: none !important;
  -webkit-background-clip: border-box !important;
  background-clip: border-box !important;
  text-shadow: 0 0 5px rgba(255,255,255,.18), 0 0 10px rgba(255,255,255,.08) !important;
  opacity: var(--cr-solutions-opacity) !important;
  animation: none !important;
  animation-name: none !important;
  animation-duration: 0s !important;
  animation-delay: 0s !important;
  animation-iteration-count: 1 !important;
  animation-direction: normal !important;
  animation-fill-mode: none !important;
  animation-play-state: paused !important;
  transition: none !important;
  will-change: opacity !important;
}
@media (prefers-reduced-motion: reduce) {
  html body section#cr-hero h1.cr-heading span.cr-heading-line2 {
    --cr-solutions-opacity: 0;
    text-shadow: none !important;
  }
}
</style>
<script id="cr-solutions-animation-js-v4-script">
(function(){
  function init(){
    var el=document.querySelector('section#cr-hero h1.cr-heading span.cr-heading-line2');
    if(!el || el.dataset.crContinuousReady==='1') return;
    el.dataset.crContinuousReady='1';
    if(!el.getAttribute('data-cr-text')) el.setAttribute('data-cr-text',(el.textContent||'').trim());

    var mq=window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
    if(mq && mq.matches){
      el.style.setProperty('--cr-solutions-opacity','0');
      return;
    }

    var minOpacity=0.06;
    var maxOpacity=1;
    var period=6400;
    var phase=0;
    var last=performance.now();

    function frame(now){
      var dt=now-last;
      last=now;
      if(dt<0 || !isFinite(dt)) dt=0;
      /* Clamp long background-tab gaps; resume from the exact visible phase instead of jumping. */
      if(dt>50) dt=50;
      phase += (dt/period) * Math.PI * 2;
      /* No modulo/reset: cosine is inherently periodic and continuous in value + velocity. */
      var mix=0.5 - 0.5*Math.cos(phase);
      var opacity=minOpacity + (maxOpacity-minOpacity)*mix;
      el.style.setProperty('--cr-solutions-opacity', opacity.toFixed(5));
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
</script>
<!-- cr-solutions-animation-js-v4:end -->
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
            raw=e.read().decode(errors='replace'); last=f'{e.code}: {raw[:1000]}'
            if e.code==403 and i<retries-1:
                time.sleep(8*(i+1)); continue
            raise RuntimeError(last)
    raise RuntimeError(last)

code,page=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,modified,content'})
raw=page['content']['raw']
raw=re.sub(re.escape(OLD_START)+r'.*?'+re.escape(OLD_END),'',raw,flags=re.S)
raw=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',raw,flags=re.S)
raw=re.sub(
    r'<span\s+class=["\']cr-heading-line2["\'](?:\s+data-cr-text=["\'][^"\']*["\'])?\s*>(.*?)</span>',
    lambda m:'<span class="cr-heading-line2" data-cr-text="'+re.sub(r'<[^>]+>','',m.group(1)).strip().replace('"','&quot;')+'">'+m.group(1)+'</span>',
    raw,count=1,flags=re.S)
raw=raw.rstrip()+"\n\n"+BLOCK+"\n"
code,updated=request('POST','/wp/v2/pages/6',payload={'content':raw})
if code not in (200,201): raise RuntimeError(f'homepage update failed {code}')
code,verify=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,modified,content'})
v=verify['content']['raw']
checks={
  'marker_count':v.count(START),
  'old_final_removed':OLD_START not in v,
  'js_script_present':'cr-solutions-animation-js-v4-script' in v,
  'request_animation_frame_present':'requestAnimationFrame(frame)' in v,
  'no_modulo_reset':'phase %' not in v and 'phase=' in v,
  'base_animation_locked':'animation-name: none !important' in v and 'animation-duration: 0s !important' in v,
  'overlay_css_animation_disabled':'transition: none !important' in v,
  'data_text_present':'data-cr-text="Çözümleri"' in v,
}
print(json.dumps({'status':'success','modified':verify.get('modified'),'checks':checks},ensure_ascii=False,indent=2))
