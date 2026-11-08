"""
Erzeugt die Container-Datei für die App "Glaskontainer".

Fragt einmal (wöchentlich) alle Altglas-Container in Deutschland bei OpenStreetMap (Overpass) ab und
schreibt sie in Kacheln von 1 × 1 Grad:  cells/<breite>_<länge>.json  (z. B. cells/53_9.json)
Jede Kachel: {"v":1, "t":"<Stand>", "c":[[id, lat, lon, titel, [details...]], ...]}
Dazu meta.json mit Stand, Anzahl und Liste der Kacheln.

Daten © OpenStreetMap-Mitwirkende, Lizenz ODbL 1.0.
Aufruf:  python tools/build_data.py <ausgabeordner>
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = "Glaskontainer-App-Datenbau/1.0 (privat)"
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
QUERY = """[out:json][timeout:600];
area["ISO3166-1"="DE"][admin_level=2]->.de;
(
  nwr["amenity"="recycling"]["recycling:glass_bottles"="yes"](area.de);
  nwr["amenity"="recycling"]["recycling:glass"="yes"](area.de);
);
out center tags;"""


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    last = None
    for attempt in range(4):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=700) as r:
                    result = json.load(r)
                if len(result.get("elements", [])) < 10000:
                    raise RuntimeError(f"zu wenige Container ({len(result.get('elements', []))}) – Abfrage unvollständig?")
                return result
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"{url}: {e}", file=sys.stderr)
        time.sleep(60 * (attempt + 1))
    raise SystemExit(f"Overpass nicht erreichbar: {last}")


# Gleiche Regeln wie OverpassClient.kt in der App
def title(tags):
    if "name" in tags:
        return tags["name"]
    return "Wertstoffhof" if tags.get("recycling_type") == "centre" else "Glascontainer"


def details(tags):
    out = []
    if "opening_hours" in tags:
        out.append("Einwurfzeiten: " + tags["opening_hours"])
    if "operator" in tags:
        out.append("Betreiber: " + tags["operator"])
    if tags.get("recycling:clothes") == "yes" or tags.get("recycling:shoes") == "yes":
        out.append("Auch Altkleider")
    if tags.get("recycling:paper") == "yes":
        out.append("Auch Papier")
    if "description" in tags:
        out.append(tags["description"])
    return out


def main(out_dir):
    result = fetch()
    stand = result.get("osm3s", {}).get("timestamp_osm_base") or datetime.now(timezone.utc).isoformat()
    cells = {}
    for el in result["elements"]:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        row = [f"osm-{el['type']}-{el['id']}", round(lat, 6), round(lon, 6), title(tags), details(tags)]
        key = f"{math.floor(lat)}_{math.floor(lon)}"
        cells.setdefault(key, []).append(row)

    cell_dir = os.path.join(out_dir, "cells")
    os.makedirs(cell_dir, exist_ok=True)
    for name in os.listdir(cell_dir):  # alte Kacheln entfernen
        os.remove(os.path.join(cell_dir, name))
    total = 0
    for key, rows in sorted(cells.items()):
        rows.sort(key=lambda r: r[0])
        total += len(rows)
        with open(os.path.join(cell_dir, key + ".json"), "w", encoding="utf-8") as f:
            json.dump({"v": 1, "t": stand, "c": rows}, f, ensure_ascii=False, separators=(",", ":"))
    meta = {
        "v": 1,
        "stand": stand,
        "anzahl": total,
        "kacheln": sorted(cells.keys()),
        "lizenz": "Daten © OpenStreetMap-Mitwirkende, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"{total} Container in {len(cells)} Kacheln, Stand {stand}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
