"""MusicBrainz Turkish-artist recording candidate collector (NOT a lyrics importer).

The old `lang:tur` query matched titles containing 'tur', including foreign tracks.
This version queries known Turkish performers by exact artist name and verifies
artist credit before retaining each recording. Results are *candidates*, not
verified Turkish-language works, and are never auto-published.
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
USER_AGENT = 'MusicStudioCatalogImporter/1.1 (https://github.com/music-studio-app/music-app)'
ARTISTS = [
    'Neşet Ertaş', 'Musa Eroğlu', 'Arif Sağ', 'Orhan Gencebay',
    'Ferdi Tayfur', 'Müslüm Gürses', 'İbrahim Tatlıses', 'Sezen Aksu',
    'Barış Manço', 'Cem Karaca', 'Ajda Pekkan', 'Zeki Müren',
    'Bülent Ersoy', 'Selda Bağcan', 'Mahzuni Şerif', 'Yıldız Tilbe',
    'Sibel Can', 'Ebru Gündeş', 'Tarkan', 'Kenan Doğulu',
    'Sertab Erener', 'Teoman', 'Haluk Levent', 'Cengiz Kurtoğlu',
    'Hakan Altun', 'Gülşen', 'Mustafa Ceceli', 'Koray Avcı',
    'Ankaralı Namık', 'Ankaralı Turgut', 'Oğuz Yılmaz', 'Hüseyin Kağıt',
]

def fetch(artist, offset, count):
    escaped = artist.replace('\\', '\\\\').replace('"', '\\"')
    params = urllib.parse.urlencode({'query': f'artist:"{escaped}"', 'fmt': 'json', 'limit': count, 'offset': offset})
    req = urllib.request.Request(API + '?' + params, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0, help='Per-artist search offset')
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or args.offset < 0:
        parser.error('limit must be 1..1000 and offset >= 0')
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(data.get('records'), list):
        raise ValueError('Invalid catalog records')
    seen = {r.get('id') for r in data['records'] if isinstance(r, dict)}
    added = 0
    for artist in ARTISTS:
        if added >= args.limit:
            break
        page_offset = args.offset
        for _ in range(3):  # Bounded pages per performer to avoid excessive API use
            if added >= args.limit:
                break
            result = fetch(artist, page_offset, min(100, args.limit - added))
            recordings = result.get('recordings', [])
            for rec in recordings:
                rid, title = rec.get('id'), (rec.get('title') or '').strip()
                credits = [a.get('artist', {}).get('name', '').strip() for a in rec.get('artist-credit', []) if isinstance(a, dict)]
                if not rid or not title or artist.casefold() not in {a.casefold() for a in credits}:
                    continue
                record_id = 'mbrec_' + rid
                if record_id in seen:
                    continue
                data['records'].append({
                    'id': record_id, 'title': title,
                    'singers': list(dict.fromkeys(a for a in credits if a)),
                    'composer': '', 'lyricist': '', 'region': '', 'genre': '',
                    'source': 'MusicBrainz recording ' + rid,
                    'metadataStatus': 'Türk sanatçı kaydı adayı; dil ve eser eşleştirmesi doğrulanmadı',
                })
                seen.add(record_id)
                added += 1
                if added >= args.limit:
                    break
            page_offset += len(recordings)
            time.sleep(1.2)
            if not recordings or len(recordings) < min(100, args.limit - (added - len(recordings))):
                break
    CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Collected {added} artist-matched recording candidates. Total: {len(data["records"])}')
    print('REVIEW REQUIRED: Turkish artist does not guarantee Turkish lyrics or unique work identity.')

if __name__ == '__main__':
    main()
