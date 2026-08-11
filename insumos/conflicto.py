"""
Acciones bélicas por municipio, para descartar celdas en territorio en disputa.

La fuente es el SIEVCAC del Centro Nacional de Memoria Histórica, publicado en
datos.gov.co. Trae un registro por hecho, con fecha, municipio, actores y coordenada.

Sobre la coordenada, que es la trampa de esta capa. Parece que permite ubicar el hecho
en el mapa, pero no: el CNMH geocodifica a un punto de referencia del municipio, y la
mediana es que el 58% de los eventos de un municipio caigan en la misma coordenada. El
radio del círculo equivalente del municipio mediano con eventos es de 15 km, así que
cualquier corte por distancia menor que eso inventa una precisión que el dato no tiene.
Por eso aquí se agrega por municipio, que es la escala a la que la fuente existe.

El umbral no se escogió a dedo. Se calibró contra las plantas solares que ya operan,
igual que se hizo con el rango de tensión de las subestaciones. De las diez plantas de
50 MW o más del país, ninguna está en un municipio con acciones bélicas desde 2022, y de
las veintitrés de 10 MW o más solo cinco lo están. A escala utility el sector ya evita
estas zonas, y el criterio recoge esa conducta en vez de imponer una preferencia.

Uso:
    .venv\\Scripts\\python.exe conflicto.py            # descarga y resume
    .venv\\Scripts\\python.exe conflicto.py --subir    # y publica el crudo en el bucket
    .venv\\Scripts\\python.exe conflicto.py --refrescar
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para poder importar config y gcs, que viven
# un nivel arriba de este paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
CACHE = config.PROJECT_ROOT / "data" / "conflicto"
BUCKET = "prospectos"
PREFIJO = "insumos/conflicto"

#: Recurso 39qq-a72j de datos.gov.co, acciones bélicas del conflicto armado.
RECURSO = "39qq-a72j"
URL = f"https://www.datos.gov.co/resource/{RECURSO}.json"

#: Año desde el que cuentan los hechos. Cuatro años es suficiente para distinguir un
#: territorio en disputa de uno con un incidente aislado, y corto para que no arrastre
#: dinámicas ya cerradas. Es una constante y no una ventana móvil a propósito, para que
#: dos corridas del reporte den lo mismo. Conviene revisarla cada par de años.
DESDE = 2022

#: Los dos filtros. Se exige que se cumplan los dos.
#:
#: El conteo separa el territorio en disputa del incidente suelto. El de densidad corrige
#: el sesgo de tamaño: Montería tiene tres hechos en 3.093 km², que es un evento por cada
#: mil km² y no describe nada, mientras que Bugalagrande tiene cuatro en 394 km². Sin el
#: segundo filtro, los municipios grandes caen por ser grandes.
MIN_EVENTOS = 3
MIN_DENSIDAD = 3.0        # eventos por cada 1.000 km²


def descargar(refrescar: bool = False) -> pd.DataFrame:
    """Baja los hechos crudos y los cachea. Intenta el bucket antes que el portal."""
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"sievcac_{DESDE}.json"

    if destino.exists() and not refrescar:
        return pd.DataFrame(json.loads(destino.read_text(encoding="utf-8")))

    if not refrescar:
        try:
            import gcs
            ruta = gcs.obtener(BUCKET, f"{PREFIJO}/{destino.name}", verbose=False)
            return pd.DataFrame(json.loads(Path(ruta).read_text(encoding="utf-8")))
        except Exception:
            pass

    filas, off = [], 0
    while True:
        r = requests.get(URL, params={"$limit": 5000, "$offset": off,
                                      "$where": f"a_o >= {DESDE}"},
                         headers=UA, timeout=180)
        r.raise_for_status()
        lote = r.json()
        if not lote:
            break
        filas.extend(lote)
        off += 5000
        if len(lote) < 5000:
            break

    destino.write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    return pd.DataFrame(filas)


def areas_municipales() -> pd.Series:
    """Área en km² por código DANE, de la base veredal que ya usa el reporte."""
    import geopandas as gpd
    ruta = config.PROJECT_ROOT / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    if not ruta.exists():
        return pd.Series(dtype=float)
    v = gpd.read_file(ruta, columns=["DPTOMPIO", "AREA_HA"], ignore_geometry=True)
    v["dane"] = v.DPTOMPIO.astype(str).str.zfill(5)
    return v.groupby("dane").AREA_HA.sum() / 100.0


def por_municipio(refrescar: bool = False) -> pd.DataFrame:
    """
    Una fila por municipio con hechos: cuántos, con qué densidad y quién.

    Devuelve también si el municipio cae bajo los dos filtros, que es lo que después
    descarta la celda.
    """
    ev = descargar(refrescar)
    if ev.empty:
        return pd.DataFrame()

    ev["dane"] = ev.c_digo_dane_de_municipio.astype(str).str.zfill(5)
    ev["anio"] = pd.to_numeric(ev.a_o, errors="coerce")

    # El actor se toma del segundo grupo, que es el no estatal en los combates. Cuando
    # no lo hay se cae al primero, que en las operaciones militares es la fuerza pública.
    act = ev.get("descripci_n_grupo_armado_1", pd.Series(dtype=object))
    alt = ev.get("descripci_n_grupo_armado", pd.Series(dtype=object))
    ev["actor"] = act.where(act.notna() & ~act.isin(["NO APLICA", "OTRO"]), alt)

    def actores(s):
        c = s.dropna().value_counts()
        return "; ".join(f"{k.title()} ({v})" for k, v in c.head(3).items())

    g = ev.groupby("dane").agg(
        eventos=("dane", "size"),
        municipio=("municipio", "first"),
        departamento=("departamento", "first"),
        ultimo_anio=("anio", "max"),
        actores=("actor", actores),
    ).reset_index()

    a = areas_municipales()
    g["area_km2"] = g.dane.map(a)
    g["densidad"] = (g.eventos / g.area_km2 * 1000).round(1)

    g["descarta"] = (g.eventos >= MIN_EVENTOS) & (g.densidad >= MIN_DENSIDAD)
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--refrescar", action="store_true")
    a = ap.parse_args(argv)

    print("=" * 80)
    print(f"ACCIONES BÉLICAS POR MUNICIPIO  ·  SIEVCAC del CNMH, {DESDE} en adelante")
    print("=" * 80)

    g = por_municipio(a.refrescar)
    if g.empty:
        print("  sin datos")
        return 1

    print(f"  municipios con hechos      : {len(g)}")
    print(f"  hechos                     : {int(g.eventos.sum())}")
    print(f"  bajo los dos filtros       : {int(g.descarta.sum())} "
          f"(>= {MIN_EVENTOS} hechos y >= {MIN_DENSIDAD:.0f} por mil km²)")
    print()
    print("  los diez con más carga:")
    print("  %-24s %-16s %7s %9s %8s" % ("municipio", "departamento", "hechos",
                                          "km2", "dens."))
    for _, r in g.nlargest(10, "eventos").iterrows():
        print("  %-24s %-16s %7d %9.0f %8.1f%s" % (
            str(r.municipio)[:24], str(r.departamento)[:16], r.eventos,
            r.area_km2 or 0, r.densidad or 0, "  <-" if r.descarta else ""))

    if a.subir:
        import gcs
        n = gcs.subir_carpeta(BUCKET, PREFIJO, CACHE, "*.json")
        print(f"\n  subidos al bucket: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
