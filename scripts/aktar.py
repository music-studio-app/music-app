"""Vikikaynak yöresel türkü arşivi: küçük partilerle, kaldığı yerden aktarım."""
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from html import unescape

API = 'https://tr.wikisource.org/w/api.php'
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalog' / 'sarki-sozleri.json'
REPORT = ROOT / 'catalog' / 'aktarim-raporu.json'
BATCH_SIZE = max(1, min(int(os.getenv('BATCH_SIZE', '30')), 100))
TIMEOUT = 12
HEADERS = {'User-Agent': 'MusicRepertuvarArchiveImporter/2.0 (GitHub Actions; contact via repository)', 'Accept': 'application/json'}

class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
                self.skip += 1
            return
        cl = dict(attrs).get('class', '')
        if tag in ('script', 'style', 'table', 'sup') or any(k in cl for k in ('mw-editsection', 'navbox', 'metadata', 'reference', 'printfooter', 'catlinks')):
            self.skip = 1
            return
        if tag in ('p', 'div', 'br', 'li', 'h2', 'h3'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
        elif tag in ('p', 'div', 'li'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
    def text(self):
        s = unescape(''.join(self.parts))
        s = re.sub(r'[ \t]+', ' ', s)
        return re.sub(r'\n[ \t]*\n[ \t]*\n+', '\n\n', s).strip()

def api(**params):
    params.update(format='json', formatversion=2)
    url = API + '?' + urllib.parse.urlencode(params)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT) as response:
                result = json.load(response)
            if 'error' in result:
                raise RuntimeError(str(result['error']))
            return result
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 1:
                raise
            print(f'  Bağlantı denemesi başarısız: {exc}; tekrar deneniyor', flush=True)
            time.sleep(1.5)

def members(category):
    token = None
    while True:
        args = dict(action='query', list='categorymembers', cmtitle=category, cmlimit='max')
        if token:
            args['cmcontinue'] = token
        data = api(**args)
        yield from data.get('query', {}).get('categorymembers', [])
        token = data.get('continue', {}).get('cmcontinue')
        if not token:
            return

def load_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding='utf-8'))

def atomic_write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def discover():
    print('Yöre kategorileri bulunuyor...', flush=True)
    regions = [x['title'] for x in members('Kategori:Yörelere göre türküler') if x.get('ns') == 14]
    titles = {}
    for i, cat in enumerate(regions, 1):
        region = re.sub(r' türküler(i)?$', '', cat.removeprefix('Kategori:'), flags=re.I).strip()
        try:
            for item in members(cat):
                if item.get('ns') == 0:
                    titles.setdefault(item['title'], set()).add(region)
        except Exception as exc:
            print(f'Kategori atlandı: {cat}: {exc}', flush=True)
        print(f'Kategori {i}/{len(regions)}: {cat}', flush=True)
    return [{'title': title, 'regions': sorted(rs)} for title, rs in sorted(titles.items())]

def main():
    catalog = load_json(OUT, {'version': 1, 'records': []})
    records = catalog.get('records', [])
    if not isinstance(records, list):
        raise ValueError('Katalog records alanı liste değil; güvenli durduruldu.')
    by_title = {r['title']: r for r in records if isinstance(r, dict) and r.get('title')}
    report = load_json(REPORT, {})
    titles = report.get('titles')
    if not isinstance(titles, list) or not titles:
        titles = discover()
        if not titles:
            raise RuntimeError('Türkü listesi boş; mevcut arşiv korunuyor.')
        report['titles'] = titles
        report['cursor'] = 0
        report['failures'] = {}
    cursor = int(report.get('cursor', 0))
    if cursor >= len(titles):
        print('Tüm kayıtlar daha önce tarandı. Yeni tarama için rapor dosyasındaki cursor sıfırlanabilir.', flush=True)
        return
    end = min(cursor + BATCH_SIZE, len(titles))
    failures = report.get('failures', {})
    if not isinstance(failures, dict):
        failures = {}
    for index in range(cursor, end):
        item = titles[index]
        title = item['title']
        old = by_title.get(title)
        if old and str(old.get('lyrics', '')).strip():
            print(f'[{index+1}/{len(titles)}] Zaten kayıtlı: {title}', flush=True)
            continue
        try:
            parsed = api(action='parse', page=title, prop='text|revid').get('parse', {})
            raw = parsed.get('text', '')
            if isinstance(raw, dict):
                raw = raw.get('*', '')
            if not raw:
                raise ValueError('Sayfa metni boş')
            extractor = Extract()
            extractor.feed(raw)
            lyrics = extractor.text()
            if not 35 <= len(lyrics) <= 18000:
                raise ValueError(f'Şüpheli uzunluk: {len(lyrics)}')
            by_title[title] = {
                'title': title, 'lyrics': lyrics, 'publishingAuthorized': False,
                'source': 'Vikikaynak',
                'sourceUrl': 'https://tr.wikisource.org/wiki/' + urllib.parse.quote(title.replace(' ', '_')),
                'regions': item.get('regions', []), 'reviewRequired': True,
                'license': 'Kaynak sayfası ve yayınlama izni kontrol edilmeli'
            }
            failures.pop(title, None)
            print(f'[{index+1}/{len(titles)}] Alındı: {title}', flush=True)
        except Exception as exc:
            failures[title] = str(exc)
            print(f'[{index+1}/{len(titles)}] Hata: {title}: {exc}', flush=True)
        time.sleep(0.15)
    catalog['version'] = catalog.get('version', 1)
    catalog.setdefault('description', 'Kaynak metinler; inceleme sonrası publishingAuthorized=true yapılır.')
    catalog['records'] = sorted(by_title.values(), key=lambda r: r.get('title', '').casefold())
    report.update({'cursor': end, 'total': len(titles), 'imported': sum(bool(str(r.get('lyrics', '')).strip()) for r in by_title.values()), 'failures': failures, 'complete': end == len(titles)})
    atomic_write(OUT, catalog)
    atomic_write(REPORT, report)
    print(f'KAYDEDİLDİ: {end}/{len(titles)} tarandı, {report["imported"]} söz kayıtlı, {len(failures)} hata. Sonraki çalıştırmada devam.', flush=True)

if __name__ == '__main__':
    main()
