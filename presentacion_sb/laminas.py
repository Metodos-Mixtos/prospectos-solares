"""Vuelca el PDF compilado a PNG, una imagen por lamina.

Sirve para revisar la presentacion lamina a lamina sin abrir el PDF.

Uso:  python laminas.py
"""
import pathlib
import sys

import pymupdf

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PDF = RAIZ / "outputs" / "presentacion_sb" / "build" / "prospectos_solares_sb.pdf"
SAL = RAIZ / "outputs" / "presentacion_sb" / "laminas"


def main():
    # Ruta alterna por argumento, para cuando el PDF de siempre esta abierto en un
    # visor y hay que compilar con otro nombre.
    pdf = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    SAL.mkdir(parents=True, exist_ok=True)
    for viejo in SAL.glob("*.png"):
        viejo.unlink()
    doc = pymupdf.open(pdf)
    for i, pagina in enumerate(doc, 1):
        pagina.get_pixmap(dpi=110).save(SAL / f"{i:02d}.png")
    print(f"{doc.page_count} laminas en {SAL}")


if __name__ == "__main__":
    main()
