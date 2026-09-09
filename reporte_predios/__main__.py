"""
Reporte de lotes: de las grillas seleccionadas al lote y su ficha.

    .venv\\Scripts\\python.exe -m reporte_predios
    .venv\\Scripts\\python.exe -m reporte_predios --grillas mi_seleccion.geojson
    .venv\\Scripts\\python.exe -m reporte_predios --sin-satelital

Entrada: el GeoJSON o CSV exportado desde el reporte de grillas (por defecto
outputs/reporte/grillas_para_predios.geojson). Requiere los lotes evaluados con
predios.lotes. Los dos pasos por separado: reporte_predios.datos y reporte_predios.html.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    from . import datos, html
    codigo = datos.main(argv)
    if codigo:
        return codigo
    return html.main()


if __name__ == "__main__":
    sys.exit(main())
