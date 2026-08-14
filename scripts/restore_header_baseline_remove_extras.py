#!/usr/bin/env python3
import base64, json, os, re, time, urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from pathlib import Path

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamHeaderBaseline/1.0)'
OUT = Path('.ops/header-baseline-restore-2026-08-15.json')
BACKUP = Path('.ops/header-baseline-restore-backup-2026-08-15.json')
BASE_IDS = {22,23,24,25,26,28}
TARGET_PATHS = {
    '/edremit-tabela/', '/totem-tabela/', '/dijital-baski/',
    '/arac-giydirme/', '/cam-giydirme/', '/kutu-harf-tabela/'
}


def api(method, route, params=None, payload=None):
    q={'rest_route':route}
    if params: q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q,doseq=True)
    data=None
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    last=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,data=data,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read().decode('utf-8',errors='replace')
                try: body=json.loads(raw) if raw else {}
                except Exception: body={'raw_sample':raw[:1000]}
                return r.status,body
        except urllib.error.HTTPError as e:
            raw=e.read().decode('utf-8',errors='replace')
            try: body=json.loads(raw)
            except Exception: body={'raw_sample':raw[:1000]}
            last=(e.code,body)
            if e.code==403 and attempt<3:
                time.sleep(8*(attempt+1)); continue
            return last
        except Exception as e:
            last=(0,{'error':f'{type(e).__name__}: {e}'})
            if attempt<3:
                time.sleep(5*(attempt+1)); continue
            return last
    return last


def norm_path(url):
    if not url: return ''
    p=urllib.parse.urlparse(urllib.parse.urljoin(BASE+'/',str(url))).path or '/'
    return p.rstrip('/')+'/' if p!='/' else '/'


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self.cur={'href':dict(attrs).get('href',''),'text':''}
    def handle_data(self,data):
        if self.cur is not None: self.cur['text']+=data
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.cur is not None:
            self.cur['text']=' '.join(self.cur['text'].split()); self.links.append(self.cur); self.cur=None


def region(raw,tag):
    m=re.search(rf'<{tag}\b[^>]*>.*?</{tag}>',raw,re.I|re.S)
    return m.group(0) if m else ''


def live_state():
    req=urllib.request.Request(BASE+'/?header-baseline-check='+str(int(time.time())),headers={
        'User-Agent':UA,'Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache'
    })
    with urllib.request.urlopen(req,timeout=60) as r: raw=r.read().decode('utf-8',errors='replace')
    out={}
    for tag in ('header','footer'):
        p=Links(); p.feed(region(raw,tag))
        all_links=[{'text':x['text'],'path':norm_path(x['href'])} for x in p.links]
        out[tag+'_service_hits']=[x for x in all_links if x['path'] in TARGET_PATHS]
        out[tag+'_service_count']=len(out[tag+'_service_hits'])
        if tag=='header': out['header_links']=all_links
    return out


def main():
    result={'status':'preflight','deleted':[],'verification':{}}
    code,items=api('GET','/wp/v2/menu-items',{'context':'edit','per_page':100,'_fields':'id,status,title,url,menus'})
    if code!=200 or not isinstance(items,list): raise RuntimeError(f'menu read failed: {code} {items}')
    base=[x for x in items if x.get('id') in BASE_IDS]
    if len(base)!=6: raise RuntimeError(f'baseline menu identity mismatch: {[x.get("id") for x in base]}')
    menu_ids={int(x.get('menus')) for x in base if x.get('menus')}
    if len(menu_ids)!=1: raise RuntimeError(f'primary menu ambiguous: {menu_ids}')
    primary=next(iter(menu_ids))
    extras=[x for x in items if int(x.get('menus') or 0)==primary and norm_path(x.get('url')) in TARGET_PATHS]
    backup={'primary_menu':primary,'base_items':base,'extra_service_items':extras,'live_before':live_state()}
    save(BACKUP,backup)

    for x in extras:
        c,b=api('DELETE',f"/wp/v2/menu-items/{x['id']}",{'force':'true'})
        ok=c==200 and isinstance(b,dict) and b.get('deleted')
        result['deleted'].append({'id':x.get('id'),'path':norm_path(x.get('url')),'http':c,'deleted':bool(ok)})
        if not ok: raise RuntimeError(f"menu delete failed {x.get('id')}: {c} {b}")

    c,after=api('GET','/wp/v2/menu-items',{'context':'edit','per_page':100,'_fields':'id,status,title,url,menus'})
    if c!=200 or not isinstance(after,list): raise RuntimeError(f'after menu read failed: {c}')
    remaining=[x for x in after if int(x.get('menus') or 0)==primary and norm_path(x.get('url')) in TARGET_PATHS]
    base_after=[x for x in after if x.get('id') in BASE_IDS]
    time.sleep(4)
    live=live_state()
    result['verification']={
        'base_menu_count':len(base_after),
        'remaining_service_menu_items':len(remaining),
        'live':live,
    }
    ok=(len(base_after)==6 and len(remaining)==0 and live.get('header_service_count')==0 and live.get('footer_service_count')==0)
    result['status']='success' if ok else 'verification-failed'
    save(OUT,result)
    print(json.dumps(result,ensure_ascii=True,indent=2))
    if not ok: raise SystemExit(2)

if __name__=='__main__': main()
