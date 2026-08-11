"""
Contraste de la capa de subestaciones contra OpenStreetMap.

POR QUÉ
-------
La capa que usa el proyecto, `Colombia/Energia_electrica/Subestaciones.geojson`, es un
inventario con enfoque de licenciamiento ambiental: sus campos son licencia ambiental,
plan de manejo y convenio UPME. Sus vigencias van de 2017 a 2021, 159 de sus 499
registros no traen fecha, y la última entrada en operación que registra es de noviembre
de 2020.

Eso importa porque la distancia al punto de conexión es el criterio de mayor peso del
índice de aptitud. Si hay subestaciones posteriores a 2020 que no están en la capa,
puede que estemos midiendo contra una red incompleta.

Las fuentes oficiales no se dejan consultar desde aquí. La API de XM solo publica
operación del mercado, no inventario. El listado de Datos Abiertos, actualizado en
agosto de 2024, responde 403 al acceso programático. El servidor de la UPME tiene el
certificado TLS roto. Queda OSM, que no es oficial pero sí está vivo, y sirve para
responder la pregunta práctica: ¿falta algo, y ese algo cambia alguna decisión?

Uso:
    .venv\\Scripts\\python.exe -m calibracion subestaciones
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para poder importar config y gcs, que viven
# un nivel arriba de este paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

UA = "prospectos-solares/1.0 (Metodos Mixtos Consultores; prospeccion solar Colombia)"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
CACHE = config.PROJECT_ROOT / "data" / "subestaciones_osm"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

LON0, LON1 = -79.3, -66.6
LAT0, LAT1 = -4.4, 13.7
COLUMNAS, FILAS = 3, 4
PAUSA = 3
#: Por debajo de 50 kV es distribución, y ahí OSM tiene una cobertura muy desigual.
VOLTAJE_MINIMO = 50_000
#: Dos subestaciones a menos de esta distancia se consideran la misma instalación.
RADIO_COINCIDENCIA_M = 1500


def malla():
    dw = (LON1 - LON0) / COLUMNAS
    dh = (LAT1 - LAT0) / FILAS
    return [(LAT0 + f * dh, LON0 + c * dw, LAT0 + (f + 1) * dh, LON0 + (c + 1) * dw)
            for f in range(FILAS) for c in range(COLUMNAS)]


def consultar(bbox, etiqueta: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"subest_{etiqueta}.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))

    s, w, n, e = bbox
    # nwr recoge nodos, vías y relaciones: una subestación puede ser cualquiera de las tres
    query = (f'[out:json][timeout:180];'
             f'nwr["power"="substation"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});'
             f'out center tags;')

    data, fallos = None, []
    for url in ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query},
                              headers={"User-Agent": UA}, timeout=240)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:
            fallos.append(type(exc).__name__)
            time.sleep(PAUSA)
    if data is None:
        raise RuntimeError("; ".join(fallos))

    destino.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(PAUSA)
    return data


def _kv(tags: dict):
    v = tags.get("voltage")
    if not v:
        return None
    vals = []
    for t in str(v).replace(",", ";").split(";"):
        try:
            vals.append(int(float(t.strip())))
        except ValueError:
            pass
    return max(vals) if vals else None


def descargar() -> gpd.GeoDataFrame:
    bloques = malla()
    print(f"  malla {COLUMNAS}x{FILAS} = {len(bloques)} bloques")
    vistos, filas = set(), []
    for i, b in enumerate(bloques, 1):
        print(f"  bloque {i:>2}/{len(bloques)}...", end=" ", flush=True)
        try:
            data = consultar(b, str(i))
        except Exception as exc:
            print(f"error: {str(exc)[:50]}")
            continue
        nuevos = 0
        for el in data.get("elements", []):
            clave = (el.get("type"), el.get("id"))
            if clave in vistos:
                continue
            tags = el.get("tags", {})
            kv = _kv(tags)
            if kv is not None and kv < VOLTAJE_MINIMO:
                continue
            if el.get("type") == "node":
                lon, lat = el.get("lon"), el.get("lat")
            else:
                c = el.get("center") or {}
                lon, lat = c.get("lon"), c.get("lat")
            if lon is None or lat is None:
                continue
            vistos.add(clave)
            filas.append({"nombre": tags.get("name") or "Sin nombre", "kv": kv,
                          "operador": tags.get("operator"),
                          "geometry": Point(lon, lat)})
            nuevos += 1
        print(f"{nuevos} nuevas")

    return gpd.GeoDataFrame(filas, geometry="geometry", crs=config.CRS_GEOGRAFICO)


def main() -> int:
    print("=" * 78)
    print("SUBESTACIONES  ·  contraste de la capa del proyecto contra OpenStreetMap")
    print("=" * 78)

    osm = descargar()
    if osm.empty:
        print("\nNo se obtuvo ninguna subestación de OSM.")
        return 1

    ofi = gpd.read_file(config.SUBESTACIONES_PATH)
    if ofi.crs is None:
        ofi = ofi.set_crs(config.CRS_GEOGRAFICO)

    m_osm = osm.to_crs(config.CRS_METRICO)
    m_ofi = ofi.to_crs(config.CRS_METRICO)

    # Cuáles de OSM no tienen pareja en la capa del proyecto
    j = gpd.sjoin_nearest(m_osm, m_ofi[["geometry"]], how="left", distance_col="_d")
    j = j[~j.index.duplicated(keep="first")]
    nuevas = j[j["_d"] > RADIO_COINCIDENCIA_M].copy()

    print()
    print("-" * 78)
    print("COMPARACIÓN")
    print("-" * 78)
    print(f"  capa del proyecto      : {len(ofi)}")
    print(f"  OSM, 50 kV o más       : {len(osm)}")
    print(f"  con pareja a menos de {RADIO_COINCIDENCIA_M} m : {len(j) - len(nuevas)}")
    print(f"  en OSM y no en la capa : {len(nuevas)}")

    if len(nuevas):
        print("\n  por tensión declarada en OSM:")
        print(nuevas["kv"].value_counts(dropna=False).head(8).to_string())

    # ¿Cambia la distancia de alguna candidata?
    ruta = SALIDA / "grillas_candidatas.gpkg"
    if not ruta.exists():
        print("\n  (sin candidatas para contrastar)")
        return 0

    g = gpd.read_file(ruta).to_crs(config.CRS_METRICO)
    cent = gpd.GeoDataFrame(geometry=g.geometry.centroid, crs=g.crs)

    d_ofi = cent.geometry.apply(lambda p: m_ofi.distance(p).min() / 1000)
    todas = pd.concat([m_ofi[["geometry"]], m_osm[["geometry"]]], ignore_index=True)
    d_todo = cent.geometry.apply(lambda p: todas.distance(p).min() / 1000)

    g["km_actual"] = d_ofi.values.round(2)
    g["km_con_osm"] = d_todo.values.round(2)
    g["mejora_km"] = (g["km_actual"] - g["km_con_osm"]).round(2)

    cambian = g[g["mejora_km"] > 0.5].sort_values("mejora_km", ascending=False)

    print()
    print("-" * 78)
    print("IMPACTO EN LAS CANDIDATAS")
    print("-" * 78)
    print(f"  distancia media actual        : {g['km_actual'].mean():.2f} km")
    print(f"  distancia media sumando OSM   : {g['km_con_osm'].mean():.2f} km")
    print(f"  celdas que acortan más de 500 m: {len(cambian)} de {len(g)}")

    if len(cambian):
        print()
        print(cambian.head(12)[["cell_id", "departamento", "clasificacion",
                                "km_actual", "km_con_osm", "mejora_km"]].to_string(index=False))

        # ¿alguna cruzaría el umbral de 15 km que define el objetivo del criterio?
        cruza = cambian[(cambian["km_actual"] > 15) & (cambian["km_con_osm"] <= 15)]
        print(f"\n  cruzan el objetivo de 15 km: {len(cruza)}")
        if len(cruza):
            print(cruza[["cell_id", "departamento", "km_actual", "km_con_osm"]].to_string(index=False))

    SALIDA.mkdir(parents=True, exist_ok=True)
    osm.to_file(SALIDA / "subestaciones_osm.gpkg", driver="GPKG")
    g[["cell_id", "km_actual", "km_con_osm", "mejora_km"]].to_csv(
        SALIDA / "contraste_subestaciones.csv", index=False, encoding="utf-8-sig")
    print(f"\n  GPKG -> {SALIDA / 'subestaciones_osm.gpkg'}")
    print(f"  CSV  -> {SALIDA / 'contraste_subestaciones.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
