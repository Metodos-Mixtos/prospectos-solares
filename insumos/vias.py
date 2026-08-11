"""
Distancia de cada grilla candidata a la red vial, usando OpenStreetMap.

Cubre el único punto del bloque de caracterización que no se podía resolver con los
datos del bucket, porque no hay capa vial ni en geoinfo ni en el panel.

Descarga de Overpass las vías de jerarquía relevante para acceso de obra y calcula,
para cada grilla, la distancia de su centroide a la vía más cercana. Distingue dos
niveles, porque no es lo mismo llegar con un camión de transformadores que con una
camioneta:

    red primaria    motorway, trunk, primary, secondary
    red secundaria  lo anterior más tertiary y unclassified

Para no saturar el servicio hace una consulta por grupo geográfico, no una por grilla,
y cachea el resultado en data/osm/. Si ya hay caché no vuelve a descargar.

Uso:
    .venv\\Scripts\\python.exe distancia_vias.py
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import argparse
import geopandas as gpd
import hashlib
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para poder importar config y gcs, que viven
# un nivel arriba de este paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# Overpass responde 406 a las peticiones sin User-Agent propio, que es lo que manda
# requests por defecto. La política de uso de OSM pide además identificar la aplicación.
UA = "prospectos-solares/1.0 (Metodos Mixtos Consultores; prospeccion solar Colombia)"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
CACHE = config.PROJECT_ROOT / "data" / "osm"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

PRIMARIA = ["motorway", "trunk", "primary", "secondary"]
SECUNDARIA = PRIMARIA + ["tertiary", "unclassified"]

# Un bbox por grilla, no por departamento. Un bbox departamental con holgura cubre
# decenas de miles de km² y Overpass encola la petición hasta agotar el tiempo.
# Con ±0,08° se cubren unos 9 km alrededor de una grilla de 5 km, de sobra para
# encontrar la vía más cercana, y la consulta vuelve en segundos.
MARGEN = 0.08
# Con 10 bbox por consulta la petición supera el tiempo de cómputo que concede
# Overpass y responde 400. Con 4 vuelve en unos 30 segundos.
LOTE = 4
PAUSA = 3              # segundos entre consultas, por cortesía con el servicio


def lotes(g: gpd.GeoDataFrame, tam: int = LOTE):
    """Parte las grillas en lotes de índices para consultar en bloque."""
    idx = list(range(len(g)))
    for i in range(0, len(idx), tam):
        yield i // tam + 1, idx[i:i + tam]


def bbox_de(g: gpd.GeoDataFrame, i: int) -> tuple[float, float, float, float]:
    """
    Bbox de una grilla en el orden que espera Overpass: sur, oeste, norte, este.

    Ojo: g tiene que venir en grados. Las candidatas salen del notebook 1 en EPSG:32618,
    en metros, y pasarle metros a Overpass devuelve un 400 sin explicar por qué.
    """
    if g.crs is not None and g.crs.is_projected:
        raise ValueError("bbox_de necesita coordenadas geográficas, no proyectadas")
    minx, miny, maxx, maxy = g.iloc[[i]].total_bounds
    return (miny - MARGEN, minx - MARGEN, maxy + MARGEN, maxx + MARGEN)


def clave_lote(bboxes) -> str:
    """
    Nombre del archivo de caché, derivado de los bbox consultados.

    Va por contenido y no por número de lote a propósito. Con el nombre secuencial,
    correr el reporte sobre otras candidatas leía el lote_1.json de las anteriores y
    devolvía distancias de celdas que no eran, sin dar ningún error. Con el hash del
    bbox, un conjunto distinto de celdas produce un nombre distinto y el caché solo
    responde a lo que de verdad se le preguntó.
    """
    firma = ";".join(f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}" for (s, w, n, e) in bboxes)
    return hashlib.sha1(firma.encode()).hexdigest()[:12]


def consultar_lote(bboxes, tipos, etiqueta=None) -> dict:
    """Pide en una sola consulta las vías de varios bbox. Cachea el resultado crudo."""
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"vias_{clave_lote(bboxes)}.json"

    if destino.exists():
        with open(destino, encoding="utf-8") as fh:
            return json.load(fh)

    filtro = "|".join(tipos)
    partes = "".join(
        f'way["highway"~"^({filtro})$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});'
        for (s, w, n, e) in bboxes
    )
    query = f"[out:json][timeout:180];({partes});out geom;"

    data, fallos = None, []
    for url in ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query},
                              headers={"User-Agent": UA}, timeout=240)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:
            fallos.append(f"{url.split('//')[1].split('/')[0]}: {type(exc).__name__}")
            time.sleep(PAUSA)
    if data is None:
        raise RuntimeError("; ".join(fallos))

    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    time.sleep(PAUSA)
    return data


def a_lineas(data: dict, solo: list[str] | None = None) -> list[LineString]:
    """Convierte la respuesta de Overpass en geometrías, filtrando por jerarquía."""
    lineas = []
    for el in data.get("elements", []):
        if solo and el.get("tags", {}).get("highway") not in solo:
            continue
        geom = el.get("geometry") or []
        if len(geom) >= 2:
            lineas.append(LineString([(p["lon"], p["lat"]) for p in geom]))
    return lineas


def distancias(centroides: gpd.GeoSeries, lineas: list[LineString]) -> np.ndarray:
    """Distancia en km de cada centroide a la línea más cercana, en CRS métrico."""
    if not lineas:
        return np.full(len(centroides), np.nan)
    red = gpd.GeoSeries(lineas, crs=config.CRS_GEOGRAFICO).to_crs(config.CRS_METRICO)
    union = red.union_all()
    pts = centroides.to_crs(config.CRS_METRICO)
    return np.array([p.distance(union) / 1000 for p in pts])


def calcular(g: gpd.GeoDataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Distancia a vía de las celdas que se le pasen. Devuelve cell_id y las dos columnas.

    Está separada de main() para que reporte_grillas.py la llame con el GeoDataFrame
    que tenga en memoria. Así no hay que acordarse de correr los scripts en un orden
    concreto ni de borrar un CSV viejo cuando cambian las candidatas.
    """
    gw = g.to_crs(config.CRS_GEOGRAFICO).reset_index(drop=True)
    cent = gpd.GeoSeries(gw.geometry.centroid, crs=gw.crs)
    d_pri = np.full(len(gw), np.nan)
    d_sec = np.full(len(gw), np.nan)

    total_lotes = (len(gw) + LOTE - 1) // LOTE
    if verbose:
        print(f"  consultas a Overpass: {total_lotes} lotes de hasta {LOTE} grillas\n")

    for num, idx in lotes(gw):
        bboxes = [bbox_de(gw, i) for i in idx]
        if verbose:
            print(f"  lote {num}/{total_lotes} ({len(idx)} grillas)...", end=" ", flush=True)
        try:
            data = consultar_lote(bboxes, SECUNDARIA)
        except Exception as exc:
            # Se avisa siempre, también en silencioso. Overpass limita por ráfaga y un
            # lote perdido deja celdas sin el criterio; callarlo hace que el índice
            # cambie sin que nadie sepa por qué.
            print(f"{'' if verbose else '    lote sin respuesta, '}"
                  f"error: {type(exc).__name__}: {str(exc)[:90]}", flush=True)
            continue

        sec = a_lineas(data)
        pri = a_lineas(data, solo=PRIMARIA)

        # Cada grilla se mide solo contra las vías de su entorno, no contra las del
        # lote entero, que puede incluir grillas a cientos de km.
        for i in idx:
            bs, bw, bn, be = bbox_de(gw, i)
            cerca_s = [ln for ln in sec if ln.bounds[0] <= be and ln.bounds[2] >= bw
                       and ln.bounds[1] <= bn and ln.bounds[3] >= bs]
            cerca_p = [ln for ln in pri if ln.bounds[0] <= be and ln.bounds[2] >= bw
                       and ln.bounds[1] <= bn and ln.bounds[3] >= bs]
            uno = cent.iloc[[i]]
            d_sec[i] = distancias(uno, cerca_s)[0]
            d_pri[i] = distancias(uno, cerca_p)[0]

        if verbose:
            print(f"{len(sec)} tramos   media {np.nanmean(d_sec[idx]):.2f} km", flush=True)

    return pd.DataFrame({
        "cell_id": gw["cell_id"].astype(str).values,
        "dist_via_km": np.round(d_sec, 2),
        "dist_via_principal_km": np.round(d_pri, 2),
    })


def _celdas_por_defecto() -> Path:
    """El insumo del modelo primero; el reporte ya generado como alternativa."""
    for cand in (config.TOP_CANDIDATOS_PATH, SALIDA / "grillas_candidatas.gpkg"):
        if cand.exists():
            return cand
    raise SystemExit("No encuentro top_candidates.gpkg ni grillas_candidatas.gpkg")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--celdas", help="gpkg o geojson de celdas; por defecto top_candidates")
    a = ap.parse_args(argv)
    ruta = Path(a.celdas) if a.celdas else _celdas_por_defecto()
    if not ruta.is_absolute():
        ruta = config.PROJECT_ROOT / ruta
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}")

    # Antes de molestar a Overpass, mirar si el equipo ya publicó estas respuestas.
    # Bajarlas del bucket tarda segundos; volver a descargarlas, veinte minutos.
    try:
        from . import asegurar
        n = asegurar("osm_vias")
        if n:
            print(f"  recuperadas {n} respuestas de Overpass desde el bucket")
    except Exception:
        pass

    g = gpd.read_file(ruta)
    print("=" * 74)
    print("DISTANCIA A VÍA  ·  OpenStreetMap")
    print("=" * 74)
    print(f"  grillas: {len(g)}   fuente: {ruta.name}")
    print(f"  CRS de entrada: {g.crs.to_string() if g.crs else 'sin CRS'}")

    res = calcular(g)
    SALIDA.mkdir(parents=True, exist_ok=True)
    res.to_csv(SALIDA / "distancia_vias.csv", index=False, encoding="utf-8-sig")
    print(f"\n  CSV -> {SALIDA / 'distancia_vias.csv'}")

    print()
    print("-" * 74)
    print("RESULTADO")
    print("-" * 74)
    ok = np.isfinite(res["dist_via_km"])
    print(f"  con dato: {ok.sum()} de {len(res)}")
    if ok.sum():
        print(f"  a vía carrozable   min {res['dist_via_km'].min():.2f}  "
              f"media {res['dist_via_km'].mean():.2f}  max {res['dist_via_km'].max():.2f} km")
        print(f"  a vía principal    min {res['dist_via_principal_km'].min():.2f}  "
              f"media {res['dist_via_principal_km'].mean():.2f}  "
              f"max {res['dist_via_principal_km'].max():.2f} km")
        print()
        print("  Reparto por cercanía a vía carrozable")
        cortes = pd.cut(res["dist_via_km"], [0, 0.5, 1, 2, 5, 999],
                        labels=["< 0,5 km", "0,5 a 1", "1 a 2", "2 a 5", "> 5 km"])
        print(cortes.value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
