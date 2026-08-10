#!/usr/bin/env python3
import base64,json,os,re,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def build(route,params=None):
    q={'rest_route':route}
    if params:q.update(params)
    return BASE+'/?'+urllib.parse.urlencode(q)

def one(method,route,params=None,payload=None):
    data=None; headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(build(route,params),data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode(errors='replace')
            try:return r.status,json.loads(raw) if raw else {}
            except:return r.status,{'raw':raw[:1000]}
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try:body=json.loads(raw)
        except:body={'raw':raw[:1000]}
        return e.code,body

def req(method,route,params=None,payload=None):
    time.sleep(4)
    for a in range(4):
        code,b=one(method,route,params,payload)
        low=json.dumps(b,ensure_ascii=False).lower() if isinstance(b,(dict,list)) else str(b).lower()
        if code!=403 or 'imunify360' not in low:return code,b
        time.sleep(15*(a+1))
    return code,b

def ok(code,b,label):
    if code not in (200,201):raise RuntimeError(f'{label}: HTTP {code} {b}')

# Homepage: strengthen the GSC-visible "edremit reklam / reklamcı" intent naturally, without keyword stuffing.
code,home=req('GET','/wp/v2/pages/6',{'context':'edit','_fields':'id,content'});ok(code,home,'read homepage')
raw=home.get('content',{}).get('raw','')
old='Edremit’te tabela, totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
new='Edremit’te tabela ve reklam firması olarak; totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
home_changed=False
if new not in raw and old in raw:
    raw=raw.replace(old,new,1)
    code,b=req('POST','/wp/v2/pages/6',payload={'content':raw});ok(code,b,'update homepage GSC copy');home_changed=True
meta={'rank_math_title':'Edremit Tabela & Reklam Firması | Class Reklam','rank_math_description':'Edremit tabela ve reklam firması Class Reklam; totem, kutu harf, dijital baskı, araç ve cam giydirme çözümleri için keşif ve teklif sunar.','rank_math_focus_keyword':'edremit tabela','rank_math_canonical_url':BASE+'/'}
code,b=req('POST','/rankmath/v1/updateMeta',payload={'objectType':'post','objectID':6,'meta':meta});ok(code,b,'homepage Rank Math')

# Services hub: add direct crawlable links to the six dedicated commercial landing pages.
code,page=req('GET','/wp/v2/pages/10',{'context':'edit','_fields':'id,content'});ok(code,page,'read services page')
content=page.get('content',{}).get('raw','')
marker='cr-seo-service-hub-links'
service_changed=False
if marker not in content:
    block='''\n<!-- cr-seo-service-hub-links -->\n<!-- wp:heading -->\n<h2 class="wp-block-heading">Edremit Tabela ve Reklam Hizmetleri</h2>\n<!-- /wp:heading -->\n<!-- wp:paragraph -->\n<p>İhtiyacınıza göre <a href="/edremit-tabela/">Edremit tabela</a>, <a href="/totem-tabela/">totem tabela</a>, <a href="/dijital-baski/">dijital baskı</a>, <a href="/arac-giydirme/">araç giydirme</a>, <a href="/cam-giydirme/">cam giydirme ve folyo</a> ile <a href="/kutu-harf-tabela/">kutu harf tabela</a> hizmetlerimizin detaylarını inceleyebilirsiniz.</p>\n<!-- /wp:paragraph -->\n'''
    code,b=req('POST','/wp/v2/pages/10',payload={'content':content+block});ok(code,b,'update services hub links');service_changed=True
print(json.dumps({'status':'success','homepage_copy_changed':home_changed,'homepage_meta_updated':True,'services_hub_links_added':service_changed},ensure_ascii=False,indent=2))
