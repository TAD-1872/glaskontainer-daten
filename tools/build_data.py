"""
Erzeugt die Container-Datei für die App "Glaskontainer".

Fragt einmal (wöchentlich) alle Altglas-Container in Deutschland bei OpenStreetMap (Overpass) ab und
schreibt sie in Kacheln von 1 × 1 Grad:  cells/<breite>_<länge>.json  (z. B. cells/53_9.json)
Jede Kachel: {"v":1, "t":"<Stand>", "c":[[id, lat, lon, titel, [details...]], ...]}
Zusätzlich amtliche Listen (tools/amtlich.py): Zeilen mit 6. Feld = Quellen-Schlüssel, nur Standorte,
die nicht schon (≤ 60 m) in OpenStreetMap sind. Dazu meta.json mit Stand, Anzahl, Kacheln und Quellen.

Daten © OpenStreetMap-Mitwirkende, Lizenz ODbL 1.0; amtliche Daten siehe meta.json "quellen".
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amtlich  # noqa: E402

GLEICH_M = 60  # amtlicher Eintrag so nah an einem OSM-Container = derselbe Standort

UA = "Glaskontainer-App-Datenbau/1.0 (privat)"
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
QUERY = """[out:json][timeout:600];
area["ISO3166-1"="DE"][admin_level=2]->.de;
(
  nwr["amenity"="recycling"]["recycling:glass_bottles"="yes"](area.de);
  nwr["amenity"="recycling"]["recycling:glass"="yes"](area.de);
);
out center tags;"""

# Weitere Ebenen (Filter in der App): Wertstoffhöfe und Deponien aus OpenStreetMap
QUERY_HOEFE = """[out:json][timeout:600];
area["ISO3166-1"="DE"][admin_level=2]->.de;
nwr["amenity"="recycling"]["recycling_type"="centre"](area.de);
out center tags;"""
QUERY_DEPONIEN = """[out:json][timeout:600];
area["ISO3166-1"="DE"][admin_level=2]->.de;
nwr["landuse"="landfill"]["disused"!="yes"]["abandoned"!="yes"]["landfill:status"!="closed"](area.de);
out center tags;"""


def fetch(query=QUERY, mindestens=10000):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(4):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=700) as r:
                    result = json.load(r)
                if len(result.get("elements", [])) < mindestens:
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


MATERIAL = [
    ("glass_bottles", "Altglas"), ("paper", "Papier"), ("clothes", "Altkleider"),
    ("electrical_appliances", "Elektrogeräte"), ("batteries", "Batterien"), ("green_waste", "Grünschnitt"),
    ("wood", "Holz"), ("scrap_metal", "Schrott"), ("hazardous_waste", "Sondermüll"), ("rubble", "Bauschutt"),
]


def hof_details(tags):
    out = []
    if "opening_hours" in tags:
        out.append("Öffnungszeiten: " + tags["opening_hours"])
    if "operator" in tags:
        out.append("Betreiber: " + tags["operator"])
    angenommen = [name for key, name in MATERIAL if tags.get("recycling:" + key) == "yes"
                  or (key == "glass_bottles" and tags.get("recycling:glass") == "yes")]
    if angenommen:
        out.append("Nimmt an: " + ", ".join(angenommen))
    if "addr:street" in tags:
        out.append(f"{tags['addr:street']} {tags.get('addr:housenumber', '')}".strip()
                   + (f", {tags['addr:city']}" if "addr:city" in tags else ""))
    return out


def deponie_details(tags):
    out = []
    if "operator" in tags:
        out.append("Betreiber: " + tags["operator"])
    if "opening_hours" in tags:
        out.append("Öffnungszeiten: " + tags["opening_hours"])
    if "description" in tags:
        out.append(tags["description"])
    return out


def ebene_schreiben(out_dir, ordner, result, titel, details_fn):
    """Schreibt eine Zusatz-Ebene (Wertstoffhöfe, Deponien) in <ordner>/<lat>_<lon>.json."""
    cells = {}
    for el in result["elements"]:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        row = [f"osm-{el['type']}-{el['id']}", round(lat, 6), round(lon, 6), tags.get("name") or titel, details_fn(tags)]
        cells.setdefault(f"{math.floor(lat)}_{math.floor(lon)}", []).append(row)
    pfad = os.path.join(out_dir, ordner)
    os.makedirs(pfad, exist_ok=True)
    for name in os.listdir(pfad):
        os.remove(os.path.join(pfad, name))
    for key, rows in cells.items():
        rows.sort(key=lambda r: r[0])
        with open(os.path.join(pfad, key + ".json"), "w", encoding="utf-8") as f:
            json.dump({"v": 1, "c": rows}, f, ensure_ascii=False, separators=(",", ":"))
    anzahl = sum(len(r) for r in cells.values())
    print(f"{ordner}: {anzahl} in {len(cells)} Kacheln")
    return {"kacheln": sorted(cells.keys()), "anzahl": anzahl}


def _abstand_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320.0
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def amtliche_listen(out_dir):
    """Lädt alle amtlichen Listen; bei Fehler die gespeicherte Kopie aus amtlich/<key>.json."""
    ordner = os.path.join(out_dir, "amtlich")
    os.makedirs(ordner, exist_ok=True)
    ergebnis = []
    for src in amtlich.QUELLEN:
        datei = os.path.join(ordner, src["key"] + ".json")
        stand = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            liste = amtlich.standorte(src, amtlich.laden(src))
            if not liste:
                raise RuntimeError("keine Standorte")
            with open(datei, "w", encoding="utf-8") as f:
                json.dump({"stand": stand, "c": liste}, f, ensure_ascii=False, separators=(",", ":"))
            print(f"amtlich {src['key']}: {len(liste)}")
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(datei):
                print(f"amtlich {src['key']}: nicht erreichbar ({e}), keine alte Kopie", file=sys.stderr)
                continue
            with open(datei, encoding="utf-8") as f:
                alt = json.load(f)
            liste, stand = [tuple(x) for x in alt["c"]], alt["stand"]
            print(f"amtlich {src['key']}: nicht erreichbar ({e}), alte Kopie vom {stand}: {len(liste)}", file=sys.stderr)
        ergebnis.append((src, stand, liste))
    return ergebnis


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
        if tags.get("recycling_type") == "centre":
            continue  # Wertstoffhöfe stehen in der eigenen Ebene "hoefe"
        row = [f"osm-{el['type']}-{el['id']}", round(lat, 6), round(lon, 6), title(tags), details(tags)]
        key = f"{math.floor(lat)}_{math.floor(lon)}"
        cells.setdefault(key, []).append(row)

    ebenen = {
        "hoefe": ebene_schreiben(out_dir, "hoefe", fetch(QUERY_HOEFE, 2000), "Wertstoffhof", hof_details),
        "deponien": ebene_schreiben(out_dir, "deponien", fetch(QUERY_DEPONIEN, 1000), "Deponie", deponie_details),
    }

    # Raster (ca. 110 m) der OSM-Container für den Abgleich
    raster = {}
    for rows in cells.values():
        for row in rows:
            raster.setdefault((math.floor(row[1] * 1000), math.floor(row[2] * 1000)), []).append(row)

    quellen = []
    for src, q_stand, liste in amtliche_listen(out_dir):
        neu = 0
        for sid, lat, lon, titel, det in liste:
            i, j = math.floor(lat * 1000), math.floor(lon * 1000)
            best, best_d = None, GLEICH_M
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for row in raster.get((i + di, j + dj), []):
                        d = _abstand_m(lat, lon, row[1], row[2])
                        if d <= best_d:
                            best, best_d = row, d
            if best is not None:
                hinweis = "Auch in der amtlichen Liste: " + src["name"]
                if hinweis not in best[4]:
                    best[4].append(hinweis)
                continue
            key = f"{math.floor(lat)}_{math.floor(lon)}"
            cells.setdefault(key, []).append([sid, lat, lon, titel, list(det), src["key"]])
            neu += 1
        quellen.append({
            "key": src["key"], "name": src["name"], "lizenz": src["lizenz"],
            "namensnennung": src["namensnennung"], "stand": q_stand,
            "anzahl": len(liste), "zusaetzlich": neu,
        })

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
        "quellen": quellen,
        "ebenen": ebenen,
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"{total} Container in {len(cells)} Kacheln, Stand {stand}, "
          f"davon {sum(q['zusaetzlich'] for q in quellen)} nur aus amtlichen Listen")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
