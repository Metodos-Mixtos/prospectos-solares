"""
Entorno del lote: cruces contra geoservicios públicos ambientales, de riesgo, climáticos,
mineros, de hidrocarburos y territoriales. Las capas que deciden o miden superficie se
cruzan con el polígono real (solape en ha); las demás por envolvente o centroide. Se
guarda por lote en data/entorno/<CODIGO>.json con fecha y versión de cada capa; la capa
que falla queda como error y se reintenta sola. Fuentes (ArcGIS REST y WFS, verificadas
en agosto de 2026): IDEAM (drenajes, inundaciones de seis episodios de La Niña, zonas
inundables periódicamente 2022, climatología de El Niño y La Niña, sequía, incendios);
MADS/SIAC (humedales, POMCA, páramos); Parques Nacionales (RUNAP vivo); ANT
(resguardos y consejos comunitarios); IGAC (capacidad de uso multiescalar 2024); UPRA
(frontera agrícola); ANM (títulos y solicitudes); ANH (bloques); SGC (sísmica, movimientos
en masa). Uso: python -m predios.entorno [--perfil utility] [--forzar]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
CACHE = config.PROJECT_ROOT / "data" / "entorno"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
TIMEOUT = 60

#: Servicios por envolvente. clave -> (url de la capa, campos que se guardan)
CAPAS = {
    "drenajes": ("http://dhime.ideam.gov.co/server/rest/services/Cartografia_Basica/Hidrografia/MapServer/0",
                 ["nombre_geografico", "estado_drenaje"]),
    "drenajes_dobles": ("http://dhime.ideam.gov.co/server/rest/services/Cartografia_Basica/Hidrografia/MapServer/1",
                        ["nombre_geografico"]),
    # Manchas de inundación observadas en los episodios de La Niña (IDEAM, Amenaza_Ambiental;
    # V2 donde existe) y zonas inundables periódicamente 2022, todas cruzadas con el
    # polígono del lote para tener hectáreas de solape y no solo un "toca".
    "inundacion_1988": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/6",
                        ["emergencia", "area_ha"]),
    "inundacion_2000": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/26",
                        ["mancha", "area_ha"]),
    "inundacion_2011": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/22",
                        ["mancha", "area_ha"]),
    "inundacion_2012": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/27",
                        ["mancha", "area_ha"]),
    "inundacion_2016": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/23",
                        ["mancha", "area_ha"]),
    "inundacion_2020_2022": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer/24",
                             ["mancha", "area_ha"]),
    "zip_2022": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Indicadores_Hidricos/MapServer/21",
                 ["zip", "area_ha"]),
    "humedales": ("https://services6.arcgis.com/hxAwRYAu9QHliJ8T/arcgis/rest/services/Ecosistema_Estrategico/FeatureServer/3",
                  ["humedal", "grado_tran", "nomszh", "area_ha"]),
    "pomca": ("https://services6.arcgis.com/hxAwRYAu9QHliJ8T/arcgis/rest/services/POMCAS_actualizado_2023/FeatureServer/0",
              ["nom_pomca", "nom_fase", "res_adop", "car_lider"]),
    "frontera_agricola": ("https://geoservicios.upra.gov.co/arcgis/rest/services/ordenamiento_productivo/frontera_agricola_frontera_agricola_condicionada/MapServer/0",
                          ["tipo_frontera"]),
    "mineria_titulos": ("https://geo.anm.gov.co/webgis/rest/services/ANM/ServiciosANM/MapServer/4",
                        ["CODIGO_EXPEDIENTE", "ESTADO", "MODALIDAD", "ETAPA", "MINERALES", "NOMBRE_DE_TITULAR"]),
    "mineria_solicitudes": ("https://geo.anm.gov.co/webgis/rest/services/ANM/ServiciosANM/MapServer/2",
                            ["CODIGO_EXPEDIENTE", "ESTADO", "MODALIDAD", "MINERALES"]),
    "hidrocarburos": ("https://geovisor.anh.gov.co/server/rest/services/GEOVISOR_v32/ANH_TIERRAS_EGDB_ATTACH/MapServer/0",
                      ["CONTRATO_N", "CLASIFICAC", "TIPO_CONTR", "ESTAD_AREA", "OPERADOR"]),
    "mov_masa": ("https://srvags.sgc.gov.co/arcgis/rest/services/Mapa_Nacional_Amenaza_Mov_Masa_100K/Mapa_Nacional_Amenaza_Movimientos_Masa_100K/MapServer/3",
                 ["CATEGORIA", "SUM_BAJA", "SUM_MEDIA", "SUM_ALTA", "SUM_MUY_AL"]),
    # Figuras territoriales que el reporte de grillas usa como excluyentes, medidas ahora en
    # el polígono del lote, desde la entidad que las titula: resguardos y consejos de la ANT
    # (datos abiertos, información a 25 de junio de 2026), páramos de la capa institucional
    # del MADS. El RUNAP va por WFS de Parques Nacionales (CAPAS_WFS), que es el registro vivo.
    "resguardo": ("https://utility.arcgis.com/usrsvcs/servers/8944116ccfd34a7189c4bc44b8e19186/rest/services/DatosAbiertos/Resguardo_Indigena_Formalizado/FeatureServer/0",
                  ["NOMBRE", "PUEBLO", "ULTIMO_TIPO_ACTO_ADMIN", "ULTIMO_NUMERO_ACTO_ADMIN", "ULTIMA_FECHA_ACTO_ADMIN"]),
    "consejo_comunitario": ("https://utility.arcgis.com/usrsvcs/servers/abf2f9f6727b4073902c1f57c280d5dc/rest/services/DatosAbiertos/Consejo_Comunitario_Titulado/FeatureServer/0",
                            ["NOMBRE", "ULTIMO_TIPO_ACTO_ADMIN", "ULTIMO_NUMERO_ACTO_ADMIN", "ULTIMA_FECHA_ACTO_ADMIN"]),
    "paramo": ("https://services6.arcgis.com/hxAwRYAu9QHliJ8T/arcgis/rest/services/Ecosistema_Estrategico/FeatureServer/1",
               ["nombre", "acto_admin", "fecha_acto"]),
}
#: Servicios WFS (GeoServer) cruzados con el polígono del lote: clave -> (url, typename, campos).
CAPAS_WFS = {
    "runap": ("https://mapas.parquesnacionales.gov.co/services/pnn/ows", "pnn:runap",
              ["ap_nombre", "ap_categoria", "condicion", "organizacion", "fecha_inscrita"]),
}
#: Versión de la definición de cada capa. Al cambiar la fuente o los campos de una capa se
#: sube aquí y los lotes ya cacheados la vuelven a consultar, solo esa.
VERSION_CAPA = {"inundacion_2011": 3, "inundacion_2016": 2, "inundacion_2020_2022": 2, "runap": 2,
                "resguardo": 2, "consejo_comunitario": 2, "paramo": 2, "clase_agrologica": 2}
#: Servicios por punto (centroide).
CAPAS_PUNTO = {
    # Capacidad de uso de las tierras, multiescalar 2024: integra los levantamientos
    # 1:100.000, 1:25.000 y 1:10.000 y dice de qué estudio y año sale cada polígono.
    "clase_agrologica": ("https://mapas.igac.gov.co/server/rest/services/agrologia/capacidaddeusodelastierrasmultiescalar/MapServer/0",
                         ["UCP", "Clase", "Subclase", "Limitantes", "Estudio", "Escala", "Año"]),
    # Climatología ENSO del IDEAM (1981-2010): cómo cambia la lluvia en un Niño y en una
    # Niña típicos, y cada cuántos años vuelve la sequía meteorológica.
    "nino_precip": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Fenomeno_El_nino/MapServer/41",
                    ["gridcode", "rango", "cond"]),
    "nina_precip": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Fenomeno_La_Nina/MapServer/31",
                    ["gridcode", "rango", "cond"]),
    "sequia_retorno": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Agrometeorologia/MapServer/10",
                       ["gridcode", "rango"]),
}
#: Servicios por envolvente ampliada: clave -> (url, campos, margen en grados). Incendios de
#: la cobertura vegetal reportados por el IDEAM en ~5 km alrededor del lote.
CAPAS_RADIO = {
    "incendios_5km": ("https://visualizador.ideam.gov.co/gisserver/rest/services/Tematica/Incendios/MapServer/0",
                      ["anio", "area_total_ha", "num_eventos", "municipio"], 0.045),
}
#: Amenaza sísmica por municipio (where NOMMUN).
SISMICA_URL = "https://srvags.sgc.gov.co/arcgis/rest/services/Amenaza_Sismica/Amenaza_Sismica_Nacional/MapServer/0/query"


def _query(url: str, params: dict, intentos: int = 3) -> list[dict]:
    """Consulta con reintento: los servidores estatales fallan de forma intermitente."""
    import time
    import requests
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.get(url + "/query" if not url.endswith("/query") else url,
                             headers=UA, params={**params, "f": "json"}, timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"].get("message", "error"))
            return [f.get("attributes", {}) for f in d.get("features", [])]
        except Exception as exc:
            ultimo = exc
            time.sleep(1.5 * (i + 1))
    raise ultimo


def _bbox_query(url: str, bbox, campos: list[str]) -> list[dict]:
    minx, miny, maxx, maxy = bbox
    feats = _query(url, {"geometry": f"{minx},{miny},{maxx},{maxy}", "geometryType": "esriGeometryEnvelope",
                         "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                         "outFields": ",".join(campos) or "*", "returnGeometry": "false"})
    return [{k: v for k, v in f.items() if k in campos or not campos} for f in feats]


#: Tolerancia (m) con que se simplifica el polígono antes de enviarlo: hay predios del
#: IGAC con cientos de miles de vértices y la petición no puede llevarlos todos.
SIMPLIFICAR_M = 5.0


def anillos_esri(geom_wgs84, wkid: int = 4326, transformar=None) -> dict:
    """Polígono simplificado (SIMPLIFICAR_M) en el formato de geometría de ArcGIS REST."""
    from shapely.geometry import mapping
    from shapely.ops import transform
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 3116, always_xy=True)
    simple = transform(tr.transform, geom_wgs84).simplify(SIMPLIFICAR_M, preserve_topology=True)
    inv = Transformer.from_crs(3116, 4326, always_xy=True)
    simple = transform(inv.transform, simple)
    if transformar is not None:
        simple = transformar(simple)
    coords = mapping(simple)
    rings = coords["coordinates"] if coords["type"] == "Polygon" else [r for p in coords["coordinates"] for r in p]
    return {"rings": [[list(pt) for pt in ring] for ring in rings], "spatialReference": {"wkid": wkid}}


def _poligono_query(url: str, geom_wgs84, campos: list[str]) -> list[dict]:
    """
    Intersección con el polígono real del lote, no con su envolvente: para lo que
    excluye (minería) el envolvente daría falsos positivos con títulos vecinos.
    Devuelve los atributos más el área de solape en hectáreas. Va por POST porque la
    geometría no cabe en una URL.
    """
    import time
    import requests
    from shapely.ops import transform
    from pyproj import Transformer
    esri = anillos_esri(geom_wgs84)
    d = None
    for i in range(3):
        try:
            r = requests.post(url + "/query", headers=UA, timeout=TIMEOUT, data={
                "geometry": json.dumps(esri), "geometryType": "esriGeometryPolygon", "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(campos),
                "returnGeometry": "true", "outSR": 4326, "f": "json"})
            r.raise_for_status(); d = r.json()
            if "error" in d: raise RuntimeError(d["error"].get("message", "error"))
            break
        except Exception as exc:
            d = None; ultimo = exc
            time.sleep(1.5 * (i + 1))
    if d is None:
        raise ultimo
    tr = Transformer.from_crs(4326, 3116, always_xy=True)
    lote_m = transform(tr.transform, geom_wgs84)
    out = []
    for f in d.get("features", []):
        a = {k: v for k, v in f.get("attributes", {}).items() if k in campos}
        rings = (f.get("geometry") or {}).get("rings") or []
        try:
            from shapely.geometry import Polygon, MultiPolygon
            poly = MultiPolygon([Polygon(rg) for rg in rings if len(rg) >= 4]) if len(rings) > 1 else Polygon(rings[0])
            inter = transform(tr.transform, poly.buffer(0)).intersection(lote_m).area / 1e4
        except Exception:
            inter = None
        if inter is None or inter > 0.01:      # solape real, no un roce del envolvente
            a["solape_ha"] = round(inter, 2) if inter is not None else None
            out.append(a)
    return out


def _wfs_poligono(url: str, typename: str, geom_wgs84, campos: list[str]) -> list[dict]:
    """
    GetFeature de un WFS (GeoServer) por envolvente del lote y cruce local con el polígono
    real; devuelve atributos más el solape en hectáreas. Misma salida que _poligono_query.
    """
    import time
    import requests
    from shapely.geometry import shape
    from shapely.ops import transform
    from pyproj import Transformer
    minx, miny, maxx, maxy = geom_wgs84.bounds
    d = None
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, params={
                "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": typename,
                "outputFormat": "application/json", "srsName": "EPSG:4326",
                "bbox": f"{minx},{miny},{maxx},{maxy},EPSG:4326"})
            r.raise_for_status(); d = r.json()
            break
        except Exception as exc:
            d = None; ultimo = exc
            time.sleep(1.5 * (i + 1))
    if d is None:
        raise ultimo
    tr = Transformer.from_crs(4326, 3116, always_xy=True)
    lote_m = transform(tr.transform, geom_wgs84)
    out = []
    for f in d.get("features", []):
        a = {k: v for k, v in (f.get("properties") or {}).items() if k in campos}
        try:
            inter = transform(tr.transform, shape(f["geometry"]).buffer(0)).intersection(lote_m).area / 1e4
        except Exception:
            inter = None
        if inter is None or inter > 0.01:
            a["solape_ha"] = round(inter, 2) if inter is not None else None
            out.append(a)
    return out


def _punto_query(url: str, lon: float, lat: float, campos: list[str]) -> list[dict]:
    feats = _query(url, {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                         "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(campos),
                         "returnGeometry": "false"})
    return [{k: v for k, v in f.items() if k in campos} for f in feats]


#: Capas que deciden (excluyen): se cruzan con el polígono real, no con el envolvente.
CAPAS_POLIGONO = ("mineria_titulos", "mineria_solicitudes", "resguardo", "consejo_comunitario",
                  "paramo", "inundacion_1988", "inundacion_2000", "inundacion_2011", "inundacion_2012",
                  "inundacion_2016", "inundacion_2020_2022", "zip_2022")


def _con_error(e: dict) -> set[str]:
    return {k for k, v in e.items() if isinstance(v, dict) and "error" in v}


def consultar_lote(codigo: str, bbox, centro, municipio: str | None,
                   forzar: bool = False, geom=None) -> dict:
    """
    Todas las capas para un lote, desde caché si existe. Una capa que falló (servidor
    caído) queda anotada como error y se reintenta sola en la siguiente corrida, sin
    repetir las que sí respondieron. Devuelve dict por capa.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"{codigo}.json"
    out = {"_fecha": date.today().isoformat(), "_version": 2}
    pendientes = None
    if ruta.exists() and not forzar:
        e = json.loads(ruta.read_text(encoding="utf-8"))
        if e.get("_version") == 2 or geom is None:
            # Capas que fallaron, que se añadieron después de cachear el lote o cuya
            # definición cambió de versión (VERSION_CAPA).
            todas = list(CAPAS) + list(CAPAS_WFS) + list(CAPAS_PUNTO) + list(CAPAS_RADIO)
            vers = e.get("_versiones") or {}
            pendientes = (_con_error(e) | {k for k in todas if k not in e}
                          | {k for k in todas if vers.get(k, 1) != VERSION_CAPA.get(k, 1)})
            if not pendientes:
                return e
            out = e
    out.setdefault("_versiones", {})
    def _toca(clave):
        return pendientes is None or clave in pendientes
    for clave, (url, campos) in CAPAS.items():
        if not _toca(clave):
            continue
        try:
            if clave in CAPAS_POLIGONO and geom is not None:
                out[clave] = _poligono_query(url, geom, campos)
            else:
                out[clave] = _bbox_query(url, bbox, campos)
        except Exception as exc:
            out[clave] = {"error": type(exc).__name__}
        out["_versiones"][clave] = VERSION_CAPA.get(clave, 1)
    for clave, (url, typename, campos) in CAPAS_WFS.items():
        if not _toca(clave):
            continue
        try:
            out[clave] = _wfs_poligono(url, typename, geom, campos) if geom is not None else []
        except Exception as exc:
            out[clave] = {"error": type(exc).__name__}
        out["_versiones"][clave] = VERSION_CAPA.get(clave, 1)
    for clave, (url, campos) in CAPAS_PUNTO.items():
        if not _toca(clave):
            continue
        try:
            out[clave] = _punto_query(url, centro[0], centro[1], campos)
        except Exception as exc:
            out[clave] = {"error": type(exc).__name__}
        out["_versiones"][clave] = VERSION_CAPA.get(clave, 1)
    for clave, (url, campos, margen) in CAPAS_RADIO.items():
        if not _toca(clave):
            continue
        try:
            minx, miny, maxx, maxy = bbox
            out[clave] = _bbox_query(url, (minx - margen, miny - margen, maxx + margen, maxy + margen), campos)
        except Exception as exc:
            out[clave] = {"error": type(exc).__name__}
        out["_versiones"][clave] = VERSION_CAPA.get(clave, 1)
    if municipio and _toca("sismica"):
        try:
            out["sismica"] = _query(SISMICA_URL, {"where": f"NOMMUN='{municipio}'",
                                                  "outFields": "NIVEL,AA,AV,PGA475", "returnGeometry": "false"})
        except Exception as exc:
            out["sismica"] = {"error": type(exc).__name__}
    ruta.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _lista(x) -> list:
    return x if isinstance(x, list) else []


EPISODIOS_NINA = ("inundacion_1988", "inundacion_2000", "inundacion_2011", "inundacion_2012",
                  "inundacion_2016", "inundacion_2020_2022")


def _cond(x) -> str | None:
    """'Déficit (40 - 80)' a partir de cond y rango de las capas ENSO del IDEAM."""
    fs = _lista(x)
    if not fs:
        return None
    c = str(fs[0].get("cond") or "").strip()
    r = str(fs[0].get("rango") or "").strip()
    return r if r else (c or None)


def resumir(e: dict) -> dict:
    """Columnas planas para la tabla de lotes a partir del dict de capas."""
    dren = _lista(e.get("drenajes")) + _lista(e.get("drenajes_dobles"))
    nombres = sorted({str(d.get("nombre_geografico") or "").strip() for d in dren} - {"", "None"})
    hum = _lista(e.get("humedales"))
    tit = _lista(e.get("mineria_titulos")); sol = _lista(e.get("mineria_solicitudes"))
    hid = _lista(e.get("hidrocarburos"))
    pom = _lista(e.get("pomca")); fro = _lista(e.get("frontera_agricola"))
    agro = _lista(e.get("clase_agrologica")); mm = _lista(e.get("mov_masa")); sis = _lista(e.get("sismica"))
    def _fig(clave, nombre, extra=None):
        fs = _lista(e.get(clave))
        ha = sum(f.get("solape_ha") or 0 for f in fs)
        txt = "; ".join(f"{f.get(nombre)}" + (f" ({f.get(extra)})" if extra and f.get(extra) else "") for f in fs[:2])
        return (txt or None), (round(ha, 2) if fs else 0.0)
    runap, runap_ha = _fig("runap", "ap_nombre", "ap_categoria")
    resg, resg_ha = _fig("resguardo", "NOMBRE", "PUEBLO")
    cons, cons_ha = _fig("consejo_comunitario", "NOMBRE")
    para, para_ha = _fig("paramo", "nombre")
    return {
        "ent_runap": runap, "ent_runap_ha": runap_ha,
        "ent_resguardo": resg, "ent_resguardo_ha": resg_ha,
        "ent_consejo": cons, "ent_consejo_ha": cons_ha,
        "ent_paramo": para, "ent_paramo_ha": para_ha,
        "ent_drenajes_n": len(dren),
        "ent_drenajes": "; ".join(nombres)[:120] if nombres else ("sin nombre" if dren else ""),
        "ent_inundacion_1988": bool(_lista(e.get("inundacion_1988"))),
        "ent_inundacion_2000": bool(_lista(e.get("inundacion_2000"))),
        "ent_inundacion_2011": bool(_lista(e.get("inundacion_2011"))),
        "ent_inundacion_2012": bool(_lista(e.get("inundacion_2012"))),
        "ent_inundacion_2016": bool(_lista(e.get("inundacion_2016"))),
        "ent_inundacion_2020_2022": bool(_lista(e.get("inundacion_2020_2022"))),
        "ent_inundaciones_nina": sum(bool(_lista(e.get(k))) for k in EPISODIOS_NINA),
        "ent_inundacion_ha_max": round(max((sum(f.get("solape_ha") or 0 for f in _lista(e.get(k))) for k in EPISODIOS_NINA), default=0.0), 2),
        "ent_zip_ha": round(sum(f.get("solape_ha") or 0 for f in _lista(e.get("zip_2022"))
                                if str(f.get("zip", "")).lower().startswith("zona")), 2),
        "ent_cuerpo_agua_ha": round(sum(f.get("solape_ha") or 0 for f in _lista(e.get("zip_2022"))
                                        if str(f.get("zip", "")).lower().startswith("cuerpo")), 2),
        "ent_nino_precip": _cond(e.get("nino_precip")),
        "ent_nina_precip": _cond(e.get("nina_precip")),
        "ent_sequia_retorno": (_lista(e.get("sequia_retorno"))[0].get("rango") if _lista(e.get("sequia_retorno")) else None),
        "ent_incendios_5km": len(_lista(e.get("incendios_5km"))),
        "ent_incendios_ha_5km": round(sum(float(f.get("area_total_ha") or 0) for f in _lista(e.get("incendios_5km"))), 1),
        "ent_incendios_ultimo": max((int(f.get("anio")) for f in _lista(e.get("incendios_5km")) if f.get("anio")), default=None),
        "ent_humedal": (f"{hum[0].get('humedal', '')} {hum[0].get('grado_tran', '')}".strip()
                        if hum else ""),
        "ent_pomca": (f"{pom[0].get('nom_pomca', '')} ({pom[0].get('nom_fase', '')})" if pom else ""),
        "ent_frontera_agricola": "; ".join(sorted({str(f.get("tipo_frontera", "")) for f in fro})),
        "ent_clase_agrologica": ((agro[0].get("UCP") or agro[0].get("UCCapacida")) if agro else None),
        "ent_clase_agrologica_fuente": (f"{agro[0].get('Estudio', '')} {agro[0].get('Escala', '')} {agro[0].get('Año', '')}".strip()
                                        if agro and agro[0].get("Estudio") else None),
        "ent_mineria_titulos": len(tit),
        "ent_mineria_detalle": "; ".join(
            f"{t.get('CODIGO_EXPEDIENTE')} {t.get('MINERALES', '')}"[:50]
            + (f" ({t['solape_ha']:.0f} ha)" if t.get('solape_ha') is not None else "") for t in tit[:3]),
        "ent_mineria_solicitudes": len(sol),
        "ent_hidrocarburos": "; ".join(f"{h.get('CONTRATO_N')} {h.get('ESTAD_AREA', '')} ({h.get('OPERADOR', '')})"[:70] for h in hid[:2]),
        "ent_mov_masa": (mm[0].get("CATEGORIA") if mm else None),
        "ent_sismica": (sis[0].get("NIVEL") if sis else None),
        "ent_fecha": e.get("_fecha"),
        "ent_capas_sin_respuesta": "; ".join(sorted(_con_error(e))) or None,
    }


def enriquecer(p: pd.DataFrame, geoms=None, verbose: bool = True, hilos: int = 8) -> pd.DataFrame:
    """
    Añade las columnas ent_* a una tabla de lotes. `geoms` es una GeoSeries alineada con
    p (para bbox y centroide); si no se da, se leen de outputs/reporte/lotes_<perfil>.geojson.
    """
    import geopandas as gpd
    p = p.copy()
    if geoms is None:
        perfil = str(p["perfil"].iloc[0]) if "perfil" in p.columns and len(p) else "utility"
        g = gpd.read_file(SALIDA / f"lotes_{perfil}.geojson").to_crs(4326).set_index("CODIGO")
        geoms = g.geometry.reindex(p["CODIGO"].astype(str)).values
    tareas = []
    for (_, r), geom in zip(p.iterrows(), geoms):
        if geom is None or getattr(geom, "is_empty", True):
            tareas.append(None); continue
        c = geom.centroid
        tareas.append((str(r["CODIGO"]), geom.bounds, (c.x, c.y), r.get("municipio"), geom))
    def _una(t):
        return consultar_lote(t[0], t[1], t[2], t[3], geom=t[4]) if t else {}
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        resultados = list(ex.map(_una, tareas))
    filas = [resumir(e) for e in resultados]
    df = pd.DataFrame(filas, index=p.index)
    for c in df.columns:
        p[c] = df[c]
    if verbose:
        con = int(p["ent_fecha"].notna().sum())
        con_error = sum(1 for e in resultados if _con_error(e))
        if con_error:
            print(f"  entorno: {con_error} lotes con alguna capa sin respuesta; se reintenta "
                  f"en la próxima corrida")
        print(f"  entorno: {con} de {len(p)} lotes con capas; inundación Niña 2011 en "
              f"{int(p['ent_inundacion_2011'].sum())}, humedal en "
              f"{int((p['ent_humedal'] != '').sum())}, título minero en "
              f"{int((p['ent_mineria_titulos'] > 0).sum())}, hidrocarburos en "
              f"{int((p['ent_hidrocarburos'] != '').sum())}")
    return p


def main(argv=None) -> int:
    """CLI: enriquece los lotes de un perfil e imprime un resumen."""
    ap = argparse.ArgumentParser(description="Entorno del lote desde geoservicios públicos")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args(argv)
    ruta = SALIDA / f"lotes_{a.perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    p = pd.read_csv(ruta, dtype={"CODIGO": str})
    if a.forzar:
        for f in CACHE.glob("*.json"):
            f.unlink()
    q = enriquecer(p)
    print("=" * 74)
    print(f"ENTORNO DEL LOTE, perfil {a.perfil}")
    print("=" * 74)
    cols = ["orden", "municipio", "ent_inundacion_2011", "ent_humedal", "ent_clase_agrologica",
            "ent_mineria_titulos", "ent_hidrocarburos", "ent_mov_masa"]
    print(q[cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
