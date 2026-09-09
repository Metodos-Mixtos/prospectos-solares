"""
Variables de la grilla medidas en el lote: recurso solar del punto (Global Solar Atlas,
API de largo plazo, 250 m), distancia desde el lindero a la línea de transmisión más
cercana (OSM, insumos/lineas) y al centro poblado y caserío más cercanos (nodos place de
OSM por Overpass, cacheados por grilla en data/poblados/). Las figuras territoriales
(RUNAP, resguardos, consejos comunitarios, páramos) van en entorno.py. Caché por lote en
data/contexto/. Uso: python -m predios.contexto [--perfil utility]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
CACHE = config.PROJECT_ROOT / "data" / "contexto"
CACHE_POBLADOS = config.PROJECT_ROOT / "data" / "poblados"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}

#: Recurso solar de largo plazo en un punto (Solargis para el Global Solar Atlas).
GSA_URL = "https://api.globalsolaratlas.info/data/lta"
GSA_CAMPOS = {"PVOUT_csi": "pvout", "GHI": "ghi", "DNI": "dni", "DIF": "dif",
              "GTI_opta": "gti", "OPTA": "opta", "TEMP": "temp", "ELE": "ele"}

#: Overpass: nodos place alrededor de la grilla. Radio en grados (~25 km).
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter")
RADIO_POBLADOS = 0.25
POBLADO = ("city", "town", "village")
CASERIO = ("hamlet",)


def recurso_punto(codigo: str, lon: float, lat: float, forzar: bool = False) -> dict:
    """Capas anuales del GSA en el punto, cacheadas por lote."""
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"{codigo}.json"
    if ruta.exists() and not forzar:
        e = json.loads(ruta.read_text(encoding="utf-8"))
        if "error" not in e and all(v in e for v in GSA_CAMPOS.values()):
            return e
    import requests
    out = {"_fecha": date.today().isoformat()}
    for i in range(3):
        try:
            r = requests.get(GSA_URL, params={"loc": f"{lat:.5f},{lon:.5f}"}, headers=UA, timeout=45)
            r.raise_for_status()
            datos = (r.json().get("annual") or {}).get("data") or {}
            for k, v in GSA_CAMPOS.items():
                out[v] = datos.get(k)
            break
        except Exception as exc:
            out["error"] = type(exc).__name__
            time.sleep(1.5 * (i + 1))
    ruta.write_text(json.dumps(out), encoding="utf-8")
    return out


def poblados_celda(cell_id: str, bbox, forzar: bool = False) -> list[dict]:
    """Nodos place de OSM alrededor de la grilla: [{nombre, tipo, lon, lat}], cacheados."""
    CACHE_POBLADOS.mkdir(parents=True, exist_ok=True)
    ruta = CACHE_POBLADOS / f"poblados_{cell_id}.json"
    if ruta.exists() and not forzar:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    else:
        import requests
        minx, miny, maxx, maxy = bbox
        s, w, n, e = miny - RADIO_POBLADOS, minx - RADIO_POBLADOS, maxy + RADIO_POBLADOS, maxx + RADIO_POBLADOS
        tipos = "|".join(POBLADO + CASERIO)
        query = f'[out:json][timeout:120];node["place"~"^({tipos})$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});out;'
        data = None
        for url in OVERPASS:
            try:
                r = requests.post(url, data={"data": query}, headers=UA, timeout=180)
                r.raise_for_status()
                data = r.json()
                break
            except Exception:
                time.sleep(3)
        if data is None:
            return []
        ruta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return [{"nombre": el.get("tags", {}).get("name"), "tipo": el.get("tags", {}).get("place"),
             "lon": el["lon"], "lat": el["lat"]} for el in data.get("elements", []) if "lat" in el]


def _lineas():
    """Líneas de transmisión (OSM) como GeoSeries métrica, desde el JSON del reporte."""
    import geopandas as gpd
    from shapely.geometry import LineString
    ruta = SALIDA / "lineas_transmision.json"
    if not ruta.exists():
        return None
    d = json.loads(ruta.read_text(encoding="utf-8"))
    geoms = [LineString(x["coords"]) for x in d if len(x.get("coords", [])) >= 2]
    kv = [x.get("kv") for x in d if len(x.get("coords", [])) >= 2]
    g = gpd.GeoDataFrame({"kv": kv}, geometry=geoms, crs=config.CRS_GEOGRAFICO)
    return g.to_crs(config.CRS_METRICO)


def enriquecer(p: pd.DataFrame, geoms, celdas=None, verbose: bool = True, hilos: int = 8) -> pd.DataFrame:
    """
    Añade ctx_pvout, ctx_ghi, ctx_dni, ctx_dif, ctx_gti, ctx_opta, ctx_temp, ctx_ele (GSA en el centroide),
    ctx_linea_km y ctx_linea_kv (línea más cercana al lindero), ctx_poblado, ctx_poblado_tipo,
    ctx_poblado_km, ctx_caserio y ctx_caserio_km. `geoms` alineada con p, WGS84.
    """
    import geopandas as gpd
    from shapely.geometry import Point
    p = p.copy()
    gs = gpd.GeoSeries(list(geoms), crs=config.CRS_GEOGRAFICO)
    gm = gs.to_crs(config.CRS_METRICO)
    cent = gm.centroid.to_crs(config.CRS_GEOGRAFICO)

    # recurso solar del punto
    tareas = [(str(c), x, y) for c, x, y in zip(p["CODIGO"], cent.x, cent.y)]
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        res = list(ex.map(lambda t: recurso_punto(*t), tareas))
    for k in GSA_CAMPOS.values():
        p[f"ctx_{k}"] = [r.get(k) for r in res]

    # línea de transmisión más cercana
    li = _lineas()
    if li is not None and len(li):
        sidx = li.sindex
        km, kv = [], []
        for g in gm.values:
            i = sidx.nearest(g, return_all=False)[1][0]
            km.append(round(li.geometry.iloc[i].distance(g) / 1000, 2))
            v = li["kv"].iloc[i]
            kv.append(int(v / 1000) if v else None)
        p["ctx_linea_km"], p["ctx_linea_kv"] = km, kv
    else:
        p["ctx_linea_km"], p["ctx_linea_kv"] = np.nan, None

    # centro poblado y caserío más cercanos, por grilla
    cols = {"ctx_poblado": [], "ctx_poblado_tipo": [], "ctx_poblado_km": [], "ctx_caserio": [], "ctx_caserio_km": []}
    cache_nodos = {}
    for (cid, g) in zip(p["cell_id"].astype(str), gm.values):
        if cid not in cache_nodos:
            b = gs[p["cell_id"].astype(str).values == cid].total_bounds
            nodos = poblados_celda(cid, b)
            nd = gpd.GeoDataFrame(nodos, geometry=[Point(n["lon"], n["lat"]) for n in nodos],
                                  crs=config.CRS_GEOGRAFICO).to_crs(config.CRS_METRICO) if nodos else None
            cache_nodos[cid] = nd
        nd = cache_nodos[cid]
        for tipos, k_nom, k_km, k_tipo in ((POBLADO, "ctx_poblado", "ctx_poblado_km", "ctx_poblado_tipo"),
                                           (CASERIO, "ctx_caserio", "ctx_caserio_km", None)):
            sub = nd[nd["tipo"].isin(tipos)] if nd is not None else None
            if sub is None or not len(sub):
                cols[k_nom].append(None); cols[k_km].append(np.nan)
                if k_tipo: cols[k_tipo].append(None)
                continue
            d = sub.geometry.distance(g)
            j = int(d.values.argmin())
            cols[k_nom].append(sub["nombre"].iloc[j]); cols[k_km].append(round(float(d.iloc[j]) / 1000, 2))
            if k_tipo: cols[k_tipo].append(sub["tipo"].iloc[j])
    for k, v in cols.items():
        p[k] = v

    if verbose:
        con = int(pd.notna(p["ctx_pvout"]).sum())
        print(f"  contexto: recurso GSA en {con} de {len(p)} lotes; línea a "
              f"{p['ctx_linea_km'].median():.1f} km (mediana); poblado a "
              f"{p['ctx_poblado_km'].median():.1f} km (mediana)")
    return p


def main(argv=None) -> int:
    """CLI: enriquece los lotes de un perfil e imprime un resumen."""
    import geopandas as gpd
    ap = argparse.ArgumentParser(description="Variables de la grilla medidas en el lote")
    ap.add_argument("--perfil", default="utility")
    a = ap.parse_args(argv)
    ruta = SALIDA / f"lotes_{a.perfil}.geojson"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    g = gpd.read_file(ruta).to_crs(config.CRS_GEOGRAFICO)
    q = enriquecer(g, g.geometry.values)
    pd.set_option("display.width", 160)
    print(q[["CODIGO", "municipio", "ctx_pvout", "ctx_linea_km", "ctx_linea_kv",
             "ctx_poblado", "ctx_poblado_km"]].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
