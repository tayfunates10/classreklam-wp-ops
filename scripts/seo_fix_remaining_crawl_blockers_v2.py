#!/usr/bin/env python3
import base64, copy, html, json, os, re, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36'
OUT=Path('.ops/seo-crawl-blocker-remediation-v2-2026-08-14.json')
BACKUP=Path('.ops/seo-crawl-blocker-backup-v2-2026-08-14.json')
MARKER='cr-seo-legal-bridge-v1'
PIDS=(8,10,12,14,683,1183,1186)


def qurl(route,params=None):
    q={'rest_route':route}
    if params:q.update(params)
    return BASE+'/?'+urllib.parse.urlencode(q,doseq=True,safe='/:,')

def api_once(method,route,params=None,payload=None):
    data=None; h={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode(); h['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(qurl(route,params),data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=70) as r:
            raw=r.read().decode(errors='replace')
            try:b=json.loads(raw) if raw else {}
            except:b={'raw_sample':raw[:1500]}
            return r.status,b
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try:b=json.loads(raw)
        except:b={'raw_sample':raw[:1500]}
        return e.code,b
    except Exception as e:return 0,{'error':f'{type(e).__name__}: {e}'}

def api(method,route,params=None,payload=None,retries=5):
    last=None
    for i in range(retries):
        time.sleep(1.8); c,b=api_once(method,route,params,payload); last=(c,b)
        txt=json.dumps(b,ensure_ascii=False).lower() if isinstance(b,(dict,list)) else str(b).lower()
        if not (c==0 or (c==403 and ('imunify360' in txt or 'bot-protection' in txt))):return c,b
        time.sleep(8*(i+1))
    return last

def ensure(c,b,label):
    if c not in (200,201):raise RuntimeError(f'{label}: HTTP {c} {b}')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None
NOREDIRECT=urllib.request.build_opener(NoRedirect)

def is_waf(s):
    s=(s or '').lower(); return 'one moment, please' in s or 'imunify360' in s

def public(path,no_redirect=False,cache_bust=True,limit=900000):
    url=BASE+path if path.startswith('/') else path
    if cache_bust:
        p=urllib.parse.urlsplit(url); pairs=urllib.parse.parse_qsl(p.query,keep_blank_values=True); pairs.append(('crseo',str(int(time.time()*1000))))
        url=urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(pairs),p.fragment))
    opener=NOREDIRECT if no_redirect else urllib.request.build_opener()
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xml,text/xml;q=0.9,*/*;q=0.5','Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache'})
    try:
        with opener.open(req,timeout=70) as r:
            body=r.read(limit).decode(errors='replace'); return {'http':r.status,'location':r.headers.get('Location',''),'final_url':r.geturl(),'waf':is_waf(body),'body':body}
    except urllib.error.HTTPError as e:
        body=e.read(limit).decode(errors='replace'); return {'http':e.code,'location':e.headers.get('Location',''),'final_url':e.geturl(),'waf':is_waf(body),'body':body}
    except Exception as e:return {'http':0,'location':'','final_url':url,'waf':False,'body':'','error':f'{type(e).__name__}: {e}'}

def clean(s):return re.sub(r'\s+',' ',html.unescape(str(s or ''))).strip()
def h1s(raw):return [clean(re.sub(r'<[^>]+>',' ',x)) for x in re.findall(r'<h1\b[^>]*>(.*?)</h1>',raw or '',re.I|re.S)]
def canonical(raw):
    m=re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',raw or '',re.I) or re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',raw or '',re.I)
    return html.unescape(m.group(1)).strip() if m else ''
def robots(raw):
    m=re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)',raw or '',re.I) or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']robots["\']',raw or '',re.I)
    return html.unescape(m.group(1)).strip() if m else ''

def read_page(pid):
    c,b=api('GET',f'/wp/v2/pages/{pid}',{'context':'edit','_fields':'id,slug,status,link,title,content,excerpt,modified'})
    ensure(c,b,f'get page {pid}'); return b
def raw(p):return str((p.get('content') or {}).get('raw') or '')
def update_page(pid,payload,label):
    c,b=api('POST',f'/wp/v2/pages/{pid}',payload=payload); ensure(c,b,label); return b
def rankmeta(pid,meta,label):
    c,b=api('POST','/rankmath/v1/updateMeta',payload={'objectType':'post','objectID':int(pid),'meta':meta}); ensure(c,b,label); return b

def menu_items():
    c,b=api('GET','/wp/v2/menu-items',{'context':'edit','per_page':100}); ensure(c,b,'menu items');
    if not isinstance(b,list):raise RuntimeError('menu-items not list')
    return b
def tval(i):
    t=i.get('title') or ''; return str((t.get('raw') or t.get('rendered') or '') if isinstance(t,dict) else t)
def mbackup(i):
    keys=['id','status','url','type','object','object_id','parent','attr_title','description','classes','xfn','target','menus','menu_order']; d={k:copy.deepcopy(i.get(k)) for k in keys if k in i}; d['title']=tval(i); return d
def delete_menu(iid):
    c,b=api('DELETE',f'/wp/v2/menu-items/{iid}',{'force':'true'}); ensure(c,b,f'delete menu {iid}')
    if not isinstance(b,dict) or not b.get('deleted'):raise RuntimeError(f'menu {iid} delete unconfirmed')
def recreate_menu(s):
    payload={'status':'publish','title':s.get('title') or '','type':s.get('type') or 'custom','parent':int(s.get('parent') or 0),'menus':int(s.get('menus') or 0),'menu_order':int(s.get('menu_order') or 0),'attr_title':s.get('attr_title') or '','description':s.get('description') or '','classes':s.get('classes') or [],'xfn':s.get('xfn') or [],'target':s.get('target') or ''}
    if payload['type']=='custom':payload['url']=s.get('url') or BASE+'/'
    else:payload['object']=s.get('object') or 'page'; payload['object_id']=int(s.get('object_id') or 0)
    c,b=api('POST','/wp/v2/menu-items',payload=payload); ensure(c,b,'recreate menu'); return b

def promote(rawhtml,selector,text,label):
    if re.search(r'<h1\b',rawhtml,re.I):return rawhtml,'already-has-h1'
    pat=re.compile(rf'<h2(\b[^>]*)>\s*{re.escape(text)}\s*</h2>',re.I|re.S); ms=list(pat.finditer(rawhtml))
    if len(ms)!=1:raise RuntimeError(f'{label}: expected one H2 {text}, found {len(ms)}')
    out=pat.sub(lambda m:f'<h1{m.group(1)}>{text}</h1>',rawhtml,count=1)
    old=selector+' h2'; new=selector+' h1'
    if old not in out:raise RuntimeError(f'{label}: selector {old} missing')
    return out.replace(old,new),'promoted'

def pverify(path,h1=None,canon=None,noindex=None):
    r=public(path); body=r.get('body',''); info={'http':r.get('http'),'waf':r.get('waf'),'h1':h1s(body),'canonical':canonical(body),'robots':robots(body)}
    if info['http']!=200 or info['waf']:raise RuntimeError(f'{path}: HTTP/WAF {info}')
    if h1 is not None and info['h1']!=[h1]:raise RuntimeError(f'{path}: H1 {info["h1"]}, expected {h1}')
    if canon is not None and info['canonical']!=canon:raise RuntimeError(f'{path}: canonical {info["canonical"]}, expected {canon}')
    if noindex is True and 'noindex' not in info['robots'].lower():raise RuntimeError(f'{path}: expected noindex, got {info["robots"]}')
    if noindex is False and 'noindex' in info['robots'].lower():raise RuntimeError(f'{path}: unexpected noindex')
    return info
def punavailable(path):
    r=public(path,no_redirect=True); info={'http':r.get('http'),'waf':r.get('waf'),'location':r.get('location')}
    if info['waf'] or info['http'] not in (404,410):raise RuntimeError(f'{path}: expected 404/410, got {info}')
    return info

def plugin_route(p):return '/wp/v2/plugins/'+(p[:-4] if p.endswith('.php') else p)
def restore_page(p):
    return api('POST',f"/wp/v2/pages/{p['id']}",payload={'status':p.get('status') or 'draft','slug':p.get('slug') or '','title':(p.get('title') or {}).get('raw') or '','content':raw(p),'excerpt':(p.get('excerpt') or {}).get('raw') or ''})

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result={'status':'preflight','changes':[],'verification':{},'rollback':[],'cache':[]}
    pages={}; deleted=[]; plugin=None; plugin_initial=None; plugin_created=False
    try:
        pages={i:read_page(i) for i in PIDS}
        expected={8:('hakkimizda','publish'),10:('hizmetlerimiz','publish'),12:('galeri','publish'),14:('blog','publish'),683:('referans-isler','draft'),1183:('gizlilik-politikasi','draft'),1186:('gizlilik-politikasi-2','publish')}
        for pid,(slug,status) in expected.items():
            p=pages[pid]
            if p.get('slug')!=slug or p.get('status')!=status:raise RuntimeError(f'page {pid}: expected {slug}/{status}, got {p.get("slug")}/{p.get("status")}')
        if '[class_referans_isleri]' not in raw(pages[683]):raise RuntimeError('legacy reference page lost expected listing shortcode')
        if MARKER not in raw(pages[1183]) or MARKER not in raw(pages[1186]):raise RuntimeError('privacy marker mismatch')
        items=menu_items(); p1183=[i for i in items if int(i.get('object_id') or 0)==1183]; p1186=[i for i in items if int(i.get('object_id') or 0)==1186]
        if len(p1183)!=1:raise RuntimeError(f'expected one menu item for 1183, got {[i.get("id") for i in p1183]}')
        if len(p1186)>1:raise RuntimeError(f'expected <=1 menu item for 1186, got {[i.get("id") for i in p1186]}')
        BACKUP.write_text(json.dumps({'pages':pages,'menus':[mbackup(i) for i in p1183+p1186],'blog_canonical':BASE+'/blog/'},ensure_ascii=False,indent=2),encoding='utf-8')

        # Privacy collision: canonical page becomes 1183; duplicate -2 retires.
        update_page(1186,{'status':'draft'},'draft duplicate privacy')
        update_page(1183,{'status':'publish','slug':'gizlilik-politikasi','title':'Gizlilik Politikası','content':raw(pages[1183])},'publish privacy 1183')
        rankmeta(1183,{'rank_math_title':'Gizlilik Politikası | Class Reklam','rank_math_description':'Class Reklam web sitesi gizlilik ve kişisel verilerle ilgili genel bilgilendirme bağlantıları.','rank_math_canonical_url':BASE+'/gizlilik-politikasi/','rank_math_robots':['noindex','follow']},'privacy meta')
        result['changes'] += [{'page':1186,'status':'draft'},{'page':1183,'status':'publish'}]
        for i in p1186:
            s=mbackup(i); delete_menu(int(i['id'])); deleted.append(s); result['changes'].append({'menu_deleted':int(i['id']),'reason':'duplicate privacy'})

        # Functional legacy alias: keep shortcode-driven slider clicks working but remove alias from index.
        update_page(683,{'status':'publish','content':raw(pages[683]),'title':'Referans İşler'},'publish functional legacy reference alias')
        rankmeta(683,{'rank_math_title':'Referans İşler | Class Reklam','rank_math_description':'Class Reklam referans işlerini ve tabela, baskı, araç giydirme uygulamalarını inceleyin.','rank_math_canonical_url':BASE+'/referanslar/','rank_math_robots':['noindex','follow']},'legacy reference noindex meta')
        result['changes'].append({'page':683,'status':'publish','robots':'noindex,follow','canonical_target':BASE+'/referanslar/'})

        # H1 repairs preserving existing visual selectors.
        a,act=promote(raw(pages[8]),'.cr-about-head','Hakkımızda','Hakkımızda'); update_page(8,{'content':a},'Hakkımızda H1'); result['changes'].append({'page':8,'h1':act})
        s,act=promote(raw(pages[10]),'.cr-services-v2-head','Hizmetlerimiz','Hizmetlerimiz'); update_page(10,{'content':s},'Hizmetlerimiz H1'); result['changes'].append({'page':10,'h1':act})
        g=raw(pages[12])
        if not re.search(r'<h1\b',g,re.I):
            if '[cr_gallery]' not in g:raise RuntimeError('gallery shortcode missing')
            g='<!-- wp:heading {"level":1,"textAlign":"center","className":"cr-gallery-page-title"} -->\n<h1 class="wp-block-heading has-text-align-center cr-gallery-page-title">Galeri</h1>\n<!-- /wp:heading -->\n'+g
            update_page(12,{'content':g},'Galeri H1'); result['changes'].append({'page':12,'h1':'added'})

        # Let Rank Math generate page-aware canonicals for /blog/page/N/.
        rankmeta(14,{'rank_math_canonical_url':''},'clear hardcoded blog canonical'); result['changes'].append({'page':14,'canonical':'dynamic'})

        # Proven LiteSpeed save hook to invalidate server/sitemap cache; clean up afterward.
        c,pl=api('GET','/wp/v2/plugins',{'context':'edit'}); ensure(c,pl,'plugins')
        ls=[x for x in pl if str(x.get('plugin','')).startswith('litespeed-cache/') or 'LiteSpeed Cache' in str(x.get('name',''))] if isinstance(pl,list) else []
        if ls:
            plugin=ls[0]['plugin']; plugin_initial=ls[0].get('status','inactive')
            if plugin_initial!='active':c,b=api('POST',plugin_route(plugin),payload={'status':'active'}); ensure(c,b,'activate LiteSpeed'); result['cache'].append({'activate_existing':plugin})
        else:
            c,b=api('POST','/wp/v2/plugins',payload={'slug':'litespeed-cache','status':'active'}); ensure(c,b,'temp install LiteSpeed'); plugin=b.get('plugin'); plugin_created=True; plugin_initial='absent'; result['cache'].append({'temp_install':plugin})
        for pid in (683,1183,8,10,12,14):
            p=read_page(pid); update_page(pid,{'content':raw(p),'status':p.get('status')},f'resave page {pid} cache purge')
        time.sleep(5)

        # Public validations.
        result['verification']['privacy']=pverify('/gizlilik-politikasi/',noindex=True)
        result['verification']['privacy_duplicate']=punavailable('/gizlilik-politikasi-2/')
        result['verification']['legacy_alias']=pverify('/referans-isler/',h1='Referans İşler',noindex=True)
        result['verification']['references_archive']=pverify('/referanslar/',noindex=False)
        result['verification']['about']=pverify('/hakkimizda/',h1='Hakkımızda',canon=BASE+'/hakkimizda/')
        result['verification']['services']=pverify('/hizmetlerimiz/',h1='Hizmetlerimiz',canon=BASE+'/hizmetlerimiz/')
        result['verification']['gallery']=pverify('/galeri/',h1='Galeri',canon=BASE+'/galeri/')
        result['verification']['blog']=pverify('/blog/',canon=BASE+'/blog/',noindex=False)
        result['verification']['blog2']=pverify('/blog/page/2/',canon=BASE+'/blog/page/2/',noindex=False)
        home=public('/'); hb=home.get('body',''); result['verification']['home_links']={'http':home.get('http'),'waf':home.get('waf'),'page_id_1183':hb.count('page_id=1183'),'privacy_minus_2':hb.count('/gizlilik-politikasi-2/'),'legacy_alias_links':hb.count('/referans-isler/')}
        hv=result['verification']['home_links']
        if hv['http']!=200 or hv['waf'] or hv['page_id_1183'] or hv['privacy_minus_2'] or hv['legacy_alias_links']==0:raise RuntimeError(f'homepage link state invalid: {hv}')
        sm=public('/page-sitemap.xml',limit=600000); sb=sm.get('body',''); result['verification']['page_sitemap']={'http':sm.get('http'),'waf':sm.get('waf'),'legacy_alias':'/referans-isler/' in sb,'privacy':'/gizlilik-politikasi/' in sb,'privacy_minus_2':'/gizlilik-politikasi-2/' in sb}
        sv=result['verification']['page_sitemap']
        if sv['http']!=200 or sv['waf'] or sv['legacy_alias'] or sv['privacy'] or sv['privacy_minus_2']:raise RuntimeError(f'noindex/draft URLs remain in page sitemap: {sv}')
        result['status']='success'
    except Exception as e:
        result['status']='failed-rollback-attempted'; result['error']=f'{type(e).__name__}: {e}'
        for pid in reversed(PIDS):
            if pid not in pages:continue
            try:c,b=restore_page(pages[pid]); result['rollback'].append({'page':pid,'http':c,'ok':c in (200,201)})
            except Exception as x:result['rollback'].append({'page':pid,'ok':False,'error':repr(x)})
        try:c,b=api('POST','/rankmath/v1/updateMeta',payload={'objectType':'post','objectID':14,'meta':{'rank_math_canonical_url':BASE+'/blog/'}}); result['rollback'].append({'blog_canonical':c})
        except Exception as x:result['rollback'].append({'blog_canonical_error':repr(x)})
        for s in deleted:
            try:b=recreate_menu(s); result['rollback'].append({'menu_recreated_from':s.get('id'),'new_id':b.get('id'),'ok':True})
            except Exception as x:result['rollback'].append({'menu_recreated_from':s.get('id'),'ok':False,'error':repr(x)})
    finally:
        if plugin:
            try:
                if plugin_created:
                    api('POST',plugin_route(plugin),payload={'status':'inactive'}); c,b=api('DELETE',plugin_route(plugin),{'force':'true'}); result['cache'].append({'temp_cleanup_http':c,'deleted':b.get('deleted') if isinstance(b,dict) else None})
                elif plugin_initial!='active':c,b=api('POST',plugin_route(plugin),payload={'status':'inactive'}); result['cache'].append({'restore_inactive_http':c})
                else:result['cache'].append({'left_active_as_found':True})
            except Exception as x:result['cache'].append({'restore_error':repr(x)})
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status')!='success':raise SystemExit(1)

if __name__=='__main__':main()
