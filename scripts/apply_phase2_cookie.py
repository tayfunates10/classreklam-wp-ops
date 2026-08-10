#!/usr/bin/env python3
import json, os, re, urllib.error, urllib.parse, urllib.request

BASE=os.environ['WP_URL'].rstrip('/')
COOKIE=os.environ['WP_SESSION_COOKIE_HEADER']
NONCE=os.environ['WP_REST_NONCE']
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def request(method,path,payload=None):
    data=None
    headers={'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/','Cookie':COOKIE,'X-WP-Nonce':NONCE}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode('utf-8',errors='replace')
            try: return r.status,json.loads(raw) if raw else {}
            except Exception: return r.status,{'raw':raw[:1500]}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8',errors='replace')
        try: body=json.loads(raw)
        except Exception: body={'raw':raw[:1500]}
        return e.code,body

def ensure(code,body,label):
    if code not in (200,201): raise RuntimeError(f'{label}: HTTP {code} {body}')

def rank_meta(object_id,title,description,focus,canonical,object_type='post',extra=None):
    meta={'rank_math_title':title,'rank_math_description':description,'rank_math_focus_keyword':focus,'rank_math_canonical_url':canonical}
    if extra: meta.update(extra)
    code,body=request('POST','/wp-json/rankmath/v1/updateMeta',{'objectType':object_type,'objectID':int(object_id),'meta':meta})
    ensure(code,body,f'Rank Math meta {object_type}:{object_id}')

def get_post(post_id,kind='posts'):
    code,body=request('GET',f'/wp-json/wp/v2/{kind}/{post_id}?context=edit&_fields=id,slug,content,title,status,link')
    ensure(code,body,f'get {kind}/{post_id}')
    return body

def update_content(post_id,content,kind='posts'):
    code,body=request('POST',f'/wp-json/wp/v2/{kind}/{post_id}',{'content':content})
    ensure(code,body,f'update {kind}/{post_id}')

def append_internal_link(post_id,target_url,anchor):
    p=get_post(post_id)
    raw=p.get('content',{}).get('raw','')
    if target_url in raw: return 'already-linked'
    block=f'''\n<!-- wp:paragraph {{"className":"cr-seo-related-service"}} -->\n<p class="cr-seo-related-service">Bu konu için uygulama ve teklif detaylarını <a href="{target_url}">{anchor}</a> sayfamızda inceleyebilirsiniz.</p>\n<!-- /wp:paragraph -->\n'''
    update_content(post_id,raw+block)
    return 'linked'

def add_localbusiness_schema():
    page=get_post(6,'pages')
    raw=page.get('content',{}).get('raw','')
    marker='class-reklam-localbusiness-schema'
    if marker in raw: return 'already-present'
    schema={
      '@context':'https://schema.org','@type':'LocalBusiness','@id':BASE+'/#localbusiness',
      'name':'Class Reklam','alternateName':'Class Reklam & Tabela','url':BASE+'/',
      'telephone':'+905469364271',
      'address':{'@type':'PostalAddress','streetAddress':'Hamidiye Mh. Mithatpaşa Cd. No:18/C','postalCode':'10300','addressLocality':'Edremit','addressRegion':'Balıkesir','addressCountry':'TR'},
      'areaServed':[{'@type':'City','name':'Edremit'},{'@type':'AdministrativeArea','name':'Balıkesir'}],
      'description':'Edremit ve Balıkesir çevresinde tabela, kutu harf, totem, dijital baskı, araç giydirme ve folyo uygulamaları sunan reklam işletmesi.'
    }
    script='\n<!-- '+marker+' -->\n<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False,separators=(',',':'))+'</script>\n'
    update_content(6,raw+script,'pages')
    return 'added'

def main():
    results={'meta':[],'links':[]}
    metas=[
      (801,"Edremit’te Tabela Yaptırmak: Öneriler | Class Reklam","Edremit’te tabela yaptırırken malzeme, görünürlük, ölçü ve montajda dikkat edilmesi gerekenleri öğrenin. Class Reklam’dan teklif alın.",'edremit tabela',BASE+'/edremitte-tabela-yaptirmak-isteyenlere-oneriler/'),
      (18,'Class Reklam İletişim | Edremit Tabela ve Reklam','Edremit’te tabela, reklam, dijital baskı, araç giydirme ve folyo uygulamaları için Class Reklam’a ulaşın. Telefon: 0546 936 42 71.','class reklam iletişim',BASE+'/iletisim/'),
      (10,'Edremit Tabela ve Reklam Hizmetleri | Class Reklam','Edremit tabela, totem, kutu harf, dijital baskı, araç giydirme ve cam folyo hizmetlerini inceleyin. Class Reklam’dan teklif alın.','edremit reklam tabela',BASE+'/hizmetlerimiz/'),
      (8,'Class Reklam Hakkımızda | Edremit Reklam ve Tabela','Class Reklam’ın Edremit’te tabela, reklam, baskı ve uygulama hizmetlerine yaklaşımını ve çalışma alanlarını keşfedin.','class reklam edremit',BASE+'/hakkimizda/'),
      (12,'Class Reklam Galeri | Edremit Tabela Uygulamaları','Edremit ve çevresinde Class Reklam tarafından gerçekleştirilen tabela, kutu harf, totem, araç giydirme ve reklam uygulamalarını inceleyin.','edremit tabela uygulamaları',BASE+'/galeri/'),
      (14,'Tabela ve Reklam Rehberi | Class Reklam Edremit','Tabela, kutu harf, folyo, araç giydirme, dijital baskı ve dış mekân reklamları hakkında Class Reklam rehber içerikleri.','edremit tabela blog',BASE+'/blog/'),
    ]
    for m in metas:
        rank_meta(*m); results['meta'].append(m[0])
    # Default Uncategorized archive: keep crawlable links but remove thin archive from index.
    code,body=request('POST','/wp-json/rankmath/v1/updateMeta',{'objectType':'term','objectID':1,'meta':{'rank_math_robots':['noindex','follow']}})
    ensure(code,body,'noindex category 1'); results['category_noindex']=True
    links=[
      (801,BASE+'/edremit-tabela/','Edremit tabela'),
      (805,BASE+'/arac-giydirme/','Edremit araç giydirme'),
      (777,BASE+'/totem-tabela/','Edremit totem tabela'),
      (771,BASE+'/kutu-harf-tabela/','Edremit kutu harf tabela'),
      (774,BASE+'/dijital-baski/','Edremit dijital baskı'),
      (783,BASE+'/cam-giydirme/','Edremit cam giydirme ve folyo'),
      (780,BASE+'/cam-giydirme/','Edremit folyo ve cam giydirme'),
    ]
    for post_id,url,anchor in links:
        results['links'].append({'post':post_id,'status':append_internal_link(post_id,url,anchor)})
    results['localbusiness_schema']=add_localbusiness_schema()
    print(json.dumps({'status':'success','results':results},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
