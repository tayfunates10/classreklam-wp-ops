#!/usr/bin/env python3
import base64,json,os,re,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def build(route,params=None):
    q={'rest_route':route}
    if params: q.update(params)
    return BASE+'/?'+urllib.parse.urlencode(q)

def one(method,route,params=None,payload=None):
    data=None
    headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode(); headers['Content-Type']='application/json; charset=utf-8'
    req=urllib.request.Request(build(route,params),data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode(errors='replace')
            try: return r.status,json.loads(raw) if raw else {}
            except: return r.status,{'raw':raw[:1200]}
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try: body=json.loads(raw)
        except: body={'raw':raw[:1200]}
        return e.code,body

def request(method,route,params=None,payload=None):
    time.sleep(3)
    last=None
    for a in range(4):
        code,body=one(method,route,params,payload); last=(code,body)
        low=json.dumps(body,ensure_ascii=False).lower() if isinstance(body,(dict,list)) else str(body).lower()
        if code!=403 or 'imunify360' not in low: return code,body
        time.sleep(12*(a+1))
    return last

def ensure(code,body,label):
    if code not in (200,201): raise RuntimeError(f'{label}: HTTP {code} {body}')

def upsert_category(name,slug,description):
    code,arr=request('GET','/wp/v2/categories',{'slug':slug,'context':'edit','per_page':10}); ensure(code,arr,f'lookup category {slug}')
    if arr:
        cid=arr[0]['id']
        code,b=request('POST',f'/wp/v2/categories/{cid}',payload={'name':name,'description':description}); ensure(code,b,f'update category {slug}')
    else:
        code,b=request('POST','/wp/v2/categories',payload={'name':name,'slug':slug,'description':description}); ensure(code,b,f'create category {slug}'); cid=b['id']
    return cid

def noindex_term(cid):
    payload={'objectType':'term','objectID':int(cid),'meta':{'rank_math_robots':['noindex','follow']}}
    code,b=request('POST','/rankmath/v1/updateMeta',payload=payload); ensure(code,b,f'noindex category {cid}')

def choose(slug,title):
    s=(slug+' '+title).lower()
    if any(x in s for x in ['arac','araç']): return 'arac-giydirme-rehberi'
    if any(x in s for x in ['folyo','cam-kaplama','cam kaplama','vitrin','one-way','one way']): return 'folyo-cam-giydirme'
    if any(x in s for x in ['baski','baskı','branda','mesh','vinil']): return 'dijital-baski-rehberi'
    if any(x in s for x in ['tabela','totem','neon','led','yonlendirme','yönlendirme','cephe','kutu-harf','kutu harf']): return 'tabela-rehberi'
    return 'reklam-rehberi'

catspec={
 'tabela-rehberi':('Tabela Rehberi','Tabela türleri, üretim, montaj, kutu harf, totem ve cephe uygulamaları hakkında rehberler.'),
 'dijital-baski-rehberi':('Dijital Baskı Rehberi','Dijital baskı, branda, vinil ve dış mekân baskı uygulamaları hakkında içerikler.'),
 'arac-giydirme-rehberi':('Araç Giydirme Rehberi','Araç giydirme, araç kaplama ve ticari araç reklam uygulamaları hakkında içerikler.'),
 'folyo-cam-giydirme':('Folyo ve Cam Giydirme','Folyo kesim, vitrin, one way vision ve cam giydirme uygulamaları hakkında içerikler.'),
 'reklam-rehberi':('Reklam Rehberi','Tabela, reklam uygulamaları ve doğru malzeme seçimi hakkında genel rehberler.'),
}
ids={}
for slug,(name,desc) in catspec.items():
    cid=upsert_category(name,slug,desc); ids[slug]=cid; noindex_term(cid)
code,posts=request('GET','/wp/v2/posts',{'context':'edit','per_page':100,'_fields':'id,slug,title,categories,status'}); ensure(code,posts,'list posts')
updated=[]
for p in posts:
    title=p.get('title',{}).get('raw') or p.get('title',{}).get('rendered','')
    bucket=choose(p.get('slug',''),title); cid=ids[bucket]
    if p.get('categories') != [cid]:
        code,b=request('POST',f"/wp/v2/posts/{p['id']}",payload={'categories':[cid]}); ensure(code,b,f"assign post {p['id']}")
        updated.append({'id':p['id'],'slug':p.get('slug'),'category':bucket})
# Make a meaningful category the WordPress default, then remove old Uncategorized if empty.
code,b=request('POST','/wp/v2/settings',payload={'default_category':ids['reklam-rehberi']}); ensure(code,b,'set default category')
code,uncat=request('GET','/wp/v2/categories/1',{'context':'edit'}); ensure(code,uncat,'read Uncategorized')
deleted=False
if int(uncat.get('count',0))==0:
    code,b=request('DELETE','/wp/v2/categories/1',{'force':'true'}); ensure(code,b,'delete Uncategorized'); deleted=True
print(json.dumps({'status':'success','categories':ids,'posts_total':len(posts),'posts_updated':len(updated),'assignments':updated,'uncategorized_deleted':deleted},ensure_ascii=False,indent=2))
