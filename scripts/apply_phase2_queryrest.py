#!/usr/bin/env python3
import base64, importlib.util, json, os, urllib.error, urllib.parse, urllib.request

BASE=os.environ['WP_URL'].rstrip('/')
USER=os.environ['WP_USER']
APP=os.environ['WP_APP_PASSWORD']
AUTH='Basic '+base64.b64encode(f'{USER}:{APP}'.encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def queryrest_url(path):
    parsed=urllib.parse.urlsplit(path)
    route=parsed.path
    if route.startswith('/wp-json'):
        route=route[len('/wp-json'):]
    if not route.startswith('/'):
        route='/'+route
    url=BASE+'/?rest_route='+urllib.parse.quote(route,safe='/')
    if parsed.query:
        url+='&'+parsed.query
    return url

def request(method,path,payload=None):
    data=None
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(queryrest_url(path),data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode('utf-8',errors='replace')
            try: body=json.loads(raw) if raw else {}
            except Exception: body={'raw':raw[:1500]}
            return r.status,body
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8',errors='replace')
        try: body=json.loads(raw)
        except Exception: body={'raw':raw[:1500]}
        return e.code,body

os.environ.setdefault('WP_SESSION_COOKIE_HEADER','')
os.environ.setdefault('WP_REST_NONCE','')
spec=importlib.util.spec_from_file_location('phase2','scripts/apply_phase2_cookie.py')
phase2=importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase2)
phase2.request=request
phase2.main()
