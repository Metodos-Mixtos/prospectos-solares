"""
De dónde salen los parámetros de la matriz de criterios.

Los tres análisis que sostienen el índice de aptitud. Ninguno corre al generar el
reporte: se ejecutan de vez en cuando, sus resultados se pegan a mano en CRITERIOS y
PERFILES dentro de reporte/datos.py, y viven aquí para que cualquiera pueda auditarlos
o rehacerlos cuando cambien los datos de partida.

Se pegan a mano y no se calculan al vuelo a propósito. Hacerlo en cada corrida obligaría
a leer el panel completo y a consultar Overpass cada vez, y sobre todo un umbral que
cambia solo es un umbral que nadie puede auditar: dos personas que generen el reporte el
mismo día tienen que obtener la misma nota para la misma grilla.

    pesos          Cuánto separa cada covariable las celdas con planta de las demás.
                   De ahí sale la d de Cohen con la que se pondera cada criterio.

    umbrales       Los tres puntos de la escala de cada criterio, leídos de la
                   distribución de las plantas que ya operan.

    subestaciones  Contraste de la capa de subestaciones contra OpenStreetMap, para
                   saber cuánta red le falta y si el criterio de conexión mide bien.

Uso:
    .venv\\Scripts\\python.exe -m soporte.calibracion pesos
    .venv\\Scripts\\python.exe -m soporte.calibracion umbrales --mw 20
    .venv\\Scripts\\python.exe -m soporte.calibracion subestaciones
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
# La raíz del proyecto va al path para que los tres análisis puedan importar config,
# gcs y reporte_grillas igual que cuando estaban sueltos en la raíz.
# La raiz y soporte/ van al path: config y gcs viven en soporte, y los
# paquetes del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]

ANALISIS = {
    "pesos": "Efecto de cada covariable, la d que pondera los criterios",
    "umbrales": "Los tres puntos de la escala de cada criterio",
    "subestaciones": "Cuánta red le falta a la capa de subestaciones",
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    sub, resto = argv[0], argv[1:]
    if sub not in ANALISIS:
        print(f"Análisis desconocido: {sub}\n")
        for k, v in ANALISIS.items():
            print(f"  {k:<15} {v}")
        return 2

    modulo = __import__(f"calibracion.{sub}", fromlist=["main"])
    fn = getattr(modulo, "main")
    # Los tres nacieron como scripts sueltos y no todos aceptan argumentos.
    try:
        return fn(resto)
    except TypeError:
        return fn()


if __name__ == "__main__":
    sys.exit(main())
