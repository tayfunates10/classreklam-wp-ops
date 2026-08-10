#!/usr/bin/env python3
import base64,json,os,re,time,urllib.error,urllib.parse,urllib.request
BASE=os.environ['WP_URL'].rstrip('/')
AUTH='Basic '+base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

def url(path):
    p=urllib.parse.urlsplit(path); route=p.path
    if route.startswith('/wp-json'): route=route[len('/wp-json'):]
    u=BASE+'/?rest_route='+urllib.parse.quote(route,safe='/')
    if p.query: u+='&'+p.query
    return u

def get(path):
    time.sleep(3)
    req=urllib.request.Request(url(path),headers={'Authorization':AUTH,'Accept':'application/json','User-Agent':UA,'Referer':BASE+'/wp-admin/'})
    with urllib.request.urlopen(req,timeout=45) as r:
        return json.loads(r.read().decode('utf-8',errors='replace'))

def tags(content,tag):
    return [re.sub(r'<[^>]+>','',x).strip() for x in re.findall(rf'<{tag}[^>]*>(.*?)</{tag}>',content,re.I|re.S)]

out={}
home=get('/wp-json/wp/v2/pages/6?context=edit&_fields=id,slug,status,content,modified')
hraw=home.get('content',{}).get('raw','')
out['home']={'modified':home.get('modified'),'h1':tags(hraw,'h1'),'has_localbusiness_marker':'class-reklam-localbusiness-schema' in hraw,'service_links':{s:(f'/{slug}/' in hraw) for s,slug in {'Tabela':'edremit-tabela','Totem':'totem-tabela','Dijital Baskı':'dijital-baski','Araç Giydirme':'arac-giydirme','Cam Giydirme':'cam-giydirme','Kutu Harf':'kutu-harf-tabela'}.items()}}
contact=get('/wp-json/wp/v2/pages/18?context=edit&_fields=id,slug,status,content,title,modified')
craw=contact.get('content',{}).get('raw','')
out['contact']={'title':contact.get('title',{}).get('raw'),'h1':tags(craw,'h1'),'h2':tags(craw,'h2')[:10],'modified':contact.get('modified')}
slugs=['edremit-tabela','totem-tabela','dijital-baski','arac-giydirme','cam-giydirme','kutu-harf-tabela']
out['services']=[]
for slug in slugs:
    arr=get('/wp-json/wp/v2/pages?context=edit&slug='+urllib.parse.quote(slug)+'&_fields=id,slug,status,link,title,content,modified')
    if arr:
        p=arr[0]; raw=p.get('content',{}).get('raw','')
        out['services'].append({'id':p.get('id'),'slug':slug,'status':p.get('status'),'link':p.get('link'),'title':p.get('title',{}).get('raw'),'h1':tags(raw,'h1'),'h2':tags(raw,'h2')[:8],'content_chars':len(raw),'modified':p.get('modified')})
    else:
        out['services'].append({'slug':slug,'missing':True})
post801=get('/wp-json/wp/v2/posts/801?context=edit&_fields=id,slug,content,modified')
praw=post801.get('content',{}).get('raw','')
out['post801']={'modified':post801.get('modified'),'links_to_edremit_tabela':BASE+'/edremit-tabela/' in praw}
cat=get('/wp-json/wp/v2/categories/1?context=edit&_fields=id,name,slug,count,link')
out['category1']=cat
print(json.dumps(out,ensure_ascii=False,indent=2))
