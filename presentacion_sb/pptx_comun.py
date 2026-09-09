"""Lo que los dos exportadores de PowerPoint comparten.

python-pptx no recalcula nada de docProps: lo copia de su plantilla, que declara
cero diapositivas, formato 4:3, PowerPoint para Macintosh y a otro autor, con
fecha de 2013. Y el tamano de diapositiva sale marcado como screen4x3 sobre unas
medidas que son 16:9, de modo que PowerPoint rotula la cinta como 4:3 y
cualquier reaplicacion de plantilla reescala la lamina entera.

Estaba resuelto en powerpoint.py y no en powerpoint_editable.py, que es
justamente el que el cliente abre para editar.
"""
import zipfile

AUTOR = "Métodos Mixtos Consultores"


def app_xml(n_laminas, titulo):
    """El bloque de propiedades extendidas, con las cifras de este mazo."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" xmlns:vt="http://schemas.openxmlformats.org/'
        'officeDocument/2006/docPropsVTypes">'
        "<TotalTime>0</TotalTime><Words>0</Words>"
        "<Application>python-pptx</Application>"
        "<PresentationFormat>Presentación en pantalla (16:9)</PresentationFormat>"
        f"<Paragraphs>0</Paragraphs><Slides>{n_laminas}</Slides><Notes>0</Notes>"
        "<HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        "<ScaleCrop>false</ScaleCrop>"
        '<HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant>'
        "<vt:lpstr>Tema</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4>"
        "</vt:variant></vt:vector></HeadingPairs>"
        '<TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>'
        f"{titulo}</vt:lpstr></vt:vector></TitlesOfParts>"
        f"<Manager></Manager><Company>{AUTOR}</Company>"
        "<LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>"
        "<HyperlinkBase></HyperlinkBase><HyperlinksChanged>false</HyperlinksChanged>"
        "<AppVersion>16.0000</AppVersion></Properties>"
    )


def sanear(ruta, pagina_portada, n_laminas, titulo):
    """Corrige lo que python-pptx hereda de su plantilla y no recalcula.

    `pagina_portada` es la pagina de pymupdf de la que sale la miniatura, y
    `n_laminas` el numero de laminas que se anadieron de verdad: con una
    exportacion parcial, tomarlos del documento entero declararia 33 laminas en
    un mazo de dos y sacaria la miniatura de una pagina que no esta.
    """
    mini = pagina_portada.get_pixmap(dpi=40).tobytes("jpeg")
    dentro = zipfile.ZipFile(ruta)
    piezas = [(i, dentro.read(i.filename)) for i in dentro.infolist()]
    dentro.close()

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as fuera:
        for info, datos in piezas:
            if info.filename == "docProps/app.xml":
                datos = app_xml(n_laminas, titulo).encode("utf-8")
            elif info.filename == "docProps/thumbnail.jpeg":
                datos = mini
            elif info.filename == "ppt/presentation.xml":
                datos = datos.replace(b' type="screen4x3"', b"")
            fuera.writestr(info, datos)


def fijar_propiedades(pres, titulo, ahora):
    """Los campos de docProps/core.xml que PowerPoint ensena en Informacion."""
    props = pres.core_properties
    props.title = titulo
    props.author = AUTOR
    props.last_modified_by = AUTOR
    props.comments = ""
    props.created = ahora
    props.modified = ahora
    props.revision = 1
