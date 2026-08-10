#!/usr/bin/env python3
import json,os,re,subprocess,urllib.parse
from html.parser import HTMLParser
BASE=os.environ['WP_URL'].rstrip('/')
TARGET={'/edremit-tabela/','/totem-tabela/','/dijital-baski/','/arac-giydirme/','/cam-giydirme/','/kutu-harf-tabela/'}
class P(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.cur=None
    def handle_starttag(self,t,a):
        if t=='a':self.cur={'href':dict(a).get('href',''),'text':''}
    def handle_data(self,d):
        if self.cur is not None:self.cur['text']+=d
    def handle_endtag(self,t):
        if t=='a' and self.cur is not None:
            self.cur['text']=' '.join(self.cur['text'].split());self.links.append(self.cur);self.cur=None
def path(u):
    try:p=urllib.parse.urlparse(u).path
    except:p=u
    return ('/'+p.lstrip('/')).rstrip('/')+'/'
def reg(h,t):
    m=re.search(rf'<{t}\b[^>]*>.*?</{t}>',h,re.I|re.S);return m.group(0) if m else ''
cp=subprocess.run(['curl','-sS','-L','--compressed','--max-time','40','-A','Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/138 Safari/537.36',BASE+'/'],capture_output=True,text=True)
h=cp.stdout
out={'curl_exit':cp.returncode,'html_chars':len(h),'waf':'One moment, please' in h or 'Imunify360' in h}
for t in ['header','footer']:
    p=P();p.feed(reg(h,t));hits=[{'text':x['text'],'href':x['href'],'path':path(x['href'])} for x in p.links if path(x['href']) in TARGET]
    out[t+'_found']=bool(reg(h,t));out[t+'_hits']=hits;out[t+'_count']=len(hits)
out['footer_paths']=sorted({x['path'] for x in out.get('footer_hits',[])})
out['success']=(not out['waf'] and out.get('header_count')==0 and out.get('footer_count')==6 and set(out['footer_paths'])==TARGET)
print(json.dumps(out,ensure_ascii=False,indent=2))
