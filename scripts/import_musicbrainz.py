
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Turkce muzik katalog adaylarini MusicBrainz'den toplar.
Sarki sozlerini indirmez.
Mevcut uygulama katalog dosyasini degistirmez.
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://musicbrainz.org/ws/2/recording/"
USER_AGENT = (
    "MusicStudioCatalogImporter/1.1 "
    "(https://github.com/music-studio-app/music-app)"
)

ARTISTS = [
    "Neşet Ertaş",
    "Müslüm Gürses",
    "Sezen Aksu",
    "Orhan Gencebay",
    "Ferdi Tayfur",
    "İbrahim Tatlıses",
    "Arif Sağ",
    "Musa Eroğlu",
    "Zara",
    "Cem Karaca",
    "Barış Manço",
    "Ajda Pekkan",
    "Zeki Müren",
    "Bülent Ersoy",
    "Selda Bağcan",
    "Mahzuni Şerif",
    "Yıldız Tilbe",
    "Sibel Can",
    "Ebru Gündeş",
    "Tarkan",
    "Kenan Doğulu",
    "Sertab Erener",
    "Teoman",
    "Haluk Levent",
    "Cengiz Kurtoğlu",
    "Hakan Altun",
    "Gökhan Türkmen",
    "Mustafa Ceceli",
    "Koray Avcı",
    "Ankaralı Namık",
    "Ankaralı Turgut",
    "Oğuz Yılmaz",
    "Hüseyin Kağıtçı",
]

def normalize(value):
    return " ".join(str(value or "").casefold().split())


def fetch_recordings(artist, limit=100):
    query = 'artist:"' + artist.replace('"', "") + '"'
    params = urllib.parse.urlencode({
        "query": query,
        "fmt": "json",
        "limit": min(limit, 100),
    })

    request = urllib.request.Request(
        API_URL + "?" + params,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response).get("recordings", [])


def verified_artist(recording, artist):
    credits = recording.get("artist-credit", [])

    for credit in credits:
        if not isinstance(credit, dict):
            continue

        artist_data = credit.get("artist") or {}
        names = [
            artist_data.get("name", ""),
            artist_data.get("sort-name", ""),
            credit.get("name", ""),
        ]

        if normalize(artist) in [normalize(name) for name in names]:
            return True

    return False


def collect(max_records):
    results = []
    seen = set()

    for artist in ARTISTS:
        if len(results) >= max_records:
            break

        print("Araniyor:", artist, flush=True)

        try:
            recordings = fetch_recordings(artist)
        except Exception as error:
            print("Arama hatasi:", artist, error, flush=True)
            time.sleep(1.2)
            continue

        for recording in recordings:
            if len(results) >= max_records:
                break

            if not verified_artist(recording, artist):
                continue

            title = str(recording.get("title") or "").strip()
            mbid = str(recording.get("id") or "").strip()

            if not title or not mbid or mbid in seen:
                continue

            seen.add(mbid)

            results.append({
                "id": "mbrec_" + mbid,
                "title": title,
                "artist": artist,
                "singers": [artist],
                "musicbrainz_recording_id": mbid,
                "genre": "",
                "region": "",
                "composer": "",
                "lyricist": "",
                "lyrics": "",
                "metadataStatus": "Dogrulanmamis katalog adayi",
                "source": "MusicBrainz",
            })

        print(
            "Toplam aday:",
            len(results),
            flush=True,
        )

        time.sleep(1.2)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Toplanacak en fazla kayit sayisi",
    )
    parser.add_argument(
        "--output",
        default="catalog/katalog-adaylari.json",
        help="Cikti JSON dosyasi",
    )
parser.add_argument(
    "--offset",
    type=int,
    default=0,
    help="Baslangic konumu",
)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit en az 1 olmali")

    records = collect(args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "version": 1,
        "description": (
            "MusicBrainz Turk sanatci kayit adaylari. "
            "Eser ve dil dogrulamasi yapilmamistir. "
            "Sarki sozleri icermez."
        ),
        "generatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "count": len(records),
        "records": records,
    }

    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Tamamlandi:", output_path)
    print("Kayit sayisi:", len(records))


if __name__ == "__main__":
    main()
