#!/usr/bin/env python3
import base64,json,os,re,time,urllib.parse,urllib.request,urllib.error
from html.parser import HTMLParser
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/138 Safari/537.36'
SERVICES=[
 ('Edremit Tabela','/edremit-tabela/'),
 ('Totem Tabela','/totem-tabela/'),
 ('Dijital Baskı','/dijital-baski/'),
 ('Araç Giydirme','/arac-giydirme/'),
 ('Cam Giydirme','/cam-giydirme/'),
 ('Kutu Harf Tabela','/kutu-harf-tabela/'),
]
TARGET_PATHS={p for _,p in SERVICES}

def req(method,route,params=None,payload=None,retries=5):
    q={'rest_route':route}
    if params:q.update(params)
    url=BASE+'/?'+urllib.parse.urlencode(q)
    data=None
    h={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode(); h['Content-Type']='application/json; charset=utf-8'
    last=''
    for i in range(retries):
        try:
            r=urllib.request.Request(url,data=data,headers=h,method=method)
            with urllib.request.urlopen(r,timeout=70) as x:
                raw=x.read().decode(errors='replace')
                return x.status,json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='replace'); last=f'HTTP {e.code}: {raw[:1500]}'
            if e.code==403 and i<retries-1: time.sleep(8*(i+1)); continue
            return e.code, {'error':last}
        except Exception as e:
            last=repr(e)
            if i<retries-1: time.sleep(5*(i+1)); continue
            raise
    raise RuntimeError(last)

def plugin_route(plugin_file):
    p=plugin_file[:-4] if plugin_file.endswith('.php') else plugin_file
    return '/wp/v2/plugins/'+p

def norm_path(url):
    if not url:return ''
    try:p=urllib.parse.urlparse(url).path
    except:p=str(url)
    if not p.startswith('/'):p='/'+p
    return p.rstrip('/')+'/'

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.cur={'href':dict(attrs).get('href',''),'text':''}
    def handle_data(self,data):
        if self.cur is not None:self.cur['text']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.cur is not None:
            self.cur['text']=' '.join(self.cur['text'].split()); self.links.append(self.cur); self.cur=None

def region(html,tag):
    m=re.search(rf'<{tag}\b[^>]*>.*?</{tag}>',html,re.I|re.S); return m.group(0) if m else ''

def public_html(url):
    r=urllib.request.Request(url,headers={'User-Agent':UA,'Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache'})
    with urllib.request.urlopen(r,timeout=70) as x:return x.read().decode(errors='replace'),dict(x.headers)

def live_check():
    html,h=public_html(BASE+'/')
    out={}
    for tag in ['header','footer']:
        p=Links(); p.feed(region(html,tag))
        hits=[{'text':x['text'],'href':x['href'],'path':norm_path(x['href'])} for x in p.links if norm_path(x['href']) in TARGET_PATHS]
        out[tag+'_target_hits']=hits
    out['header_count']=len(out['header_target_hits'])
    out['footer_count']=len(out['footer_target_hits'])
    out['footer_paths']=sorted({x['path'] for x in out['footer_target_hits']})
    out['server']=h.get('Server') or h.get('server'); out['cache_control']=h.get('Cache-Control') or h.get('cache-control')
    return out

result={'status':'started','steps':[]}
created=False; plugin_file=None; initial_status=None
try:
    # Temporarily activate LiteSpeed Cache so menu/widget mutations purge server cache through native hooks.
    c,plugins=req('GET','/wp/v2/plugins',{'context':'edit'})
    ls=[p for p in plugins if str(p.get('plugin','')).startswith('litespeed-cache/') or 'LiteSpeed Cache' in str(p.get('name',''))] if isinstance(plugins,list) else []
    if ls:
        plugin_file=ls[0]['plugin']; initial_status=ls[0].get('status','inactive')
        if initial_status!='active':
            c,b=req('POST',plugin_route(plugin_file),payload={'status':'active'}); result['steps'].append({'litespeed_activate_http':c})
        else: result['steps'].append({'litespeed_initial':'active'})
    else:
        c,b=req('POST','/wp/v2/plugins',payload={'slug':'litespeed-cache','status':'active'})
        if c not in (200,201): raise RuntimeError(f'LiteSpeed temporary install failed: {c} {b}')
        plugin_file=b.get('plugin'); created=True; initial_status='absent'; result['steps'].append({'litespeed_temp_install_http':c,'plugin':plugin_file})

    # Delete only the six exact service menu items currently exposed in the header.
    c,items=req('GET','/wp/v2/menu-items',{'context':'edit','per_page':'100'})
    if c!=200 or not isinstance(items,list): raise RuntimeError(f'menu-items read failed {c}')
    matched=[]
    names={n for n,_ in SERVICES}
    for it in items:
        title=it.get('title',{})
        if isinstance(title,dict): title=title.get('raw') or title.get('rendered') or ''
        path=norm_path(it.get('url',''))
        if title in names or path in TARGET_PATHS:
            matched.append({'id':it.get('id'),'title':title,'path':path,'menus':it.get('menus')})
    # Safety: expected exactly these six unique service menu items.
    ids=[x['id'] for x in matched if x.get('id')]
    if len(ids)!=6: raise RuntimeError(f'Expected 6 service menu items, found {len(ids)}: {matched}')
    deleted=[]
    for x in matched:
        c,b=req('DELETE',f"/wp/v2/menu-items/{x['id']}",{'force':'true'})
        deleted.append({'id':x['id'],'title':x['title'],'http':c,'deleted':bool(isinstance(b,dict) and b.get('deleted'))})
        if c!=200 or not (isinstance(b,dict) and b.get('deleted')): raise RuntimeError(f"menu delete failed {x['id']} {c} {b}")
    result['steps'].append({'header_menu_deleted':deleted})

    # Update existing footer widget block-61 instead of creating duplicates.
    c,w=req('GET','/wp/v2/widgets/block-61',{'context':'edit'})
    if c!=200 or not isinstance(w,dict): raise RuntimeError(f'footer widget block-61 read failed {c} {w}')
    inst=w.get('instance') or {}; raw=inst.get('raw') if isinstance(inst,dict) else None
    raw_container=None
    if isinstance(raw,dict):
        if isinstance(raw.get('content'),str): content=raw['content']; raw_container='dict-content'
        else: raise RuntimeError(f'Unsupported block-61 raw dict keys: {list(raw.keys())}')
    elif isinstance(raw,str): content=raw; raw_container='string'
    else: raise RuntimeError(f'Unsupported block-61 instance format: {type(raw).__name__} {inst}')

    lis='\n'.join([f'<li><a href="{path}">{name}</a></li>' for name,path in SERVICES])
    desired=f'<ul class="footer-link-list">\n{lis}\n</ul>'
    if re.search(r'<ul\b[^>]*class=["\'][^"\']*footer-link-list[^"\']*["\'][^>]*>.*?</ul>',content,re.I|re.S):
        new_content=re.sub(r'<ul\b[^>]*class=["\'][^"\']*footer-link-list[^"\']*["\'][^>]*>.*?</ul>',desired,content,count=1,flags=re.I|re.S)
    else:
        raise RuntimeError('footer-link-list not found inside block-61 raw content')

    if raw_container=='dict-content':
        new_raw=dict(raw); new_raw['content']=new_content
    else: new_raw=new_content
    c,b=req('POST','/wp/v2/widgets/block-61',payload={'instance':{'raw':new_raw}})
    if c!=200: raise RuntimeError(f'footer widget update failed {c}: {b}')
    result['steps'].append({'footer_widget_update_http':c,'widget':'block-61','links':[{'text':n,'href':p} for n,p in SERVICES]})

    # Verify authoritative widget rendering before restoring temporary plugin.
    c,v=req('GET','/wp/v2/widgets/block-61',{'context':'edit'})
    rendered=v.get('rendered','') if isinstance(v,dict) else ''
    auth_paths=sorted({norm_path(h) for h in re.findall(r'href=["\']([^"\']+)["\']',rendered) if norm_path(h) in TARGET_PATHS})
    result['steps'].append({'footer_authoritative_paths':auth_paths})
    if set(auth_paths)!=TARGET_PATHS: raise RuntimeError(f'footer authoritative verification failed: {auth_paths}')

    time.sleep(4)
    result['live_before_restore']=live_check()
finally:
    if plugin_file:
        try:
            if created:
                req('POST',plugin_route(plugin_file),payload={'status':'inactive'})
                c,b=req('DELETE',plugin_route(plugin_file),{'force':'true'})
                result['steps'].append({'litespeed_temp_removed':c==200,'delete_http':c})
            elif initial_status!='active':
                c,b=req('POST',plugin_route(plugin_file),payload={'status':'inactive'}); result['steps'].append({'litespeed_restored':'inactive','http':c})
            else: result['steps'].append({'litespeed_restored':'left-active-as-found'})
        except Exception as e: result['steps'].append({'litespeed_restore_error':repr(e)})

time.sleep(2)
result['final_live']=live_check()
final=result['final_live']
ok=(final['header_count']==0 and final['footer_count']==6 and set(final['footer_paths'])==TARGET_PATHS)
result['status']='success' if ok else 'failed'
print(json.dumps(result,ensure_ascii=False,indent=2))
