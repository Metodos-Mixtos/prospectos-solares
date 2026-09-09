"""
De dónde salen los umbrales de la matriz de criterios.

Ninguno se puso a criterio propio. Los tres se leen de la distribución de las celdas del
país que ya contienen una planta solar de la escala que se está prospectando:

    tope   = el decil mejor de lo construido, vale 100 en el índice
    bueno  = la mediana, donde está la mitad de lo construido, vale 70
    limite = el decil peor de lo construido, vale 0

Cuál percentil es cuál depende del sentido del criterio, y conviene no escribirlo
al revés: donde menos es mejor, tope es el percentil 10 y límite el 90; donde más
es mejor, como en producción fotovoltaica, la asignación se voltea. Eso es lo que
hace la línea `ps = (P_TOPE, P_BUENO, P_LIMITE) if not mayor_mejor else ...`.

Los números que salen de aquí se pegan a mano en CRITERIOS, dentro de reporte/datos.py.
No se calculan en cada corrida a propósito. Hacerlo obligaría a leer el panel completo y
a consultar Overpass cada vez que se genera el reporte, y sobre todo un umbral que cambia
solo es un umbral que nadie puede auditar: dos personas que corran el reporte el mismo día
tienen que obtener la misma nota para la misma celda.

El corte de tamaño importa. Con todas las plantas, los límites de terreno se van al doble,
porque las de 1 MW son autogeneradores en techos industriales que no eligen el terreno,
van donde está la fábrica. Con 10 MW en adelante quedan las que sí lo eligen.

Uso:
    .venv\\Scripts\\python.exe -m soporte.calibracion umbrales
    .venv\\Scripts\\python.exe -m soporte.calibracion umbrales --mw 20
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para poder importar config y gcs, que viven
# un nivel arriba de este paquete.
# La raiz y soporte/ van al path: config y gcs viven en soporte, y los
# paquetes del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

#: Percentiles que anclan la escala. El primero es el lado bueno de la distribución.
P_TOPE, P_BUENO, P_LIMITE = 10, 50, 90


def celdas_con_planta(mw_min: float) -> "gpd.GeoDataFrame":
    """Celdas del panel que contienen al menos mw_min de solar instalada."""
    import geopandas as gpd
    p = gpd.read_file(config.PANEL_PATH)
    xm = gpd.read_file(config.GRANJAS_PATH)
    sol = xm[xm.tipo_generacion.astype(str).str.upper()
             .str.contains("SOLAR", na=False)].copy()
    sol["mw"] = pd.to_numeric(sol.capacidad_efectiva_neta_mw, errors="coerce").fillna(0)

    pm = p.to_crs(config.CRS_METRICO)
    sm = sol.to_crs(config.CRS_METRICO)
    j = gpd.sjoin(sm[["mw", "geometry"]], pm[["geometry"]], predicate="within")
    p["mw_solar"] = p.index.map(j.groupby("index_right").mw.sum()).fillna(0)
    return p[p.mw_solar >= mw_min].copy().reset_index(drop=True)


def enriquecer(con: "gpd.GeoDataFrame", con_vias: bool = True) -> "gpd.GeoDataFrame":
    """Añade las tres variables que no vienen en el panel, igual que el reporte."""
    import geopandas as gpd
    import reporte.datos as rg

    s = gpd.read_file(config.SUBESTACIONES_PATH)
    kv = rg._num(s.get("tension", pd.Series(dtype=str))).where(lambda x: x > 0)
    s = s[kv.between(rg.KV_CONEXION_MIN, rg.KV_CONEXION_MAX, inclusive="both")]
    red = s.to_crs(config.CRS_METRICO).union_all()
    cm = con.to_crs(config.CRS_METRICO)
    con["dist_sub"] = [g.centroid.distance(red) / 1000 for g in cm.geometry]

    tot = pd.Series(0.0, index=con.index)
    for c, w in rg.APTITUD_COBERTURA.items():
        if c in con.columns:
            tot = tot + pd.to_numeric(con[c], errors="coerce").fillna(0) * w
    obs = pd.Series(100.0, index=con.index)
    if rg.CLASE_NO_OBSERVADA in con.columns:
        obs = (100.0 - pd.to_numeric(con[rg.CLASE_NO_OBSERVADA],
                                     errors="coerce").fillna(0)).clip(lower=1)
    con["cobertura"] = (tot / obs * 100).clip(0, 100)

    con["dist_via"] = np.nan
    if con_vias:
        import insumos.vias as dv
        if "cell_id" not in con.columns:
            con["cell_id"] = [f"ref_{i:04d}" for i in range(len(con))]
        con["cell_id"] = con["cell_id"].astype(str)
        v = dv.calcular(con)
        con["dist_via"] = con.cell_id.map(dict(zip(v.cell_id, v.dist_via_km)))
    return con


CAMPO = {"dist_sub": "dist_sub", "cobertura": "cobertura", "pendiente": "slope_mean",
         "recurso": "pvout", "rugosidad": "elevation_std", "dist_via": "dist_via"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mw", type=float, default=10.0,
                    help="capacidad mínima de la planta de referencia")
    ap.add_argument("--sin-vias", action="store_true",
                    help="omite la consulta a Overpass, que es la parte lenta")
    a = ap.parse_args(argv)

    import reporte.datos as rg

    print("=" * 94)
    print(f"UMBRALES DE REFERENCIA  ·  plantas de {a.mw:.0f} MW o más")
    print("=" * 94)

    con = celdas_con_planta(a.mw)
    print(f"  celdas de referencia: {len(con)}")
    con = enriquecer(con, con_vias=not a.sin_vias)

    print()
    print("  %-11s %9s %11s %9s   |  %-20s %s" % (
        "criterio", "tope p10", "bueno p50", "lim p90", "en el código hoy", "n"))
    nuevos = {}
    for k, col in CAMPO.items():
        if col not in con.columns:
            continue
        s = pd.to_numeric(con[col], errors="coerce").dropna()
        if len(s) < 10:
            print(f"  {k:<11} muestra insuficiente ({len(s)}), se conserva lo que hay")
            continue
        cfg = rg.CRITERIOS[k]
        ps = (P_TOPE, P_BUENO, P_LIMITE) if not cfg["mayor_mejor"] else (P_LIMITE, P_BUENO, P_TOPE)
        tope, bueno, limite = (float(np.percentile(s, x)) for x in ps)
        dec = 0 if cfg["unidad"] in ("kWh/kWp", "%") else 1
        nuevos[k] = tuple(round(x, dec) for x in (tope, bueno, limite))
        print("  %-11s %9.1f %11.1f %9.1f   |  %5.1f / %5.1f / %-5.1f  %3d" % (
            k, tope, bueno, limite, cfg["tope"], cfg["bueno"], cfg["limite"], len(s)))

    print()
    print("  Cuántas plantas de referencia incumplirían el límite que hay hoy:")
    for k, col in CAMPO.items():
        if col not in con.columns:
            continue
        s = pd.to_numeric(con[col], errors="coerce").dropna()
        if not len(s):
            continue
        cfg = rg.CRITERIOS[k]
        fuera = (s < cfg["limite"]).sum() if cfg["mayor_mejor"] else (s > cfg["limite"]).sum()
        aviso = "   <- el límite está mal puesto" if fuera / len(s) > 0.15 else ""
        print("     %-11s %3d de %3d  (%2.0f%%)%s" % (k, fuera, len(s),
                                                      100 * fuera / len(s), aviso))

    print()
    print("  Para pegar en CRITERIOS, dentro de reporte/datos.py:")
    for k, (tope, bueno, limite) in nuevos.items():
        print(f'     "{k}": tope={tope}, bueno={bueno}, limite={limite},')
    print()
    print(f"  Y actualizar REFERENCIA_N = {len(con)} y REFERENCIA_MW = {a.mw:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
