"""
Insumos derivados: publicarlos en el bucket y recuperarlos de allí.

El proyecto usa tres cosas que no vienen de los buckets originales sino que se
construyen por el camino:

  - la red vial de OpenStreetMap alrededor de cada celda, y la distancia resultante
  - los predios catastrales del IGAC de las celdas seleccionadas
  - las líneas de transmisión de OpenStreetMap
  - los informes de capacidad por barra de la UPME, catorce PDF de unos 100 MB

Si viven solo en el disco de quien los descargó, el proyecto deja de ser reproducible:
el siguiente que lo corra tiene que volver a golpear Overpass durante veinte minutos y
al IGAC durante otros tantos, con el riesgo de que además devuelvan algo distinto.
Publicarlos en el bucket los convierte en insumo estable y compartido.

La regla de uso es sencilla: los scripts miran primero el bucket, y solo descargan de
la fuente original lo que no encuentren allí.

Uso:
    python insumos.py estado          # qué hay local y qué hay en el bucket
    python insumos.py subir           # publica lo local que falte en el bucket
    python insumos.py bajar           # trae del bucket lo que falte en local
    python insumos.py subir --forzar  # reescribe aunque ya exista
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# La raiz y soporte/ van al path: config y gcs viven en soporte/, y los paquetes
# del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config
import gcs

BUCKET = "prospectos"

# Solo insumos crudos: lo que llega de una fuente externa tal cual y no se puede
# reconstruir sin volver a ella. Todo lo que calculamos nosotros (distancias, áreas,
# clasificaciones, el consolidado de predios, el reporte) se queda fuera del bucket:
# se regenera con los scripts en segundos y publicarlo solo crea copias que envejecen
# y acaban contradiciendo al código.
#
#: (clave, prefijo en el bucket, carpeta local, patrón, descripción)
CONJUNTOS = [
    # El nombre del archivo lleva el hash de los bbox consultados, no un número de
    # lote, para que un conjunto distinto de celdas no reutilice la respuesta de otro.
    ("osm_vias", "insumos/osm_vias", config.PROJECT_ROOT / "data" / "osm",
     "vias_*.json", "Respuestas de Overpass tal cual, una por bloque de celdas"),
    ("igac_predios", "insumos/igac_predios", config.PROJECT_ROOT / "data" / "igac",
     "igac_*.*", "Respuestas del FeatureServer del IGAC, por celda y capa, y fichas REGISTRO_1/2"),
    ("lineas_transmision", "insumos/lineas_transmision", config.PROJECT_ROOT / "data" / "lineas",
     "lineas_*.json", "Líneas de transmisión de OSM, por lote de celdas"),
    ("capacidad_barras", "insumos/capacidad_barras", config.PROJECT_ROOT / "data" / "barras" / "upme",
     "*.pdf", "Informes de capacidad por barra de la UPME (ciclo 2023-2024) y Circulares 054 y 042 de 2026"),
    ("restricciones", "insumos/restricciones", config.PROJECT_ROOT / "data" / "restricciones",
     "*.geojson", "Capas de restricción que no vienen en el panel, tal cual las publica la entidad"),
    ("normativa", "insumos/normativa", config.PROJECT_ROOT / "data" / "normativa",
     "*.*", "Normas completas que sustentan los criterios; ver normativa.py y NORMATIVA.md"),
    ("conflicto", "insumos/conflicto", config.PROJECT_ROOT / "data" / "conflicto",
     "*.json", "Acciones bélicas del SIEVCAC (CNMH), tal cual las devuelve datos.gov.co"),
    ("satelital", "insumos/satelital", config.PROJECT_ROOT / "data" / "satelital",
     "sat_*", "Imagen de Esri World Imagery por grilla y por lote, y su fecha de captura"),
    ("juridico", "insumos/juridico", config.PROJECT_ROOT / "data" / "juridico",
     "*.json", "UAF por municipio (ANT) y solicitudes de restitución (URT), tal cual responden"),
    ("valor", "insumos/valor", config.PROJECT_ROOT / "data" / "valor",
     "zhg_*.json", "Zonas geoeconómicas rurales del IGAC por municipio, con valor por hectárea"),
    ("entorno", "insumos/entorno", config.PROJECT_ROOT / "data" / "entorno",
     "*.json", "Cruces de cada lote contra geoservicios ambientales, mineros, de hidrocarburos y de riesgo"),
    ("pot", "insumos/pot", config.PROJECT_ROOT / "data" / "pot",
     "*.json", "Norma urbana de cada lote (zonificación rural, clasificación y POT municipal, IGAC LADM-COL)"),
    ("registro", "insumos/registro", config.PROJECT_ROOT / "data" / "registro",
     "*.csv", "Matrículas inmobiliarias conocidas por lote (respuesta de la SNR o consulta manual)"),
    ("contexto", "insumos/contexto", config.PROJECT_ROOT / "data" / "contexto",
     "*.json", "Recurso solar del Global Solar Atlas en el centroide de cada lote"),
    ("poblados", "insumos/poblados", config.PROJECT_ROOT / "data" / "poblados",
     "poblados_*.json", "Nodos place de OSM alrededor de cada grilla, tal cual responde Overpass"),
    ("pot_documentos", "insumos/pot_documentos", config.PROJECT_ROOT / "data" / "pot_documentos",
     "*.*", "Acuerdos y documentos de los POT/PBOT/EOT municipales del área de trabajo (PDF), nombrados DANE_municipio_acto"),
    ("calibracion", "insumos/calibracion", config.PROJECT_ROOT / "data" / "calibracion",
     "*.*", "Lotes catastrales de las plantas de XM usados para calibrar los umbrales a escala de lote"),
]


def _locales(carpeta: Path, patron: str) -> list[Path]:
    if not carpeta.is_dir():
        return []
    return sorted(f for f in carpeta.glob(patron) if f.is_file())


def estado(verbose: bool = True) -> dict:
    """Compara lo que hay en disco con lo que hay en el bucket."""
    resumen = {}
    if verbose:
        print("=" * 78)
        print(f"INSUMOS DERIVADOS  ·  gs://{gcs.BUCKETS[BUCKET]}/insumos")
        print("=" * 78)
        print("%-20s %8s %8s   %s" % ("CONJUNTO", "LOCAL", "BUCKET", "DESCRIPCIÓN"))
        print("-" * 78)

    for clave, prefijo, carpeta, patron, desc in CONJUNTOS:
        locales = _locales(carpeta, patron)
        try:
            remotos = [n for n, _ in gcs.listar(BUCKET, prefijo + "/", limite=5000)
                       if not n.endswith("/")]
            # el prefijo de un conjunto puede solapar con el de su subcarpeta
            remotos = [n for n in remotos
                       if Path(n).parent.as_posix() == prefijo.strip("/")]
        except Exception:
            remotos = []
        resumen[clave] = {"local": len(locales), "bucket": len(remotos),
                          "prefijo": prefijo, "carpeta": carpeta, "patron": patron}
        if verbose:
            print("%-20s %8d %8d   %s" % (clave, len(locales), len(remotos), desc[:38]))

    if verbose:
        print("-" * 78)
    return resumen


def subir(forzar: bool = False) -> int:
    total = 0
    print("=" * 78)
    print("PUBLICANDO INSUMOS EN EL BUCKET")
    print("=" * 78)
    for clave, prefijo, carpeta, patron, _desc in CONJUNTOS:
        locales = _locales(carpeta, patron)
        if not locales:
            print(f"\n{clave}: nada que subir")
            continue
        print(f"\n{clave}  ({len(locales)} archivos)")
        n = gcs.subir_carpeta(BUCKET, prefijo, carpeta, patron, forzar=forzar)
        total += n
        print(f"  subidos {n}, ya estaban {len(locales) - n}")
    print("\n" + "-" * 78)
    print(f"Total subido: {total} archivos")
    return total


def bajar(forzar: bool = False) -> int:
    """Trae del bucket lo que falte en local. Es lo que hace reproducible el proyecto."""
    total = 0
    print("=" * 78)
    print("RECUPERANDO INSUMOS DEL BUCKET")
    print("=" * 78)
    for clave, prefijo, carpeta, _patron, _desc in CONJUNTOS:
        try:
            remotos = [n for n, _ in gcs.listar(BUCKET, prefijo + "/", limite=5000)
                       if not n.endswith("/")
                       and Path(n).parent.as_posix() == prefijo.strip("/")]
        except Exception as exc:
            print(f"\n{clave}: no se pudo listar ({type(exc).__name__})")
            continue
        if not remotos:
            print(f"\n{clave}: nada en el bucket")
            continue
        print(f"\n{clave}  ({len(remotos)} en el bucket)")
        carpeta.mkdir(parents=True, exist_ok=True)
        n = 0
        for objeto in remotos:
            destino = carpeta / Path(objeto).name
            if destino.exists() and not forzar:
                continue
            ruta = gcs.obtener(BUCKET, objeto, forzar=forzar, verbose=False)
            if ruta != destino:
                destino.write_bytes(Path(ruta).read_bytes())
            n += 1
        total += n
        print(f"  bajados {n}, ya estaban {len(remotos) - n}")
    print("\n" + "-" * 78)
    print(f"Total recuperado: {total} archivos")
    return total


def asegurar(clave: str, verbose: bool = False) -> int:
    """
    Recupera del bucket un conjunto concreto si no está en local.

    Pensada para llamarse desde los scripts antes de salir a la fuente original:
    si el insumo ya está publicado no hay por qué volver a descargarlo de Overpass
    o del IGAC.
    """
    entrada = next((c for c in CONJUNTOS if c[0] == clave), None)
    if entrada is None:
        return 0
    _clave, prefijo, carpeta, patron, _desc = entrada
    if _locales(carpeta, patron):
        return 0
    try:
        remotos = [n for n, _ in gcs.listar(BUCKET, prefijo + "/", limite=5000)
                   if not n.endswith("/")
                   and Path(n).parent.as_posix() == prefijo.strip("/")]
    except Exception:
        return 0
    if not remotos:
        return 0
    carpeta.mkdir(parents=True, exist_ok=True)
    n = 0
    for objeto in remotos:
        destino = carpeta / Path(objeto).name
        if destino.exists():
            continue
        ruta = gcs.obtener(BUCKET, objeto, verbose=False)
        if Path(ruta) != destino:
            destino.write_bytes(Path(ruta).read_bytes())
        n += 1
    if verbose and n:
        print(f"  recuperados {n} archivos de {clave} desde el bucket")
    return n


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Insumos derivados en el bucket")
    p.add_argument("accion", choices=["estado", "subir", "bajar"])
    p.add_argument("--forzar", action="store_true")
    a = p.parse_args(argv)

    if a.accion == "estado":
        estado()
    elif a.accion == "subir":
        subir(forzar=a.forzar)
        print()
        estado()
    else:
        bajar(forzar=a.forzar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
