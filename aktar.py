import json, time, urllib.parse, urllib.request, re, pathlib, html
from html.parser import HTMLParser

API='https://tr.wikisource.org/w/api.php'
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'catalog'/'sarki-sozleri.json'
REGIONS=ROOT/'catalog'/'yoresel-turkuler.json'
HEADERS={'User-Agent':'MusicRepertuvarArchiveImporter/1.0 (GitHub Actions; Wikimedia API; contact via repository)'}

class Extract(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0;self.block=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs);cl=d.get('class','')
  if self.skip:self.skip+=1;return
  if tag in ('script','style','table','sup') or any(k in cl for k in ('mw-editsection','navbox','metadata','reference','printfooter','catlinks')):
   self.skip=1;return
  if tag in ('p','div','br','li','h2','h3'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if self.skip:self.skip-=1
  elif tag in ('p','div','li'):self.parts.append('\n')
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
 def text(self):
  s=html.unescape(''.join(self.parts));s=re.sub(r'[ \t]+',' ',s);s=re.sub(r'\n[ \t]*\n[ \t]*\n+','\n\n',s)
  return s.strip()

def api(**kw):
 kw.update(format='json',formatversion=2)
 url=API+'?'+urllib.parse.urlencode(kw)
 for i in range(4):
  try:
   req=urllib.request.Request(url,headers=HEADERS)
   with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
  except Exception as e:
   if i==3:raise
   time.sleep(2*(i+1))

def members(category):
 token=None
 while True:
  args=dict(action='query',list='categorymembers',cmtitle=category,cmlimit='max')
  if token:args['cmcontinue']=token
  data=api(**args)
  for item in data.get('query',{}).get('categorymembers',[]):yield item
  token=data.get('continue',{}).get('cmcontinue')
  if not token:break

def main():
 regions=[]
 for c in members('Kategori:Yörelere göre türküler'):
  if c.get('ns')==14:regions.append(c['title'])
 print('Yöre kategorileri:',len(regions))
 title_regions={}
 for cat in regions:
  region=re.sub(r' türküler(i)?$','',cat.removeprefix('Kategori:'),flags=re.I).strip()
  try:
   for item in members(cat):
    if item.get('ns')==0:title_regions.setdefault(item['title'],set()).add(region)
  except Exception as e:print('Kategori okunamadı:',cat,e)
 print('Benzersiz eser:',len(title_regions))
 OUT.parent.mkdir(parents=True,exist_ok=True)
 existing={}
 if OUT.exists():
  try:
   for item in json.loads(OUT.read_text(encoding='utf-8')).get('records',[]):
    if item.get('title'):existing[item['title']]=item
  except Exception:pass
 records=[];missing=[]
 for i,(title,regionset) in enumerate(sorted(title_regions.items())):
  old=existing.get(title)
  if old and old.get('lyrics','').strip():records.append(old);continue
  try:
   data=api(action='parse',page=title,prop='text|revid')
   parsed=data.get('parse',{})
   raw=parsed.get('text','')
   if not raw:raise ValueError('Sayfa metni boş')
   extractor=Extract();extractor.feed(raw)
   lyrics=extractor.text()
   # Çok kısa sayfaları veya aşırı uzun sayfa içeriklerini otomatik onaylama.
   if len(lyrics)<35 or len(lyrics)>18000:raise ValueError('Şüpheli uzunluk: '+str(len(lyrics)))
   records.append({'title':title,'lyrics':lyrics,'publishingAuthorized':False,
     'source':'Vikikaynak','sourceUrl':'https://tr.wikisource.org/wiki/'+urllib.parse.quote(title.replace(' ','_')),
     'regions':sorted(regionset),'reviewRequired':True,
     'license':'Kaynak sayfası ve yayınlama izni kontrol edilmeli'})
  except Exception as e:missing.append({'title':title,'error':str(e)})
  if (i+1)%25==0:print(f'{i+1}/{len(title_regions)} sayfa işlendi')
  time.sleep(.12)
 OUT.write_text(json.dumps({'version':1,'description':'Kaynak metinler; gözden geçirilmeden uygulamada yayımlanmaz. İnceleme sonrası publishingAuthorized=true yapın.','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT.parent/'aktarim-raporu.json').write_text(json.dumps({'total':len(title_regions),'imported':len(records),'failed':missing},ensure_ascii=False,indent=2),encoding='utf-8')
 print('Aktarım tamamlandı:',len(records),'başarılı,',len(missing),'hatalı. İçerik kontrolü bekliyor.')

if __name__=='__main__':main()
