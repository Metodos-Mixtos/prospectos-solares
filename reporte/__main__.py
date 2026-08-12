"""
Genera el reporte de caracterización de grillas candidatas.

Un solo comando hace todo: lee las candidatas, las enriquece, las clasifica, descarga lo
que le falte de fuera y escribe las salidas.

    .venv\\Scripts\\python.exe -m reporte

Sobre otras candidatas, que es el caso normal cuando el modelo se vuelve a correr:

    .venv\\Scripts\\python.exe -m reporte --celdas ruta/a/mis_celdas.gpkg

Al archivo de entrada solo se le exige una columna cell_id, la geometría y las
covariables del panel. Todo lo demás lo deriva.

Deja en outputs/reporte:

    reporte_grillas.html   el reporte, con la carpeta satelital/ al lado
    grillas_candidatas.*   la tabla en CSV, XLSX, GPKG, GeoJSON, KML y JSON
    zonas_prospeccion.csv  las zonas agrupadas
    concurrencia_subestaciones.csv   competencia por punto de conexión

Los dos pasos se pueden correr por separado si solo se quiere rehacer el HTML tras tocar
el diseño, que es bastante más rápido que recalcularlo todo:

    .venv\\Scripts\\python.exe -m reporte.datos
    .venv\\Scripts\\python.exe -m reporte.html
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    from . import datos, html

    # Los argumentos van al primer paso, que es el que decide qué celdas se evalúan y
    # con qué perfil. El HTML solo lee lo que aquel dejó escrito.
    codigo = datos.main(argv)
    if codigo:
        return codigo
    return html.main()


if __name__ == "__main__":
    sys.exit(main())
