"""
Los insumos del reporte: descargarlos de su fuente y sincronizarlos con el bucket.

Cada módulo de este paquete trae una cosa de fuera, siempre cruda y siempre cacheada:

    vias           red vial de OpenStreetMap, por bloque de grillas
    lineas         líneas de transmisión de OpenStreetMap, malla nacional
    barras         capacidad por barra de los informes de la UPME
    restricciones  Reserva Forestal de Ley 2ª del MinAmbiente
    conflicto      acciones bélicas del SIEVCAC del CNMH
    satelital      imagen de Esri World Imagery, una por grilla
    normativa      las normas completas que sustentan los criterios

El reporte llama solo a los que necesita y descarga lo que falte, así que en general no
hace falta ejecutar nada de aquí a mano. Sirve para forzar una descarga, para refrescar
una capa o para publicar en el bucket lo que se haya bajado.

Uso:
    .venv\\Scripts\\python.exe -m insumos bajar          # trae del bucket lo que falte
    .venv\\Scripts\\python.exe -m insumos subir          # publica lo descargado
    .venv\\Scripts\\python.exe -m insumos estado         # compara disco contra bucket
    .venv\\Scripts\\python.exe -m insumos satelital      # corre un módulo concreto
    .venv\\Scripts\\python.exe -m insumos vias --celdas otras.gpkg
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Módulos que traen datos de fuera. Cada uno se puede ejecutar por su cuenta.
FUENTES = {
    "vias": "Red vial de OpenStreetMap",
    "lineas": "Líneas de transmisión de OpenStreetMap",
    "barras": "Capacidad por barra de la UPME",
    "restricciones": "Reserva Forestal de Ley 2ª del MinAmbiente",
    "conflicto": "Acciones bélicas del SIEVCAC (CNMH)",
    "satelital": "Imagen satelital de Esri World Imagery",
    "normativa": "Normas que sustentan los criterios",
}

#: Operaciones sobre el bucket, definidas en __init__.py.
BUCKET = {
    "bajar": "Trae del bucket lo que falte en disco",
    "subir": "Publica en el bucket lo descargado",
    "estado": "Compara lo que hay en disco con lo que hay en el bucket",
}


def _ayuda() -> int:
    print(__doc__)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        return _ayuda()

    sub, resto = argv[0], argv[1:]

    if sub in BUCKET:
        from . import bajar, estado, subir
        forzar = "--forzar" in resto
        if sub == "bajar":
            bajar(forzar=forzar)
        elif sub == "subir":
            subir(forzar=forzar)
        else:
            estado()
        return 0

    if sub in FUENTES:
        modulo = __import__(f"insumos.{sub}", fromlist=["main"])
        fn = getattr(modulo, "main")
        try:
            return fn(resto)
        except TypeError:
            return fn()

    print(f"No existe: {sub}\n")
    print("  Sobre el bucket:")
    for k, v in BUCKET.items():
        print(f"    {k:<15} {v}")
    print("\n  Fuentes:")
    for k, v in FUENTES.items():
        print(f"    {k:<15} {v}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
