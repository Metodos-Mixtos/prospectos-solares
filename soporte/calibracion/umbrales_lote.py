"""
Umbrales del índice calibrados a escala de LOTE, con los lotes reales de las plantas.

Los umbrales de la matriz (umbrales.py) salen de celdas de 5 x 5 km con planta; aplicarlos
a un lote lo favorece, porque el lote se mide en su polígono y no en el promedio de la
celda. Aquí se hace lo mismo pero sobre el lote catastral donde está cada planta solar del
registro de XM: se ubica el lote por el punto de la planta (catastro público del IGAC), se
miden las mismas variables con el mismo código de predios/ y se leen los percentiles
10/50/90. Los números se pegan a mano en PERFILES[...]["umbrales_lote"] (reporte/datos.py).

Uso:
    .venv\\Scripts\\python.exe -m soporte.calibracion umbrales_lote
    .venv\\Scripts\\python.exe -m soporte.calibracion umbrales_lote --sin-vias
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
_raiz = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

from calibracion.umbrales import P_TOPE, P_BUENO, P_LIMITE  # noqa: E402

#: Registro de plantas de XM (capa UPME proyectos_generacion_xm, solo solar).
XM = config.DATA_DIR / "geoinfo" / "Colombia" / "Energia_electrica" / "Proyectos de generación (XM) 2026-08-18.geojson"
CACHE = config.DATA_DIR / "calibracion"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

#: Rangos de capacidad de referencia por perfil (MW), los mismos de umbrales.py.
RANGOS = {"utility": (10.0, None), "distribuida": (0.5, 5.0)}
ESTADOS = ("OPERACIÓN", "PRUEBAS")

#: Un punto que cae en un lote demasiado pequeño para la planta es una coordenada
#: imprecisa (centroide municipal, subestación): no sirve de referencia.
HA_MIN_POR_MW = 0.5
#: Plantas en municipios con gestor catastral propio (sin catastro público): a partir de
#: esta capacidad se usa como lote una huella aproximada, un círculo centrado en el punto
#: con el área que ocupa la planta (MW x hectáreas por MWp). Se marca tipo "aprox".
MW_HUELLA_APROX = 5.0


def plantas() -> "gpd.GeoDataFrame":
    """Plantas solares en operación o pruebas, con su capacidad en MW."""
    import geopandas as gpd
    x = gpd.read_file(XM)
    x = x[x["tipo_generacion"].astype(str).str.upper().str.contains("SOLAR", na=False)]
    x = x[x["estado_recurso"].isin(ESTADOS)].copy()
    x["mw"] = pd.to_numeric(x["capacidad_efectiva_neta_mw"], errors="coerce").fillna(0)
    x = x[x["mw"] >= 0.5].to_crs(config.CRS_GEOGRAFICO).reset_index(drop=True)
    return x


def lote_en_punto(lon: float, lat: float) -> dict | None:
    """Lote del catastro público del IGAC bajo el punto: rural (14) o urbano (7)."""
    import requests
    import predios_igac as pig
    for capa, tipo in ((14, "rural"), (7, "urbano")):
        for i in range(3):
            try:
                r = requests.get(f"{pig.BASE}/{capa}/query", headers=pig.UA, timeout=60, params={
                    "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects", "outFields": "CODIGO,codigo_municipio",
                    "returnGeometry": "true", "outSR": 4326, "f": "geojson"})
                r.raise_for_status()
                fs = r.json().get("features", [])
                break
            except Exception:
                fs = None
                time.sleep(1.5 * (i + 1))
        if fs:
            f = fs[0]
            return {"CODIGO": f["properties"]["CODIGO"], "tipo": tipo, "geometry": f["geometry"]}
    return None


def lotes_de_plantas(forzar: bool = False, verbose: bool = True) -> "gpd.GeoDataFrame":
    """Lote catastral de cada planta, cacheado en data/calibracion/."""
    import geopandas as gpd
    from shapely.geometry import shape
    import predios_igac as pig
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"lotes_xm_{pig.CORTE}.geojson"
    if ruta.exists() and not forzar:
        return gpd.read_file(ruta)
    x = plantas()
    filas = []
    for i, r in x.iterrows():
        lote = lote_en_punto(r.geometry.x, r.geometry.y)
        if verbose:
            print(f"  [{i + 1:>3}/{len(x)}] {str(r['nombre_recurso'])[:32]:<32} {r['mw']:>7.2f} MW  "
                  f"-> {lote['tipo'] + ' ' + lote['CODIGO'] if lote else 'sin catastro público'}", flush=True)
        filas.append({
            "xm_id": r.get("id"), "nombre": r["nombre_recurso"], "mw": r["mw"], "estado": r["estado_recurso"],
            "municipio": r.get("municipio_oficial"), "dane": r.get("cod_mpio"), "anio_fpo": r.get("anio_fpo"),
            "lon": r.geometry.x, "lat": r.geometry.y,
            "CODIGO": lote["CODIGO"] if lote else None, "tipo": lote["tipo"] if lote else "sin catastro",
            "geometry": shape(lote["geometry"]) if lote else r.geometry,
        })
    g = gpd.GeoDataFrame(filas, geometry="geometry", crs=config.CRS_GEOGRAFICO)
    g.to_file(ruta, driver="GeoJSON")
    return g


def medir(g: "gpd.GeoDataFrame", con_vias: bool = True, verbose: bool = True) -> "gpd.GeoDataFrame":
    """Las siete variables del índice medidas en cada lote, con los módulos de predios/."""
    import geopandas as gpd
    from shapely.geometry import box
    import lotes as lt
    import terreno
    import contexto
    import reporte.datos as rg

    # Sin catastro público y planta grande: huella aproximada alrededor del punto.
    g = g.copy()
    gm0 = g.to_crs(config.CRS_METRICO)
    aprox = (g["tipo"] == "sin catastro") & (g["mw"] >= MW_HUELLA_APROX)
    if aprox.any():
        radios = np.sqrt(g.loc[aprox, "mw"] * rg.HA_POR_MWP * 1e4 / np.pi)
        huellas = gpd.GeoSeries([pt.buffer(r) for pt, r in zip(gm0.loc[aprox].geometry, radios)],
                                crs=config.CRS_METRICO).to_crs(config.CRS_GEOGRAFICO)
        g.loc[aprox, "geometry"] = huellas.values
        g.loc[aprox, "tipo"] = "aprox"
    g = g[g["tipo"].isin(("rural", "aprox"))].copy().reset_index(drop=True)
    gm = g.to_crs(config.CRS_METRICO)
    g["area_ha"] = (gm.geometry.area / 1e4).round(2)
    g = g[g["area_ha"] >= np.maximum(1.0, g["mw"] * HA_MIN_POR_MW)].copy().reset_index(drop=True)
    gm = g.to_crs(config.CRS_METRICO)
    g["cell_id"] = [f"xm_{int(i)}" if pd.notna(i) else f"xm_r{k}" for k, i in enumerate(g["xm_id"])]

    # Pseudoceldas: el lote con 500 m de holgura, para que terreno recorte DEM y cobertura.
    celdas = gpd.GeoDataFrame({"cell_id": g["cell_id"]},
                              geometry=[box(*b.buffer(500).bounds) for b in gm.geometry],
                              crs=config.CRS_METRICO).to_crs(config.CRS_GEOGRAFICO)
    if verbose:
        print(f"  lotes de referencia: {int((g['tipo'] == 'rural').sum())} catastrales rurales y "
              f"{int((g['tipo'] == 'aprox').sum())} huellas aproximadas (sin catastro público)")
    m = terreno.metricas(g, celdas, verbose=False)
    for c in m.columns:
        g[c] = m[c].values

    for perfil, cfg in rg.PERFILES.items():
        q = lt.añadir_conexion(g, cfg["kv_min"], cfg["kv_max"], verbose=False)
        g[f"dist_sub_{perfil}"] = q["conexion_km"].values

    if con_vias:
        import insumos.vias as dv
        dv.calcular(celdas, verbose=verbose)      # cachea las vías alrededor de cada lote
    g = lt.añadir_dist_via(g, verbose=False)

    cent = gm.geometry.centroid.to_crs(config.CRS_GEOGRAFICO)
    pv = [contexto.recurso_punto(f"xm_{c}", x, y).get("pvout") for c, x, y in zip(g["CODIGO"], cent.x, cent.y)]
    g["pvout"] = pv
    return g


#: Criterio -> columna medida en el lote (dist_sub lleva sufijo de perfil).
CAMPO = {"dist_sub": "dist_sub_{perfil}", "cobertura": "cobertura_apta_pct", "pendiente": "pendiente_media",
         "recurso": "pvout", "rugosidad": "rugosidad_m", "dist_via": "dist_via_km"}


def percentiles(g: "gpd.GeoDataFrame", perfil: str) -> dict:
    import reporte.datos as rg
    lo, hi = RANGOS[perfil]
    sub = g[(g["mw"] >= lo) & ((g["mw"] <= hi) if hi else True)]
    sub = sub.assign(_k=sub["CODIGO"].fillna(sub["cell_id"])).drop_duplicates("_k")
    out = {"n": int(len(sub)), "n_aprox": int((sub["tipo"] == "aprox").sum()), "umbrales": {}}
    for k, col in CAMPO.items():
        col = col.format(perfil=perfil)
        s = pd.to_numeric(sub.get(col), errors="coerce").dropna()
        if len(s) < 10:
            continue
        cfg = rg.CRITERIOS[k]
        ps = (P_TOPE, P_BUENO, P_LIMITE) if not cfg["mayor_mejor"] else (P_LIMITE, P_BUENO, P_TOPE)
        tope, bueno, limite = (float(np.percentile(s, x)) for x in ps)
        dec = 0 if cfg["unidad"] in ("kWh/kWp", "%") else 1
        out["umbrales"][k] = {"tope": round(tope, dec), "bueno": round(bueno, dec), "limite": round(limite, dec), "n": int(len(s))}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Umbrales del índice a escala de lote")
    ap.add_argument("--sin-vias", action="store_true", help="omite Overpass, la parte lenta")
    ap.add_argument("--forzar", action="store_true", help="reubica los lotes de las plantas")
    a = ap.parse_args(argv)
    import reporte.datos as rg

    print("=" * 94)
    print("UMBRALES A ESCALA DE LOTE  ·  lotes catastrales de las plantas solares de XM")
    print("=" * 94)
    g = lotes_de_plantas(forzar=a.forzar)
    print(f"  plantas: {len(g)}  ({(g['tipo'] == 'rural').sum()} en lote rural, "
          f"{(g['tipo'] == 'urbano').sum()} en lote urbano, {(g['tipo'] == 'sin catastro').sum()} sin catastro público)")
    g = medir(g, con_vias=not a.sin_vias)
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(g.drop(columns="geometry")).to_csv(SALIDA / "calibracion_lotes_xm.csv", index=False, encoding="utf-8-sig")

    resultado = {}
    for perfil in rg.PERFILES:
        res = percentiles(g, perfil)
        resultado[perfil] = res
        lo, hi = RANGOS[perfil]
        print(f"\n  Perfil {perfil} ({lo:g}{'-' + format(hi, 'g') if hi else ' o más'} MW): {res['n']} lotes de referencia "
              f"({res['n_aprox']} huellas aproximadas)")
        print("  %-11s %9s %11s %9s   |  %-22s %s" % ("criterio", "tope p10", "bueno p50", "lim p90", "grilla (hoy)", "n"))
        um_g = rg.PERFILES[perfil]["umbrales"]
        for k, u in res["umbrales"].items():
            print("  %-11s %9.1f %11.1f %9.1f   |  %5.1f / %5.1f / %-6.1f %3d" % (
                k, u["tope"], u["bueno"], u["limite"], um_g[k]["tope"], um_g[k]["bueno"], um_g[k]["limite"], u["n"]))
    (SALIDA / "umbrales_lote.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  JSON -> {SALIDA / 'umbrales_lote.json'}   CSV -> {SALIDA / 'calibracion_lotes_xm.csv'}")
    print("  Para pegar en PERFILES[perfil]['umbrales_lote'] de reporte/datos.py:")
    for perfil, res in resultado.items():
        print(f"    {perfil}:")
        for k, u in res["umbrales"].items():
            print(f'      "{k}": {{"tope": {u["tope"]}, "bueno": {u["bueno"]}, "limite": {u["limite"]}}},')
    return 0


if __name__ == "__main__":
    sys.exit(main())
