"""
Verificador del entorno del proyecto.

Comprueba, en orden, y no se detiene en el primer fallo:

  1. Que la versión de Python sea la del proyecto.
  2. Que las librerías del núcleo estén instaladas y con qué versión.
  3. Que estén las del procedimiento de lotes, incluido el navegador de playwright,
     que pip no descarga y hay que pedir aparte.
  4. Que modelo/functions.py importe sin errores.
  5. Que haya credenciales de Google Cloud y que los buckets respondan.
  6. Que las rutas de datos resuelvan (delega en config.check).

Uso:

    python herramientas/check_setup.py

En Windows con el entorno virtual del proyecto:

    .venv\\Scripts\\python.exe herramientas/check_setup.py
"""

from __future__ import annotations

import importlib
import pathlib
import sys
from pathlib import Path

# La raiz y soporte/ van al path: config y gcs viven en soporte, y los paquetes del
# proyecto (modelo, predios, reporte) se importan desde la raiz. Esta carpeta cuelga de
# soporte/, asi que la raiz esta dos niveles arriba.
_raiz = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]

# (módulo importable, nombre en pip). Difieren cuando el paquete se llama distinto.
NUCLEO = [
    ("geopandas", "geopandas"),
    ("shapely", "shapely"),
    ("pyproj", "pyproj"),
    ("pyogrio", "pyogrio"),
    ("rasterio", "rasterio"),
    ("contextily", "contextily"),
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("sklearn", "scikit-learn"),
    ("skgstat", "scikit-gstat"),
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
    ("folium", "folium"),
    ("mapclassify", "mapclassify"),
    ("requests", "requests"),
    ("pypdf", "pypdf"),
    ("openpyxl", "openpyxl"),
]

#: Versión de Python con la que se desarrolló y probó el proyecto. Ver requirements.txt.
PYTHON_ESPERADO = (3, 12)

# Hacen falta para el procedimiento de lotes (predios/, reporte_predios/) y para los
# insumos. No los pedían los notebooks 1 y 2, y por eso no estaban en NUCLEO.
LOTES = [
    ("google.cloud.storage", "google-cloud-storage"),
    ("PIL", "pillow"),
    ("pymupdf", "pymupdf"),  # insumos/barras.py lo importa como `fitz`
    ("playwright", "playwright"),
]

# Solo hacen falta para los notebooks 1.1 y 1.2, que todavía son código heredado.
BAYESIANO = [
    ("pymc", "pymc"),
    ("pytensor", "pytensor"),
    ("arviz", "arviz"),
]


def _version(mod) -> str:
    for attr in ("__version__", "version", "VERSION"):
        v = getattr(mod, attr, None)
        if isinstance(v, str):
            return v
    # Algunos paquetes, playwright entre ellos, no exponen __version__.
    try:
        from importlib.metadata import version as _v
        return _v(mod.__name__.split(".")[0])
    except Exception:
        return "?"


def revisar_grupo(titulo: str, paquetes, obligatorio: bool) -> list[str]:
    """Importa cada paquete del grupo e imprime el resultado. Devuelve los que faltan."""
    print(f"\n{titulo}")
    print("-" * 70)
    faltantes = []
    ancho = max(len(m) for m, _ in paquetes)

    for modulo, pip_name in paquetes:
        try:
            mod = importlib.import_module(modulo)
        except ImportError:
            faltantes.append(pip_name)
            marca = "FALTA" if obligatorio else "  --  "
            print(f"[{marca}] {modulo.ljust(ancho)}")
        except Exception as exc:
            # Un paquete instalado pero roto (DLL, versión incompatible) importa mal.
            faltantes.append(pip_name)
            print(f"[ERROR] {modulo.ljust(ancho)}  {type(exc).__name__}: {exc}")
        else:
            print(f"[OK   ] {modulo.ljust(ancho)}  {_version(mod)}")

    return faltantes


def revisar_navegador() -> str | None:
    """
    El chromium empaquetado de playwright. pip instala la librería pero no el binario:
    hay que pedirlo con `python -m playwright install chromium`. Sin él, el paso 4
    (matrícula en la Superintendencia) falla al abrir el navegador.

    Devuelve el aviso si falta, o None si está.
    """
    print("\nNavegador de playwright (paso 4, matrícula)")
    print("-" * 70)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[  --  ] playwright no está instalado; se omite")
        return None
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            version = navegador.version
            navegador.close()
    except Exception as exc:
        print(f"[FALTA] chromium  {type(exc).__name__}")
        print("        Descárgalo una vez por máquina:")
        print("            .venv\\Scripts\\python.exe -m playwright install chromium")
        return "chromium de playwright sin descargar"
    print(f"[OK   ] chromium  {version}")
    return None


def revisar_bucket() -> str | None:
    """
    Credenciales de Google Cloud y lectura de los dos buckets. Sin esto no hay datos:
    el repositorio trae código, no insumos. Devuelve el aviso si algo falla.
    """
    print("\nGoogle Cloud (los datos viven en los buckets, no en el repositorio)")
    print("-" * 70)
    try:
        import gcs
    except Exception as exc:
        print(f"[FALTA] gcs.py no importa  {type(exc).__name__}: {exc}")
        return "gcs.py no importa"

    problemas = []
    for alias in ("geoinfo", "prospectos"):
        try:
            gcs.listar(alias, "", limite=1)
        except Exception as exc:
            nombre = gcs.BUCKETS.get(alias, alias)
            print(f"[FALTA] gs://{nombre}  {type(exc).__name__}")
            problemas.append(nombre)
        else:
            print(f"[OK   ] gs://{gcs.BUCKETS.get(alias, alias)}  se puede leer")

    if problemas:
        print("        Inicia sesión, o pide acceso de lectura a esos buckets:")
        print("            gcloud auth application-default login")
        print("            gcloud config set project mmc-general")
        return "sin acceso a " + ", ".join(problemas)
    return None


#: Los cinco archivos del shapefile veredal del DANE, en gs://geoinfo.
BASE_VEREDAL = [f"base_veredas/base_veredas.{ext}"
                for ext in ("shp", "dbf", "shx", "prj", "cpg")]


def revisar_base_veredal() -> str | None:
    """
    La base veredal del DANE, de la que salen el nombre del municipio y el de la vereda.

    Es el unico insumo que ningun comando trae solo: `insumos bajar` cubre el bucket
    prospectos_solares, y `config.asegurar_datos()` cubre el panel, las granjas de XM y
    las subestaciones, pero esta capa vive en gs://geoinfo y se lee por ruta directa. Si
    falta, el codigo no se cae: municipio y vereda salen vacios en el reporte y en las
    fichas de lote. Se prefiere decirlo aqui antes que descubrirlo en el entregable.
    """
    print("\nBase veredal del DANE (nombre de municipio y de vereda)")
    print("-" * 70)
    try:
        import config
    except Exception:
        print("[  --  ] no se pudo cargar config.py; se omite")
        return None

    carpeta = config.DATA_DIR / "geoinfo" / "base_veredas"
    faltan = [n for n in BASE_VEREDAL if not (carpeta / pathlib.Path(n).name).exists()]
    if not faltan:
        print(f"[OK   ] {carpeta}")
        return None

    print(f"[FALTA] {carpeta}")
    print("        No la trae ningun comando de descarga. Son 352 MB y se piden asi:")
    for objeto in BASE_VEREDAL:
        print(f'            .venv\\Scripts\\python.exe soporte\\gcs.py get geoinfo "{objeto}"')
    print("        Sin ella el proyecto corre igual, pero municipio y vereda van vacios.")
    return "falta la base veredal (municipio y vereda quedan vacios)"


def main() -> int:
    print("=" * 70)
    print("VERIFICACIÓN DEL ENTORNO - prospectos-solares")
    print("=" * 70)
    print(f"Python     : {sys.version.split()[0]}")
    print(f"Ejecutable : {sys.executable}")

    avisos = []
    if sys.version_info[:2] != PYTHON_ESPERADO:
        esperado = ".".join(str(n) for n in PYTHON_ESPERADO)
        actual = ".".join(str(n) for n in sys.version_info[:2])
        print(f"             aviso: el proyecto se probó con Python {esperado}, "
              f"y este es {actual}")
        avisos.append(f"Python {actual} en vez de {esperado}")

    faltan_nucleo = revisar_grupo("Núcleo (notebooks 1 y 2)", NUCLEO, obligatorio=True)
    faltan_lotes = revisar_grupo("Procedimiento de lotes y bucket", LOTES, obligatorio=True)
    revisar_grupo("Bayesiano (notebooks 1.1 y 1.2, opcional)", BAYESIANO, obligatorio=False)

    # modelo/functions.py solo se puede importar si el núcleo está completo
    print("\nMódulo local")
    print("-" * 70)
    if faltan_nucleo:
        print("[  --  ] modelo/functions.py  (se omite, faltan dependencias del núcleo)")
    else:
        try:
            importlib.import_module("modelo.functions")
        except Exception as exc:
            print(f"[ERROR] modelo/functions.py  {type(exc).__name__}: {exc}")
            faltan_nucleo.append("modelo/functions.py no importa")
        else:
            print("[OK   ] modelo/functions.py")

    aviso_navegador = revisar_navegador()
    if aviso_navegador:
        avisos.append(aviso_navegador)

    aviso_bucket = revisar_bucket()
    if aviso_bucket:
        avisos.append(aviso_bucket)

    aviso_veredas = revisar_base_veredal()
    if aviso_veredas:
        avisos.append(aviso_veredas)

    # Rutas de datos
    print()
    try:
        import config
    except Exception as exc:
        print(f"No se pudo cargar config.py: {type(exc).__name__}: {exc}")
        rutas_ok = False
    else:
        rutas_ok = config.check()

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    if faltan_nucleo or faltan_lotes:
        print("Faltan dependencias. Instálalas con:")
        print("    .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    else:
        print("Dependencias completas.")

    if rutas_ok:
        print("Rutas de datos disponibles. Se pueden correr los notebooks 1 y 2.")
    else:
        print("Faltan datos. Tráelos del bucket; la guía está en docs/REPLICAR.md.")
        print("El notebook 2 (IGAC) sí se puede correr igual, porque descarga los")
        print("predios directamente del FeatureServer.")

    if avisos:
        print("\nAvisos:")
        for a in avisos:
            print(f"  - {a}")

    print("\nPuesta en marcha desde cero: docs/REPLICAR.md")

    return 0 if (not faltan_nucleo and not faltan_lotes and rutas_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
