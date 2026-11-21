# Glaskontainer-Daten

Altglas-Container in Deutschland für die App „Glaskontainer“, wöchentlich automatisch erneuert
(GitHub Actions, `tools/build_data.py`).

- `meta.json` – Stand, Anzahl, Liste der Kacheln, amtliche Quellen (`quellen`)
- `cells/<breite>_<länge>.json` – Container einer 1 × 1-Grad-Kachel:
  `[id, breite, länge, titel, [details]]` (OpenStreetMap) bzw.
  `[id, breite, länge, titel, [details], quelle]` (nur in einer amtlichen Liste, nicht in OpenStreetMap)
- `hoefe/<breite>_<länge>.json` – Wertstoffhöfe aus OpenStreetMap (`amenity=recycling` + `recycling_type=centre`)
- `deponien/<breite>_<länge>.json` – Deponien aus OpenStreetMap (`landuse=landfill`, ohne stillgelegte)
- `kleider/<breite>_<länge>.json` – Kleidercontainer (OSM `recycling:clothes=yes` + amtliche Listen; IDs mit Vorsilbe `kl-`)
- `amtlich/<quelle>.json` – letzte erfolgreich geladene Kopie jeder amtlichen Liste (Reserve, falls ein Server ausfällt)

## Quellen
Grundlage ist OpenStreetMap (ganz Deutschland). Dazu kommen frei lizenzierte amtliche Listen von Städten,
Kreisen und Abfallbetrieben (`tools/amtlich.py`). Ein amtlicher Standort, der höchstens 60 m von einem
OSM-Container entfernt ist, gilt als derselbe Standort und wird nicht doppelt aufgenommen.

| Gebiet | Herausgeber | Lizenz |
|---|---|---|
| Hamburg | Freie und Hansestadt Hamburg, Behörde für Umwelt und Energie | Datenlizenz Deutschland – Namensnennung 2.0 |
| Kiel | Landeshauptstadt Kiel | CC BY 4.0 |
| Lübeck | Entsorgungsbetriebe Lübeck | ODbL 1.0 |
| Norderstedt | Stadt Norderstedt | Datenlizenz Deutschland – Namensnennung 2.0 |
| Rostock | Hanse- und Universitätsstadt Rostock | CC0 |
| Landkreis Vorpommern-Greifswald | ©Landkreis Vorpommern-Greifswald | Datenlizenz Deutschland – Namensnennung 2.0 |
| Aachen | Stadt Aachen | Datenlizenz Deutschland – Namensnennung 2.0 |
| Münster | Stadt Münster | Datenlizenz Deutschland – Namensnennung 2.0 |
| Grevenbroich | Stadt Grevenbroich / Rhein-Kreis Neuss | CC0 |
| Meerbusch | Stadt Meerbusch / Rhein-Kreis Neuss | Datenlizenz Deutschland – Namensnennung 2.0 |
| Essen | Stadt Essen | Datenlizenz Deutschland – Namensnennung 2.0 |
| Gelsenkirchen | Stadt Gelsenkirchen / Gelsendienste | Datenlizenz Deutschland – Zero 2.0 |
| Herne | Stadt Herne | Datenlizenz Deutschland – Zero 2.0 |
| Dorsten | Stadt Dorsten / Entsorgungsbetrieb Dorsten | Datenlizenz Deutschland – Namensnennung 2.0 |
| Kreis Herford | Kreis Herford | freie Nutzung |
| Bonn | Bundesstadt Bonn | CC0 |
| Trier | Stadt Trier / A.R.T. Trier | Datenlizenz Deutschland – Namensnennung 2.0 |
| Mannheim | Stadt Mannheim | Datenlizenz Deutschland – Namensnennung 2.0 |
| München | Landeshauptstadt München, AWM / GeodatenService München | Datenlizenz Deutschland – Namensnennung 2.0 |
| Regensburg | Stadt Regensburg | CC BY 4.0 |
| Amberg | Stadt Amberg | CC BY 3.0 |
| Memmingen | Stadt Memmingen | CC BY 4.0 |
| Landkreis Regensburg | Landkreis Regensburg | CC0 |

**Wertstoffhöfe / Recyclinghöfe** (Ebene `hoefe`; ein amtlicher Hof ≤ 250 m von einem OSM-Hof ergänzt diesen,
amtliche Öffnungszeiten ersetzen die aus OSM): Hamburg (DL-DE BY 2.0), Kiel (CC BY 4.0), Lübeck – Entsorgungsbetriebe
Lübeck (ODbL), Aachen (DL-DE BY 2.0), Herne (DL-DE Zero 2.0), Dresden (DL-DE BY 2.0), München – AWM (DL-DE BY 2.0),
Landkreis Regensburg (CC0), Landkreis Vorpommern-Greifswald (DL-DE BY 2.0), Cottbus (DL-DE BY 2.0).
Zusätzlich Wertstoffhöfe, die in OpenStreetMap als Container mit Namen „Wertstoffhof …“ oder als Umladestation
(`waste_transfer_station`) eingetragen sind (IDs `hof-…`, nur wenn kein anderer Hof ≤ 250 m entfernt ist).

**Regionalverband Ruhr** (DL-DE BY 2.0): Containerstandorte und Recyclinghöfe im ganzen Ruhrgebiet;
**Landkreis Rostock** (CC0): Wertstoffhöfe.

**Kleidercontainer** (Ebene `kleider`): Hamburg, Kiel, Lübeck, Norderstedt, Rostock, Köln – AWB (DL-DE Zero 2.0),
Münster, Essen, Gelsenkirchen, Herne, Regionalverband Ruhr, Dorsten, Kreis Herford, Trier, Mannheim, München,
Regensburg, Memmingen (Lizenzen wie bei den Glascontainern derselben Herausgeber).

**Deponien** (Ebene `deponien`, nur in der Ablagerungsphase; Abgleich mit OSM bis 800 m; aus der Deponieklasse
wird ein Hinweis „Darf annehmen: …“ erzeugt):
Nordrhein-Westfalen – OpenAddisWeb, LANUK NRW (DL-DE BY 2.0), Brandenburg – Landesamt für Umwelt (DL-DE BY 2.0),
Saarland – Umweltministerium (CC BY 4.0).

Datenlizenz Deutschland: <https://www.govdata.de/dl-de/by-2-0> bzw. <https://www.govdata.de/dl-de/zero-2-0>.
Die amtlichen Daten wurden übernommen, auf Glas-Standorte gefiltert, in GPS-Koordinaten umgerechnet und mit
OpenStreetMap abgeglichen.

## Lizenz
OpenStreetMap-Daten: **© OpenStreetMap-Mitwirkende**, verfügbar unter der
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Diese Sammlung ist eine abgeleitete Datenbank und steht ebenfalls unter der ODbL 1.0;
für die amtlichen Anteile gelten zusätzlich die Namensnennungen oben.
Mehr: <https://www.openstreetmap.org/copyright>
