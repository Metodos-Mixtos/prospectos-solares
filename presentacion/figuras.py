"""Figuras vectoriales de la presentacion.

Se generan en PDF para que el texto quede nitido a cualquier tamano. La paleta es
la del logotipo, la misma de reporte/plantilla.py, para que la presentacion y el
entregable se lean como un mismo producto.

Todas las cifras salen de los ficheros reales del proyecto. Cuando una figura es un
esquema conceptual (fig_similitud) se dice en la propia lamina.

Sobre el tamano del lienzo: tam() recibe CENTIMETROS del hueco real que la figura
ocupa en la lamina, no pulgadas. Asi la escala de colocacion es 1 y el cuerpo que
se escribe aqui es el que se lee proyectado. Cada figura debe declarar la
proporcion de su hueco: si el hueco mide 14 x 4,1 cm y el lienzo 14 x 7, la
restriccion de altura muerde, la figura entra a 8 cm de ancho y el texto vuelve a
encogerse. Al cambiar el hueco en el .tex hay que cambiar el lienzo aqui.

Regla de revision: ninguna fuente por debajo de 7 pt, que es el cuerpo del pie de
la presentacion. Se comprueba sobre el PDF compuesto, no sobre la figura suelta.

Uso:  python figuras.py
Salida: ../outputs/presentacion/figuras/*.pdf
"""
import pathlib
import sys
import textwrap
from decimal import Decimal, ROUND_HALF_UP

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Ellipse, Rectangle
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
REP = RAIZ / "outputs" / "reporte"
SAL = RAIZ / "outputs" / "presentacion" / "figuras"
SAL.mkdir(parents=True, exist_ok=True)

MARCA = "#18919C"
ACENTO = "#157F88"
ACENTO2 = "#0F5E65"
ACENTOSUAVE = "#E2F0F1"
TINTA = "#1E2829"
TINTA2 = "#49585A"
TINTA3 = "#7F8E90"
LINEA = "#DFE2E2"
BIEN = "#3D7A5A"
AVISO = "#B0761E"
MAL = "#A8492F"
DEGRADADO = ["#DCEAEB", "#B5D5D8", "#7FBBC0", "#3E9BA3", "#0F5E65"]

# Escala de aptitud del lote, la misma del visor: azul cuando es idoneo, ambar
# cuando la gestion lo resuelve, rojo cuando no lo resuelve ninguna gestion. El
# verde queda reservado para estado y no para clasificacion, que era la confusion
# que Samuel senala: en la imagen satelital el verde se pierde contra el terreno.
AZUL = "#2C5F9E"

#: De las etiquetas que produce la caracterizacion a la escala de tres clases.
#: "Idoneo" y "Viable" solo se distinguian por el umbral 70 del indice, y el
#: indice ha dejado de ordenar la lista: se funden. "Pequeno" no es una clase de
#: aptitud sino el lote por debajo del minimo de caracterizacion, y queda fuera.
CLASE = {"Idóneo": "Idóneo", "Viable": "Idóneo",
         "Con reparos": "Viable con gestión",
         "No apto": "No viable", "Excluido": "No viable"}
ORDEN_CLASE = ["Idóneo", "Viable con gestión", "No viable"]
COLOR_CLASE = {"Idóneo": AZUL, "Viable con gestión": AVISO, "No viable": MAL}

#: Ancho util de la lamina, en centimetros. \textwidth = \paperwidth - 2 x 1 cm.
ANCHO_LAMINA = 14.0

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "text.color": TINTA,
    "axes.labelcolor": TINTA2,
    "xtick.color": TINTA2,
    "ytick.color": TINTA2,
    "axes.edgecolor": LINEA,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})


def tam(ancho_cm, alto_cm):
    """Lienzo en CENTIMETROS del hueco que la figura ocupa en la lamina.

    matplotlib mide el lienzo en pulgadas, y ahi estaba el defecto: los numeros de
    diseno se pasaban como pulgadas, de modo que un lienzo de «12,2 x 4,9» media en
    realidad 24,8 x 10,0 cm. La lamina lo colocaba a 14 cm de ancho, todo el texto
    se reducia al 56 % y una etiqueta de 10,5 pt aterrizaba en 5,9 pt, por debajo
    del cuerpo mas pequeno del propio diseno. Cinco figuras quedaban con
    interlineados de 2,9 a 4,9 pt sobre una pagina de 16 x 9 cm.

    Declarando el lienzo en centimetros del hueco real, la escala de colocacion es
    1 y el cuerpo que se escribe aqui es el cuerpo que se lee en la proyeccion. La
    regla para revisar una figura pasa a ser directa: ninguna fuente por debajo de
    7 pt, que es el limite del pie de la presentacion.

    Hay que darle a cada figura la proporcion de su hueco. Si el hueco es 14 x 4,1
    y el lienzo 14 x 7, la restriccion de altura muerde, la figura se coloca a 8 cm
    y volvemos al problema de partida.
    """
    return (ancho_cm / 2.54, alto_cm / 2.54)


def es(v, dec=0):
    """Numero en formato espanol: punto de miles y coma decimal, redondeo al alza."""
    q = Decimal(str(float(v))).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    s = f"{q:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def limpiar(ax, ejes=("top", "right")):
    for e in ejes:
        ax.spines[e].set_visible(False)
    ax.tick_params(length=0)


def guardar(fig, nombre):
    fig.savefig(SAL / nombre, bbox_inches="tight")
    plt.close(fig)
    print(nombre)


def _csv(nombre):
    return pd.read_csv(REP / nombre, encoding="utf-8-sig")


# =============================================================== 1. LA CADENA
def cadena():
    """Los seis pasos y el artefacto que viaja entre uno y el siguiente.

    El paso 6 estaba en la tabla de la lamina 4 y en el rotulo de seccion, pero no
    en este diagrama, de modo que el lector contaba cinco cajas y luego encontraba
    seis. Recibe la lista corta y entrega el expediente de compra.
    """
    lot = _csv("lotes_distribuida.csv")
    desc = _csv("lotes_distribuida_descartados.csv")
    n_caract = len(lot)
    n_catastro = n_caract + len(desc)          # 2.745
    n_grillas = 21447                          # panel_final.gpkg, filas
    n_cols = 43                                # panel_final.gpkg, columnas con geometria
    n_granjas = 112                            # panel_final.gpkg, n_granjas > 0
    n_sel = len(_csv("grillas_para_predios.csv"))  # 10, grillas del piloto

    pasos = [
        ("P A S O  1", "Dónde se ha\nconstruido", "se mide el perfil"),
        ("P A S O  2", "El mapa\nde grillas", "se divide el país"),
        ("P A S O  3", "El modelo", "se puntúa\nla similitud"),
        ("P A S O  4", "Caracterización\ny selección", "se aplican\nlos criterios"),
        ("P A S O  5", "Del cuadro\nal lote", "se mide el lote"),
        ("P A S O  6", "La información\npara comprar", "se arma\nel expediente"),
    ]
    # Cifras cortas: el rotulo del puente dispone de unos 2,4 cm de ancho, de modo
    # que una linea larga se monta sobre la del puente vecino.
    puentes = [
        ("Perfil de referencia", f"{es(n_granjas)} grillas"),
        ("Panel nacional", f"{es(n_grillas)} grillas · {n_cols} col."),
        ("Cien candidatas", "celda · polígono"),
        ("Grillas seleccionadas", f"{n_sel} en el piloto"),
        ("Lista corta y ficha", f"{es(n_caract)} lotes"),
    ]

    # Coordenadas en centimetros del propio lienzo: con seis cajas y cinco puentes
    # en 14 cm, cada elemento dispone de poco mas de un centimetro y hay que
    # medirlo, no estimarlo en fracciones.
    #
    # El nombre del artefacto va en una BANDA PROPIA debajo de las cajas, centrado
    # en su flecha. Puesto en el hueco entre cajas, como estaba, pedia unos 2,5 cm
    # de ancho por puente que el hueco no tiene, y los cinco rotulos se montaban
    # unos sobre otros y sobre los titulos de los pasos.
    # W tiene que ser exactamente 6 cajas mas 5 huecos. Con 13,6 la sexta caja
    # arrancaba en 11,91 y terminaba en 14,0, fuera del limite del eje: matplotlib
    # recorta los parches al eje y el PASO 6 salia cortado por la mitad en la
    # lamina, que es justo el paso que el guion habia anadido.
    # El alto baja de 4,40 a 3,95. El recuadro que sale del dibujo mide medio
    # centimetro mas que el lienzo, de modo que con 4,40 la figura llegaba a la
    # lamina con 4,91 cm de alto; como el hueco de la lamina es de 4,50, mandaba
    # la restriccion de altura, la figura entraba al 91 % y los rotulos de 7,4 pt
    # aterrizaban en 6,7. Con 3,95 manda el ancho y la escala sube al 96 %.
    W, A = 6 * 2.09 + 5 * 0.292, 3.95
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    # El ancho de caja se DERIVA del lienzo, no se escribe a mano. Con 2,09 y un
    # hueco de 0,292 las seis cajas sumaban 14,0 cm sobre un lienzo de 13,6: la
    # sexta se salia por la derecha y pdflatex la recortaba a media palabra, de
    # modo que la lamina que abre el guion ensenaba «La informaci / para compr».
    hueco = 0.28
    w = (W - 5 * hueco) / 6
    y0, alto = 1.42, 1.86
    xs = [i * (w + hueco) for i in range(6)]
    # Seis tonos de la misma rampa: DEGRADADO trae cinco.
    tonos = ["#DCEAEB", "#B9D8DB", "#8CC3C8", "#4FA5AC", "#1E7C84", "#0F5E65"]

    for i, ((rot, tit, verbo), x) in enumerate(zip(pasos, xs)):
        ax.add_patch(FancyBboxPatch((x, y0), w, alto,
                     boxstyle="round,pad=0.012,rounding_size=0.06",
                     fc=tonos[i], ec="none"))
        tc = TINTA if i < 3 else "white"
        cx = x + w / 2
        ax.text(cx, y0 + alto - 0.26, rot, ha="center", va="center",
                fontsize=7.4, color=tc, alpha=0.95)
        ax.text(cx, y0 + alto * 0.52, tit, ha="center", va="center",
                fontsize=7.8, fontweight="bold", color=tc, linespacing=1.2)
        ax.text(cx, y0 + 0.30, verbo, ha="center", va="center",
                fontsize=7.4, color=tc, linespacing=1.2)

    yf = y0 + alto / 2
    for i in range(5):
        a, b = xs[i] + w + 0.035, xs[i + 1] - 0.035
        ax.add_patch(FancyArrowPatch((a, yf), (b, yf), arrowstyle="-|>",
                     mutation_scale=8, color=ACENTO, lw=0.9, shrinkA=0, shrinkB=0))
        cx = (a + b) / 2
        nom, cif = puentes[i]
        # Guia fina desde la flecha hasta su rotulo, para que se sepa cual es cual.
        ax.plot([cx, cx], [y0 - 0.10, 1.14], color=LINEA, lw=0.6, zorder=0)
        ax.text(cx, 1.04, textwrap.fill(nom, 16), ha="center", va="top",
                fontsize=7.6, fontweight="bold", color=TINTA2, linespacing=1.25)
        ax.text(cx, 0.42, cif.replace("\n", " "), ha="center", va="top",
                fontsize=7.2, color=TINTA3, linespacing=1.25,
                wrap=False)

    guardar(fig, "fig_cadena.pdf")


# ============================================================ 2. EL CONTRASTE
UNIDAD = {
    "Privación socioeconómica": ("", 1),
    "Cobertura arbórea 2000": (" %", 1),
    "Área construida": (" %", 1),
    "Cultivos": (" %", 1),
    "Bosque": (" %", 1),
    "Distancia a subestación": (" km", 1),
    "Irradiación en plano inclinado": (" kWh/m²", 0),
    "Irradiación horizontal": (" kWh/m²", 0),
    "Pendiente media": ("°", 1),
    "Producción fotovoltaica": (" kWh/kWp", 0),
}


def contraste():
    """Las diez variables que mas separan las grillas con planta de las demas."""
    d = _csv("influencia_covariables.csv")
    d = d.reindex(d.d_cohen.abs().sort_values(ascending=False).index).head(10)
    d = d.reset_index(drop=True)

    # Lienzo ancho y bajo. Con 10,5 x 5,6 la figura pedia 1,88 de proporcion y en
    # la lamina la altura disponible la estrangulaba a 8,8 cm de ancho, con las
    # etiquetas a 7,0 pt. Con 12,5 x 4,9 cabe a ancho casi completo y el texto
    # crece con el lienzo.
    # El margen izquierdo pasa de 0,30 a 0,50 del lienzo. Los nombres de variable
    # se escriben en x=-0,03, es decir fuera del area de ejes, y con 0,30 medían
    # 6,7 cm sobre un margen de 4,1: el recuadro de la figura crecia hasta 17,3 cm
    # y la lamina, que tiene 14, la reducia al 81 %, con los rotulos de 10,5 pt
    # aterrizando en 6,8. Con 0,50 el nombre cabe dentro de su margen.
    fig, ax = plt.subplots(figsize=tam(13.8, 5.20))
    fig.subplots_adjust(left=0.40, right=0.955, top=0.90, bottom=0.14)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.7, len(d) - 0.3)
    ax.invert_yaxis()
    for e in ("top", "right", "left", "bottom"):
        ax.spines[e].set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])

    resaltada = "Irradiación en plano inclinado"
    for i, f in d.iterrows():
        sin, con = float(f.media_sin), float(f.media_con)
        if f.nombre == resaltada:
            ax.axhspan(i - 0.46, i + 0.46, color=ACENTOSUAVE, zorder=0, lw=0)
        lo, hi = min(sin, con), max(sin, con)
        x_sin, x_con = (0.22, 0.78) if sin <= con else (0.78, 0.22)
        ax.plot([0.22, 0.78], [i, i], color=LINEA, lw=2.2, zorder=1,
                solid_capstyle="round")
        ax.scatter([x_sin], [i], s=95, color=TINTA3, zorder=3)
        ax.scatter([x_con], [i], s=110, color=MARCA, zorder=4,
                   edgecolor="white", linewidth=0.8)
        # La unidad va una sola vez, junto al nombre. Repetirla en cada valor
        # ensanchaba el rotulo hasta invadir el nombre en las filas de irradiacion.
        uni, dec = UNIDAD[f.nombre]
        etiqueta = f.nombre if not uni.strip() else f"{f.nombre}  ({uni.strip()})"
        ax.text(-0.035, i, etiqueta, ha="right", va="center", fontsize=9.2,
                color=TINTA)
        # La cifra se separa de su punto: a 0,145 y 0,855, con el punto en 0,18 y
        # 0,82, el numero y el circulo se tocaban en las diez filas.
        for val, x in ((sin, x_sin), (con, x_con)):
            txt = es(val, dec)
            if x < 0.5:
                ax.text(0.165, i, txt, ha="right", va="center", fontsize=8.2,
                        color=TINTA2, clip_on=False)
            else:
                ax.text(0.835, i, txt, ha="left", va="center", fontsize=8.2,
                        color=TINTA2, clip_on=False)
        # La nota «el recurso aparece aqui» iba en x=1,20, es decir fuera del area
        # de ejes: el recuadro de la figura crecia 4 cm a la derecha y la lamina
        # tenia que reducirla al 79 %, con lo que las etiquetas caian a 4 pt. Lo
        # que decia lo dice ya el parrafo de la lamina, asi que se retira.

    ax.legend(handles=[
        Line2D([], [], marker="o", ls="none", ms=8.5, color=MARCA,
               markeredgecolor="white", label="grillas con planta en operación"),
        Line2D([], [], marker="o", ls="none", ms=8, color=TINTA3,
               label="grillas sin planta"),
    ], loc="lower right", bbox_to_anchor=(1.0, 1.01), frameon=False,
        fontsize=8.6, ncol=2, handletextpad=0.4, columnspacing=1.6)

    ax.text(0.5, len(d) - 0.45,
            "Cada fila se escala por separado: las unidades no son comparables.",
            ha="center", va="top", fontsize=8.2, color=TINTA3)
    guardar(fig, "fig_contraste.pdf")


# ============================================================= 3. LAS VARIABLES
GRUPOS = [
    (6, "Recurso solar",
     "irradiación global horizontal · irradiación directa · irradiación difusa · "
     "irradiación en plano inclinado · ángulo óptimo · producción fotovoltaica"),
    (4, "Clima y relieve",
     "temperatura media · pendiente media · elevación media · rugosidad del relieve"),
    (10, "Cobertura del suelo",
     "agua · bosque · área construida · pastizal · vegetación inundable · cultivos · "
     "suelo desnudo · nubosidad · nieve y hielo · cobertura arbórea de referencia"),
    (4, "Red y accesibilidad",
     "distancia a subestación · número de subestaciones · presencia de subestación · "
     "tiempo de viaje a centro poblado"),
    (2, "Sociales y demográficas",
     "densidad de población · índice de privación"),
    (1, "Económica",
     "producto interno bruto de la celda"),
    (5, "Jurídicas y ambientales",
     "parque nacional · área protegida · resguardo indígena · consejo comunitario · "
     "ecosistemas estratégicos"),
    (1, "Riesgo operativo",
     "densidad de cultivos de coca"),
]


def variables():
    """Las columnas del panel agrupadas por indole.

    El listado de variables de cada tarjeta se compuso durante meses a 8 pt sobre
    un lienzo que la lamina reduce a dos tercios: en proyeccion quedaba en unos
    4,8 pt de interlineado, por debajo del pie de la propia presentacion. La
    tarjeta se queda con la cifra y el titulo, que es lo que hay que leer de un
    vistazo, y el listado completo baja a la nota de fuente de la lamina, donde se
    compone con el cuerpo del documento y se lee.
    """
    # El alto del lienzo reserva una banda para la nota de abajo. Con 2,50 la nota
    # aterrizaba dentro de la segunda fila de tarjetas y se leian los dos textos
    # superpuestos.
    fig, ax = plt.subplots(figsize=tam(13.6, 3.10))
    ax.set_xlim(0, 4); ax.set_ylim(0, 2.70); ax.axis("off")
    ax.invert_yaxis()

    mx, my = 0.045, 0.075
    for k, (n, titulo, _lista) in enumerate(GRUPOS):
        cx, cy = k % 4, k // 4
        x, y = cx + mx, cy + my + 0.13
        w, h = 1 - 2 * mx, 1 - 2 * my
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.005,rounding_size=0.05",
                     fc="#F9FBFB", ec=LINEA, lw=0.6))
        # Cuerpos ajustados al ancho real de la tarjeta: 3,5 cm de celda menos los
        # margenes y la cifra dejan unos 2,2 cm para el titulo, y a 11,5 pt
        # «Cobertura del» ya medía 2,4 cm y se salia de la caja.
        ax.text(x + 0.055, y + 0.285, str(n), ha="left", va="center",
                fontsize=17, fontweight="bold", color=ACENTO2)
        # La cifra de dos digitos ocupa el doble: el titulo arranca despues de ella.
        # Con la cifra a 20 pt y el titulo a 8,5 el hueco que quedaba era de 2,09 cm
        # y «Cobertura del» medía 2,43: los cuatro titulos largos se salian de su
        # tarjeta por la derecha. La cifra cede ancho y el titulo parte a 11.
        # break_long_words=False: con el corte por defecto, «demográficas» y
        # «accesibilidad» se partian a mitad de palabra («demográfica / s»).
        ax.text(x + 0.100 + 0.058 * len(str(n)), y + 0.285,
                textwrap.fill(titulo, 12, break_long_words=False), ha="left",
                va="center", fontsize=7.4, fontweight="bold", color=TINTA,
                linespacing=1.25)

    # va="top" y no "bottom": con el eje invertido, «bottom» dibuja el rotulo hacia
    # arriba, es decir dentro de la segunda fila de tarjetas.
    ax.text(2.0, 2.22,
            "43 columnas por grilla contando la geometría. El modelo de similitud usa 33.",
            ha="center", va="top", fontsize=8.0, color=TINTA3)
    fig.tight_layout()
    guardar(fig, "fig_variables.pdf")


# ================================================================ 4. LO URBANO
def urbano():
    """El suelo urbano en las dos escalas: la grilla y el lote."""
    g = _csv("grillas_candidatas.csv")
    col = "Área construida (%)"
    v = g[col].astype(float)

    desc = _csv("lotes_distribuida_descartados.csv")
    exc = desc[desc.clasificacion == "Excluido"].motivo.astype(str)
    urb = exc.str.contains("capa urbana", case=False)
    hab = (~urb) & exc.str.contains("habitacional", case=False)
    minero = (~urb) & (~hab) & exc.str.contains("minero", case=False)
    reparto = [(int(urb.sum()), "tocan la capa urbana del catastro", MAL),
               (int(hab.sum()), "destino habitacional", AVISO),
               (int(minero.sum()), "título minero vigente", TINTA3)]
    n_exc = len(exc)
    if sum(n for n, _, _ in reparto) != n_exc:
        raise SystemExit("El reparto de exclusiones no suma el total de excluidos.")
    n_total = len(_csv("lotes_distribuida.csv")) + len(desc)

    fig = plt.figure(figsize=tam(13.6, 3.50))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], wspace=0.22,
                          left=0.05, right=0.97, top=0.86, bottom=0.12)

    # --- izquierda: la grilla
    a = fig.add_subplot(gs[0, 0])
    a.set_title("E S C A L A   D E   G R I L L A", fontsize=9, color=TINTA3,
                loc="left", pad=14)
    a.hist(v, bins=np.arange(0, 8.5, 0.5), color=MARCA, alpha=0.85, lw=0)
    a.axvline(v.mean(), color=ACENTO2, lw=1.1, ls=(0, (3, 2.5)))
    a.text(v.mean() + 0.18, a.get_ylim()[1] * 0.34, f"media {es(v.mean(), 2)} %",
           fontsize=9, color=ACENTO2, va="top")
    a.set_xlabel("Área construida de la grilla (%)", fontsize=9.5, labelpad=7)
    a.set_xticks([0, 2, 4, 6, 8])
    a.set_xticklabels(["0", "2", "4", "6", "8"], fontsize=9)
    a.set_yticks([])
    for e in ("top", "right", "left"):
        a.spines[e].set_visible(False)
    a.tick_params(length=0)
    # La nota estaba a media altura del eje y le caia encima a la barra alta y a
    # la linea de la media. Arriba del todo, contra el borde derecho, no pisa nada:
    # las barras a la derecha de 1,5 % no llegan al quinto de la altura.
    # Y a 38 caracteres por linea el bloque llegaba hasta el rotulo de la media,
    # que esta a la misma altura. A 30 su borde izquierdo queda a la derecha de la
    # linea de la media.
    a.text(0.98, 0.99, textwrap.fill(
        "Ninguna de las cien llega al 10 %. Lo rural sale de la similitud, "
        "no de un recorte previo de capa urbana.", 30),
        transform=a.transAxes, ha="right", va="top", fontsize=9.0, color=TINTA2,
        linespacing=1.40)

    # --- derecha: el lote
    b = fig.add_subplot(gs[0, 1])
    b.set_title("E S C A L A   D E   L O T E", fontsize=9, color=TINTA3,
                loc="left", pad=14)
    b.set_xlim(0, 1); b.set_ylim(0, 1); b.axis("off")

    # El rotulo va por encima de las etiquetas de los segmentos estrechos, que
    # salen fuera de la barra: a la misma altura, «773 lotes excluidos de 2.745»
    # llegaba hasta el 68 y el 102 y se montaba sobre ellos.
    x, ybar, hbar = 0.0, 0.47, 0.19
    b.text(0, ybar + hbar + 0.26, f"{es(n_exc)} lotes excluidos de {es(n_total)}",
           fontsize=9.5, color=TINTA, va="bottom")
    fig.canvas.draw()
    ancho_pt = b.get_window_extent().width * 72 / fig.dpi
    for n, _, color in reparto:
        w = n / n_exc
        b.add_patch(Rectangle((x, ybar), w, hbar, fc=color, ec="white", lw=1.0))
        etiqueta = es(n)
        if w * ancho_pt > len(etiqueta) * 8.5:
            b.text(x + w / 2, ybar + hbar / 2, etiqueta, ha="center", va="center",
                   fontsize=11, fontweight="bold", color="white")
        else:
            b.plot([x + w / 2, x + w / 2], [ybar + hbar, ybar + hbar + 0.10],
                   color=color, lw=0.9)
            b.text(x + w / 2, ybar + hbar + 0.12, etiqueta, ha="center", va="bottom",
                   fontsize=11, fontweight="bold", color=color)
        x += w

    yl = ybar - 0.16
    for n, texto, color in reparto:
        b.add_patch(Rectangle((0.0, yl - 0.028), 0.030, 0.056, fc=color, ec="none"))
        b.text(0.045, yl, f"{es(n)}  {texto}", ha="left", va="center",
               fontsize=9, color=TINTA2)
        yl -= 0.135

    guardar(fig, "fig_urbano.pdf")


# =============================================================== 5. SIMILITUD
def similitud():
    """Esquema de los dos componentes del puntaje de similitud."""
    rng = np.random.default_rng(11)
    nube = rng.multivariate_normal([0.0, 0.0], [[1.00, 0.62], [0.62, 0.85]], 40)
    cand = np.array([2.55, -1.55])
    centro = nube.mean(axis=0)
    cov = np.cov(nube.T)
    val, vec = np.linalg.eigh(cov)
    ang = np.degrees(np.arctan2(vec[1, -1], vec[0, -1]))

    fig = plt.figure(figsize=tam(13.6, 3.85))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.85], wspace=0.20,
                          left=0.04, right=0.97, top=0.84, bottom=0.20)

    def marco(ax, titulo):
        ax.set_title(titulo, fontsize=8, color=TINTA3, loc="left", pad=8)
        # Escala igual en los dos ejes: si no, la vecindad se ve deformada y los
        # cinco vecinos mas proximos no parecen los mas proximos.
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(-3.7, 3.7); ax.set_ylim(-3.4, 3.4)
        ax.set_xticks([]); ax.set_yticks([])
        for e in ("top", "right"):
            ax.spines[e].set_visible(False)
        for e in ("left", "bottom"):
            ax.spines[e].set_color(LINEA)

    a = fig.add_subplot(gs[0, 0])
    marco(a, "C O M P O N E N T E   A")
    for k, al in ((2.6, 0.06), (1.8, 0.10), (1.0, 0.16)):
        a.add_patch(Ellipse(centro, 2 * k * np.sqrt(val[-1]), 2 * k * np.sqrt(val[0]),
                            angle=ang, fc=ACENTO, alpha=al, ec="none", zorder=1))
    a.scatter(nube[:, 0], nube[:, 1], s=15, color=MARCA, alpha=0.55, zorder=2, lw=0)
    a.scatter(*centro, marker="x", s=70, color=ACENTO2, lw=1.6, zorder=4)
    a.add_patch(FancyArrowPatch(tuple(cand), tuple(centro), arrowstyle="-|>",
                mutation_scale=10, color=TINTA2, lw=1.0, ls=(0, (3, 2.2)),
                shrinkA=7, shrinkB=7, zorder=3))
    a.scatter(*cand, s=150, facecolor="none", edgecolor=MAL, lw=1.8, zorder=5)
    a.text(0.0, -0.07, textwrap.fill(
        "similitud al perfil: distancia al promedio, corregida por cómo se "
        "correlacionan las variables", 32),
        transform=a.transAxes, ha="left", va="top", fontsize=7.2, color=TINTA2,
        linespacing=1.45)

    b = fig.add_subplot(gs[0, 1])
    marco(b, "C O M P O N E N T E   B")
    dist = np.linalg.norm(nube - cand, axis=1)
    cinco = np.argsort(dist)[:5]
    for j in cinco:
        b.plot([cand[0], nube[j, 0]], [cand[1], nube[j, 1]], color=ACENTO,
               lw=0.8, zorder=2)
    b.scatter(nube[:, 0], nube[:, 1], s=15, color=MARCA, alpha=0.55, zorder=3, lw=0)
    b.scatter(nube[cinco, 0], nube[cinco, 1], s=34, color=MARCA, zorder=4,
              edgecolor=ACENTO2, lw=1.0)
    b.scatter(*cand, s=150, facecolor="none", edgecolor=MAL, lw=1.8, zorder=5)
    b.text(0.0, -0.07, textwrap.fill(
        "cercanía a las más parecidas: distancia media a las cinco grillas con "
        "planta más próximas", 32),
        transform=b.transAxes, ha="left", va="top", fontsize=7.2, color=TINTA2,
        linespacing=1.45)

    c = fig.add_subplot(gs[0, 2])
    c.set_xlim(0, 1); c.set_ylim(0, 1); c.axis("off")
    # El peso va escrito sobre la barra. Una barra sin cifra al lado de una
    # advertencia de no calibracion deja al lector suponiendo lo peor.
    for y, nombre, frac, color in ((0.80, "Componente A", 0.60, ACENTO2),
                                   (0.55, "Componente B", 0.40, MARCA)):
        c.text(0, y + 0.085, nombre, fontsize=9.5, color=TINTA, va="bottom")
        c.text(1.0, y + 0.085, f"{es(100 * frac)} %", fontsize=9.5, color=color,
               va="bottom", ha="right", fontweight="bold")
        c.add_patch(Rectangle((0, y), 1.0, 0.055, fc=LINEA, ec="none"))
        c.add_patch(Rectangle((0, y), frac, 0.055, fc=color, ec="none"))
    c.add_patch(FancyBboxPatch((0, 0.16), 1.0, 0.20,
                boxstyle="round,pad=0.01,rounding_size=0.05",
                fc=ACENTOSUAVE, ec="none"))
    c.text(0.5, 0.26, "Puntaje de similitud", ha="center", va="center",
           fontsize=10.5, fontweight="bold", color=ACENTO2)
    c.text(0, 0.09, textwrap.fill(
        "La ponderación entre los dos componentes está puesta a criterio, no "
        "calibrada.", 34),
        ha="left", va="top", fontsize=7.2, color=TINTA3, linespacing=1.45)

    guardar(fig, "fig_similitud.pdf")


# ============================================================ 6. CRIBA DE LOTES
def criba_lotes():
    """Del inventario catastral a los lotes caracterizados."""
    lot = _csv("lotes_distribuida.csv")
    desc = _csv("lotes_distribuida_descartados.csv")
    n_car = len(lot)
    n_peq = int((desc.clasificacion == "Pequeño").sum())
    n_exc = int((desc.clasificacion == "Excluido").sum())
    total = n_car + n_peq + n_exc

    exc = desc[desc.clasificacion == "Excluido"].motivo.astype(str)
    urb = exc.str.contains("capa urbana", case=False)
    hab = (~urb) & exc.str.contains("habitacional", case=False)
    mino = (~urb) & (~hab) & exc.str.contains("minero", case=False)

    filas = [
        ("Pequeños", n_peq, TINTA3, "menos de 2 ha; quedan medidos, no borrados"),
        ("Excluidos", n_exc, MAL,
         f"{es(int(urb.sum()))} capa urbana · {es(int(hab.sum()))} destino "
         f"habitacional · {es(int(mino.sum()))} título minero"),
        ("Caracterizados", n_car, ACENTO2, "medidos, calificados y con ficha"),
    ]

    # X0 es la columna de rotulos de la izquierda. Con 0,155 medía 2,05 cm y
    # «Caracterizados» a 10,5 pt pide 2,6: el rotulo se metia dentro de la barra.
    fig, ax = plt.subplots(figsize=tam(12.8, 3.50))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    X0, W = 0.225, 0.555
    ytop, htop = 0.860, 0.070
    ax.text(X0, ytop + htop + 0.040, f"{es(total)} lotes del catastro",
            fontsize=10.5, fontweight="bold", color=TINTA, va="bottom")

    # La barra madre ya viene partida en las tres tajadas: el reparto se ve antes
    # de bajar. El reparto se lee luego en dos tramos, un abanico que estrecha cada
    # tajada hasta su ancho final y una columna vertical que baja hasta su barra.
    # Asi las bandas quedan encajadas una dentro de otra y no se cruzan en diagonal.
    acum_t = 0
    for _, n, color, _ in filas:
        ax.add_patch(Rectangle((X0 + W * acum_t / total, ytop), W * n / total, htop,
                     fc=color, alpha=0.28, ec="white", lw=1.0))
        acum_t += n

    y_abanico = ytop - 0.150
    acum = 0
    for k, (etiqueta, n, color, glosa) in enumerate(filas):
        y = 0.535 - k * 0.180
        h = 0.098
        w = W * n / total
        xa = X0 + W * acum / total
        xb = X0 + W * (acum + n) / total
        acum += n
        ax.add_patch(Polygon([(xa, ytop), (xb, ytop),
                              (X0 + w, y_abanico), (X0, y_abanico)],
                     closed=True, fc=color, alpha=0.16, ec="none", zorder=0))
        ax.add_patch(Rectangle((X0, y + h), w, y_abanico - y - h,
                     fc=color, alpha=0.16, ec="none", zorder=0))
        ax.add_patch(Rectangle((X0, y), w, h, fc=color, ec="none", zorder=3))
        ax.text(X0 - 0.014, y + h / 2, etiqueta, ha="right", va="center",
                fontsize=9.0, color=color, fontweight="bold")
        ax.text(X0 + w / 2, y + h / 2, es(n), ha="center", va="center",
                fontsize=10, fontweight="bold", color="white", zorder=4)
        ax.text(X0 + w + 0.014, y + h / 2, glosa, ha="left", va="center",
                fontsize=7.6, color=TINTA2)

    ax.text(X0, 0.015,
            "El registro de lo que quedó fuera conserva cada lote con su motivo escrito.",
            fontsize=7.6, color=TINTA3, va="bottom")
    fig.tight_layout()
    guardar(fig, "fig_criba_lotes.pdf")


# ================================================================ 7. PERFILES
def perfiles():
    """Los mismos lotes bajo los dos perfiles de proyecto."""
    u = _csv("lotes_utility.csv")
    d = _csv("lotes_distribuida.csv")
    total = len(d)
    if len(u) != total:
        raise SystemExit("Los dos perfiles no tienen el mismo numero de lotes.")

    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg
    pu, pd_ = rg.PERFILES["utility"], rg.PERFILES["distribuida"]
    an_u = float(u["ancho_minimo_m"].iloc[0])
    an_d = float(d["ancho_minimo_m"].iloc[0])

    # Las cuentas salen del propio archivo de salida, agregadas a la escala de
    # tres clases. Ninguna cifra de esta figura esta escrita a mano.
    cu = u.clasificacion.map(CLASE).value_counts()
    cd = d.clasificacion.map(CLASE).value_counts()
    orden = [c for c in ORDEN_CLASE if cu.get(c, 0) or cd.get(c, 0)]

    dominante = int(u["reparos"].astype(str).str.contains("capacidad libre").sum())

    # El rotulo de cada perfil va ENCIMA de su barra, no a la izquierda. Con el
    # rotulo a la izquierda hacia falta una cuarta parte del lienzo solo para
    # texto, y la linea larga («proyecto de 50 MW · 150 ha · 387 m de ancho») se
    # salia del lienzo y arrastraba el recuadro de la figura a 22 cm de ancho, con
    # lo que la lamina la reducia al 57 % y todo bajaba de 5 pt.
    fig, ax = plt.subplots(figsize=tam(12.5, 3.05))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # Bandas verticales explicitas, de arriba abajo. Cada elemento tiene su franja
    # y no se calcula por desplazamiento respecto del anterior, que es como se
    # solapaban el rotulo de la segunda barra y el recuadro de la nota.
    W, H = 1.0, 0.140
    barras = [
        (0.755, 0.955, "Escala utility",
         f"proyecto de {es(pu['mw_proyecto'])} MW · {es(pu['ha_proyecto'])} ha · "
         f"{es(an_u)} m de ancho", cu),
        (0.275, 0.455, "Generación distribuida",
         f"proyecto de {es(pd_['mw_proyecto'])} MW · {es(pd_['ha_proyecto'])} ha · "
         f"{es(an_d)} m de ancho", cd),
    ]
    for y, y_rot, titulo, sub, cuentas in barras:
        ax.text(0, y_rot, titulo, ha="left", va="center",
                fontsize=10.5, fontweight="bold", color=TINTA)
        ax.text(1.0, y_rot, sub, ha="right", va="center",
                fontsize=8.5, color=TINTA3)
        x = 0.0
        for cl in orden:
            n = int(cuentas.get(cl, 0))
            if not n:
                continue
            w = W * n / total
            ax.add_patch(Rectangle((x, y), w, H, fc=COLOR_CLASE[cl], ec="white",
                                   lw=1.0))
            etiqueta = f"{es(n)} {cl.lower()}" if w > 0.30 else es(n)
            ax.text(x + w / 2, y + H / 2, etiqueta, ha="center", va="center",
                    fontsize=10 if w > 0.22 else 8.5, fontweight="bold",
                    color="white")
            x += w

    ax.add_patch(FancyBboxPatch((0, 0.615), W, 0.115,
                 boxstyle="round,pad=0.006,rounding_size=0.05",
                 fc=ACENTOSUAVE, ec="none"))
    ax.text(0.5, 0.6725,
            f"Los mismos {es(total)} lotes. Lo que cambia es la capacidad que se le "
            "exige a la barra.",
            ha="center", va="center", fontsize=9.5, color=TINTA2)

    x = 0.0
    for cl in orden:
        ax.add_patch(Rectangle((x, 0.152), 0.018, 0.046, fc=COLOR_CLASE[cl],
                               ec="none"))
        ax.text(x + 0.028, 0.175, cl, ha="left", va="center", fontsize=8.5,
                color=TINTA2)
        x += 0.028 + 0.011 * len(cl) + 0.035

    # Nota corta a proposito: a 8,5 pt la version larga medía casi 18 cm y sacaba
    # el recuadro de la figura muy por fuera del lienzo, con lo que la lamina la
    # reducia y todo el texto bajaba de 5 pt.
    ax.text(0, 0.038,
            f"A escala utility el reparo es siempre el mismo: falta capacidad "
            f"libre en el punto de conexión ({es(dominante)} de {es(total)}).",
            fontsize=8.0, color=TINTA3, va="center", ha="left")
    guardar(fig, "fig_perfiles.pdf")


# ================================================================== 8. PESOS
def pesos():
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg

    it = [(v["etiqueta"], v["d_cohen"]) for v in rg.CRITERIOS.values()]
    it.sort(key=lambda x: x[1])
    suma = sum(d for _, d in it)

    # Siete filas en 2,80 cm daban 11 pt de paso por fila para un rotulo de 8,5:
    # los nombres de criterio se tocaban unos con otros y el porcentaje blanco
    # caia sobre el borde de su propia barra. Con 3,60 cm el paso sube a 14 pt.
    fig, ax = plt.subplots(figsize=tam(11.7, 3.60))
    y = np.arange(len(it))
    vals = [d for _, d in it]
    ax.barh(y, vals, height=0.52, color=[ACENTO2 if d == max(vals) else MARCA for d in vals])
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _ in it], fontsize=8.5)
    for i, (n, d) in enumerate(it):
        ax.text(d + 0.016, i, es(d, 2), va="center", ha="left",
                fontsize=8, color=TINTA2)
        ax.text(d - 0.018, i, f"{es(100 * d / suma)} %", va="center", ha="right",
                fontsize=8, color="white", fontweight="bold")
    ax.set_xlim(0, 0.72)
    # Rotulo corto: el largo medía 15,5 cm en un lienzo de 12 y se salia por los
    # dos lados. La poblacion exacta que se contrasta queda en la nota de la lamina.
    ax.set_xlabel("Capacidad para separar las grillas con planta del resto",
                  fontsize=8, labelpad=8)
    ax.set_xticks([])
    limpiar(ax, ("top", "right", "bottom"))
    ax.invert_yaxis()
    fig.tight_layout()
    guardar(fig, "fig_pesos.pdf")


# ================================================================== 9. ESCALA
def escala():
    """La escala de un criterio: limite, objetivo y tope, y como se interpola.

    Sustituye a la captura de la matriz de criterios del reporte. Aquella es una
    tabla de siete filas por seis columnas capturada a 2.388 px de ancho: puesta
    en la lamina su cuerpo aterrizaba en 2 pt y no se leia ninguna cifra. Lo que
    la lamina afirma es como se puntua un criterio, y eso se dibuja.
    """
    fig, ax = plt.subplots(figsize=tam(13.2, 3.4))
    # Sin tight_layout: la nota de abajo se salia del rango del eje y tight_layout
    # respondia estrechando el eje a la mitad, con lo que «Objetivo» y «Tope» se
    # montaban. Los margenes se fijan y el texto se recorta a lo que cabe.
    fig.subplots_adjust(left=0.005, right=0.995, top=0.98, bottom=0.02)
    ax.set_xlim(-2, 102)
    # El rotulo de cada punto lleva dos lineas y antes se dibujaba de abajo hacia
    # arriba desde y=1,10, con lo que «percentil 90 / de lo construido» acababa
    # dentro de la palabra «Límite». Ahora las dos bandas son explicitas y el
    # texto crece hacia abajo desde su techo.
    ax.set_ylim(-1.5, 2.9)
    ax.axis("off")

    grad = np.linspace(0, 1, 512).reshape(1, -1)
    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("m", ["#F2F4F5", "#BFE0E2", MARCA, ACENTO2])
    ax.imshow(grad, extent=[0, 100, 0.15, 0.75], aspect="auto", cmap=cm, zorder=1)
    ax.add_patch(plt.Rectangle((0, 0.15), 100, 0.60, fill=False, ec=LINEA, lw=0.8, zorder=3))

    for x, ali, arriba, abajo, col in [
        (0, "left", "Límite", "percentil 90 de lo construido", TINTA2),
        (70, "center", "Objetivo", "mediana", TINTA2),
        (100, "right", "Tope", "percentil 10", ACENTO2),
    ]:
        ax.plot([x, x], [0.75, 1.15], color=col, lw=1.1, zorder=4)
        ax.text(x, 2.85, arriba, ha=ali, va="top", fontsize=12,
                fontweight="bold", color=col)
        ax.text(x, 2.10, abajo, ha=ali, va="top", fontsize=9, color=TINTA3,
                linespacing=1.35, multialignment=ali)
        ax.text(x, 0.02, str(x), ha=ali, va="top", fontsize=11,
                fontweight="bold", color=col)

    # ejemplo real
    ax.annotate("", xy=(49, 0.15), xytext=(49, -0.62),
                arrowprops=dict(arrowstyle="-|>", color=MAL, lw=1.4))
    ax.text(49, -0.72, "Subestación a 15 km  →  49 puntos",
            ha="center", va="top", fontsize=10.5, color=MAL, fontweight="bold")
    ax.text(0, -1.16, "No es un cumple o no cumple: se interpola.",
            ha="left", va="top", fontsize=9.0, color=TINTA3)
    guardar(fig, "fig_escala.pdf")


# ============================================================== 9 bis. TAMANO
def tamano():
    """Los lotes caracterizados sobre el eje de superficie, con los dos preajustes.

    Sustituye a la captura del panel de filtros. Aquella ensenaba etiquetas que ya
    no existen y un reparto por clase que va a cambiar; esto sale de la salida
    vigente y solo afirma lo que la lamina quiere decir: que la superficie acota la
    lista y no borra ningun lote.
    """
    d = _csv("lotes_distribuida.csv")
    an_u = float(_csv("lotes_utility.csv")["ancho_minimo_m"].iloc[0])
    an_d = float(d["ancho_minimo_m"].iloc[0])
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg
    ha_u = float(rg.PERFILES["utility"]["ha_proyecto"])
    ha_d = float(rg.PERFILES["distribuida"]["ha_proyecto"])
    n_u = int(((d.area_ha >= ha_u) & (d.ancho_util_m >= an_u)).sum())
    n_d = int(((d.area_ha >= ha_d) & (d.ancho_util_m >= an_d)).sum())

    fig, ax = plt.subplots(figsize=tam(13.0, 3.6))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.72, bottom=0.30)
    rng = np.random.default_rng(11)
    ax.scatter(d.area_ha, rng.uniform(-0.34, 0.34, len(d)), s=20, color=MARCA,
               alpha=0.42, edgecolor="none", zorder=3)
    ax.set_xscale("log")
    ax.set_xlim(1.6, 1000)
    ax.set_ylim(-0.75, 0.75)
    ax.set_yticks([])
    marcas = [2, 5, 10, 25, 50, 150, 400, 800]
    ax.set_xticks(marcas)
    ax.set_xticklabels([es(v) for v in marcas], fontsize=9.0)
    ax.set_xlabel("Superficie del lote, en hectáreas. Escala logarítmica.",
                  fontsize=9.0, labelpad=6)
    ax.tick_params(axis="x", length=3, pad=3)
    ax.minorticks_off()
    limpiar(ax, ("top", "right", "left"))

    # Los rotulos van en coordenadas de ejes para el alto y de datos para el
    # ancho: asi no empujan el recuadro de la figura al recortar por contenido,
    # que es lo que hacia salir el lienzo a 20 cm y aplastaba el eje.
    mixto = ax.get_xaxis_transform()
    for x, alto, tit, sub in [
        (ha_d, 1.30, "Generación distribuida",
         f"desde {es(ha_d)} ha y {es(an_d)} m de ancho"),
        (ha_u, 1.30, "Escala utility",
         f"desde {es(ha_u)} ha y {es(an_u)} m de ancho"),
    ]:
        ax.axvline(x, color=ACENTO2, lw=1.1, ls=(0, (4, 3)), zorder=4)
        ax.text(x * 1.10, alto, tit, ha="left", va="bottom", fontsize=10.0,
                fontweight="bold", color=ACENTO2, transform=mixto)
        ax.text(x * 1.10, alto - 0.22, sub, ha="left", va="bottom", fontsize=8.6,
                color=TINTA3, transform=mixto)

    # Nota deliberadamente corta: a 8,6 pt cada linea larga saca el recuadro de la
    # figura por fuera del lienzo declarado, y la lamina la reduce hasta bajar todo
    # el texto por debajo de los 7 pt del pie.
    ax.text(0.5, -0.80,
            f"Un punto por lote. De los {es(len(d))}, {es(n_u)} alcanzan el "
            "preajuste de escala utility.",
            ha="center", va="top", fontsize=8.6, color=TINTA2,
            transform=ax.transAxes)
    guardar(fig, "fig_tamano.pdf")


# ============================================================= 10. LAS CIEN
def distribucion():
    d = _csv("grillas_candidatas.csv")
    col_i, col_c = "Índice de aptitud", "Clasificación"
    orden = ["Prioritaria", "Elegible", "Condicionada", "Excluida"]
    color = {"Prioritaria": ACENTO2, "Elegible": AVISO, "Condicionada": MAL,
             "Excluida": TINTA3}

    # Cuatro filas separadas 1,0 sobre un rango de 4,9 en 3,4 cm dejaban 13 pt de
    # paso para un rotulo de 11 pt, con lo que los cuatro nombres de clase y sus
    # cuatro cuentas se tocaban. El rango sube a 5,9 y el cuerpo baja a 9,5.
    # Y la nota del corte 70 estaba dentro del area de puntos: sube por encima.
    fig, ax = plt.subplots(figsize=tam(12.6, 3.90))
    rng = np.random.default_rng(7)
    for k, cl in enumerate(orden):
        sub = d[d[col_c] == cl]
        if sub.empty:
            continue
        # Las Excluidas no llevan punto. En el archivo su indice vale cero porque
        # es el valor que ocupa la casilla, no una calificacion: dibujarlas sobre
        # el cero del eje afirmaria que sacaron cero, y lo que ocurre es que no se
        # califican. Se enuncian con palabras en su propia fila.
        if cl == "Excluida":
            ax.text(2, 1.25 * k, "no reciben calificación", ha="left",
                    va="center", fontsize=9.0, color=TINTA3, style="italic")
        else:
            y = 1.25 * k + rng.uniform(-0.20, 0.20, len(sub))
            ax.scatter(sub[col_i], y, s=42, color=color[cl], alpha=0.80,
                       edgecolor="white", linewidth=0.6, zorder=3)
        ax.text(-6, 1.25 * k, f"{cl}", ha="right", va="center", fontsize=9.5,
                color=color[cl], fontweight="bold")
        ax.text(104, 1.25 * k, f"{len(sub)}", ha="left", va="center",
                fontsize=9.5, color=TINTA2)

    ax.axvline(70, color=ACENTO, lw=1.1, ls=(0, (4, 3)), zorder=2)
    ax.text(70, -0.92, "índice 70: el corte de la lista corta",
            ha="center", va="center", fontsize=9.0, color=ACENTO)
    ax.set_xlim(-40, 114)
    ax.set_ylim(-1.25, 4.35)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 70, 100])
    ax.tick_params(axis="x", labelsize=9)
    ax.set_xlabel("Índice de aptitud", fontsize=9.5, labelpad=7)
    limpiar(ax, ("top", "right", "left"))
    ax.invert_yaxis()
    fig.tight_layout()
    guardar(fig, "fig_distribucion.pdf")


# ============================================================= 11. CAPACIDAD
NOMBRE_CORTO = {"San Marcos -Cesar 110 kV": "San Marcos - Cesar 110 kV"}


def capacidad():
    """Las 31 subestaciones a las que se conectan las cien candidatas.

    Antes la lamina dibujaba siete barras escogidas a mano, y con esa seleccion
    Planeta Rica parecia la unica con holgura. Con las 31 se ve que son cinco las
    que superan el limite de 50 MW, entre ellas Lanceros, la del piloto. Dibujar
    el archivo entero es lo que evita que la figura sostenga una frase falsa.
    """
    c = _csv("capacidad_barras.csv")
    c = c.dropna(subset=["capacidad_disponible_mw"])
    c = c.sort_values("capacidad_disponible_mw", ascending=False)
    it = [(NOMBRE_CORTO.get(n, n), float(v), int(k))
          for n, v, k in zip(c.sub_nombre_subestacion,
                             c.capacidad_disponible_mw, c.candidatas)]

    # Dos columnas. Treinta barras en una sola columna obligan a una figura tan
    # alta que en la lamina cabe a 8 cm de ancho, y entonces cada fila queda en
    # unos 4 pt: ilegible, que es justo el defecto que esta figura corrige. En dos
    # columnas la figura es ancha y baja, entra a ancho completo y la fila dobla.
    mitad = (len(it) + 1) // 2
    grupos = [it[:mitad], it[mitad:]]
    piso = 0.02

    fig, axes = plt.subplots(1, 2, figsize=tam(13.6, 4.55))
    # wspace sube de 0,70 a 1,15: las cifras de la columna izquierda se escriben
    # fuera de su barra y con 0,70 «218,6» y «190,6» caian sobre los nombres de
    # subestacion de la columna derecha.
    fig.subplots_adjust(left=0.215, right=0.995, top=0.86, bottom=0.03, wspace=1.15)

    for ax, grupo in zip(axes, grupos):
        y = np.arange(len(grupo))
        vals = [v for _, v, _ in grupo]
        cols = [BIEN if v >= 50 else (AVISO if v >= 10 else MAL) for v in vals]
        # Escala logaritmica: con 218 MW arriba y 0,00 abajo, en lineal las
        # ultimas barras serian invisibles y no se podria leer cual tiene cupo.
        ax.barh(y, [max(v, piso) for v in vals], height=0.62, color=cols, zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{n}  ·  {k}" for n, _v, k in grupo], fontsize=7.8)
        for i, (_n, v, _k) in enumerate(grupo):
            # Fondo blanco en la cifra: las barras de 15 a 49 MW dejan su rotulo
            # justo encima de la linea de puntos y el trazo cruzaba los digitos.
            ax.text(max(v, piso) * 1.22, i, es(v, 2 if v < 10 else 1),
                    va="center", fontsize=7.8, color=cols[i], fontweight="bold",
                    zorder=5,
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
        # La linea del criterio va DETRAS de las barras y de las cifras: por
        # delante tachaba los rotulos de las que caen justo por debajo de 50 MW.
        ax.axvline(50, color=TINTA, lw=1.0, ls=(0, (4, 3)), zorder=1)
        ax.set_xscale("log")
        ax.set_xlim(piso, 1600)
        ax.set_xticks([])
        ax.minorticks_off()
        ax.set_ylim(mitad - 0.15, -0.7)
        limpiar(ax, ("top", "right", "bottom", "left"))
        ax.tick_params(axis="y", length=0)

    axes[0].text(0, 1.045,
                 "Capacidad libre en la barra (MW)  ·  subestación  ·  candidatas que cuelgan de ella",
                 transform=axes[0].transAxes, ha="left", va="bottom", fontsize=8.4,
                 color=TINTA3)
    # Las dos columnas comparten escala, de modo que las barras siguen siendo
    # comparables entre una y otra y la linea de 50 MW cae en el mismo sitio. El
    # rotulo va solo en la primera: repetirlo en la segunda no anade nada.
    # El rotulo del criterio va en la columna DERECHA, sobre la primera fila. En la
    # izquierda caia sobre la cifra de Planeta Rica, porque en escala logaritmica
    # un texto de ancho fijo centrado en 50 MW se extiende hasta pasado el 200; y
    # al pie caia sobre la ultima barra. Ahi arriba no hay nada dibujado.
    axes[1].text(50, len(grupos[1]) / 2, "50 MW, el límite del criterio", fontsize=7.8,
                 color=TINTA, va="center", ha="center",
                 bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
    guardar(fig, "fig_capacidad.pdf")


# =============================================================== 12. EMBUDO
def embudo():
    """La cascada completa, del panel nacional al lote caracterizado.

    Las dos cifras del buffer se verificaron sobre grids_within_buffer.gpkg:
    7.239 celdas dentro del radio de una subestacion, de las cuales 71 ya tienen
    planta y se apartan, y 7.168 son las que el modelo puntua.

    Antes era un grafico de barras cuyas longitudes no codificaban las cifras: la
    barra de 10 grillas salia mas larga que la de 2.745 lotes, y las siete filas
    compartian una escala unica pese a que las cinco primeras cuentan grillas y las
    dos ultimas lotes. Una barra que no mide es peor que ninguna barra, asi que se
    sustituye por la cifra en escalera, con una linea rotulada donde cambia la
    unidad. La cifra grande se lee de sobra a tamano de proyeccion.
    """
    lot = _csv("lotes_distribuida.csv")
    desc = _csv("lotes_distribuida_descartados.csv")
    pasos = [("Panel nacional", es(21447), "celdas de 5 x 5 km"),
             ("Al alcance de la red", es(7239), "dentro del radio de una subestación"),
             ("Puntuadas por el modelo", es(7168), "se apartan las 71 que ya tienen planta"),
             ("Candidatas", es(len(_csv("grillas_candidatas.csv"))), "mayor afinidad con el perfil"),
             ("Selección del cliente", es(len(_csv("grillas_para_predios.csv"))), "grillas marcadas en el reporte"),
             ("Catastro del IGAC", es(len(lot) + len(desc)), "lotes descargados, sin filtrar"),
             ("Caracterización", es(len(lot)), "lotes medidos uno a uno")]
    # Donde cambia la unidad: hasta la fila 5 se cuentan grillas, desde la 6 lotes.
    CORTE = 5

    # En centimetros del lienzo. Siete filas en 5 cm dan 0,65 cm por fila, que es
    # justo lo que ocupan una cifra de 12 pt y su rotulo de 7 pt. Con coordenadas
    # en fracciones esto no se puede comprobar, y las filas se solapaban.
    W, A = 13.6, 4.35
    FILA, HUECO = 0.645, 0.60
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    n = len(pasos)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    tonos = ["#BCDCDF", "#A2CFD3", "#88C2C7", "#5FAEB4", "#3E9BA3", "#1E7C84", "#0F5E65"]

    # Borde superior de cada fila, con un hueco extra donde cambia la unidad para
    # que la linea divisoria caiga en blanco y no encima de una fila.
    tops = [A - i * FILA - (0.0 if i < CORTE else HUECO) for i in range(n)]

    for i, ((et, num, sub), c) in enumerate(zip(pasos, tonos)):
        t = tops[i]
        # Escalera: cada fila entra un poco mas que la anterior.
        x = 0.20 + i * 0.52
        ax.plot([x, x], [t - 0.58, t - 0.06], color=c, lw=2.6,
                solid_capstyle="round", zorder=2)
        ax.text(x + 0.22, t - 0.245, num, va="center", ha="left", fontsize=12,
                fontweight="bold", color=c, zorder=3)
        ax.text(x + 0.22, t - 0.51, sub, va="center", ha="left", fontsize=7.6,
                color=TINTA2, zorder=3)
        ax.text(W, t - 0.245, et, va="center", ha="right", fontsize=8.2,
                color=TINTA, zorder=3)

    # A media altura entre el pie de la ultima fila de grillas y la cabeza de la
    # primera de lotes, calculado de las posiciones reales y no a ojo.
    ycorte = ((tops[CORTE - 1] - 0.58) + tops[CORTE]) / 2
    ax.plot([0, W], [ycorte, ycorte], color=LINEA, lw=0.8, zorder=1)
    # El rotulo va DEBAJO de la linea: encima se montaba sobre el pie de la
    # ultima fila de grillas, que baja mas que su propio trazo.
    ax.text(0, ycorte - 0.05,
            "cambia la unidad: de grillas de 25 km²  a  lotes del catastro",
            va="top", ha="left", fontsize=7.6, color=TINTA3)

    guardar(fig, "fig_embudo.pdf")


# ================================================================ 13. EL MAPA
#: Tramos del indice de aptitud para la leyenda del mapa. El corte de 70 es el de
#: la lista corta (INDICE_PRIORITARIA en reporte/datos.py); los otros dos parten el
#: resto en tercios legibles.
TRAMOS = [(70, 100, "70 y más", "#0F5E65"),
          (60, 70, "60 a 70", "#2E8B93"),
          (50, 60, "50 a 60", "#7FBBC0"),
          (0, 50, "menos de 50", "#BCDCDF")]


def _colombia():
    import geopandas as gpd
    g = gpd.read_file(RAIZ / "data" / "paises" / "ne_50m_admin_0_countries.shp")
    return g[g.ADMIN.str.contains("Colombia", case=False, na=False)]


def _candidatas():
    import geopandas as gpd
    c = gpd.read_file(REP / "grillas_candidatas.geojson")
    # Centroide en un CRS proyectado y de vuelta: en geografico el aviso de
    # geopandas es legitimo, aunque a esta escala la diferencia sea invisible.
    p = c.to_crs(3116).geometry.centroid.to_crs(4326)
    c = c.copy()
    c["lon"], c["lat"] = p.x.values, p.y.values
    return c


def _dibujar_mapa(ax, co, c, tam_punto, lw_pais, con_leyenda):
    co.boundary.plot(ax=ax, color="#9AA8A9", linewidth=lw_pais, zorder=2)
    co.plot(ax=ax, color="#F2F5F5", zorder=1)
    for lo, hi, et, col in TRAMOS:
        s = c[(c.indice_aptitud >= lo) & (c.indice_aptitud < hi if hi < 100
                                          else c.indice_aptitud <= hi)]
        if s.empty:
            continue
        ax.scatter(s.lon, s.lat, s=tam_punto, color=col, zorder=4,
                   edgecolor="white", linewidth=0.35, label=f"{et}  ({len(s)})")
    ax.set_aspect("equal")
    ax.set_xlim(-79.6, -66.5); ax.set_ylim(-4.6, 13.2)
    ax.axis("off")
    if con_leyenda:
        # La leyenda va FUERA del mapa, a su derecha. Dentro, anclada abajo a la
        # izquierda, quedaba dibujada encima de Colombia: los cuatro rotulos se
        # leian sobre el relleno del pais y sobre los propios puntos del Pacifico.
        leg = ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.52),
                        frameon=False, fontsize=8.6, handletextpad=0.35,
                        labelspacing=0.70, borderpad=0.0,
                        title="Índice de aptitud", title_fontsize=8.6)
        leg._legend_box.align = "left"
        leg.get_title().set_color(TINTA3)


def mapa():
    """Las cien candidatas sobre el pais, con leyenda del indice.

    Sustituye a la captura de pantalla v2_mapa.png, que llegaba a la lamina con
    3,19 cm de ancho, los cien puntos en dos o tres pixeles cada uno, el contorno
    del pais en un gris casi invisible y sin leyenda ninguna: es la lamina que
    ensena el resultado del modelo y no se podia leer que significaba el color.
    En vectorial el punto no se empasta al reducir y la leyenda dice la variable.
    """
    co, c = _colombia(), _candidatas()
    fig, ax = plt.subplots(figsize=tam(5.4, 3.95))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    _dibujar_mapa(ax, co, c, tam_punto=30, lw_pais=0.8, con_leyenda=True)
    guardar(fig, "fig_mapa.pdf")


def mapa_portada():
    """El mismo mapa, sin leyenda y en un solo tono, para la portada."""
    co, c = _colombia(), _candidatas()
    fig, ax = plt.subplots(figsize=tam(4.5, 7.00))
    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    co.plot(ax=ax, color="#EEF2F2", zorder=1)
    co.boundary.plot(ax=ax, color="#C7D0D0", linewidth=0.7, zorder=2)
    ax.scatter(c.lon, c.lat, s=26, color=MARCA, zorder=4, alpha=0.9,
               edgecolor="white", linewidth=0.4)
    ax.set_aspect("equal")
    ax.set_xlim(-79.6, -66.5); ax.set_ylim(-4.6, 13.2)
    ax.axis("off")
    guardar(fig, "fig_mapa_portada.pdf")


# ============================================================== 14. EL PILOTO
def _piloto():
    """El lote 13 de la grilla del piloto, leido del propio entregable.

    Se lee del JSON incrustado en entregables/piloto/reporte_predios.html y no de
    una copia a mano, para que la lamina no pueda desincronizarse del fichero que
    se entrega. Es exactamente el defecto que tenia la ficha de la lamina 27.
    """
    import json
    ruta = RAIZ / "entregables" / "piloto" / "reporte_predios.html"
    s = ruta.read_text(encoding="utf-8", errors="replace")
    i = s.index("const D = {") + len("const D = ")
    prof, j = 0, i
    while True:
        prof += (s[j] == "{") - (s[j] == "}")
        j += 1
        if prof == 0:
            break
    D = json.loads(s[i:j])
    lote = [x for x in D["lotes"]["utility"] if x["orden"] == 13][0]
    return D, D["celdas"][0], lote


#: Los siete criterios en el orden de la ficha, con la columna que los mide.
#:
#: Capacidad y recurso se leen de la celda y no del lote: son las dos variables que
#: el lote no puede cambiar. Que el recurso se toma de la celda se comprueba en el
#: propio reporte, cuyo motivo dice «produccion fotovoltaica de 1443 kWh/kWp», que
#: es el pvout de la celda (1.442,6) y no el del lote (1.436,3).
CR_PILOTO = [("pendiente", "pendiente_media", 1),
             ("cobertura", "cobertura_apta_pct", 1),
             ("capacidad", None, 1),
             ("rugosidad", "rugosidad_m", 1),
             ("dist_via", "dist_via_km", 2),
             ("dist_sub", "conexion_km", 1),
             ("recurso", None, 0)]


def _nota(c, v):
    """La nota 0-100 de un valor contra los tres umbrales del criterio.

    Es la misma interpolacion de la plantilla del reporte: limite vale 0, bueno
    vale 70, tope vale 100, y entre ellos se interpola en dos tramos.
    """
    lim, bue, top = c["limite"], c["bueno"], c["tope"]
    if c["mayor_mejor"]:
        if v <= lim:
            return 0.0
        if v >= top:
            return 100.0
        return (70 + 30 * (v - bue) / (top - bue) if v >= bue
                else 70 * (v - lim) / (bue - lim))
    if v >= lim:
        return 0.0
    if v <= top:
        return 100.0
    return (70 + 30 * (bue - v) / (bue - top) if v <= bue
            else 70 * (lim - v) / (lim - bue))


def _tabla_criterios(CR, valores, pie, nombre, alto=4.9):
    """Dibuja la tabla de los siete criterios de un lote.

    Sustituye a las capturas v2_ficha_criterios.png. Aquella se tomo antes de que
    los umbrales se recalibraran a escala de lote, de modo que mostraba 29,4 / 8,8
    / 2,7 en distancia al punto de conexion y un indice de 77, cuando el reporte
    que se entrega dice 28,9 / 6,3 / 3,5 y un indice de 65 para el mismo lote.
    Dibujarla aqui, leyendo los umbrales y los valores de la salida vigente, es lo
    que impide que la lamina y el entregable vuelvan a separarse.
    """
    peso_tot = sum(CR[k]["d_cohen"] for k, _, _ in CR_PILOTO)
    filas = []
    for k, _col, dec in CR_PILOTO:
        c = CR[k]
        v = valores[k]
        filas.append((c["etiqueta"], c["unidad"], v, dec, c["limite"], c["bueno"],
                      c["tope"], _nota(c, v), 100 * c["d_cohen"] / peso_tot))

    fig, ax = plt.subplots(figsize=tam(13.6, alto))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.90, bottom=0.02)
    # El margen superior negativo es el sitio de la cabecera, que ahora lleva dos
    # lineas: «LÍMITE / (0)» en vez de «LÍMITE (0)», que no cabia a lo ancho.
    ax.set_xlim(0, 1); ax.set_ylim(-0.55, len(filas) + 1.90); ax.axis("off")
    ax.invert_yaxis()

    # Las columnas se colocan midiendo el texto, no con posiciones escritas a
    # mano. Con posiciones fijas los rotulos se pisaban entre si en el PDF
    # compuesto: «Cobertura apta del suelo» invadia la columna del valor y las
    # cabeceras de los tres umbrales se montaban unas sobre otras.
    def ancho(t, fs, bold=False):
        tx = ax.text(0, 0, t, fontsize=fs, fontweight="bold" if bold else "normal")
        w = tx.get_window_extent(renderer=fig.canvas.get_renderer()).width
        tx.remove()
        return w / (fig.get_size_inches()[0] * fig.dpi)

    FS_CRIT, FS_VAL, FS_UMB, FS_CAB, FS_NOTA = 9.8, 9.8, 8.8, 7.8, 9.8
    HUECO, BARRA = 0.020, 0.062

    txt_val = {k: f"{es(v, dec)} {u}"
               for (k, _, _), (_, u, v, dec, *_) in zip(CR_PILOTO, filas)}
    cols = [
        ("lim", "LÍMITE\n(0)", [es(f[4], f[3]) for f in filas], FS_UMB, False),
        ("bue", "OBJETIVO\n(70)", [es(f[5], f[3]) for f in filas], FS_UMB, False),
        ("top", "TOPE\n(100)", [es(f[6], f[3]) for f in filas], FS_UMB, False),
        ("nota", "NOTA", [es(f[7]) for f in filas], FS_NOTA, True),
        ("peso", "PESO", [f"{es(f[8])} %" for f in filas], FS_UMB, False),
    ]
    # De derecha a izquierda: cada columna reserva lo que mide su cabecera o su
    # dato mas ancho, mas un hueco fijo.
    X, borde = {}, 1.0 - BARRA - HUECO
    for k, cab, vals, fs, bold in reversed(cols):
        w = max([ancho(l, FS_CAB) for l in cab.split("\n")]
                + [ancho(t, fs, bold) for t in vals])
        X[k] = borde
        borde -= w + HUECO
    X["val"] = borde
    X["crit"] = 0.0
    # Si el nombre del criterio y su valor no caben en lo que queda, se reduce el
    # cuerpo de las dos columnas hasta que caben. Nunca por debajo de 7,4 pt.
    w_crit = max(ancho(f[0], FS_CRIT, True) for f in filas)
    w_val = max(ancho(t, FS_VAL, True) for t in txt_val.values())
    while w_crit + HUECO + w_val > borde and FS_CRIT > 7.4:
        FS_CRIT -= 0.2
        FS_VAL -= 0.2
        w_crit = max(ancho(f[0], FS_CRIT, True) for f in filas)
        w_val = max(ancho(t, FS_VAL, True) for t in txt_val.values())

    ax.text(0.0, 0.35, "CRITERIO", ha="left", va="center", fontsize=FS_CAB,
            color=TINTA3)
    ax.text(X["val"], 0.35, "EN EL LOTE", ha="right", va="center",
            fontsize=FS_CAB, color=TINTA3)
    for k, cab, _v, _f, _b in cols:
        ax.text(X[k], 0.35, cab, ha="right", va="center", fontsize=FS_CAB,
                color=TINTA3, linespacing=1.35, multialignment="right")
    ax.plot([0, 1], [1.02, 1.02], color=TINTA2, lw=1.1)

    for i, (et, uni, v, dec, lim, bue, top, nt, pes) in enumerate(filas):
        y = i + 1.62
        # Rojo cuando el criterio esta por debajo de su limite: es el reparo que
        # deja el lote Viable con gestion, y es la lectura que la lamina permite.
        rojo = nt <= 0
        col = MAL if rojo else TINTA
        ax.text(X["crit"], y, et, ha="left", va="center", fontsize=FS_CRIT,
                color=col, fontweight="bold" if rojo else "normal")
        ax.text(X["val"], y, f"{es(v, dec)} {uni}", ha="right", va="center",
                fontsize=FS_VAL, color=col, fontweight="bold")
        for k, val in (("lim", lim), ("bue", bue), ("top", top)):
            ax.text(X[k], y, es(val, dec), ha="right", va="center", fontsize=FS_UMB,
                    color=TINTA3)
        ax.text(X["nota"], y, es(nt), ha="right", va="center", fontsize=FS_NOTA,
                color=col, fontweight="bold")
        ax.text(X["peso"], y, f"{es(pes)} %", ha="right", va="center",
                fontsize=FS_UMB, color=TINTA2)
        # Barra de la nota, a la derecha del todo.
        x0 = 1.0 - BARRA
        ax.add_patch(Rectangle((x0, y - 0.16), BARRA, 0.32, fc=LINEA, ec="none"))
        if nt > 0:
            ax.add_patch(Rectangle((x0, y - 0.16), BARRA * nt / 100, 0.32,
                                   fc=MARCA, ec="none"))
        ax.plot([0, 1], [y + 0.5, y + 0.5], color=LINEA, lw=0.5)

    ax.text(0.0, len(filas) + 1.62, pie, ha="left", va="center", fontsize=9.4,
            color=TINTA2)
    guardar(fig, nombre)
    return filas


def piloto_criterios():
    """Los siete criterios de El Poblado, el lote del piloto.

    Lienzo mas bajo que el de la ficha porque su lamina lleva ademas los dos
    bloques de texto del veredicto: el hueco es de 3,9 cm y no de 4,2.
    """
    D, celda, lote = _piloto()
    val = {k: (float(celda["capacidad_at_mw"]) if k == "capacidad"
               else float(celda["pvout"]) if k == "recurso"
               else float(lote[col]))
           for k, col, _ in CR_PILOTO}
    pie = (f"Índice del lote {es(lote['indice_lote'])} sobre 100 · "
           f"{lote['criterios_cumplidos']} criterio cumplido de "
           f"{lote['criterios_evaluados']} · 3 criterios por debajo de su límite")
    _tabla_criterios(D["criterios"], val, pie, "fig_piloto_criterios.pdf", alto=3.9)


def ficha_criterios():
    """Los siete criterios del lote de Sabana de Torres, el de la ficha.

    Los umbrales se leen de umbrales_lote.json (escala de lote, utility) sobre las
    definiciones de reporte/datos.py, que es exactamente la composicion que aplica
    el reporte entregado: cr = {...cr0, ...(umb[k] || {})}.
    """
    import json
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg

    umb = json.loads((REP / "umbrales_lote.json").read_text(encoding="utf-8"))
    CR = {k: {**v} for k, v in rg.CRITERIOS.items()}
    for k, u in umb["utility"]["umbrales"].items():
        CR[k].update({x: u[x] for x in ("tope", "bueno", "limite")})

    u = _csv("lotes_utility.csv")
    lote = u[u.CODIGO.astype(str) == "686550001000000050003000000000"].iloc[0]
    import geopandas as gpd
    g = gpd.read_file(REP / "grillas_candidatas.geojson")
    celda = g[g.cell_id.astype(str).str.zfill(7) == str(lote.cell_id).zfill(7)].iloc[0]

    val = {"pendiente": float(lote.pendiente_media),
           "cobertura": float(lote.cobertura_apta_pct),
           "capacidad": float(celda.capacidad_at_mw),
           "rugosidad": float(lote.rugosidad_m),
           "dist_via": float(lote.dist_via_km),
           "dist_sub": float(lote.conexion_km),
           "recurso": float(celda.pvout)}
    pie = (f"Índice del lote {es(lote.indice_lote)} sobre 100 · "
           f"{lote.criterios_cumplidos} criterios cumplidos de "
           f"{lote.criterios_evaluados} · 1 criterio por debajo de su límite")
    _tabla_criterios(CR, val, pie, "fig_ficha_criterios.pdf", alto=4.2)


if __name__ == "__main__":
    cadena(); contraste(); variables(); urbano(); similitud()
    criba_lotes(); perfiles()
    pesos(); escala(); tamano(); distribucion(); capacidad(); embudo()
    mapa(); mapa_portada(); piloto_criterios(); ficha_criterios()
