"""Compila las dos presentaciones y publica los seis entregables.

Existe porque hacerlo a mano ya costo caro: el 2 de septiembre de 2026 se
compilo la version comercial y no se publico, de modo que el PDF que estaba en
entregables/ llevaba una revision de retraso y decia cosas que la fuente ya no
decia. Aqui la compilacion y la publicacion son el mismo acto.

QUE PRODUCE, Y POR QUE CADA UNO

  presentacion_<mazo>.pdf          Para enviar y para proyectar. Es la
                                   composicion de LaTeX, exacta.
  presentacion_<mazo>.pptx         EDITABLE. Cada texto es un cuadro de texto y
                                   cada figura una imagen suelta: se mueven, se
                                   reescriben y se redimensionan.
  presentacion_<mazo>_imagen.pptx  Una imagen por lamina. No se edita nada, y a
                                   cambio se ve identica al PDF pixel a pixel.
                                   Util para proyectar desde PowerPoint.

El PPTX editable lleva el nombre corto a proposito: es el que se abre cuando
alguien hace doble clic sin pensarlo, y es el que casi siempre se quiere.

EL PESO DEL PDF

Las capturas satelitales viajan sin perdida y son casi todo el peso. Se
recodifican solo las laminas donde la diferencia queda por debajo del umbral de
percepcion, y la lamina que no lo pasa conserva su calidad intacta. La medida es
la relacion senal a ruido, lamina a lamina; no se decide a ojo.

Uso:  python publicar.py [comercial|tecnica]     (sin argumentos, las dos)
"""
import math
import pathlib
import shutil
import subprocess
import sys

import numpy as np
import pymupdf

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
BUILD = RAIZ / "outputs" / "presentacion_sb" / "build"
ENT = RAIZ / "entregables"

MAZOS = {
    "comercial": ("prospectos_solares_comercial", "presentacion_comercial"),
    "tecnica": ("prospectos_solares_sb", "presentacion_tecnica"),
}

#: Calidad del JPEG con que se recodifican las laminas fotograficas.
CALIDAD = 88
#: Por debajo de esta relacion senal a ruido la lamina se deja como estaba. A
#: 45 dB la diferencia esta muy por debajo del umbral de percepcion; medido, las
#: laminas de fotografia dan entre 52 y 57 dB y las de grafico vectorial entre
#: 24 y 31, que si se notan.
PSNR_MINIMO = 45.0
PPP_COMPARA = 130


def _psnr(a, b):
    if a.shape != b.shape:
        return -1.0
    d = a.astype(np.float64) - b.astype(np.float64)
    e = float((d * d).mean())
    return math.inf if e == 0 else 10 * math.log10(255.0 * 255.0 / e)


def _matriz(pg):
    px = pg.get_pixmap(dpi=PPP_COMPARA)
    return np.frombuffer(px.samples, dtype=np.uint8).reshape(px.height, px.width, px.n)


def aligerar(origen, destino):
    """Copia el PDF comprimiendo solo las laminas donde no se nota."""
    fuente = pymupdf.open(origen)
    salida = pymupdf.open()
    tocadas, intactas = [], []

    for n in range(fuente.page_count):
        antes = _matriz(fuente[n])
        prueba = pymupdf.open()
        prueba.insert_pdf(fuente, from_page=n, to_page=n)
        prueba.rewrite_images(quality=CALIDAD, lossy=True, lossless=True,
                              color=True, gray=True, bitonal=False)
        crudo = prueba.tobytes(garbage=4, deflate=True, clean=True)
        prueba.close()
        rev = pymupdf.open("pdf", crudo)
        v = _psnr(antes, _matriz(rev[0]))
        if v >= PSNR_MINIMO:
            salida.insert_pdf(rev)
            tocadas.append(n + 1)
        else:
            salida.insert_pdf(fuente, from_page=n, to_page=n)
            if v is not math.inf:
                intactas.append((n + 1, v))
        rev.close()

    salida.save(destino, garbage=4, deflate=True, clean=True)
    salida.close()
    fuente.close()
    return tocadas, intactas


def corre(*orden):
    r = subprocess.run(orden, cwd=AQUI, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        cola = "\n".join((r.stdout or "").splitlines()[-25:])
        raise SystemExit(f"fallo {' '.join(orden[:3])}\n{cola}\n{r.stderr}")
    return r.stdout


def publicar(mazo):
    guion, nombre = MAZOS[mazo]
    print(f"\n=== {mazo} ===")

    # Dos pasadas: la primera resuelve las referencias de seccion del pie.
    for _ in range(2):
        corre("pdflatex", "-interaction=nonstopmode", "-halt-on-error",
              f"-output-directory={BUILD}", f"{guion}.tex")
    pdf = BUILD / f"{guion}.pdf"
    print(f"  compilado: {pymupdf.open(pdf).page_count} laminas")

    salida = corre(sys.executable, "verificar.py", str(pdf))
    print("  " + salida.strip().splitlines()[-1])

    # Windows bloquea el fichero que un visor tiene abierto. No es motivo para
    # abandonar la publicacion entera: se hace lo que se puede y se dice cual
    # quedo pendiente.
    pendientes = []

    def publica(destino, hacer):
        if destino.exists() and not _escribible(destino):
            pendientes.append(destino.name)
            print(f"  ABIERTO, sin publicar: {destino.name}")
            return
        hacer(destino)
        print(f"  {destino.name}: {destino.stat().st_size / 1048576:.2f} MiB")

    def _pdf(destino):
        tocadas, intactas = aligerar(pdf, destino)
        print(f"    {len(tocadas)} laminas comprimidas, {len(intactas)} intactas")

    publica(ENT / f"{nombre}.pdf", _pdf)
    publica(ENT / f"{nombre}.pptx",
            lambda d: corre(sys.executable, "powerpoint_editable.py", str(pdf), str(d)))
    publica(ENT / f"{nombre}_imagen.pptx",
            lambda d: corre(sys.executable, "powerpoint.py", str(pdf), str(d)))
    return pendientes


def _escribible(f):
    try:
        with open(f, "r+b"):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    cuales = sys.argv[1:] or list(MAZOS)
    faltan = []
    for m in cuales:
        if m not in MAZOS:
            raise SystemExit(f"mazo desconocido: {m}. Hay {list(MAZOS)}")
        faltan += publicar(m)
    if faltan:
        print("\nQuedaron sin publicar, por estar abiertos: " + ", ".join(faltan))
        print("Cierralos y vuelve a correr esto.")
        raise SystemExit(1)
