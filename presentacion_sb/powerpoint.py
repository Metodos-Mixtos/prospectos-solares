"""Convierte el PDF compilado en un PPTX, una lamina por diapositiva.

Cada diapositiva lleva la lamina rasterizada a sangre completa. Es deliberado:
el guion usa Helvetica, cajas de tikz, filetes de medida fija y figuras
vectoriales de matplotlib, y ningun conversor a formas de PowerPoint reproduce
eso sin mover tipografia ni espaciado. Rasterizando, lo que se ve en el PPTX es
exactamente lo que se ve en el PDF, en la misma proporcion 16:9.

La contrapartida, que hay que decir: el texto no queda editable en PowerPoint.
Para cambiar una lamina se edita el .tex y se vuelve a exportar.

Uso:  python powerpoint.py [ruta_pdf]
"""
import datetime
import pathlib
import sys
import zipfile

import pymupdf
from pptx import Presentation
from pptx.util import Inches

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PDF = RAIZ / "outputs" / "presentacion_sb" / "build" / "prospectos_solares_sb.pdf"
SAL = RAIZ / "entregables" / "presentacion_prospectos_solares.pptx"
TMP = RAIZ / "outputs" / "presentacion_sb" / "_pptx"

#: 450 ppp sobre una pagina de 6,3 pulgadas dejan unos 2.835 px de ancho, que
#: proyectados a 13,3 pulgadas son unos 213 ppp. Samuel pidio la maxima resolucion
#: posible aunque el fichero pese mas.
DPI = 450
#: Firma del entregable, en los tres sitios donde PowerPoint la enseña.
AUTOR = "Métodos Mixtos Consultores"
#: 16:9 en el tamano que PowerPoint llama panoramico.
ANCHO, ALTO = Inches(13.333), Inches(7.5)


def main():
    # Con dos guiones, el tecnico y el comercial, la salida se deduce del nombre
    # del PDF para no tener que pasarla aparte ni arriesgarse a pisar el otro.
    pdf = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    global SAL
    if len(sys.argv) > 2:
        SAL = pathlib.Path(sys.argv[2])
    TMP.mkdir(parents=True, exist_ok=True)
    for viejo in TMP.glob("*.png"):
        viejo.unlink()

    doc = pymupdf.open(pdf)
    pres = Presentation()
    pres.slide_width, pres.slide_height = ANCHO, ALTO
    # El diseno 6 de la plantilla por defecto es el unico sin marcadores de
    # posicion: con cualquier otro, PowerPoint dibuja cuadros de titulo vacios
    # encima de la imagen.
    vacio = pres.slide_layouts[6]

    for i, pagina in enumerate(doc, 1):
        ruta = TMP / f"{i:02d}.png"
        pagina.get_pixmap(dpi=DPI).save(ruta)
        lamina = pres.slides.add_slide(vacio)
        lamina.shapes.add_picture(str(ruta), 0, 0, width=ANCHO, height=ALTO)

    ahora = datetime.datetime.now()
    props = pres.core_properties
    props.title = "Prospectos Solares"
    props.author = AUTOR
    props.subject = ("Identificación y caracterización de terrenos aptos para "
                     "generación solar en Colombia")
    # Los cuatro que python-pptx no toca y que PowerPoint enseña en Informacion.
    # Sin fijarlos, el entregable llega al cliente firmado por el autor de la
    # libreria y fechado en 2013.
    props.last_modified_by = AUTOR
    props.comments = ""
    props.created = ahora
    props.modified = ahora
    props.revision = 1
    pres.save(SAL)

    _sanear(SAL, doc)
    print(f"{doc.page_count} diapositivas en {SAL}")
    print(f"{SAL.stat().st_size / 1e6:.1f} MB")


def _app_xml(n):
    """El bloque de propiedades extendidas, con las cifras de este mazo.

    python-pptx no recalcula docProps/app.xml: lo copia de su plantilla, que
    declara cero diapositivas, formato 4:3 y PowerPoint para Macintosh. Nada de
    eso es cierto aqui y es lo que se lee en el explorador y en SharePoint.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" xmlns:vt="http://schemas.openxmlformats.org/'
        'officeDocument/2006/docPropsVTypes">'
        "<TotalTime>0</TotalTime><Words>0</Words>"
        "<Application>python-pptx</Application>"
        "<PresentationFormat>Presentación en pantalla (16:9)</PresentationFormat>"
        f"<Paragraphs>0</Paragraphs><Slides>{n}</Slides><Notes>0</Notes>"
        "<HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        "<ScaleCrop>false</ScaleCrop>"
        '<HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant>'
        "<vt:lpstr>Tema</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4>"
        "</vt:variant></vt:vector></HeadingPairs>"
        '<TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>'
        "Prospectos Solares</vt:lpstr></vt:vector></TitlesOfParts>"
        f"<Manager></Manager><Company>{AUTOR}</Company>"
        "<LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>"
        "<HyperlinkBase></HyperlinkBase><HyperlinksChanged>false</HyperlinksChanged>"
        "<AppVersion>16.0000</AppVersion></Properties>"
    )


def _sanear(ruta, doc):
    """Corrige lo que python-pptx hereda de su plantilla y no recalcula.

    Tres cosas, ninguna de las cuales toca un pixel de las laminas: las
    propiedades extendidas, la miniatura (que era un rectangulo blanco en 4:3) y
    el atributo de tipo del tamano de diapositiva, que decia screen4x3 sobre unas
    medidas que son 16:9.
    """
    mini = doc[0].get_pixmap(dpi=40).tobytes("jpeg")
    dentro = zipfile.ZipFile(ruta)
    piezas = [(i, dentro.read(i.filename)) for i in dentro.infolist()]
    dentro.close()

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as fuera:
        for info, datos in piezas:
            if info.filename == "docProps/app.xml":
                datos = _app_xml(doc.page_count).encode("utf-8")
            elif info.filename == "docProps/thumbnail.jpeg":
                datos = mini
            elif info.filename == "ppt/presentation.xml":
                datos = datos.replace(b' type="screen4x3"', b"")
            fuera.writestr(info, datos)


if __name__ == "__main__":
    main()
