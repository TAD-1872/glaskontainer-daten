"""
Amtliche, frei lizenzierte Listen von Glascontainern (Städte, Kreise, Abfallbetriebe).

Jede Quelle wird normal und öffentlich abgerufen (keine Zugangsdaten, keine Sperren umgangen).
Geprüft am 2026-11-08: Lizenz offen (DL-DE BY/Zero, CC BY, CC0, ODbL), Koordinaten vorhanden.
Ist eine Quelle beim Datenbau nicht erreichbar, wird die letzte gespeicherte Kopie (amtlich/<key>.json) benutzt.

title/details sind Vorlagen: {feld} wird durch den Wert aus den Daten ersetzt; eine Zeile entfällt,
wenn alle ihre Felder leer sind. "nur" ist ein Filter (nur Standorte mit Glas übernehmen).
"""
import csv
import io
import json
import math
import re
import sqlite3
import struct
import tempfile
import urllib.request
import zipfile

UA = "Glaskontainer-App-Datenbau/1.0 (privat)"

DL_BY = "Datenlizenz Deutschland – Namensnennung 2.0"
DL_ZERO = "Datenlizenz Deutschland – Zero 2.0"


def _ja(*felder):
    """Filter: mindestens eines der Felder ist 'ja' oder eine Zahl > 0."""
    def f(p):
        for k in felder:
            v = str(p.get(k) or "").strip().lower()
            if v in ("ja", "yes", "x", "true") or (v.replace(".", "", 1).isdigit() and float(v) > 0):
                return True
        return False
    return f


def _enthaelt(feld, wort):
    return lambda p: wort.lower() in str(p.get(feld) or "").lower()


LKR_REGENSBURG = ("https://geoportal.landkreis-regensburg.de/ogcapi/datasets/entsorgungseinrichtungen/collections/"
                  "Entsorgungseinrichtungen/items?bulk=true&f=json")

def _rvr(kategorie_id):
    """WFS-Abfrage beim Regionalverband Ruhr, nur eine POI-Kategorie (statt aller 79.000 POIs)."""
    import urllib.parse
    filt = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
            f'<fes:ValueReference>kategorie_id</fes:ValueReference><fes:Literal>{kategorie_id}</fes:Literal>'
            '</fes:PropertyIsEqualTo></fes:Filter>')
    return ("https://geodaten.metropoleruhr.de/poi/poi?service=WFS&version=2.0.0&request=GetFeature"
            "&typeNames=ms:poi_einfach&outputFormat=geojson&srsName=EPSG:4326&FILTER=" + urllib.parse.quote(filt))


QUELLEN = [
    dict(key="hamburg", name="Hamburg", lizenz=DL_BY,
         namensnennung="Freie und Hansestadt Hamburg, Behörde für Umwelt und Energie",
         url="https://geodienste.hamburg.de/HH_WFS_abfall_recycling?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
             "&typeNames=de.hh.up:abfall_recycling_2_glas&outputFormat=application/geo%2Bjson&srsName=EPSG:4326",
         title="{standort}",
         details=["Container: {weissglas_depotcontainer}× weiß, {gruenglas_depotcontainer}× grün, {braunglas_depotcontainer}× braun"]),
    dict(key="kiel", name="Kiel", lizenz="CC BY 4.0", namensnennung="Landeshauptstadt Kiel",
         url="https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer"
             "?request=GetFeature&service=WFS&typeName=Glascontainer&outputFormat=geoJSON",
         title="{Standort}", details=["{Anmerkung}"]),
    dict(key="luebeck", name="Lübeck", lizenz="ODbL 1.0", namensnennung="Entsorgungsbetriebe Lübeck",
         url="https://umap.openstreetmap.de/de/datalayer/50246/037f8037-f979-442a-81c5-7a0e09794261/",
         title="Glascontainer", details=[]),
    dict(key="norderstedt", name="Norderstedt", lizenz=DL_BY, namensnennung="Stadt Norderstedt",
         url="https://geoservice.norderstedt.de/geoserver/pub/ows?service=WFS&version=1.0.0&request=GetFeature"
             "&typeName=pub:glascontainer&outputFormat=application/json&srsName=EPSG:4326",
         title="{anschrift}", details=["{bemerk1}"]),
    dict(key="rostock", name="Rostock", lizenz="CC0", namensnennung="Hanse- und Universitätsstadt Rostock",
         url="https://geo.sv.rostock.de/download/opendata/glascontainer/glascontainer.json",
         title="{bezeichnung}", details=["Betreiber: {bewirtschafter}"]),
    dict(key="vorpommern-greifswald", name="Landkreis Vorpommern-Greifswald", lizenz=DL_BY,
         namensnennung="©Landkreis Vorpommern-Greifswald",
         url="https://service.geoportal-vg.de/dienste/wfs/abfallwirtschaft?SERVICE=WFS&VERSION=2.0.0"
             "&REQUEST=GetFeature&TYPENAMES=ms:glascontainerstandorte",
         format="gml", utm=33, title="{strasse_name} {hausnummer}", details=["{gemeinde_name}"]),
    dict(key="aachen", name="Aachen", lizenz=DL_BY, namensnennung="Stadt Aachen",
         url="https://geoserver.aachen.de/opendata/abfallnavi/ows?service=WFS&request=GetFeature"
             "&typeName=abfallnavi%3AGlascontainer&outputFormat=application%2Fjson&srsName=EPSG:4326",
         title="{strasse} {hausnummer}", details=["{ortsteil}", "{zusatz}", "Einwurfzeiten: {oeffnungszeiten}"]),
    dict(key="muenster", name="Münster", lizenz=DL_BY, namensnennung="Stadt Münster",
         url="https://raw.githubusercontent.com/od-ms/converter-scripts/master/data/awm-glascontainer-combined.geojson",
         title="{Standort}", details=["Sorten: {Sorten}"]),
    dict(key="grevenbroich", name="Grevenbroich", lizenz="CC0", namensnennung="Stadt Grevenbroich / Rhein-Kreis Neuss",
         url="https://opendata.rhein-kreis-neuss.de/api/v2/catalog/datasets/grevenbroich-glascontainer-standorte/exports/geojson",
         title="{strasse}", details=["{standort}", "{stadtteil}"]),
    dict(key="meerbusch", name="Meerbusch", lizenz=DL_BY, namensnennung="Stadt Meerbusch / Rhein-Kreis Neuss",
         url="https://opendata.rhein-kreis-neuss.de/api/v2/catalog/datasets/meerbusch-wertstoffcontainer/exports/geojson",
         title="{standort}", details=["{stadtteil}", "{einwurfzeiten}"]),
    dict(key="essen", name="Essen", lizenz=DL_BY, namensnennung="Stadt Essen",
         url="https://opendata.essen.de/sites/default/files/Depotcontainer_2026.geojson",
         nur=_ja("GLAS"), title="{ADRESSE}", details=["Container: {TYP}"],
         ersetzen={"PPK": "Papier", "AKL": "Altkleider"}),
    dict(key="gelsenkirchen", name="Gelsenkirchen", lizenz=DL_ZERO, namensnennung="Stadt Gelsenkirchen / Gelsendienste",
         url="https://maps.gelsenkirchen.de/geoserver/infrastrukturdatenbank/ogc/features/v1/collections/entsorgung/items?f=json&limit=5000",
         nur=_enthaelt("Schlagworte", "Glas"), title="{Strasse}", details=["{Stadtteil}", "Container: {Schlagworte}"]),
    dict(key="herne", name="Herne", lizenz=DL_ZERO, namensnennung="Stadt Herne",
         url="https://geodaten.herne.de/geoserver/abfall/entsorgungskarte?SERVICE=WFS&REQUEST=GetFeature"
             "&TYPENAME=wertstoffsammelstelle&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326",
         nur=_ja("glas"), title="{standplatz}", details=["{beschreibung}", "{bezirk}"]),
    dict(key="dorsten", name="Dorsten", lizenz=DL_BY, namensnennung="Stadt Dorsten / Entsorgungsbetrieb Dorsten",
         url="https://geoportal.dorsten.de/cgi-bin/qgis_mapserv.fcgi?map=/var/qgis/AAP-plus/openlayers/"
             "qgis_EBD_stadtreinigung_extern2.qgs&SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&TYPENAME=Glascontainer"
             "&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326",
         title="{Standort}", details=[]),
    dict(key="herford", name="Kreis Herford", lizenz="freie Nutzung (Kreis Herford)", namensnennung="Kreis Herford",
         url="https://geoportal.kreis-herford.de/wfs/VersorgungEntsorgung?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
             "&TYPENAMES=ms:VerEntsorgungseinrichtungen&OUTPUTFORMAT=text/csv",
         format="csv", lat="lat", lon="lon", nur=lambda p: p.get("thema") == "Glascontainer",
         title="{adresse}", details=["{ort}"]),
    dict(key="bonn", name="Bonn", lizenz="CC0", namensnennung="Bundesstadt Bonn",
         url="https://stadtplan.bonn.de/geojson?OD=4726",
         title="{standort}", details=["{bezeichnung}"]),
    dict(key="trier", name="Trier", lizenz=DL_BY, namensnennung="Stadt Trier / A.R.T. Trier",
         url="https://geoportal.trier.de/trier/mod_ogc/wfs_getmap.php?mapfile=abfallentsorgung&SERVICE=WFS&VERSION=1.1.0"
             "&REQUEST=GetFeature&TYPENAME=ms:glascontainer",
         format="gml", utm=32, title="{bez}", details=["{beschr}"]),
    dict(key="mannheim", name="Mannheim", lizenz=DL_BY, namensnennung="Stadt Mannheim",
         url="https://mannheim.opendatasoft.com/api/explore/v2.1/catalog/datasets/150824-altglascontainer-mannheim/exports/geojson",
         title="{title}", details=["{beschr}"]),
    dict(key="muenchen", name="München", lizenz=DL_BY, namensnennung="Landeshauptstadt München, AWM / GeodatenService München",
         url="https://geoportal.muenchen.de/geoserver/gsm_wfs/ows?service=WFS&version=1.0.0&request=GetFeature"
             "&typeName=gsm_wfs:awm_container&outputFormat=application/json&srsName=EPSG:4326",
         nur=_ja("glas_weiss", "glas_gruen", "glas_braun"), title="{adresse}",
         details=["Container: {glas_weiss}× weiß, {glas_gruen}× grün, {glas_braun}× braun"]),
    dict(key="regensburg", name="Regensburg", lizenz="CC BY 4.0", namensnennung="Stadt Regensburg",
         url="https://mapservice.regensburg.de/cgi-bin/mapserv?map=/data/ows/maps/altglas_wfs.map&VERSION=1.0.0"
             "&outputformat=geojson&SERVICE=WFS&REQUEST=GetFeature&TYPENAME=altglas",
         utm=32, title="{BEZEICHNUNG}", details=["{LAGEBESCHREIBUNG}"]),
    dict(key="amberg", name="Amberg", lizenz="CC BY 3.0", namensnennung="Stadt Amberg",
         url="https://amberg.de/fileadmin/opendata/container.csv",
         format="csv", lat="Latitude", lon="Longitude",
         nur=_enthaelt("description", "Altglas"), title="{name}", details=["Container: {description}"]),
    dict(key="memmingen", name="Memmingen", lizenz="CC BY 4.0", namensnennung="Stadt Memmingen",
         url="https://www.memmingen.de/fileadmin/opendata/amt54_abfall/Memmingen_Wertstoffcontainer_gpkg.zip",
         format="gpkg-zip", utm=32,
         nur=_ja("Weissglas", "Gruenglas", "Braunglas"), title="{Lage}", details=["{Gebiet}"]),
    # ---- Glascontainer: weitere ----
    dict(key="landkreis-regensburg", name="Landkreis Regensburg", lizenz="CC0", namensnennung="Landkreis Regensburg",
         url=LKR_REGENSBURG, nur=lambda p: p.get("unterkategorie") == "Glascontainer",
         title="{name}", details=["{adresse}"], ersetzen={"|": " · "}),

    # ---- Wertstoffhöfe / Recyclinghöfe (Ebene "hoefe") ----
    dict(key="hof-hamburg", ebene="hoefe", name="Hamburg (Recyclinghöfe)", lizenz=DL_BY,
         namensnennung="Freie und Hansestadt Hamburg, Behörde für Umwelt und Energie",
         url="https://geodienste.hamburg.de/HH_WFS_abfall_recycling?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
             "&typeNames=de.hh.up:abfall_recycling_6_recyhof&outputFormat=application/geo%2Bjson&srsName=EPSG:4326",
         title="{langbez}", details=["Öffnungszeiten: {oeffnungszeiten}", "{standort}, {stadtteil}"]),
    dict(key="hof-kiel", ebene="hoefe", name="Kiel (Recyclinghöfe)", lizenz="CC BY 4.0", namensnennung="Landeshauptstadt Kiel",
         url="https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer"
             "?request=GetFeature&service=WFS&typeName=Recyclinghoefe&outputFormat=geoJSON",
         title="Recyclinghof {Bezeichnung}", details=["{Internet}"]),
    dict(key="hof-luebeck", ebene="hoefe", name="Lübeck (Wertstoffhöfe)", lizenz="ODbL 1.0", namensnennung="Entsorgungsbetriebe Lübeck",
         url="https://umap.openstreetmap.de/de/datalayer/49064/aa47e154-d9ae-4a33-9f9c-32e52a0c3188/",
         title="{name}", details=["{description}"]),
    dict(key="hof-aachen", ebene="hoefe", name="Aachen (Recyclinghöfe)", lizenz=DL_BY, namensnennung="Stadt Aachen / Aachener Stadtbetrieb",
         url="https://geoserver.aachen.de/opendata/abfallnavi/ows?service=WFS&request=GetFeature"
             "&typeName=abfallnavi%3ARecyclingh%C3%B6fe&outputFormat=application%2Fjson&srsName=EPSG:4326",
         title="Recyclinghof {anlagenbezeichnung}", details=["Öffnungszeiten: {oeffnungszeiten}", "{strasse} {hausnummer}, {plz} {ort}"]),
    dict(key="hof-herne", ebene="hoefe", name="Herne (Wertstoffhof)", lizenz=DL_ZERO, namensnennung="Stadt Herne",
         url="https://geodaten.herne.de/geoserver/abfall/entsorgungskarte?SERVICE=WFS&REQUEST=GetFeature"
             "&TYPENAME=entsorgungsanlagen&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326",
         nur=_enthaelt("beschr", "Wertstoffhof"), title="Wertstoffhof", details=["{stndplz} {hsnr}"]),
    dict(key="hof-dresden", ebene="hoefe", name="Dresden (Wertstoffhöfe)", lizenz=DL_BY, namensnennung="Landeshauptstadt Dresden",
         url="https://kommisdd.dresden.de/net3/public/ogc.ashx?NodeId=748&Service=WFS&Request=GetFeature&Version=2.0.0"
             "&TypeNames=cls:L566&outputFormat=application/geo%2Bjson&srsName=EPSG:4326",
         title="{name}", details=["Öffnungszeiten: {oef_text}", "{url}"]),
    dict(key="hof-muenchen", ebene="hoefe", name="München (Wertstoffhöfe)", lizenz=DL_BY,
         namensnennung="Landeshauptstadt München, AWM / GeodatenService München",
         url="https://geoportal.muenchen.de/geoserver/gsm_wfs/ows?service=WFS&version=1.1.0&request=GetFeature"
             "&typeName=gsm_wfs:awm_wertstoffhoefe&outputFormat=application/json&srsName=EPSG:4326",
         title="Wertstoffhof {adresse}", details=["{link}"]),
    dict(key="hof-landkreis-regensburg", ebene="hoefe", name="Landkreis Regensburg (Wertstoffhöfe)", lizenz="CC0",
         namensnennung="Landkreis Regensburg", url=LKR_REGENSBURG,
         nur=lambda p: p.get("unterkategorie") == "Wertstoffhöfe",
         title="Wertstoffhof {name}", details=["{adresse}"], ersetzen={"|": " · "}),

    # ---- Deponien (Ebene "deponien"): nur Deponien, auf denen noch abgelagert wird ----
    dict(key="deponie-nrw", ebene="deponien", name="Nordrhein-Westfalen (Deponien)", lizenz=DL_BY,
         namensnennung="Land NRW / Landesamt für Natur, Umwelt und Klima (OpenAddisWeb)",
         url="https://www.opengeodata.nrw.de/produkte/umwelt_klima/anlagen_abfall/abfall/addis/OpenAddisWeb-Deponien_EPSG25832_Shape.zip",
         format="nrw-deponien", utm=32, nur=lambda p: p.get("phase") == "Ablagerungsphase",
         title="{name}", details=["{klasse}", "Betreiber: {betreiber}"]),
    dict(key="deponie-brandenburg", ebene="deponien", name="Brandenburg (Deponien)", lizenz=DL_BY,
         namensnennung="Landesamt für Umwelt Brandenburg (LfU)",
         url="https://data.geobasis-bb.de/geofachdaten/Luft_und_Luftqualitaet/depo.zip",
         format="shp-zip", utm=33, nur=_ja("Phase_a"),
         title="Deponie {Bez}", details=["Deponieklasse {klassen}"]),
    dict(key="deponie-saarland", ebene="deponien", name="Saarland (Deponien)", lizenz="CC BY 4.0",
         namensnennung="Ministerium für Umwelt, Klima, Mobilität, Agrar und Verbraucherschutz des Saarlandes",
         url="https://geoportal.saarland.de/arcgis/services/Internet/Abfallbeseitigung/MapServer/WFSServer"
             "?request=GetFeature&VERSION=2.0.0&SERVICE=WFS&typeNames=Abfallbeseitigung:Deponien",
         format="gml", utm=32, nur=_enthaelt("phase", "Ablagerung"),
         title="{name}", details=["Deponieklasse {klasse}"]),
    # ---- Regionalverband Ruhr (ganzes Ruhrgebiet), nur die Kategorien Containerstandorte / Recyclinghöfe ----
    dict(key="rvr-glas", name="Regionalverband Ruhr (Containerstandorte)", lizenz=DL_BY, namensnennung="Regionalverband Ruhr (RVR)",
         url=_rvr(197028), nur=lambda p: "glas" in (str(p.get("name")) + str(p.get("beschreibung"))).lower(),
         title="{strasse} {hausnummer}", details=["{beschreibung}", "{ort}"]),
    dict(key="hof-rvr", ebene="hoefe", name="Regionalverband Ruhr (Recyclinghöfe)", lizenz=DL_BY,
         namensnennung="Regionalverband Ruhr (RVR)", url=_rvr(197030),
         title="{name}", details=["{beschreibung}", "{strasse} {hausnummer}, {plz} {ort}", "{link}"]),
    dict(key="hof-landkreis-rostock", ebene="hoefe", name="Landkreis Rostock (Wertstoffhöfe)", lizenz="CC0",
         namensnennung="Landkreis Rostock",
         url="https://geoportal.lkros.de/dienste/wertstoffhoefe?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:wertstoffhoefe",
         format="gml", utm=33, title="Wertstoffhof", details=[]),
    dict(key="hof-vorpommern-greifswald", ebene="hoefe", name="Landkreis Vorpommern-Greifswald (Wertstoffhöfe)", lizenz=DL_BY,
         namensnennung="©Landkreis Vorpommern-Greifswald",
         url="https://service.geoportal-vg.de/dienste/wfs/abfallwirtschaft?SERVICE=WFS&VERSION=2.0.0"
             "&REQUEST=GetFeature&TYPENAMES=ms:wertstoffhoefe",
         format="gml", utm=33, title="{name}",
         details=["{bemerkung}", "{strasse_name} {hausnummer}", "{gemeinde_name}", "Telefon: {telefon}", "{website}"]),
    dict(key="hof-cottbus", ebene="hoefe", name="Cottbus (Wertstoffhöfe)", lizenz=DL_BY,
         namensnennung="Stadt Cottbus/Chóśebuz",
         url="https://datenportal.cottbus.de/server/rest/services/FB70/station%C3%A4re_Annahmestellen/FeatureServer/0/query"
             "?where=1%3D1&outFields=*&outSR=4326&f=geojson",
         nur=lambda p: any(w in str(p.get("objekt")) for w in ("Wertstoffhof", "Schadstoff")),
         title="{objekt}",
         details=["Öffnungszeiten März–November: {maerz_november}", "Öffnungszeiten Dezember–Februar: {dezember_februar}",
                  "{Info} {info_2}", "{bemerkung}", "{standort}, Cottbus", "Telefon: {telefon}"]),
    # ---- Kleidercontainer (Ebene "kleider") ----
    dict(key="kl-hamburg", ebene="kleider", name="Hamburg (Altkleider)", lizenz=DL_BY,
         namensnennung="Freie und Hansestadt Hamburg, Behörde für Umwelt und Energie",
         url="https://geodienste.hamburg.de/HH_WFS_abfall_recycling?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
             "&typeNames=de.hh.up:abfall_recycling_4_textil&outputFormat=application/geo%2Bjson&srsName=EPSG:4326",
         title="{standort}", details=[]),
    dict(key="kl-kiel", ebene="kleider", name="Kiel (Altkleider)", lizenz="CC BY 4.0", namensnennung="Landeshauptstadt Kiel",
         url="https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer"
             "?request=GetFeature&service=WFS&typeName=Altkleidercontainer&outputFormat=geoJSON",
         title="{Standort}", details=["{Anmerkung}"]),
    dict(key="kl-luebeck", ebene="kleider", name="Lübeck (Altkleider)", lizenz="ODbL 1.0", namensnennung="Entsorgungsbetriebe Lübeck",
         url="https://umap.openstreetmap.de/de/datalayer/50246/06a9800d-f95a-412c-a199-30c6506dc66e/",
         title="Altkleidercontainer", details=["{description}"]),
    dict(key="kl-norderstedt", ebene="kleider", name="Norderstedt (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Norderstedt",
         url="https://geoservice.norderstedt.de/geoserver/pub/ows?service=WFS&version=1.0.0&request=GetFeature"
             "&typeName=pub:altkleidercontainer&outputFormat=application/json&srsName=EPSG:4326",
         title="{anschrift}", details=["{bezeich}"]),
    dict(key="kl-rostock", ebene="kleider", name="Rostock (Altkleider)", lizenz="CC0", namensnennung="Hanse- und Universitätsstadt Rostock",
         url="https://geo.sv.rostock.de/download/opendata/altkleidercontainer/altkleidercontainer.json",
         title="{bezeichnung}", details=["Betreiber: {bewirtschafter}"]),
    dict(key="kl-koeln", ebene="kleider", name="Köln (Altkleider)", lizenz=DL_ZERO, namensnennung="AWB Abfallwirtschaftsbetriebe Köln",
         url="https://www.awbkoeln.de/geodaten/altkleider/", format="awb-xml",
         title="{locationname}", details=["{area} – {district}"]),
    dict(key="kl-muenster", ebene="kleider", name="Münster (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Münster",
         url="https://raw.githubusercontent.com/od-ms/converter-scripts/master/data/awm-altkleider.geojson",
         title="{Standort}", details=["{Stadtteil}"]),
    dict(key="kl-essen", ebene="kleider", name="Essen (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Essen",
         url="https://opendata.essen.de/sites/default/files/Depotcontainer_2026.geojson",
         nur=_ja("ALTKLEIDER"), title="{ADRESSE}", details=[]),
    dict(key="kl-gelsenkirchen", ebene="kleider", name="Gelsenkirchen (Altkleider)", lizenz=DL_ZERO,
         namensnennung="Stadt Gelsenkirchen / Gelsendienste",
         url="https://maps.gelsenkirchen.de/geoserver/infrastrukturdatenbank/ogc/features/v1/collections/entsorgung/items?f=json&limit=5000",
         nur=_enthaelt("Schlagworte", "Altkleider"), title="{Strasse}", details=["{Stadtteil}"]),
    dict(key="kl-herne", ebene="kleider", name="Herne (Altkleider)", lizenz=DL_ZERO, namensnennung="Stadt Herne",
         url="https://geodaten.herne.de/geoserver/abfall/entsorgungskarte?SERVICE=WFS&REQUEST=GetFeature"
             "&TYPENAME=wertstoffsammelstelle&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326",
         nur=_ja("textil"), title="{standplatz}", details=["{beschreibung}", "{bezirk}"]),
    dict(key="kl-rvr", ebene="kleider", name="Regionalverband Ruhr (Altkleider)", lizenz=DL_BY, namensnennung="Regionalverband Ruhr (RVR)",
         url=_rvr(197028), nur=lambda p: "kleider" in (str(p.get("name")) + str(p.get("beschreibung"))).lower(),
         title="{strasse} {hausnummer}", details=["{name}", "{ort}"]),
    dict(key="kl-dorsten", ebene="kleider", name="Dorsten (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Dorsten / Entsorgungsbetrieb Dorsten",
         url="https://geoportal.dorsten.de/cgi-bin/qgis_mapserv.fcgi?map=/var/qgis/AAP-plus/openlayers/"
             "qgis_EBD_stadtreinigung_extern2.qgs&SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&TYPENAME=Altkleidercontainer"
             "&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326",
         title="{Standort}", details=[]),
    dict(key="kl-herford", ebene="kleider", name="Kreis Herford (Altkleider)", lizenz="freie Nutzung (Kreis Herford)",
         namensnennung="Kreis Herford",
         url="https://geoportal.kreis-herford.de/wfs/VersorgungEntsorgung?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
             "&TYPENAMES=ms:VerEntsorgungseinrichtungen&OUTPUTFORMAT=text/csv",
         format="csv", lat="lat", lon="lon", nur=lambda p: p.get("thema") == "Altkleidercontainer",
         title="{adresse}", details=["{ort}"]),
    dict(key="kl-trier", ebene="kleider", name="Trier (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Trier / A.R.T. Trier",
         url="https://geoportal.trier.de/trier/mod_ogc/wfs_getmap.php?mapfile=abfallentsorgung&SERVICE=WFS&VERSION=1.1.0"
             "&REQUEST=GetFeature&TYPENAME=ms:altkleidercontainer",
         format="gml", utm=32, title="{bez}", details=["{beschr}"]),
    dict(key="kl-mannheim", ebene="kleider", name="Mannheim (Altkleider)", lizenz=DL_BY, namensnennung="Stadt Mannheim",
         url="https://mannheim.opendatasoft.com/api/explore/v2.1/catalog/datasets/150824-altkleidercontainer-mannheim/exports/geojson",
         title="{title}", details=["{beschr}"]),
    dict(key="kl-muenchen", ebene="kleider", name="München (Altkleider)", lizenz=DL_BY,
         namensnennung="Landeshauptstadt München, AWM / GeodatenService München",
         url="https://geoportal.muenchen.de/geoserver/gsm_wfs/ows?service=WFS&version=1.0.0&request=GetFeature"
             "&typeName=gsm_wfs:awm_container&outputFormat=application/json&srsName=EPSG:4326",
         nur=_ja("altkleider"), title="{adresse}", details=["Container: {altkleider}"]),
    dict(key="kl-regensburg", ebene="kleider", name="Regensburg (Altkleider)", lizenz="CC BY 4.0", namensnennung="Stadt Regensburg",
         url="https://mapservice.regensburg.de/cgi-bin/mapserv?map=/data/ows/maps/kleider_wfs.map&VERSION=1.0.0"
             "&outputformat=geojson&SERVICE=WFS&REQUEST=GetFeature&TYPENAME=kleider",
         utm=32, title="{BEZEICHNUNG}", details=["{LAGEBESCHREIBUNG}"]),
    dict(key="kl-memmingen", ebene="kleider", name="Memmingen (Altkleider)", lizenz="CC BY 4.0", namensnennung="Stadt Memmingen",
         url="https://www.memmingen.de/fileadmin/opendata/amt54_abfall/Memmingen_Wertstoffcontainer_gpkg.zip",
         format="gpkg-zip", utm=32, nur=_ja("Altkleider"), title="{Lage}", details=[]),
]


def _laden(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def _text(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _geojson(data):
    out = []
    for f in json.loads(_text(data)).get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        c = g.get("coordinates") or []
        if len(c) < 2:
            continue
        props = {k: v for k, v in (f.get("properties") or {}).items() if not isinstance(v, (dict, list))}
        out.append((float(c[0]), float(c[1]), props))
    return out


_POS = re.compile(r"<gml:pos[^>]*>\s*([-\d.]+)\s+([-\d.]+)\s*</gml:pos>")
_FELD = re.compile(r"<\w+:([\w-]+)>([^<]*)</\w+:\1>")


def _gml(data):
    out = []
    for chunk in re.split(r"<wfs:member>|<gml:featureMember>", _text(data))[1:]:
        m = _POS.search(chunk)
        if not m:
            continue
        props = {k: v for k, v in _FELD.findall(chunk)}
        out.append((float(m.group(1)), float(m.group(2)), props))
    return out


def _csv(data, src):
    out = []
    text = _text(data)
    dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;")
    for row in csv.DictReader(io.StringIO(text), dialect=dialect):
        try:
            lat = float(str(row[src["lat"]]).replace(",", "."))
            lon = float(str(row[src["lon"]]).replace(",", "."))
        except (KeyError, ValueError):
            continue
        out.append((lon, lat, row))
    return out


def _gpkg_punkt(blob):
    # GeoPackage-Kopf: "GP", Version, Flags, SRS-ID, dann Hülle (je nach Flags), danach WKB
    flags = blob[3]
    hülle = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get((flags >> 1) & 7, 0)
    wkb = blob[8 + hülle:]
    end = "<" if wkb[0] == 1 else ">"
    typ = struct.unpack(end + "I", wkb[1:5])[0]
    if typ % 1000 != 1:
        return None
    return struct.unpack(end + "dd", wkb[5:21])


def _gpkg_zip(data):
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".gpkg"))
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
            tmp.write(z.read(name))
            pfad = tmp.name
    con = sqlite3.connect(pfad)
    try:
        tabelle = con.execute("select table_name from gpkg_contents where data_type='features'").fetchone()[0]
        geomspalte = con.execute("select column_name from gpkg_geometry_columns where table_name=?", (tabelle,)).fetchone()[0]
        cur = con.execute(f'select * from "{tabelle}"')
        spalten = [d[0] for d in cur.description]
        for row in cur:
            props = dict(zip(spalten, row))
            p = _gpkg_punkt(props.pop(geomspalte))
            if p:
                out.append((p[0], p[1], {k: v for k, v in props.items() if not isinstance(v, bytes)}))
    finally:
        con.close()
    return out


def _dbf(b, enc):
    n = struct.unpack("<I", b[4:8])[0]
    kopf, satz = struct.unpack("<HH", b[8:12])
    felder, i = [], 32
    while b[i] != 0x0D:
        felder.append((b[i:i + 11].split(b"\0")[0].decode("ascii", "replace"), b[i + 16]))
        i += 32
    out = []
    for k in range(n):
        r = b[kopf + k * satz:kopf + (k + 1) * satz]
        if r[:1] == b"*":  # gelöscht
            continue
        o, d = 1, {}
        for name, laenge in felder:
            d[name] = r[o:o + laenge].decode(enc, "replace").strip()
            o += laenge
        out.append(d)
    return out


def _shp(b):
    """Mittelpunkte aller Formen einer .shp-Datei (Punkt = Punkt, Fläche/Linie = Mitte des Umrisses)."""
    out, o = [], 100
    while o + 8 <= len(b):
        laenge = struct.unpack(">i", b[o + 4:o + 8])[0] * 2
        inhalt = b[o + 8:o + 8 + laenge]
        typ = struct.unpack("<i", inhalt[:4])[0] if len(inhalt) >= 4 else 0
        if typ in (1, 11, 21):
            out.append(struct.unpack("<dd", inhalt[4:20]))
        elif typ in (3, 5, 13, 15, 23, 25):
            x0, y0, x1, y1 = struct.unpack("<dddd", inhalt[4:36])
            out.append(((x0 + x1) / 2, (y0 + y1) / 2))
        else:
            out.append(None)
        o += 8 + laenge
    return out


def _shp_zip(data, name=None):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        namen = z.namelist()
        basis = name or next(n for n in namen if n.lower().endswith(".shp"))[:-4]
        cpg = next((n for n in namen if n.lower() == (basis + ".cpg").lower()), None)
        enc = z.read(cpg).decode("ascii", "replace").strip() if cpg else "cp1252"
        if enc.upper().replace("-", "") == "UTF8":
            enc = "utf-8"
        elif enc.upper() in ("ANSI", "1252"):
            enc = "cp1252"
        punkte = _shp(z.read(basis + ".shp"))
        saetze = _dbf(z.read(basis + ".dbf"), enc)
    out = []
    for p, d in zip(punkte, saetze):
        if p:
            # Brandenburg: Deponieklassen als lesbaren Text zusammenfassen
            klassen = [k[2:] for k in ("Dk0", "Dk1", "Dk2", "Dk3") if d.get(k) == "1"]
            if klassen:
                d["klassen"] = ", ".join(klassen)
            out.append((p[0], p[1], d))
    return out


def _xlsx_zeilen(data):
    """Erste Tabelle einer Excel-Datei als Liste von Zeilen (nur Text/Zahlen)."""
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        texte = []
        if "xl/sharedStrings.xml" in z.namelist():
            texte = ["".join(t.text or "" for t in si.iter(ns + "t"))
                     for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(ns + "si")]
        blatt = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    zeilen = []
    for r in blatt.iter(ns + "row"):
        zeile = []
        for c in r.iter(ns + "c"):
            v = c.find(ns + "v")
            v = v.text if v is not None else ""
            zeile.append(texte[int(v)] if c.get("t") == "s" and v else v)
        zeilen.append(zeile)
    return zeilen


def _nrw_deponien(data):
    """NRW OpenAddisWeb: Deponie-Umrisse (Grenze.shp) + Liste mit Name, Klasse, Phase, Betreiber (Excel)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        liste = next(n for n in z.namelist() if n.lower().startswith("deponien") and n.lower().endswith(".xlsx"))
        zeilen = _xlsx_zeilen(z.read(liste))
    info = {}
    for z in zeilen[1:]:
        if len(z) >= 5 and z[0]:
            # Spalten laut Inhalt: Entsorgernummer, Bezeichnung, Deponieklasse, Betriebsphase, Betreiber
            info[z[0]] = {"name": z[1], "klasse": z[2], "phase": z[3], "betreiber": z[4]}
    lage = {}
    for x, y, d in _shp_zip(data, "Grenze"):
        lage.setdefault(d.get("ENR"), []).append((x, y))
    out = []
    for enr, punkte in lage.items():
        if enr in info:
            x = sum(p[0] for p in punkte) / len(punkte)
            y = sum(p[1] for p in punkte) / len(punkte)
            out.append((x, y, info[enr]))
    return out


def _awb_xml(data):
    """AWB Köln: <address> mit <coordinates>breite,länge</coordinates>."""
    import xml.etree.ElementTree as ET
    out = []
    for a in ET.fromstring(data).iter("address"):
        werte = {c.tag: (c.text or "").strip() for c in a}
        try:
            lat, lon = (float(x) for x in werte.get("coordinates", "").split(","))
        except ValueError:
            continue
        out.append((lon, lat, werte))
    return out


def utm_zu_gps(e, n, zone):
    """Rechts-/Hochwert (ETRS89 / UTM) → (Breite, Länge). Genauigkeit ca. 1 m (wie in der App)."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = e - 500000.0
    m = n / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
         + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    sp, cp, tp = math.sin(p), math.cos(p), math.tan(p)
    n1 = a / math.sqrt(1 - e2 * sp * sp)
    t1 = tp * tp
    c1 = ep2 * cp * cp
    r1 = a * (1 - e2) / (1 - e2 * sp * sp) ** 1.5
    d = x / (n1 * k0)
    lat = p - (n1 * tp / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * ep2) * d ** 4 / 24
                                + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * ep2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * ep2 + 24 * t1 * t1) * d ** 5 / 120) / cp
    return math.degrees(lat), zone * 6 - 183 + math.degrees(lon)


_PLATZ = re.compile(r"\{([\w-]+)\}")


def _sauber(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    t = str(v)
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"\*\*Route:\*\*.*", "", t, flags=re.S)  # Navigationslink (uMap)
    t = re.sub(r"\[\[.*?\]\]", "", t).replace("**", "")
    t = re.sub(r"\(Hinweis:.*?\)", "", t, flags=re.S).strip()
    return "" if t.lower() in ("", "null", "none", "-", "–") else t


def _fuellen(vorlage, props):
    werte = [_sauber(props.get(k)) for k in _PLATZ.findall(vorlage)]
    if _PLATZ.search(vorlage) and not any(werte):
        return None
    text = _PLATZ.sub(lambda m: _sauber(props.get(m.group(1))), vorlage)
    return re.sub(r"\s+", " ", text).strip(" ,") or None


def rohdaten_lesen(src, data):
    fmt = src.get("format", "geojson")
    if fmt == "gml":
        return _gml(data)
    if fmt == "csv":
        return _csv(data, src)
    if fmt == "gpkg-zip":
        return _gpkg_zip(data)
    if fmt == "shp-zip":
        return _shp_zip(data)
    if fmt == "nrw-deponien":
        return _nrw_deponien(data)
    if fmt == "awb-xml":
        return _awb_xml(data)
    return _geojson(data)


def standorte(src, data):
    """Liste von (id, lat, lon, titel, details) aus den heruntergeladenen Daten."""
    out = []
    nur = src.get("nur")
    for x, y, props in rohdaten_lesen(src, data):
        if nur and not nur(props):
            continue
        if src.get("utm"):
            lat, lon = utm_zu_gps(x, y, src["utm"])
        else:
            lat, lon = y, x
        if not (47.0 <= lat <= 55.5 and 5.5 <= lon <= 15.5):
            continue
        titel = _fuellen(src["title"], props) or "Glascontainer"
        details = []
        for v in src.get("details", []):
            t = _fuellen(v, props)
            for alt, neu in src.get("ersetzen", {}).items():
                t = t.replace(alt, neu) if t else t
            if t and t != titel and t not in details:
                details.append(t)
        out.append((f"amt-{src['key']}-{lat:.5f}_{lon:.5f}", round(lat, 6), round(lon, 6), titel, details))
    # Viele Einträge auf exakt demselben Punkt = Platzhalter-Koordinate (Adresse nicht verortet) → weglassen
    zahl = {}
    for s in out:
        zahl[s[0]] = zahl.get(s[0], 0) + 1
    # gleiche Stelle doppelt in der Liste (z. B. je Glasfarbe ein Eintrag) → einmal
    gesehen = set()
    einmal = []
    for s in out:
        if zahl[s[0]] > 5:
            continue
        if s[0] not in gesehen:
            gesehen.add(s[0])
            einmal.append(s)
    return einmal


def laden(src):
    return _laden(src["url"])
