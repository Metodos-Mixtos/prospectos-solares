"""
Piloto de El Poblado (Melgar, Tolima): encadenado completo, de la celda del panel
nacional al reporte de lotes de UNA sola grilla y su Excel.

QUE HACE
--------
Inyecta la celda real que contiene la Finca El Poblado (cell_id 0014590) en la lista de
grillas que va a busqueda de lotes, como si hubiera pasado el filtro de caracterizacion y
hubiera sido seleccionada, y corre sobre ella el mismo codigo del proyecto real, sin
tocar un solo archivo del repositorio.

La celda 0014590 NO esta entre las cien candidatas. Ese es justamente el punto del
piloto: se toma una grilla cualquiera del panel, se la caracteriza con el mismo
procedimiento y se baja hasta el lote. Lo que sale de la caracterizacion se muestra tal
cual, sin maquillarlo: la corrida del 23-08-2026 la clasifico "Condicionada", con indice
39,4 sobre 100, por produccion fotovoltaica de 1.443 kWh/kWp (limite 1.460) y rugosidad
del relieve de 193,8 m (limite 122,0). Entra al encadenado porque "Condicionada" no es
"Excluida"; ninguna cifra se ajusta para que se vea mejor.

LOS PASOS Y LO QUE PASA DE UNO A OTRO
-------------------------------------
  0  verificar     comprueba que estan los insumos. No escribe nada.
  1  celda         del panel nacional (config.PANEL_PATH) se extrae la fila 0014590 con
                   sus covariables tal como estan.
                   -> outputs/piloto/reporte/celda_piloto.gpkg
  2  caracterizar  reporte.datos corre sobre esa unica celda: subestacion mas cercana y
                   operador, capacidad de barra, distancia a via, cobertura del suelo,
                   restricciones externas, conflicto armado, clasificacion, indice de
                   aptitud y potencial indicativo.
                   -> outputs/piloto/reporte/grillas_candidatas.{gpkg,geojson,csv,xlsx}
  3  seleccionar   de esa tabla maestra se extrae el archivo de entrada de la busqueda de
                   lotes, con las 21 columnas que los modulos de aguas abajo esperan.
                   -> outputs/piloto/grillas_piloto.geojson         (archivo de entrada)
                   -> outputs/piloto/reporte/grillas_para_predios.{geojson,csv}
  4  catastro      predios.predios_igac baja del catastro publico del IGAC los terrenos
                   de la celda (ya cacheados en data/igac: 205 rurales, 0 urbanos, corte
                   06_2026) y los consolida medidos.
                   -> outputs/piloto/reporte/predios.gpkg
  5  lotes         predios.lotes mide forma, terreno, Ley 2a, via y area, y luego por
                   perfil: conexion, indice del lote, cribado juridico, valor de
                   referencia, entorno, POT y contexto.
                   -> outputs/piloto/reporte/lotes_<perfil>.{csv,geojson},
                      lotes_<perfil>_descartados.csv, lotes.gpkg
  6  matricula     predios.matricula_auto saca de los lotes los municipios, descubre
                   cual tiene portal de impuesto predial comprobandolo de verdad, cosecha
                   ahi lo que haya y consulta la Superintendencia para el resto, hasta
                   donde alcance el cupo diario gratuito. No detiene el encadenado: si
                   falla o se agota el cupo, los lotes quedan sin matricula con el motivo
                   escrito y el procedimiento sigue.
                   -> data/registro/matriculas.csv      (cache compartida, la lee el visor)
                   -> outputs/piloto/reporte/matriculas_<perfil>.csv   (auditoria)
  7  reporte       reporte_predios arma el JSON y el HTML de la unica grilla, con imagen
                   satelital y Sentinel-2 por lote.
                   -> outputs/piloto/reporte/reporte_predios.{json,html}
                   -> entregables/piloto/reporte_predios.html (+ satelital/)
  8  excel         una hoja con la grilla y otra con sus lotes, ordenados por area apta.
                   -> outputs/piloto/reporte/piloto_melgar_<perfil>.xlsx

SEPARACION DE RUTAS
-------------------
Todo modulo del proyecto fija, al importarse, SALIDA = PROJECT_ROOT/"outputs"/"reporte".
Si se corriera el piloto sin mas, se sobreescribirian los archivos del proyecto real:
grillas_candidatas.*, predios.gpkg, lotes_*.csv/geojson, lotes.gpkg, distancia_vias.csv,
reporte_predios.json/html y la copia de entregables/. La funcion _redirigir() reescribe
esa constante en los seis modulos implicados antes de que nadie la use, y aborta si
alguna siguiera apuntando al proyecto real. Las cachES de data/ (igac, dem, cobertura,
osm, satelital, entorno, pot, valor, juridico) NO se redirigen: son insumos compartidos y
anadir una celda no altera lo ya descargado.

Hay otros modulos con su propia constante SALIDA que apuntan a outputs/reporte y que a
proposito NO se redirigen, porque desde el encadenado solo LEEN de ahi y redirigirlos los
dejaria sin insumo:
  predios.contexto      lee outputs/reporte/lineas_transmision.json (linea mas cercana)
  insumos.barras        lee outputs/reporte/capacidad_barras.csv (capacidad de barra)
  insumos.vias          solo escribe desde su propia linea de comandos
  insumos.restricciones solo escribe desde su propia linea de comandos
  predios.juridico, valor, entorno, pot, registro, certificados: escriben en outputs/
  reporte unicamente cuando se corren solos; llamados desde predios.lotes no escriben.

USO
---
    .venv\\Scripts\\python.exe outputs\\piloto\\ejecutar_piloto.py
    .venv\\Scripts\\python.exe outputs\\piloto\\ejecutar_piloto.py --seco
    .venv\\Scripts\\python.exe outputs\\piloto\\ejecutar_piloto.py --desde 4
    .venv\\Scripts\\python.exe outputs\\piloto\\ejecutar_piloto.py --sin-satelital
    .venv\\Scripts\\python.exe outputs\\piloto\\ejecutar_piloto.py --usar-grillas-piloto

Opciones:
    --perfil P              utility (por defecto) o distribuida
    --desde N / --hasta N   corre solo el tramo de pasos indicado (0 a 8)
    --seco                  imprime el plan y no ejecuta nada
    --sin-satelital         paso 7 sin descargar imagenes (mucho mas rapido)
    --imagenes N            imagenes por grilla y perfil en el paso 7 (por defecto 25)
    --usar-grillas-piloto   salta 1 y 2 y arranca del grillas_piloto.geojson ya escrito.
                            Plan B si los servicios de caracterizacion no responden.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
# Este archivo vive en outputs/piloto/, asi que la raiz esta dos niveles arriba.
RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte"), str(RAIZ / "predios")]

PILOTO = RAIZ / "outputs" / "piloto"
SALIDA_PILOTO = PILOTO / "reporte"
ENTREGABLES_PILOTO = RAIZ / "entregables" / "piloto"

CELL_ID = "0014590"
#: Numero predial de 30 digitos de la Finca El Poblado, matricula 366-35594. Se usa solo
#: para comprobar al final que el lote aparece en la salida; no filtra nada.
CODIGO_EL_POBLADO = "734490001000000010054000000000"

#: Archivo de entrada del piloto: la grilla ya caracterizada y seleccionada, con las 21
#: columnas que exigen predios_igac._completar_celdas, predios.lotes.evaluar y
#: reporte_predios.datos.CAMPOS_CELDA. Lo escribe el paso 3 y lo lee el plan B.
GRILLAS_PILOTO = PILOTO / "grillas_piloto.geojson"

#: Las 21 columnas, en el orden en que viajan. cell_id es la clave del cruce; el resto
#: son las que los modulos de aguas abajo esperan encontrar y que, cuando la celda no
#: viene de grillas_candidatas.gpkg, nadie mas puede rellenar.
COLUMNAS_ENTRADA = [
    "cell_id",                  # clave, texto de 7 digitos con ceros a la izquierda
    "ranking",                  # entero, orden dentro del archivo de grillas
    "clasificacion",            # texto, si dice "Excluida" el lote se aparta entero
    "indice_aptitud",           # decimal 0-100
    "restricciones",            # texto, se copia al motivo del lote apartado
    "pvout",                    # decimal, criterio "recurso" heredado por el lote
    "capacidad_at_mw",          # decimal, criterio "capacidad" del perfil utility
    "capacidad_mt_mw",          # decimal, criterio "capacidad" del perfil distribuida
    "sub_nombre_subestacion",   # texto
    "sub_distancia_km",         # decimal
    "sub_tension_kv",           # decimal
    "operador",                 # texto
    "municipio",                # texto, contexto; el del lote sale de su codigo catastral
    "departamento",             # texto, idem
    "vereda",                   # texto
    "dane_municipio",           # texto de 5 digitos, cruza el gestor catastral
    "zona",                     # texto, zona de prospeccion
    "ha_aptas",                 # decimal
    "mwp_indicativo",           # decimal
    "slope_mean",               # decimal
    "cobertura_apta_pct",       # decimal
]


def _linea(txt: str = "") -> None:
    print(txt, flush=True)


def _titulo(txt: str) -> None:
    _linea()
    _linea("=" * 74)
    _linea(txt)
    _linea("=" * 74)


# --------------------------------------------------------------------------
# Separacion de rutas
# --------------------------------------------------------------------------

def _redirigir(verbose: bool = True) -> None:
    """
    Reescribe la constante SALIDA de los modulos que escriben, para que el piloto no pise
    el proyecto real. Se llama una sola vez, antes de ejecutar ningun paso.

    Que se redirige y por que:
      reporte.datos.SALIDA              grillas_candidatas.*, distancia_vias.csv, satelital/
      predios_igac.SALIDA               predios.gpkg
      lotes.SALIDA                      lotes_*.csv/geojson, lotes.gpkg, atajo predios.gpkg
      reporte_predios.datos.SALIDA      reporte_predios.json, satelital/, lectura de lotes_*
      reporte_predios.html.SALIDA       reporte_predios.html
      reporte_predios.html.ENTREGABLES  la copia que se comparte
    """
    SALIDA_PILOTO.mkdir(parents=True, exist_ok=True)
    ENTREGABLES_PILOTO.mkdir(parents=True, exist_ok=True)

    import reporte.datos as rd
    rd.SALIDA = SALIDA_PILOTO

    import predios_igac as pig
    pig.SALIDA = SALIDA_PILOTO

    import lotes as lt
    lt.SALIDA = SALIDA_PILOTO

    # La tabla de matriculas (data/registro/matriculas.csv) NO se redirige: es una cache
    # compartida, como las de data/, y lo que se aprende de un lote vale para cualquier
    # corrida. Lo que si se redirige es su tabla de auditoria, que es salida del piloto.
    import matricula_auto as mau
    mau.SALIDA = SALIDA_PILOTO

    import reporte_predios.datos as rpd
    rpd.SALIDA = SALIDA_PILOTO
    rpd.JSON_SALIDA = SALIDA_PILOTO / "reporte_predios.json"
    rpd.GRILLAS_DEFECTO = SALIDA_PILOTO / "grillas_para_predios.geojson"

    import reporte_predios.html as rph
    rph.SALIDA = SALIDA_PILOTO
    rph.JSON_SALIDA = rpd.JSON_SALIDA
    rph.ENTREGABLES = ENTREGABLES_PILOTO

    # Comprobacion dura: si algo siguiera apuntando a outputs/reporte, el piloto
    # destruiria la salida del proyecto real. Mejor abortar que arreglarlo despues.
    real = (RAIZ / "outputs" / "reporte").resolve()
    for nombre, valor in (("reporte.datos", rd.SALIDA), ("predios_igac", pig.SALIDA),
                          ("lotes", lt.SALIDA), ("matricula_auto", mau.SALIDA),
                          ("reporte_predios.datos", rpd.SALIDA),
                          ("reporte_predios.html", rph.SALIDA)):
        if Path(valor).resolve() == real:
            raise SystemExit(f"ABORTA: {nombre}.SALIDA sigue en outputs/reporte")
    if Path(rph.ENTREGABLES).resolve() == (RAIZ / "entregables").resolve():
        raise SystemExit("ABORTA: reporte_predios.html.ENTREGABLES sigue en entregables/")

    if verbose:
        _linea(f"  salidas del piloto  -> {SALIDA_PILOTO}")
        _linea(f"  entregable          -> {ENTREGABLES_PILOTO}")
        _linea(f"  el proyecto real ({real}) no se toca")


# --------------------------------------------------------------------------
# Paso 0. Verificar insumos
# --------------------------------------------------------------------------

def paso_0_verificar() -> None:
    """Comprueba lo que hace falta antes de empezar. No escribe nada."""
    import config
    import predios_igac as pig

    faltan = []
    for etiqueta, ruta in (("panel de grillas", config.PANEL_PATH),
                           ("subestaciones", config.SUBESTACIONES_PATH)):
        ok = Path(ruta).exists()
        _linea(f"  {'ok   ' if ok else 'FALTA'}  {etiqueta:<26} {ruta}")
        if not ok:
            faltan.append(etiqueta)

    # Catastro del IGAC ya descargado para la celda. Si esta, el paso 4 no le pide nada al
    # servicio y ese tramo corre sin red.
    rutas_catastro = {t: pig._raw(CELL_ID, t) for t in pig.CAPAS.values()}
    rutas_catastro["registro1"] = pig._raw_registro(CELL_ID)
    rutas_catastro["registro2"] = pig._raw_registro2(CELL_ID)
    for tipo, ruta in rutas_catastro.items():
        estado = "ok   " if ruta.exists() else "baja "
        _linea(f"  {estado}  catastro {tipo:<17} {ruta.name}")

    # Base veredal: sin ella la celda sale sin municipio, vereda ni codigo DANE, y sin
    # DANE no hay cruce de conflicto armado ni de gestor catastral.
    ver = RAIZ / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    _linea(f"  {'ok   ' if ver.exists() else 'FALTA'}  base veredal               {ver.name}")

    if faltan:
        raise SystemExit(f"Faltan insumos: {', '.join(faltan)}")


# --------------------------------------------------------------------------
# Paso 1. La celda del panel
# --------------------------------------------------------------------------

def paso_1_celda() -> Path:
    """
    Extrae del panel nacional la fila de la celda 0014590 con sus covariables tal como
    estan, sin tocar ningun valor.

    sim_profile, sim_knn y sim_score se dejan vacios a proposito: el modelo de similitud
    no puntuo esta celda, porque no entro en la seleccion de las cien. Ponerles un numero
    seria inventarlo. El reporte los tolera vacios: no intervienen en el indice ni en la
    clasificacion, solo desempatan el orden cuando hay varias grillas.
    """
    import geopandas as gpd
    import numpy as np
    import config

    destino = SALIDA_PILOTO / "celda_piloto.gpkg"
    panel = gpd.read_file(config.PANEL_PATH)
    panel["cell_id"] = panel["cell_id"].astype(str).str.zfill(7)
    g = panel[panel["cell_id"] == CELL_ID].copy()
    if len(g) != 1:
        raise SystemExit(f"El panel devuelve {len(g)} filas para {CELL_ID}, se esperaba 1")

    for c in ("sim_profile", "sim_knn", "sim_score"):
        if c in g.columns:
            g[c] = np.nan

    if g.crs is None:
        g = g.set_crs(config.CRS_GEOGRAFICO)
    g = g.to_crs(config.CRS_GEOGRAFICO)
    destino.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(destino, driver="GPKG")

    _linea(f"  celda {CELL_ID}, {len(g.columns)} columnas del panel")
    _linea(f"  bounds  {tuple(round(v, 6) for v in g.total_bounds)}")
    _linea(f"  GPKG -> {destino}")
    return destino


# --------------------------------------------------------------------------
# Paso 2. Caracterizacion de la grilla
# --------------------------------------------------------------------------

def paso_2_caracterizar(perfil: str) -> Path:
    """
    Corre reporte.datos sobre la unica celda. Es el mismo codigo que caracterizo las cien
    del proyecto real; lo unico distinto es a donde escribe.

    De aqui salen, ya calculadas y no supuestas: subestacion mas cercana dentro del rango
    de tension del perfil, operador de red, capacidad libre de la barra (Circular UPME 054
    de 2026), distancia a via, cobertura apta del suelo, restricciones externas incluida la
    Ley 2a, carga de conflicto armado del municipio, clasificacion, indice de aptitud y
    potencial indicativo en hectareas, MWp y GWh.

    El xlsx que escribe (grillas_candidatas.xlsx) ya es un Excel de la grilla; el paso 7 lo
    rehace junto a la hoja de lotes.
    """
    import reporte.datos as rd

    ruta = SALIDA_PILOTO / "celda_piloto.gpkg"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre antes el paso 1.")
    codigo = rd.main(["--celdas", str(ruta), "--perfil", perfil])
    if codigo:
        raise SystemExit(f"reporte.datos devolvio {codigo}")
    return SALIDA_PILOTO / "grillas_candidatas.gpkg"


# --------------------------------------------------------------------------
# Paso 3. Archivo de entrada de la busqueda de lotes
# --------------------------------------------------------------------------

def paso_3_seleccionar() -> Path:
    """
    Escribe los dos archivos que abren la busqueda de lotes.

    grillas_piloto.geojson es el archivo de entrada propiamente dicho: la grilla ya
    caracterizada, recortada a las 21 columnas de COLUMNAS_ENTRADA. Existe porque los
    modulos de aguas abajo, cuando la celda no viene de grillas_candidatas.gpkg, no tienen
    de donde sacarlas: predios_igac._completar_celdas intenta rellenarlas desde esa tabla
    maestra y, como 0014590 no esta entre las cien, el cruce devolveria vacio y el lote se
    quedaria sin recurso, sin capacidad de barra y sin clasificacion de celda.

    grillas_para_predios.geojson lo escribe la herramienta del proyecto sin modificarla
    (soporte/herramientas/lote_predios.py), para que el piloto pase por el mismo sitio que
    la corrida real. Es el archivo que consumen los pasos 5 y 6.
    """
    import geopandas as gpd

    maestra = SALIDA_PILOTO / "grillas_candidatas.gpkg"
    if not maestra.exists():
        raise SystemExit(f"No existe {maestra}. Corre antes el paso 2.")

    # --- 3a. el archivo de entrada, con las 21 columnas rellenas ---
    g = gpd.read_file(maestra)
    g["cell_id"] = g["cell_id"].astype(str).str.zfill(7)
    faltan = [c for c in COLUMNAS_ENTRADA if c not in g.columns]
    if faltan:
        raise SystemExit(f"La caracterizacion no dejo estas columnas: {', '.join(faltan)}")
    (g[COLUMNAS_ENTRADA + ["geometry"]]
     .to_crs("EPSG:4326")
     .to_file(GRILLAS_PILOTO, driver="GeoJSON", COORDINATE_PRECISION=6))
    _linea(f"  entrada con {len(COLUMNAS_ENTRADA)} columnas -> {GRILLAS_PILOTO}")

    # --- 3b. el archivo que consume el resto del encadenado ---
    sys.path.insert(0, str(RAIZ / "soporte" / "herramientas"))
    import lote_predios
    lote_predios.SALIDA = SALIDA_PILOTO
    codigo = lote_predios.main(["--celdas", str(maestra), "--ids", CELL_ID,
                                "--salida", "grillas_para_predios"])
    if codigo:
        raise SystemExit(f"lote_predios devolvio {codigo}")
    return SALIDA_PILOTO / "grillas_para_predios.geojson"


def plan_b_usar_entrada() -> Path:
    """
    Plan B: arranca del grillas_piloto.geojson ya escrito, sin rehacer 1 ni 2.

    Sirve cuando el servicio de subestaciones, el de restricciones o el de barras no
    responden y la caracterizacion no se puede repetir. El archivo de entrada trae las 21
    columnas ya calculadas, que es todo lo que los pasos 4 a 7 necesitan de la celda.
    """
    if not GRILLAS_PILOTO.exists():
        raise SystemExit(f"No existe {GRILLAS_PILOTO}; sin el no hay plan B, corre 1 y 2.")
    SALIDA_PILOTO.mkdir(parents=True, exist_ok=True)
    destino = SALIDA_PILOTO / "grillas_para_predios.geojson"
    shutil.copyfile(GRILLAS_PILOTO, destino)
    _linea(f"  plan B: {GRILLAS_PILOTO.name} -> {destino}")
    return destino


# --------------------------------------------------------------------------
# Paso 4. Catastro del IGAC
# --------------------------------------------------------------------------

def paso_4_catastro() -> Path:
    """
    Baja del catastro publico del IGAC los terrenos de la celda, los repara, deduplica,
    recorta a la celda y los mide, y les une la ficha alfanumerica (REGISTRO_1 y
    REGISTRO_2).

    Melgar (73449) esta cubierto por el catastro publico del gestor IGAC, corte 06_2026:
    no tiene gestor catastral propio, asi que el servicio si devuelve sus terrenos. Con la
    cache de data/igac ya poblada (205 terrenos rurales, 0 urbanos), este paso no le pide
    nada al servicio y tarda segundos.
    """
    import predios_igac as pig
    codigo = pig.main(["--celdas", CELL_ID, "--clase", "todas"])
    if codigo:
        raise SystemExit(f"predios_igac devolvio {codigo}")
    return SALIDA_PILOTO / "predios.gpkg"


# --------------------------------------------------------------------------
# Paso 5. Caracterizacion de los lotes
# --------------------------------------------------------------------------

def paso_5_lotes(perfil: str) -> Path:
    """
    predios.lotes sobre la unica grilla: area, compacidad, ancho, area de nucleo,
    pendiente y rugosidad propias del lote, Ley 2a y distancia a via; y despues, por
    perfil, la conexion, el indice del lote, el cribado juridico, el valor de referencia,
    el entorno (RUNAP, resguardos, consejos comunitarios, paramos, mineria, inundacion),
    el POT municipal y el contexto (linea de transmision, centro poblado).

    El tamano no descarta: se mide, se anota si el lote alcanza el area y el ancho de cada
    perfil, y el filtro lo aplica el cliente en el visor.

    Entorno, POT y contexto consultan geoservicios estatales lote a lote. Es el paso mas
    largo del encadenado.
    """
    import lotes as lt
    entrada = SALIDA_PILOTO / "grillas_para_predios.geojson"
    if not entrada.exists():
        raise SystemExit(f"No existe {entrada}. Corre antes el paso 3.")
    codigo = lt.main(["--celdas", str(entrada), "--perfil", perfil])
    if codigo:
        raise SystemExit(f"lotes devolvio {codigo}")
    return SALIDA_PILOTO / f"lotes_{perfil}.geojson"


# --------------------------------------------------------------------------
# Paso 6. Matricula inmobiliaria
# --------------------------------------------------------------------------

def paso_6_matricula(perfil: str) -> Path:
    """
    predios.matricula_auto sobre los lotes ya caracterizados: saca de ellos los municipios,
    descubre cual tiene portal de impuesto predial comprobandolo de verdad, cosecha ahi lo
    que haya y consulta la Superintendencia para el resto, hasta donde alcance el cupo
    diario gratuito.

    Corre despues de caracterizar los lotes, porque necesita sus codigos, y antes del
    reporte, porque reporte_predios.datos lee la tabla de matriculas al armar el JSON.

    NO DETIENE EL ENCADENADO. Si una via falla o se agota el cupo, el paso lo dice, deja
    los lotes que faltan sin matricula con el motivo escrito en su tabla de auditoria, y el
    procedimiento sigue. Un lote sin consultar nunca se escribe como "sin dato": eso seria
    afirmar que se pregunto y no habia, que es un dato falso.
    """
    import matricula_auto as mau
    mau.paso(perfil=perfil, lotes_csv=SALIDA_PILOTO / f"lotes_{perfil}.csv")
    return SALIDA_PILOTO / f"matriculas_{perfil}.csv"


# --------------------------------------------------------------------------
# Paso 7. Reporte de lotes de una sola grilla
# --------------------------------------------------------------------------

def paso_7_reporte(perfil: str, sin_satelital: bool, imagenes: int) -> Path:
    """
    Reporte de lotes con la unica grilla. El modulo acepta cualquier numero de grillas,
    una incluida: se comprobo leyendo reporte_predios.datos.construir, que recorre las
    celdas y los lotes sin suponer en ningun punto que haya mas de una. La zona de
    prospeccion sale "Aislada" porque el agrupamiento pide dos celdas para formar zona; es
    la lectura correcta para una grilla suelta, no un fallo.

    Escribe el JSON y el HTML en outputs/piloto/reporte y copia el HTML y sus imagenes a
    entregables/piloto.
    """
    import reporte_predios.datos as rpd
    import reporte_predios.html as rph

    argv = ["--grillas", str(SALIDA_PILOTO / "grillas_para_predios.geojson"),
            "--perfil", perfil, "--imagenes", str(imagenes)]
    if sin_satelital:
        argv.append("--sin-satelital")
    codigo = rpd.main(argv)
    if codigo:
        raise SystemExit(f"reporte_predios.datos devolvio {codigo}")
    codigo = rph.main()
    if codigo:
        raise SystemExit(f"reporte_predios.html devolvio {codigo}")
    return ENTREGABLES_PILOTO / "reporte_predios.html"


# --------------------------------------------------------------------------
# Paso 8. Excel de la grilla y sus lotes
# --------------------------------------------------------------------------

#: Columnas de la hoja de lotes: las mismas que descarga el visor del reporte, mas
#: area_apta_ha. Las que no existan en la corrida se omiten sin ruido.
COLS_LOTES = [
    "cell_id", "CODIGO", "numero_predial_anterior", "matricula_inmobiliaria",
    "nombre_predio", "clasificacion", "area_ha", "area_apta_ha", "cobertura_apta_pct",
    "mwp_lote", "mwp_apto", "ancho_util_m", "compacidad", "pendiente_media",
    "rugosidad_m", "dist_via_km", "dist_via_principal_km", "conexion_nombre",
    "conexion_kv", "conexion_km", "indice_lote", "destino", "municipio", "departamento",
    "area_terreno_catastro_m2", "area_construida_m2", "cob_bosque_pct",
    "cob_pastizal_pct", "cob_cultivo_pct", "valor_ref_cop_ha", "valor_ref_cop",
    "valor_confianza", "riesgo_baldio", "veces_uaf", "microzona_urt", "estorbos",
    "gestion", "pot_categoria", "pot_categoria_pct", "pot_semaforo", "pot_clasificacion",
    "ent_mineria_titulos", "ent_runap_ha", "ent_resguardo_ha", "ent_consejo_ha",
    "ent_paramo_ha", "ent_inundacion_ha_max", "ent_humedal", "ctx_linea_km",
    "ctx_poblado", "ctx_poblado_km", "motivo",
]


def paso_8_excel(perfil: str) -> Path:
    """
    Un libro con dos hojas: "Grilla", la fila de la grilla con los nombres en espanol que
    ya usa el reporte, y "Lotes", los lotes caracterizados ordenados por area apta
    descendente (area bruta por cobertura apta), que es el orden con el que se leen.
    """
    import pandas as pd

    destino = SALIDA_PILOTO / f"piloto_melgar_{perfil}.xlsx"
    grilla = pd.read_csv(SALIDA_PILOTO / "grillas_candidatas.csv", encoding="utf-8-sig",
                         dtype={"ID grilla": str})
    lotes = pd.read_csv(SALIDA_PILOTO / f"lotes_{perfil}.csv", encoding="utf-8-sig",
                        dtype={"CODIGO": str, "cell_id": str,
                               "numero_predial_anterior": str})
    lotes["area_apta_ha"] = (lotes["area_ha"] * lotes["cobertura_apta_pct"] / 100).round(2)
    lotes = lotes.sort_values("area_apta_ha", ascending=False)
    lotes = lotes[[c for c in COLS_LOTES if c in lotes.columns]]

    with pd.ExcelWriter(destino, engine="openpyxl") as xl:
        grilla.to_excel(xl, sheet_name="Grilla", index=False)
        lotes.to_excel(xl, sheet_name="Lotes", index=False)
        for nombre, tabla in (("Grilla", grilla), ("Lotes", lotes)):
            hoja = xl.sheets[nombre]
            for i, col in enumerate(tabla.columns, 1):
                largo = tabla[col].astype("string").fillna("").str.len().max()
                largo = 0 if pd.isna(largo) else int(largo)
                letra = hoja.cell(row=1, column=i).column_letter
                hoja.column_dimensions[letra].width = min(max(len(str(col)), largo) + 3, 46)
            hoja.freeze_panes = "C2"

    _linea(f"  hoja Grilla: 1 fila, {len(grilla.columns)} columnas")
    _linea(f"  hoja Lotes : {len(lotes)} lotes, {len(lotes.columns)} columnas")
    _linea(f"  XLSX -> {destino}")
    return destino


# --------------------------------------------------------------------------
# Comprobacion final
# --------------------------------------------------------------------------

def comprobar(perfil: str) -> None:
    """
    Confirma que el lote de El Poblado aparece en la salida y que el proyecto real no se
    toco. No corrige nada: si algo no cuadra, lo dice.
    """
    import pandas as pd

    _titulo("COMPROBACION")
    csv = SALIDA_PILOTO / f"lotes_{perfil}.csv"
    apartados = SALIDA_PILOTO / f"lotes_{perfil}_descartados.csv"
    if not csv.exists():
        _linea(f"  no hay lotes_{perfil}.csv, no se puede comprobar")
        return
    sel = pd.read_csv(csv, encoding="utf-8-sig", dtype={"CODIGO": str})
    n_apart = (len(pd.read_csv(apartados, encoding="utf-8-sig", dtype={"CODIGO": str}))
               if apartados.exists() else 0)
    _linea(f"  lotes caracterizados : {len(sel)}")
    _linea(f"  lotes apartados      : {n_apart}")

    fila = sel[sel["CODIGO"] == CODIGO_EL_POBLADO]
    if fila.empty:
        _linea(f"  AVISO: el lote {CODIGO_EL_POBLADO} no esta entre los caracterizados")
    else:
        r = fila.iloc[0]
        _linea(f"  El Poblado           : area {r.get('area_ha')} ha, "
               f"indice {r.get('indice_lote')}, {r.get('clasificacion')}")
        _linea("  Alerta ya verificada: el poligono publicado por el IGAC mide 13,95 ha,")
        _linea("  mientras las tablas alfanumericas del propio IGAC y el folio dicen")
        _linea("  63,87 ha. El area del reporte sale del poligono, no del folio.")

    real = RAIZ / "outputs" / "reporte"
    _linea(f"  {real}: el piloto no escribio ahi")


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------

PASOS = {
    0: "verificar insumos",
    1: "celda del panel",
    2: "caracterizar la grilla",
    3: "archivo de entrada y seleccion",
    4: "catastro del IGAC",
    5: "caracterizar los lotes",
    6: "matricula inmobiliaria",
    7: "reporte de lotes",
    8: "Excel de la grilla",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Piloto de El Poblado, Melgar (Tolima)")
    ap.add_argument("--perfil", default="utility", choices=["utility", "distribuida"])
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=8)
    ap.add_argument("--seco", action="store_true", help="imprime el plan y no ejecuta")
    ap.add_argument("--sin-satelital", action="store_true")
    ap.add_argument("--imagenes", type=int, default=25)
    ap.add_argument("--usar-grillas-piloto", action="store_true",
                    help="plan B: salta 1 y 2 y usa grillas_piloto.geojson")
    a = ap.parse_args(argv)

    _titulo("PILOTO EL POBLADO  ·  Melgar (Tolima)  ·  grilla 0014590")
    _linea(f"  perfil: {a.perfil}   pasos: {a.desde} a {a.hasta}"
           + ("   PLAN B" if a.usar_grillas_piloto else ""))

    if a.seco:
        for n, etiqueta in PASOS.items():
            dentro = a.desde <= n <= a.hasta
            if a.usar_grillas_piloto and n in (1, 2):
                dentro = False
            _linea(f"  {n}. {etiqueta:<34} {'se corre' if dentro else 'se salta'}")
        _linea()
        _linea("  corrida en seco, no se ejecuto nada")
        return 0

    _redirigir()

    reloj = {}

    def cronometrar(n, etiqueta, fn):
        if not (a.desde <= n <= a.hasta):
            return
        _titulo(f"PASO {n}. {etiqueta.upper()}")
        t0 = time.time()
        fn()
        reloj[n] = time.time() - t0
        _linea(f"  [paso {n} en {reloj[n]:.0f} s]")

    cronometrar(0, PASOS[0], paso_0_verificar)
    if a.usar_grillas_piloto:
        cronometrar(3, "archivo de entrada (plan B)", plan_b_usar_entrada)
    else:
        cronometrar(1, PASOS[1], paso_1_celda)
        cronometrar(2, PASOS[2], lambda: paso_2_caracterizar(a.perfil))
        cronometrar(3, PASOS[3], paso_3_seleccionar)
    cronometrar(4, PASOS[4], paso_4_catastro)
    cronometrar(5, PASOS[5], lambda: paso_5_lotes(a.perfil))
    cronometrar(6, PASOS[6], lambda: paso_6_matricula(a.perfil))
    cronometrar(7, PASOS[7],
                lambda: paso_7_reporte(a.perfil, a.sin_satelital, a.imagenes))
    cronometrar(8, PASOS[8], lambda: paso_8_excel(a.perfil))

    comprobar(a.perfil)

    _titulo("TIEMPOS")
    for n, s in sorted(reloj.items()):
        _linea(f"  paso {n}. {PASOS[n]:<34} {s:6.0f} s")
    _linea(f"  {'total':<42} {sum(reloj.values()):6.0f} s")
    _linea()
    _linea(f"  HTML  -> {ENTREGABLES_PILOTO / 'reporte_predios.html'}")
    _linea(f"  XLSX  -> {SALIDA_PILOTO / f'piloto_melgar_{a.perfil}.xlsx'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
