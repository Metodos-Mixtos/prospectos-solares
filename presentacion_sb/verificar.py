"""Verifica la presentacion compilada.

Tres comprobaciones, porque cada una atrapa un fallo distinto:
  1. Contenido que se sale de la lamina.
  2. Contenido que LaTeX descarta en silencio cuando la lamina se llena.
     Este es el peligroso: no da aviso ninguno y la nota desaparece.
  3. Palabras partidas por justificacion.

Uso:  python verificar.py
"""
import io
import pathlib
import re
import sys

import fitz

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TEX = RAIZ / "presentacion_sb" / "prospectos_solares_sb.tex"
PDF = RAIZ / "outputs" / "presentacion_sb" / "build" / "prospectos_solares_sb.pdf"


# Ruta alterna por argumento: cuando el PDF de siempre esta abierto en un visor,
# Windows lo bloquea y hay que compilar con otro nombre; y desde que hay dos
# guiones, el tecnico y el comercial, hay que poder revisar cualquiera de los dos.
if len(sys.argv) > 1:
    PDF = pathlib.Path(sys.argv[1])
    # El guion que le corresponde se deduce del nombre del PDF, para no tener que
    # pasarlo aparte y para no comparar un PDF contra las notas de otro.
    for candidato in (RAIZ / "presentacion_sb" / (PDF.stem + ".tex"),
                      RAIZ / "presentacion_sb" / "prospectos_solares_sb.tex"):
        if candidato.exists():
            TEX = candidato
            break


def texto_pdf(doc):
    return "\n".join(p.get_text() for p in doc)


def normalizar(s):
    # Primero los escapes de un solo caracter (\_ \& \% \#): en el PDF salen como
    # el caracter suelto. Si no se deshacen aqui, cada ruta con guion bajo produce
    # un falso positivo de nota descartada.
    s = re.sub(r"\\([_&%#$])", r"\1", s)
    # Espacios finos y demas comandos de un signo: en el PDF salen como espacio.
    s = re.sub(r"\\[,;:!]", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", " ", s)
    s = s.replace("{", " ").replace("}", " ").replace("~", " ")
    return re.sub(r"\s+", " ", s).strip()


def main():
    doc = fitz.open(PDF)
    H = doc[0].rect.height
    fallos = []

    # 1. desbordes y choques con el pie
    #    El limite no es una fraccion fija de la pagina sino el propio pie de
    #    lamina, cuando lo hay: las laminas [plain] no lo llevan y pueden bajar mas.
    GAP = 4.0

    def es_pie(b):
        """El pie son el rotulo de seccion en mayusculas y el numero de lamina.
        Identificarlo por su contenido y no por su posicion evita que una nota
        que ya esta pisando el pie se confunda con el pie y pase inadvertida."""
        if b[1] <= H * 0.93:
            return False
        t = b[4].strip()
        return t.isdigit() or (t == t.upper() and len(t) < 60)

    for i, p in enumerate(doc, 1):
        bloques = [b for b in p.get_text("blocks") if b[4].strip()]
        pie = [b for b in bloques if es_pie(b)]
        techo = min((b[1] for b in pie), default=H) - GAP
        cajas = [b[3] for b in bloques if b not in pie]
        for x in p.get_images(full=True):
            try:
                cajas.append(p.get_image_bbox(x).y1)
            except Exception:
                pass
        if cajas and max(cajas) > techo:
            que = "choca con el pie" if pie else "se sale de la lamina"
            fallos.append(f"lamina {i}: {que}, contenido a {max(cajas):.0f} pt, limite {techo:.0f}")

    # 2. contenido descartado: cada \fuente debe aparecer en el PDF
    src = io.open(TEX, encoding="utf-8").read()
    todo = texto_pdf(doc)
    todo_n = normalizar(todo)
    for m in re.finditer(r"\\fuente\{", src):
        i, prof = m.end(), 1
        while i < len(src) and prof:
            prof += (src[i] == "{") - (src[i] == "}")
            i += 1
        cuerpo = normalizar(src[m.end():i - 1])
        clave = " ".join(cuerpo.split()[:6])
        # Sin espacios en ninguno de los dos lados: los comandos de LaTeX dejan
        # separaciones que el PDF no reproduce, y comparar con espacios da falsos
        # positivos en cada nota que lleve una ruta entre \texttt.
        aplanar = lambda t: re.sub(r"\s+", "", t)
        if clave and aplanar(clave) not in aplanar(todo_n):
            fallos.append(f"NOTA DESCARTADA, no aparece en el PDF: '{clave}...'")

    # 3. palabras partidas
    partidas = [i for i, p in enumerate(doc, 1) if "-\n" in p.get_text()]
    if partidas:
        fallos.append(f"palabras partidas en las laminas {partidas}")

    print(f"laminas: {doc.page_count}")
    if fallos:
        print("FALLOS:")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("OK: sin desbordes, sin notas descartadas, sin palabras partidas")


if __name__ == "__main__":
    main()
