"""
HTML del reporte de lotes a partir del JSON de datos.py.

    python -m reporte_predios.html

Escribe outputs/reporte/reporte_predios.html y su copia en entregables/, junto con las
imágenes que referencia en satelital/.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config
from reporte_predios.datos import JSON_SALIDA, SALIDA
from reporte_predios.plantilla import HTML

ENTREGABLES = config.PROJECT_ROOT / "entregables"


def main(argv=None) -> int:
    """Genera el HTML, lo copia a entregables/ junto con sus imágenes e imprime el resumen."""
    if not JSON_SALIDA.exists():
        raise SystemExit(f"No existe {JSON_SALIDA.name}. Corre antes: "
                         f"python -m reporte_predios.datos")
    datos = JSON_SALIDA.read_text(encoding="utf-8")
    # Un "</script>" dentro del JSON cerraría el bloque antes de tiempo.
    datos = datos.replace("</", "<\\/")
    html = HTML.replace("__DATOS__", datos)

    salida = SALIDA / "reporte_predios.html"
    salida.write_text(html, encoding="utf-8")
    ENTREGABLES.mkdir(exist_ok=True)
    shutil.copy2(salida, ENTREGABLES / salida.name)

    d = json.loads(JSON_SALIDA.read_text(encoding="utf-8"))
    n_lotes = {k: len(v) for k, v in d["lotes"].items()}
    con_sat = sum(1 for v in d["lotes"].values() for l in v if l.get("sat"))

    # Se copian a entregables/satelital/ solo las imágenes que este HTML referencia.
    copiadas = 0
    fuentes = ([c.get("sat") for c in d["celdas"]] + [l.get("sat") for v in d["lotes"].values() for l in v]
               + [l.get("sat2") for v in d["lotes"].values() for l in v])
    for s in fuentes:
        if not s:
            continue
        origen = SALIDA / s["src"]
        destino = ENTREGABLES / s["src"]
        if origen.exists() and (not destino.exists()
                                or destino.stat().st_mtime < origen.stat().st_mtime):
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
            copiadas += 1
    print("=" * 74)
    print("REPORTE DE LOTES · HTML")
    print("=" * 74)
    print(f"  grillas: {len(d['celdas'])}   lotes: {n_lotes}   con imagen: {con_sat}")
    print(f"  HTML -> {salida}")
    print(f"  copia -> {ENTREGABLES / salida.name}  (+ {copiadas} imágenes a entregables/satelital/)")
    print(f"  Tamaño: {salida.stat().st_size / 1024:.0f} KB")
    print("  Para compartir, llevar el HTML y la carpeta satelital/ juntos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
