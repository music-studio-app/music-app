"""Conservative MusicBrainz recording metadata importer; no lyrics.

Usage: python scripts/import_musicbrainz.py --limit 100
MusicBrainz recordings are NOT assumed to be unique compositions: each recording
is retained separately unless it shares an exact MusicBrainz recording ID.
"""
import argparse
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'catalog' / 'turkce-sarkilar.json'
API = 'https://musicbrainz.org/ws/2/recording/'
USER_AGENT = 'MusicStudioCatalogImporter/1.0 (https://github.com/music-studio-app/music-app)'

def fetch(offset, count):
    # Turkish-language recordings; metadata quality and work identity require review.
    params = urllib.parse.urlencode({'query':'lang:tur', 'fmt':'json', 'limit':min(count, 100), 'offset':offset})
    req = urllib.request.Request(API + '?' + params, headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--offset',type=int,default=0)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or args.offset < 0:
        parser.error('limit 1..1000 and offset >= 0 required')
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(data.get('records'),list):
        raise ValueError('Invalid catalog records')
    seen = {r.get('id') for r in data['records'] if isinstance(r,dict)}
    added = 0
    for offset in range(args.offset, args.offset+args.limit, 100):
        result = fetch(offset, min(100,args.offset+args.limit-offset))
        for rec in result.get('recordings',[]):
            rid=rec.get('id')
            title=(rec.get('title') or '').strip()
            if not rid or not title: continue
            id_='mbrec_'+rid
            if id_ in seen: continue
            artists=[a.get('artist',{}).get('name','').strip() for a in rec.get('artist-credit',[]) if isinstance(a,dict)]
            artists=list(dict.fromkeys(a for a in artists if a))
            data['records'].append({'id':id_,'title':title,'singers':artists,'composer':'','lyricist':'','region':'','genre':'','source':'MusicBrainz recording '+rid,'metadataStatus':'Kayıt düzeyi; eser eşleştirmesi doğrulanmadı'})
            seen.add(id_)
            added+=1
        if offset+100 < args.offset+args.limit: time.sleep(1.2)
    CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Added {added} recording candidates. Total: {len(data["records"])}')
    print('WARNING: Recording candidates are NOT deduplicated works. Review before publishing.')

if __name__=='__main__':main()
