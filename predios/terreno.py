"""
Pendiente, rugosidad, elevación y cobertura del suelo medidas dentro de cada predio,
no con el agregado de celda del panel (en 0011452 los predios van de 0,12° a 7,52°).

Fuentes abiertas leídas por ventana (COG): Copernicus DEM GLO-30 (30 m; es DSM, la
copa del bosque añade pendiente y por eso no descarta sola) y ESA WorldCover 2021
(10 m). Recortes por celda cacheados en data/dem/ y data/cobertura/, fuera del bucket.

Entrada: outputs/reporte/predios.gpkg y grillas_candidatas.gpkg. Salida: DataFrame
de métricas por predio (metricas / metricas_celda); la CLI imprime un resumen.

Uso:
    .venv\\Scripts\\python.exe -m predios.terreno [--celdas 0011452,...] [--forzar]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
# La raiz y soporte/ van al path: config y gcs viven en soporte/.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]

# Sin EMPTY_DIR, GDAL lista el directorio remoto en cada apertura y la primera
# lectura sobre S3 tarda diez veces más.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import calculate_default_transform, reproject
from rasterio.windows import from_bounds

import config

CACHE_DEM = config.PROJECT_ROOT / "data" / "dem"
CACHE_COB = config.PROJECT_ROOT / "data" / "cobertura"

DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/"
           "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
           "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
COB_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
           "ESA_WorldCover_10m_2021_v200_{ns}{lat:02d}{ew}{lon:03d}_Map.tif")

RES_DEM = 30.0      # m, la nativa del GLO-30 en el ecuador
RES_COB = 10.0      # m, la nativa de WorldCover
MARGEN = 300.0      # m de holgura alrededor de la celda, para el gradiente del borde

#: Aptitud de cada clase de WorldCover, de 0 a 1. Mismos coeficientes que
#: reporte_grillas.APTITUD_COBERTURA (clases ESRI), clase a clase: matorral y pastizal
#: toman el 1,00 del "rangeland"; manglar (Decreto 1076 de 2015) y musgo (páramo), 0.
APTITUD_WORLDCOVER = {
    10: 0.00,    # bosque: aprovechamiento forestal, licencia y compensación
    20: 1.00,    # matorral: terreno abierto
    30: 1.00,    # pastizal: terreno abierto, nada que retirar
    40: 0.70,    # cultivo: apto y frecuente, con riesgo de restricción del POT
    50: 0.00,    # construido: no disponible y con la propiedad fragmentada
    60: 0.80,    # suelo desnudo: abierto, pero puede ser roca o arena
    70: 0.00,    # nieve y hielo
    80: 0.00,    # agua permanente
    90: 0.00,    # humedal herbáceo: ronda hídrica y riesgo
    95: 0.00,    # manglar
    100: 0.00,   # musgo y liquen
}

NOMBRE_WORLDCOVER = {
    10: "bosque", 20: "matorral", 30: "pastizal", 40: "cultivo", 50: "construido",
    60: "suelo desnudo", 70: "nieve", 80: "agua", 90: "humedal", 95: "manglar",
    100: "musgo",
}

#: Sufijo de la columna que guarda cada clase: cob_<sufijo>_pct. Se guardan las once
#: clases que publica la capa, sin excepción, porque el reporte de lotes describe la
#: cobertura clase a clase y una clase que no se guarda no se puede describir.
SUFIJO_WORLDCOVER = {
    10: "bosque", 20: "matorral", 30: "pastizal", 40: "cultivo", 50: "construido",
    60: "desnudo", 70: "nieve", 80: "agua", 90: "humedal", 95: "manglar",
    100: "musgo",
}


# --------------------------------------------------------------------------
# Localización de las teselas
# --------------------------------------------------------------------------

def _tesela_dem(lat: float, lon: float) -> str:
    la, lo = math.floor(lat), math.floor(lon)
    return DEM_URL.format(ns="N" if la >= 0 else "S", lat=abs(la),
                          ew="E" if lo >= 0 else "W", lon=abs(lo))


def _tesela_cob(lat: float, lon: float) -> str:
    """WorldCover va en teselas de 3 x 3 grados ancladas en múltiplos de 3."""
    la = math.floor(lat / 3) * 3
    lo = math.floor(lon / 3) * 3
    return COB_URL.format(ns="N" if la >= 0 else "S", lat=abs(la),
                          ew="E" if lo >= 0 else "W", lon=abs(lo))


def _teselas_de(bounds_wgs84, cual: str) -> list[str]:
    """Todas las teselas que tocan un bbox. Una celda puede caer sobre dos."""
    x0, y0, x1, y1 = bounds_wgs84
    fn = _tesela_dem if cual == "dem" else _tesela_cob
    urls = []
    paso = 1.0 if cual == "dem" else 3.0
    y = math.floor(y0 / paso) * paso
    while y <= y1:
        x = math.floor(x0 / paso) * paso
        while x <= x1:
            u = fn(y + paso / 2, x + paso / 2)
            if u not in urls:
                urls.append(u)
            x += paso
        y += paso
    return urls


# --------------------------------------------------------------------------
# Recorte y caché
# --------------------------------------------------------------------------

def _recortar(celda: str, bounds_wgs84, cual: str, forzar: bool = False):
    """
    Devuelve (array, transform) del recorte de la celda en CRS métrico, desde caché o del
    servicio. Se reproyecta a metros aquí para que la pendiente se calcule sobre una malla
    de paso constante; en grados el paso en x y en y difiere y el gradiente sale sesgado.
    """
    carpeta = CACHE_DEM if cual == "dem" else CACHE_COB
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{cual}_{celda}.tif"

    if destino.exists() and not forzar:
        with rasterio.open(destino) as s:
            return s.read(1), s.transform

    res = RES_DEM if cual == "dem" else RES_COB
    resamp = Resampling.bilinear if cual == "dem" else Resampling.nearest
    dtype = "float32" if cual == "dem" else "uint8"

    # Holgura en grados, aproximada; cubre el gradiente del borde y los predios que sobresalen.
    dg = MARGEN / 111_000.0
    x0, y0, x1, y1 = bounds_wgs84
    bb = (x0 - dg, y0 - dg, x1 + dg, y1 + dg)

    trozos = []
    for url in _teselas_de(bb, cual):
        try:
            with rasterio.open("/vsicurl/" + url) as s:
                w = from_bounds(*bb, s.transform).round_offsets().round_lengths()
                w = w.intersection(rasterio.windows.Window(0, 0, s.width, s.height))
                if w.width < 1 or w.height < 1:
                    continue
                a = s.read(1, window=w)
                t = s.window_transform(w)
                trozos.append((a, t, s.crs, s.nodata))
        except Exception as exc:
            raise RuntimeError(f"{cual}: no se pudo leer {url.rsplit('/', 1)[-1]}: "
                               f"{type(exc).__name__}") from exc

    if not trozos:
        raise RuntimeError(f"{cual}: ninguna tesela cubre la celda {celda}")

    # Malla de destino en metros, común a todos los trozos
    dst_crs = config.CRS_METRICO
    tr, ancho, alto = calculate_default_transform(
        trozos[0][2], dst_crs, 1, 1, *bb, resolution=res)
    salida = np.zeros((alto, ancho), dtype=dtype)

    for a, t, crs, nod in trozos:
        parcial = np.zeros((alto, ancho), dtype=dtype)
        reproject(source=a, destination=parcial,
                  src_transform=t, src_crs=crs, src_nodata=nod,
                  dst_transform=tr, dst_crs=dst_crs, resampling=resamp)
        salida = np.where(salida == 0, parcial, salida)

    perfil = {"driver": "GTiff", "height": alto, "width": ancho, "count": 1,
              "dtype": dtype, "crs": dst_crs, "transform": tr, "compress": "deflate"}
    with rasterio.open(destino, "w", **perfil) as d:
        d.write(salida, 1)
    return salida, tr


# --------------------------------------------------------------------------
# Estadísticos por predio
# --------------------------------------------------------------------------

def _pendiente(dem: np.ndarray, res: float) -> np.ndarray:
    """Pendiente en grados por diferencias centradas (método de Horn simplificado)."""
    dy, dx = np.gradient(dem.astype("float64"), res, res)
    return np.degrees(np.arctan(np.hypot(dx, dy)))


def _etiquetas(predios_m: gpd.GeoDataFrame, forma, transform) -> np.ndarray:
    """
    Rasteriza los predios con un entero por predio para agregar con bincount en una
    pasada (con 1.163 predios pasa de minutos a menos de un segundo).
    """
    pares = [(g, i + 1) for i, g in enumerate(predios_m.geometry)]
    return rasterize(pares, out_shape=forma, transform=transform,
                     fill=0, dtype="int32", all_touched=False)


def _por_etiqueta(lab: np.ndarray, valores: np.ndarray, n: int):
    """Suma, conteo y suma de cuadrados por etiqueta."""
    plano = lab.ravel()
    v = valores.ravel()
    cnt = np.bincount(plano, minlength=n + 1)[1:]
    suma = np.bincount(plano, weights=v, minlength=n + 1)[1:]
    sq = np.bincount(plano, weights=v * v, minlength=n + 1)[1:]
    return cnt, suma, sq


def metricas_celda(celda: str, predios: gpd.GeoDataFrame, geom_celda_wgs84,
                   forzar: bool = False) -> pd.DataFrame:
    """
    Pendiente, rugosidad, elevación y cobertura de cada predio de una celda. Devuelve un
    DataFrame con el índice de `predios`; NaN si ningún píxel cae dentro (a 30 m, < 0,09 ha).
    """
    if predios.empty:
        return pd.DataFrame(index=predios.index)

    pm = predios.to_crs(config.CRS_METRICO)
    n = len(pm)
    res = {}

    # --- relieve ---
    dem, tr = _recortar(celda, geom_celda_wgs84.bounds, "dem", forzar)
    lab = _etiquetas(pm, dem.shape, tr)
    pend = _pendiente(dem, RES_DEM)

    cnt, suma, _sq = _por_etiqueta(lab, pend, n)
    con = cnt > 0
    media = np.where(con, suma / np.maximum(cnt, 1), np.nan)
    res["pendiente_media"] = np.round(media, 2)

    # Percentil 90 exacto, no media + 1,28 sigma: la distribución de pendientes en un
    # predio no es normal (masa cerca de cero y cola larga).
    dentro = lab.ravel() > 0
    p90 = np.full(n, np.nan)
    if dentro.any():
        q = (pd.DataFrame({"lab": lab.ravel()[dentro], "v": pend.ravel()[dentro]})
             .groupby("lab")["v"].quantile(0.90))
        p90[q.index.values - 1] = q.values
    res["pendiente_p90"] = np.round(p90, 2)

    cnt_e, suma_e, sq_e = _por_etiqueta(lab, dem.astype("float64"), n)
    med_e = np.where(con, suma_e / np.maximum(cnt_e, 1), np.nan)
    var_e = np.where(con, sq_e / np.maximum(cnt_e, 1) - np.nan_to_num(med_e) ** 2, np.nan)
    res["elevacion_media"] = np.round(med_e, 1)
    res["rugosidad_m"] = np.round(np.sqrt(np.clip(var_e, 0, None)), 1)
    res["px_dem"] = cnt

    # --- cobertura ---
    cob, trc = _recortar(celda, geom_celda_wgs84.bounds, "cobertura", forzar)
    labc = _etiquetas(pm, cob.shape, trc)
    total = np.bincount(labc.ravel(), minlength=n + 1)[1:]
    apta = np.zeros(n)
    fracciones = {}
    for clase, coef in APTITUD_WORLDCOVER.items():
        mascara = (cob == clase).astype("float64")
        c = np.bincount(labc.ravel(), weights=mascara.ravel(), minlength=n + 1)[1:]
        fracciones[clase] = c
        apta += c * coef
    conc = total > 0
    # Porcentaje del lote en cada clase, tal como la publica la capa y sin transformar.
    # Es lo que el reporte de lotes describe.
    for clase, sufijo in SUFIJO_WORLDCOVER.items():
        res[f"cob_{sufijo}_pct"] = np.round(
            np.where(conc, fracciones[clase] / np.maximum(total, 1) * 100, np.nan), 1)
    # Agregado ponderado con coeficientes de este estudio. No se publica en la ficha del
    # lote: queda solo como variable de entrada del criterio de cobertura del índice de
    # aptitud, cuyos percentiles se calibraron sobre esta misma escala.
    res["cobertura_apta_pct"] = np.round(
        np.where(conc, apta / np.maximum(total, 1) * 100, np.nan), 1)
    res["px_cobertura"] = total

    return pd.DataFrame(res, index=predios.index)


def metricas(predios: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame,
             forzar: bool = False, verbose: bool = True) -> pd.DataFrame:
    """
    Métricas de terreno para todos los predios de todas las celdas. Si una celda falla se
    avisa y sus predios quedan con NaN; no se rellena con el valor de la celda.
    """
    cw = celdas.to_crs(config.CRS_GEOGRAFICO).set_index(celdas["cell_id"].astype(str))
    partes, fallos = [], []
    ids = list(dict.fromkeys(predios["cell_id"].astype(str)))
    for i, cid in enumerate(ids, 1):
        sub = predios[predios["cell_id"].astype(str) == cid]
        if cid not in cw.index:
            fallos.append((cid, "la celda no está en el archivo de celdas"))
            continue
        try:
            partes.append(metricas_celda(cid, sub, cw.loc[cid].geometry, forzar))
        except Exception as exc:
            fallos.append((cid, f"{type(exc).__name__}: {str(exc)[:70]}"))
            continue
        if verbose:
            print(f"  [{i:>3}/{len(ids)}] {cid}  {len(sub):>4} predios", flush=True)

    if fallos:
        print(f"  {len(fallos)} celdas sin métricas de terreno:")
        for cid, msg in fallos[:10]:
            print(f"    {cid}: {msg}")

    if not partes:
        return pd.DataFrame(index=predios.index)
    return pd.concat(partes).reindex(predios.index)


def main(argv=None) -> int:
    """CLI: mide el terreno de los predios de las celdas indicadas e imprime un resumen."""
    p = argparse.ArgumentParser(description="Pendiente y cobertura por predio")
    p.add_argument("--celdas", default=None, help="lista de cell_id separada por comas")
    p.add_argument("--forzar", action="store_true", help="ignorar la caché de recortes")
    a = p.parse_args(argv)

    salida = config.PROJECT_ROOT / "outputs" / "reporte"
    predios = gpd.read_file(salida / "predios.gpkg")
    celdas = gpd.read_file(salida / "grillas_candidatas.gpkg")
    celdas["cell_id"] = celdas["cell_id"].astype(str)
    if a.celdas:
        pedidas = {c.strip() for c in a.celdas.split(",")}
        predios = predios[predios["cell_id"].astype(str).isin(pedidas)]

    print("=" * 74)
    print("TERRENO POR PREDIO  ·  Copernicus DEM 30 m + ESA WorldCover 10 m")
    print("=" * 74)
    m = metricas(predios, celdas, forzar=a.forzar)
    print()
    print(m.describe().round(2).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
