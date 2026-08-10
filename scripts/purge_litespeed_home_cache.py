#!/usr/bin/env python3
import base64,json,os,time,urllib.error,urllib.parse,urllib.request

BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
TARGET_MARKER='cr-solutions-animation-js-v4'

def request(method,route,params=None,payload=None,auth=True,retries=4):
    q={'rest_route':route} if route else {}
    if params: q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q) if q else BASE+'/'
    data=None
    headers={'Accept':'application/json' if route else 'text/html,*/*','User-Agent':UA}
    if auth: headers['Authorization']=AUTH
    if route: headers['Referer']=BASE+'/wp-admin/'
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    last=''
    for i in range(retries):
        try:
            req=urllib.request.Request(url,data=data,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read().decode(errors='replace')
                if route:
                    try: body=json.loads(raw) if raw else {}
                    except Exception: body={'raw':raw[:2000]}
                else: body=raw
                return r.status,body,dict(r.headers)
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace'); last=f'HTTP {e.code}: {raw[:1800]}'
            if e.code==403 and i<retries-1:
                time.sleep(8*(i+1)); continue
            raise RuntimeError(last)
    raise RuntimeError(last)

def plugin_route(plugin_file):
    p=plugin_file[:-4] if plugin_file.endswith('.php') else plugin_file
    return '/wp/v2/plugins/'+p

def live_check(label):
    stamp=str(int(time.time()*1000))
    url=BASE+'/?crpurgev4='+stamp+'&phase='+urllib.parse.quote(label)
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache','Accept':'text/html,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:
        html=r.read().decode(errors='replace'); hdr=dict(r.headers)
    return {
        'marker_present':TARGET_MARKER in html,
        'overlay_present':'data-cr-text="Çözümleri"' in html,
        'raf_present':'requestAnimationFrame(frame)' in html,
        'cosine_present':'Math.cos(phase)' in html,
        'css_keyframe_absent':'@keyframes cr-solutions-white' not in html,
        'base_locked':'animation-name: none !important' in html and 'animation-duration: 0s !important' in html,
        'variable_overlay':'opacity: var(--cr-solutions-opacity)' in html,
        'minimum_nonzero':'minOpacity=0.06' in html,
        'server':hdr.get('Server') or hdr.get('server'),
        'cache_control':hdr.get('Cache-Control') or hdr.get('cache-control'),
        'html_chars':len(html),
    }

result={'status':'started','steps':[]}; created=False; plugin_file=None; initial_status=None
try:
    code,plugins,_=request('GET','/wp/v2/plugins',params={'context':'edit'})
    ls=[p for p in plugins if str(p.get('plugin','')).startswith('litespeed-cache/') or 'LiteSpeed Cache' in str(p.get('name',''))]
    if ls:
        plugin_file=ls[0]['plugin']; initial_status=ls[0].get('status','inactive')
        result['steps'].append({'plugin_initial':'present','plugin':plugin_file,'status':initial_status})
        if initial_status!='active':
            code,body,_=request('POST',plugin_route(plugin_file),payload={'status':'active'})
            result['steps'].append({'plugin_activation_http':code,'status':body.get('status') if isinstance(body,dict) else None})
    else:
        code,body,_=request('POST','/wp/v2/plugins',payload={'slug':'litespeed-cache','status':'active'})
        plugin_file=body.get('plugin') if isinstance(body,dict) else None
        if not plugin_file: raise RuntimeError(f'LiteSpeed Cache install did not return plugin id: {body}')
        created=True; initial_status='absent'
        result['steps'].append({'plugin_initial':'absent','plugin_install_http':code,'plugin':plugin_file,'status':body.get('status')})

    code,page,_=request('GET','/wp/v2/pages/6',params={'context':'edit','_fields':'id,content,modified'})
    raw=page.get('content',{}).get('raw','')
    if TARGET_MARKER not in raw: raise RuntimeError('Authoritative homepage content does not contain JS V4 animation marker')
    code,updated,_=request('POST','/wp/v2/pages/6',payload={'content':raw})
    result['steps'].append({'homepage_resave_http':code,'modified':updated.get('modified') if isinstance(updated,dict) else None})
    time.sleep(3)
    result['after_purge_live']=live_check('active')
    if not result['after_purge_live']['marker_present']:
        code,updated,_=request('POST','/wp/v2/pages/6',payload={'content':raw})
        result['steps'].append({'second_resave_http':code}); time.sleep(3)
        result['after_second_purge_live']=live_check('active2')
finally:
    if plugin_file:
        try:
            if created:
                request('POST',plugin_route(plugin_file),payload={'status':'inactive'})
                result['steps'].append({'plugin_restore':'deactivated-temporary'})
                try:
                    code,body,_=request('DELETE',plugin_route(plugin_file))
                    result['steps'].append({'plugin_cleanup':'deleted-temporary','http':code,'deleted':body.get('deleted') if isinstance(body,dict) else None})
                except Exception as e:
                    result['steps'].append({'plugin_cleanup':'delete-failed-left-inactive','error':str(e)[:500]})
            elif initial_status!='active':
                code,body,_=request('POST',plugin_route(plugin_file),payload={'status':'inactive'})
                result['steps'].append({'plugin_restore':'inactive','http':code})
            else: result['steps'].append({'plugin_restore':'left-active-as-found'})
        except Exception as e: result['steps'].append({'plugin_restore_error':str(e)[:800]})
try:
    time.sleep(2); result['final_live']=live_check('final')
except Exception as e: result['final_live_error']=str(e)[:1000]
final=result.get('final_live',{})
ok=all(final.get(k) for k in ['marker_present','raf_present','cosine_present','css_keyframe_absent','base_locked','variable_overlay','minimum_nonzero'])
result['status']='success' if ok else 'failed'
print(json.dumps(result,ensure_ascii=False,indent=2))
