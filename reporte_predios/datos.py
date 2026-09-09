"""
Datos del reporte de lotes: un JSON compacto a partir de las grillas seleccionadas.

Entrada: el GeoJSON o CSV exportado desde el reporte de grillas (cualquier número de
grillas). Salida: outputs/reporte/reporte_predios.json con las celdas, todos los predios
caracterizados de cada perfil (geometría simplificada a ~5 m) y la imagen satelital
descargada de los mayores de cada grilla; los demás la cargan del servicio al abrir la
ficha, para que el HTML no crezca con el número de grillas.

    python -m reporte_predios.datos --grillas outputs/reporte/grillas_para_predios.geojson
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping

import config
import reporte.datos as rg
import registro   # precio del certificado, definido en un solo sitio
# Las clases de cobertura del suelo y su redacción se definen una sola vez, en el módulo
# que evalúa los lotes; aquí se leen para no repetir la lista ni la prosa.
import lotes as pl
from lotes import CLASES_COBERTURA, COLUMNAS_COBERTURA, ETIQUETA_CRITERIO

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
GRILLAS_DEFECTO = SALIDA / "grillas_para_predios.geojson"
JSON_SALIDA = SALIDA / "reporte_predios.json"

#: Tolerancia de simplificación en grados (~2 m) para lotes de 50 ha o más; los menores
#: se simplifican menos, en proporción a la raíz de su área, para que el error de área se
#: mantenga por debajo del 0,5% también en los de 2 ha.
TOLERANCIA = 0.00002


def _tolerancia(area_ha) -> float:
    try:
        a = float(area_ha)
    except (TypeError, ValueError):
        return TOLERANCIA
    return TOLERANCIA * min(1.0, max(0.1, (a / 50.0) ** 0.5))

#: Matrículas inmobiliarias ya conocidas (respuesta de la SNR o consulta manual): CSV con
#: columnas CODIGO;matricula_inmobiliaria[;fuente;fecha]. Es insumo, vive en data/ y en el
#: bucket, nunca en el repositorio. Sin él, la ficha explica cómo obtener la matrícula.
MATRICULAS = config.PROJECT_ROOT / "data" / "registro" / "matriculas.csv"

#: Imágenes satelitales descargadas por grilla y perfil: las de mayor área. El resto
#: se pide al servicio desde el navegador al abrir la ficha (--imagenes cambia el número).
IMAGENES_POR_CELDA = 25

#: Medidas del lote calculadas en otras salidas del proyecto, cruzadas por código
#: catastral. Cada entrada es
#: ruta relativa a outputs/ -> columnas que se traen.
DERIVADAS_EXTRA = {
    "umbrales/base_derivada.csv": ["pct_cuerpo_agua", "pct_zip"],
    "umbrales/agregacion_tierra.csv": ["lotes_pegados", "ha_pegadas", "lotes_para_150ha",
                                       "ha_catastro_1km"],
    "derivadas/fragmentacion.csv": ["n_parches_utiles", "parche_mayor_frac", "desnivel_total_m"],
    "derivadas/rectangulo.csv": ["rect_largo_m", "rect_ancho_m", "alargamiento", "llenado_rect"],
    "derivadas/graduadas.csv": ["pomca_fase", "humedal_natural", "frontera_condicionada",
                                "hc_estado"],
}
DERIVADAS_EXTRA_COLS = [c for cols in DERIVADAS_EXTRA.values() for c in cols]

#: Objetivo de superficie con el que se contó cuántos lotes contiguos hay que reunir
#: (columna lotes_para_150ha). Se escribe junto a la cifra para que se pueda leer sola.
OBJETIVO_AGREGACION_HA = 150


def cargar_derivadas() -> pd.DataFrame:
    """Tabla CODIGO -> medidas derivadas de las demás salidas, vacía si no hay archivos."""
    out = None
    for rel, cols in DERIVADAS_EXTRA.items():
        ruta = SALIDA.parent / rel
        if not ruta.exists():
            continue
        try:
            t = pd.read_csv(ruta, encoding="utf-8-sig", dtype={"CODIGO": str})
        except Exception:
            continue
        if "CODIGO" not in t.columns:
            continue
        t["CODIGO"] = t["CODIGO"].astype(str).str.strip().str.zfill(30)
        hay = [c for c in cols if c in t.columns]
        t = t[["CODIGO"] + hay].drop_duplicates(subset="CODIGO")
        out = t if out is None else out.merge(t, on="CODIGO", how="outer")
    return out if out is not None else pd.DataFrame(columns=["CODIGO"])


#: Columnas del lote que viajan al HTML; el resto queda en el CSV.
CAMPOS_LOTE = [
    "orden", "cell_id", "CODIGO", "numero_predial_anterior", "clasificacion", "indice_lote", "motivo",
    "departamento", "municipio", "municipio_celda", "clase_suelo", "destino", "area_ha", "mwp_lote",
    "ancho_util_m", "compacidad", "pendiente_media", "pendiente_p90", "rugosidad_m",
    "elevacion_media",
    # Cobertura del suelo clase a clase, tal como la publica ESA WorldCover.
    ] + COLUMNAS_COBERTURA + [
    # El agregado ponderado no se publica en ninguna cifra de la ficha: viaja solo porque
    # es la variable de entrada del criterio de cobertura del índice de aptitud, cuyos
    # percentiles de referencia se calibraron sobre esta misma escala.
    "cobertura_apta_pct",
    "area_construida_m2",
    "area_terreno_catastro_m2", "dist_via_km", "dist_via_principal_km",
    "conexion_km", "conexion_nombre", "conexion_kv",
    # `reparos` no viaja: el visor vuelve a calcular los criterios que quedan bajo su
    # límite a partir del catálogo, de modo que el texto no puede quedarse atrás.
    "criterios_evaluados", "criterios_cumplidos",
    "cabe_perfil", "cabe_utility", "cabe_distribuida",
    "estorbos", "gestion",
    "dane_predio", "uaf_max_ha", "uaf_fuente", "veces_uaf", "riesgo_baldio",
    "restitucion_mpio", "microzona_urt",
    "nombre_predio", "zonas_economicas", "zona_economica_dominante", "n_construcciones",
    "construccion_uso_principal", "construccion_puntaje_max",
    "valor_ref_cop_ha", "valor_ref_cop", "valor_ref_cobertura", "ant_mediana_cop_ha",
    "ant_banda", "valor_confianza",
    "ent_drenajes_n", "ent_drenajes", "ent_inundacion_1988", "ent_inundacion_2000", "ent_inundacion_2011", "ent_inundacion_2012", "ent_inundacion_2016", "ent_inundacion_2020_2022", "ent_inundaciones_nina", "ent_inundacion_ha_max", "ent_zip_ha", "ent_cuerpo_agua_ha", "ent_nino_precip", "ent_nina_precip", "ent_sequia_retorno", "ent_incendios_5km", "ent_incendios_ha_5km", "ent_incendios_ultimo", "ent_humedal",
    "ent_pomca", "ent_frontera_agricola", "ent_clase_agrologica", "ent_clase_agrologica_fuente", "ent_mineria_titulos",
    "ent_mineria_detalle", "ent_mineria_solicitudes", "ent_hidrocarburos", "ent_mov_masa",
    "ent_sismica", "ent_fecha", "ent_capas_sin_respuesta",
    "ent_runap", "ent_runap_ha", "ent_resguardo", "ent_resguardo_ha",
    "ent_consejo", "ent_consejo_ha", "ent_paramo", "ent_paramo_ha",
    "ctx_pvout", "ctx_ghi", "ctx_dni", "ctx_dif", "ctx_gti", "ctx_opta", "ctx_temp", "ctx_ele",
    "ctx_linea_km", "ctx_linea_kv", "ctx_poblado", "ctx_poblado_tipo", "ctx_poblado_km",
    "ctx_caserio", "ctx_caserio_km",
    "pot_categoria", "pot_categoria_cod", "pot_categoria_pct", "pot_reparto", "pot_uso_principal",
    "pot_proteccion_pct", "pot_uso_prohibido", "pot_semaforo", "pot_clasificacion", "pot_acto",
    "pot_tipo", "pot_acto_municipal", "pot_anio", "pot_revision", "pot_fecha", "pot_estado",
    # Estado de la norma urbana del municipio: si su zonificación está publicada, qué
    # instrumento la adopta, cuánto del lote queda cubierto y cuánto en protección.
    "pot_estado_norma", "pot_cobertura", "pot_instrumento", "pot_instrumento_anios",
    "pot_instrumento_vencido", "pot_zonificado_pct", "pot_rojo_pct", "pot_nota",
    # Condiciones del lote que fijan su clase, y avisos que no bajan de clase porque son
    # huecos de la fuente y no defectos del terreno.
    "condiciones", "advertencias",
    "matricula_inmobiliaria", "matricula_fuente", "matricula_fecha", "certificado",
    "matricula_estado", "matricula_motivo",
    # Columnas medidas en el CSV de lotes que el visor tambien muestra.
    "destino_economico", "area_nucleo_ha", "nucleo_frac", "dist_via_centro_km",
] + list(DERIVADAS_EXTRA_COLS)

CAMPOS_CELDA = [
    "cell_id", "ranking", "clasificacion", "indice_aptitud", "zona", "departamento",
    "municipio", "vereda", "ha_aptas", "mwp_indicativo", "sub_nombre_subestacion",
    "operador", "sub_tension_kv", "sub_distancia_km", "pvout", "dane_municipio",
    "capacidad_at_mw", "capacidad_mt_mw",
]

#: Portales para personas de cada fuente (el cuadro de fuentes cita el servicio que consulta
#: el código, que es una dirección para máquinas; esta es la que se abre para mirar).
PORTALES = {
    "Catastro público del IGAC": "https://geoportal.igac.gov.co/contenido/consulta-catastral",
    # https://www.igac.gov.co/gestores-catastrales devuelve 404 desde el 24 de agosto
    # de 2026; la pagina viva de la direccion que habilita gestores es esta.
    "IGAC, gestores catastrales": "https://www.igac.gov.co/el-igac/areas-estrategicas/direccion-de-regulacion-y-habilitacion/habilitacion-y-deshabilitacion",
    "IGAC, Zonas Homogéneas Geoeconómicas": "https://geoportal.igac.gov.co/contenido/consulta-catastral",
    # El contenido de ordenamiento del geoportal devuelve 404 y redirige al home
    # generico; el portal documental de POT municipales es Colombia OT.
    "IGAC, datos nacionales POT (LADM-COL)": "https://www.colombiaot.gov.co/",
    # El contenido de agrologia responde 200 pero redirige al home generico de Colombia
    # en Mapas; se enlaza directamente Colombia en Mapas, que es donde aterriza.
    "IGAC, capacidad de uso de las tierras (multiescalar 2024)": "https://www.colombiaenmapas.gov.co/",
    "ANT, Observatorio de Tierras Rurales": "https://observatorio.ant.gov.co/",
    # El certificado del sitio solo ampara urt.gov.co, sin www: con www falla el TLS.
    # La ruta /estadisticas-de-restitucion-de-tierras devuelve 404 desde el 24-08-2026
    # (comprobado dos veces); se apunta a la portada de la entidad, que responde 200.
    "URT, Unidad de Restitución de Tierras": "https://urt.gov.co",
    "SNR, Superintendencia de Notariado y Registro": "https://certificados.supernotariado.gov.co/certificado",
    "UPME, Circular Externa 054 de 2026 y anexo": "https://www.upme.gov.co/nosotros/biblioteca-juridica/circulares-upme/",
    "UPME, Resolución 567 de 2026 (antes Circular 042)": "https://www.upme.gov.co/nosotros/biblioteca-juridica/resoluciones-upme/",
    "Subestaciones y líneas del SIN": "https://geo.upme.gov.co/",
    "Global Solar Atlas (Solargis, Banco Mundial)": "https://globalsolaratlas.info/map",
    "Copernicus DEM GLO-30": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM",
    "ESA WorldCover": "https://viewer.esa-worldcover.org/worldcover/",
    "OpenStreetMap (Overpass)": "https://www.openstreetmap.org/",
    # visualizador.ideam.gov.co no responde en el puerto 80; el servidor de servicios sí.
    "IDEAM, hidrografía e inundaciones": "https://visualizador.ideam.gov.co/gisserver/rest/services",
    "IDEAM, climatología ENSO": "https://visualizador.ideam.gov.co/gisserver/rest/services",
    "MADS, SIAC": "https://siac-datosabiertos-mads.hub.arcgis.com/",
    "Parques Nacionales, RUNAP": "https://runap.parquesnacionales.gov.co/",
    "ANT, datos abiertos": "https://data-agenciadetierras.opendata.arcgis.com/",
    "UPRA": "https://sipra.upra.gov.co/",
    "ANM, Catastro Minero Colombiano": "https://annamineria.anm.gov.co/",
    "ANH": "https://geovisor.anh.gov.co/tierras/",
    "SGC": "https://www2.sgc.gov.co/sgc/mapas/Paginas/geoportal.aspx",
    "Esri World Imagery (Vantor, antes Maxar; Earthstar Geographics)": "https://www.arcgis.com/home/webmap/viewer.html?useExisting=1&layers=10df2279f9684e4a9f6a7f08febac2a9",
    "Copernicus Sentinel-2 (ESA), vía Earth Search de AWS": "https://browser.dataspace.copernicus.eu/",
    "Registro de plantas de XM (capa UPME proyectos_generacion_xm)": "https://geo.upme.gov.co/",
}

#: Portales cuya dirección admite un centro y un nivel de acercamiento. Se escriben con
#: los de la selección de la corrida, de modo que el enlace abre donde están las grillas y
#: no en un punto fijo.
PORTALES_CENTRADOS = {
    "Global Solar Atlas (Solargis, Banco Mundial)": "https://globalsolaratlas.info/map?c={lat},{lon},{z}",
    "OpenStreetMap (Overpass)": "https://www.openstreetmap.org/#map={z}/{lat}/{lon}",
}

#: Grados de extensión de la selección por encima de los cuales se aleja un nivel el mapa,
#: para que quepan todas las grillas por dispersas que estén.
_ZOOM_POR_EXTENSION = ((0.2, 11), (1.0, 9), (4.0, 7), (10.0, 6))


def _zoom(extension: float) -> int:
    """Nivel de acercamiento con el que caben todas las grillas de la selección."""
    for tope, z in _ZOOM_POR_EXTENSION:
        if extension <= tope:
            return z
    return 5


def portales(grillas) -> dict[str, str]:
    """Direcciones de los portales, centradas en la selección donde el portal lo admite."""
    out = dict(PORTALES)
    try:
        x0, y0, x1, y1 = grillas.total_bounds
        lat, lon = f"{(y0 + y1) / 2:.2f}", f"{(x0 + x1) / 2:.2f}"
        z = _zoom(max(x1 - x0, y1 - y0))
    except Exception:
        return out
    for nombre, patron in PORTALES_CENTRADOS.items():
        out[nombre] = patron.format(lat=lat, lon=lon, z=z)
    return out

#: Vigencia del POT verificada a mano contra alcaldía, concejo y corporación autónoma,
#: por código DANE del municipio. Un POT sigue vigente hasta que el concejo adopte otro;
#: "en curso" es proceso sin adoptar. Los municipios que no estén aquí muestran en la
#: ficha lo que declara la capa nacional, y la prosa del cuadro de fuentes lo dice; al
#: verificar un municipio nuevo, se añade su código a esta tabla.
VIGENCIA_POT = {
    "70820": {"estado": "vigente", "nota": "PBOT Acuerdo 010 de 2000 vigente (modificación excepcional Acuerdo 004 de 2012); revisión en concertación con Carsucre desde 2023, sin adoptar."},
    "70708": {"estado": "vigente", "nota": "PBOT Acuerdo 040 de 2001 vigente, modificado por Acuerdo 001 de 2019; sin proceso de revisión en curso."},
    "70124": {"estado": "vigente", "nota": "EOT Acuerdo 009 de 2002 vigente; actualización en formulación (insumos POT Modernos devueltos por Corpomojana), sin adoptar."},
    "70400": {"estado": "vigente", "nota": "EOT Acuerdo 015 de 2004 vigente; revisión en formulación, sin adoptar."},
    "23580": {"estado": "vigente", "nota": "Acuerdo 003 de 2006 vigente; revisión estructural del EOT en curso con consultor, sin adoptar."},
    "68655": {"estado": "vigente", "nota": "EOT con revisión excepcional del Acuerdo 033 de 2015 vigente; sin proceso en curso."},
    "23350": {"estado": "vigente", "nota": "EOT Acuerdo 002 de 2016 vigente, modificado por Acuerdo 004 de 2017; sin proceso en curso."},
    "23079": {"estado": "vigente", "nota": "EOT Acuerdo 006 de 2016 vigente; sin proceso de revisión confirmado."},
    "08141": {"estado": "vigente", "nota": "EOT del año 2000 vigente; actualización en curso según la Gobernación del Atlántico, sin adoptar."},
    "08436": {"estado": "desactualizado_igac", "nota": "Existe el Acuerdo 012 de 2017 (revisión y ajuste del EOT), posterior a lo que muestra el geoservicio del IGAC: la zonificación mostrada puede no reflejarlo. Pedir el EOT 2017 a la alcaldía antes de decidir."},
}
VIGENCIA_POT_FECHA = "2026-08-19"

#: Fuentes de información del visor y la ficha: nombre, qué aporta, versión o corte y
#: dirección. Es la tabla que cierra el reporte; se mantiene aquí, en un solo sitio.
FUENTES = [
    ("Catastro público del IGAC", "polígono del lote, número predial, áreas, destino, zonas económicas, construcciones (capas R_TERRENO 14 y 7, tablas REGISTRO_1 y REGISTRO_2)", "corte 30 de junio de 2026 (Base_Catastral_Publica_del_Gestor_IGAC_06_2026, publicada el 28 de julio; el IGAC publica un corte mensual). Solo municipios con gestor IGAC", "https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/Base_Catastral_Publica_del_Gestor_IGAC_06_2026/FeatureServer"),
    ("IGAC, gestores catastrales", "quién lleva el catastro de cada municipio (explica las grillas con poca cobertura del catastro público)", "CAPA_GESTORES_10062026", "https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/CAPA_GESTORES_10062026/FeatureServer/0"),
    ("IGAC, Zonas Homogéneas Geoeconómicas", "valor catastral de referencia por hectárea (VALOR_HECTAREA) ponderado por el área del lote en cada zona", "servicio Vigencias 2026 (última edición 9 de junio de 2026); el año base de cada zona es el de su formación o actualización (de 2002 a 2026 según el municipio)", "https://services2.arcgis.com/RVvWzU3lgJISqdke/ArcGIS/rest/services/Zonas_Homogeneas_Gestor_IGAC_Vigencias_2026/FeatureServer/11"),
    ("IGAC, datos nacionales POT (LADM-COL)", "norma urbana del lote: categoría de suelo rural y uso principal repartidos por área sobre el polígono del lote y no sobre su centro; clasificación del suelo (urbano, rural o expansión) y el acto que la adopta; tipo de instrumento del municipio, acto de adopción, año y última revisión", "zonificación del suelo rural publicada para 761 de los 1.103 municipios del país; datos nacionales POT para 1.102 municipios. Cuando el servicio de clasificación del suelo no responde, se muestra la última consulta guardada y la ficha lo declara", "https://mapas2.igac.gov.co/server/rest/services/ordenamiento"),
    ("IGAC, capacidad de uso de las tierras (multiescalar 2024)", "clase agrológica en el lote, con el estudio, la escala y el año del levantamiento", "CUT_Multiescalar_2024 (levantamientos 1:100.000, 1:25.000 y 1:10.000 hasta 2024)", "https://mapas.igac.gov.co/server/rest/services/agrologia/capacidaddeusodelastierrasmultiescalar/MapServer/0"),
    ("ANT, Observatorio de Tierras Rurales", "mediana municipal del valor de la tierra (banda de contraste) y UAF por municipio", "última publicación disponible por departamento; UAF según la resolución vigente del municipio", "https://www.ant.gov.co"),
    ("URT, Unidad de Restitución de Tierras", "solicitudes de restitución y microzonas focalizadas por municipio", "corte 31 de julio de 2026", "https://urt.gov.co"),
    ("SNR, Superintendencia de Notariado y Registro", "certificado de tradición y libertad (propietario, gravámenes, origen); precio del certificado", "Res. SNR 2026-001726, $23.000 electrónico", "https://certificados.supernotariado.gov.co/certificado"),
    ("UPME, Circular Externa 054 de 2026 y anexo", "capacidad disponible por barra 2026-2039 (escenario crítico, variable limitante); criterio de capacidad", "10 de junio de 2026, corte de información 5 de mayo de 2026, informe preliminar; completa con los 14 informes del ciclo 2023-2024 (Circular 077 de 2024)", "https://docs.upme.gov.co/Normatividad/Circular_054_2026_y_anexos.pdf"),
    ("UPME, Resolución 567 de 2026 (antes Circular 042)", "obras urgentes por agotamiento de subestaciones por cortocircuito: qué barra se repotencia y en qué año", "Resolución definitiva del 6 de agosto de 2026 y Circular 082 de 2026 con la respuesta a comentarios", "https://docs.upme.gov.co/Normatividad/567_2026.pdf"),
    ("Subestaciones y líneas del SIN", "punto de conexión, tensión y distancia; línea de transmisión más cercana", "inventario de subestaciones preparado por el equipo del proyecto y líneas de transmisión de OpenStreetMap, consultadas en vivo", "https://www.openstreetmap.org"),
    ("Global Solar Atlas (Solargis, Banco Mundial)", "recurso en el punto del lote: PVOUT, GHI, DNI, DIF, GTI, OPTA, TEMP, ELE", "promedios de largo plazo, datos 1.7, abril de 2026, 250 m", "https://globalsolaratlas.info"),
    ("Copernicus DEM GLO-30", "pendiente, rugosidad y elevación medidas dentro del lote", "release 2021, 30 m; se leen los mosaicos de un grado del repositorio público del programa Copernicus que cubren las grillas de la corrida", "https://copernicus-dem-30m.s3.amazonaws.com"),
    ("ESA WorldCover", "porcentaje del lote en cada clase de cobertura del suelo (pastizal, bosque, cultivo, matorral, suelo construido, suelo desnudo, humedal, agua permanente, manglar, nieve y musgo), sin transformar", "2021 v200, 10 m (último mapa de la serie; el sucesor LCFM aún no publica 2021 en adelante)", "https://esa-worldcover.org"),
    ("OpenStreetMap (Overpass)", "vías y distancia a vía; centros poblados y caseríos", "vivo (fecha en cada respuesta cacheada)", "https://overpass-api.de"),
    ("IDEAM, hidrografía e inundaciones", "drenajes sencillos y dobles (ronda hídrica); manchas de inundación observadas en los episodios de La Niña 1988, 2000, 2010-2011, 2012, 2016 y 2020-2022; zonas inundables periódicamente 2022", "cartografía básica 1:100.000; Amenaza_Ambiental capas 6, 26, 22, 27, 23, 24; Indicadores_Hidricos capa 21", "https://visualizador.ideam.gov.co/gisserver/rest/services/Amenaza_Ambiental/MapServer"),
    ("IDEAM, climatología ENSO", "alteración de la precipitación en un Niño y una Niña típicos (1981-2010), periodo de retorno de la sequía meteorológica, incendios de cobertura vegetal reportados", "Fenomeno_El_nino capa 41, Fenomeno_La_Nina capa 31, Agrometeorologia capa 10, Tematica/Incendios capa 0", "https://visualizador.ideam.gov.co/gisserver/rest/services"),
    ("MADS, SIAC", "humedales, POMCA, páramos delimitados", "Humedales V3 (MADS 2020); estado de los POMCA del SIRH a jul-2026; páramos capa institucional Ecosistema_Estrategico (actos de delimitación 2014-2018; las delimitaciones posteriores pueden no estar cargadas)", "https://services6.arcgis.com/hxAwRYAu9QHliJ8T/arcgis/rest/services"),
    ("Parques Nacionales, RUNAP", "áreas protegidas inscritas en el Registro Único Nacional, cruzadas con el polígono del lote", "WFS vivo, consultado en cada corrida", "https://mapas.parquesnacionales.gov.co/services/pnn/ows"),
    ("ANT, datos abiertos", "resguardos indígenas formalizados y consejos comunitarios titulados, cruzados con el polígono del lote", "información a 25 de junio de 2026", "https://www.ant.gov.co"),
    ("UPRA", "frontera agrícola nacional", "actualización 2024 (Res. MADR 261 de 2018)", "https://geoservicios.upra.gov.co"),
    ("ANM, Catastro Minero Colombiano", "títulos mineros vigentes (excluyen) y solicitudes, cruzados con el polígono del lote", "servicio vivo (AnnA Minería), consultado en cada corrida", "https://geo.anm.gov.co/webgis/rest/services/ANM/ServiciosANM/MapServer"),
    ("ANH", "bloques de hidrocarburos (contrato, estado, operador)", "servicio vivo; la capa se declara «Tierras 2026-08-06», corte del 6 de agosto de 2026", "https://geovisor.anh.gov.co"),
    ("SGC", "amenaza por movimientos en masa (1:100.000, 2015) y amenaza sísmica (NSR-10, 2010)", "mapas vigentes", "https://srvags.sgc.gov.co/arcgis/rest/services"),
        ("Esri World Imagery (Vantor, antes Maxar; Earthstar Geographics)", "imagen satelital del lote y de la grilla, con fecha de captura", "mosaico vivo; la fecha se muestra en cada imagen", "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"),
    ("Registro de plantas de XM (capa UPME proyectos_generacion_xm)", "calibración de los umbrales del índice (percentiles de las plantas construidas)", "copia del 18 de agosto de 2026, con 351 plantas registradas, que es la que calibra los umbrales del índice", "https://geo.upme.gov.co/server/rest/services/Capas_EnergiaElectrica/proyectos_generacion_xm/FeatureServer/24"),
]



#: Conectores que van en minúscula al normalizar el uso de mayúsculas heredado del catastro.
_CONECTORES = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "al", "a"}
#: Siglas que no se recapitalizan.
_SIGLAS = {"kV", "MW", "MWp", "kWh", "POT", "EOT", "PBOT", "UAF", "IGAC", "ANT", "URT",
           "SNR", "ANM", "ANH", "SGC", "SIN", "FV", "II", "III", "IV"}


def _cap1(p: str) -> str:
    """Primera letra en mayúscula y el resto en minúscula, respetando el signo inicial."""
    for i, ch in enumerate(p):
        if ch.isalpha():
            return p[:i] + ch.upper() + p[i + 1:].lower()
    return p


def _titulo(v):
    """«VILLA DEL RIO» y «Villa rio 115 kV» -> «Villa del Rio», «Villa Rio 115 kV»."""
    if not isinstance(v, str) or not v.strip():
        return v
    texto = re.sub(r"\s+-(?=[^\s-])", " - ", v.strip())
    out = []
    for i, p in enumerate(texto.split()):
        if p in _SIGLAS or any(c.isdigit() for c in p):
            out.append(p)
        elif i and p.lower().strip(",.") in _CONECTORES:
            out.append(p.lower())
        else:
            out.append(_cap1(p))
    return " ".join(out)


#: Marcadores del catastro que significan «no hay dato», no un nombre.
_SIN_NOMBRE = {"sin definir", "sin dato", "sin nombre", "no definido", "ninguno", "n/a", "-"}


def _nombre_o_nada(v):
    """Devuelve None cuando el catastro trae un marcador de ausencia en vez de un nombre."""
    if not isinstance(v, str) or v.strip().lower() in _SIN_NOMBRE or not v.strip():
        return None
    return _titulo(v)


#: Campos de prosa que Python compone con punto decimal. El visor los imprime tal cual y
#: en un documento en español el separador decimal es la coma. `gestion` queda fuera a
#: propósito: ahí el punto ya es separador de millares («2.272 m² construidos»).
CAMPOS_PROSA = ("motivo", "pot_reparto", "ant_banda", "ent_mineria_detalle", "pot_nota")



#: Un número suelto dentro de una frase, con los separadores que traiga pegados.
_NUMERO_EN_FRASE = re.compile(r"\d[\d.,]*\d|\d")
#: Miles escritos con punto: grupos de tres dígitos. «2.441» no es dos coma cuatro.
_MILLARES = re.compile(r"\d{1,3}(?:\.\d{3})+")


def _numero_espanol(tok: str) -> str:
    """
    Un número escrito dentro de una frase, pasado a la ortografía española.

    Estos campos mezclan números que compone Python con punto decimal («82.2») y
    números que predios.lotes ya escribe en español («2.441,0 ha»). Cambiar todo punto
    entre dígitos por coma partía los segundos en «2,441,0», que no es un número. Se
    respeta el que ya trae coma decimal y el que ya escribe los miles con punto; en el
    resto, el punto es decimal y pasa a coma.
    """
    if "," in tok or _MILLARES.fullmatch(tok):
        return tok
    return tok.replace(".", ",")


def _coma_decimal(v):
    """«capacidad libre en la barra de 19.4 MW» -> «... de 19,4 MW»; «2.441,0 ha» se respeta."""
    if not isinstance(v, str):
        return v
    return _NUMERO_EN_FRASE.sub(lambda m: _numero_espanol(m.group(0)), v)


def _fecha_iso(f) -> str:
    """La fecha de captura llega del servicio de Esri como M/D/AAAA; se guarda AAAA-MM-DD."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", str(f or ""))
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else str(f or "")


# ---------------------------------------------------------------------------
# Prosa contada de la corrida
#
# Las notas del cuadro de fuentes llevan cifras. Escritas a mano envejecen en cuanto
# cambia la selección de grillas, y una nota que afirma «ninguno» cuando ya hay uno
# contradice a la ficha del propio lote. Aquí se cuentan todas sobre los lotes de esta
# corrida, y las frases se arman para que sigan siendo ciertas con cualquier selección:
# cuántos municipios hay, cómo se reparten las clases y qué figuras territoriales
# aparecen o no aparecen sale del dato y no del texto. Una afirmación en negativo solo
# se escribe después de comprobar el cero, y un párrafo cuyo fenómeno no ocurre en esta
# corrida no se escribe.
# ---------------------------------------------------------------------------

#: Años de vigencia del contenido de largo plazo del plan de ordenamiento: tres periodos
#: constitucionales de la administración municipal, artículo 28 de la Ley 388 de 1997.
POT_LARGO_PLAZO_ANIOS = 12

#: Orden y adjetivo de cada clase en la prosa. Las etiquetas son las de predios.lotes.
CLASES_PROSA = (("Idóneo", "idóneos"), ("Viable con gestión", "viables con gestión"),
                ("No viable", "no viables"))

#: Nombre corto de cada condición para la prosa del cuadro de fuentes. Si predios.lotes
#: añade una condición que no esté aquí, se usa su código en palabras: la frase pierde
#: elegancia pero sigue diciendo la verdad.
CONDICION_CORTA = {
    "proteccion-pot": "el suelo de protección",
    "titulo-minero": "el título minero vigente",
    "area-protegida": "el área protegida inscrita en el Registro Único Nacional",
    "resguardo-indigena": "el resguardo indígena titulado",
    "consejo-comunitario": "el consejo comunitario titulado",
    "paramo": "el páramo delimitado",
    "unidad-agricola-familiar": "el área por encima de la Unidad Agrícola Familiar",
    "inundacion-la-nina": "la inundación registrada en episodios de La Niña",
    "microzona-restitucion": "la microzona de restitución",
    "humedal": "el humedal dentro del lote",
    "proteccion-pot-parcial": "el suelo de protección sobre una parte del lote",
}

#: Por qué un lote queda sin la categoría del suelo verificada. Las claves son los
#: valores que escribe predios.pot en `pot_cobertura`.
COBERTURA_PROSA = {
    "sin cartografía": "la zonificación rural de su municipio no está publicada",
    "sin instrumento": "el municipio no tiene instrumento de ordenamiento registrado",
    "sin respuesta del servicio": "el servicio de ordenamiento no respondió en la última consulta",
    "sin cobertura": "la zonificación publicada no alcanza al lote",
}

#: Figuras territoriales que se cruzan contra el polígono del lote. De cada una se dice
#: cómo se nombra al afirmarla y al negarla, con qué columna se mide y qué condición del
#: catálogo dispara cuando el solape pasa del umbral de verificación.
FIGURAS_TERRITORIALES = (
    {"codigo": "area-protegida", "col": "ent_runap",
     "afirma": "el área protegida inscrita en el Registro Único Nacional de Áreas Protegidas",
     "niega": "ninguna área protegida inscrita en el Registro Único Nacional de Áreas Protegidas",
     "motivo": ("El uso permitido dentro de un área protegida lo fija su plan de manejo, que no "
                "contempla generación en suelo")},
    {"codigo": "resguardo-indigena", "col": "ent_resguardo",
     "afirma": "el resguardo indígena titulado",
     "niega": "ningún resguardo indígena titulado",
     "motivo": "El territorio de un resguardo es propiedad colectiva y no se puede comprar"},
    {"codigo": "consejo-comunitario", "col": "ent_consejo",
     "afirma": "el consejo comunitario titulado",
     "niega": "ningún consejo comunitario titulado",
     "motivo": ("El territorio colectivo titulado a un consejo comunitario no se puede "
                "comprar")},
    {"codigo": "paramo", "col": "ent_paramo",
     "afirma": "el páramo delimitado",
     "niega": "ningún páramo delimitado",
     "motivo": ("El páramo delimitado es suelo de protección y en él no se permiten "
                "actividades de esta naturaleza")},
)

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

#: Los números pequeños se escriben con letra dentro de la prosa; el resto, en cifra.
_LETRAS = ("cero", "un", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
           "diez", "once", "doce", "trece", "catorce", "quince")


def _n(x) -> str:
    """Entero a la española: punto de millar."""
    return f"{int(round(float(x))):,}".replace(",", ".")


def _dec(x, dec: int = 2) -> str:
    """Decimal a la española: punto de millar y coma decimal."""
    return f"{float(x):,.{dec}f}".replace(",", "·").replace(".", ",").replace("·", ".")


def _letra(n: int, femenino: bool = False) -> str:
    """«un», «una», «trece», «1.204»."""
    n = int(n)
    if 0 <= n < len(_LETRAS):
        return "una" if femenino and n == 1 else _LETRAS[n]
    return _n(n)


def _lotes(n: int) -> str:
    """«un lote», «24 lotes»: la concordancia se calcula, no se escribe a mano."""
    return "un lote" if int(n) == 1 else f"{_n(n)} lotes"


def _los_lotes(n: int) -> str:
    """«el único lote», «los 24 lotes»."""
    return "el único lote" if int(n) == 1 else f"los {_n(n)} lotes"


def _cosas(n: int, sing: str, plur: str, femenino: bool = False) -> str:
    """«un municipio», «trece municipios»: cifra y sustantivo concordados."""
    return f"{_letra(n, femenino)} {sing if int(n) == 1 else plur}"


def _enum(partes, conj: str = "y") -> str:
    """
    «a», «a y b», «a, b y c». La «y» pasa a «e» ante i- o hi-, y la «o» a «u» ante o-.

    Si los propios elementos llevan comas dentro, la conjunción final va precedida de
    coma para que se vea dónde termina el penúltimo.
    """
    partes = [p for p in partes if p]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    ultimo = partes[-1].lstrip("«¿¡").lower()
    if conj == "y" and (ultimo.startswith("i")
                        or (ultimo.startswith("hi") and not ultimo.startswith("hie"))):
        conj = "e"
    if conj == "o" and (ultimo.startswith("o") or ultimo.startswith("ho")):
        conj = "u"
    coma = "," if any("," in p for p in partes) else ""
    return ", ".join(partes[:-1]) + f"{coma} {conj} " + partes[-1]


def _de(frase: str) -> str:
    """Contracción del artículo: «de el resguardo» -> «del resguardo»."""
    return "del " + frase[3:] if frase.startswith("el ") else "de " + frase


def _sin_articulo(frase: str) -> str:
    """«el resguardo indígena titulado» -> «resguardo indígena titulado»."""
    for art in ("el ", "la ", "los ", "las ", "un ", "una "):
        if frase.startswith(art):
            return frase[len(art):]
    return frase


def _mayus1(t: str) -> str:
    """Primera letra en mayúscula sin tocar el resto de la frase."""
    return t[:1].upper() + t[1:] if t else t


def _fecha_larga(iso: str) -> str:
    """«2026-08-19» -> «19 de agosto de 2026»; si no es una fecha, se devuelve tal cual."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso or "").strip())
    if not m:
        return str(iso or "")
    return f"{int(m.group(3))} de {_MESES[int(m.group(2)) - 1]} de {m.group(1)}"


def _numero(v) -> float:
    """Valor numérico de un campo del lote; cero si falta o no es número."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if x != x else x


def _universo(por_perfil: dict) -> list[dict]:
    """Los lotes de la corrida, una sola vez cada uno aunque aparezcan en varios perfiles."""
    vistos: set[str] = set()
    out: list[dict] = []
    for filas in por_perfil.values():
        for f in filas:
            clave = str(f.get("CODIGO") or id(f))
            if clave in vistos:
                continue
            vistos.add(clave)
            out.append(f)
    return out


def _codigos_condicion(f: dict) -> set[str]:
    """
    Códigos de las condiciones que se cumplen en un lote.

    La columna viaja en tres formas según el momento: la lista completa que escribe
    predios.lotes, el JSON del CSV, y el par [código, detalle] al que la comprime
    `catalogo_condiciones`. Se aceptan las tres para que el conteo no dependa del orden
    en que se llame a esta función.
    """
    bruto = f.get("condiciones")
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto)
        except (TypeError, ValueError):
            bruto = []
    out = set()
    for c in bruto or []:
        if isinstance(c, dict):
            codigo = c.get("codigo")
        elif isinstance(c, (list, tuple)) and c:
            codigo = c[0]
        else:
            codigo = None
        if codigo:
            out.add(str(codigo))
    return out


def _clase_por_condicion() -> dict[str, str]:
    """Código de condición -> clase a la que lleva, leído del catálogo de predios.lotes."""
    try:
        import lotes as _lt
        return {c["codigo"]: c["clase"] for c in _lt.CONDICIONES}
    except Exception:
        return {}


def _reparto_clases(filas: list[dict]) -> str:
    """«N son idóneos, N viables con gestión y N no viables», contado de la corrida."""
    cuenta = collections.Counter(str(f.get("clasificacion") or "sin clase") for f in filas)
    partes, vistas = [], set()
    for etiqueta, adjetivo in CLASES_PROSA:
        vistas.add(etiqueta)
        n = cuenta.get(etiqueta, 0)
        if n:
            partes.append(f"{_n(n)} {'son ' if not partes else ''}{adjetivo}")
    for etiqueta, n in sorted(cuenta.items()):
        if etiqueta not in vistas and n:
            partes.append(f"{_n(n)} {'son ' if not partes else ''}{etiqueta.lower()}")
    return _enum(partes)


def _nota_clases(filas: list[dict], codigos: dict) -> str:
    """Cierre del apartado de clasificación: reparto por clase y condiciones más frecuentes."""
    total = len(filas)
    clase_de = _clase_por_condicion()
    cuenta = collections.Counter()
    for f in filas:
        cuenta.update(codigos[id(f)])
    corta = lambda c: CONDICION_CORTA.get(c, c.replace("-", " "))
    gestion = [(c, n) for c, n in cuenta.most_common() if clase_de.get(c) == "Viable con gestión"]
    duras = [(c, n) for c, n in cuenta.most_common() if clase_de.get(c) == "No viable"]

    texto = f"De {_los_lotes(total)} caracterizados en esta corrida, {_reparto_clases(filas)}."
    if gestion:
        texto += (" Las condiciones que más lotes afectan son "
                  + _enum([f"{corta(c)}, con {_n(n)}" for c, n in gestion[:3]]) + ".")
    else:
        texto += (" Ninguna de las condiciones que se resuelven con un trámite se cumple en "
                  "los lotes de esta corrida.")
    if duras:
        partes = [f"{corta(c)} afecta a {_lotes(n)}" if i == 0 else f"{corta(c)} a {_n(n)}"
                  for i, (c, n) in enumerate(duras)]
        texto += " Entre las que no admiten gestión, " + _enum(partes) + "."
    else:
        texto += (" Ninguna de las condiciones que no admiten gestión se cumple en los lotes "
                  "de esta corrida.")
    return texto


def _notas_pot(filas: list[dict]) -> list[str]:
    """Los párrafos con cifras del apartado de la norma urbanística del municipio."""
    total = len(filas)
    cobertura = collections.Counter(str(f.get("pot_cobertura") or "sin dato") for f in filas)
    verificados = cobertura.get("verificado", 0)
    faltan = total - verificados
    motivos = [f"en {_n(n)} {COBERTURA_PROSA.get(k, 'la fuente no da la categoría del suelo')}"
               for k, n in cobertura.most_common() if k != "verificado" and n]
    parrafo = (f"De {_los_lotes(total)} de la lista, {_n(verificados)} "
               f"{'tiene' if verificados == 1 else 'tienen'} su categoría verificada contra la "
               f"zonificación publicada y {_n(faltan)} no la "
               f"{'tiene' if faltan == 1 else 'tienen'}")
    parrafo += (": " + _enum(motivos) + "." if motivos else ".")

    sin_capa = [f for f in filas if str(f.get("pot_cobertura") or "") == "sin cartografía"]
    if sin_capa:
        por_mpio = collections.Counter(str(f.get("municipio") or "sin municipio") for f in sin_capa)
        de_mpio = collections.Counter(str(f.get("municipio") or "sin municipio") for f in filas)
        orden = sorted(por_mpio.items(), key=lambda kv: (-kv[1], kv[0]))
        completos = [m for m, n in orden if n == de_mpio[m]]
        parciales = [m for m, n in orden if n != de_mpio[m]]
        if len(orden) == 1:
            solo = orden[0][0]
            parrafo += (f" Están en {solo}, donde "
                        + ("ningún lote tiene la categoría verificada" if completos
                           else "el vacío alcanza solo a una parte de sus lotes") + ".")
        else:
            parrafo += (f" Los lotes sin cartografía publicada están en "
                        f"{_cosas(len(por_mpio), 'municipio', 'municipios')}: "
                        + _enum([f"{m} con {_n(n)}" for m, n in orden]) + ".")
            if completos:
                parrafo += (f" En {_enum(completos)} no hay un solo lote con la categoría "
                            f"verificada")
                parrafo += (f"; en {_enum(parciales)} el vacío alcanza solo a una parte de sus "
                            f"lotes." if parciales else ".")
            elif parciales:
                parrafo += f" En {_enum(parciales)} el vacío alcanza solo a una parte de sus lotes."
        con_instrumento = {m for m in por_mpio
                           if any(str(f.get("pot_instrumento") or "").strip()
                                  for f in sin_capa if str(f.get("municipio") or "") == m)}
        if con_instrumento:
            cuantos = ("ese municipio" if len(por_mpio) == 1
                       else "todos ellos" if len(con_instrumento) == len(por_mpio)
                       else f"{_letra(len(con_instrumento))} de ellos")
            parrafo += (f" En {cuantos} el instituto sí registra un instrumento de ordenamiento "
                        f"adoptado, de modo que el vacío está en la capa nacional y no en el "
                        f"municipio.")
        parrafo += (" Para ese municipio la norma se pide a la alcaldía." if len(por_mpio) == 1
                    else " Para esos municipios la norma se pide a la alcaldía.")
    salida = [parrafo]

    ajenos = [f for f in filas if f.get("pot_municipio_ajeno")]
    if ajenos:
        por_mpio = collections.Counter(str(f.get("municipio") or "sin municipio") for f in ajenos)
        orden = sorted(por_mpio.items(), key=lambda kv: (-kv[1], kv[0]))
        tope = max(_numero(f.get("pot_zonificado_pct")) for f in ajenos)
        k = len(ajenos)
        cuerpo = (f"{_mayus1(_lotes(k))} de {orden[0][0]}" if len(orden) == 1 else
                  f"{_mayus1(_lotes(k))}, "
                  + _enum([f"{_n(n)} en {m}" for m, n in orden]) + ",")
        salida.append(
            f"{cuerpo} {'trae' if k == 1 else 'traen'} una categoría que ponen polígonos de un "
            f"municipio vecino: la zonificación publicada no cubre más del {_dec(tope, 1)} por "
            f"ciento de su superficie. Esa categoría no describe la norma del municipio donde "
            f"está el lote, y la ficha lo advierte lote a lote.")
    return salida


def _nota_vigencia(filas: list[dict]) -> list[str]:
    """Cuántos municipios superan la vigencia de largo plazo y en cuántos se verificó a mano."""
    anios: dict[str, float] = {}
    danes: dict[str, str] = {}
    for f in filas:
        mpio = str(f.get("municipio") or "").strip()
        if not mpio:
            continue
        anios[mpio] = max(anios.get(mpio, 0.0), _numero(f.get("pot_instrumento_anios")))
        danes.setdefault(mpio, str(f.get("CODIGO") or "").zfill(30)[:5])
    n_mpio = len(anios)
    if not n_mpio:
        return []
    viejos = [m for m, a in anios.items() if a > POT_LARGO_PLAZO_ANIOS]
    if n_mpio == 1:
        frase = ("El único municipio con lotes en la lista supera los doce años contados desde "
                 "la adopción de su instrumento." if viejos else
                 "El único municipio con lotes en la lista no llega a los doce años contados "
                 "desde la adopción de su instrumento.")
    elif len(viejos) == n_mpio:
        frase = (f"Los {_letra(n_mpio)} municipios con lotes en la lista superan los doce años "
                 f"contados desde la adopción de su instrumento.")
    elif not viejos:
        frase = (f"Ninguno de los {_letra(n_mpio)} municipios con lotes en la lista llega a los "
                 f"doce años contados desde la adopción de su instrumento.")
    else:
        frase = (f"De los {_letra(n_mpio)} municipios con lotes en la lista, "
                 f"{_letra(len(viejos))} superan los doce años contados desde la adopción de su "
                 f"instrumento y {_letra(n_mpio - len(viejos))} no llegan a ellos.")
    primero = (frase + " La ficha de cada lote nombra el acuerdo que lo adopta, el año, la "
               "revisión registrada si la hay, y cuántos años han pasado desde la adopción.")

    verificados = sorted(m for m, d in danes.items() if d in VIGENCIA_POT)
    fecha = _fecha_larga(VIGENCIA_POT_FECHA)
    if not verificados:
        segundo = (f"La vigencia {'de ese municipio' if n_mpio == 1 else 'de estos municipios'} "
                   f"no se ha comprobado contra alcaldía, concejo y corporación autónoma; la "
                   f"ficha muestra lo que declara la capa nacional.")
    elif len(verificados) == n_mpio:
        cual = ("del municipio" if n_mpio == 1
                else f"de cada uno de los {_letra(n_mpio)} municipios")
        segundo = (f"La vigencia {cual} se verificó el {fecha} contra alcaldía, concejo y "
                   f"corporación autónoma, y el resultado se muestra en la ficha del lote.")
    else:
        segundo = (f"La vigencia se verificó el {fecha} contra alcaldía, concejo y corporación "
                   f"autónoma en {_letra(len(verificados))} de los {_letra(n_mpio)} "
                   f"municipios, y ese resultado se muestra en la ficha del lote; en los demás "
                   f"la ficha muestra lo que declara la capa nacional.")
    return [primero, segundo]


def _solape_figura(fig: dict, sub: list[dict]) -> str:
    """«un lote toca «X» en 0,18 hectáreas de su superficie», con el municipio del dato."""
    mpios = sorted({str(f.get("municipio") or "").strip() for f in sub} - {""})
    col = fig.get("col")
    nombres = sorted({str(f.get(col) or "").strip() for f in sub} - {""}) if col else []
    clave = fig["pct"] if fig.get("pct") else f"{col}_ha"
    valores = sorted(_numero(f.get(clave)) for f in sub)
    if fig.get("pct"):
        medida = (f" en el {_dec(valores[0], 1)} por ciento de su superficie"
                  if valores[0] == valores[-1] else
                  f", entre el {_dec(valores[0], 1)} y el {_dec(valores[-1], 1)} por ciento de "
                  f"la superficie de cada lote")
    else:
        medida = (f" en {_dec(valores[0])} hectáreas de su superficie"
                  if valores[0] == valores[-1] else
                  f", entre {_dec(valores[0])} y {_dec(valores[-1])} hectáreas de cada lote")
    texto = _lotes(len(sub))
    if mpios:
        texto += f" de {_enum(mpios)}"
    texto += " toca " if len(sub) == 1 else " tocan "
    # El nombre viene de la capa oficial y no siempre admite artículo ni tiene género
    # previsible: se entrecomilla en vez de intentar concordarlo.
    texto += _enum([f"«{n}»" for n in nombres]) if nombres else fig["afirma"]
    return texto + medida


def _notas_figuras(filas: list[dict], codigos: dict) -> list[str]:
    """
    Lo que el cruce encontró y lo que no, contado figura por figura.

    Un cero se afirma solo después de comprobarlo. Un solape que no llega al umbral de
    verificación se declara como tal y no se calla, porque la ficha del lote sí lo dice.
    Una figura que no aparece en esta corrida no deja párrafo detrás.
    """
    total = len(filas)
    ninguna, bajo_umbral, efectivas = [], [], []
    for fig in FIGURAS_TERRITORIALES:
        clave = fig["pct"] if fig.get("pct") else f"{fig['col']}_ha"
        tocan = [f for f in filas if _numero(f.get(clave)) > 0]
        pasan = [f for f in tocan if fig["codigo"] in codigos[id(f)]]
        menores = [f for f in tocan if f not in pasan]
        if not tocan:
            ninguna.append(fig)
        if pasan:
            efectivas.append((fig["codigo"], fig, pasan, menores))
        elif menores:
            bajo_umbral.append((fig, menores))

    salida = []
    if ninguna:
        salida.append(
            f"En {_los_lotes(total)} de la lista, el cruce no encontró "
            + _enum([f["niega"] for f in ninguna])
            + ". Es un cero medido sobre el polígono de cada lote y no una consulta sin "
              "respuesta.")
    for _codigo, fig, pasan, menores in efectivas:
        texto = (f"Sí hay {_sin_articulo(fig['afirma'])} sobre lotes de la lista. "
                 + _mayus1(_solape_figura(fig, pasan))
                 + f". {fig['motivo']}, de modo que el solape efectivo deja el lote No viable.")
        if menores:
            texto += (" Otro solape de la misma figura queda por debajo del umbral: "
                      if len(menores) == 1 else
                      " Otros solapes de la misma figura quedan por debajo del umbral: ")
            texto += _solape_figura(fig, menores) + "."
        salida.append(texto)
    for fig, menores in bajo_umbral:
        salida.append(
            f"{_mayus1(_de(fig['afirma']))} sí hay rastro, por debajo del umbral de "
            f"verificación y no en cero: " + _solape_figura(fig, menores) + ". Por debajo del "
            "umbral, que es una "
            "hectárea o el dos por ciento del área del lote, el solape se lee como desajuste de "
            "linderos entre capas de distinta precisión y se anota en la ficha sin cambiar la "
            "clase, que es lo que hace la ficha de ese lote.")
    if not bajo_umbral and not efectivas:
        salida.append(
            "El umbral de verificación de estas figuras es una hectárea o el dos por ciento del "
            "área del lote. Por debajo, el solape se leería como desajuste de linderos entre "
            "capas de distinta precisión y se anotaría en la ficha sin cambiar la clase; en esta "
            "corrida no hay ninguno.")
    salida.append(
        "La colindancia importa aunque no haya solape. La consulta previa se decide por área de "
        "influencia del proyecto y no por traslape de linderos, de modo que un lote vecino de un "
        "resguardo o de un consejo comunitario se verifica igualmente ante el Ministerio del "
        "Interior antes de avanzar.")
    salida.append(
        "El cruce descarta solapes iguales o menores a 0,01 hectáreas, cien metros cuadrados, "
        "para que la envolvente del lote no produzca falsos positivos con figuras vecinas.")
    return salida


def notas_fuentes(por_perfil: dict) -> list[tuple[str, list[str]]]:
    """
    Notas al pie del cuadro de fuentes, con cada cifra contada de esta corrida.

    Explican lo que una tabla de una línea por fuente no puede decir: cómo se clasifica
    un lote y cuántos caen en cada clase, cómo se lee el semáforo del POT y dónde no hay
    dato, qué significa un plan de ordenamiento antiguo, y qué figuras territoriales
    encontró el cruce y cuáles no.
    """
    filas = _universo(por_perfil)
    codigos = {id(f): _codigos_condicion(f) for f in filas}
    return [
        ("Cómo se clasifica cada lote", [
            "La clase no sale de una nota ni de un promedio: sale de las condiciones que se "
            "comprobaron sobre el polígono del lote, una por una, contra la fuente oficial de "
            "cada figura. Cada condición trae el trámite que exige, la entidad ante la cual se "
            "surte y la fuente de la que salió el dato, y la ficha del lote las enumera todas.",
            "No viable es el lote en el que se cumple al menos una condición que ninguna gestión "
            "del proyecto resuelve: suelo de protección del plan de ordenamiento sobre la mitad "
            "del lote o más, título minero vigente, área protegida inscrita en el Registro Único "
            "Nacional, resguardo indígena, consejo comunitario titulado o páramo delimitado.",
            "Viable con gestión es el lote en el que se cumple al menos una condición que sí "
            "tiene un trámite conocido: área por encima de la Unidad Agrícola Familiar del "
            "municipio, inundación registrada en episodios de La Niña, microzona focalizada de "
            "restitución de tierras, humedal dentro del lote, o suelo de protección sobre "
            "una parte del lote de entre el diez y el "
            "cincuenta por ciento de su superficie.",
            "Idóneo es el lote en el que no se cumple ninguna de las anteriores.",
            _nota_clases(filas, codigos),
            "El índice de aptitud del lote no interviene en la clase. Es un descriptor técnico "
            "que se muestra dentro de la ficha, junto a su desglose criterio por criterio, y no "
            "ordena la lista ni la clasifica. La lista se ordena por el área catastral del lote, "
            "que es la que el Instituto Geográfico Agustín Codazzi registra para él.",
            "La cobertura del suelo se describe clase a clase, con el porcentaje del lote en cada "
            "una tal como lo publica ESA WorldCover y sin combinarlas en ninguna cifra única. "
            "Este estudio retiró el agregado ponderado que antes ocupaba ese lugar: sus "
            "coeficientes eran una elección propia y no una clasificación de ninguna entidad, y "
            "una negociación con el Estado se sostiene sobre lo que la fuente publica.",
        ]),
        ("Cómo se lee la norma urbanística del municipio, y dónde no hay dato", [
            "La categoría del suelo sale de una sola capa, la zonificación del suelo rural del "
            "Instituto Geográfico Agustín Codazzi. Se cruza el polígono completo del lote y se "
            "mide qué superficie suya cae en categorías de protección. Por encima del cincuenta "
            "por ciento el lote queda No viable; entre el diez y el cincuenta queda Viable con "
            "gestión, porque la parte protegida se excluye de la implantación y el resto se "
            "puede ocupar; por debajo del diez por ciento solo se anota en la ficha. La medida "
            "es de superficie y no de categoría dominante, de modo que un lote con el doce por "
            "ciento en protección no queda igualado a uno que lo está por completo.",
            "Ninguna de estas categorías sustituye el certificado de uso del suelo de la "
            "alcaldía, que es el documento con valor legal y puede corregir la cartografía "
            "publicada. La cartografía ordena la lista de visitas; no decide.",
            *_notas_pot(filas),
            "La capa de origen publica polígonos superpuestos de una misma categoría, uno dentro "
            "de otro, que al sumarse declaran más superficie que la del propio lote. Las "
            "categorías se unen antes de medir, de modo que ningún reparto supera el cien por "
            "ciento del área del lote.",
            "El estado de la norma se declara en la ficha con cinco resultados posibles: "
            "verificada contra la zonificación publicada; sin cartografía publicada y con el "
            "instrumento vencido; sin cobertura sobre el lote; sin instrumento de ordenamiento "
            "registrado; y consulta sin respuesta. Ninguno de los cinco baja la clase del lote: "
            "son huecos de la fuente y no defectos del terreno.",
        ]),
        ("Vigencia del plan de ordenamiento y qué significa un plan antiguo", [
            "Los instrumentos se llaman POT en municipios de más de 100.000 habitantes, PBOT "
            "entre 30.000 y 100.000 y EOT por debajo de 30.000, según el artículo 9 de la Ley "
            "388 de 1997.",
            "El artículo 28 de la Ley 388 de 1997, modificado por el artículo 2 de la Ley 902 de "
            "2004 (Diario Oficial 45.622 del 27 de julio de 2004), fija la vigencia del "
            "contenido estructural en tres periodos constitucionales, es decir doce años, y "
            "cierra así: «si al finalizar el plazo de vigencia establecido no se ha adoptado un "
            "nuevo plan de ordenamiento territorial, seguirá vigente el ya adoptado». Un plan "
            "antiguo no deja de regir. Sigue siendo la norma exigible mientras el concejo no "
            "adopte otra.",
            *_nota_vigencia(filas),
            "El modelo de datos LADM_COL-POT es obligatorio para quien formule, revise o ajuste "
            "su plan bajo el Decreto 1232 de 2020, que modifica el Decreto 1077 de 2015. Los "
            "dominios de categorías rurales y de usos vienen de la Resolución 0495 de 2022 del "
            "Ministerio de Vivienda, Ciudad y Territorio, modificada por la Resolución 0058 del "
            "12 de febrero de 2025 del mismo ministerio, que lleva el modelo a la versión 2.0.",
        ]),
        ("Figuras territoriales: lo que el cruce encontró y lo que no",
         _notas_figuras(filas, codigos)),
        ("Qué mide el índice de aptitud y qué no se ha medido de él", [
            "El índice del lote es un descriptor y no un orden de compra: promedia siete "
            "criterios de terreno, acceso, recurso y capacidad, cada uno llevado a una nota de 0 "
            "a 100 contra los percentiles 90, 50 y 10 de los lotes catastrales donde están las "
            "plantas construidas del registro de XM, y los pondera por la d de Cohen de cada "
            "criterio. La ficha de cada lote muestra ese desglose completo, criterio a criterio.",
            "El índice no clasifica ningún lote y no ordena la lista. Un criterio por debajo de "
            "su límite de referencia no es un obstáculo administrativo: es una condición del "
            "sitio que encarece o condiciona la ingeniería, y así se declara en la ficha.",
            "El modelo de similitud con el que se eligieron las grillas no tiene una medida de "
            "precisión publicada: no hay validación cruzada ni curva ROC contra un conjunto de "
            "prueba independiente.",
        ]),
    ]


def _posicion_ranking(grillas) -> str:
    """
    Qué lugar ocupan en el ranking del reporte de grillas las celdas recibidas.

    Solo se afirma que son las primeras cuando lo son: si la selección no es el tramo
    inicial del ranking, se dice el lugar que ocupan y no se insinúa un orden que no hay.
    """
    if "ranking" not in grillas.columns:
        return ""
    puestos = sorted({int(v) for v in grillas["ranking"] if str(v) not in ("", "nan", "None")})
    n = len(grillas)
    if len(puestos) != n:
        return ""
    if puestos == list(range(1, n + 1)):
        return (" y es la primera del ranking de ese reporte" if n == 1 else
                f" y son las {_letra(n, femenino=True)} primeras de su ranking")
    if n == 1:
        return f" y ocupa el puesto {_n(puestos[0])} de su ranking"
    return f" y ocupan puestos entre el {_n(puestos[0])} y el {_n(puestos[-1])} de su ranking"


def origen_nota(grillas, gestores: dict[str, str] | None = None) -> str:
    """
    De dónde salen las grillas de este visor. El número de grillas, su lugar en el
    ranking, su reparto por clase y los municipios con catastro propio se cuentan de la
    selección recibida; ninguna de esas cifras se escribe a mano.
    """
    n = len(grillas)
    columna = list(grillas["clasificacion"]) if "clasificacion" in grillas.columns else []
    cuenta = collections.Counter(str(c) for c in columna if str(c) not in ("", "nan", "None"))
    conocidas = ("Prioritaria", "Elegible", "Condicionada")
    orden = [c for c in conocidas if cuenta.get(c)] + sorted(c for c in cuenta if c not in conocidas)
    reparto = _enum([f"{_letra(cuenta[c], femenino=True)}"
                     + (" está clasificada" if i == 0 else "")
                     + f" como {c if cuenta[c] == 1 else c + 's'}"
                     for i, c in enumerate(orden)])
    cabeza = ("La grilla de este visor viene del reporte de grillas" if n == 1 else
              f"Las {_letra(n, femenino=True)} grillas de este visor vienen del reporte de "
              f"grillas")
    texto = cabeza + _posicion_ranking(grillas) + "."
    if reparto:
        texto += f" De ellas, {reparto}."
    propios = sorted(_gestor_propio(grillas, gestores))
    if propios:
        k = len(propios)
        texto += (f" El catastro público del instituto no publica los lotes de "
                  f"{_enum(propios)}, "
                  f"{'que administra su propio catastro' if k == 1 else 'que administran su propio catastro'}"
                  f".")
    return texto


def _gestor_propio(grillas, gestores: dict[str, str] | None) -> set[str]:
    """Municipios de la selección cuyo gestor catastral no es el instituto nacional."""
    if not gestores or "dane_municipio" not in grillas.columns:
        return set()
    out = set()
    for _, r in grillas.iterrows():
        dane = str(r.get("dane_municipio") or "").zfill(5)
        gestor = str(gestores.get(dane) or "").strip()
        if gestor and "igac" not in gestor.lower():
            nombre = _titulo(str(r.get("municipio") or "").strip())
            if nombre:
                out.add(nombre)
    return out


def _limpio(v):
    """Convierte a tipos nativos JSON; NaN pasa a None."""
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, str):
        # Las banderas ent_* llegan del GeoJSON como texto cuando la columna tuvo vacíos.
        if v in ("True", "False"):
            return v == "True"
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime.date, datetime.datetime)):
        return v.strftime("%Y-%m-%d")
    return v


def _ordenar_por_area(filas: list[dict]) -> list[dict]:
    """
    Ordena por área catastral descendente y renumera 'orden' dentro de cada celda. El área
    catastral es la que el IGAC registra para el lote: se puede citar a la entidad y no
    depende de ningún cálculo de este estudio. Desempate por código predial.
    """
    filas.sort(key=lambda f: (-(f.get("area_ha") or 0.0), str(f.get("CODIGO") or "")))
    contador: dict[str, int] = {}
    for f in filas:
        celda = str(f.get("cell_id") or "")
        contador[celda] = contador.get(celda, 0) + 1
        f["orden"] = contador[celda]
    return filas


def embudo(perfil: str, celdas: set[str]) -> dict | None:
    """
    Cascada del catastro a la lista, contada desde el CSV de descartados: cuántos lotes
    del catastro público hay en estas grillas, cuántos quedan por debajo del mínimo de
    caracterización, cuántos excluye una regla dura y cuántos quedan.
    """
    ruta = SALIDA / f"lotes_{perfil}_descartados.csv"
    if not ruta.exists():
        return None
    try:
        d = pd.read_csv(ruta, dtype=str, usecols=["cell_id", "clasificacion", "motivo"])
    except Exception:
        return None
    d["cell_id"] = d["cell_id"].astype(str).str.zfill(7)
    d = d[d["cell_id"].isin(celdas)]
    m = d["motivo"].fillna("").str.lower()
    peq = d["clasificacion"] == "Pequeño"
    exc = d["clasificacion"] == "Excluido"
    por_grilla = {}
    for cid, sub in d.groupby("cell_id"):
        por_grilla[cid] = {
            "pequenos": int((sub["clasificacion"] == "Pequeño").sum()),
            "excluidos": int((sub["clasificacion"] == "Excluido").sum()),
        }
    return {
        "pequenos": int(peq.sum()),
        "excluidos": int(exc.sum()),
        "urbano": int((exc & m.str.contains("capa urbana")).sum()),
        "habitacional": int((exc & m.str.contains("habitacional")).sum()),
        "minero": int((exc & m.str.contains("minero")).sum()),
        "por_grilla": por_grilla,
    }


def cargar_grillas(ruta: Path) -> gpd.GeoDataFrame:
    """Celdas seleccionadas, desde GeoJSON/GPKG con geometría o CSV con cell_id."""
    if ruta.suffix.lower() == ".csv":
        # El reporte de grillas exporta con ";" y BOM; otros CSV usan ",". El separador se
        # detecta en la primera línea (el sniffer de pandas falla con una sola columna).
        primera = ruta.read_text(encoding="utf-8-sig").splitlines()[0]
        sep = ";" if primera.count(";") >= primera.count(",") else ","
        tabla = pd.read_csv(ruta, sep=sep, encoding="utf-8-sig", dtype=str)
        col = next((c for c in tabla.columns if c.strip().lower() in ("cell_id", "id grilla", "id")), None)
        if col is None:
            raise SystemExit(f"{ruta.name} no trae columna cell_id. Columnas: {list(tabla.columns)[:8]}")
        ids = tabla[col].astype(str).str.strip().str.zfill(7)
        todas = gpd.read_file(SALIDA / "grillas_candidatas.geojson")
        todas["cell_id"] = todas["cell_id"].astype(str).str.zfill(7)
        g = todas[todas["cell_id"].isin(set(ids))].copy()
        perdidas = sorted(set(ids) - set(g["cell_id"]))
        if perdidas:
            print(f"  aviso: {len(perdidas)} celdas del CSV no están en grillas_candidatas "
                  f"({', '.join(perdidas[:5])}{'...' if len(perdidas) > 5 else ''}); "
                  f"si son de otra corrida del modelo, regenera antes el reporte de grillas")
    else:
        g = gpd.read_file(ruta)
        g["cell_id"] = g["cell_id"].astype(str).str.zfill(7)
        # Columnas que la exportación no incluye se completan desde la tabla maestra.
        faltan = [c for c in CAMPOS_CELDA if c not in g.columns and c != "cell_id"]
        maestro = SALIDA / "grillas_candidatas.geojson"
        if faltan and maestro.exists():
            m = gpd.read_file(maestro, ignore_geometry=True)
            m["cell_id"] = m["cell_id"].astype(str).str.zfill(7)
            g = g.merge(m[["cell_id"] + [c for c in faltan if c in m.columns]],
                        on="cell_id", how="left")
    if g.crs is None:
        g = g.set_crs(config.CRS_GEOGRAFICO)
    return g.to_crs(config.CRS_GEOGRAFICO)


#: Quién lleva el catastro de cada municipio (IGAC o gestor propio). Explica las grillas con
#: poca cobertura del catastro público.
GESTORES_URL = ("https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/"
                "CAPA_GESTORES_10062026/FeatureServer/0/query")
CACHE_GESTORES = config.PROJECT_ROOT / "data" / "igac" / "gestores_catastrales.json"


def gestores_catastrales(danes: list[str]) -> dict[str, str]:
    """DANE del municipio -> nombre del gestor catastral, consultado una vez y cacheado."""
    cache = {}
    if CACHE_GESTORES.exists():
        cache = json.loads(CACHE_GESTORES.read_text(encoding="utf-8"))
    faltan = sorted({d for d in danes if d and d not in cache})
    if faltan:
        try:
            import requests
            where = "mpio_cdpmp IN (" + ",".join(f"'{d}'" for d in faltan) + ")"
            r = requests.get(GESTORES_URL, timeout=60, params={
                "where": where, "outFields": "mpio_cdpmp,mpio_cnmbr,Gestor", "returnGeometry": "false", "f": "json"})
            for f in r.json().get("features", []):
                a = f["attributes"]
                cache[str(a["mpio_cdpmp"])] = str(a.get("Gestor") or "").strip()
            CACHE_GESTORES.parent.mkdir(parents=True, exist_ok=True)
            CACHE_GESTORES.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return cache


def cobertura_catastral(grillas: gpd.GeoDataFrame) -> dict[str, float]:
    """
    Porcentaje de la superficie de cada grilla cubierto por lotes del catastro público
    (todos, no solo los caracterizados), desde outputs/reporte/predios.gpkg. Donde es bajo,
    el hueco es del servicio del IGAC (gestor propio o sin formar), no del método.
    """
    ruta = SALIDA / "predios.gpkg"
    if not ruta.exists():
        return {}
    try:
        p = gpd.read_file(ruta, columns=["cell_id"]).to_crs(config.CRS_METRICO)
    except Exception:
        return {}
    p["cell_id"] = p["cell_id"].astype(str).str.zfill(7)
    gm = grillas.to_crs(config.CRS_METRICO)
    out = {}
    for _, c in gm.iterrows():
        cid = str(c["cell_id"])
        sub = p[p["cell_id"] == cid]
        if sub.empty:
            out[cid] = 0.0
            continue
        out[cid] = round(sub.geometry.union_all().intersection(c.geometry).area / c.geometry.area * 100, 1)
    return out


#: Red eléctrica dibujada sobre el mapa de la grilla. El margen es el mismo con el que
#: se encuadra el mapa, para que una línea que pasa cerca del borde se vea entrar.
MARGEN_RED_GRADOS = 0.06
LINEAS_JSON = SALIDA / "lineas_transmision.json"


def _kv(v):
    """El voltaje de OpenStreetMap llega en voltios y a veces como «110000;34500»."""
    try:
        return round(float(str(v).split(";")[0]) / 1000, 1)
    except (TypeError, ValueError):
        return None


def _kv_sub(v):
    """La capa de subestaciones publica la tensión ya en kV y con coma decimal («230,00»)."""
    try:
        return round(float(str(v).replace(".", "").replace(",", ".")), 1)
    except (TypeError, ValueError):
        return None


def red_electrica(grillas: gpd.GeoDataFrame) -> dict[str, dict]:
    """
    Líneas de transmisión, subestaciones y plantas de generación registradas que caen
    dentro de cada grilla o en su entorno inmediato. Es lo que permite ver si el sistema
    eléctrico pasa por la grilla en vez de dejar el mapa mudo.
    """
    from shapely.geometry import LineString, box as _box

    lineas = []
    if LINEAS_JSON.exists():
        try:
            lineas = json.loads(LINEAS_JSON.read_text(encoding="utf-8"))
        except Exception:
            lineas = []
    subs = plantas = None
    try:
        subs = gpd.read_file(config.SUBESTACIONES_PATH).to_crs(config.CRS_GEOGRAFICO)
    except Exception:
        subs = None
    try:
        plantas = gpd.read_file(config.GRANJAS_PATH).to_crs(config.CRS_GEOGRAFICO)
    except Exception:
        plantas = None

    out: dict[str, dict] = {}
    m = MARGEN_RED_GRADOS
    for _, r in grillas.iterrows():
        cid = str(r["cell_id"])
        x0, y0, x1, y1 = r.geometry.bounds
        env = _box(x0 - m, y0 - m, x1 + m, y1 + m)
        tramos = []
        for L in lineas:
            cs = L.get("coords") or []
            if len(cs) < 2:
                continue
            xs = [c[0] for c in cs]; ys = [c[1] for c in cs]
            if max(xs) < x0 - m or min(xs) > x1 + m or max(ys) < y0 - m or min(ys) > y1 + m:
                continue
            try:
                corte = LineString(cs).intersection(env)
            except Exception:
                continue
            if corte.is_empty:
                continue
            partes = list(getattr(corte, "geoms", [corte]))
            kv = _kv(L.get("kv"))
            for g_ in partes:
                if g_.geom_type != "LineString" or len(g_.coords) < 2:
                    continue
                tramos.append({"kv": kv,
                               "dentro": bool(g_.intersects(r.geometry)),
                               "coords": [[round(x, 5), round(y, 5)] for x, y in g_.coords]})
        s_out = []
        if subs is not None and len(subs):
            sel = subs[subs.geometry.within(env)]
            for _, q in sel.iterrows():
                s_out.append({
                    "nombre": _titulo(q.get("nombre_subestacion")),
                    "kv": _kv_sub(q.get("tension")),
                    "operador": _titulo(q.get("nombre_propietario") or q.get("nombre_organizacion")),
                    "sistema": q.get("sistema"),
                    "dentro": bool(q.geometry.within(r.geometry)),
                    "punto": [round(q.geometry.x, 5), round(q.geometry.y, 5)]})
        p_out = []
        if plantas is not None and len(plantas):
            sel = plantas[plantas.geometry.within(env)]
            for _, q in sel.iterrows():
                p_out.append({
                    "nombre": _titulo(q.get("nombre_recurso")),
                    "mw": _limpio(q.get("capacidad_efectiva_neta_mw")),
                    "tipo": _titulo(q.get("tipo_generacion")),
                    "estado": _titulo(q.get("estado_recurso")),
                    "agente": _titulo(q.get("agente_representante")),
                    "dentro": bool(q.geometry.within(r.geometry)),
                    "punto": [round(q.geometry.x, 5), round(q.geometry.y, 5)]})
        out[cid] = {"lineas": tramos, "subestaciones": s_out, "plantas": p_out,
                    "margen_km": round(m * 111.32, 1)}
    return out


def cargar_matriculas() -> pd.DataFrame:
    """
    Tabla CODIGO -> matrícula inmobiliaria conocida, vacía si no hay archivo.

    Se conservan también las consultas que se hicieron y no encontraron folio: llevan el
    motivo que dio la entidad, y la ficha lo escribe en vez de dejar la casilla muda. Un
    lote sin fila aquí es un lote que todavía no se ha consultado, que es otra cosa.
    """
    cols = ["CODIGO", "matricula_inmobiliaria", "matricula_fuente", "matricula_fecha",
            "matricula_estado", "matricula_motivo"]
    if not MATRICULAS.exists():
        return pd.DataFrame(columns=cols)
    m = pd.read_csv(MATRICULAS, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    m.columns = [c.strip().lower() for c in m.columns]
    m = m.rename(columns={"codigo": "CODIGO", "matricula": "matricula_inmobiliaria",
                          "fuente": "matricula_fuente", "fecha": "matricula_fecha",
                          "estado": "matricula_estado", "motivo": "matricula_motivo"})
    for c in cols:
        if c not in m.columns:
            m[c] = None
    m["CODIGO"] = m["CODIGO"].str.strip().str.zfill(30)
    m = m[cols]
    m = m[m["matricula_inmobiliaria"].notna() | m["matricula_motivo"].notna()]
    # Un código catastral puede tener varias matrículas (englobes sin registrar,
    # segregaciones sin desenglobe): se conservan todas, separadas por punto y coma.
    return (m.groupby("CODIGO", as_index=False)
             .agg({c: (lambda s: "; ".join(sorted({str(x) for x in s.dropna()}))) for c in cols[1:]}))


def lectura_certificados(matriculas) -> dict:
    """
    Lectura del certificado de tradición por matrícula, para los folios que ya se leyeron.

    Solo se adjunta lo que existe: un lote sin certificado no lleva nada, y la ficha no
    escribe una sección vacía. La lectura la produce predios.certificado_ia y ya viene
    comprobada contra las anotaciones del propio folio.
    """
    try:
        sys.path[:0] = [str(config.PROJECT_ROOT / "predios")]
        import certificado_ia as cia
    except Exception:
        return {}
    out = {}
    for m in {x for x in matriculas if x}:
        for una in str(m).split(";"):
            d = cia.de_matricula(una.strip())
            if d:
                # Se copia el analisis entero salvo lo interno, en vez de enumerar
                # campos: enumerarlos hacia que un campo nuevo del prompt no llegara a
                # la ficha y la seccion saliera vacia sin que nada avisara.
                INTERNO = {"version_prompt", "documento", "lote", "semaforo_por_reglas",
                           "razon_por_reglas"}
                out[una.strip()] = {k: v for k, v in d.items() if k not in INTERNO}
    return out


def cargar_lotes(perfil: str, celdas: set[str]) -> gpd.GeoDataFrame:
    """Lotes de un perfil restringidos a las celdas dadas, con matrícula si se conoce, en EPSG:4326."""
    ruta = SALIDA / f"lotes_{perfil}.geojson"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    g = gpd.read_file(ruta)
    g["cell_id"] = g["cell_id"].astype(str).str.zfill(7)
    g = g[g["cell_id"].isin(celdas)].copy()
    g["CODIGO"] = g["CODIGO"].astype(str).str.strip().str.zfill(30)
    m = cargar_matriculas()
    if len(m):
        g = g.merge(m, on="CODIGO", how="left")
    d = cargar_derivadas()
    if len(d):
        g = g.merge(d[[c for c in d.columns if c == "CODIGO" or c not in g.columns]],
                    on="CODIGO", how="left")
    g = completar_cobertura(g)
    return g.to_crs(config.CRS_GEOGRAFICO)


#: Clases de cobertura medidas sobre el recorte de ESA WorldCover ya guardado de cada
#: grilla. Solo se usa para completar las clases que la corrida de lotes no dejó escritas:
#: rehacer la caracterización entera volvería a consultar servicios externos y no es lo
#: que se quiere para añadir una columna que ya está medida en la capa.
CACHE_COBERTURA = SALIDA / "cobertura_clases.csv"


def _medir_cobertura(g: gpd.GeoDataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Porcentaje del lote en cada clase de ESA WorldCover, leído del recorte guardado de su
    grilla. Devuelve una tabla CODIGO -> cob_<clase>_pct, vacía si no hay recortes.
    """
    try:
        import rasterio
        import terreno
    except Exception:
        return pd.DataFrame(columns=["CODIGO"])

    partes, sin_recorte = [], []
    for cid, sub in g.groupby(g["cell_id"].astype(str).str.zfill(7)):
        ruta = terreno.CACHE_COB / f"cobertura_{cid}.tif"
        if not ruta.exists():
            sin_recorte.append(cid)
            continue
        with rasterio.open(ruta) as s:
            cob, tr = s.read(1), s.transform
        pm = sub.to_crs(config.CRS_METRICO)
        n = len(pm)
        lab = terreno._etiquetas(pm, cob.shape, tr).ravel()
        total = np.bincount(lab, minlength=n + 1)[1:]
        con = total > 0
        fila = {"CODIGO": sub["CODIGO"].astype(str).values}
        for clase, sufijo in terreno.SUFIJO_WORLDCOVER.items():
            c = np.bincount(lab, weights=(cob == clase).astype("float64").ravel(),
                            minlength=n + 1)[1:]
            fila[f"cob_{sufijo}_pct"] = np.round(
                np.where(con, c / np.maximum(total, 1) * 100, np.nan), 1)
        partes.append(pd.DataFrame(fila))
    if sin_recorte and verbose:
        print(f"  aviso: sin recorte de cobertura guardado para "
              f"{len(sin_recorte)} grillas: {', '.join(sin_recorte[:6])}")
    if not partes:
        return pd.DataFrame(columns=["CODIGO"])
    return pd.concat(partes, ignore_index=True).drop_duplicates(subset="CODIGO")


def completar_cobertura(g: gpd.GeoDataFrame, verbose: bool = True) -> gpd.GeoDataFrame:
    """
    Añade las clases de cobertura del suelo que el archivo de lotes no traiga, medidas
    sobre el recorte de ESA WorldCover de su grilla. Las clases que el archivo ya trae no
    se tocan. Si no hay recortes, el marco vuelve tal cual y la ficha dirá "sin dato".
    """
    faltan = [c for c in COLUMNAS_COBERTURA if c not in g.columns]
    if not faltan:
        return g
    codigos = set(g["CODIGO"].astype(str))
    tabla = None
    if CACHE_COBERTURA.exists():
        try:
            tabla = pd.read_csv(CACHE_COBERTURA, encoding="utf-8-sig", dtype={"CODIGO": str})
            tabla["CODIGO"] = tabla["CODIGO"].astype(str).str.strip().str.zfill(30)
        except Exception:
            tabla = None
    # La medida se rehace si al archivo guardado le falta una clase o un lote: con otra
    # selección de grillas el anterior no cubre los lotes nuevos.
    if (tabla is None or not set(faltan) <= set(tabla.columns)
            or not codigos <= set(tabla["CODIGO"])):
        tabla = _medir_cobertura(g, verbose=verbose)
        if len(tabla):
            tabla["CODIGO"] = tabla["CODIGO"].astype(str).str.strip().str.zfill(30)
            CACHE_COBERTURA.parent.mkdir(parents=True, exist_ok=True)
            tabla.to_csv(CACHE_COBERTURA, index=False, encoding="utf-8-sig")
    if not len(tabla):
        return g
    hay = [c for c in faltan if c in tabla.columns]
    if not hay:
        return g
    if verbose:
        print(f"  cobertura: {len(hay)} clases de ESA WorldCover medidas para "
              f"{int(tabla[hay].notna().any(axis=1).sum())} lotes "
              f"({', '.join(c[4:-4] for c in hay)})")
    return g.merge(tabla[["CODIGO"] + hay], on="CODIGO", how="left")


#: El motivo se redacta al evaluar el lote. En un archivo escrito antes de retirar el
#: agregado de cobertura, la frase de cierre todavía cita ese agregado; se vuelve a
#: redactar aquí con los porcentajes por clase del mismo lote, que es lo que dice hoy
#: predios.lotes. No se inventa nada: las dos frases salen de la misma fila.
_MEDIDA_VIEJA = re.compile(r"El lote mide .*?% de cobertura apta\.")


def _remedir_motivo(fila: dict) -> str | None:
    """Frase final del motivo reescrita con la composición de la cobertura por clase."""
    texto = fila.get("motivo")
    if not texto or "cobertura apta" not in texto:
        return texto
    area = fila.get("area_ha")
    medida = f"{pl._cifra(area, 1)} ha de área catastral" if area is not None else "sin dato"
    cob = pl.composicion_cobertura(fila)
    if cob:
        medida += f", y su cobertura del suelo es {cob}"
    return _MEDIDA_VIEJA.sub(f"El lote mide {medida}.", texto, count=1)


def satelital_lote(clave: str, geom, forzar: bool = False, px: int = 1200,
                   margen: float = 0.25) -> dict | None:
    """Imagen satelital de una geometría con margen; se cachea y se copia a satelital/."""
    try:
        import shutil
        from insumos import satelital as sat
    except Exception:
        return None
    bbox = sat.recuadro(geom, margen=margen)
    # Recuadro cuadrado: el servicio devuelve la imagen deformada si no lo es.
    minx, miny, maxx, maxy = bbox
    lado = max(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    bbox = (cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2)
    ruta = sat.bajar(f"lote_{clave}", bbox, px=px, forzar=forzar)
    if not ruta:
        return None
    destino = SALIDA / "satelital" / ruta.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists() or forzar:
        shutil.copy2(ruta, destino)
    # La fecha de captura es otra petición; se cachea junto a la imagen.
    lateral = ruta.with_suffix(".fecha")
    if lateral.exists() and not forzar:
        fecha = lateral.read_text(encoding="utf-8").strip()
    else:
        fecha = ""
        try:
            fecha = sat.fecha_imagen(cx, cy)
        except Exception:
            pass
        lateral.write_text(fecha, encoding="utf-8")
    # La fecha llega del servicio como M/D/AAAA. En un documento en español eso es
    # ambiguo (1/10/2026), así que se guarda en ISO y el visor la escribe en prosa.
    return {"src": f"satelital/{ruta.name}", "bbox": [round(v, 6) for v in bbox],
            "fecha": _fecha_iso(fecha)}


def sentinel_lote(clave: str, bbox_cuadrado, forzar: bool = False) -> dict | None:
    """Última escena limpia de Sentinel-2 sobre el mismo recuadro que la imagen Esri; se copia a satelital/."""
    try:
        import shutil
        from insumos import sentinel as s2
    except Exception:
        return None
    d = s2.recorte(clave, tuple(bbox_cuadrado), forzar=forzar)
    if not d:
        return None
    origen = s2.CACHE / d["src"]
    destino = SALIDA / "satelital" / d["src"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.exists() and (not destino.exists() or forzar):
        shutil.copy2(origen, destino)
    return {"src": f"satelital/{d['src']}", "bbox": d["bbox"], "fecha": d["fecha"],
            "nubes": d.get("nubes"), "escena": d.get("escena")}


#: Campos de texto largo que se repiten palabra por palabra en muchos lotes: la nota de la
#: norma urbana es casi la misma dentro de un municipio, y los avisos se reducen a cuatro
#: redacciones. Se escriben una sola vez en una tabla común y cada lote guarda su posición
#: en ella, de modo que el documento no crezca por repetir el mismo párrafo cientos de veces.
TEXTOS_COMPARTIDOS = ("pot_nota", "advertencias", "gestion", "condiciones_texto")

#: Claves que describen una condición del lote y que viajan una sola vez, en el catálogo.
CLAVES_CONDICION = ("codigo", "clase", "condicion", "tramite", "entidad", "fuente")


def catalogo_condiciones(por_perfil: dict) -> list[dict]:
    """
    Catálogo único de condiciones del lote y compactación de la columna de cada uno.

    Cada lote llega con la lista completa de sus condiciones, y cada condición repite el
    trámite, la entidad y la fuente, que son los mismos para todos los lotes que la
    comparten. El catálogo se escribe una sola vez y en cada lote quedan solo el código de
    la condición y el detalle medido en ese lote. La ficha vuelve a unir las dos partes.
    """
    catalogo: dict[str, dict] = {}
    try:
        import lotes as _lt
        for c in _lt.CONDICIONES:
            catalogo[c["codigo"]] = {k: c.get(k) for k in CLAVES_CONDICION}
    except Exception:
        pass
    for filas in por_perfil.values():
        for f in filas:
            bruto = f.get("condiciones")
            try:
                lista = json.loads(bruto) if isinstance(bruto, str) else list(bruto or [])
            except (TypeError, ValueError):
                lista = []
            compacta = []
            for c in lista:
                codigo = c.get("codigo")
                if not codigo:
                    continue
                catalogo.setdefault(codigo, {k: c.get(k) for k in CLAVES_CONDICION})
                compacta.append([codigo, c.get("detalle") or ""])
            f["condiciones"] = compacta
    return list(catalogo.values())


def compartir_textos(por_perfil: dict) -> list[str]:
    """Sustituye los textos largos repetidos por su posición en una tabla común."""
    tabla: dict[str, int] = {}
    for filas in por_perfil.values():
        for f in filas:
            for c in TEXTOS_COMPARTIDOS:
                if c not in f:
                    continue
                v = f.get(c)
                if isinstance(v, str) and v.strip():
                    f[c] = tabla.setdefault(v, len(tabla))
                else:
                    f[c] = None
    return list(tabla)


def construir(ruta_grillas: Path, con_satelital: bool = True,
              perfiles: list[str] | None = None,
              imagenes_por_celda: int = IMAGENES_POR_CELDA) -> dict:
    """Diccionario completo del reporte: celdas, lotes por perfil con geometría e imagen, y metadatos."""
    perfiles = perfiles or list(rg.PERFILES)
    grillas = cargar_grillas(ruta_grillas)
    ids = set(grillas["cell_id"])
    print(f"  grillas recibidas : {len(ids)}  ({ruta_grillas.name})")

    cobertura = cobertura_catastral(grillas)
    red = red_electrica(grillas)
    n_lin = sum(len(v["lineas"]) for v in red.values())
    n_sub = sum(len(v["subestaciones"]) for v in red.values())
    n_pla = sum(len(v["plantas"]) for v in red.values())
    print(f"  red electrica      : {n_lin} tramos de linea, {n_sub} subestaciones y "
          f"{n_pla} plantas registradas en las grillas y sus {MARGEN_RED_GRADOS * 111.32:.0f} km de entorno")
    danes = [str(d).zfill(5) for d in grillas["dane_municipio"].dropna()] if "dane_municipio" in grillas.columns else []
    gestores = gestores_catastrales(danes)
    celdas = []
    for _, r in grillas.iterrows():
        geom = r.geometry.simplify(TOLERANCIA, preserve_topology=True)
        dane = str(r.get("dane_municipio") or "").zfill(5) if pd.notna(r.get("dane_municipio")) else ""
        fila_celda = {c: _limpio(r.get(c)) for c in CAMPOS_CELDA if c in grillas.columns}
        # El catastro y las capas de subestaciones traen el uso de mayúsculas de origen
        # («DEPARTAMENTO», «Villa Del Rio», «Villa rio 115 kV»): se normaliza al
        # escribirlo, no al leerlo, para no tocar ninguna clave de cruce.
        for c in ("municipio", "departamento", "sub_nombre_subestacion", "operador"):
            if c in fila_celda:
                fila_celda[c] = _titulo(fila_celda[c])
        if "vereda" in fila_celda:
            fila_celda["vereda"] = _nombre_o_nada(fila_celda["vereda"])
        celdas.append({**fila_celda,
                       "red": red.get(str(r["cell_id"])),
                       "catastro_pct": cobertura.get(str(r["cell_id"])),
                       "gestor_catastral": gestores.get(dane),
                       "bbox": [round(v, 6) for v in r.geometry.bounds],
                       "geom": mapping(geom), "sat": None})

    lotes = {}
    sin_evaluar = None
    for perfil in perfiles:
        g = cargar_lotes(perfil, ids)
        print(f"  lotes {perfil:<12}: {len(g)} en {g['cell_id'].nunique()} celdas")
        # Grillas sin ningún lote evaluado (ni seleccionado ni descartado): falta correr
        # predios.lotes sobre ellas.
        if sin_evaluar is None:
            desc = SALIDA / f"lotes_{perfil}_descartados.csv"
            vistas = set(g["cell_id"])
            if desc.exists():
                vistas |= set(pd.read_csv(desc, usecols=["cell_id"], dtype=str)["cell_id"]
                              .astype(str).str.zfill(7))
            sin_evaluar = sorted(ids - vistas)
        # Las lecturas de folio se buscan una sola vez por perfil, no lote a lote.
        _CERTIF = lectura_certificados(g.get("matricula_inmobiliaria", []))
        if _CERTIF:
            print(f"  certificados leídos: {len(_CERTIF)}")
        filas = []
        for _, r in g.iterrows():
            geom = r.geometry.simplify(_tolerancia(r.get("area_ha")), preserve_topology=True)
            fila = {c: _limpio(r.get(c)) for c in CAMPOS_LOTE if c in g.columns}
            # La lectura del folio, si ese lote tiene certificado leido. Viaja con el
            # lote para que la ficha la pueda imprimir sin volver a consultar nada.
            _m = fila.get("matricula_inmobiliaria")
            if _m:
                _c = _CERTIF.get(str(_m).split(";")[0].strip())
                if _c:
                    fila["certificado"] = _c
            for c in ("municipio", "municipio_celda", "departamento", "conexion_nombre",
                      "nombre_predio"):
                if c in fila:
                    fila[c] = _titulo(fila[c])
            for c in CAMPOS_PROSA:
                if c in fila:
                    fila[c] = _coma_decimal(fila[c])
            # El motivo de una corrida anterior cierra citando el agregado de cobertura
            # que se retiró; se vuelve a redactar con las clases de este mismo lote.
            if fila.get("motivo"):
                fila["motivo"] = _remedir_motivo(fila)
            # El reparto del POT suma solapes de la capa de origen sin disolverlos, de modo
            # que en algunos lotes pasa del 100 %. No se puede corregir aquí sin rehacer el
            # cruce, así que se acota a 100, se conserva la cifra cruda y la ficha lo
            # declara. Ver la nota del POT en el cuadro de fuentes.
            for c in ("pot_categoria_pct", "pot_proteccion_pct"):
                v = fila.get(c)
                if v is not None and v > 100:
                    fila[c + "_bruto"] = v
                    fila[c] = 100.0
                    fila["pot_solape"] = True
            # Municipio sin zonificación rural publicada en la capa nacional: si aun así
            # sale una categoría, la ponen polígonos de un municipio vecino y no describen
            # la norma del municipio del lote. Se deduce del propio dato, de modo que vale
            # para cualquier municipio del país.
            if (str(fila.get("pot_cobertura") or "") == "sin cartografía"
                    and fila.get("pot_categoria")):
                fila["pot_municipio_ajeno"] = True
            # Porcentaje del lote bajo agua y en zona inundable: la casilla existente solo
            # dice sí o no; el porcentaje permite graduar el criterio.
            for destino, origen in (("pct_cuerpo_agua", "ent_cuerpo_agua_ha"),
                                    ("pct_zip", "ent_zip_ha")):
                if fila.get(destino) is None and fila.get(origen) is not None and fila.get("area_ha"):
                    fila[destino] = round(100.0 * float(fila[origen]) / float(fila["area_ha"]), 2)
            # Desajuste entre el área que declara el catastro y la que mide la geometría.
            if fila.get("area_terreno_catastro_m2") and fila.get("area_ha"):
                fila["desajuste_catastro_pct"] = round(
                    abs(float(fila["area_terreno_catastro_m2"]) / 1e4 - float(fila["area_ha"]))
                    / max(1e-9, float(fila["area_ha"])) * 100, 1)
            fila["geom"] = mapping(geom)
            fila["bbox"] = [round(v, 6) for v in r.geometry.bounds]
            fila["centro"] = [round(v, 6) for v in (r.geometry.centroid.x, r.geometry.centroid.y)]
            fila["_geom_real"] = r.geometry
            filas.append(fila)
        lotes[perfil] = _ordenar_por_area(filas)

    if sin_evaluar:
        print(f"  AVISO: {len(sin_evaluar)} de las {len(ids)} grillas recibidas no tienen "
              f"lotes evaluados: {', '.join(sin_evaluar[:8])}{' ...' if len(sin_evaluar) > 8 else ''}")
        print(f"         Córrelas antes con:  python -m predios.lotes --celdas "
              f"{','.join(sin_evaluar[:8])}{',...' if len(sin_evaluar) > 8 else ''}")
        print(f"         (baja el catastro del IGAC, mide terreno y clasifica; luego repite este comando)")

    condiciones_catalogo = catalogo_condiciones(lotes)
    textos = compartir_textos(lotes)

    if con_satelital:
        # Fondo del mapa de cada celda: imagen del envolvente de la celda y de todos sus
        # lotes, porque un lote grande sobresale de la celda y quedaría fuera de la foto.
        for c in celdas:
            x0, y0, x1, y1 = c["bbox"]
            for fs in lotes.values():
                for f in fs:
                    if f["cell_id"] == c["cell_id"]:
                        b = f["bbox"]
                        x0, y0, x1, y1 = min(x0, b[0]), min(y0, b[1]), max(x1, b[2]), max(y1, b[3])
            from shapely.geometry import box as _box
            c["sat"] = satelital_lote(f"celda_{c['cell_id']}", _box(x0, y0, x1, y1), px=1000, margen=0.05)
        # Se descargan las de los mayores de cada grilla y perfil, una vez por lote aunque
        # esté en los dos perfiles; en paralelo (8 hilos). El resto va bajo demanda.
        from concurrent.futures import ThreadPoolExecutor
        elegidos = {}
        for perfil, fs in lotes.items():
            por_celda = {}
            for f in fs:
                por_celda.setdefault(f["cell_id"], []).append(f)
            for fs_c in por_celda.values():
                fs_c.sort(key=lambda f: -(f.get("area_ha") or 0))
                top = fs_c if imagenes_por_celda < 0 else fs_c[:imagenes_por_celda]
                for f in top:
                    elegidos.setdefault(f["CODIGO"], (perfil, f))
        tareas = list(elegidos.values())
        print(f"  imágenes satelitales: {len(tareas)} lotes "
              f"({'todos' if imagenes_por_celda < 0 else f'hasta {imagenes_por_celda} por grilla y perfil'}), 8 hilos ...")
        def _una(par):
            perfil, f = par
            return satelital_lote(f"{perfil[:1]}_{f['CODIGO']}", f["_geom_real"])
        imgs = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            for (perfil, f), s in zip(tareas, ex.map(_una, tareas)):
                imgs[f["CODIGO"]] = s
        for fs in lotes.values():
            for f in fs:
                f["sat"] = imgs.get(f["CODIGO"])
        ok = sum(1 for s in imgs.values() if s)
        print(f"  imágenes obtenidas: {ok} de {len(tareas)}; las demás se cargan al abrir la ficha")
        # Sentinel-2 se retiro de la ficha el 26 de agosto de 2026, por decision del
        # cliente: a 10 metros por pixel la escena no deja ver un lindero, y al lado de
        # la imagen de alta resolucion solo aportaba ruido. Tampoco se descarga ya, para
        # no gastar tiempo ni disco en algo que no se muestra. La funcion sentinel_lote
        # se conserva por si vuelve a hacer falta el estado reciente del terreno.
        # Las imágenes son insumo y viven en el bucket, no en el repositorio: se publican
        # las que falten allí, para que otra máquina no vuelva a pedirlas a Esri. Con
        # PROSPECTOS_SIN_BUCKET=1 se omite (se publican después con `python -m insumos subir`).
        import os
        if os.environ.get("PROSPECTOS_SIN_BUCKET"):
            print("  publicación en el bucket omitida (PROSPECTOS_SIN_BUCKET); correr `python -m insumos subir`")
        else:
          try:
              import gcs
              from insumos import satelital as sat
              n = gcs.subir_carpeta(sat.BUCKET, sat.PREFIJO, sat.CACHE, "sat_lote_*.jpg", verbose=False)
              n += gcs.subir_carpeta(sat.BUCKET, sat.PREFIJO, sat.CACHE, "sat_lote_*.fecha", verbose=False)
              n += gcs.subir_carpeta(sat.BUCKET, sat.PREFIJO, sat.CACHE, "sat_s2_lote_*.*", verbose=False)
              print(f"  publicadas en el bucket: {n} nuevas")
          except Exception as exc:
              print(f"  aviso: no se pudo publicar en el bucket ({type(exc).__name__}); "
                    f"quedan en data/satelital/ y se subirán en la próxima corrida con acceso")
    for fs in lotes.values():
        for f in fs:
            f.pop("_geom_real", None)

    from insumos import satelital as sat
    import lotes as lt
    _portales = portales(grillas)
    # La tabla de vigencia verificada cubre todos los municipios comprobados hasta hoy; al
    # documento solo viajan los de esta selección, para que no lleve datos de municipios
    # que no aparecen en él.
    danes_lote = {str(f.get("CODIGO") or "").zfill(30)[:5]
                  for fs in lotes.values() for f in fs} | set(danes)
    return {
        "generado": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "origen_grillas": ruta_grillas.name,
        "origen_nota": origen_nota(grillas, gestores),
        "embudo": embudo(perfiles[0], ids),
        "perfiles": {k: {"etiqueta": v["etiqueta"], "ha_proyecto": v["ha_proyecto"],
                         "mw_proyecto": v["mw_proyecto"],
                         "ancho_minimo_m": round(lt.ancho_minimo(v["ha_proyecto"]))}
                     for k, v in rg.PERFILES.items()},
        "ha_minima": lt.HA_MINIMA_CARACTERIZAR,
        "sat_servicio": sat.SERVICIO,
        "sat_px": 1200,
        "sat_margen": 0.25,
        "criterios": {k: {"etiqueta": ETIQUETA_CRITERIO.get(k, v["etiqueta"]),
                          "unidad": v.get("unidad", ""),
                          "limite": v["limite"], "bueno": v["bueno"], "tope": v["tope"],
                          "mayor_mejor": bool(v["mayor_mejor"]), "d_cohen": v["d_cohen"]}
                      for k, v in rg.CRITERIOS.items()},
        "pesos": {k: dict(v.get("pesos") or {c: rg.CRITERIOS[c]["d_cohen"] for c in rg.CRITERIOS})
                  for k, v in rg.PERFILES.items()},
        # Cada perfil tiene sus propios límite/bueno/tope (rg.aplicar_perfil los escribe en
        # CRITERIOS); el visor los necesita por perfil para reconstruir el índice.
        "umbrales": {k: rg.umbrales_de(k, "lote") for k in rg.PERFILES},
        "umbrales_escala": {k: ("lote" if rg.PERFILES[k].get("umbrales_lote") else "grilla") for k in rg.PERFILES},
        "indice_prioritaria": rg.INDICE_PRIORITARIA,
        "fuentes": [{"fuente": f, "aporta": a, "version": v, "url": u, "portal": _portales.get(f)} for f, a, v, u in FUENTES],
        "notas_fuentes": [{"titulo": t, "parrafos": ps}
                          for t, ps in notas_fuentes(lotes)],
        "vigencia_pot": {d: v for d, v in VIGENCIA_POT.items() if d in danes_lote},
        "vigencia_pot_fecha": VIGENCIA_POT_FECHA,
        "ha_por_mwp": rg.HA_POR_MWP,
        "objetivo_agregacion_ha": OBJETIVO_AGREGACION_HA,
        "margen_red_km": round(MARGEN_RED_GRADOS * 111.32, 1),
        "costo_certificado": registro.COSTO_CERTIFICADO,
        "url_snr": "https://certificados.supernotariado.gov.co/certificado",
        "condiciones_catalogo": condiciones_catalogo,
        "textos": textos,
        "textos_campos": list(TEXTOS_COMPARTIDOS),
        "celdas": celdas,
        "lotes": lotes,
    }


def main(argv=None) -> int:
    """CLI: construye el JSON del reporte a partir del archivo de grillas."""
    ap = argparse.ArgumentParser(description="Datos del reporte de lotes")
    ap.add_argument("--grillas", default=str(GRILLAS_DEFECTO),
                    help="GeoJSON/GPKG/CSV con las celdas exportadas del reporte de grillas")
    ap.add_argument("--sin-satelital", action="store_true",
                    help="no descarga imágenes (más rápido, la ficha las carga del servicio)")
    ap.add_argument("--imagenes", type=int, default=IMAGENES_POR_CELDA,
                    help=f"imágenes descargadas por grilla y perfil, las de mayor área "
                         f"(por defecto {IMAGENES_POR_CELDA}; -1 todas, 0 ninguna)")
    ap.add_argument("--perfil", default=None, help="solo un perfil")
    a = ap.parse_args(argv)

    ruta = Path(a.grillas)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Exporta la selección desde el reporte de "
                         f"grillas (botón de descarga GeoJSON) o pásala con --grillas.")

    print("=" * 74)
    print("REPORTE DE LOTES · datos")
    print("=" * 74)
    d = construir(ruta, con_satelital=not a.sin_satelital,
                  perfiles=[a.perfil] if a.perfil else None, imagenes_por_celda=a.imagenes)
    JSON_SALIDA.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
    print(f"  JSON -> {JSON_SALIDA.name}  ({JSON_SALIDA.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
