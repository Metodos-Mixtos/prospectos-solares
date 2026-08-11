"""
Reporte de caracterización de las grillas candidatas.

Responde al primer bloque de pasos-a-seguir.md:
  - Reporte por grilla con radiación, jurisdicciones especiales, etc.
  - Identificación del operador de red
  - Configuración de barras de la subestación de conexión

Cruza las 100 grillas candidatas del notebook 1 con:
  - el panel de covariables (radiación, pendiente, restricciones, cobertura)
  - las subestaciones del SIN (operador, tensión, configuración de barras)
  - los departamentos del MGN
  - el área de trabajo, de donde se recupera la capacidad instalada en MW

Genera, en outputs/reporte/:
  grillas_candidatas.csv      tabla plana
  grillas_candidatas.xlsx     con formato y anchos de columna
  grillas_candidatas.gpkg     con geometría, para QGIS
  grillas_candidatas.json     insumo del reporte HTML

Uso:
    .venv\\Scripts\\python.exe reporte_grillas.py
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import gcs

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

# Criterios de aptitud. Cuatro, no dos, y ninguno manda sobre los demás.
#
# La selección no es arbitraria: calibracion/pesos.py mide con la d de Cohen
# cuánto separa cada variable las celdas con planta de escala utility del resto.
# Entran las que combinan efecto medible y sentido operativo, y se dejan fuera las
# que solo describen el contexto socioeconómico de las plantas existentes (privación,
# densidad de población, área construida), porque usarlas como criterio replicaría
# una decisión de mercado en vez de evaluar aptitud.
#
#   cobertura apta      d = 0,85   qué hay hoy en el suelo condiciona el costo de
#                                  habilitarlo y las barreras para intervenirlo
#   distancia a la red  d = 0,79   define el costo de conexión
#   recurso solar       d = 0,70   define los ingresos del proyecto
#   pendiente           d = 0,69   define el costo de movimiento de tierras
#
# Los tres umbrales de cada criterio se leen de la distribución de las celdas del país
# que ya contienen una planta solar de 10 MW o más, que es la escala que se prospecta.
#
#     tope   = percentil 10   el decil mejor de lo construido, vale 100
#     bueno  = mediana        donde está la mitad de lo construido, vale 70
#     limite = percentil 90   más allá casi nadie ha construido, vale 0
#
# Se derivan con REFERENCIA_SCRIPT y se pegan aquí en vez de calcularse en cada corrida,
# porque calcularlos al vuelo obligaría a consultar Overpass y a leer el panel completo
# cada vez, y porque un umbral que cambia solo es un umbral que nadie puede auditar.
#
# Antes estaban puestos a criterio propio, y dos estaban mal: con el límite de pendiente
# de 10° el 23% de las plantas existentes quedaba fuera, y con el de rugosidad de 90 m,
# el 15%. Los de distancia, cobertura y recurso resultaron bien calibrados.
REFERENCIA_N = 53
REFERENCIA_MW = 10
REFERENCIA_SCRIPT = "python -m calibracion umbrales"

# El peso de cada criterio es su d de Cohen dividida por la suma de las seis.
#
# La d compara las celdas con planta contra el resto de las 7.239 que están dentro del
# radio de una subestación, y no contra las 21.447 del panel. La diferencia no es menor:
# medida contra el país entero, la cercanía a la red daba 0,79 y era el criterio más
# pesado, pero ese filtro ya se había aplicado al quedarse con las celdas conectables, así
# que lo estábamos contando dos veces. Medida dentro del buffer da 0,52. Al recurso solar
# le pasa lo mismo, baja de 0,68 a 0,48, porque el buffer ya está sesgado hacia zonas de
# buena radiación.
#
# La d no se puede calcular dentro de las cien candidatas, que sería lo más natural de
# pedir: ninguna de ellas tiene planta, así que no hay dos grupos que contrastar.
#
# Aviso para quien lea el índice: el peso dice cuánto queremos que importe cada criterio,
# no cuánto acaba importando. Lo segundo depende también de cuánto varíe el criterio
# dentro de la cartera, y ahí distancia a vía manda mucho más de lo que su peso sugiere,
# porque va de cero a ocho kilómetros mientras los demás se apiñan.

CRITERIOS = {
    "dist_sub": {
        "etiqueta": "Distancia al punto de conexión",
        "unidad": "km",
        "tope": 2.7,
        "bueno": 8.8,
        "limite": 29.4,
        "mayor_mejor": False,
        "d_cohen": 0.52,
        "por_que": "define el costo de conexión, que suele decidir la viabilidad económica",
    },
    "cobertura": {
        "etiqueta": "Cobertura apta del suelo",
        "unidad": "%",
        "tope": 84.0,
        "bueno": 58.0,
        "limite": 27.0,
        "mayor_mejor": True,
        "d_cohen": 0.58,
        "por_que": "lo que hay hoy en el suelo condiciona el costo de habilitarlo",
    },
    "pendiente": {
        "etiqueta": "Pendiente media",
        "unidad": "°",
        "tope": 2.2,
        "bueno": 4.2,
        "limite": 16.6,
        "mayor_mejor": False,
        "d_cohen": 0.62,
        "por_que": "define el movimiento de tierras y el tipo de estructura",
    },
    "recurso": {
        "etiqueta": "Producción fotovoltaica",
        "unidad": "kWh/kWp",
        "tope": 1625.0,
        "bueno": 1563.0,
        "limite": 1460.0,
        "mayor_mejor": True,
        "d_cohen": 0.48,
        "por_que": "define los ingresos por megavatio instalado",
    },
    "rugosidad": {
        "etiqueta": "Rugosidad del relieve",
        "unidad": "m",
        "tope": 4.2,
        "bueno": 17.5,
        "limite": 122.0,
        "mayor_mejor": False,
        "d_cohen": 0.54,
        "por_que": "una pendiente media baja puede esconder terreno ondulado",
    },
    # Séptimo criterio, y el único que no sale del panel sino de los informes de la UPME.
    #
    # Entra porque cumple lo que se les exige a los demás y además es el que de verdad
    # decide si el proyecto existe. Es independiente de todo lo que ya medimos: su
    # correlación con los otros seis va de -0,22 a +0,06. Y discrimina más que ninguna
    # otra variable evaluada, con un coeficiente de variación de 2,6 frente al 0,18 del
    # propio índice. Hoy una grilla puede salir Prioritaria con la barra copada.
    #
    # De las 86 candidatas con dato, diez cuelgan de una barra con menos de 1 MW libre.
    #
    # El tope se fija por percentil y no por el máximo observado: Cerromatoso declara
    # 1.500 MW libres, que es real pero es la subestación de la mina de níquel, y
    # anclarle la escala aplastaría a todas las demás.
    "capacidad": {
        "etiqueta": "Capacidad libre en la barra",
        "unidad": "MW",
        "tope": 200.0,
        "bueno": 100.0,
        "limite": 50.0,
        "mayor_mejor": True,
        "d_cohen": 0.55,
        "por_que": "si la barra no tiene cupo, no hay proyecto por bueno que sea el terreno",
    },
    "dist_via": {
        "etiqueta": "Distancia a vía carrozable",
        "unidad": "km",
        "tope": 0.1,
        "bueno": 0.5,
        "limite": 1.5,
        "mayor_mejor": False,
        # Medida, ya no estimada. Como la variable no está en el panel, hubo que
        # consultar Overpass celda por celda: 24 con planta contra 96 sin planta dentro
        # del buffer, con medias de 0,56 y 1,30 km. La muestra es la más pequeña de las
        # seis porque Overpass rechazó parte de los lotes.
        "d_cohen": 0.53,
        "por_que": "condiciona el acceso de equipos pesados durante la obra",
    },
}

# Índice a partir del cual una celda entra en la lista corta.
#
# Setenta, y el número no es arbitrario: con la escala anclada en las plantas existentes,
# 70 es exactamente la nota de una celda que está en la mediana de lo construido en todos
# los criterios. Así que «índice 70 o más» se lee como «esta celda iguala o supera a la
# planta típica que ya opera en el país», que es una frase que se puede defender.
#
# Estaba en 80, calibrado para la escala anterior, donde el tramo alto se medía contra el
# mejor valor de la cartera y era mucho más fácil de alcanzar. Con la escala absoluta ese
# corte dejaba solo dos celdas en la lista corta.
INDICE_PRIORITARIA = 70.0


# --------------------------------------------------------------------------
# Perfiles de proyecto
# --------------------------------------------------------------------------
#
# El mismo terreno no sirve igual para una granja de 50 MW que para una de 1 MW, así que
# los umbrales se rederivan contra plantas del tamaño que se busca. Se elige con --perfil.
#
# Lo que sale al compararlos es que el perfil distribuido es más laxo en todo. Las plantas
# pequeñas del país están más lejos de la red, en más pendiente y con peor cobertura que
# las grandes, porque son autogeneradores que se ponen donde está la finca o la fábrica y
# no eligen el mejor terreno disponible.
#
# AVISO sobre la conexión en el perfil distribuido. Un proyecto de 1 a 2 MW se conecta a
# un circuito de media tensión de 13,2 o 34,5 kV, no a la subestación, y el blueprint pide
# estar a 1,5 km de ese circuito. Esa red no está publicada en Colombia: no está en
# OpenStreetMap, que devuelve cero líneas de distribución en Córdoba y Bolívar, ni en los
# geoservicios de la UPME, ni en los portales de datos abiertos, que remiten a pedírsela a
# cada operador. Lo que este perfil mide es la distancia a la subestación de
# subtransmisión, que es de donde cuelgan esos circuitos, y sirve para descartar lo
# claramente remoto pero no sustituye al Estudio de Conexión Simplificado ante el
# operador. Por eso su mediana da 16,2 km y no 1,5: son dos cosas distintas.
#
# Los PESOS también van por perfil, y no por gusto. Al medir la d de Cohen por tramos de
# tamaño sale un patrón limpio: todos los criterios pesan más cuanto mayor es el proyecto.
# De 0,5 a 5 MW las d van de 0,20 a 0,36; de 5 a 20 MW, de 0,24 a 0,56; de 20 MW en
# adelante, de 0,50 a 0,56. Una planta de 50 MW hace estudio de sitio y un autogenerador
# de 1 MW se pone donde hay terreno, así que el terreno explica mucho menos dónde están
# los pequeños. Usar los pesos de las grandes para el perfil chico sería atribuirle a esas
# plantas un criterio de selección que no tuvieron.
#
# La d de distancia a vía es la misma en los dos perfiles porque medirla exige consultar
# Overpass celda por celda y no da la muestra para partirla por tramos. Queda anotado.
PERFILES = {
    "utility": {
        "etiqueta": "Escala utility, 10 MW o más",
        "kv_min": 57.5, "kv_max": 230.0,
        "mw_referencia": 10, "n_referencia": 53,
        "ha_proyecto": 150.0,
        "mw_proyecto": 50.0,
        "pesos": {"dist_sub": 0.52, "cobertura": 0.58, "pendiente": 0.62,
                  "recurso": 0.48, "rugosidad": 0.54, "dist_via": 0.53,
                  "capacidad": 0.55},
        "umbrales": {
            "dist_sub":  {"tope": 2.7,    "bueno": 8.8,    "limite": 29.4},
            "cobertura": {"tope": 84.0,   "bueno": 58.0,   "limite": 27.0},
            "pendiente": {"tope": 2.2,    "bueno": 4.2,    "limite": 16.6},
            "recurso":   {"tope": 1625.0, "bueno": 1563.0, "limite": 1460.0},
            "rugosidad": {"tope": 4.2,    "bueno": 17.5,   "limite": 122.0},
            "dist_via":  {"tope": 0.1,    "bueno": 0.5,    "limite": 1.5},
            # La capacidad no se calibra por percentiles como los demás: el dato de la
            # UPME es de 2024 y las plantas existentes se conectaron antes, cuando había
            # más cupo, así que compararlas sería anacrónico. El umbral sale del tamaño
            # del proyecto, que es lo que de verdad decide si cabe.
            "capacidad": {"tope": 200.0,  "bueno": 100.0,  "limite": 50.0},
        },
    },
    "distribuida": {
        "etiqueta": "Generación distribuida, 1 a 2 MWp",
        # Solo hasta 115 kV: de ahí para arriba es transmisión y de esas subestaciones no
        # cuelgan circuitos de media tensión a los que un proyecto así pueda conectarse.
        "kv_min": 57.5, "kv_max": 115.0,
        "mw_referencia": 0.5, "n_referencia": 24,
        "ha_proyecto": 2.0,
        "mw_proyecto": 2.0,
        # Medidos contra las plantas de 0,5 a 5 MW, que es el tramo del blueprint. Son
        # todos pequeños: el terreno explica poco dónde se ubican estas plantas.
        "pesos": {"dist_sub": 0.33, "cobertura": 0.20, "pendiente": 0.36,
                  "recurso": 0.26, "rugosidad": 0.29, "dist_via": 0.53,
                  "capacidad": 0.36},
        "umbrales": {
            "dist_sub":  {"tope": 3.6,    "bueno": 16.2,   "limite": 29.0},
            "cobertura": {"tope": 86.0,   "bueno": 47.0,   "limite": 8.0},
            "pendiente": {"tope": 2.3,    "bueno": 8.4,    "limite": 23.6},
            "recurso":   {"tope": 1630.0, "bueno": 1531.0, "limite": 1351.0},
            "rugosidad": {"tope": 7.4,    "bueno": 43.0,   "limite": 233.2},
            "dist_via":  {"tope": 0.1,    "bueno": 0.6,    "limite": 2.8},
            "capacidad": {"tope": 20.0,   "bueno": 6.0,    "limite": 2.0},
        },
        "aviso_conexion": (
            "La conexión real de un proyecto de 1 a 2 MWp es a un circuito de media "
            "tensión de 13,2 o 34,5 kV, que debe quedar a menos de 1,5 km. Esa red no "
            "está publicada, así que aquí se mide la distancia a la subestación de "
            "subtransmisión, de donde cuelgan esos circuitos. Sirve para descartar lo "
            "remoto, no para confirmar la conexión: eso exige el Estudio de Conexión "
            "Simplificado ante el operador de red, bajo CREG 174."
        ),
    },
}

PERFIL_POR_DEFECTO = "utility"


def aplicar_perfil(nombre: str) -> dict:
    """
    Reescribe CRITERIOS y el rango de tensión con los valores del perfil elegido.

    Muta los globales a propósito, porque el resto del módulo y la plantilla del HTML
    leen de CRITERIOS. Es lo que evita tener que pasar el perfil por veinte funciones.
    """
    global KV_CONEXION_MIN, KV_CONEXION_MAX, REFERENCIA_N, REFERENCIA_MW, PERFIL_ACTIVO

    if nombre not in PERFILES:
        raise SystemExit(f"Perfil desconocido: {nombre}. Hay {', '.join(PERFILES)}")
    p = PERFILES[nombre]
    for clave, u in p["umbrales"].items():
        CRITERIOS[clave].update(u)
    for clave, w in p.get("pesos", {}).items():
        if clave in CRITERIOS:
            CRITERIOS[clave]["d_cohen"] = w
    KV_CONEXION_MIN = p["kv_min"]
    KV_CONEXION_MAX = p["kv_max"]
    REFERENCIA_N = p["n_referencia"]
    REFERENCIA_MW = p["mw_referencia"]
    PERFIL_ACTIVO = nombre
    return p


PERFIL_ACTIVO = PERFIL_POR_DEFECTO

# Alias que conserva el resto del código y los notebooks
PENDIENTE_BUENA = CRITERIOS["pendiente"]["bueno"]
PENDIENTE_LIMITE = CRITERIOS["pendiente"]["limite"]
DIST_SUBEST_BUENA = CRITERIOS["dist_sub"]["bueno"]
DIST_SUBEST_LIMITE = CRITERIOS["dist_sub"]["limite"]

# --------------------------------------------------------------------------
# Exclusiones
# --------------------------------------------------------------------------
#
# Se aplican antes que nada y sacan la celda del ejercicio: no compite, no se puntúa
# y no suma potencial. Ningún umbral del índice la rescata.
#
# El orden importa. Primero se descarta, y solo sobre lo que sobrevive se calcula la
# aptitud. Así, si la selección de las 100 se rehace algún día y devuelve otras celdas,
# el descarte ocurre igual y en el mismo punto.
#
# Las etiquetas van en minúscula porque se incrustan en medio de una frase, y las
# siglas se respetan: pasar la cadena entera por lower() convertiría RUNAP en runap.

#: Figuras jurídicas, todas en la misma bolsa. Cualquiera basta para descartar.
RESTRICCIONES_EXCLUYENTES = {
    "en_parque_nacional": "parque nacional natural",
    "territorio_indigena": "resguardo indígena",
    "consejo_comunitario": "consejo comunitario",
    "area_protegida": "área protegida del RUNAP",
}

#: Exclusiones por umbral: (columna, comparación, valor, texto para el motivo).
#:
#: La altitud descarta el páramo, donde la Ley 1930 de 2018 prohíbe las actividades de
#: alto impacto. La planta solar más alta del país está a 2.600 m, así que el corte en
#: 3.000 no contradice nada de lo construido.
#:
#: La presencia de cultivos de coca descarta por riesgo operativo, y no necesita más
#: explicación. Como comprobación, ninguna de las 45 plantas de escala utility del país
#: está en una celda con coca.
EXCLUSIONES_UMBRAL = [
    ("elevation_mean", ">", 3000.0, "altitud sobre 3.000 m, zona de páramo"),
    ("coca_density_2023", ">", 0.0, "presencia de cultivos de coca"),
]

#: Conflicto armado. El criterio y los dos umbrales viven en conflicto.py; aquí solo se
#: repite el año para poder escribirlo en el motivo.
#:
#: Descarta la celda cuyo municipio acumula acciones bélicas de forma densa. Va por
#: municipio y no por distancia porque el CNMH geocodifica los hechos a un punto de
#: referencia municipal: la mediana es que el 58% de los hechos de un municipio caigan en
#: la misma coordenada, y el radio equivalente del municipio mediano con hechos es de
#: 15 km. Un corte por kilómetros inventaría una precisión que la fuente no tiene.
#:
#: El umbral está calibrado contra lo que el sector ya hace, no contra una preferencia.
#: De las diez plantas solares de 50 MW o más en operación en el país, ninguna está en un
#: municipio que caiga bajo estos filtros.
CONFLICTO_DESDE = 2022

#: Porcentaje de la celda cubierto por Reserva Forestal de Ley 2ª a partir del cual se
#: descarta.
#:
#: La reserva no prohíbe el proyecto como sí lo hace un parque nacional. Reserva el suelo
#: para economía forestal, de modo que darle otro uso exige que el ministerio sustraiga
#: primero esa porción del área. Ese trámite está regulado por la Resolución 110 de 2022
#: del MADS [1], que exige que la actividad sea de utilidad pública o interés social. Un
#: proyecto solar cumple ese requisito de entrada, porque el artículo 4 de la Ley 1715 de
#: 2014 [2] declara de utilidad pública el desarrollo de fuentes no convencionales de
#: energía renovable. La puerta legal existe; lo que añade es tiempo y compensaciones.
#:
#: Por eso el corte es de área, no de presencia. Una celda de 2.500 ha con la reserva
#: encima del 30% deja 1.700 ha libres, y una planta de 100 MW ocupa unas 150: el lote se
#: sitúa fuera del polígono y no hay sustracción que tramitar. Solo cuando la reserva
#: cubre casi toda la celda no queda dónde ponerla, y ahí sí descarta.
#:
#: Queda un cabo suelto que el reporte no resuelve y conviene mirar en campo: la línea de
#: conexión hasta la subestación sí puede cruzar la reserva aunque los paneles estén
#: fuera, y para líneas de transmisión la Resolución 110 pide sustracción temporal.
#:
#: [1] Resolución 110 de 2022 del MADS, que derogó la Resolución 1526 de 2012 salvo sus
#:     artículos 7 y 8 sobre términos de referencia. Fija el plazo de decisión en unos 85
#:     días hábiles y remite las compensaciones al Manual del Medio Biótico, actualizado
#:     por la Resolución 0305 de 2026 del MADS.
#: [2] Artículo 4 de la Ley 1715 de 2014, en la redacción que le dio la Ley 2099 de 2021.
#:     Ojo con el número: el artículo 3 de esa ley es el ámbito de aplicación, no la
#:     declaratoria de utilidad pública.
LEY2_EXCLUYE_PCT = 90.0


def _may(texto: str) -> str:
    """Mayúscula inicial sin tocar el resto, para no estropear las siglas."""
    return texto[:1].upper() + texto[1:] if texto else texto


def _num(serie: pd.Series) -> pd.Series:
    """Convierte texto con coma decimal y separador de miles a número."""
    return pd.to_numeric(
        serie.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def cargar_candidatas(ruta: str | Path | None = None) -> gpd.GeoDataFrame:
    """
    Lee las celdas a caracterizar. Por defecto las que dejó el notebook 1.

    Se puede apuntar a cualquier otro archivo con --celdas. Lo único que el reporte
    exige es una columna cell_id, la geometría y las covariables del panel; el resto
    lo deriva. Si mañana el modelo devuelve otras cien celdas, o mil, el procedimiento
    es el mismo y no hay nada que ajustar a mano.
    """
    ruta = Path(ruta) if ruta else config.TOP_CANDIDATOS_PATH
    if not ruta.is_absolute():
        ruta = config.PROJECT_ROOT / ruta
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}\nCorre antes el notebook 1 para generar las candidatas."
        )
    g = gpd.read_file(ruta)
    if "cell_id" not in g.columns:
        raise SystemExit(f"{ruta.name} no tiene columna cell_id")
    g["cell_id"] = g["cell_id"].astype(str)
    if g.crs is None:
        g = g.set_crs(config.CRS_GEOGRAFICO)
    g.attrs["origen"] = ruta.name
    return g


# Rango de tensión en el que una granja solar en suelo puede conectarse de verdad.
#
# No es un criterio de despacho: se comprobó contra las plantas que ya existen. De las
# 55 plantas de 10 MW o más con subestación a menos de 20 km, 47 tienen al lado una de
# 110 o 115 kV, y de las diez de 50 MW o más ninguna está junto a una de 220 kV o más.
# Las de 500 kV son red troncal: conectarse ahí exige un patio y un transformador que
# ningún proyecto solar de este tamaño justifica, así que contarlas como punto de
# conexión daría por bien conectada una celda que no lo está.
KV_CONEXION_MIN = 57.5
KV_CONEXION_MAX = 230.0


def añadir_subestacion(g: gpd.GeoDataFrame, kv_min: float | None = None,
                       kv_max: float | None = None, sufijo: str = "") -> gpd.GeoDataFrame:
    """
    Subestación más cercana a cada grilla, con su operador y configuración.

    El rango de tensión se puede pasar para calcular más de un perfil en la misma
    corrida. Con sufijo, las columnas salen como sub_distancia_km_dg y demás, de modo
    que el reporte lleva las dos lecturas y el HTML conmuta entre ellas sin recargar.
    """
    kv_min = KV_CONEXION_MIN if kv_min is None else kv_min
    kv_max = KV_CONEXION_MAX if kv_max is None else kv_max

    s = gpd.read_file(config.SUBESTACIONES_PATH)
    if s.crs is None:
        s = s.set_crs(config.CRS_GEOGRAFICO)

    kv = _num(s.get("tension", pd.Series(dtype=str))).where(lambda x: x > 0)
    aptas = kv.between(kv_min, kv_max, inclusive="both")
    descartadas = int((~aptas).sum())
    s = s[aptas].copy()
    print(f"  subestaciones aptas      : {len(s)} "
          f"({descartadas} fuera del rango {kv_min:.0f}-{kv_max:.0f} kV)")

    cols = [c for c in [
        "nombre_subestacion", "nombre_organizacion", "nombre_propietario",
        "tension", "nivel_tension_circuito", "configuracion", "sistema",
        "tipo_subestacion", "municipio", "vigencia",
    ] if c in s.columns]

    # Se mide desde el centroide, no desde el borde del polígono. Medir al borde da
    # la lectura más favorable posible y subestima el trayecto en unos 3 km de media,
    # que en un criterio con umbral de 15 no es poco: el proyecto se construirá en
    # algún punto interior de la celda, no pegado a su esquina más cercana.
    gm = g.to_crs(config.CRS_METRICO).copy()
    gm["geometry"] = gm.geometry.centroid
    sm = s[cols + ["geometry"]].to_crs(config.CRS_METRICO)

    # distance_col da la distancia real al vecino más cercano
    j = gpd.sjoin_nearest(gm, sm, how="left", distance_col="_dist_m")
    j = j[~j.index.duplicated(keep="first")]   # empates: se queda el primero

    g = g.copy()
    for c in cols:
        g["sub_" + c + sufijo] = j[c].values
    g["sub_distancia_km" + sufijo] = (j["_dist_m"].values / 1000).round(2)
    if sufijo:
        # Para el perfil alterno basta la distancia y el nombre; el resto de campos
        # derivados (operador, tensión, barras) se calcula solo para el principal.
        return g

    # La tensión trae 4 registros con -333, que es un centinela de dato ausente.
    if "sub_tension" in g:
        t = _num(g["sub_tension"])
        g["sub_tension_kv"] = t.where(t > 0).round(0)
    else:
        g["sub_tension_kv"] = np.nan

    # 16 subestaciones no traen nombre_organizacion. En esos casos el propietario
    # es el mejor sustituto disponible para identificar al operador.
    org = g.get("sub_nombre_organizacion", pd.Series("", index=g.index)).astype(str).str.strip()
    prop = g.get("sub_nombre_propietario", pd.Series("", index=g.index)).astype(str).str.strip()
    vacio = org.isin(["", "nan", "None", "Sin información", "NA"])
    g["operador"] = org.mask(vacio, prop)
    g["operador_origen"] = np.where(vacio, "propietario", "organización")

    # Varios nombres traen espacios dobles, lo que parte una misma empresa en dos filas
    # al contar. Solo se colapsan los espacios: tocar los puntos rompería "S.A. E.S.P.".
    g["operador"] = (
        g["operador"].str.replace(r"\s+", " ", regex=True).str.strip()
        .replace({"": "Sin identificar", "nan": "Sin identificar"})
    )
    return g


def añadir_departamento(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Departamento en el que cae el centroide de la grilla."""
    try:
        shp = gcs.obtener("geoinfo", "Colombia/Colombia_boundary/MGN_ADM_DPTO_POLITICO.shp",
                          verbose=False)
        for ext in (".dbf", ".shx", ".prj", ".cpg"):
            try:
                gcs.obtener("geoinfo",
                            "Colombia/Colombia_boundary/MGN_ADM_DPTO_POLITICO" + ext,
                            verbose=False)
            except Exception:
                pass
        d = gpd.read_file(shp)
    except Exception as exc:
        print(f"  aviso: no se pudo cargar departamentos ({type(exc).__name__}), se omite")
        g["departamento"] = None
        return g

    col = next((c for c in d.columns if "DPTO" in c.upper() and "CNMBR" in c.upper()), None)
    if col is None:
        col = next((c for c in d.columns if d[c].dtype == object and c != "geometry"), None)

    d = d[[col, "geometry"]].rename(columns={col: "departamento"}).to_crs(g.crs)
    cent = g.copy()
    cent["geometry"] = g.geometry.centroid
    j = gpd.sjoin(cent, d, how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    g = g.copy()
    g["departamento"] = j["departamento"].values
    return g


def añadir_ubicacion(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Municipio y vereda donde cae cada celda, por cruce con la base veredal.

    Hasta ahora la ficha mostraba el municipio de la subestación más cercana, que puede
    estar en otro municipio e incluso en otro departamento que la celda. Para buscar una
    celda por su ubicación hace falta la suya propia, no la de su punto de conexión.

    Se usa el centroide: una celda de 5 km toca varias veredas y quedarse con la del
    centro es más honesto que inventar una regla de mayoría sobre polígonos partidos.
    """
    g = g.copy()
    g["municipio"] = None
    g["vereda"] = None

    ver = config.PROJECT_ROOT / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    if not ver.exists():
        return g

    try:
        v = gpd.read_file(ver)
        if v.crs is None:
            v = v.set_crs(config.CRS_GEOGRAFICO)
        v = v.to_crs(g.crs)
    except Exception as exc:
        print(f"  aviso: sin base veredal ({type(exc).__name__})")
        return g

    nom_mpio = next((c for c in v.columns
                     if c.upper() in ("NOM_MUN", "NOMBRE_MUN", "MPIO_CNMBR", "NOMB_MPIO")), None)
    nom_ver = next((c for c in v.columns
                    if c.upper() in ("NOMBRE_VER", "NOM_VER", "VEREDA")), None)
    # El código DANE se guarda además del nombre, porque cruzar municipios por nombre
    # falla con las tildes y con los nombres largos: el mismo municipio aparece como
    # TUMACO y como SAN ANDRES DE TUMACO según la fuente.
    cod_mpio = next((c for c in v.columns
                     if c.upper() in ("DPTOMPIO", "MPIO_CDPMP", "COD_MPIO")), None)
    cols = [c for c in (nom_mpio, nom_ver, cod_mpio) if c]
    if not cols:
        return g

    cent = g.copy()
    cent["geometry"] = g.geometry.centroid
    j = gpd.sjoin(cent, v[cols + ["geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]

    if nom_mpio:
        g["municipio"] = [str(x).strip().title() if pd.notna(x) else None
                          for x in j[nom_mpio].values]
    if nom_ver:
        g["vereda"] = [str(x).strip().title() if pd.notna(x) else None
                       for x in j[nom_ver].values]
    if cod_mpio:
        g["dane_municipio"] = [str(x).split(".")[0].zfill(5) if pd.notna(x) else None
                               for x in j[cod_mpio].values]
    return g


def añadir_capacidad(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Recupera capacidad_efectiva_neta_mw, que existe aguas arriba pero no en el panel."""
    try:
        ruta = gcs.obtener("prospectos", "final_working_area/grid_trabajo_final.gpkg",
                           verbose=False)
        w = gpd.read_file(ruta)
    except Exception:
        g["capacidad_vecina_mw"] = np.nan
        return g

    if "capacidad_efectiva_neta_mw" not in w.columns:
        g["capacidad_vecina_mw"] = np.nan
        return g

    m = dict(zip(w["cell_id"].astype(str), _num(w["capacidad_efectiva_neta_mw"])))
    g = g.copy()
    g["capacidad_vecina_mw"] = g["cell_id"].astype(str).map(m)
    return g


# --------------------------------------------------------------------------
# Potencial técnico
# --------------------------------------------------------------------------
#
# Traduce la geografía de cada grilla a las magnitudes con las que se habla del
# negocio: hectáreas aprovechables, megavatios pico y energía al año.
#
# Los supuestos están aquí arriba, a la vista, porque son discutibles y cambian
# el resultado. Ninguno pretende sustituir un estudio de sitio.

HA_POR_GRILLA = 2500.0     # una celda de 5 x 5 km
HA_POR_MWP = 1.5           # huella típica de planta en suelo, seguidor de un eje
FACTOR_PENDIENTE = [       # (pendiente máxima, fracción del terreno que sigue sirviendo)
    (5.0, 1.00),
    (10.0, 0.55),
    (15.0, 0.20),
    (999.0, 0.05),
]
# Aptitud del suelo por tipo de cobertura, de 0 a 1.
#
# Antes esto era una suma de tres clases tratadas como equivalentes, lo que en la
# práctica lo convertía en un criterio de pastizal: de los 39,5 puntos medios, 35,0
# venían de ahí. Ahora cada cobertura pesa según lo que cuesta o impide desarrollar
# encima, y las que estorban restan en vez de simplemente no sumar.
#
# Los coeficientes salen del criterio de desarrollo, no de la estadística. Es una
# distinción que importa: medir cuánto se parece una celda a las que ya tienen planta
# premia decisiones pasadas, y ya vimos que esas decisiones respondieron sobre todo a
# infraestructura y acceso. El área construida, por ejemplo, es 3,9 veces más frecuente
# donde hay plantas, y aun así no la queremos: no es terreno disponible.
#
# Lo que sí se contrastó contra los datos fue el sentido de cada peso, para descartar
# contradicciones. Ahí saltó una: los cultivos aparecen 3,7 veces más donde hay plantas
# que en el resto del país, señal de que el conflicto con el uso agrícola no está
# frenando proyectos, así que pesan más de lo que un criterio prudente les daría.
APTITUD_COBERTURA = {
    "%rangeland": 1.00,   # pastizal: terreno abierto, nada que retirar
    "%baregnd":   0.80,   # suelo desnudo: abierto, pero puede ser roca o arena
    "%crops":     0.70,   # cultivo: apto y frecuente, con riesgo de restricción del POT
    "%trees":     0.00,   # bosque: aprovechamiento forestal, licencia y compensación
    "%builtarea": 0.00,   # construido: no disponible y con la propiedad fragmentada
    "%flood_veg": 0.00,   # vegetación inundable: ronda hídrica y riesgo
    "%water":     0.00,
    "%snow_ice":  0.00,
}
#: Lo que la nube tapó no se puede evaluar, así que se descuenta del área valorable en
#: vez de contarlo como no apto. En las candidatas actuales no cambia nada, el máximo
#: es 0,2%, pero en el panel completo hay celdas con hasta un 96% sin observar.
CLASE_NO_OBSERVADA = "%clouds"

#: Referencia para señalar en la ficha una celda mayoritariamente urbana. No excluye:
#: se comprobó que cualquier corte razonable tumbaría plantas que ya operan.
BUILT_AVISO = 40.0


def añadir_cobertura(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Aptitud del suelo de la celda, de 0 a 100, ponderando cada cobertura.

    Cada clase aporta según su coeficiente en APTITUD_COBERTURA y el resultado se
    normaliza sobre el área efectivamente observada, no sobre la celda entera: lo que
    tapó la nube no se puede juzgar, así que se saca del denominador en lugar de
    penalizarlo como si fuera bosque.

    Una celda de puro pastizal sale 100. Una mitad pastizal y mitad bosque, 50. Una
    mitad pastizal y mitad cultivo, 85.
    """
    g = g.copy()
    presentes = {c: k for c, k in APTITUD_COBERTURA.items() if c in g.columns}

    ponderado = pd.Series(0.0, index=g.index)
    for col, coef in presentes.items():
        ponderado = ponderado + g[col].fillna(0) * coef

    observado = pd.Series(100.0, index=g.index)
    if CLASE_NO_OBSERVADA in g.columns:
        observado = (100.0 - g[CLASE_NO_OBSERVADA].fillna(0)).clip(lower=0)

    apta = (ponderado / observado.replace(0, np.nan) * 100).clip(0, 100)
    g["cobertura_apta_pct"] = apta.fillna(0).round(1)

    # Guardadas aparte para poder explicar de dónde sale cada puntuación en la ficha
    g["cob_pastizal_pct"] = g.get("%rangeland", pd.Series(0.0, index=g.index)).round(1)
    g["cob_cultivo_pct"] = g.get("%crops", pd.Series(0.0, index=g.index)).round(1)
    g["cob_bosque_pct"] = g.get("%trees", pd.Series(0.0, index=g.index)).round(1)
    g["cob_construido_pct"] = g.get("%builtarea", pd.Series(0.0, index=g.index)).round(1)

    g["suelo_urbano"] = g["cob_construido_pct"] > BUILT_AVISO
    if g["suelo_urbano"].any():
        print(f"  aviso, celdas con más de {BUILT_AVISO:.0f}% construido: "
              f"{int(g['suelo_urbano'].sum())}")
    return g


def añadir_restricciones_externas(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Cruza las celdas con las capas de restricción que no vienen en el panel.

    El cruce se hace aquí y no se lee de un CSV previo a propósito. El panel de Daniel
    trae las cuatro figuras jurídicas ya resueltas por celda, pero la Ley 2ª no está en
    él, y si el reporte dependiera de una tabla precalculada bastaría con que el modelo
    devolviera otras celdas para que la tabla dejara de cubrirlas sin avisar. Cruzando
    contra la geometría que llega, el resultado es correcto sea cual sea el conjunto.

    La capa viene del bucket. Si no hay credenciales se cae a la caché local y, en
    último término, al servicio del MADS.
    """
    g = g.copy()
    try:
        import insumos.restricciones as cr
    except Exception as exc:
        print(f"  restricciones externas no disponibles ({type(exc).__name__})")
        return g

    for clave in cr.CAPAS:
        try:
            ruta = cr.obtener_capa(clave)
            if ruta is None:
                continue
            res = cr.cruzar(clave, gpd.read_file(ruta), g)
        except Exception as exc:
            print(f"  {clave}: no se pudo cruzar ({type(exc).__name__})")
            continue
        g = g.merge(res, on="cell_id", how="left")
        for col in (f"{clave}_ha", f"{clave}_pct"):
            if col in g.columns:
                g[col] = g[col].fillna(0.0)

    if "ley2_pct" in g.columns:
        tocadas = int((g["ley2_pct"] > 0).sum())
        fuera = int((g["ley2_pct"] >= LEY2_EXCLUYE_PCT).sum())
        print(f"  Ley 2ª: {tocadas} celdas tocadas, {fuera} por encima del "
              f"{LEY2_EXCLUYE_PCT:.0f}% que descarta")
    return g


def añadir_capacidad_barra(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Capacidad libre de la barra a la que se conectaría cada grilla.

    Se toma la de alta tensión para el perfil utility y la de media para el distribuido,
    porque son puntos de conexión distintos: un proyecto de 1 a 2 MW entra por un
    circuito de 13,2 o 34,5 kV y uno de 50 MW por la barra de 110.

    El dato viene de los catorce informes de capacidad por barra de la UPME, ciclo
    2023-2024. Es el techo físico del nodo, no el cupo libre a día de hoy: para
    comprometer una conexión hay que confirmarlo con el operador de red.
    """
    g = g.copy()
    g["capacidad_barra_mw"] = np.nan
    g["capacidad_at_mw"] = np.nan
    g["capacidad_mt_mw"] = np.nan
    if "sub_nombre_subestacion" not in g.columns:
        return g

    try:
        import insumos.barras as cb
        cap = cb.capacidad_por_subestacion()
    except Exception as exc:
        print(f"  capacidad de barra       : no disponible ({type(exc).__name__})")
        return g
    if cap.empty:
        return g

    base = g["sub_nombre_subestacion"].astype(str).map(
        lambda x: cb.ALIAS.get(cb._partir(x)[0], cb._partir(x)[0]))
    g["capacidad_at_mw"] = base.map(dict(zip(cap["base"], cap["capacidad_at_mw"])))
    g["capacidad_mt_mw"] = base.map(dict(zip(cap["base"], cap["capacidad_mt_mw"])))

    col = "capacidad_mt_mw" if PERFIL_ACTIVO == "distribuida" else "capacidad_at_mw"
    g["capacidad_barra_mw"] = g[col]
    n = int(g["capacidad_barra_mw"].notna().sum())
    print(f"  capacidad de barra       : {n} de {len(g)} grillas "
          f"({'media' if PERFIL_ACTIVO == 'distribuida' else 'alta'} tensión)")
    return g


#: Las fotos van en una carpeta al lado del HTML y no embebidas. A la resolución que hace
#: falta para reconocer el terreno, unos 7 m por píxel, las cien pesan 30 MB y meterlas
#: dentro del HTML lo volvía inmanejable. Con la carpeta, el reporte sigue funcionando sin
#: conexión: basta con llevarse las dos cosas juntas.
CARPETA_SAT = "satelital"


def _atribucion_satelital() -> str:
    """Crédito de la imagen. El servicio lo exige y la ficha lo muestra."""
    try:
        import insumos.satelital as satelital
        return satelital.ATRIBUCION
    except Exception:
        return ""


def añadir_satelital(gw: gpd.GeoDataFrame) -> dict:
    """
    Imagen satelital de cada grilla, descargando la que falte.

    Se llama desde el pipeline y no a mano, para que valga con cualquier conjunto de
    grillas: si el modelo devuelve otras cien, estas se piden solas la primera vez que
    se genere el reporte.

    Devuelve, por cell_id, la ruta relativa de la foto, el recuadro que cubre y el
    contorno real de la grilla, que es lo que el HTML dibuja encima.
    """
    try:
        import json as _json
        import shutil
        import insumos.satelital as satelital
    except Exception as exc:
        print(f"  imagen satelital         : no disponible ({type(exc).__name__})")
        return {}

    faltan = [(str(r["cell_id"]), r.geometry) for _, r in gw.iterrows()
              if not (satelital.CACHE / f"sat_{r['cell_id']}_{satelital.PX}.jpg").exists()]
    if faltan:
        print(f"  imagen satelital         : faltan {len(faltan)}, se descargan")
        for cid, geo in faltan:
            satelital.bajar(cid, satelital.recuadro(geo), satelital.PX)

    destino = SALIDA / CARPETA_SAT
    destino.mkdir(parents=True, exist_ok=True)
    ruta_f = satelital.CACHE / "fechas.json"
    fechas = _json.loads(ruta_f.read_text(encoding="utf-8")) if ruta_f.exists() else {}

    sat = {}
    for _, r in gw.iterrows():
        cid = str(r["cell_id"])
        p = satelital.CACHE / f"sat_{cid}_{satelital.PX}.jpg"
        if not p.exists() or p.stat().st_size < 2000:
            continue
        shutil.copyfile(p, destino / f"{cid}.jpg")
        geo = r.geometry
        anillo = (geo.exterior if geo.geom_type == "Polygon"
                  else max(geo.geoms, key=lambda x: x.area).exterior)
        sat[cid] = {
            "src": f"{CARPETA_SAT}/{cid}.jpg",
            "bbox": [round(x, 6) for x in satelital.recuadro(geo)],
            "poly": [[round(x, 6), round(y, 6)] for x, y in anillo.coords],
            "fecha": fechas.get(cid, ""),
        }

    if sat:
        mb = sum((destino / f"{c}.jpg").stat().st_size for c in sat) / 1024 / 1024
        print(f"  imagen satelital         : {len(sat)} de {len(gw)} grillas, "
              f"{mb:.1f} MB en outputs/reporte/{CARPETA_SAT}/")
    return sat


def añadir_conflicto(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Carga de acciones bélicas del municipio de cada celda.

    Se agrega por municipio y no por distancia porque la fuente no da para más: el CNMH
    geocodifica los hechos a un punto de referencia del municipio, no al sitio. Los
    detalles del criterio y de dónde salen los umbrales están en conflicto.py.
    """
    g = g.copy()
    for col, val in (("conf_eventos", 0), ("conf_densidad", 0.0),
                     ("conf_actores", ""), ("conf_ultimo", None),
                     ("conf_descarta", False)):
        g[col] = val

    if "dane_municipio" not in g.columns:
        print("  conflicto: sin código DANE de municipio, no se puede cruzar")
        return g

    try:
        import insumos.conflicto as conflicto
        m = conflicto.por_municipio()
    except Exception as exc:
        print(f"  conflicto: no disponible ({type(exc).__name__})")
        return g
    if m.empty:
        return g

    idx = m.set_index("dane")
    d = g["dane_municipio"]
    g["conf_eventos"] = d.map(idx.eventos).fillna(0).astype(int)
    g["conf_densidad"] = d.map(idx.densidad).fillna(0.0).round(1)
    g["conf_actores"] = d.map(idx.actores).fillna("")
    g["conf_ultimo"] = d.map(idx.ultimo_anio)
    g["conf_descarta"] = d.map(idx.descarta).fillna(False).astype(bool)

    print(f"  conflicto armado         : {int((g.conf_eventos > 0).sum())} celdas con "
          f"hechos en su municipio, {int(g.conf_descarta.sum())} bajo los dos filtros")
    return g


def añadir_potencial(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Hectáreas aprovechables, capacidad indicativa en MWp y energía anual en GWh."""
    g = g.copy()

    apta = g["cobertura_apta_pct"].fillna(0) / 100.0
    pend = g.get("slope_mean", pd.Series(np.nan, index=g.index)).fillna(99)
    factor = pd.Series(0.05, index=g.index)
    for limite, f in reversed(FACTOR_PENDIENTE):
        factor = factor.mask(pend <= limite, f)

    # Una celda descartada no aporta potencial aprovechable, por muy buena que sea su
    # superficie. Sumarla al agregado inflaría la oportunidad con terreno inutilizable.
    libre = pd.Series(1.0, index=g.index)
    if "clasificacion" in g.columns:
        libre = libre.mask(g["clasificacion"] == "Excluida", 0.0)
    else:
        for col in RESTRICCIONES_EXCLUYENTES:
            if col in g.columns:
                libre = libre.mask(g[col].fillna(0) > 0, 0.0)

    g["ha_aptas"] = (HA_POR_GRILLA * apta * factor * libre).round(0)
    g["mwp_indicativo"] = (g["ha_aptas"] / HA_POR_MWP).round(0)
    g["gwh_anio"] = (g["mwp_indicativo"] * g.get("pvout", 0) / 1000).round(0)

    # Cuántos proyectos de tamaño típico cabrían, que es la lectura práctica
    g["proyectos_20mw"] = np.floor(g["mwp_indicativo"] / 20).astype("Int64")
    return g


def añadir_zonas(g: gpd.GeoDataFrame, radio_km: float = 20.0) -> gpd.GeoDataFrame:
    """
    Agrupa grillas próximas en zonas de prospección.

    Cien puntos sueltos no son una hoja de ruta. Diez zonas sí, porque el trabajo de
    campo, la norma municipal y la negociación con el operador se hacen por zona y no
    por celda. Se usa DBSCAN sobre coordenadas métricas, sin número de grupos prefijado.
    """
    from sklearn.cluster import DBSCAN

    g = g.copy()
    m = g.to_crs(config.CRS_METRICO)
    xy = np.c_[m.geometry.centroid.x, m.geometry.centroid.y]

    etiquetas = DBSCAN(eps=radio_km * 1000, min_samples=2).fit_predict(xy)
    g["_cluster"] = etiquetas

    # Se renumeran por tamaño, para que la zona 1 sea la mayor. Las sueltas van aparte.
    tam = pd.Series(etiquetas).value_counts()
    orden = [c for c in tam.index if c != -1]
    mapa = {c: i + 1 for i, c in enumerate(orden)}
    g["zona"] = [("Z%02d" % mapa[c]) if c != -1 else "Aislada" for c in etiquetas]

    resumen = (
        g[g["zona"] != "Aislada"]
        .groupby("zona")
        .agg(grillas=("cell_id", "size"),
             ha_aptas=("ha_aptas", "sum"),
             mwp=("mwp_indicativo", "sum"),
             pvout=("pvout", "mean"),
             dist_sub=("sub_distancia_km", "mean"),
             depto=("departamento", lambda s: s.mode().iat[0] if len(s.mode()) else ""),
             operador=("operador", lambda s: s.mode().iat[0] if len(s.mode()) else ""),
             prioritarias=("clasificacion", lambda s: int((s == "Prioritaria").sum())))
        .sort_values("mwp", ascending=False)
    )
    g.attrs["zonas"] = resumen
    return g.drop(columns=["_cluster"])


def añadir_vias(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Distancia a vía, del CSV ya calculado y, para lo que falte, consultando Overpass.

    Lo importante es el segundo paso. Antes, si el CSV no cubría una celda, la columna
    quedaba vacía y el criterio simplemente desaparecía del índice de esa celda sin que
    nada lo advirtiera: se comparaba con cinco criterios contra las que tenían seis.
    Ahora se completa lo que falte, y solo se rinde si Overpass no responde.
    """
    g = g.copy()
    csv = SALIDA / "distancia_vias.csv"
    cols = ("dist_via_km", "dist_via_principal_km")

    for col in cols:
        g[col] = np.nan
    if csv.exists():
        v = pd.read_csv(csv, dtype={"cell_id": str})
        for col in cols:
            if col in v.columns:
                g[col] = g["cell_id"].astype(str).map(dict(zip(v["cell_id"], v[col])))

    faltan = g["dist_via_km"].isna()
    if not faltan.any():
        return g

    print(f"  distancia a vía          : faltan {int(faltan.sum())} celdas, se consultan")
    try:
        import insumos.vias as distancia_vias
        res = distancia_vias.calcular(g.loc[faltan], verbose=False)
    except Exception as exc:
        print(f"    no se pudo consultar Overpass ({type(exc).__name__}), quedan sin dato")
        return g

    for col in cols:
        nuevos = dict(zip(res["cell_id"], res[col]))
        g[col] = g[col].fillna(g["cell_id"].astype(str).map(nuevos))

    # El CSV se rehace con todo lo que hay, para que la siguiente corrida no repita
    # las consultas y para que quede constancia de con qué celdas se generó.
    SALIDA.mkdir(parents=True, exist_ok=True)
    g[["cell_id", *cols]].to_csv(csv, index=False, encoding="utf-8-sig")
    return g


def clasificar(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Clasificación en cuatro niveles, con el motivo escrito para cada celda.

    Se evalúa en este orden y el primero que aplica manda:

      Descartada   cae sobre una figura jurídica excluyente. No compite, sale.
      Con reparos  sin restricción jurídica, pero la pendiente supera los 10° o la
                   subestación queda a más de 30 km. Cualquiera de las dos basta.
      Preferente   pendiente por debajo de 5° y subestación a 15 km o menos. Se
                   exigen las dos a la vez.
      Viable       el resto. Sin reparos, pero corta en pendiente o en distancia.

    Solo tres variables clasifican: figura jurídica, pendiente y distancia al punto
    de conexión. Todo lo demás que trae el reporte (elevación, temperatura, cobertura
    del suelo, densidad de población) es contexto para leer la celda, no criterio.
    """
    g = g.copy()

    detalle = [[] for _ in range(len(g))]
    for col, txt in RESTRICCIONES_EXCLUYENTES.items():
        if col in g.columns:
            for i, v in enumerate((g[col].fillna(0) > 0).values):
                if v:
                    detalle[i].append(txt)

    # Exclusiones por umbral. El suelo urbano no está aquí a propósito: cualquier corte
    # razonable de área construida tumbaría plantas que existen de verdad, seguramente
    # autogeneradores en zona industrial. Penaliza dentro del índice, no excluye.
    for col, cmp_, valor, texto in EXCLUSIONES_UMBRAL:
        if col not in g.columns:
            continue
        serie = g[col].fillna(-np.inf if cmp_ == ">" else np.inf)
        hit = serie > valor if cmp_ == ">" else serie < valor
        for i, v in enumerate(hit.values):
            if v:
                detalle[i].append(texto)

    # Conflicto armado. Descarta cuando el municipio acumula hechos y además los acumula
    # de forma densa, no por ser grande. El umbral se calibró contra las plantas que ya
    # operan: ninguna de las diez de 50 MW o más del país está en un municipio así.
    if "conf_descarta" in g.columns:
        for i, (fuera, n, dens) in enumerate(zip(
                g["conf_descarta"].fillna(False).values,
                g["conf_eventos"].fillna(0).values,
                g["conf_densidad"].fillna(0).values)):
            if fuera:
                detalle[i].append(
                    f"territorio en disputa, {int(n)} acciones bélicas en el municipio "
                    f"desde {CONFLICTO_DESDE} ({dens:.0f} por mil km²)"
                )

    # Ley 2ª. Descarta solo si cubre la celda casi entera, porque con cobertura parcial
    # el proyecto se sitúa fuera del polígono y no hay sustracción que tramitar.
    if "ley2_pct" in g.columns:
        for i, pct in enumerate(g["ley2_pct"].fillna(0).values):
            if pct >= LEY2_EXCLUYE_PCT:
                detalle[i].append(
                    f"Reserva Forestal de Ley 2ª de 1959 sobre el {pct:.0f}% de la celda"
                )

    g["ley2_parcial"] = (
        (g["ley2_pct"].fillna(0) > 0) & (g["ley2_pct"].fillna(0) < LEY2_EXCLUYE_PCT)
        if "ley2_pct" in g.columns else False
    )

    g["restricciones"] = [_may("; ".join(d)) if d else "Sin restricción registrada"
                          for d in detalle]
    g["n_restricciones"] = [len(d) for d in detalle]

    # Valor de cada criterio, con la precisión con la que se publica. Comparar con el
    # crudo haría que una pendiente de 10,04° se mostrara como 10,0° pero se
    # clasificara como si pasara el límite, y el reporte se contradiría con lo que
    # enseña. Es el mismo redondeo que aplica la matriz del HTML.
    nan = pd.Series(np.nan, index=g.index)
    valores = {
        "dist_sub": g.get("sub_distancia_km", nan).round(2),
        "cobertura": g.get("cobertura_apta_pct", nan).round(1),
        "pendiente": g.get("slope_mean", nan).round(1),
        "recurso": g.get("pvout", nan).round(0),
        "rugosidad": g.get("elevation_std", nan).round(1),
        "dist_via": g.get("dist_via_km", nan).round(2),
        "capacidad": g.get("capacidad_barra_mw", nan).round(1),
    }

    def fmt(clave, v):
        u = CRITERIOS[clave]["unidad"]
        dec = 0 if u in ("kWh/kWp", "%") else 1
        return f"{v:.{dec}f}{'' if u == '°' else ' '}{u}"

    def utilidad(clave, v):
        """
        Puntuación de 0 a 100 de un criterio, en dos tramos y en escala absoluta.

        Cero en el límite, 70 en el objetivo y 100 en el tope. Los tres puntos salen de
        la distribución de las plantas que ya operan, no de la cartera que se esté
        evaluando, y esa es la diferencia que importa. Antes el tramo de arriba se
        calibraba contra el mejor valor de las cien candidatas, de modo que la misma
        celda sacaba distinta nota según con quién se la comparara y dos corridas no se
        podían poner una al lado de la otra.

        Se sigue permitiendo pasar de 100 hacia arriba, pero recortado: una celda mejor
        que el decil superior de lo construido ya no tiene contra qué distinguirse.
        """
        cfg = CRITERIOS[clave]
        lim, bue, tope = cfg["limite"], cfg["bueno"], cfg["tope"]
        signo = 1.0 if cfg["mayor_mejor"] else -1.0
        v_, lim_, bue_, tope_ = signo * v, signo * lim, signo * bue, signo * tope

        if v_ <= lim_:
            return 0.0
        if v_ <= bue_:
            return 70.0 * (v_ - lim_) / max(1e-9, bue_ - lim_)
        holgura = tope_ - bue_
        if holgura <= 1e-9:
            return 70.0
        return 70.0 + 30.0 * min(1.0, (v_ - bue_) / holgura)

    pesos = {k: c["d_cohen"] for k, c in CRITERIOS.items()}

    clases, motivos, indices, cumples = [], [], [], []
    for i in range(len(g)):
        # --- exclusión por figura jurídica, manda sobre todo lo demás ---
        if detalle[i]:
            clases.append("Excluida")
            motivos.append("Excluida: la celda cae sobre " + " y ".join(detalle[i]) + ".")
            indices.append(0.0)
            cumples.append(0)
            continue

        bajo_limite, cortos, ok = [], [], []
        suma, peso_total = 0.0, 0.0
        for clave, cfg in CRITERIOS.items():
            v = valores[clave].iloc[i]
            if pd.isna(v):
                continue
            v = float(v)
            suma += utilidad(clave, v) * pesos[clave]
            peso_total += pesos[clave]

            peor = v < cfg["limite"] if cfg["mayor_mejor"] else v > cfg["limite"]
            corto = v < cfg["bueno"] if cfg["mayor_mejor"] else v > cfg["bueno"]
            texto = f"{cfg['etiqueta'].lower()} de {fmt(clave, v)}"
            if peor:
                bajo_limite.append(f"{texto}, fuera del límite de {fmt(clave, cfg['limite'])}")
            elif corto:
                cortos.append(texto)
            else:
                ok.append(clave)

        indice = round(suma / peso_total, 1) if peso_total else 0.0
        indices.append(indice)
        cumples.append(len(ok))

        # La reserva parcial no cambia de clase, pero tiene que quedar escrita: el lote
        # se puede sitiar fuera del polígono, y quien lea la ficha debe saberlo antes de
        # salir a mirar predios.
        nota = ""
        if bool(g["ley2_parcial"].iloc[i]):
            nota = (f" El {g['ley2_pct'].iloc[i]:.0f}% de la celda está en Reserva "
                    f"Forestal de Ley 2ª: el lote debe quedar fuera del polígono o "
                    f"habría que tramitar sustracción ante el MADS.")

        # El índice resume, pero no puede tapar un criterio fuera de límite: una celda
        # excelente en cinco cosas y con la subestación a 40 km sigue siendo un problema.
        if bajo_limite:
            clases.append("Condicionada")
            motivos.append(
                f"Índice {indice:.0f} sobre 100. Requiere gestión adicional por "
                + "; y ".join(bajo_limite) + "." + nota
            )
        elif indice >= INDICE_PRIORITARIA:
            clases.append("Prioritaria")
            motivos.append(
                f"Índice {indice:.0f} sobre 100, cumpliendo {len(ok)} de "
                f"{len(CRITERIOS)} criterios. Entra en la lista corta." + nota
            )
        else:
            clases.append("Elegible")
            detalle_corto = (" Por debajo del objetivo en " + " y ".join(cortos) + "."
                             if cortos else "")
            motivos.append(
                f"Índice {indice:.0f} sobre 100. Cumple {len(ok)} de "
                f"{len(CRITERIOS)} criterios.{detalle_corto}" + nota
            )

    g["clasificacion"] = clases
    g["motivo"] = motivos
    g["indice_aptitud"] = indices
    g["criterios_cumplidos"] = cumples
    return g


def concurrencia_subestaciones(g: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Cuántas candidatas compiten por la misma subestación.

    Todavía no tenemos el cupo libre en MW de cada barra, que es lo que pide el tercer
    punto de la hoja de ruta y vive en unos PDF. Pero sí se puede ver el otro lado de la
    ecuación: la demanda que se le vendría encima a cada punto de conexión si varias de
    estas grillas prosperaran. Una barra con ocho candidatas apuntándole es una barra
    donde los proyectos compiten entre sí, y eso cambia el orden en que conviene moverse.
    """
    if "sub_nombre_subestacion" not in g.columns:
        return pd.DataFrame()

    t = (
        g.groupby("sub_nombre_subestacion")
        .agg(candidatas=("cell_id", "size"),
             mwp_pretendido=("mwp_indicativo", "sum"),
             km_medio=("sub_distancia_km", "mean"),
             tension_kv=("sub_tension_kv", "first"),
             barras=("sub_configuracion", "first"),
             operador=("operador", "first"),
             municipio=("sub_municipio", "first"),
             solar_vecina_mw=("capacidad_vecina_mw", "max"),
             prioritarias=("clasificacion", lambda s: int((s == "Prioritaria").sum())))
        .sort_values("candidatas", ascending=False)
    )
    return t


def exportar_kml(g: gpd.GeoDataFrame, destino: Path) -> None:
    """
    KML para Google Earth, con una ficha legible al hacer clic en cada polígono.

    Es el formato con el que de verdad se revisa un terreno antes de ir a campo: se abre
    encima de la imagen satelital y se ve si el sitio está despejado, si hay vías y qué
    hay alrededor. Se escribe a mano porque el driver KML de GDAL no permite dar estilo
    ni cuerpo HTML a los globos.
    """
    from xml.sax.saxutils import escape

    colores = {              # KML usa aabbggrr, no rrggbb
        "Prioritaria": "cc5a7a3d",
        "Elegible": "cc1e76b0",
        "Condicionada": "cc2f49a8",
        "Excluida": "99707070",
    }

    gw = g.to_crs(config.CRS_GEOGRAFICO)
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        "<name>Grillas candidatas para granjas solares</name>",
        "<description>Metodos Mixtos Consultores. Prospeccion solar Colombia.</description>",
    ]
    for clase, color in colores.items():
        partes.append(
            f'<Style id="{clase.replace(" ", "_")}">'
            f"<LineStyle><color>ff{color[2:]}</color><width>2</width></LineStyle>"
            f"<PolyStyle><color>{color}</color></PolyStyle></Style>"
        )

    for clase in colores:
        sub = gw[gw["clasificacion"] == clase]
        if sub.empty:
            continue
        partes.append(f"<Folder><name>{clase} ({len(sub)})</name>")
        for _, r in sub.iterrows():
            ficha = (
                f"<h3>Grilla {r['cell_id']}</h3>"
                f"<b>Puesto:</b> {r['ranking']} de {len(gw)}<br/>"
                f"<b>Clasificacion:</b> {r['clasificacion']}<br/>"
                f"<b>Motivo:</b> {r['motivo']}<br/><br/>"
                f"<b>Departamento:</b> {r.get('departamento', '')}<br/>"
                f"<b>Produccion FV:</b> {r.get('pvout', float('nan')):.0f} kWh/kWp/ano<br/>"
                f"<b>Pendiente:</b> {r.get('slope_mean', float('nan')):.1f} grados<br/>"
                f"<b>Hectareas aptas:</b> {r.get('ha_aptas', 0):.0f} ha<br/>"
                f"<b>Potencial indicativo:</b> {r.get('mwp_indicativo', 0):.0f} MWp<br/><br/>"
                f"<b>Subestacion:</b> {r.get('sub_nombre_subestacion', '')} "
                f"a {r.get('sub_distancia_km', float('nan')):.1f} km<br/>"
                f"<b>Operador:</b> {r.get('operador', '')}<br/>"
                f"<b>Restricciones:</b> {r['restricciones']}<br/>"
                f"<b>Zona:</b> {r.get('zona', '')}"
            )
            anillo = " ".join(f"{x:.6f},{y:.6f},0" for x, y in r.geometry.exterior.coords)
            # El nombre visible en Google Earth evita el MWp a propósito: puesto encima
            # del polígono, esa cifra se lee como capacidad del proyecto y es el techo
            # teórico de la superficie. La producción específica no se malinterpreta.
            partes.append(
                f"<Placemark><name>#{r['ranking']} · {r['cell_id']} · "
                f"{r.get('pvout', float('nan')):.0f} kWh/kWp</name>"
                f"<styleUrl>#{clase.replace(' ', '_')}</styleUrl>"
                f"<description><![CDATA[{ficha}]]></description>"
                f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{anillo}"
                f"</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>"
            )
        partes.append("</Folder>")

    partes.append("</Document></kml>")
    destino.write_text("\n".join(partes), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--celdas",
                    help="gpkg o geojson de celdas candidatas; "
                         "por defecto el top_candidates del notebook 1")
    ap.add_argument("--perfil", choices=list(PERFILES), default=PERFIL_POR_DEFECTO,
                    help="tamaño de proyecto para el que se evalúa; cambia los umbrales "
                         "y el rango de tensión del punto de conexión")
    a = ap.parse_args(argv)

    perfil = aplicar_perfil(a.perfil)

    print("=" * 74)
    print("REPORTE DE CARACTERIZACIÓN DE GRILLAS CANDIDATAS")
    print("=" * 74)
    print(f"  perfil                   : {perfil['etiqueta']}")
    print(f"  umbrales calibrados con  : {perfil['n_referencia']} celdas con planta de "
          f"{perfil['mw_referencia']} MW o más")

    g = cargar_candidatas(a.celdas)
    print(f"  candidatas cargadas      : {len(g)} de {g.attrs.get('origen', '?')}")

    g = añadir_subestacion(g)
    print(f"  subestación de conexión  : {g['sub_nombre_subestacion'].notna().sum()} asignadas")

    # El otro perfil se calcula también, para que el HTML pueda conmutar entre los dos
    # sin regenerar nada. Solo cambia el techo de tensión, así que solo cambia esto.
    for nombre, p in PERFILES.items():
        if nombre == PERFIL_ACTIVO:
            continue
        g = añadir_subestacion(g, p["kv_min"], p["kv_max"], sufijo=f"__{nombre}")

    g = añadir_departamento(g)
    print(f"  departamento             : {g['departamento'].notna().sum()} asignados")

    g = añadir_ubicacion(g)
    print(f"  municipio y vereda       : {g['municipio'].notna().sum()} y "
          f"{g['vereda'].notna().sum()} asignados")

    g = añadir_capacidad(g)
    g = añadir_vias(g)
    n_via = int(g["dist_via_km"].notna().sum())
    print(f"  distancia a vía          : {n_via} con dato"
          + ("" if n_via else "  (corre distancia_vias.py)"))
    g = añadir_cobertura(g)
    g = añadir_restricciones_externas(g)
    g = añadir_conflicto(g)
    g = añadir_capacidad_barra(g)
    g = clasificar(g)
    g = añadir_potencial(g)

    # Se ordena por el índice de aptitud, no por sim_score. El puntaje de similitud es
    # lo que sirvió para escoger estas cien entre 21.447, pero dentro de ellas ya no
    # discrimina: va de 0,762 a 0,842 y su correlación con el índice es 0,02. Ordenar
    # por él dejaba de primera a una celda con índice 47,9 y de puesto 83 a la mejor de
    # la cartera, así que el reporte se contradecía consigo mismo. Se desempata con
    # sim_score, que para eso sí sirve.
    g = g.sort_values(["indice_aptitud", "sim_score"], ascending=False).reset_index(drop=True)
    g.insert(0, "ranking", range(1, len(g) + 1))

    g = añadir_zonas(g)
    zonas = g.attrs.get("zonas")
    print(f"  zonas de prospección     : {g['zona'].nunique() - (1 if (g['zona'] == 'Aislada').any() else 0)}"
          f" agrupadas, {(g['zona'] == 'Aislada').sum()} aisladas")

    # ---- tabla de salida, en orden de lectura ----
    columnas = [
        ("ranking", "Ranking"),
        ("cell_id", "ID grilla"),
        ("zona", "Zona de prospección"),
        ("indice_aptitud", "Índice de aptitud"),
        ("criterios_cumplidos", "Criterios cumplidos"),
        ("sim_score", "Puntaje de similitud"),
        ("clasificacion", "Clasificación"),
        ("cobertura_apta_pct", "Cobertura apta (%)"),
        ("ley2_pct", "Reserva Ley 2ª (% de la celda)"),
        ("conf_eventos", "Acciones bélicas en el municipio"),
        ("conf_densidad", "Acciones bélicas por mil km²"),
        ("conf_actores", "Actores armados registrados"),
        ("ha_aptas", "Hectáreas aptas"),
        ("mwp_indicativo", "Potencial indicativo (MWp)"),
        ("gwh_anio", "Energía anual (GWh)"),
        ("proyectos_20mw", "Proyectos de 20 MW que caben"),
        ("motivo", "Motivo de la clasificación"),
        ("departamento", "Departamento"),
        ("municipio", "Municipio"),
        ("vereda", "Vereda"),
        ("sub_municipio", "Municipio de la subestación"),
        ("restricciones", "Restricciones"),
        ("dist_via_km", "Distancia a vía (km)"),
        ("dist_via_principal_km", "Distancia a vía principal (km)"),
        ("pvout", "Producción FV (kWh/kWp/año)"),
        ("gti", "Irradiación GTI (kWh/m²/año)"),
        ("ghi", "Irradiación GHI (kWh/m²/año)"),
        ("temp", "Temperatura media (°C)"),
        ("slope_mean", "Pendiente media (°)"),
        ("elevation_mean", "Elevación media (m)"),
        ("sub_distancia_km", "Distancia a subestación (km)"),
        ("sub_nombre_subestacion", "Subestación más cercana"),
        ("sub_tension_kv", "Tensión (kV)"),
        ("sub_configuracion", "Configuración de barras"),
        ("operador", "Operador de red"),
        ("operador_origen", "Origen del operador"),
        ("sub_nombre_propietario", "Propietario"),
        ("sub_sistema", "Sistema"),
        ("sub_vigencia", "Vigencia del dato de red"),
        ("capacidad_vecina_mw", "Capacidad solar vecina (MW)"),
        ("%crops", "Cultivos (%)"),
        ("%rangeland", "Pastizal (%)"),
        ("%trees", "Bosque (%)"),
        ("%builtarea", "Área construida (%)"),
        ("pop_density_mean", "Densidad poblacional"),
    ]
    presentes = [(c, n) for c, n in columnas if c in g.columns]
    tabla = g[[c for c, _ in presentes]].copy()
    tabla.columns = [n for _, n in presentes]

    for c in tabla.columns:
        if pd.api.types.is_numeric_dtype(tabla[c]):
            tabla[c] = tabla[c].round(2)

    SALIDA.mkdir(parents=True, exist_ok=True)

    tabla.to_csv(SALIDA / "grillas_candidatas.csv", index=False, encoding="utf-8-sig")
    print(f"\n  CSV   -> {SALIDA / 'grillas_candidatas.csv'}")

    try:
        with pd.ExcelWriter(SALIDA / "grillas_candidatas.xlsx", engine="openpyxl") as xl:
            tabla.to_excel(xl, sheet_name="Candidatas", index=False)
            hoja = xl.sheets["Candidatas"]
            for i, col in enumerate(tabla.columns, 1):
                # Una columna entera de NaN devuelve NA al medir longitudes, no un número
                largos = tabla[col].astype("string").fillna("").str.len().max()
                largos = 0 if pd.isna(largos) else int(largos)
                ancho = max(len(str(col)), largos)
                hoja.column_dimensions[hoja.cell(row=1, column=i).column_letter].width = min(ancho + 3, 46)
            hoja.freeze_panes = "C2"
        print(f"  XLSX  -> {SALIDA / 'grillas_candidatas.xlsx'}")
    except Exception as exc:
        print(f"  aviso: no se pudo escribir el xlsx ({type(exc).__name__}: {exc})")

    g.to_file(SALIDA / "grillas_candidatas.gpkg", driver="GPKG")
    print(f"  GPKG  -> {SALIDA / 'grillas_candidatas.gpkg'}")

    gw_exp = g.to_crs(config.CRS_GEOGRAFICO)
    gw_exp.to_file(SALIDA / "grillas_candidatas.geojson", driver="GeoJSON")
    print(f"  GEOJSON -> {SALIDA / 'grillas_candidatas.geojson'}")

    exportar_kml(g, SALIDA / "grillas_candidatas.kml")
    print(f"  KML   -> {SALIDA / 'grillas_candidatas.kml'}  (Google Earth)")

    if zonas is not None and len(zonas):
        zonas.round(1).to_csv(SALIDA / "zonas_prospeccion.csv", encoding="utf-8-sig")
        print(f"  ZONAS -> {SALIDA / 'zonas_prospeccion.csv'}")

    conc = concurrencia_subestaciones(g)
    if len(conc):
        # Capacidad disponible en barras, si alguien ya cargó el dato de la UPME.
        # Mientras no exista, la columna queda vacía y el reporte lo dice.
        try:
            import insumos.barras as capacidad_barras
            # Se cruza por el nombre base, sin exigir que coincida el nivel de tensión,
            # y así una misma subestación aporta su barra de alta y la de media si el
            # informe trae las dos. Antes se exigía coincidencia exacta de nombre y kV,
            # y eso descartaba las 509 barras de media tensión de los informes, que son
            # justo donde se conecta un proyecto de generación distribuida.
            cap = capacidad_barras.capacidad_por_subestacion()
            if len(cap):
                base = conc.index.to_series().map(
                    lambda x: capacidad_barras.ALIAS.get(capacidad_barras._partir(x)[0],
                                                         capacidad_barras._partir(x)[0]))
                for col in ("capacidad_at_mw", "capacidad_mt_mw", "kv_mt"):
                    conc[col] = base.map(dict(zip(cap["base"], cap[col])))
                # Se conserva el nombre de siempre para no romper lo que ya lo lee
                conc["capacidad_disponible_mw"] = conc["capacidad_at_mw"]
                n_at = int(conc["capacidad_at_mw"].notna().sum())
                n_mt = int(conc["capacidad_mt_mw"].notna().sum())
                print(f"  capacidad en barras      : {n_at} de {len(conc)} en alta tensión, "
                      f"{n_mt} en media")
            else:
                conc["capacidad_disponible_mw"] = np.nan
        except Exception as exc:
            print(f"  capacidad en barras      : no disponible ({type(exc).__name__})")
            conc["capacidad_disponible_mw"] = np.nan

        conc.round(1).to_csv(SALIDA / "concurrencia_subestaciones.csv", encoding="utf-8-sig")
        print(f"  BARRAS -> {SALIDA / 'concurrencia_subestaciones.csv'}")

    # ---- json para el reporte html ----
    gw = g.to_crs(config.CRS_GEOGRAFICO)
    cent = gw.geometry.centroid

    sat = añadir_satelital(gw)
    registros = []
    for i, row in gw.iterrows():
        registros.append({
            "ranking": int(row["ranking"]),
            "id": str(row["cell_id"]),
            "score": round(float(row["sim_score"]), 4),
            "clase": row["clasificacion"],
            "motivo": row["motivo"],
            "depto": row.get("departamento") or "Sin dato",
            "municipio": row.get("municipio") or "Sin dato",
            "vereda": row.get("vereda") or "Sin dato",
            "sub_municipio": row.get("sub_municipio") or "Sin dato",
            "restricciones": row["restricciones"],
            "n_restric": int(row["n_restricciones"]),
            # Los valores de los seis criterios se exportan con el mismo redondeo con el
            # que clasificar() los usa. Si el JSON manda más decimales, el navegador
            # recalcula el índice sobre otros números y aparecen diferencias de una
            # décima que rompen el orden del ranking sin que nada esté mal de fondo.
            "via": round(float(row["dist_via_km"]), 2) if pd.notna(row.get("dist_via_km")) else None,
            "via_pri": float(row["dist_via_principal_km"]) if pd.notna(row.get("dist_via_principal_km")) else None,
            "vigencia": row.get("sub_vigencia") or "Sin información",
            "pvout": round(float(row["pvout"]), 0) if pd.notna(row.get("pvout")) else None,
            "gti": round(float(row["gti"]), 1) if pd.notna(row.get("gti")) else None,
            "temp": round(float(row["temp"]), 1) if pd.notna(row.get("temp")) else None,
            "pendiente": round(float(row["slope_mean"]), 1) if pd.notna(row.get("slope_mean")) else None,
            "cobertura": round(float(row["cobertura_apta_pct"]), 1) if pd.notna(row.get("cobertura_apta_pct")) else None,
            "ley2": round(float(row["ley2_pct"]), 1) if pd.notna(row.get("ley2_pct")) else 0.0,
            "conf_n": int(row.get("conf_eventos") or 0),
            "conf_d": round(float(row.get("conf_densidad") or 0), 1),
            "conf_act": row.get("conf_actores") or "",
            "cap_mw": (round(float(row["capacidad_barra_mw"]), 1)
                       if pd.notna(row.get("capacidad_barra_mw")) else None),
            "cap_at": (round(float(row["capacidad_at_mw"]), 1)
                       if pd.notna(row.get("capacidad_at_mw")) else None),
            "cap_mt": (round(float(row["capacidad_mt_mw"]), 1)
                       if pd.notna(row.get("capacidad_mt_mw")) else None),
            # Contexto para leer la grilla. No entran en el índice, pero explican por qué
            # un criterio sale como sale y qué se va a encontrar quien vaya al terreno.
            #
            # La cobertura arbórea de 2000 se publica tal cual y NO se resta de la de hoy
            # para estimar deforestación. Vienen de fuentes distintas, Hansen mide dosel
            # por umbral y la de hoy es la clase "árboles" de Sentinel-2, así que la resta
            # mide la diferencia entre dos metodologías y no el cambio del bosque: hecha
            # sobre estas cien grillas daba que 76 habían ganado bosque, que no es creíble.
            "depriv": (round(float(row["deprivation"]), 1)
                       if pd.notna(row.get("deprivation")) else None),
            "bosque_2000": (round(float(row["tree_cover_2000_pct"]), 1)
                            if pd.notna(row.get("tree_cover_2000_pct")) else None),
            "agua": (round(float(row["%water"]), 2)
                     if pd.notna(row.get("%water")) else None),
            "construido": (round(float(row["cob_construido_pct"]), 1)
                           if pd.notna(row.get("cob_construido_pct")) else None),
            "pobl": (round(float(row["pop_density_mean"]), 0)
                     if pd.notna(row.get("pop_density_mean")) else None),
            "viaje": (round(float(row["travel_time"]), 0)
                      if pd.notna(row.get("travel_time")) else None),
            # Las siete capas del Global Solar Atlas. Solo pvout y gti entran en el
            # índice; las demás van a la ficha porque caracterizan el recurso y explican
            # de dónde sale la producción estimada.
            "ghi": (round(float(row["ghi"]), 0) if pd.notna(row.get("ghi")) else None),
            "dni": (round(float(row["dni"]), 0) if pd.notna(row.get("dni")) else None),
            "dif": (round(float(row["dif"]), 0) if pd.notna(row.get("dif")) else None),
            "opta": (round(float(row["opta"]), 1) if pd.notna(row.get("opta")) else None),
            "rugosidad": round(float(row["elevation_std"]), 1) if pd.notna(row.get("elevation_std")) else None,
            "indice": float(row["indice_aptitud"]),
            "cumple": int(row["criterios_cumplidos"]),
            "elevacion": round(float(row["elevation_mean"]), 0) if pd.notna(row.get("elevation_mean")) else None,
            "dist_sub": round(float(row["sub_distancia_km"]), 2) if pd.notna(row.get("sub_distancia_km")) else None,
            # distancia al punto de conexión de cada perfil, para conmutar en el HTML
            **{f"dist_sub__{n}": (round(float(row[f"sub_distancia_km__{n}"]), 2)
                                  if pd.notna(row.get(f"sub_distancia_km__{n}")) else None)
               for n in PERFILES if f"sub_distancia_km__{n}" in row.index},
            "subestacion": row.get("sub_nombre_subestacion") or "Sin dato",
            "tension": float(row["sub_tension_kv"]) if pd.notna(row.get("sub_tension_kv")) else None,
            "barras": row.get("sub_configuracion") or "Sin dato",
            "operador": row.get("operador") or "Sin identificar",
            "cultivos": round(float(row.get("%crops", np.nan)), 1) if pd.notna(row.get("%crops")) else None,
            "bosque": round(float(row.get("%trees", np.nan)), 1) if pd.notna(row.get("%trees")) else None,
            "zona": row.get("zona", "Aislada"),
            "ha": float(row.get("ha_aptas", 0) or 0),
            "mwp": float(row.get("mwp_indicativo", 0) or 0),
            "gwh": float(row.get("gwh_anio", 0) or 0),
            "proy20": int(row["proyectos_20mw"]) if pd.notna(row.get("proyectos_20mw")) else 0,
            "restric_crudas": {
                k: int(row.get(k, 0) or 0)
                for k in ("area_protegida", "en_parque_nacional",
                          "territorio_indigena", "consejo_comunitario")
                if k in gw.columns
            },
            "lon": round(float(cent.iloc[i].x), 4),
            "lat": round(float(cent.iloc[i].y), 4),
        })

    payload = {
        "grillas": registros,
        "zonas": (zonas.reset_index().round(1).to_dict("records")
                  if zonas is not None and len(zonas) else []),
        # NaN de pandas no es JSON válido y llega al navegador como NaN, no como null,
        # así que las comprobaciones de dato ausente fallan. Se convierte antes.
        "barras": (conc.reset_index().round(1).head(14)
                   .astype(object).where(pd.notna(conc.reset_index().round(1).head(14)), None)
                   .to_dict("records") if len(conc) else []),
        "criterios": CRITERIOS,
        "satelital": sat,
        "satelital_fuente": _atribucion_satelital() if sat else "",
        "supuestos": {
            "ha_por_grilla": HA_POR_GRILLA,
            "ha_por_mwp": HA_POR_MWP,
            "indice_prioritaria": INDICE_PRIORITARIA,
            "n_referencia": REFERENCIA_N,
            "mw_referencia": REFERENCIA_MW,
            "perfil": PERFIL_ACTIVO,
            "kv_min": KV_CONEXION_MIN,
            "kv_max": KV_CONEXION_MAX,
            # Los dos perfiles enteros viajan al HTML para que el conmutador funcione
            # sin volver a correr nada. Cada uno trae sus umbrales y su salvedad.
            "perfiles": {n: {"etiqueta": p["etiqueta"],
                             "umbrales": p["umbrales"],
                             "pesos": p.get("pesos", {}),
                             "mw_proyecto": p.get("mw_proyecto"),
                             "kv_min": p["kv_min"], "kv_max": p["kv_max"],
                             "n_referencia": p["n_referencia"],
                             "mw_referencia": p["mw_referencia"],
                             "ha_proyecto": p["ha_proyecto"],
                             "aviso": p.get("aviso_conexion", "")}
                         for n, p in PERFILES.items()},
        },
    }
    with open(SALIDA / "grillas_candidatas.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"  JSON  -> {SALIDA / 'grillas_candidatas.json'}")

    # ---- resumen en consola ----
    print()
    print("-" * 74)
    print("RESUMEN")
    print("-" * 74)
    print(g["clasificacion"].value_counts().to_string())
    print()
    print("Por departamento (top 8)")
    print(g["departamento"].value_counts().head(8).to_string())
    print()
    print("Por operador de red (top 8)")
    print(g["operador"].value_counts().head(8).to_string())
    print()
    if zonas is not None and len(zonas):
        print("Zonas de prospección (por potencial)")
        print(zonas.head(8).round(0).to_string())
        print()
    # Ojo con la lectura: es potencial técnico de toda la superficie apta, no una
    # cartera de proyectos. Sirve para dimensionar la oportunidad, no para prometerla.
    print("Potencial técnico teórico  %.0f ha aptas  ·  %.0f MWp  ·  %.0f GWh/año"
          % (g["ha_aptas"].sum(), g["mwp_indicativo"].sum(), g["gwh_anio"].sum()))
    print("  (es el techo físico de la superficie apta, no una cartera comprometida)")
    print()
    print("Producción FV  min %.0f   media %.0f   max %.0f  kWh/kWp/año"
          % (g["pvout"].min(), g["pvout"].mean(), g["pvout"].max()))
    print("Distancia a subestación  min %.1f  media %.1f  max %.1f km"
          % (g["sub_distancia_km"].min(), g["sub_distancia_km"].mean(), g["sub_distancia_km"].max()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
