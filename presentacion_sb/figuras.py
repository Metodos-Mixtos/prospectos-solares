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
import json
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
SAL = RAIZ / "outputs" / "presentacion_sb" / "figuras"
SAL.mkdir(parents=True, exist_ok=True)

NL = chr(10)

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


#: Resolucion a la que se embeben los mapas de bits dentro del PDF vectorial.
#: matplotlib usa por defecto la dpi de la figura, que son 100, y a ese valor una
#: captura de 1.242 px colocada a 6,7 cm se remuestreaba a unos 260: las imagenes
#: satelitales y las de la ficha llegaban visiblemente pastosas. A 600 ppp toda
#: captura se embebe por encima de su resolucion nativa, de modo que ninguna se
#: remuestrea. El texto y las lineas siguen siendo vectoriales.
PPP_MAPA_DE_BITS = 600


def guardar(fig, nombre):
    fig.savefig(SAL / nombre, bbox_inches="tight", dpi=PPP_MAPA_DE_BITS)
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
    pasos = [
        ("P A S O  1", "El mapa de celdas", "se divide el país"),
        ("P A S O  2", "Dónde se ha construido", "se mide el perfil"),
        ("P A S O  3", "El modelo", "se puntúa lo que alcanza la red"),
        ("P A S O  4", "Selección de celdas", "se aplican los criterios"),
        ("P A S O  5", "De la celda al lote", "se mide el lote"),
        ("P A S O  6", "La información para comprar", "se arma el expediente"),
    ]
    # Solo el nombre del resultado. La lamina responde a que viaja entre un paso y
    # el siguiente, no a cuanto mide: las cifras que llevaba debajo (112 grillas,
    # 21.447, 10 en el piloto, 647 lotes) adelantaban resultados que el guion aun
    # no ha contado y competian con el nombre, que es lo unico que hay que retener.
    puentes = ["Panel nacional", "Perfil de referencia", "Cien candidatas",
               "Celdas seleccionadas", "Lista corta y ficha"]

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
    # El alto baja de 3,95 a 2,98: al quitar la cifra del puente sobraba media
    # banda en blanco al pie, y con ella la figura llegaba encogida a la lamina.
    W, A = 6 * 2.09 + 5 * 0.292, 4.65
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    ren = fig.canvas.get_renderer()

    # El ancho de caja se DERIVA del lienzo, no se escribe a mano. Con 2,09 y un
    # hueco de 0,292 las seis cajas sumaban 14,0 cm sobre un lienzo de 13,6: la
    # sexta se salia por la derecha y pdflatex la recortaba a media palabra, de
    # modo que la lamina que abre el guion ensenaba «La informaci / para compr».
    hueco = 0.28
    w = (W - 5 * hueco) / 6
    y0, alto = 1.62, 2.85
    xs = [i * (w + hueco) for i in range(6)]
    # Seis tonos de la misma rampa: DEGRADADO trae cinco.
    tonos = ["#DCEAEB", "#B9D8DB", "#8CC3C8", "#4FA5AC", "#1E7C84", "#0F5E65"]

    for i, ((rot, tit, verbo), x) in enumerate(zip(pasos, xs)):
        ax.add_patch(FancyBboxPatch((x, y0), w, alto,
                     boxstyle="round,pad=0.012,rounding_size=0.06",
                     fc=tonos[i], ec="none"))
        tc = TINTA if i < 3 else "white"
        # Medido y no a ojo: con los saltos escritos a mano, «que alcanza la
        # red» sobresalia de sus 2,03 cm de caja y se metia en la del paso 4.
        _pila_en_caja(ax, ren, x, y0, w, alto,
                      [(rot, 8.0, {"color": tc, "ha": "center", "alpha": 0.95}),
                       (tit, 7.8, {"color": tc, "ha": "center",
                                   "fontweight": "bold"}),
                       (verbo, 7.9, {"color": tc, "ha": "center"})],
                      pad_x=0.10, pad_y=0.20, sep=0.26, donde="arriba")

    yf = y0 + alto / 2
    for i in range(5):
        a, b = xs[i] + w + 0.035, xs[i + 1] - 0.035
        ax.add_patch(FancyArrowPatch((a, yf), (b, yf), arrowstyle="-|>",
                     mutation_scale=8, color=ACENTO, lw=0.9, shrinkA=0, shrinkB=0))
        cx = (a + b) / 2
        nom = puentes[i]
        # Guia fina desde la flecha hasta su rotulo, para que se sepa cual es cual.
        ax.plot([cx, cx], [y0 - 0.12, 0.80], color=LINEA, lw=0.6, zorder=0)
        ax.text(cx, 0.70, textwrap.fill(nom, 16), ha="center", va="top",
                fontsize=8.6, fontweight="bold", color=TINTA2, linespacing=1.25)

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
    """Las diez variables que mas separan, una barra por grupo y un panel por variable.

    Rehecha por decision de la reunion del 27 de agosto. Antes era una sola fila
    por variable con dos puntos unidos por una linea, y Daniel Wiesner senalo el
    problema: en las variables donde un valor MAYOR significa algo PEOR, como la
    privacion socioeconomica, la lectura se invierte y la figura confunde. Con dos
    barras clasicas por variable la comparacion es directa y el sentido de cada
    escala se puede rotular.

    Cada panel lleva su propia escala, porque las unidades no son comparables
    entre variables. Eso se dice al pie.
    """
    d = _csv("influencia_covariables.csv")
    d = d.reindex(d.d_cohen.abs().sort_values(ascending=False).index).head(10)
    d = d.reset_index(drop=True)

    #: Donde el sentido de la escala no es obvio se dice, que es lo que Daniel
    #: Wiesner pidio: en privacion, un valor mas alto es peor, no mejor.
    SENTIDO = {"Privación socioeconómica": "índice 0 a 100 · más alto, peor"}

    COL, FIL = 5, 2
    W, A = 13.6, 5.65
    fig, ejes = plt.subplots(FIL, COL, figsize=tam(W, A))
    fig.subplots_adjust(left=0.012, right=0.988, top=0.74, bottom=0.06,
                        wspace=0.42, hspace=0.95)

    for k, ax in enumerate(ejes.ravel()):
        if k >= len(d):
            ax.axis("off")
            continue
        f = d.iloc[k]
        uni, dec = UNIDAD.get(f.nombre, ("", 1))
        con, sin = float(f.media_con), float(f.media_sin)
        ax.bar([0], [con], width=0.62, color=ACENTO2, zorder=3)
        ax.bar([1], [sin], width=0.62, color="#B9C2C3", zorder=3)
        tope = max(con, sin)
        for x, v in ((0, con), (1, sin)):
            ax.text(x, v + tope * 0.055, es(v, dec), ha="center", va="bottom",
                    fontsize=7.6, fontweight="bold",
                    color=ACENTO2 if x == 0 else TINTA2)
        ax.set_title(textwrap.fill(f.nombre, 17), fontsize=7.8, color=TINTA,
                     pad=5, linespacing=1.25)
        ax.set_xlim(-0.7, 1.7)
        ax.set_ylim(0, tope * 1.30)
        ax.set_xticks([])
        ax.set_yticks([])
        for e in ("top", "right", "left"):
            ax.spines[e].set_visible(False)
        ax.spines["bottom"].set_color(LINEA)
        pie = SENTIDO.get(f.nombre) or uni.strip()
        if pie:
            ax.text(0.5, -0.09, pie, transform=ax.transAxes, ha="center",
                    va="top", fontsize=6.6, color=TINTA3)

    fig.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, fc=ACENTO2),
        plt.Rectangle((0, 0), 1, 1, fc="#B9C2C3")],
        labels=["grillas con planta de 10 MW o más", "el resto del panel"],
        loc="upper left", bbox_to_anchor=(0.012, 1.005), frameon=False, ncol=2,
        fontsize=8.8, handlelength=1.1, handleheight=0.9, columnspacing=1.8)
    guardar(fig, "fig_contraste.pdf")


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
            "El archivo de lo que quedó fuera conserva cada lote con su motivo escrito.",
            fontsize=7.6, color=TINTA3, va="bottom")
    fig.tight_layout()
    guardar(fig, "fig_criba_lotes.pdf")


# ================================================================ 7. PERFILES
def perfiles():
    """Los mismos lotes bajo los dos perfiles de proyecto.

    Rehecha. La version anterior comparaba el REPARTO POR CLASE de cada perfil, y
    eso dejo de decir nada: en la salida vigente la clase depende de las
    condiciones juridicas y de ordenamiento del lote, que son las mismas mire
    quien mire, de modo que los dos perfiles daban dos barras identicas.

    Lo que si cambia con el perfil es cuantos lotes tienen el tamano que el
    proyecto necesita, y la calificacion del mismo lote, porque el perfil exige
    otra capacidad de barra y otro punto de conexion. Eso es lo que se dibuja.
    """
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
    cabe_u = int(u["cabe_utility"].astype(bool).sum())
    cabe_d = int(d["cabe_distribuida"].astype(bool).sum())

    W, A = 12.8, 3.55
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    X0, ANCHO = 0.15, W - 0.30
    filas = [
        (A - 0.75, "Escala utility",
         f"proyecto de {es(pu['mw_proyecto'])} MW · {es(pu['ha_proyecto'])} ha · "
         f"{es(an_u)} m de ancho", cabe_u, ACENTO2),
        (A - 2.05, "Generación distribuida",
         f"proyecto de {es(pd_['mw_proyecto'])} MW · {es(pd_['ha_proyecto'])} ha · "
         f"{es(an_d)} m de ancho", cabe_d, MARCA),
    ]
    for y, nom, sub, n, col in filas:
        ax.text(X0, y + 0.42, nom, ha="left", va="center", fontsize=9.6,
                fontweight="bold", color=TINTA)
        ax.text(X0 + ANCHO, y + 0.42, sub, ha="right", va="center", fontsize=8.2,
                color=TINTA3)
        ax.add_patch(FancyBboxPatch((X0, y - 0.155), ANCHO, 0.31,
                     boxstyle="round,pad=0,rounding_size=0.05", fc=LINEA,
                     ec="none", zorder=2))
        ax.add_patch(FancyBboxPatch((X0, y - 0.155), ANCHO * n / total, 0.31,
                     boxstyle="round,pad=0,rounding_size=0.05", fc=col, ec="none",
                     zorder=3))
        dentro = ANCHO * n / total > 1.4
        ax.text(X0 + ANCHO * n / total + (-0.16 if dentro else 0.16), y,
                f"{es(n)} de {es(total)} lotes tienen ese tamaño",
                ha="right" if dentro else "left", va="center", fontsize=8.6,
                fontweight="bold", color="white" if dentro else col, zorder=4)

    ax.plot([X0, X0 + ANCHO], [0.86, 0.86], color=LINEA, lw=0.8)
    ax.text(X0, 0.50, "El mismo lote de Sabana de Torres califica 65 sobre 100 como "
            "utility y 78 como distribuida:", ha="left", va="center", fontsize=8.6,
            color=TINTA2)
    ax.text(X0, 0.16, "cambia la capacidad de barra que se exige, no el terreno.",
            ha="left", va="center", fontsize=8.6, color=TINTA2)
    guardar(fig, "fig_perfiles.pdf")


def pesos():
    """Los siete criterios, ordenados por lo que pesan en el indice.

    Diseno. Antes cada barra llevaba DOS cifras: la d de Cohen fuera del extremo y
    el peso en blanco dentro, pegado al borde, de modo que a tamano de proyeccion
    el porcentaje se leia partido por el canto de su propia barra. Y la longitud
    medida era la d, cuando el rotulo de la lamina pregunta por el peso: la barra
    no respondia a la pregunta que la lamina hace.

    Ahora la barra ES el peso y lleva una sola cifra, fuera y en su color. La d
    baja a una columna propia y rotulada, a la derecha, que es de donde el peso
    sale. El orden se invierte para que el que mas pesa quede arriba.
    """
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg

    it = sorted(((v["etiqueta"], v["d_cohen"]) for v in rg.CRITERIOS.values()),
                key=lambda x: -x[1])
    suma = sum(d for _, d in it)
    pes = [100 * d / suma for _, d in it]

    #: Columna de la d, alineada por la derecha. El eje llega a 26,5 para que la
    #: cifra del peso quepa fuera de la barra sin invadirla.
    XD, XMAX = 25.4, 26.5

    fig, ax = plt.subplots(figsize=tam(11.7, 3.90))
    y = np.arange(len(it))
    ax.barh(y, pes, height=0.52,
            color=[ACENTO2 if k == 0 else MARCA for k in range(len(it))], zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _ in it], fontsize=8.5)
    for k, ((_n, d), q) in enumerate(zip(it, pes)):
        ax.text(q + 0.45, k, f"{es(q)} %", va="center", ha="left", fontsize=8.5,
                fontweight="bold", color=ACENTO2 if k == 0 else MARCA, zorder=4)
        ax.text(XD, k, es(d, 2), va="center", ha="right", fontsize=8, color=TINTA2)

    ax.text(0, -1.02, "PESO ASIGNADO", va="center", ha="left", fontsize=7.2,
            color=TINTA3)
    ax.text(XD, -1.02, "CAPACIDAD DE SEPARACIÓN", va="center", ha="right",
            fontsize=7.2, color=TINTA3)

    ax.set_xlim(0, XMAX)
    # Limites al reves en lugar de invert_yaxis: asi el hueco de la cabecera se
    # escribe una sola vez y no depende del orden en que se llamen las dos cosas.
    ax.set_ylim(len(it) - 0.45, -1.45)
    ax.set_xticks([])
    limpiar(ax, ("top", "right", "bottom", "left"))
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    guardar(fig, "fig_pesos.pdf")


# ================================================================== 9. ESCALA
def escala():
    """La escala de un criterio, primero en abstracto y luego con uno real.

    Arriba, los tres puntos y de donde salen. Abajo, el mismo mecanismo sobre la
    produccion fotovoltaica, con sus umbrales reales leidos de la salida: sirve
    ademas para ensenar que la escala funciona en los dos sentidos, porque aqui
    mas es mejor y la banda crece hacia la derecha igual que en distancia, donde
    menos es mejor.
    """
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg
    c = rg.CRITERIOS["recurso"]
    EJEMPLO = 1520.0
    nota = _nota(c, EJEMPLO)

    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("m", ["#F2F4F5", "#BFE0E2", MARCA, ACENTO2])
    grad = np.linspace(0, 1, 512).reshape(1, -1)

    fig, ax = plt.subplots(figsize=tam(13.2, 5.15))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.01)
    ax.set_xlim(-2, 102); ax.set_ylim(-4.30, 2.9); ax.axis("off")

    # --- Arriba: el mecanismo -----------------------------------------------
    ax.imshow(grad, extent=[0, 100, 0.15, 0.72], aspect="auto", cmap=cm, zorder=1)
    ax.add_patch(plt.Rectangle((0, 0.15), 100, 0.57, fill=False, ec=LINEA, lw=0.8,
                               zorder=3))
    for x, ali, arriba, abajo, col in [
        (0, "left", "Límite", "el decil peor de lo construido", TINTA2),
        (70, "center", "Objetivo", "la mediana", TINTA2),
        (100, "right", "Tope", "el decil mejor", ACENTO2),
    ]:
        ax.plot([x, x], [0.72, 1.10], color=col, lw=1.1, zorder=4)
        ax.text(x, 2.85, arriba, ha=ali, va="top", fontsize=12, fontweight="bold",
                color=col)
        ax.text(x, 2.12, abajo, ha=ali, va="top", fontsize=9, color=TINTA3,
                linespacing=1.35, multialignment=ali)
        ax.text(x, 0.02, str(x), ha=ali, va="top", fontsize=11, fontweight="bold",
                color=col)
    ax.text(0, -0.42, "No es un cumple o no cumple: se interpola.", ha="left",
            va="top", fontsize=9.0, color=TINTA3)

    # --- Abajo: el mismo mecanismo sobre un criterio con nombre y cifras -----
    ax.plot([0, 100], [-1.22, -1.22], color=LINEA, lw=0.8)
    ax.text(0, -1.46, c["etiqueta"].upper(), ha="left", va="top", fontsize=8.2,
            color=TINTA3)
    ax.text(100, -1.46, "aquí más es mejor, y la escala se lee igual", ha="right",
            va="top", fontsize=8.2, color=TINTA3)

    # Las cifras van ENCIMA de la banda y colgando (va="top"): puestas debajo se
    # montaban con el rotulo del criterio, y el 0-70-100 de abajo sobraba porque
    # el panel de arriba ya lo ensena.
    ax.imshow(grad, extent=[0, 100, -3.14, -2.62], aspect="auto", cmap=cm, zorder=1)
    ax.add_patch(plt.Rectangle((0, -3.14), 100, 0.52, fill=False, ec=LINEA, lw=0.8,
                               zorder=3))
    for x, val, ali, col in [(0, c["limite"], "left", TINTA2),
                             (70, c["bueno"], "center", TINTA2),
                             (100, c["tope"], "right", ACENTO2)]:
        ax.plot([x, x], [-2.62, -2.50], color=col, lw=1.1, zorder=4)
        ax.text(x, -2.05, f"{es(val)} {c['unidad']}", ha=ali, va="top",
                fontsize=9.4, fontweight="bold", color=col)

    ax.annotate("", xy=(nota, -3.14), xytext=(nota, -3.70),
                arrowprops=dict(arrowstyle="-|>", color=MAL, lw=1.4))
    ax.text(nota, -3.78,
            f"{es(EJEMPLO)} {c['unidad']}  →  {es(nota)} puntos",
            ha="center", va="top", fontsize=10.0, color=MAL, fontweight="bold")
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
    ax.text(0, -0.60,
            f"Un punto por lote. De los {es(len(d))}, {es(n_u)} alcanzan el "
            "preajuste de escala utility.",
            ha="left", va="top", fontsize=8.6, color=TINTA2,
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
        ax.text(-6, 1.25 * k, f"{cl}  {len(sub)}", ha="right", va="center",
                fontsize=9.5, color=color[cl], fontweight="bold")

    ax.axvline(70, color=ACENTO, lw=1.1, ls=(0, (4, 3)), zorder=2)
    ax.text(70, -0.92, "índice 70: el corte entre Elegible y Prioritaria",
            ha="center", va="center", fontsize=9.0, color=ACENTO)
    ax.set_xlim(-40, 106)
    ax.set_ylim(-1.25, 4.35)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 70, 100])
    ax.tick_params(axis="x", labelsize=9)
    ax.set_xlabel("Índice de la grilla", fontsize=9.5, labelpad=7)
    limpiar(ax, ("top", "right", "left"))
    ax.invert_yaxis()
    fig.tight_layout()
    guardar(fig, "fig_distribucion.pdf")


# ============================================================= 11. CAPACIDAD
NOMBRE_CORTO = {"San Marcos -Cesar 110 kV": "San Marcos - Cesar 110 kV"}


def capacidad():
    """Cuantas subestaciones tienen cupo y cuantas candidatas cuelgan de ellas.

    Diseno. Antes eran 31 barras en dos columnas con nombre, cifra y recuento en
    cada fila: casi cien datos para sostener una sola idea, y sin marcas en el eje,
    de modo que el lector no podia saber si 15 MW era mucho o poco. La lamina
    ensenaba el inventario y no la conclusion.

    Aqui se nombran solo las cinco que dan la talla, que son las accionables, y las
    veinticinco restantes se resumen en una banda partida por tramo. Abajo, lo que
    de verdad decide: cuantas de las cien candidatas cuelgan de una subestacion con
    cupo.
    """
    c = _csv("capacidad_barras.csv").dropna(subset=["capacidad_disponible_mw"])
    it = sorted(((NOMBRE_CORTO.get(n, n), float(v), int(k)) for n, v, k in
                 zip(c.sub_nombre_subestacion, c.capacidad_disponible_mw, c.candidatas)),
                key=lambda x: -x[1])
    LIM = 50.0
    con = [t for t in it if t[1] >= LIM]
    medio = [t for t in it if 10 <= t[1] < LIM]
    bajo = [t for t in it if t[1] < 10]
    n_con = sum(k for _n, _v, k in con)
    n_sin = sum(k for _n, _v, k in it) - n_con

    W, A = 13.4, 5.05
    XNOM, XBAR, ANCHO = 3.05, 3.25, 7.35
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    esc = ANCHO / 230.0

    ax.text(XNOM, A - 0.16, "CON CUPO", ha="right", va="top", fontsize=7.6,
            color=TINTA3)
    ax.text(XBAR, A - 0.16, f"{len(con)} subestaciones superan el límite de 50 MW",
            ha="left", va="top", fontsize=7.6, color=TINTA3)

    FILA, y = 0.455, A - 0.62
    for n, v, k in con:
        ax.plot([XBAR, XBAR + v * esc], [y, y], color=BIEN, lw=8.5,
                solid_capstyle="butt", zorder=3)
        ax.text(XNOM, y, n, ha="right", va="center", fontsize=8.6, color=TINTA)
        ax.text(XBAR + v * esc + 0.14, y, es(v, 1), ha="left", va="center",
                fontsize=8.6, fontweight="bold", color=BIEN)
        ax.text(W, y, f"{k} candidata" + ("s" if k > 1 else ""), ha="right",
                va="center", fontsize=8.0, color=TINTA2)
        y -= FILA

    # La linea del criterio se dibuja sobre el bloque de arriba, que es el unico
    # donde la escala esta en juego.
    ax.plot([XBAR + LIM * esc] * 2, [y + FILA * 0.62, A - 0.36], color=TINTA,
            lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.text(XBAR + LIM * esc, y + FILA * 0.42, "50 MW", ha="center", va="top",
            fontsize=7.6, color=TINTA)

    y -= 0.30
    ax.plot([XNOM - 2.7, W], [y, y], color=LINEA, lw=0.8)

    y -= 0.52
    ax.text(XNOM, y, "SIN CUPO", ha="right", va="center", fontsize=7.6, color=TINTA3)
    tot = len(medio) + len(bajo)
    ax.plot([XBAR, XBAR + ANCHO * len(medio) / tot], [y, y], color=AVISO, lw=13,
            solid_capstyle="butt", zorder=3)
    ax.plot([XBAR + ANCHO * len(medio) / tot, XBAR + ANCHO], [y, y], color=MAL,
            lw=13, solid_capstyle="butt", zorder=3)
    ax.text(XBAR + ANCHO * len(medio) / tot / 2, y, str(len(medio)), ha="center",
            va="center", fontsize=8.6, color="white", fontweight="bold", zorder=4)
    ax.text(XBAR + ANCHO * (1 + len(medio) / tot) / 2, y, str(len(bajo)),
            ha="center", va="center", fontsize=8.6, color="white",
            fontweight="bold", zorder=4)
    ax.text(XBAR + ANCHO * len(medio) / tot / 2, y - 0.30, "entre 10 y 50 MW",
            ha="center", va="top", fontsize=7.8, color=TINTA2)
    ax.text(XBAR + ANCHO * (1 + len(medio) / tot) / 2, y - 0.30, "menos de 10 MW",
            ha="center", va="top", fontsize=7.8, color=TINTA2)
    ax.text(W, y, f"{n_sin} candidatas", ha="right", va="center", fontsize=8.0,
            color=TINTA2)

    ax.text(XBAR, 0.10,
            "Solo " + str(n_con) + " de las cien candidatas cuelgan de una "
            "subestación con cupo.", ha="left", va="bottom", fontsize=9.2,
            color=TINTA, fontweight="bold")
    guardar(fig, "fig_capacidad.pdf")


# =============================================================== 12. EMBUDO
#: Las etapas del embudo y el filtro que aplica cada una. Sin recuentos: el panel
#: nacional es fijo, pero todo lo que viene despues depende de la corrida, del
#: umbral que ponga el cliente y de la version de los insumos. Poner las cifras de
#: una corrida invita a leerlas como si fueran del metodo.
ETAPAS_EMBUDO = [
    ("Panel nacional", "entran todas, sin filtrar", 1.00),
    ("Al alcance de la red", "dentro del radio de una subestación", 0.80),
    ("Puntuadas por el modelo", "se apartan las que ya tienen planta", 0.68),
    ("Candidatas", "las de mayor afinidad con el perfil", 0.52),
    ("Selección del cliente", "las que marca en el reporte", 0.36),
    ("Catastro", "todos los lotes de esas celdas, sin filtrar", 0.74),
    ("Lotes rurales", "se apartan los de la capa urbana del catastro", 0.60),
    ("Caracterización", "los que superan el mínimo de área y no tienen otra "
     "regla excluyente", 0.46),
]
#: Donde cambia la unidad: hasta la quinta se cuentan celdas, desde la sexta lotes.
CORTE_EMBUDO = 5


def embudo():
    """La reduccion del universo de analisis, etapa a etapa.

    Sin cifras a proposito. La unica que queda es el punto de partida, 21.447
    celdas, porque es estructural: no cambia entre corridas. Ojo con llamarlo el
    pais: el panel cubre 535.660 km2 de los 1.165.526 de la malla nacional, o sea
    el 46 %, y quedan fuera Amazonas, Guainia, Vaupes y Vichada enteros. Todo lo
    demas depende de la corrida, de los umbrales que fije el cliente y de la
    version de los insumos, de modo que escribirlo aqui haria pasar por metodo lo
    que es el resultado de un dia.

    El ancho de banda es esquematico y no mide nada: a escala real la banda de
    las cien candidatas mediria dos pixeles. Como el ancho invita a leerse como
    recuento, la lamina lo declara en su nota al pie.
    """
    from matplotlib.patches import FancyBboxPatch

    # Siete filas mas el hueco del cambio de unidad no caben en 5,05: la ultima
    # banda salia por debajo del lienzo.
    # Ocho filas en vez de siete: la fila del descarte urbano se hace explicita.
    # Con FILA 0,58 la ultima quedaba fuera del lienzo.
    W, A = 13.6, 5.95
    FILA, HUECO = 0.565, 0.60
    CENTRO, SEMI = 2.60, 2.20
    XETAPA = 5.55
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    n = len(ETAPAS_EMBUDO)
    # La rampa arranca de nuevo en la sexta banda, que es donde la unidad pasa
    # de celda a lote y el ancho vuelve a subir.
    tonos = ["#BCDCDF", "#A2CFD3", "#88C2C7", "#5FAEB4", "#3E9BA3",
             "#88C2C7", "#3E9BA3", "#0F5E65"]

    ejes = [A - 0.75 - FILA * (i + 0.5) - (0.0 if i < CORTE_EMBUDO else HUECO)
            for i in range(n)]

    for i, ((etapa, sub, frac), c) in enumerate(zip(ETAPAS_EMBUDO, tonos)):
        y = ejes[i]
        semi = SEMI * frac
        ax.add_patch(FancyBboxPatch((CENTRO - semi, y - 0.165), 2 * semi, 0.33,
                     boxstyle="round,pad=0,rounding_size=0.06", fc=c, ec="none",
                     zorder=2))
        ax.text(XETAPA, y + 0.135, etapa, va="center", ha="left", fontsize=8.6,
                fontweight="bold", color=TINTA, zorder=3)
        ax.text(XETAPA, y - 0.165, sub, va="center", ha="left", fontsize=7.6,
                color=TINTA2, zorder=3)

    # El punto de partida va en su propia banda arriba, no encima de la primera
    # fila, donde se montaba con el nombre de la etapa.
    ax.text(0.10, A - 0.24, "21.447", ha="left", va="center", fontsize=12.5,
            fontweight="bold", color=ACENTO2)
    ax.text(1.50, A - 0.22, "celdas de 5 por 5 km, algo menos de la mitad del "
            "país: el punto de partida no cambia entre corridas, lo que filtra "
            "cada etapa sí", ha="left", va="center", fontsize=7.6, color=TINTA3)

    ycorte = (ejes[CORTE_EMBUDO - 1] + ejes[CORTE_EMBUDO]) / 2
    ax.plot([0.10, W], [ycorte, ycorte], color=LINEA, lw=0.8, zorder=1)
    # Alineado al canto derecho: en la columna de las etapas se pegaba a la
    # aclaracion de la fila de arriba.
    ax.text(W, ycorte + 0.10, "de celdas de 25 km²  a  lotes del catastro",
            va="bottom", ha="right", fontsize=7.8, color=TINTA3)
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


def _dibujar_mapa(ax, co, c, tam_punto, lw_pais, con_leyenda, con_red=False):
    co.boundary.plot(ax=ax, color="#9AA8A9", linewidth=lw_pais, zorder=2)
    co.plot(ax=ax, color="#F2F5F5", zorder=1)
    if con_red:
        # La red va debajo y en gris claro: es contexto, no protagonista. Sin
        # ella el mapa ensena cien puntos agrupados y no dice por que se
        # agrupan; con ella se ve que la agrupacion sigue el trazado.
        lin, _sub = _red(co)
        lin.plot(ax=ax, color="#C3D3D4", linewidth=0.45, zorder=2.5)
    cal = c[c.clasificacion != "Excluida"]
    for lo, hi, et, col in TRAMOS:
        s = cal[(cal.indice_aptitud >= lo) & (cal.indice_aptitud < hi if hi < 100
                                              else cal.indice_aptitud <= hi)]
        if s.empty:
            continue
        ax.scatter(s.lon, s.lat, s=tam_punto, color=col, zorder=4,
                   edgecolor="white", linewidth=0.35, label=et)
    exc = c[c.clasificacion == "Excluida"]
    if not exc.empty:
        ax.scatter(exc.lon, exc.lat, s=tam_punto, color="#C4CCCD", zorder=3,
                   edgecolor="white", linewidth=0.35, label="sin calificar")
    ax.set_aspect("equal")
    # Cenido al pais continental: medio grado de margen por lado era, en
    # la lamina, mapa que no se dibujaba.
    ax.set_xlim(-79.2, -66.7); ax.set_ylim(-4.4, 12.8)
    ax.axis("off")
    if con_leyenda:
        # La leyenda va FUERA del mapa, a su derecha. Dentro, anclada abajo a la
        # izquierda, quedaba dibujada encima de Colombia: los cuatro rotulos se
        # leian sobre el relleno del pais y sobre los propios puntos del Pacifico.
        leg = ax.legend(loc="center left", bbox_to_anchor=(0.99, 0.52),
                        frameon=False, fontsize=6.8, handletextpad=0.32,
                        labelspacing=0.58, borderpad=0.0,
                        title="Índice de la grilla", title_fontsize=7.6)
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
    # El eje se queda con dos tercios del lienzo y la leyenda con el resto: antes
    # compartian mitad y mitad, y al ampliar la lamina la leyenda crecia tanto como
    # el pais.
    # La proporcion se elige para que en la lamina mande la ALTURA y no el
    # ancho: el pais es mas alto que ancho, de modo que cada punto de alto que
    # se le gane es mapa mas grande. Con 1,74 de proporcion la lamina lo
    # recortaba por ancho y el mapa salia mas pequeno que antes.
    fig, ax = plt.subplots(figsize=tam(8.0, 5.20))
    fig.subplots_adjust(left=-0.02, right=0.76, top=0.99, bottom=0.01)
    _dibujar_mapa(ax, co, c, tam_punto=40, lw_pais=0.9, con_leyenda=True,
                  con_red=True)
    guardar(fig, "fig_mapa.pdf")


#: Tramos de la red por tension, de menor a mayor. El troncal se dibuja encima y
#: mas oscuro, que es como se lee un mapa de red: primero el esqueleto.
NIVELES = [(0, 220_000, "#B5D5D8", 0.32, 3),
           (220_000, 400_000, "#3E9BA3", 0.55, 4),
           (400_000, 10 ** 9, "#0F5E65", 0.85, 5)]


def _red(co):
    """Lineas de transmision y subestaciones de OSM, recortadas a Colombia.

    La descarga se hizo por bloques sobre la ventana del pais, de modo que trae
    tramos de Ecuador, Peru, Venezuela y Panama. Sin recortar, la portada ensena
    red que no es colombiana.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    tramos = json.loads((REP / "lineas_transmision.json").read_text(encoding="utf-8"))
    lin = gpd.GeoDataFrame(
        {"kv": [t["kv"] or 0 for t in tramos]},
        geometry=[LineString(t["coords"]) for t in tramos], crs=4326)
    sub = gpd.read_file(REP / "subestaciones_osm.gpkg")

    pais = co.geometry.union_all()
    return gpd.clip(lin, pais), sub[sub.within(pais)]


def grilla_contexto():
    """La celda focal dentro de su reticula, sobre imagen satelital.

    Sustituye al recorte suelto de la celda. Un cuadrado de imagen aislado no
    dice de que tamano es ni respecto a que: aqui se ve la celda dentro de una
    ventana de tres por tres, con la reticula de 5 km dibujada encima, de modo
    que el lector reconstruye la unidad de analisis mirandola.
    """
    import geopandas as gpd
    from matplotlib.patches import Rectangle
    sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte")]
    from insumos import satelital

    g = gpd.read_file(REP / "grillas_candidatas.geojson")
    cel = g[g.cell_id.astype(str).str.zfill(7) == "0008656"].geometry.iloc[0]
    x0, y0, x1, y1 = cel.bounds
    w, h = x1 - x0, y1 - y0
    bbox = (x0 - w, y0 - h, x1 + w, y1 + h)
    img = plt.imread(str(satelital.bajar("0008656_ctx", bbox, px=1400)))

    fig, ax = plt.subplots(figsize=tam(6.6, 6.6))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(img, extent=(bbox[0], bbox[2], bbox[1], bbox[3]), zorder=1)

    # Reticula de 5 km, tomada de la propia celda: dos lineas por eje bastan para
    # que se lea el teselado sin tapar la imagen.
    for k in (-1, 0, 1, 2):
        ax.plot([x0 + k * w] * 2, [bbox[1], bbox[3]], color="white", lw=0.7,
                alpha=0.45, zorder=2)
        ax.plot([bbox[0], bbox[2]], [y0 + k * h] * 2, color="white", lw=0.7,
                alpha=0.45, zorder=2)

    # Todo lo que no es la celda focal se atenua. No se oculta: la gracia de la
    # lamina es justamente ver que hay alrededor.
    for xa, ya, xb, yb in ((bbox[0], y1, bbox[2], bbox[3]),
                           (bbox[0], bbox[1], bbox[2], y0),
                           (bbox[0], y0, x0, y1), (x1, y0, bbox[2], y1)):
        ax.add_patch(Rectangle((xa, ya), xb - xa, yb - ya, fc="black",
                               alpha=0.34, ec="none", zorder=3))

    ax.add_patch(Rectangle((x0, y0), w, h, fc="none", ec="white", lw=2.0, zorder=4))
    ax.plot([x0, x1], [y0 - h * 0.055] * 2, color="white", lw=1.6, zorder=4,
            solid_capstyle="butt")
    ax.text((x0 + x1) / 2, y0 - h * 0.135, "5 km", ha="center", va="top",
            fontsize=9, color="white", fontweight="bold", zorder=4)

    # En latitud 8 grados un grado de longitud mide menos que uno de latitud: sin
    # corregir el aspecto, la celda cuadrada se dibuja rectangular.
    ax.set_aspect(1.0 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.axis("off")
    guardar(fig, "fig_grilla_contexto.pdf")


def catastro_celda():
    """Los lotes del catastro de una celda, sobre la imagen satelital.

    Sustituye a una captura del visor que llegaba a la lamina con 3,5 cm de ancho,
    con la barra de la aplicacion incluida y su texto por debajo de 2 pt. Lo que
    la lamina tiene que ensenar es que se descarga el catastro entero de la celda
    y que cada lote se mide sobre su propio poligono: eso se ve dibujando los
    poligonos, no ensenando una foto de la pantalla.
    """
    import geopandas as gpd
    from matplotlib.patches import Rectangle
    sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte")]
    from insumos import satelital

    CELDA = "0010961"
    cel = None
    for nombre in ("grillas_para_predios.geojson", "grillas_candidatas.geojson"):
        g = gpd.read_file(REP / nombre)
        f = g[g.cell_id.astype(str).str.zfill(7) == CELDA]
        if not f.empty:
            cel = f.geometry.iloc[0]
            break
    lot = gpd.read_file(REP / "lotes_distribuida.geojson")
    lot = lot[lot.cell_id.astype(str).str.zfill(7) == CELDA]

    x0, y0, x1, y1 = cel.bounds
    w, h = x1 - x0, y1 - y0
    m = 0.06
    bbox = (x0 - w * m, y0 - h * m, x1 + w * m, y1 + h * m)
    img = plt.imread(str(satelital.bajar(f"{CELDA}_cat", bbox, px=1400)))

    fig, ax = plt.subplots(figsize=tam(7.4, 7.4))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(img, extent=(bbox[0], bbox[2], bbox[1], bbox[3]), zorder=1)
    lot.plot(ax=ax, color=MARCA, alpha=0.22, ec="none", zorder=2)
    lot.boundary.plot(ax=ax, color="white", linewidth=0.55, alpha=0.85, zorder=3)
    ax.add_patch(Rectangle((x0, y0), w, h, fc="none", ec="white", lw=1.8, zorder=4))

    ax.set_aspect(1.0 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.axis("off")
    guardar(fig, "fig_catastro_celda.pdf")


#: Los dos tipos de control del visor. Sin cifras a proposito: la lamina explica
#: QUIEN decide y de que naturaleza es cada decision, no con que valores, que son
#: cosa de cada proyecto y cambian en el momento.
GRADUA = ["Área del lote", "Ancho aprovechable", "Cobertura apta",
          "Distancia a la conexión", "Valor de referencia"]
EXIGE = [("Clasificación del POT", True), ("Título minero", True),
         ("Solicitud minera", False), ("Unidad Agrícola Familiar", True),
         ("Restitución de tierras", True)]


def filtro_cliente():
    """Los dos tipos de control con los que el cliente arma su lista corta.

    Una familia se gradua, porque admite mas o menos: superficie, ancho, cobertura,
    distancia, valor. La otra no admite grados, solo se exige o no se exige: lo que
    dice el POT, si hay titulo minero, si el lote cabe en la Unidad Agricola
    Familiar. Dibujarlas como mando de corredera y como interruptor dice esa
    diferencia sin una linea de texto.
    """
    from matplotlib.patches import FancyBboxPatch, Circle

    W, A = 13.4, 4.55
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    COL = [0.15, 7.05]
    ANCHO_COL = 6.15
    FILA, Y0 = 0.545, A - 0.92
    #: Posicion del mando en cada corredera. Son posiciones de dibujo, no datos.
    POS = [0.34, 0.52, 0.62, 0.44, 0.58]

    for x, rot in zip(COL, ("LO QUE SE GRADÚA", "LO QUE SE EXIGE")):
        ax.text(x, A - 0.30, rot, ha="left", va="center", fontsize=7.8, color=TINTA3)
    ax.text(COL[0] + ANCHO_COL, A - 0.30, "admite más o menos", ha="right",
            va="center", fontsize=7.6, color=TINTA3)
    # «se cumple o no se cumple» decia lo contrario de lo que hace el visor: un
    # lote sin dato en el criterio no se retira, porque la ausencia de dato no es
    # un incumplimiento. Son 468 de 1.107 lotes sin cartografia del POT.
    ax.text(COL[1] + ANCHO_COL, A - 0.30, "se pide o no se pide", ha="right",
            va="center", fontsize=7.6, color=TINTA3)

    # Columna izquierda: correderas.
    xa, xb = COL[0] + 3.95, COL[0] + ANCHO_COL
    for i, (et, q) in enumerate(zip(GRADUA, POS)):
        y = Y0 - i * FILA
        ax.text(COL[0], y, et, ha="left", va="center", fontsize=8.6, color=TINTA)
        ax.plot([xa, xb], [y, y], color=LINEA, lw=3.4, solid_capstyle="round", zorder=2)
        ax.plot([xa, xa + (xb - xa) * q], [y, y], color=MARCA, lw=3.4,
                solid_capstyle="round", zorder=3)
        ax.add_patch(Circle((xa + (xb - xa) * q, y), 0.088, fc="white", ec=ACENTO2,
                            lw=1.1, zorder=4))

    # Columna derecha: interruptores.
    xa, xb = COL[1] + 4.55, COL[1] + ANCHO_COL
    for i, (et, on) in enumerate(EXIGE):
        y = Y0 - i * FILA
        ax.text(COL[1], y, et, ha="left", va="center", fontsize=8.6, color=TINTA)
        ax.add_patch(FancyBboxPatch((xa, y - 0.105), xb - xa, 0.21,
                                    boxstyle="round,pad=0,rounding_size=0.105",
                                    fc=ACENTO if on else LINEA, ec="none", zorder=2))
        cx = xb - 0.105 if on else xa + 0.105
        ax.add_patch(Circle((cx, y), 0.082, fc="white", ec="none", zorder=3))

    # El resultado, al pie y en el ancho entero.
    yb = 0.40
    ax.add_patch(FancyBboxPatch((COL[0], yb - 0.26), W - 2 * COL[0], 0.52,
                                boxstyle="round,pad=0,rounding_size=0.07",
                                fc=ACENTOSUAVE, ec="none", zorder=2))
    ax.text(W / 2, yb, "La lista corta que dejan esas condiciones",
            ha="center", va="center", fontsize=9.2, color=ACENTO2,
            fontweight="bold", zorder=3)
    for x in (W * 0.28, W * 0.72):
        ax.annotate("", xy=(x, yb + 0.30), xytext=(x, yb + 0.66),
                    arrowprops=dict(arrowstyle="-|>", color=ACENTO, lw=1.0))

    guardar(fig, "fig_filtro_cliente.pdf")


#: El lote que el guion usa de ejemplo, en Sabana de Torres. Por codigo y no por
#: posicion: la lista se reordena cada vez que se vuelve a correr el reporte.
LOTE_EJEMPLO = "686550001000000050003000000000"


def lote_ejemplo():
    """El lote de la ficha, sobre su imagen satelital.

    La lamina que cuenta lo que dice la ficha era toda texto. Con el poligono
    dibujado sobre la foto, el lector ve de que esta hablando: un lote real, con
    su forma y su entorno, y no una fila de una tabla.
    """
    import geopandas as gpd
    sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte")]
    from insumos import satelital

    g = gpd.read_file(REP / "lotes_utility.geojson")
    lote = g[g.CODIGO.astype(str) == LOTE_EJEMPLO]
    x0, y0, x1, y1 = lote.geometry.total_bounds
    w, h = x1 - x0, y1 - y0
    lado = max(w, h) * 1.55
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bbox = (cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2)
    img = plt.imread(str(satelital.bajar("lote_ejemplo", bbox, px=1200)))

    fig, ax = plt.subplots(figsize=tam(6.6, 6.6))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(img, extent=(bbox[0], bbox[2], bbox[1], bbox[3]), zorder=1)
    lote.plot(ax=ax, color=MARCA, alpha=0.28, ec="none", zorder=2)
    lote.boundary.plot(ax=ax, color="white", linewidth=1.9, zorder=3)

    ax.set_aspect(1.0 / np.cos(np.radians(cy)))
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.axis("off")
    guardar(fig, "fig_lote_ejemplo.pdf")


#: Los cinco eslabones entre el codigo del catastro y el diagnostico juridico.
#: Una linea por caja y nada mas: la lamina es el grafico, no el texto.
CADENA_REGISTRO = [
    ("Código catastral", "Instituto Geográfico Agustín Codazzi", True),
    ("Matrícula inmobiliaria", "Superintendencia de Notariado y Registro", True),
    ("Certificado de tradición", "se compra en línea", True),
    ("Lectura automática", "once riesgos tipificados", True),
    ("Diagnóstico jurídico", "modelo de lenguaje", False),
]


def cadena_registro():
    """Del codigo del catastro al diagnostico juridico, eslabon a eslabon.

    Comparte trazado y contenido con la version comercial. Antes eran dos
    figuras distintas y decian cosas distintas del quinto eslabon: aqui iba con
    trazo discontinuo y el rotulo «en desarrollo» mientras la otra lo daba por
    terminado. Lo esta: la lectura del certificado con modelo de lenguaje se
    corrio sobre el folio 366-35594 del lote El Poblado y se midio el 2 de
    septiembre de 2026.
    """
    _cadena_cajas(CADENA_REGISTRO_COMERCIAL, "fig_cadena_registro.pdf",
                  "Todo entra en la ficha del lote", A=4.45,
                  marca="probado de punta a punta sobre un folio real")


#: Lo que cada lectura del certificado aporta. Los once primeros son los riesgos
#: tipificados que la lectura determinista reconoce por expresion regular; los de
#: la derecha son los que solo ve el modelo, y por eso existe el segundo paso.
DET = ["Falsa tradición", "Origen baldío", "Nunca salió de la Nación", "Restitución",
       "Extinción de dominio", "Proceso agrario", "Embargo", "Hipoteca",
       "Patrimonio de familia", "Usufructo", "Servidumbre"]
IA = ["Cadena de tradición", "Cuotas y proindiviso", "Sucesión sin liquidar",
      "Folio cerrado", "Cabida inconsistente", "Condición resolutoria",
      "Litigio civil", "Afectación ambiental", "Valores de las compraventas"]


def diagnostico():
    """Lo que ve la lectura automatica y lo que anade el modelo encima.

    La lectura determinista es la verdad de base: reconoce once riesgos tipificados
    y no inventa ninguno. El modelo la audita y aporta lo que una expresion regular
    no puede ver, que es casi todo lo que exige leer la historia del folio.
    """
    from matplotlib.patches import FancyBboxPatch

    # Once filas mas la cabecera no caben en 4,45: la ultima salia cortada.
    W, A = 13.4, 5.05
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    COLS = [(0.10, 6.35, "LECTURA AUTOMÁTICA", "once riesgos tipificados", DET,
             ACENTOSUAVE, ACENTO2, "solid"),
            (7.05, 13.30, "DIAGNÓSTICO DEL MODELO", "lo que la regla no ve", IA,
             "#FFFFFF", ACENTO, "dashed")]
    for xa, xb, rot, sub, items, fc, ec, tipo in COLS:
        # Solo el rotulo de columna: la aclaracion se encabalgaba con el y va
        # ahora en el subtitulo de la lamina, que es su sitio.
        ax.text(xa, A - 0.20, rot, ha="left", va="center", fontsize=8.0, color=TINTA3)
        y = A - 0.72
        for t in items:
            ax.add_patch(FancyBboxPatch((xa, y - 0.145), xb - xa, 0.29,
                         boxstyle="round,pad=0,rounding_size=0.09", fc=fc, ec=ec,
                         lw=0.8 if tipo == "dashed" else 0,
                         ls=(0, (2.2, 1.8)) if tipo == "dashed" else "solid"))
            ax.text(xa + 0.22, y, t, ha="left", va="center", fontsize=8.0,
                    color=ACENTO2 if tipo == "solid" else TINTA)
            y -= 0.375
    guardar(fig, "fig_diagnostico.pdf")


#: De donde sale cada dato de la ficha. La entidad que lo publica es lo que un
#: tercero puede verificar; el fichero donde el proyecto lo guarda no le sirve a
#: nadie. Comprobado contra outputs/PROCEDIMIENTO_LOTES.md, apartados 2.a a 2.d.
FUENTES_LOTE = [
    ("Catastro", "Instituto Geográfico Agustín Codazzi",
     "Polígono del lote, código y destino"),
    ("Relieve y cobertura", "Copernicus y Agencia Espacial Europea",
     "Pendiente, rugosidad y cobertura"),
    ("Entorno", "Nueve entidades del Estado",
     "Veinticinco capas: inundación, minería, resguardos"),
    ("Ordenamiento", "Instituto Geográfico Agustín Codazzi",
     "Categoría del suelo y acto que la adopta"),
    ("Registro", "Superintendencia de Notariado y Registro",
     "Matrícula inmobiliaria y certificado"),
]


def fuentes_lote():
    """De donde sale la informacion de cada lote y como converge en la ficha.

    Es la lamina que faltaba: el guion contaba que el lote se mide y se clasifica,
    pero no de donde sale cada dato. Cada familia se nombra por la ENTIDAD que la
    publica, que es lo verificable, y no por el modulo que la consulta.
    """
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    W, A = 13.4, 5.45
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    XB, ANCHO_B = 0.10, 8.75
    XF, ANCHO_F = 10.35, W - 10.45
    FILA, ALTO = 0.90, 0.76
    tonos = ["#DCEAEB", "#BCDCDF", "#9BCBD0", "#79B9C0", "#4FA5AC"]
    y = A - 0.62

    for k, (((rot, quien, que), tono)) in enumerate(zip(FUENTES_LOTE, tonos)):
        det = TINTA if k >= 2 else TINTA2
        ax.add_patch(FancyBboxPatch((XB, y - ALTO / 2), ANCHO_B, ALTO,
                     boxstyle="round,pad=0,rounding_size=0.07", fc=tono, ec="none"))
        ax.text(XB + 0.26, y + 0.185, rot, ha="left", va="center", fontsize=9.0,
                fontweight="bold", color=TINTA)
        ax.text(XB + ANCHO_B - 0.26, y + 0.185, quien, ha="right", va="center",
                fontsize=7.4, color=det)
        ax.text(XB + 0.26, y - 0.155, que, ha="left", va="center", fontsize=7.4,
                color=det)
        ax.add_patch(FancyArrowPatch((XB + ANCHO_B + 0.12, y),
                     (XF - 0.14, A / 2 + 0.10), arrowstyle="-|>", mutation_scale=7,
                     color=ACENTO, lw=0.8, shrinkA=0, shrinkB=0,
                     connectionstyle="arc3,rad=0.10"))
        y -= FILA

    ax.add_patch(FancyBboxPatch((XF, A / 2 - 1.05), ANCHO_F, 2.30,
                 boxstyle="round,pad=0,rounding_size=0.09", fc=ACENTOSUAVE,
                 ec=ACENTO, lw=0.9))
    ax.text(XF + ANCHO_F / 2, A / 2 + 0.62, "LA FICHA", ha="center", va="center",
            fontsize=8.0, color=ACENTO2)
    ax.text(XF + ANCHO_F / 2, A / 2 + 0.20, "del lote", ha="center", va="center",
            fontsize=12.5, fontweight="bold", color=ACENTO2)
    ax.text(XF + ANCHO_F / 2, A / 2 - 0.52,
            "Cada dato con la" + NL + "entidad que lo publica" + NL + "y su fecha de corte",
            ha="center", va="center", fontsize=7.8, color=TINTA2, linespacing=1.4)

    # Antes decia «no contra su centroide», y no es exacto: cuatro capas de clima
    # y suelo si se consultan en el centroide. El contraste verdadero, y el que
    # importa, es que el lote no hereda los datos de su grilla.
    ax.text(XB, 0.12, "Cada lote se mide sobre su propio polígono; no hereda los "
            "datos de su grilla.", ha="left", va="bottom", fontsize=8.6,
            color=TINTA, fontweight="bold")
    guardar(fig, "fig_fuentes_lote.pdf")


#: Las tres clases y ejemplos de las condiciones que llevan a cada una. Salen del
#: catalogo de once de predios/lotes.py, cinco y seis. Sin cifras de la corrida:
#: la lamina explica COMO se clasifica un lote, no que salio esta vez.
CLASES_LOTE = [
    ("Idóneo", "Ninguna condición adversa en las fuentes que respondieron", [], AZUL),
    ("Viable con gestión", "Hay trámite conocido que la resuelve",
     ["Unidad Agrícola Familiar", "Humedal en el lote", "Restitución de tierras",
      "Mancha de inundación", "Protección parcial"], AVISO),
    ("No viable", "Ninguna gestión del proyecto la levanta",
     ["Suelo de protección", "Título minero", "Área protegida",
      "Resguardo indígena", "Consejo comunitario", "Páramo delimitado"], MAL),
]


def clases_lote():
    """Como se clasifica un lote y de que depende esa clase.

    Sin recuentos: lo que hay que retener es el mecanismo y de que figuras
    depende, no cuantos lotes cayeron en cada clase en una corrida concreta.
    """
    from matplotlib.patches import FancyBboxPatch

    W, A = 13.4, 4.95
    #: La columna de chips arranca pasado el nombre de clase y se reparte en tres.
    #: Con 3,45 y 3,62 la tercera columna se salia del lienzo por 0,7 cm.
    XC = 3.62
    XCH = (W - XC) / 3
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    y = A - 0.55
    for nom, que, cond, col in CLASES_LOTE:
        ax.text(0.10, y, nom, ha="left", va="center", fontsize=10.6,
                fontweight="bold", color=col)
        if not cond:
            # Sin descripcion suelta bajo el nombre: era mas ancha que su columna
            # y se metia por debajo de los chips de la clase siguiente.
            ax.text(XC + 0.16, y, que, ha="left", va="center", fontsize=8.2,
                    color=TINTA2)
            y -= 0.92
            continue
        for k, t in enumerate(cond):
            cx = XC + (k % 3) * XCH
            cy = y + 0.25 - (k // 3) * 0.50
            ax.add_patch(FancyBboxPatch((cx, cy - 0.175), XCH - 0.22, 0.35,
                         boxstyle="round,pad=0,rounding_size=0.09",
                         fc="white", ec=col, lw=0.8))
            ax.text(cx + 0.16, cy, t, ha="left", va="center", fontsize=7.2,
                    color=col)
        y -= 1.52

    ax.plot([0.10, W], [0.66, 0.66], color=LINEA, lw=0.8)
    ax.text(0.10, 0.38, "Cada condición trae escrito el trámite que exige y la "
            "entidad ante la que se surte.", ha="left", va="center", fontsize=8.8,
            color=TINTA, fontweight="bold")
    ax.text(0.10, 0.09, "El índice de aptitud describe el terreno; no clasifica ni "
            "ordena la lista.", ha="left", va="center", fontsize=8.0, color=TINTA2)
    guardar(fig, "fig_clases_lote.pdf")


def catastro_clasificado():
    """La misma celda de la lamina anterior, ya con cada lote clasificado.

    Va al lado del catastro en blanco: primero se ve lo que baja del catastro y
    despues los mismos poligonos con el color que el reporte les asigna. Los tres
    colores son los del visor, y por eso se toman de la escala del proyecto y no
    se inventan aqui.
    """
    import geopandas as gpd
    from matplotlib.patches import Rectangle
    sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte")]
    from insumos import satelital

    CELDA = "0010961"
    cel = None
    for nombre in ("grillas_para_predios.geojson", "grillas_candidatas.geojson"):
        g = gpd.read_file(REP / nombre)
        f = g[g.cell_id.astype(str).str.zfill(7) == CELDA]
        if not f.empty:
            cel = f.geometry.iloc[0]
            break
    lot = gpd.read_file(REP / "lotes_distribuida.geojson")
    lot = lot[lot.cell_id.astype(str).str.zfill(7) == CELDA]

    x0, y0, x1, y1 = cel.bounds
    w, h = x1 - x0, y1 - y0
    m = 0.06
    bbox = (x0 - w * m, y0 - h * m, x1 + w * m, y1 + h * m)
    img = plt.imread(str(satelital.bajar(f"{CELDA}_cat", bbox, px=1400)))

    fig, ax = plt.subplots(figsize=tam(7.4, 7.4))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(img, extent=(bbox[0], bbox[2], bbox[1], bbox[3]), zorder=1)
    for nom, col in (("Idóneo", AZUL), ("Viable con gestión", AVISO),
                     ("No viable", MAL)):
        sub = lot[lot.clasificacion == nom]
        if sub.empty:
            continue
        sub.plot(ax=ax, color=col, alpha=0.46, ec="none", zorder=2)
        sub.boundary.plot(ax=ax, color="white", linewidth=0.45, alpha=0.9, zorder=3)
    ax.add_patch(Rectangle((x0, y0), w, h, fc="none", ec="white", lw=1.8, zorder=4))

    ax.set_aspect(1.0 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.axis("off")
    guardar(fig, "fig_catastro_clasificado.pdf")


#: Las nueve secciones de la ficha, en el orden impreso. Comprobado contra los
#: Las nueve secciones de la ficha, en el orden impreso. Comprobado contra los
#: encabezados de la funcion fichaTecnica de reporte/plantilla.py.
SECCIONES_FICHA = ["Situación", "Cómo se ve", "Criterios de aptitud",
                   "Potencial estimado", "Qué hay en el suelo", "Recurso solar",
                   "Entorno socioeconómico", "Conexión", "Restricciones"]

CAP = RAIZ / "outputs" / "presentacion_sb" / "capturas"


def _captura(ax, nombre, x, cima, ancho, borde=True, recorte=None):
    """Coloca una captura por su esquina superior izquierda; devuelve su alto.

    `recorte` es la fraccion de alto que se conserva, contada desde arriba. Sirve
    para dejar fuera el trozo de la seccion siguiente que la captura arrastra:
    a tamano de miniatura no se ve, pero ampliada se lee como un corte a media
    letra.
    """
    from matplotlib.patches import FancyBboxPatch
    im = plt.imread(str(CAP / nombre))
    if recorte:
        im = im[:int(im.shape[0] * recorte)]
    alto = ancho * im.shape[0] / im.shape[1]
    ax.add_patch(FancyBboxPatch((x + 0.04, cima - alto - 0.04), ancho, alto,
                 boxstyle="round,pad=0,rounding_size=0.03", fc="#E4E8E9", ec="none",
                 zorder=1))
    ax.imshow(im, extent=(x, x + ancho, cima - alto, cima), aspect="auto", zorder=2)
    if borde:
        ax.add_patch(FancyBboxPatch((x, cima - alto), ancho, alto,
                     boxstyle="round,pad=0,rounding_size=0.03", fc="none", ec=LINEA,
                     lw=0.8, zorder=3))
    return alto


def ficha_grilla():
    """La ficha de grilla: la hoja como objeto y sus dos piezas graficas grandes.

    El cuerpo de la ficha son 11 px sobre una pagina de 900. Para que ese texto
    pase de los 7 pt del sistema hace falta ensenar una columna de 410 px a nueve
    centimetros o mas, de modo que en una lamina apaisada no cabe la hoja entera
    legible. Por eso esta lamina se queda con lo que SI escala bien, que son las
    dos piezas graficas, y la tabla de criterios pasa a la lamina siguiente.
    """
    W, A = 13.4, 5.75
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    XH, ANCHO_H = 0.12, 2.15
    cima = A - 0.40
    ax.text(XH, A - 0.18, "LA PÁGINA", ha="left", va="center", fontsize=7.4,
            color=TINTA3)
    alto_h = _captura(ax, "ficha_grilla_real.png", XH, cima, ANCHO_H)
    ax.text(XH, cima - alto_h - 0.22, "una por celda", ha="left", va="center",
            fontsize=7.4, color=TINTA3)

    # Las dos piezas graficas, a la misma altura y lo mas grandes que caben.
    XD = 2.68
    libre = W - XD - 0.12
    hueco = 0.34
    #: Proporciones medidas de los recortes: situacion 1,72 y satelital 0,94.
    alto = (libre - hueco) / (1.72 + 0.94)
    ax.text(XD, A - 0.18, "DÓNDE ESTÁ", ha="left", va="center", fontsize=7.4,
            color=TINTA3)
    a1 = _captura(ax, "f_situacion.png", XD, cima, 1.72 * alto)
    x2 = XD + 1.72 * alto + hueco
    ax.text(x2, A - 0.18, "CÓMO SE VE", ha="left", va="center", fontsize=7.4,
            color=TINTA3)
    a2 = _captura(ax, "f_satelital.png", x2, cima, 0.94 * alto)

    pie = cima - max(a1, a2) - 0.24
    ax.text(XD, pie, "el departamento, el municipio y la vereda", ha="left",
            va="center", fontsize=7.8, color=TINTA2)
    ax.text(x2, pie, "la celda sobre imagen satelital", ha="left", va="center",
            fontsize=7.8, color=TINTA2)
    guardar(fig, "fig_ficha_grilla.pdf")


#: Las secciones de la ficha imprimible de la CELDA, en su orden. No confundir
#: con SECCIONES_FICHA, que son las del lote: esta figura habla de la hoja de la
#: celda y estaba tomando la lista del lote, que ademas pasó a ser de tuplas y
#: habria salido con el parentesis y las comillas impresos en cada chip.
#: Comprobadas contra outputs/presentacion_sb/capturas/ficha_grilla_real.png.
SECCIONES_FICHA_GRILLA = [
    "Situación", "Cómo se ve", "Criterios de aptitud",
    "Potencial estimado", "Qué hay en el suelo", "Recurso solar",
    "Entorno socioeconómico", "Conexión", "Restricciones",
]


def ficha_criterios_grilla():
    """La tabla de criterios de la ficha, ampliada hasta que se lee.

    Tres filas de las siete: es lo que cabe manteniendo el cuerpo por encima de
    los 7 pt. Debajo, el resto de secciones que la hoja trae, para que se sepa
    que la ficha no termina en la tabla.
    """
    from matplotlib.patches import FancyBboxPatch

    W, A = 13.4, 5.95
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    ANCHO = 11.6
    x = (W - ANCHO) / 2
    alto = _captura(ax, "f_criterios3.png", x, A - 0.12, ANCHO)

    y = A - 0.12 - alto - 0.62
    ax.text(x, y + 0.44, "Y la hoja sigue con", ha="left", va="center",
            fontsize=7.8, color=TINTA3)
    ancho_ch = ANCHO / 3
    for k, t in enumerate(SECCIONES_FICHA_GRILLA[3:]):
        cx = x + (k % 3) * ancho_ch
        cy = y - (k // 3) * 0.50
        ax.add_patch(FancyBboxPatch((cx, cy - 0.19), ancho_ch - 0.18, 0.38,
                     boxstyle="round,pad=0,rounding_size=0.10", fc=ACENTOSUAVE,
                     ec="none"))
        ax.text(cx + (ancho_ch - 0.18) / 2, cy, t, ha="center", va="center",
                fontsize=8.0, color=ACENTO2)
    guardar(fig, "fig_ficha_criterios_grilla.pdf")


#: Los cuatro tramos del uso del modelo de lenguaje sobre el certificado, con lo
#: que garantiza cada uno. Comprobado contra predios/prompt_certificado.py.
FLUJO_IA = [
    ("Entra el certificado", "el folio comprado, tal como lo devuelve la Ventanilla "
     "Única, con su marca de agua y sus tildes corrompidas"),
    ("Lectura por regla", "once riesgos tipificados según la Resolución 7448 de 2021. "
     "Es la verdad de base y no la fija el modelo"),
    ("Lectura del modelo", "recibe el folio y la lectura anterior, y responde sobre un "
     "catálogo cerrado de veinte claves de riesgo"),
    ("Contraste", "lo que coincide confirma; lo que el modelo añade queda marcado como "
     "aporte suyo y se anexa a la ficha"),
]


def flujo_ia():
    """Como se usa el modelo de lenguaje sobre el certificado de tradicion.

    La lamina existe para responder la pregunta que un jefe hace primero: si se
    esta confiando en una IA. La respuesta es que no sustituye a nada, audita una
    lectura determinista que sigue siendo la verdad de base, y responde sobre un
    catalogo cerrado, de modo que no puede inventar categorias de riesgo.
    """
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    W, A = 13.4, 5.15
    n = len(FLUJO_IA)
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    XN, XT = 0.55, 4.45
    FILA, y = 1.02, A - 0.85
    tonos = [ACENTOSUAVE, "#B0D4D8", "#3E9BA3", ACENTOSUAVE]
    for i, ((tit, que), tono) in enumerate(zip(FLUJO_IA, tonos)):
        ax.add_patch(FancyBboxPatch((0.10, y - 0.30), XT - 0.42, 0.60,
                     boxstyle="round,pad=0,rounding_size=0.08", fc=tono, ec="none"))
        ax.add_patch(FancyBboxPatch((0.10, y - 0.30), 0.30, 0.60,
                     boxstyle="round,pad=0,rounding_size=0.08", fc=ACENTO2, ec="none"))
        ax.text(0.25, y, str(i + 1), ha="center", va="center", fontsize=9.0,
                color="white", fontweight="bold")
        ax.text(XN, y, tit, ha="left", va="center", fontsize=9.2,
                fontweight="bold", color="white" if i == 2 else TINTA)
        ax.text(XT, y, textwrap.fill(que, 62), ha="left", va="center", fontsize=8.0,
                color=TINTA2, linespacing=1.45)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((0.25, y - 0.34), (0.25, y - FILA + 0.34),
                         arrowstyle="-|>", mutation_scale=8, color=ACENTO, lw=1.0,
                         shrinkA=0, shrinkB=0))
        y -= FILA

    ax.plot([0.10, W], [0.62, 0.62], color=LINEA, lw=0.8)
    ax.text(0.10, 0.34, "El modelo no decide la clase del lote ni sustituye la lectura "
            "por regla: la audita.", ha="left", va="center", fontsize=8.8,
            fontweight="bold", color=TINTA)
    ax.text(0.10, 0.06, "Su salida va etiquetada como tal, para que se pueda contrastar "
            "con el folio.", ha="left", va="center", fontsize=8.0, color=TINTA2)
    guardar(fig, "fig_flujo_ia.pdf")


def mapa_portada():
    """La red electrica del pais: lineas de transmision y subestaciones.

    Es la imagen de portada. Antes llevaba los cien puntos de las candidatas, que
    son un resultado del procedimiento y no lo que la portada tiene que decir. La
    red si lo dice: el trabajo entero consiste en buscar terreno donde esa red
    llega. Sin leyenda ni rotulos, por lo mismo.
    """
    co = _colombia()
    lin, sub = _red(co)
    fig, ax = plt.subplots(figsize=tam(5.6, 8.60))
    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    co.plot(ax=ax, color="#F4F7F7", zorder=1)
    co.boundary.plot(ax=ax, color="#CFD8D8", linewidth=0.6, zorder=2)
    for lo, hi, col, lw, z in NIVELES:
        t = lin[(lin.kv >= lo) & (lin.kv < hi)]
        if not t.empty:
            t.plot(ax=ax, color=col, linewidth=lw, zorder=z)
    # Las subestaciones van encima de la linea y con filo blanco: sin el, sobre el
    # trazo troncal el punto se empasta y la red parece un solo garabato.
    ax.scatter(sub.geometry.x, sub.geometry.y, s=3.4, color=ACENTO2, zorder=6,
               edgecolor="white", linewidth=0.28)
    ax.set_aspect("equal")
    ax.set_xlim(-79.6, -66.5); ax.set_ylim(-4.6, 13.2)
    ax.axis("off")
    guardar(fig, "fig_mapa_portada.pdf")


# ============================================================== 14. EL PILOTO
def _piloto():
    """El lote de El Poblado, leido del propio entregable.

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
    # Por CODIGO y no por posicion: al volver a correr el piloto, El Poblado paso
    # de la fila 13 a la 14 y la figura se llevo el lote equivocado, con un indice
    # de 51 debajo de una lamina que afirma 30.
    POBLADO = "734490001000000010054000000000"
    lote = [x for x in D["lotes"]["utility"] if str(x["CODIGO"]) == POBLADO][0]
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
    # El techo baja de -0,55 a -1,15: la segunda linea de la cabecera, «(0)»,
    # «(70)» y «(100)», caia sobre el filete y sobre la primera fila.
    ax.set_xlim(0, 1); ax.set_ylim(-1.15, len(filas) + 1.95); ax.axis("off")
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

    FS_CRIT, FS_VAL, FS_UMB, FS_CAB, FS_NOTA = 9.8, 9.8, 8.8, 8.2, 9.8
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

    ax.text(0.0, 0.10, "CRITERIO", ha="left", va="center", fontsize=FS_CAB,
            color=TINTA3)
    ax.text(X["val"], 0.10, "EN EL LOTE", ha="right", va="center",
            fontsize=FS_CAB, color=TINTA3)
    for k, cab, _v, _f, _b in cols:
        ax.text(X[k], 0.10, cab, ha="right", va="center", fontsize=FS_CAB,
                color=TINTA3, linespacing=1.45, multialignment="right")
    ax.plot([0, 1], [1.12, 1.12], color=TINTA2, lw=1.1)

    for i, (et, uni, v, dec, lim, bue, top, nt, pes) in enumerate(filas):
        y = i + 1.78
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

    ax.text(0.0, len(filas) + 1.78, pie, ha="left", va="center", fontsize=9.4,
            color=TINTA2)
    guardar(fig, nombre)
    return filas


def piloto_criterios():
    """Los siete criterios de El Poblado, el lote del piloto.

    Lienzo mas bajo que el de la ficha porque su lamina lleva ademas los dos
    bloques de texto del veredicto: el hueco es de 3,9 cm y no de 4,2.

    Los umbrales se componen igual que en ficha_criterios: sobre las definiciones
    de escala de grilla se pega el override de escala de lote. La tabla imprimia
    los de grilla, de modo que las notas dibujadas daban un indice de 40,3 bajo un
    pie que declaraba 29,9. Se veia sin calculadora: dos filas en rojo bajo un pie
    que afirmaba tres.
    """
    sys.path.insert(0, str(RAIZ))
    from reporte import datos as rg

    D, celda, lote = _piloto()
    CR = {k: {**v, **D["umbrales"]["utility"].get(k, {}),
              "etiqueta": rg.CRITERIOS.get(k, v).get("etiqueta", v["etiqueta"])}
          for k, v in D["criterios"].items()}
    val = {k: (float(celda["capacidad_at_mw"]) if k == "capacidad"
               else float(celda["pvout"]) if k == "recurso"
               else float(lote[col]))
           for k, col, _ in CR_PILOTO}
    # Contado sobre las mismas notas que se dibujan y no escrito a mano, que es la
    # forma exacta en que este defecto aparecio.
    bajo = sum(1 for k, _c, _d in CR_PILOTO if _nota(CR[k], val[k]) <= 0.0)
    pie = (f"Índice del lote {es(lote['indice_lote'])} sobre 100 · "
           f"{lote['criterios_cumplidos']} criterio cumplido de "
           f"{lote['criterios_evaluados']} · {bajo} criterios por debajo de su límite")
    _tabla_criterios(CR, val, pie, "fig_piloto_criterios.pdf", alto=3.9)


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


def grilla_ancha():
    """La celda focal dentro de una ventana de siete por tres.

    Misma composicion que grilla_contexto(), otra ventana: la cuadrada la limita
    el alto de la lamina y sale a un tercio del ancho. Esta llena la diapositiva.
    """
    import geopandas as gpd
    from matplotlib.patches import Rectangle
    sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte")]
    from insumos import satelital

    g = gpd.read_file(REP / "grillas_candidatas.geojson")
    cel = g[g.cell_id.astype(str).str.zfill(7) == "0008656"].geometry.iloc[0]
    x0, y0, x1, y1 = cel.bounds
    w, h = x1 - x0, y1 - y0
    bbox = (x0 - 3 * w, y0 - h, x1 + 3 * w, y1 + h)
    img = plt.imread(str(satelital.bajar("0008656_ancho", bbox, px=2400)))

    W = 13.6
    A = W * (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(img, extent=(bbox[0], bbox[2], bbox[1], bbox[3]), zorder=1)

    for k in range(-3, 5):
        ax.plot([x0 + k * w] * 2, [bbox[1], bbox[3]], color="white", lw=0.7,
                alpha=0.45, zorder=2)
    for k in (-1, 0, 1, 2):
        ax.plot([bbox[0], bbox[2]], [y0 + k * h] * 2, color="white", lw=0.7,
                alpha=0.45, zorder=2)

    # Todo lo que no es la celda focal se atenua. No se oculta: la gracia de la
    # lamina es justamente ver que hay alrededor.
    for xa, ya, xb, yb in ((bbox[0], y1, bbox[2], bbox[3]),
                           (bbox[0], bbox[1], bbox[2], y0),
                           (bbox[0], y0, x0, y1), (x1, y0, bbox[2], y1)):
        ax.add_patch(Rectangle((xa, ya), xb - xa, yb - ya, fc="black",
                               alpha=0.34, ec="none", zorder=3))

    ax.add_patch(Rectangle((x0, y0), w, h, fc="none", ec="white", lw=2.0, zorder=4))
    ax.plot([x0, x1], [y0 - h * 0.055] * 2, color="white", lw=1.6, zorder=4,
            solid_capstyle="butt")
    ax.text((x0 + x1) / 2, y0 - h * 0.135, "5 km", ha="center", va="top",
            fontsize=9, color="white", fontweight="bold", zorder=4)
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.axis("off")
    guardar(fig, "fig_grilla_ancha.pdf")


# ====================================================== FIGURAS DE LA COMERCIAL
#: Los cuatro tramos del procedimiento tal como los ve un cliente. La version
#: tecnica los cuenta en seis pasos porque le importa que artefacto viaja entre
#: uno y otro; aqui los tres primeros son una sola cosa, «el modelo elige donde
#: mirar», y lo que hay que retener es que cada tramo entrega algo.
CADENA_COMERCIAL = [
    ("El modelo", "elige las celdas más aptas del país"),
    ("Selección de celdas", "se califican y el cliente escoge"),
    ("Selección de lotes", "catastro, medición y criba"),
    ("Ficha por lote", "toda la información en una página"),
]

#: Los siete criterios con que se califica una celda, uno por tarjeta, con el
#: grupo al que pertenece y lo que decide. El nombre y el motivo salen tal cual
#: de CRITERIOS en reporte/datos.py; los umbrales y los pesos no vienen, que son
#: cosa de la version tecnica.
#:
#: Estaban agrupados en cuatro columnas de 1, 3, 2 y 1 elementos, y asi los siete
#: criterios no se leian: la lamina parecia decir que el terreno pesa el triple
#: que el recurso. Uno por tarjeta y todas del mismo tamano, el peso visual deja
#: de mentir y el grupo pasa a ser el color y el rotulo.
#:
#: «Cobertura del suelo», y no «Cobertura apta del suelo», que es como se rotula
#: el criterio en el reporte de celdas. El agregado sigue existiendo alli, de modo
#: que la lamina no seria falsa, pero el cliente no lo va a encontrar en el
#: reporte de lotes: alli la cobertura se retiro como indice el 26 de agosto y hoy
#: se reporta clase a clase con las cifras crudas de la capa. El nombre corto es
#: cierto en los dos sitios, y la lamina lo aclara en su nota al pie.
#: Lo que decide cada criterio es su campo `por_que` de reporte/datos.py, abreviado
#: donde la tarjeta no daba y sin cambiar lo que dice: se cae la subordinada, no la
#: afirmacion. Las dos que se recortan son «...no hay proyecto POR BUENO QUE SEA EL
#: TERRENO» y «define el costo de conexion, QUE suele decidir la viabilidad
#: ECONOMICA».
CRITERIOS_CELDA = [
    ("El recurso", "Producción fotovoltaica",
     "define los ingresos por megavatio instalado"),
    ("El terreno", "Pendiente media",
     "define el movimiento de tierras y el tipo de estructura"),
    ("El terreno", "Rugosidad del relieve",
     "una pendiente media baja puede esconder terreno ondulado"),
    ("El terreno", "Cobertura del suelo",
     "lo que hay en el suelo condiciona el costo de habilitarlo"),
    ("La conexión", "Capacidad libre en la barra",
     "si la barra no tiene cupo, no hay proyecto"),
    ("La conexión", "Distancia al punto de conexión",
     "el costo de conexión suele decidir la viabilidad"),
    ("El acceso", "Distancia a vía carrozable",
     "condiciona el acceso de equipos pesados en la obra"),
]

#: Tono de fondo de cada grupo de criterios, de claro a oscuro. Es la misma rampa
#: de las cadenas, para que las dos familias de lamina se lean como un sistema.
TONO_GRUPO = {"El recurso": "#DCEAEB", "El terreno": "#C3DFE2",
              "La conexión": "#8FC4C9", "El acceso": "#4FA3AA"}


# ============================================== CAJAS QUE NO SE PUEDEN DESBORDAR
#
# El defecto que el cliente senala una y otra vez es texto que se sale de su
# cuadro. Pasa porque el texto se coloca a ojo: se cuentan caracteres para
# envolverlo y se suman alturas de renglon teoricas para apilarlo. matplotlib no
# avisa de nada, dibuja fuera de la caja sin error y el fallo solo se ve cuando
# ya esta proyectado.
#
# Aqui el texto se MIDE con el mismo renderizador que compone el PDF, y el cuerpo
# se reduce hasta que la pila entra en su rectangulo. Si no entra ni al cuerpo
# minimo del sistema, la figura no se genera: revienta con el nombre del texto que
# sobra, que es mejor que entregar una lamina desbordada.

#: Cuerpo minimo del sistema, el del pie de lamina. Por debajo no se compone nada.
CUERPO_MINIMO = 7.0


def _renderizador(fig):
    """El renderizador con el que se miden los textos. Uno por figura."""
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _medida(ax, ren, texto, **kw):
    """Ancho y alto del texto en unidades del lienzo, que son centimetros.

    El texto se pone y se quita: se mide el objeto real, con su tipografia, su
    cuerpo y su interlineado, no una estimacion.
    """
    art = ax.text(0, 0, texto, **kw)
    caja = art.get_window_extent(ren).transformed(ax.transData.inverted())
    art.remove()
    return abs(caja.width), abs(caja.height)


def _ajustar_ancho(ax, ren, texto, ancho, **kw):
    """El texto envuelto al mayor numero de columnas que cabe en `ancho` cm.

    Sin partir palabras, que es regla del sistema: con break_long_words puesto,
    «Superintendencia» salia como «Superintendenci / a» en la cadena del folio.
    Si la palabra mas larga no cabe, se devuelve igualmente y el ancho medido
    sale por encima del disponible, para que quien llama encoja el cuerpo.
    """
    if not texto:
        return "", 0.0, 0.0
    # Se arranca de una estimacion por ancho medio de caracter y se baja: sin la
    # estimacion habria que medir sesenta veces por rotulo.
    car = _medida(ax, ren, "n" * 20, **kw)[0] / 20 or 0.1
    cols = min(len(texto), max(4, int(ancho / car) + 4))
    envolver = lambda c: textwrap.fill(texto, c, break_long_words=False,
                                       break_on_hyphens=False)
    while cols > 3:
        t = envolver(cols)
        w, h = _medida(ax, ren, t, **kw)
        if w <= ancho:
            return t, h, w
        cols -= 1
    t = envolver(4)
    w, h = _medida(ax, ren, t, **kw)
    return t, h, w


def _pila_en_caja(ax, ren, x, y, w, h, piezas, pad_x=0.16, pad_y=0.16,
                  sep=0.11, cima=None, donde="arriba"):
    """Escribe una pila de textos DENTRO del rectangulo (x, y, w, h), en cm.

    `piezas` es una lista de (texto, cuerpo_pt, kwargs de ax.text). Se envuelve
    cada texto al ancho util y, si la pila no entra de alto, se reduce el cuerpo
    de todas por igual en pasos del 3 % hasta que entra. `cima` limita el borde
    superior util, para dejar sitio al numeral de la caja.

    Devuelve el alto ocupado. Si a CUERPO_MINIMO la pila sigue sin caber, falla.
    """
    tope = (y + h if cima is None else cima) - pad_y
    suelo = y + pad_y
    ancho = w - 2 * pad_x
    mayor = max(cuerpo for _, cuerpo, _ in piezas)
    escala = 1.0
    while True:
        compuesto, alto, ancho_max = [], 0.0, 0.0
        for k, (texto, cuerpo, kw) in enumerate(piezas):
            if not texto:
                continue
            # Suelo por pieza: un rotulo que ya esta en el cuerpo minimo no
            # encoge mas, y no por eso hay que dar la caja por imposible.
            c = max(cuerpo * escala, CUERPO_MINIMO)
            t, ht, wt = _ajustar_ancho(ax, ren, texto, ancho, fontsize=c, **kw)
            compuesto.append((t, c, ht, kw))
            alto += ht + (sep if k else 0.0)
            ancho_max = max(ancho_max, wt)
        # Las dos condiciones: la pila entra de alto y ninguna linea sobresale de
        # ancho. La segunda es la que atrapa la palabra larga que no se parte.
        if alto <= tope - suelo and ancho_max <= ancho + 0.01:
            break
        if mayor * escala <= CUERPO_MINIMO:
            raise ValueError(
                f"no cabe en la caja ni a {CUERPO_MINIMO} pt: "
                f"{piezas[0][0][:40]!r} necesita {alto:.2f} x {ancho_max:.2f} cm "
                f"de {tope - suelo:.2f} x {ancho:.2f} cm")
        escala -= 0.03

    yy = tope if donde == "arriba" else suelo + (tope - suelo + alto) / 2
    for k, (t, c, ht, kw) in enumerate(compuesto):
        if k:
            yy -= sep
        # La alineacion horizontal decide la abscisa: a la izquierda el texto
        # arranca en el margen interior, centrado va al eje de la caja.
        ha = kw.get("ha", "left")
        xx = x + w / 2 if ha == "center" else (
            x + w - pad_x if ha == "right" else x + pad_x)
        ax.text(xx, yy, t, va="top", fontsize=c, **{**kw, "ha": ha})
        yy -= ht
    return alto


def _cadena_cajas(entradas, nombre, cierre, W=13.6, A=4.05, marca=None):
    """Dibuja una fila de cajas encadenadas con su banda de cierre.

    Es el trazado de cadena_registro(), sacado aparte para que la cadena de la
    celda y la del folio se vean como lo que son, el mismo procedimiento a dos
    escalas, y para que una correccion de forma alcance a las dos.

    El texto ya no se coloca contando caracteres y sumando alturas de renglon
    teoricas, que es lo que hacia que en la lamina del folio «Instituto
    Geografico Agustin Codazzi» y «Superintendencia de Notariado y Registro»
    salieran por debajo de su caja. Ahora cada bloque se compone con
    _pila_en_caja(), que lo mide y lo encoge hasta que entra.
    """
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    n = len(entradas)
    hueco = 0.30
    w = (W - (n - 1) * hueco) / n

    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    ren = _renderizador(fig)

    y0, alto = 1.05, A - 1.63
    rampa = ["#DCEAEB", "#B0D4D8", "#6FB4BA", "#2E8B93", "#0F5E65"]
    tonos = [rampa[round(i * (len(rampa) - 1) / max(n - 1, 1))] for i in range(n)]
    for i, (entrada, tono) in enumerate(zip(entradas, tonos)):
        tit, des = entrada[0], entrada[1]
        listo = entrada[2] if len(entrada) > 2 else True
        x = i * (w + hueco)
        ax.add_patch(FancyBboxPatch((x, y0), w, alto,
                     boxstyle="round,pad=0.012,rounding_size=0.07",
                     fc=tono if listo else "#FFFFFF",
                     ec=ACENTO if not listo else "none",
                     ls=(0, (2.4, 1.8)) if not listo else "solid",
                     lw=1.0 if not listo else 0))
        # El texto pasa a blanco donde el fondo ya es oscuro.
        oscuro = listo and tono in ("#2E8B93", "#0F5E65")
        tc = "white" if oscuro else TINTA
        sc = "white" if oscuro else (TINTA if tono == "#6FB4BA" else TINTA2)
        cima = y0 + alto
        ax.text(x + w / 2, cima - 0.34, str(i + 1), ha="center", va="center",
                fontsize=8.0, color=sc, alpha=0.75)
        _pila_en_caja(ax, ren, x, y0, w, alto,
                      [(tit, 8.6, dict(fontweight="bold", color=tc,
                                       linespacing=1.28, ha="center")),
                       (des, 7.6, dict(color=sc, linespacing=1.32, ha="center"))],
                      pad_x=0.18, pad_y=0.16, sep=0.16,
                      cima=cima - 0.58, donde="centro")

        if i < n - 1:
            xa = x + w + 0.045
            ax.add_patch(FancyArrowPatch((xa, y0 + alto / 2),
                         (xa + hueco - 0.09, y0 + alto / 2), arrowstyle="-|>",
                         mutation_scale=8, color=ACENTO, lw=1.0, shrinkA=0,
                         shrinkB=0))

    ax.annotate("", xy=(W / 2, 0.62), xytext=(W / 2, y0 - 0.06),
                arrowprops=dict(arrowstyle="-|>", color=ACENTO, lw=1.1))
    # La banda de cierre se dimensiona por el texto medido y no por una fraccion
    # del ancho escrita a mano: con la fraccion fija, la frase de la cadena
    # comercial sobresalia por los dos lados de su propio fondo.
    ancho_cierre = _medida(ax, ren, cierre, fontsize=9.0, fontweight="bold")[0]
    banda = min(ancho_cierre + 0.70, W)
    ax.add_patch(FancyBboxPatch(((W - banda) / 2, 0.10), banda, 0.50,
                 boxstyle="round,pad=0,rounding_size=0.07", fc=ACENTOSUAVE,
                 ec="none"))
    ax.text(W / 2, 0.35, cierre, ha="center", va="center", fontsize=9.0,
            fontweight="bold", color=ACENTO2)
    if marca:
        ax.text(W, A - 0.10, marca, ha="right", va="top", fontsize=7.4,
                color=ACENTO)
    guardar(fig, nombre)


def cadena_comercial():
    """Los cuatro tramos del procedimiento, para el guion comercial."""
    _cadena_cajas(CADENA_COMERCIAL, "fig_cadena_comercial.pdf",
                  "Una lista corta de lotes, con el motivo de cada descarte escrito",
                  A=4.30)


#: La cadena del registro para el guion comercial. Es la misma de la version
#: tecnica salvo en el quinto eslabon, que alli sigue marcado como en desarrollo
#: y aqui ya no: el 2 de septiembre de 2026 el camino esta cerrado de punta a
#: punta y probado sobre un folio real, el 366-35594 del lote El Poblado en
#: Melgar. Por eso es una constante aparte y no una edicion de CADENA_REGISTRO:
#: la figura de la version tecnica no se toca en este encargo.
#:
#: Cifras comprobadas contra outputs/COSTO_IA_CERTIFICADOS.md (modelo, costo y
#: reutilizacion) y contra predios/certificados.py, cuya lista RIESGOS sigue
#: teniendo once entradas.
CADENA_REGISTRO_COMERCIAL = [
    ("Código catastral", "Instituto Geográfico Agustín Codazzi"),
    ("Matrícula inmobiliaria", "Superintendencia de Notariado y Registro"),
    ("Certificado de tradición", "se compra en línea, 23.000 pesos"),
    ("Lectura automática", "once riesgos tipificados"),
    ("Diagnóstico jurídico", "Gemini 2.5 Flash en Vertex AI"),
]


def cadena_registro_comercial():
    """Del codigo del catastro al certificado leido, ya terminado.

    La version de esta cadena que usa el guion tecnico lleva el quinto eslabon
    con trazo discontinuo y el rotulo «en desarrollo». Aqui va entero y solido, y
    el rotulo dice sobre que se probo, que es lo que hace la diferencia entre
    prometer y demostrar.
    """
    _cadena_cajas(CADENA_REGISTRO_COMERCIAL, "fig_cadena_registro_comercial.pdf",
                  "Todo entra en la ficha del lote", A=4.45,
                  marca="probado de punta a punta sobre un folio real")


def ficha_celda_comercial():
    """Las dos piezas graficas de la ficha de la celda, en grande.

    La version anterior de esta lamina metia tres capturas: la hoja entera a
    2,15 cm de ancho, la situacion y la satelital. La hoja entera a ese tamano no
    se lee, no se puede leer y no aporta nada, mientras se comia una quinta parte
    del ancho. Fuera esa, las otras dos crecen de 5,8 y 3,2 cm a 8,4 y 4,6 cm en
    la lamina, que es lo que se pedia.

    No se puede hacer mas: la tabla de los siete criterios necesita once
    centimetros de ancho para que su cuerpo llegue a 7 pt, y con ese ancho pide
    nueve de alto, que la lamina apaisada no tiene. Va en la lamina anterior, ya
    compuesta como texto de la presentacion.
    """
    W, A = 13.6, 5.15
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")

    #: Proporciones medidas de los dos recortes: situacion 1,72 y satelital 0,94.
    #: Juntas dan una proporcion de 2,66, por debajo de la del hueco de la lamina
    #: (14 por 5,4), de modo que aqui manda SIEMPRE la altura: cada centimetro que
    #: se le quite al pie es un centimetro mas de imagen. Por eso el rotulo de
    #: cabecera y la identidad de la celda salieron de la figura y bajaron a la
    #: nota al pie de la lamina, que no compite por este alto.
    #: La captura de la satelital arrastra el arranque de la seccion siguiente,
    #: cortado a media letra. A 3 cm no se veia; a 4,5 se lee. Se queda en el
    #: 93,1 % de su alto, que es donde acaba la imagen y su credito.
    RECORTE_SAT = 0.931
    PROP_SIT, PROP_SAT = 1.72, 0.94 / RECORTE_SAT
    PIE = 0.50
    cima = A - 0.05
    hueco = 0.36
    alto = min(cima - PIE, (W - hueco) / (PROP_SIT + PROP_SAT))
    ancho = alto * (PROP_SIT + PROP_SAT) + hueco
    x1 = (W - ancho) / 2
    a1 = _captura(ax, "f_situacion.png", x1, cima, PROP_SIT * alto)
    x2 = x1 + PROP_SIT * alto + hueco
    a2 = _captura(ax, "f_satelital.png", x2, cima, PROP_SAT * alto,
                  recorte=RECORTE_SAT)

    pie = cima - max(a1, a2) - 0.22
    ax.text(x1, pie, "el departamento, el municipio y la vereda", ha="left",
            va="top", fontsize=7.8, color=TINTA2)
    ax.text(x2, pie, "la celda sobre imagen satelital", ha="left", va="top",
            fontsize=7.8, color=TINTA2)
    guardar(fig, "fig_ficha_celda_comercial.pdf")


def criterios_celda():
    """Los siete criterios colgando de la celda que los produce.

    Sustituye a la version de cuatro cajas con listas dentro, que enumeraba sin
    ensenar. Aqui la celda esta en el centro y cada criterio sale de ella, con
    el color de la familia que decide: el recurso, el terreno, la conexion y el
    acceso. El texto se compone con _pila_en_caja, de modo que no puede salirse
    de su pastilla aunque cambie un rotulo.
    """
    from matplotlib.patches import FancyBboxPatch

    W, A = 13.6, 6.05
    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    ren = fig.canvas.get_renderer()

    # La celda, en el centro.
    LADO = 3.05
    cx, cy = W / 2, A / 2 - 0.20
    x0, y0 = cx - LADO / 2, cy - LADO / 2
    ax.add_patch(FancyBboxPatch((x0, y0), LADO, LADO,
                 boxstyle="round,pad=0,rounding_size=0.10",
                 fc=MARCA, ec="none", zorder=3))
    _pila_en_caja(ax, ren, x0, y0, LADO, LADO,
                  [("Una celda", 12.5, {"color": "white", "ha": "center",
                                        "fontweight": "bold", "zorder": 4}),
                   ("5 por 5 kilómetros", 8.8, {"color": "white", "ha": "center",
                                                "alpha": 0.92, "zorder": 4}),
                   ("Se mide entera y a distancia, sin salir a campo", 7.8,
                    {"color": "white", "ha": "center", "alpha": 0.80,
                     "zorder": 4})],
                  pad_x=0.26, pad_y=0.22, sep=0.16, donde="centro")

    #: El lado de cada criterio, en el orden de CRITERIOS_CELDA. El rotulo y la
    #: familia salen de esa constante y no se vuelven a escribir aqui: cuando la
    #: lista estaba duplicada, esta figura se quedo con «Cobertura apta del
    #: suelo» despues de que la constante pasara a «Cobertura del suelo», que es
    #: justo el nombre que el cliente ya no encuentra en el reporte de lotes.
    LADOS = ["izq", "izq", "izq", "der", "der", "der", "izq"]
    #: (rotulo, familia, lado). El orden es el de la columna, de arriba abajo.
    PASTILLAS = [(criterio, familia, lado)
                 for (familia, criterio, _decide), lado
                 in zip(CRITERIOS_CELDA, LADOS)]
    COLOR = {"El recurso": "#BCDCDF", "El terreno": "#8FC7CC",
             "La conexión": "#3E9BA3", "El acceso": "#0F5E65"}
    BLANCO = {"La conexión", "El acceso"}

    ANCHO_P, ALTO_P, HUECO_P = 4.35, 1.18, 0.18
    izq = [p for p in PASTILLAS if p[2] == "izq"]
    der = [p for p in PASTILLAS if p[2] == "der"]

    for lado, grupo in (("izq", izq), ("der", der)):
        n = len(grupo)
        alto_total = n * ALTO_P + (n - 1) * HUECO_P
        arriba = cy + alto_total / 2
        px = 0.0 if lado == "izq" else W - ANCHO_P
        for k, (rotulo, familia, _l) in enumerate(grupo):
            py = arriba - (k + 1) * ALTO_P - k * HUECO_P
            col = COLOR[familia]
            ax.add_patch(FancyBboxPatch((px, py), ANCHO_P, ALTO_P,
                         boxstyle="round,pad=0,rounding_size=0.08",
                         fc=col, ec="none", zorder=3))
            tc = "white" if familia in BLANCO else TINTA
            sc = "white" if familia in BLANCO else TINTA2
            _pila_en_caja(ax, ren, px, py, ANCHO_P, ALTO_P,
                          [(familia, 7.0, {"color": sc, "ha": "left"}),
                           (rotulo, 9.0, {"color": tc, "ha": "left",
                                          "fontweight": "bold"})],
                          pad_x=0.24, pad_y=0.11, sep=0.04, donde="centro")
            # El hilo que une la pastilla con la celda.
            xa = px + ANCHO_P if lado == "izq" else px
            xb = x0 if lado == "izq" else x0 + LADO
            ax.plot([xa + 0.06, xb], [py + ALTO_P / 2] * 2, color=LINEA,
                    lw=0.9, zorder=1)

    ax.text(0, A - 0.16, "LOS SIETE QUE SE USAN HOY, A MODO DE EJEMPLO",
            ha="left", va="center", fontsize=7.4, color=TINTA3)
    ax.text(W, A - 0.16, "el catálogo crece con lo que el proyecto necesite",
            ha="right", va="center", fontsize=7.4, color=TINTA3)
    guardar(fig, "fig_criterios_celda.pdf")


#: Las secciones de la ficha imprimible del lote, con los campos que trae cada
#: una. Salen de reporte_predios/plantilla.py y estan en su mismo orden: la
#: lamina promete la ficha COMPLETA, de modo que quitar o anadir una seccion aqui
#: la volveria falsa.
#:
#: Comprobadas el 2 de septiembre de 2026 contra la ficha real, componiendo
#: ctxFicha() en el visor y contando los h2: diecisiete en un lote con el
#: certificado ya leido y dieciseis en uno sin el. La decimosexta, la del
#: certificado, es la que faltaba en esta lista.
#:
#: El tercer elemento dice si la seccion sale siempre. La del certificado no:
#: aparece cuando el folio esta comprado y leido.
SECCIONES_FICHA = [
    ("Dónde está", "Situación en el municipio y la vereda", True),
    ("Imagen satelital", "Vista de alta resolución con el lindero", True),
    ("Condiciones del lote", "Cada figura que lo toca y su trámite", True),
    ("Variables de decisión", "Las que deciden si entra en la lista", True),
    ("Dimensiones y forma", "Área, potencia, ancho útil, compacidad", True),
    ("Terreno", "Pendiente, rugosidad, desnivel, elevación", True),
    ("Cobertura del suelo", "Reparto del lote por clase de cobertura", True),
    ("Acceso y conexión", "Vía, subestación, tensión y operador", True),
    ("Recurso solar y clima", "Irradiación, producción, ángulo óptimo y pérdidas", True),
    ("Valor catastral", "Valor de referencia del lote y por hectárea", True),
    ("Norma urbanística", "Clasificación y tratamiento del ordenamiento", True),
    ("Verificación jurídica", "Unidad Agrícola Familiar, restitución y lo que hay que revisar antes de escriturar", True),
    ("Entorno ambiental", "Inundación, sequía, incendios, minería, hidrocarburos y sismo", True),
    ("Cruces cartográficos", "Constancia del cruce con cada capa y su fecha", True),
    ("Índice de aptitud", "Los siete criterios con umbral, nota y peso", True),
    ("Lo que dice el certificado", "Titulares, gravámenes, cadena de tradición, origen y áreas", False),
    ("Ruta de adquisición", "Matrícula, certificado, instrumento y cierre", True),
]


def _rejilla_ficha(secciones, primero, nombre, cierre=None):
    """Una rejilla de tres por tres con las secciones de la ficha del lote.

    `primero` es el numeral de la primera tarjeta, para que la numeracion siga
    de una lamina a la otra. `cierre` ocupa la casilla que sobre.

    Antes esto era una sola lamina de cuatro por cuatro y el texto se salia de
    seis tarjetas: en una hoja de 16 por 9 no hay sitio para dieciseis rotulos
    con su descripcion. Partida en dos, la tarjeta pasa de 3,2 x 1,5 cm a
    4,3 x 1,9 cm, y el texto entra medido, no a ojo.
    """
    from matplotlib.patches import FancyBboxPatch, Rectangle

    W, A = 13.6, 6.30
    COLS, FILS = 3, 3
    MX, MY = 0.28, 0.24

    fig, ax = plt.subplots(figsize=tam(W, A))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W); ax.set_ylim(0, A); ax.axis("off")
    ren = _renderizador(fig)

    w = (W - (COLS - 1) * MX) / COLS
    h = (A - (FILS - 1) * MY) / FILS

    def casilla(k):
        col, fil = k % COLS, k // COLS
        return col * (w + MX), A - (fil + 1) * h - fil * MY

    for k, (tit, des, _) in enumerate(secciones):
        x, y = casilla(k)
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0,rounding_size=0.07",
                     fc="#F2F5F5", ec=LINEA, lw=0.6))
        # Filete de color en el canto superior, que es lo que da la sensacion de
        # ficha y no de tabla.
        ax.add_patch(Rectangle((x + 0.08, y + h - 0.06), w - 0.16, 0.05,
                               fc=MARCA, ec="none"))
        # El numeral va al canto derecho, fuera de la columna de texto: asi no
        # le roba ancho al rotulo ni le obliga a doblar antes de tiempo.
        ax.text(x + w - 0.15, y + h - 0.34, str(primero + k), ha="right",
                va="center", fontsize=7.0, color=TINTA3)
        _pila_en_caja(ax, ren, x, y, w - 0.28, h, [
            (tit, 8.8, dict(fontweight="bold", color=TINTA, linespacing=1.22)),
            (des, 7.4, dict(color=TINTA2, linespacing=1.30)),
        ], pad_x=0.18, pad_y=0.20, sep=0.12, cima=y + h - 0.14)

    if cierre:
        x, y = casilla(len(secciones))
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0,rounding_size=0.07",
                     fc=ACENTOSUAVE, ec=ACENTO, lw=0.8))
        _pila_en_caja(ax, ren, x, y, w, h, [
            (cierre[0], 8.8, dict(fontweight="bold", color=ACENTO2,
                                  linespacing=1.22)),
            (cierre[1], 7.4, dict(color=ACENTO2, linespacing=1.30)),
        ], pad_x=0.20, pad_y=0.22, sep=0.12)
    guardar(fig, nombre)


def ficha_completa():
    """Todo lo que trae la ficha de un lote, en dos laminas de tres por tres.

    La lamina no ensena una ficha sino su indice: el cliente pregunta que
    informacion recibe y esta es la respuesta, mientras que una captura de la
    hoja A4 llega a la lamina con el cuerpo por debajo de 3 pt.

    Van dos porque diecisiete secciones no caben legibles en una: a cuatro por
    cuatro la tarjeta quedaba en 3,2 x 1,5 cm y seis de ellas desbordaban.
    """
    _rejilla_ficha(SECCIONES_FICHA[:9], 1, "fig_ficha_completa_1.pdf")
    _rejilla_ficha(SECCIONES_FICHA[9:], 10, "fig_ficha_completa_2.pdf",
                   cierre=("Una sola página por lote",
                           "imprimible, con la entidad que publica cada dato y "
                           "su fecha de corte"))


# Solo las figuras que alguno de los dos guiones usa. variables(), urbano(),
# criba_lotes(), perfiles(), tamano() y capacidad() dibujan laminas que ya no
# existen y ademas referencian constantes que se retiraron con ellas, de modo
# que llamarlas rompia la regeneracion entera.
if __name__ == "__main__":
    cadena(); contraste(); similitud()
    pesos(); escala(); distribucion(); embudo()
    mapa(); mapa_portada(); grilla_contexto(); catastro_celda(); filtro_cliente(); lote_ejemplo(); ficha_grilla(); ficha_criterios_grilla(); cadena_registro(); diagnostico(); flujo_ia(); fuentes_lote(); clases_lote(); catastro_clasificado(); piloto_criterios(); ficha_criterios()
    cadena_comercial(); criterios_celda(); ficha_completa(); grilla_ancha()
    cadena_registro_comercial(); ficha_celda_comercial()
