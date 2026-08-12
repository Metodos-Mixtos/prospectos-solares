"""
Verificador del entorno del proyecto.

Comprueba tres cosas, en orden, y no se detiene en el primer fallo:

  1. Que las librerías del núcleo estén instaladas y con qué versión.
  2. Que functions.py importe sin errores.
  3. Que las rutas de datos resuelvan (delega en config.check).

Uso:

    python herramientas/check_setup.py

En Windows con el entorno virtual del proyecto:

    .venv\\Scripts\\python.exe herramientas/check_setup.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# La raiz del proyecto va al path: config.py y functions.py viven un nivel arriba de
# esta carpeta, y el verificador tiene que poder importarlos para comprobarlos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def main() -> int:
    print("=" * 70)
    print("VERIFICACIÓN DEL ENTORNO - prospectos-solares")
    print("=" * 70)
    print(f"Python     : {sys.version.split()[0]}")
    print(f"Ejecutable : {sys.executable}")

    faltan_nucleo = revisar_grupo("Núcleo (notebooks 1 y 2)", NUCLEO, obligatorio=True)
    revisar_grupo("Bayesiano (notebooks 1.1 y 1.2, opcional)", BAYESIANO, obligatorio=False)

    # functions.py solo se puede importar si el núcleo está completo
    print("\nMódulo local")
    print("-" * 70)
    if faltan_nucleo:
        print("[  --  ] functions.py  (se omite, faltan dependencias del núcleo)")
    else:
        try:
            importlib.import_module("functions")
        except Exception as exc:
            print(f"[ERROR] functions.py  {type(exc).__name__}: {exc}")
            faltan_nucleo.append("functions.py no importa")
        else:
            print("[OK   ] functions.py")

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

    if faltan_nucleo:
        print("Faltan dependencias del núcleo. Instálalas con:")
        print("    pip install -r requirements.txt")
    else:
        print("Dependencias del núcleo completas.")

    if rutas_ok:
        print("Rutas de datos disponibles. Se pueden correr los notebooks 1 y 2.")
    else:
        print("Faltan datos. El notebook 2 (IGAC) sí se puede correr igual,")
        print("porque descarga los predios directamente del FeatureServer.")

    return 0 if (not faltan_nucleo and rutas_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
