"""
Capas de restricción que no vienen en el panel y hay que traer de fuera.

El panel trae cuatro figuras jurídicas: parques nacionales, resguardos, consejos
comunitarios y RUNAP. Falta la Reserva Forestal de Ley 2ª de 1959, que cubre buena
parte del país, no forma parte del RUNAP y condiciona cualquier obra que caiga dentro.

Orden de búsqueda de cada capa:

    1. bucket gs://prospectos_solares/insumos/restricciones/   <- fuente normal
    2. caché local en data/restricciones/
    3. FeatureServer oficial del Ministerio de Ambiente        <- solo para refrescar

Así el reporte se reproduce igual en cualquier máquina sin depender de que el servicio
del MADS esté arriba. Con --refrescar se vuelve a bajar del servicio y con --subir se
publica en el bucket la versión que quede en disco.

El cruce es contra el archivo de celdas que se le pase, no contra una lista fija: si
mañana el modelo devuelve otras cien celdas, el procedimiento es el mismo.

Uso:
    .venv\\Scripts\\python.exe capas_restriccion.py
    .venv\\Scripts\\python.exe capas_restriccion.py --celdas outputs/top_candidates.gpkg
    .venv\\Scripts\\python.exe capas_restriccion.py --refrescar --subir
    .venv\\Scripts\\python.exe capas_restriccion.py --listar
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

warnings.filterwarnings("ignore")
# La raiz y soporte/ van al path: config y gcs viven en soporte/, y los paquetes
# del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
CACHE = config.PROJECT_ROOT / "data" / "restricciones"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

BUCKET = "prospectos"
PREFIJO = "insumos/restricciones"

#: Servicios oficiales. El propietario Datos_Abiertos_MADS es la cuenta institucional
#: del Ministerio de Ambiente en ArcGIS Online, que es lo que los hace citables.
CAPAS = {
    "ley2": {
        "etiqueta": "Reserva Forestal de Ley 2ª de 1959",
        "url": ("https://services6.arcgis.com/hxAwRYAu9QHliJ8T/arcgis/rest/services/"
                "Reservas_Forestales_de_Ley_2da_de_1959_/FeatureServer/0"),
        "fuente": "MinAmbiente, SIAC datos abiertos",
    },
}

PAGINA = 500


# --------------------------------------------------------------------------------------
# obtención de la capa
# --------------------------------------------------------------------------------------

def _del_servicio(clave: str) -> Path | None:
    """Pagina el FeatureServer y deja el GeoJSON crudo en la caché local."""
    cfg = CAPAS[clave]
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"{clave}.geojson"

    print(f"     bajando del servicio del MADS...", end=" ", flush=True)
    feats, offset = [], 0
    while True:
        par = {"where": "1=1", "outFields": "*", "returnGeometry": "true",
               "outSR": 4326, "f": "geojson",
               "resultRecordCount": PAGINA, "resultOffset": offset}
        try:
            r = requests.post(cfg["url"] + "/query", data=par, headers=UA, timeout=300)
            r.raise_for_status()
            d = r.json()
        except Exception as exc:
            print(f"error: {type(exc).__name__}")
            return None
        lote = d.get("features", [])
        feats.extend(lote)
        limite = d.get("properties", {}).get("exceededTransferLimit",
                                             d.get("exceededTransferLimit"))
        if len(lote) < PAGINA or not limite:
            break
        offset += PAGINA
        time.sleep(0.5)

    if not feats:
        print("sin registros")
        return None

    destino.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                  ensure_ascii=False), encoding="utf-8")
    print(f"{len(feats)} polígonos")
    return destino


def obtener_capa(clave: str, refrescar: bool = False) -> Path | None:
    """Bucket, caché local o servicio, en ese orden."""
    print(f"  {CAPAS[clave]['etiqueta']}")
    local = CACHE / f"{clave}.geojson"

    if refrescar:
        return _del_servicio(clave)

    try:
        import gcs
        ruta = gcs.obtener(BUCKET, f"{PREFIJO}/{clave}.geojson", verbose=False)
        print(f"     del bucket gs://{gcs.BUCKETS[BUCKET]}/{PREFIJO}/{clave}.geojson")
        return ruta
    except Exception as exc:
        print(f"     bucket no disponible ({type(exc).__name__})")

    if local.exists():
        print(f"     de la caché local {local.name}")
        return local

    return _del_servicio(clave)


def publicar(clave: str, ruta: Path) -> None:
    """Sube la capa cruda al bucket para que el resto del equipo la tome de ahí."""
    import gcs
    gcs.subir(BUCKET, f"{PREFIJO}/{clave}.geojson", ruta, forzar=True)


# --------------------------------------------------------------------------------------
# cruce con las celdas
# --------------------------------------------------------------------------------------

def cruzar(clave: str, capa: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Superficie de cada celda que cae dentro de la capa.

    El porcentaje se calcula sobre el área real de cada celda, no sobre un valor fijo,
    para que siga siendo correcto si el tamaño de la grilla cambia.
    """
    if capa.crs is None:
        capa = capa.set_crs(config.CRS_GEOGRAFICO)
    cm = capa.to_crs(config.CRS_METRICO)
    gm = celdas.to_crs(config.CRS_METRICO)
    gm["_area_ha"] = gm.geometry.area / 10_000

    inter = gpd.overlay(gm[["cell_id", "geometry"]], cm[["geometry"]],
                        how="intersection", keep_geom_type=True)
    if inter.empty:
        return pd.DataFrame(columns=["cell_id", f"{clave}_ha", f"{clave}_pct"])

    inter["ha"] = inter.geometry.area / 10_000
    res = inter.groupby("cell_id")["ha"].sum().reset_index()
    res.columns = ["cell_id", f"{clave}_ha"]
    res = res.merge(gm[["cell_id", "_area_ha"]], on="cell_id", how="left")
    res[f"{clave}_pct"] = (res[f"{clave}_ha"] / res["_area_ha"] * 100).round(1)
    return res.drop(columns=["_area_ha"])


def _resolver_celdas(ruta: str | None) -> Path:
    """
    Qué archivo de celdas se cruza.

    Por defecto el reporte ya enriquecido, y si no existe, el top_candidates que sale
    del modelo. Cualquiera de los dos sirve: lo único que se usa es cell_id y geometría.
    """
    if ruta:
        p = Path(ruta)
        if not p.is_absolute():
            p = config.PROJECT_ROOT / p
        if not p.exists():
            raise SystemExit(f"No existe {p}")
        return p

    for cand in (SALIDA / "grillas_candidatas.gpkg",
                 config.PROJECT_ROOT / "outputs" / "top_candidates.gpkg"):
        if cand.exists():
            return cand
    raise SystemExit("No encuentro ni grillas_candidatas.gpkg ni top_candidates.gpkg")


# --------------------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--celdas", help="gpkg o geojson de celdas a cruzar")
    p.add_argument("--listar", action="store_true", help="solo describe los servicios")
    p.add_argument("--refrescar", action="store_true", help="vuelve a bajar del MADS")
    p.add_argument("--subir", action="store_true", help="publica las capas en el bucket")
    a = p.parse_args(argv)

    print("=" * 78)
    print("CAPAS DE RESTRICCIÓN EXTERNAS")
    print("=" * 78)

    if a.listar:
        for k, c in CAPAS.items():
            print(f"\n  {k}: {c['etiqueta']}")
            print(f"     {c['url']}")
            try:
                r = requests.get(c["url"], params={"f": "json"}, headers=UA, timeout=60)
                d = r.json()
                print(f"     nombre    : {d.get('name')}")
                print(f"     geometría : {d.get('geometryType')}")
                print("     campos    : "
                      + ", ".join(f["name"] for f in d.get("fields", [])[:10]))
            except Exception as exc:
                print(f"     no accesible: {type(exc).__name__}")
        return 0

    ruta_celdas = _resolver_celdas(a.celdas)
    celdas = gpd.read_file(ruta_celdas)
    print(f"\n  Celdas: {len(celdas)} de {ruta_celdas.name}\n")

    resultado = celdas[["cell_id"]].copy()
    for clave in CAPAS:
        ruta = obtener_capa(clave, refrescar=a.refrescar)
        if ruta is None:
            print("     no se pudo obtener, se omite\n")
            continue
        if a.subir:
            publicar(clave, ruta)

        capa = gpd.read_file(ruta)
        res = cruzar(clave, capa, celdas)
        resultado = resultado.merge(res, on="cell_id", how="left")

        col = f"{clave}_pct"
        n = int((resultado[col].fillna(0) > 0).sum()) if col in resultado else 0
        print(f"     celdas tocadas: {n} de {len(celdas)}")
        if n:
            sub = resultado[resultado[col].fillna(0) > 0].nlargest(10, col)
            print(sub[["cell_id", f"{clave}_ha", col]].round(1).to_string(index=False))
        print()

    resultado = resultado.fillna(0)
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "restricciones_externas.csv"
    resultado.to_csv(destino, index=False, encoding="utf-8-sig")
    print(f"  CSV -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
