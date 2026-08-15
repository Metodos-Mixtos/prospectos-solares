"""
Arma el lote de grillas que se va a llevar a búsqueda de predios.

Consultar el FeatureServer del IGAC cuesta minutos por grilla, así que no se lanza sobre
las cien. Este script escribe el archivo que el notebook 2 toma como entrada, con las
grillas que se le pidan: las primeras del ranking, las de una zona, las prioritarias, o
las que se marquen a mano en el reporte y se descarguen desde ahí.

Sale en GeoJSON y en CSV con el contorno en WKT. Lo único que el notebook necesita es
cell_id y la geometría; el resto de columnas va para poder leer el archivo sin volver al
reporte.

Uso:
    .venv\\Scripts\\python.exe herramientas/lote_predios.py --top 10
    .venv\\Scripts\\python.exe herramientas/lote_predios.py --clase Prioritaria
    .venv\\Scripts\\python.exe herramientas/lote_predios.py --zona Z04 --salida lote_z04
    .venv\\Scripts\\python.exe herramientas/lote_predios.py --ids 0012960,0011446
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para importar config y gcs, que viven un
# nivel arriba de esta carpeta.
# La raiz y soporte/ van al path: config y gcs viven en soporte, y los
# paquetes del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

#: Lo que viaja al notebook. Se deja cell_id primero porque es la clave del cruce.
COLUMNAS = ["cell_id", "ranking", "clasificacion", "indice_aptitud", "zona",
            "departamento", "municipio", "vereda", "ha_aptas", "mwp_indicativo",
            "sub_nombre_subestacion", "operador"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--celdas", help="gpkg de grillas ya caracterizadas")
    ap.add_argument("--top", type=int, help="las N primeras del ranking")
    ap.add_argument("--clase", help="solo las de esta clasificación")
    ap.add_argument("--zona", help="solo las de esta zona")
    ap.add_argument("--ids", help="lista de cell_id separados por coma")
    ap.add_argument("--salida", default="grillas_para_predios")
    a = ap.parse_args(argv)

    import geopandas as gpd

    ruta = Path(a.celdas) if a.celdas else SALIDA / "grillas_candidatas.gpkg"
    if not ruta.is_absolute():
        ruta = config.PROJECT_ROOT / ruta
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre antes reporte_grillas.py")

    g = gpd.read_file(ruta)
    g["cell_id"] = g["cell_id"].astype(str)
    n0 = len(g)

    # Las excluidas nunca entran: no tiene sentido gastar consultas del IGAC en una
    # grilla que ya está descartada por una restricción que no se negocia.
    if "clasificacion" in g.columns:
        g = g[g["clasificacion"] != "Excluida"]
        print(f"  se descartan {n0 - len(g)} excluidas")

    if a.ids:
        pedidos = [x.strip() for x in a.ids.split(",") if x.strip()]
        g = g[g["cell_id"].isin(pedidos)]
        faltan = set(pedidos) - set(g["cell_id"])
        if faltan:
            print(f"  aviso: no están en el archivo {', '.join(sorted(faltan))}")
    if a.clase:
        g = g[g["clasificacion"].str.lower() == a.clase.lower()]
    if a.zona:
        g = g[g["zona"].str.lower() == a.zona.lower()]
    if a.top:
        g = g.nsmallest(a.top, "ranking") if "ranking" in g.columns else g.head(a.top)

    if g.empty:
        raise SystemExit("Ningún grilla cumple ese filtro")
    g = g.sort_values("ranking") if "ranking" in g.columns else g

    cols = [c for c in COLUMNAS if c in g.columns]
    salida = g[cols + ["geometry"]].to_crs(config.CRS_GEOGRAFICO)

    SALIDA.mkdir(parents=True, exist_ok=True)
    gj = SALIDA / f"{a.salida}.geojson"
    salida.to_file(gj, driver="GeoJSON")

    csv = SALIDA / f"{a.salida}.csv"
    tabla = pd.DataFrame(salida.drop(columns="geometry"))
    tabla["wkt"] = salida.geometry.astype(str)
    tabla.to_csv(csv, index=False, sep=";", encoding="utf-8-sig")

    print()
    print("=" * 74)
    print(f"LOTE PARA BÚSQUEDA DE PREDIOS  ·  {len(salida)} grillas")
    print("=" * 74)
    ver = ["ranking", "cell_id", "clasificacion", "indice_aptitud", "departamento",
           "municipio", "vereda"]
    print(salida[[c for c in ver if c in salida.columns]].to_string(index=False))
    print()
    print(f"  GeoJSON -> {gj}")
    print(f"  CSV     -> {csv}")
    print()
    print("  Para el notebook 2:")
    print(f"     python predios_igac.py --celdas outputs/reporte/{a.salida}.geojson")
    return 0


if __name__ == "__main__":
    sys.exit(main())
