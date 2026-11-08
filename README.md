# Glaskontainer-Daten

Altglas-Container in Deutschland für die App „Glaskontainer“, wöchentlich automatisch erneuert
(GitHub Actions, `tools/build_data.py`).

- `meta.json` – Stand, Anzahl, Liste der Kacheln, amtliche Quellen (`quellen`)
- `cells/<breite>_<länge>.json` – Container einer 1 × 1-Grad-Kachel:
  `[id, breite, länge, titel, [details]]` (OpenStreetMap) bzw.
  `[id, breite, länge, titel, [details], quelle]` (nur in einer amtlichen Liste, nicht in OpenStreetMap)
- `hoefe/<breite>_<länge>.json` – Wertstoffhöfe aus OpenStreetMap (`amenity=recycling` + `recycling_type=centre`)
- `deponien/<breite>_<länge>.json` – Deponien aus OpenStreetMap (`landuse=landfill`, ohne stillgelegte)
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

Datenlizenz Deutschland: <https://www.govdata.de/dl-de/by-2-0> bzw. <https://www.govdata.de/dl-de/zero-2-0>.
Die amtlichen Daten wurden übernommen, auf Glas-Standorte gefiltert, in GPS-Koordinaten umgerechnet und mit
OpenStreetMap abgeglichen.

## Lizenz
OpenStreetMap-Daten: **© OpenStreetMap-Mitwirkende**, verfügbar unter der
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Diese Sammlung ist eine abgeleitete Datenbank und steht ebenfalls unter der ODbL 1.0;
für die amtlichen Anteile gelten zusätzlich die Namensnennungen oben.
Mehr: <https://www.openstreetmap.org/copyright>
