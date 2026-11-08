# Glaskontainer-Daten

Altglas-Container in Deutschland für die App „Glaskontainer“, wöchentlich automatisch erneuert
(GitHub Actions, `tools/build_data.py`).

- `meta.json` – Stand, Anzahl, Liste der Kacheln
- `cells/<breite>_<länge>.json` – Container einer 1 × 1-Grad-Kachel:
  `[id, breite, länge, titel, [details]]`

## Lizenz
Die Daten stammen aus OpenStreetMap: **© OpenStreetMap-Mitwirkende**, verfügbar unter der
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Diese Sammlung ist eine abgeleitete Datenbank und steht ebenfalls unter der ODbL 1.0.
Mehr: <https://www.openstreetmap.org/copyright>
