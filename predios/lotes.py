"""Selección de lotes en las celdas candidatas: mide, describe y clasifica los predios
del catastro de cada celda. Método y justificación en docs/PREDIOS.md.

La clase de cada lote sale de sus condiciones comprobadas, no de un umbral del índice:
"No viable" si tiene alguna condición que ninguna gestión resuelve (categoría de
protección en el POT, título minero vigente, figura territorial que no se puede ocupar),
"Viable con gestión" si tiene alguna que sí se resuelve con un trámite conocido (supera
la Unidad Agrícola Familiar, inundación en episodios de La Niña, microzona de restitución,
humedal en el lote) e "Idóneo" si no tiene ninguna. Cada lote
lleva escrita la lista de sus condiciones con el trámite y la entidad que exige cada una
(ver CONDICIONES). El índice queda como descriptor y no ordena ni clasifica.

Entradas: celdas (GeoJSON o CSV del reporte de grillas, o códigos separados por comas;
sin ellas, las cien del reporte) e insumos cacheados en data/ (catastro IGAC, DEM,
cobertura, vías OSM). Salidas en outputs/reporte/ por perfil: lotes_<perfil>.csv
y .geojson (las tres clases de aptitud), _descartados.csv (el lote excluido de entrada,
el que no tiene área medible y el menor que el mínimo) y lotes.gpkg.
Compacidad: se calcula, no filtra (un corte en 0,30 descartaría el 21% de los 378 predios
de 150 ha o más; correlación 0,18 con el ancho útil). Distancia a vía: puntúa pero casi
no separa (mediana 166 m; 39% dentro del tope de 100 m; 6% pasado el límite de 1,5 km).
Uso: .venv\\Scripts\\python.exe -m predios.lotes [--perfil P] [--celdas X] [--justificar]
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
# Raíz, soporte/ y predios/ al path: config y gcs viven en soporte/ y los módulos hermanos
# se importan planos, tanto desde el cuaderno como con `python -m predios.lotes`.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config
import predios_igac as pig
import reporte.datos as rg
import terreno

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

# --------------------------------------------------------------------------
# Umbrales propios del lote
# --------------------------------------------------------------------------
#
# Los criterios del índice se leen de rg.CRITERIOS; aquí solo van los umbrales que no
# existen a escala de celda.

#: El tamaño no descarta: lo filtra el usuario en el visor según el proyecto que busque.
#: Los perfiles quedan como preajustes del filtro y como referencia del índice. Se
#: caracteriza (jurídico, valor, entorno, POT) todo predio no excluido con al menos esta
#: área bruta, el mínimo con sentido para un proyecto de 2 MW; por debajo se mide, se
#: clasifica "Pequeño" y va al CSV de descartes con su medida. Se cambia con --ha-minima.
HA_MINIMA_CARACTERIZAR = 2.0

#: Destinos económicos que descartan el predio, con el motivo. Solo el habitacional, único
#: cuyo significado está verificado contra la base (mediana 0,08 ha, 85% con construcción).
DESTINOS_EXCLUIDOS = {"A": "lote de destino habitacional"}

#: Retranqueo en metros para el área de núcleo. Cubre retiro a linderos y vía perimetral;
#: una franja de menos de 60 m de ancho desaparece al erosionarla.
RETRANQUEO_M = 30.0

def ancho_minimo(ha_proyecto: float) -> float:
    """
    Ancho útil mínimo en metros: lado de un bloque cuadrado con la décima parte de las
    hectáreas del perfil (387 m para 150 ha, 45 m para 2 ha). Las plantas se construyen
    por bloques separados por viales.
    """
    return round(np.sqrt(ha_proyecto / 10 * 10_000), 0)


#: Factor de aprovechamiento por pendiente, el mismo del reporte de grillas para que las
#: hectáreas del lote y las de la celda sean sumables.
FACTOR_PENDIENTE = rg.FACTOR_PENDIENTE

#: Hectáreas por MWp, huella típica en suelo con seguidor de un eje.
HA_POR_MWP = rg.HA_POR_MWP


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------

def cargar_celdas(ruta: str | None = None, celdas: str | None = None) -> gpd.GeoDataFrame:
    """Celdas sobre las que se buscan lotes, resueltas por predios_igac.resolver_celdas."""
    return pig.resolver_celdas(celdas or ruta, "todas")


def cargar_predios(celdas: gpd.GeoDataFrame, verbose: bool = True,
                   forzar: bool = False) -> gpd.GeoDataFrame:
    """
    Predios de las celdas, ya medidos. Reutiliza outputs/reporte/predios.gpkg solo si su
    conjunto de celdas coincide exactamente con el pedido; si no, los rehace desde el
    crudo cacheado (unos doce minutos para las cien celdas).
    """
    cw = celdas.to_crs(config.CRS_GEOGRAFICO)
    esperadas = {str(c) for c in celdas["cell_id"]
                 if all(pig._raw(str(c), t).exists() for t in pig.CAPAS.values())}

    atajo = SALIDA / "predios.gpkg"
    corte = SALIDA / "predios.corte"
    mismo_corte = corte.exists() and corte.read_text(encoding="utf-8").strip() == pig.CORTE
    if atajo.exists() and not forzar and esperadas and mismo_corte:
        try:
            g = gpd.read_file(atajo)
            g["cell_id"] = g["cell_id"].astype(str)
            # Las celdas descargadas sin ningún predio no aparecen en el GPKG; se compara
            # contra las que sí tienen alguno.
            con_predios = {c for c in esperadas
                           if any(json.loads(pig._raw(c, t).read_text(encoding="utf-8"))
                                  .get("features") for t in pig.CAPAS.values())}
            if (set(g["cell_id"]) == con_predios and "ancho_util_m" in g.columns
                    and "numero_predial_anterior" in g.columns):
                if verbose:
                    print(f"  lotes: reutilizando {atajo.name}, cubre exactamente las "
                          f"{len(con_predios)} grillas con lotes")
                g.attrs["celdas_sin_descarga"] = sorted(
                    {str(c) for c in celdas["cell_id"]} - esperadas)
                return g
        except Exception:
            pass

    trozos, sin_descarga = [], []
    for _, r in cw.iterrows():
        cid = str(r["cell_id"])
        if not all(pig._raw(cid, t).exists() for t in pig.CAPAS.values()):
            sin_descarga.append(cid)
            continue
        g = pig.procesar_celda(cid, r.geometry)
        if len(g):
            trozos.append(g)

    if sin_descarga and verbose:
        print(f"  {len(sin_descarga)} grillas sin lotes descargados. Para traerlos:")
        print(f"    .venv\\Scripts\\python.exe predios_igac.py --celdas "
              f"{','.join(sin_descarga[:5])}{'...' if len(sin_descarga) > 5 else ''}")
    if not trozos:
        raise SystemExit("Ninguna de las grillas pedidas tiene lotes descargados")

    p = gpd.GeoDataFrame(pd.concat(trozos, ignore_index=True),
                         geometry="geometry", crs=config.CRS_GEOGRAFICO)
    p = pig.medir(p)
    p.attrs["celdas_sin_descarga"] = sin_descarga
    # Se deja el atajo para la próxima corrida, con el corte del catastro que lo produjo.
    try:
        p.to_file(atajo, driver="GPKG")
        corte.write_text(pig.CORTE, encoding="utf-8")
    except Exception:
        pass
    return p


def asignar_celda_unica(p: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame,
                        verbose: bool = True) -> gpd.GeoDataFrame:
    """
    Un predio, una celda: el que cruza el lindero de la grilla (461 de 22.658 en las cien
    celdas) se queda en la celda con la que comparte más superficie.
    """
    dup = p["CODIGO"].duplicated(keep=False)
    if not dup.any():
        return p

    cm = celdas.to_crs(config.CRS_METRICO).set_index(celdas["cell_id"].astype(str))
    pm = p.loc[dup].to_crs(config.CRS_METRICO)
    solape = [
        g.intersection(cm.loc[c].geometry).area if c in cm.index else 0.0
        for g, c in zip(pm.geometry, pm["cell_id"].astype(str))
    ]
    orden = p.assign(_s=0.0)
    orden.loc[dup, "_s"] = solape
    quedan = (orden.sort_values("_s", ascending=False)
                   .drop_duplicates(subset=["CODIGO"], keep="first").index)
    fuera = len(p) - len(quedan)
    if verbose and fuera:
        print(f"  lotes que cruzan el lindero de la grilla: {fuera} copias retiradas, "
              f"cada una se queda en la celda con la que más superficie comparte")
    return p.loc[sorted(quedan)].reset_index(drop=True)


# --------------------------------------------------------------------------
# Medidas que solo tienen sentido en el predio
# --------------------------------------------------------------------------

def añadir_forma(p: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Área de núcleo (predio retranqueado RETRANQUEO_M) y su fracción del área bruta."""
    p = p.copy()
    m = p.to_crs(config.CRS_METRICO)
    nucleo = m.geometry.buffer(-RETRANQUEO_M)
    p["area_nucleo_ha"] = (nucleo.area / 10_000).round(2)
    p["nucleo_frac"] = (p["area_nucleo_ha"] / p["area_ha"].replace(0, np.nan)).round(3)
    return p


def añadir_dist_via(p: gpd.GeoDataFrame, verbose: bool = True) -> gpd.GeoDataFrame:
    """
    Distancia a la vía carrozable más cercana desde el lindero (dist_via_km, la que puntúa,
    porque el acceso se construye hasta el lindero) y desde el centroide (auxiliar), más la
    distancia a vía principal. Usa Overpass cacheado en data/osm/; sin cobertura queda NaN.
    """
    p = p.copy()
    p["dist_via_km"] = np.nan
    p["dist_via_centro_km"] = np.nan
    p["dist_via_principal_km"] = np.nan
    try:
        import insumos.vias as dv
    except Exception as exc:
        if verbose:
            print(f"  vías: módulo no disponible ({type(exc).__name__})")
        return p

    archivos = sorted(dv.CACHE.glob("vias_*.json"))
    if not archivos:
        if verbose:
            print("  vías: no hay respuestas de Overpass cacheadas en data/osm/")
        return p

    sec, pri = [], []
    for f in archivos:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sec.extend(dv.a_lineas(d))
        pri.extend(dv.a_lineas(d, solo=dv.PRIMARIA))

    pm = p.to_crs(config.CRS_METRICO)
    centros = gpd.GeoSeries(pm.geometry.representative_point(), crs=pm.crs)

    for lineas, geoms, col in ((sec, pm.geometry, "dist_via_km"),
                               (sec, centros, "dist_via_centro_km"),
                               (pri, pm.geometry, "dist_via_principal_km")):
        if not lineas:
            continue
        red = gpd.GeoSeries(lineas, crs=config.CRS_GEOGRAFICO).to_crs(config.CRS_METRICO)
        j = red.sindex.nearest(geoms, return_all=False)[1]
        d = geoms.distance(red.iloc[j].reset_index(drop=True), align=False).values
        p[col] = np.round(d / 1000, 3)

    if verbose:
        n = int(np.isfinite(p["dist_via_km"]).sum())
        tope = rg.CRITERIOS["dist_via"]["tope"]
        limite = rg.CRITERIOS["dist_via"]["limite"]
        print(f"  vías: {n} de {len(p)} lotes medidos desde el lindero. "
              f"Mediana {np.nanmedian(p['dist_via_km']):.3f} km; "
              f"{(p['dist_via_km'] <= tope).mean() * 100:.0f}% dentro del tope de "
              f"{tope:g} km y {(p['dist_via_km'] > limite).mean() * 100:.0f}% pasado el "
              f"límite de {limite:g} km, así que el criterio casi no separa")
    return p


def añadir_conexion(p: gpd.GeoDataFrame, kv_min: float, kv_max: float,
                    verbose: bool = True) -> gpd.GeoDataFrame:
    """
    Distancia del lindero a la subestación más cercana dentro del rango de tensión del
    perfil (hasta 115 kV distribuida, hasta 230 kV utility); se recalcula por perfil.
    """
    p = p.copy()
    s = gpd.read_file(config.SUBESTACIONES_PATH)
    if s.crs is None:
        s = s.set_crs(config.CRS_GEOGRAFICO)
    kv = rg._num(s.get("tension", pd.Series(dtype=str))).where(lambda x: x > 0)
    s = s[kv.between(kv_min, kv_max, inclusive="both")].copy()
    s["_kv"] = kv[kv.between(kv_min, kv_max, inclusive="both")].values

    sm = s.to_crs(config.CRS_METRICO).reset_index(drop=True)
    pm = p.to_crs(config.CRS_METRICO)
    col_nom = next((c for c in ("nombre_subestacion", "nombre") if c in sm.columns), None)

    # nearest vectorizado sobre el índice espacial; predio a predio tardaría minutos.
    j = sm.sindex.nearest(pm.geometry, return_all=False)[1]
    cercana = sm.iloc[j]
    p["conexion_km"] = np.round(
        pm.geometry.distance(cercana.geometry, align=False).values / 1000, 2)
    p["conexion_nombre"] = cercana[col_nom].values if col_nom else None
    p["conexion_kv"] = cercana["_kv"].values
    dist = p["conexion_km"].values
    if verbose:
        print(f"  conexión: {len(sm)} subestaciones en {kv_min:.0f}-{kv_max:.0f} kV, "
              f"mediana al lindero {np.nanmedian(dist):.1f} km")
    return p


def añadir_terreno(p: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame,
                   verbose: bool = True) -> gpd.GeoDataFrame:
    """Pendiente, rugosidad y cobertura medidas dentro del predio. Ver terreno.py."""
    try:
        m = terreno.metricas(p, celdas, verbose=False)
    except Exception as exc:
        print(f"  terreno: no disponible ({type(exc).__name__}: {str(exc)[:60]})")
        return p
    p = p.copy()
    for c in m.columns:
        p[c] = m[c].values
    if verbose and "pendiente_media" in p.columns:
        n = int(p["pendiente_media"].notna().sum())
        print(f"  terreno: {n} de {len(p)} lotes con pendiente y cobertura propias "
              f"({len(p) - n} demasiado pequeños para un píxel de 30 m)")
    return p


def añadir_area_util(p: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Potencia indicativa del lote y una estimación auxiliar de superficie aprovechable.

    `mwp_lote` es el área catastral del lote entre las hectáreas por MWp, una huella de
    referencia de ingeniería fijada en 1,5 ha/MWp para planta en suelo con seguidor de un
    eje; no la publica ninguna entidad colombiana. El área catastral y los porcentajes de
    cobertura por clase son lo que se muestra y se filtra; `area_util_ha`
    (núcleo a 30 m × cobertura apta × factor de pendiente) es una heurística propia sin
    fuente externa: queda en el CSV como columna auxiliar, no viaja al reporte de lotes
    y no clasifica ni filtra.
    """
    p = p.copy()
    apta = p.get("cobertura_apta_pct", pd.Series(np.nan, index=p.index)) / 100.0
    pend = p.get("pendiente_media", pd.Series(np.nan, index=p.index))

    factor = pd.Series(np.nan, index=p.index)
    for limite, f in reversed(FACTOR_PENDIENTE):
        factor = factor.mask(pend <= limite, f)
    factor = factor.mask(pend.isna(), np.nan)

    p["mwp_lote"] = (p["area_ha"] / HA_POR_MWP).round(1)
    p["area_util_ha"] = (p["area_nucleo_ha"].clip(lower=0) * apta * factor).round(2)
    return p


# Los dos primeros dígitos del código catastral son el código DANE del departamento;
# sirve de respaldo cuando la capa de límites del MGN no se descargó.
DANE_DPTO = {
    "05": "Antioquia", "08": "Atlántico", "11": "Bogotá D.C.", "13": "Bolívar",
    "15": "Boyacá", "17": "Caldas", "18": "Caquetá", "19": "Cauca", "20": "Cesar",
    "23": "Córdoba", "25": "Cundinamarca", "27": "Chocó", "41": "Huila",
    "44": "La Guajira", "47": "Magdalena", "50": "Meta", "52": "Nariño",
    "54": "Norte de Santander", "63": "Quindío", "66": "Risaralda",
    "68": "Santander", "70": "Sucre", "73": "Tolima", "76": "Valle del Cauca",
    "81": "Arauca", "85": "Casanare", "86": "Putumayo", "88": "San Andrés",
    "91": "Amazonas", "94": "Guainía", "95": "Guaviare", "97": "Vaupés",
    "99": "Vichada",
}


def departamento_dane(p: pd.DataFrame) -> pd.Series:
    """Departamento leído del código catastral del predio."""
    col = next((c for c in ("CODIGO", "codigo") if c in p.columns), None)
    if col is None:
        return pd.Series(None, index=p.index, dtype=object)
    return p[col].astype(str).str.zfill(30).str[:2].map(DANE_DPTO)


_DIVIPOLA: dict[str, str] | None = None


def divipola() -> dict[str, str]:
    """
    Código DANE de municipio (5 dígitos) a nombre, leído de la base veredal del DANE y
    cacheado en memoria; diccionario vacío si la base no está disponible.
    """
    global _DIVIPOLA
    if _DIVIPOLA is not None:
        return _DIVIPOLA
    _DIVIPOLA = {}
    ver = config.PROJECT_ROOT / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    if not ver.exists():
        return _DIVIPOLA
    try:
        v = gpd.read_file(ver, ignore_geometry=True)
    except Exception:
        return _DIVIPOLA
    cod = next((c for c in v.columns if c.upper() in ("DPTOMPIO", "MPIO_CDPMP", "COD_MPIO")), None)
    nom = next((c for c in v.columns if c.upper() in ("NOM_MUN", "NOMBRE_MUN", "MPIO_CNMBR", "NOMB_MPIO")), None)
    if cod and nom:
        t = v[[cod, nom]].dropna().drop_duplicates(subset=[cod])
        _DIVIPOLA = {str(c).split(".")[0].zfill(5): str(n).strip().title()
                     for c, n in zip(t[cod], t[nom])}
    return _DIVIPOLA


def municipio_dane(p: pd.DataFrame) -> pd.Series:
    """
    Municipio según los cinco primeros dígitos del código catastral. Difiere del de la
    celda cuando el predio cruza el límite municipal, y es el que vale para el trámite.
    """
    col = next((c for c in ("CODIGO", "codigo") if c in p.columns), None)
    if col is None:
        return pd.Series(None, index=p.index, dtype=object)
    return p[col].astype(str).str.zfill(30).str[:5].map(divipola())


# --------------------------------------------------------------------------
# Las tres clases y las condiciones que las producen
# --------------------------------------------------------------------------
#
# La clase de un lote no sale del índice: sale de las condiciones comprobadas sobre ese
# lote. El índice es un descriptor que resume qué tan bien puntúa el terreno frente a los
# criterios del perfil, y como descriptor viaja a la ficha; no ordena la lista ni decide
# la clase. Las tres clases son:
#
#   No viable           el lote tiene al menos una condición que ninguna gestión del
#                       proyecto resuelve: categoría de protección en el POT, título
#                       minero vigente o una figura territorial que no se puede ocupar.
#   Viable con gestión  el lote tiene al menos una condición que sí se resuelve con un
#                       trámite conocido ante una entidad conocida, y ninguna del grupo
#                       anterior. La ficha enumera cuáles son y qué exige cada una.
#   Idóneo              ninguna condición adversa en las fuentes consultadas.
#
# "Excluido", "No apto" y "Pequeño" no son clases de aptitud: son lotes que no entran a
# caracterizarse (excluidos de entrada, sin área medible, o por debajo del mínimo de
# caracterización) y se publican aparte, con su medida y su motivo.

CLASE_NO_VIABLE = "No viable"
CLASE_GESTION = "Viable con gestión"
CLASE_IDONEO = "Idóneo"

#: Solape mínimo con una figura territorial (RUNAP, resguardo, consejo comunitario,
#: páramo) para que cuente: 1 ha o el 2% del área, lo que sea mayor. Por debajo es
#: desajuste de linderos entre capas de escala distinta y solo se anota.
FIGURA_MIN_HA = 1.0
FIGURA_MIN_PCT = 2.0

#: Superficie del lote en categorías de protección del POT, en porcentaje. No se mira qué
#: categoría es la mayor sino cuánto suelo queda en protección, que es lo que decide:
#:   la mitad del lote o más   el lote es suelo de protección y ninguna gestión lo cambia;
#:   entre el 10% y la mitad   la parte protegida no se puede ocupar pero el resto sí, así
#:                             que el proyecto se rediseña alrededor y eso es un trámite;
#:   menos del 10%             roce de linderos entre capas de escala distinta, solo se anota.
POT_PROTECCION_NO_VIABLE_PCT = 50.0
POT_PROTECCION_MIN_PCT = 10.0


def _num(r, col) -> float:
    """Valor numérico de una columna del lote; NaN si falta o no es número."""
    try:
        v = float(r.get(col))
    except (TypeError, ValueError):
        return float("nan")
    return v


def _txt(r, col) -> str:
    """Valor de texto de una columna del lote; cadena vacía si falta."""
    v = r.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _si(r, col) -> bool:
    """Verdadero o falso de una columna del lote, tolerando el texto de un CSV."""
    v = r.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("true", "sí", "si", "1", "verdadero")
    return bool(v)


def _cifra(x, dec: int = 0) -> str:
    """Número en formato español (punto de miles, coma decimal); 'sin dato' si falta."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "sin dato"
    return f"{x:,.{dec}f}".replace(",", "\u00b7").replace(".", ",").replace("\u00b7", ".")


#: Clases de cobertura del suelo de ESA WorldCover, con la columna que guarda el
#: porcentaje del lote en cada una y el nombre con que se escriben en el reporte. Son las
#: clases que publica la capa, sin combinar y sin ponderar: el reporte de lotes describe
#: la cobertura clase a clase y no calcula ningún agregado propio a partir de ellas.
CLASES_COBERTURA = [
    ("cob_pastizal_pct", "pastizal"),
    ("cob_bosque_pct", "bosque"),
    ("cob_cultivo_pct", "cultivo"),
    ("cob_matorral_pct", "matorral"),
    ("cob_construido_pct", "suelo construido"),
    ("cob_desnudo_pct", "suelo desnudo"),
    ("cob_humedal_pct", "humedal"),
    ("cob_agua_pct", "agua permanente"),
    ("cob_manglar_pct", "manglar"),
    ("cob_nieve_pct", "nieve y hielo"),
    ("cob_musgo_pct", "musgo y liquen"),
]

#: Columnas de cobertura del suelo, en el orden de la capa.
COLUMNAS_COBERTURA = [c for c, _ in CLASES_COBERTURA]

#: Rótulo con que se nombra un criterio del índice de aptitud cuando el del reporte de
#: grillas no describe lo que el lote publica. El criterio de cobertura se calibró sobre
#: una escala compuesta de este estudio; ni la ficha ni el CSV publican esa escala como
#: cifra del lote, y por eso el rótulo dice de dónde sale y para qué sirve.
ETIQUETA_CRITERIO = {
    "cobertura": "Cobertura del suelo, escala de calibración del índice",
}


def composicion_cobertura(r, minimo: float = 1.0, maximo: int = 3) -> str:
    """
    Composición de la cobertura del suelo del lote, de mayor a menor y con el porcentaje
    tal como lo publica ESA WorldCover. Sin ponderar y sin agregar: cada cifra se puede
    contrastar clase a clase con la capa. Cadena vacía si el lote no tiene cobertura
    medida (a 10 m, un lote menor de 0,01 ha no cae sobre ningún píxel).
    """
    partes = []
    for col, nombre in CLASES_COBERTURA:
        v = _num(r, col)
        if pd.notna(v) and v >= minimo:
            partes.append((float(v), nombre))
    if not partes:
        return ""
    partes.sort(key=lambda x: -x[0])
    return ", ".join(f"{nombre} {_cifra(v)} %" for v, nombre in partes[:maximo])


def _umbral_figura(r) -> float:
    """Hectáreas de solape a partir de las cuales una figura territorial cuenta."""
    a = _num(r, "area_ha")
    return max(FIGURA_MIN_HA, FIGURA_MIN_PCT / 100 * (0.0 if pd.isna(a) else a))


def _figura(col: str):
    """Prueba y detalle de una figura territorial medida en hectáreas dentro del lote."""
    def prueba(r):
        ha = _num(r, col + "_ha")
        return bool(pd.notna(ha) and ha >= _umbral_figura(r))
    def detalle(r):
        ha = _num(r, col + "_ha")
        nombre = _txt(r, col)
        return (f"{nombre}, {_cifra(ha, 1)} ha del lote" if nombre
                else f"{_cifra(ha, 1)} ha del lote")
    return prueba, detalle


def _detalle_proteccion(r) -> str:
    """Cuánto del lote queda en protección y en qué categorías, una por una.

    Nombrar solo la categoría dominante deja sin decir qué tipo de protección pesa
    sobre el resto del lote, y no es lo mismo una reserva forestal que un área de
    manejo especial: cambian el trámite y la entidad ante la que se surte.
    """
    pct = _num(r, "pot_rojo_pct")
    cat = _txt(r, "pot_categoria")
    rep = _txt(r, "pot_reparto")
    txt = f"{_cifra(pct)}% de la superficie del lote en categorías de protección"
    if rep and ";" in rep:
        txt += f". Reparto por categoría: {rep}"
    elif cat and _txt(r, "pot_semaforo") == "rojo":
        txt += f", la mayor de ellas {cat}"
    zon = _num(r, "pot_zonificado_pct")
    if pd.notna(zon) and zon < 99:
        txt += f"; la zonificación publicada alcanza el {_cifra(zon)}% del lote"
    return txt


def _detalle_humedal(r) -> str:
    """
    Lo que el inventario de humedales dice del lote, sin el código numérico de la capa:
    solo el grado de transformación, que es lo único legible de ese registro. Cuando la
    capa no trae grado, se dice que no lo trae en vez de suponerlo.
    """
    bruto = _txt(r, "ent_humedal")
    grado = bruto.split(" ", 1)[1].strip() if " " in bruto else ""
    if grado.lower() == "natural":
        return "humedal en estado natural según el inventario nacional de humedales"
    if grado.lower() == "transformado":
        return ("humedal ya transformado por uso del suelo según el inventario nacional "
                "de humedales")
    return ("humedal registrado en el inventario nacional, sin grado de transformación "
            "anotado en la fuente")


_p_runap, _d_runap = _figura("ent_runap")
_p_resguardo, _d_resguardo = _figura("ent_resguardo")
_p_consejo, _d_consejo = _figura("ent_consejo")
_p_paramo, _d_paramo = _figura("ent_paramo")


#: Catálogo de condiciones del lote. Cada entrada dice qué se encontró, a qué clase lleva,
#: qué trámite exige, ante qué entidad se hace y de qué fuente sale el dato. Es lo que la
#: ficha enumera lote por lote, y lo que sustituye al umbral del índice como clasificador.
CONDICIONES = [
    # ---------------- No viable ----------------
    {
        "codigo": "proteccion-pot",
        "clase": CLASE_NO_VIABLE,
        "condicion": "El plan de ordenamiento territorial clasifica el lote como suelo de protección",
        "prueba": lambda r: _num(r, "pot_rojo_pct") >= POT_PROTECCION_NO_VIABLE_PCT,
        "detalle": _detalle_proteccion,
        "tramite": ("El suelo de protección no admite un proyecto de generación. Cambiar esa "
                    "categoría exige una revisión del plan de ordenamiento adoptada por acuerdo "
                    "del concejo municipal, que no es un trámite que el proyecto pueda promover. "
                    "Antes de descartar el lote conviene pedir el certificado de uso del suelo, "
                    "que es el documento con valor legal y puede corregir la cartografía publicada."),
        "entidad": "Secretaría de Planeación del municipio",
        "fuente": "Zonificación de suelo rural del Instituto Geográfico Agustín Codazzi",
    },
    {
        "codigo": "titulo-minero",
        "clase": CLASE_NO_VIABLE,
        "condicion": "Título minero vigente sobre el lote",
        "prueba": lambda r: _num(r, "ent_mineria_titulos") > 0,
        "detalle": lambda r: _txt(r, "ent_mineria_detalle") or "título vigente sin detalle publicado",
        "tramite": ("El título minero es un derecho vigente sobre el área y prevalece mientras "
                    "dure. Solo se libera con acuerdo del titular o con la terminación del "
                    "título, ninguna de las dos cosas al alcance del proyecto."),
        "entidad": "Agencia Nacional de Minería",
        "fuente": "Catastro minero de la Agencia Nacional de Minería",
    },
    {
        "codigo": "area-protegida",
        "clase": CLASE_NO_VIABLE,
        "condicion": "Área protegida del Sistema Nacional de Áreas Protegidas dentro del lote",
        "prueba": _p_runap, "detalle": _d_runap,
        "tramite": ("El uso permitido dentro de un área protegida lo fija su plan de manejo y no "
                    "contempla generación en suelo. El área no se puede ocupar."),
        "entidad": "Parques Nacionales Naturales de Colombia",
        "fuente": "Registro Único Nacional de Áreas Protegidas, consultado en vivo",
    },
    {
        "codigo": "resguardo-indigena",
        "clase": CLASE_NO_VIABLE,
        "condicion": "Resguardo indígena titulado sobre el lote",
        "prueba": _p_resguardo, "detalle": _d_resguardo,
        "tramite": ("El territorio del resguardo es propiedad colectiva y no se puede comprar. "
                    "Cualquier intervención exige consulta previa con la comunidad titular."),
        "entidad": "Ministerio del Interior y Agencia Nacional de Tierras",
        "fuente": "Resguardos indígenas formalizados, datos abiertos de la Agencia Nacional de Tierras",
    },
    {
        "codigo": "consejo-comunitario",
        "clase": CLASE_NO_VIABLE,
        "condicion": "Territorio colectivo de comunidades negras titulado sobre el lote",
        "prueba": _p_consejo, "detalle": _d_consejo,
        "tramite": ("El territorio colectivo titulado a un consejo comunitario no se puede "
                    "comprar. Cualquier intervención exige consulta previa con el consejo."),
        "entidad": "Ministerio del Interior y Agencia Nacional de Tierras",
        "fuente": "Consejos comunitarios titulados, datos abiertos de la Agencia Nacional de Tierras",
    },
    {
        "codigo": "paramo",
        "clase": CLASE_NO_VIABLE,
        "condicion": "Páramo delimitado sobre el lote",
        "prueba": _p_paramo, "detalle": _d_paramo,
        "tramite": ("El páramo delimitado es suelo de protección y en él no se permiten "
                    "actividades de esta naturaleza."),
        "entidad": "Ministerio de Ambiente y Desarrollo Sostenible",
        "fuente": "Páramos delimitados del Ministerio de Ambiente y Desarrollo Sostenible",
    },

    # ---------------- Viable con gestión ----------------
    {
        "codigo": "unidad-agricola-familiar",
        "clase": CLASE_GESTION,
        "condicion": "El área del lote supera la Unidad Agrícola Familiar máxima del municipio",
        "prueba": lambda r: _si(r, "riesgo_baldio"),
        "detalle": lambda r: (
            f"{_cifra(_num(r, 'area_ha'), 1)} ha, "
            f"{_cifra(_num(r, 'veces_uaf'), 1)} veces la unidad máxima de "
            f"{_cifra(_num(r, 'uaf_max_ha'), 1)} ha fijada para el municipio"
            + (f", según {_txt(r, 'uaf_fuente')}"
               if _txt(r, "uaf_fuente") not in ("", "sin dato", "sin fuente") else "")),
        "tramite": ("Se pide el folio de matrícula inmobiliaria para establecer si el lote se "
                    "originó en la adjudicación de un baldío. Si ese es su origen, la Ley 160 de "
                    "1994 condiciona la acumulación por encima de la Unidad Agrícola Familiar y la "
                    "compra requiere autorización previa. Si el origen es privado, la condición "
                    "queda resuelta con el propio folio."),
        "entidad": ("Agencia Nacional de Tierras; el folio de matrícula se solicita a la "
                    "Superintendencia de Notariado y Registro"),
        "fuente": "Unidad Agrícola Familiar por municipio, Agencia Nacional de Tierras",
    },
    {
        "codigo": "inundacion-la-nina",
        "clase": CLASE_GESTION,
        "condicion": "El lote quedó bajo agua en episodios de La Niña ya registrados",
        "prueba": lambda r: _num(r, "ent_inundaciones_nina") > 0,
        "detalle": lambda r: (
            f"{_cifra(_num(r, 'ent_inundaciones_nina'))} de los seis episodios cartografiados "
            f"entre 1988 y 2022 alcanzaron el lote; hasta "
            f"{_cifra(_num(r, 'ent_inundacion_ha_max'), 1)} ha bajo agua en el mayor de ellos"),
        "tramite": ("El diseño incorpora un estudio hidrológico y de amenaza por inundación, y la "
                    "implantación se lleva fuera de la mancha o se protege con obras. Si el "
                    "proyecto ocupa cauce o ronda hídrica, el permiso lo otorga la corporación "
                    "autónoma regional con jurisdicción en el municipio."),
        "entidad": "Corporación autónoma regional con jurisdicción en el municipio",
        "fuente": ("Manchas de inundación observadas, Instituto de Hidrología, Meteorología y "
                   "Estudios Ambientales"),
    },
    {
        "codigo": "microzona-restitucion",
        "clase": CLASE_GESTION,
        "condicion": "El municipio tiene microzona focalizada para restitución de tierras",
        "prueba": lambda r: _si(r, "microzona_urt"),
        "detalle": lambda r: (
            f"microzona focalizada y {_cifra(_num(r, 'restitucion_mpio'))} solicitudes de "
            f"restitución registradas en el municipio"
            if _num(r, "restitucion_mpio") >= 0 else
            "microzona focalizada; el número de solicitudes del municipio no está publicado"),
        "tramite": ("Antes de negociar se consulta el lote en el Registro de Tierras Despojadas "
                    "y Abandonadas Forzosamente. Si el lote está inscrito o tiene solicitud en "
                    "curso, la venta queda suspendida hasta que el proceso termine; si no aparece, "
                    "la condición queda resuelta con esa constancia."),
        "entidad": "Unidad de Restitución de Tierras",
        "fuente": ("Focalización de microzonas y solicitudes por municipio, Unidad de "
                   "Restitución de Tierras"),
    },
    {
        "codigo": "humedal",
        "clase": CLASE_GESTION,
        "condicion": "Humedal identificado dentro del lote",
        "prueba": lambda r: bool(_txt(r, "ent_humedal")),
        "detalle": _detalle_humedal,
        "tramite": ("El humedal y su ronda son suelo de protección: la implantación los excluye y "
                    "el área efectivamente utilizable se define con la corporación autónoma "
                    "regional, que delimita la ronda y otorga los permisos que correspondan."),
        "entidad": "Corporación autónoma regional con jurisdicción en el municipio",
        "fuente": ("Capa de ecosistemas estratégicos del Ministerio de Ambiente y Desarrollo "
                   "Sostenible"),
    },
    {
        "codigo": "proteccion-pot-parcial",
        "clase": CLASE_GESTION,
        "condicion": "Una parte del lote está en categoría de suelo de protección del plan de ordenamiento",
        "prueba": lambda r: (POT_PROTECCION_MIN_PCT <= _num(r, "pot_rojo_pct")
                             < POT_PROTECCION_NO_VIABLE_PCT),
        "detalle": _detalle_proteccion,
        "tramite": ("La parte en protección no se puede ocupar, pero el resto del lote sí. El "
                    "proyecto se implanta por fuera de esa franja y el certificado de uso del "
                    "suelo confirma el área efectivamente disponible antes de comprar."),
        "entidad": "Secretaría de Planeación del municipio",
        "fuente": "Zonificación de suelo rural del Instituto Geográfico Agustín Codazzi",
    },
]


def condiciones_de(r) -> list[dict]:
    """Condiciones que se cumplen en un lote, cada una con su trámite, entidad y fuente."""
    out = []
    for c in CONDICIONES:
        try:
            if not c["prueba"](r):
                continue
            detalle = c["detalle"](r)
        except Exception:
            continue
        out.append({"codigo": c["codigo"], "clase": c["clase"], "condicion": c["condicion"],
                    "detalle": detalle, "tramite": c["tramite"], "entidad": c["entidad"],
                    "fuente": c["fuente"]})
    return out


def advertencias_de(r) -> list[str]:
    """
    Avisos que no cambian la clase del lote porque son huecos de la fuente y no defectos
    del terreno: la norma urbana sin cartografía publicada y las capas que no respondieron.
    Aquí van en una frase; el texto completo, con el instrumento del municipio y su año,
    queda en la columna de la nota del POT y es lo que la ficha muestra.
    """
    av = []
    cobertura = _txt(r, "pot_cobertura")
    estado = _txt(r, "pot_estado_norma")
    if cobertura and cobertura != "verificado":
        if estado == "POT vencido sin cartografía":
            av.append("La categoría del suelo no se pudo verificar: el municipio tiene "
                      "instrumento de ordenamiento adoptado, pero su zonificación rural no "
                      "está publicada y el instrumento superó su vigencia de largo plazo.")
        elif cobertura == "sin instrumento":
            av.append("La categoría del suelo no se pudo verificar: no hay instrumento de "
                      "ordenamiento registrado para el municipio.")
        elif cobertura == "sin respuesta del servicio":
            av.append("La categoría del suelo no se pudo verificar: el servicio de "
                      "ordenamiento no respondió en la última consulta.")
        else:
            av.append("La categoría del suelo no se pudo verificar: la zonificación rural "
                      "publicada no cubre este lote.")
        av.append("Se pide a la Secretaría de Planeación del municipio mediante certificado "
                  "de uso del suelo.")
    if _txt(r, "ent_capas_sin_respuesta"):
        av.append("Alguna de las capas del entorno no respondió en la última consulta y se "
                  "reintenta automáticamente en la siguiente; la ficha muestra lo que sí "
                  "respondió.")
    return av


# --------------------------------------------------------------------------
# Clasificación
# --------------------------------------------------------------------------

def evaluar(p: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame, perfil: str,
            ha_minima: float = HA_MINIMA_CARACTERIZAR) -> gpd.GeoDataFrame:
    """
    Aplica los tres bloques (excluyentes, tamaño y forma, puntuación) y devuelve el predio
    clasificado. Mismos umbrales y utilidad que el reporte de grillas con valores del
    predio; un criterio sin dato sale del promedio y criterios_evaluados registra cuántos.
    """
    cfg = rg.PERFILES[perfil]
    rg.aplicar_perfil(perfil, escala="lote")
    ha_obj = cfg["ha_proyecto"]
    ancho_min = ancho_minimo(ha_obj)

    p = p.copy()
    ce = celdas.set_index(celdas["cell_id"].astype(str))
    cid = p["cell_id"].astype(str)
    p["celda_clasificacion"] = cid.map(ce.get("clasificacion", pd.Series(dtype=str)))
    p["celda_indice"] = cid.map(ce.get("indice_aptitud", pd.Series(dtype=float)))
    # Municipio y departamento del predio salen de su código catastral; los de la celda
    # quedan aparte como contexto.
    p["municipio_celda"] = cid.map(ce.get("municipio", pd.Series(dtype=str)))
    p["municipio"] = municipio_dane(p).fillna(p["municipio_celda"])
    p["departamento"] = departamento_dane(p).fillna(
        cid.map(ce.get("departamento", pd.Series(dtype=str))))
    p["celda_restricciones"] = cid.map(ce.get("restricciones", pd.Series(dtype=str)))

    # ---------- bloque 1: excluyentes ----------
    motivos = [[] for _ in range(len(p))]

    for i, v in enumerate((p["celda_clasificacion"] == "Excluida").values):
        if v:
            motivos[i].append(f"la celda está excluida ({p['celda_restricciones'].iloc[i]})")

    for i, v in enumerate((p["clase_suelo"] == "urbano").values):
        if v:
            motivos[i].append("lote de la capa urbana del catastro")

    if "destino_economico" in p.columns:
        for i, v in enumerate(p["destino_economico"].values):
            if v in DESTINOS_EXCLUIDOS:
                motivos[i].append(DESTINOS_EXCLUIDOS[v])

    p["excluido"] = [bool(m) for m in motivos]

    # ---------- bloque 2: tamaño y forma ----------
    # El tamaño no descarta (ver HA_MINIMA_CARACTERIZAR): falla el lote sin área medible y
    # se aparta el menor que ha_minima. Se anota si el área y el ancho del lote alcanzan
    # los de cada perfil; el filtro real lo aplica el usuario en el visor.
    falla = [[] for _ in range(len(p))]
    pequeno = [False] * len(p)
    area = p["area_ha"]
    for i, v in enumerate(area.values):
        if pd.isna(v) or v <= 0:
            falla[i].append("sin área medible en el catastro")
        elif v < ha_minima:
            pequeno[i] = True
    p["cumple_tamano"] = [not f for f in falla]
    cabe = []
    for a, w in zip(area.values, p["ancho_util_m"].values):
        cabe.append(bool(pd.notna(a) and a >= ha_obj and (pd.isna(w) or w >= ancho_min)))
    p["cabe_perfil"] = cabe
    for nombre, cfg_p in rg.PERFILES.items():
        ha_p, an_p = cfg_p["ha_proyecto"], ancho_minimo(cfg_p["ha_proyecto"])
        p[f"cabe_{nombre}"] = [bool(pd.notna(a) and a >= ha_p and (pd.isna(w) or w >= an_p))
                               for a, w in zip(area.values, p["ancho_util_m"].values)]

    # ---------- bloque 3: puntuación ----------
    # recurso y capacidad se heredan de la celda (no varían a escala de lote); el resto se
    # mide en el predio. Se recorre rg.CRITERIOS y se avisa si alguno no tiene equivalente.
    nan = pd.Series(np.nan, index=p.index)

    def _de_celda(col):
        return cid.map(ce.get(col, pd.Series(dtype=float)))

    valores = {
        "dist_sub": p.get("conexion_km", nan).round(2),
        "cobertura": p.get("cobertura_apta_pct", nan).round(1),
        "pendiente": p.get("pendiente_media", nan).round(1),
        "rugosidad": p.get("rugosidad_m", nan).round(1),
        "dist_via": p.get("dist_via_km", nan).round(2),
        "recurso": _de_celda("pvout").round(0),
        "capacidad": _de_celda("capacidad_mt_mw" if perfil == "distribuida"
                               else "capacidad_at_mw").round(1),
    }
    faltan = [k for k in rg.CRITERIOS if k not in valores]
    if faltan:
        print(f"  aviso: criterios sin equivalente en el lote, se puntúa sin ellos: "
              f"{', '.join(faltan)}")
    claves = [k for k in rg.CRITERIOS if k in valores]

    def utilidad(clave, v):
        c = rg.CRITERIOS[clave]
        lim, bue, tope = c["limite"], c["bueno"], c["tope"]
        s = 1.0 if c["mayor_mejor"] else -1.0
        v_, lim_, bue_, tope_ = s * v, s * lim, s * bue, s * tope
        if v_ <= lim_:
            return 0.0
        if v_ <= bue_:
            return 70.0 * (v_ - lim_) / max(1e-9, bue_ - lim_)
        holgura = tope_ - bue_
        if holgura <= 1e-9:
            return 70.0
        return 70.0 + 30.0 * min(1.0, (v_ - bue_) / holgura)

    # Peso: el del perfil si lo trae, si no la d de Cohen del criterio; misma regla que el
    # reporte de grillas para que ambos índices sean comparables.
    pesos = dict(cfg.get("pesos") or {k: c["d_cohen"] for k, c in rg.CRITERIOS.items()})

    indices, evaluados, cumplidos, reparos = [], [], [], []
    for i in range(len(p)):
        suma, peso, n_ok, n_ev, fuera = 0.0, 0.0, 0, 0, []
        for clave in claves:
            c = rg.CRITERIOS[clave]
            v = valores[clave].iloc[i]
            if pd.isna(v):
                continue
            v = float(v)
            suma += utilidad(clave, v) * pesos[clave]
            peso += pesos[clave]
            n_ev += 1
            peor = v < c["limite"] if c["mayor_mejor"] else v > c["limite"]
            corto = v < c["bueno"] if c["mayor_mejor"] else v > c["bueno"]
            if peor:
                rotulo = ETIQUETA_CRITERIO.get(clave, c["etiqueta"]).lower()
                fuera.append(f"{rotulo} de {v:g} {c['unidad']}".strip())
            elif not corto:
                n_ok += 1
        indices.append(round(suma / peso, 1) if peso else np.nan)
        evaluados.append(n_ev)
        cumplidos.append(n_ok)
        reparos.append("; ".join(fuera))

    p["indice_lote"] = indices
    p["criterios_evaluados"] = evaluados
    p["criterios_cumplidos"] = cumplidos
    p["reparos"] = reparos

    # ---------- apartado previo, antes de clasificar ----------
    # La clase de aptitud no sale de aquí: sale de las condiciones del lote y se decide
    # en clasificar_condiciones, que necesita el entorno, el POT y el cribado jurídico.
    # En este punto solo se apartan los lotes que ni siquiera entran a caracterizarse:
    # el excluido de entrada, el que no tiene área medible en el catastro y el menor que
    # el mínimo de caracterización. Todos los demás arrancan en "Idóneo" y bajan de clase
    # únicamente si aparece alguna condición adversa comprobada.
    clases, textos = [], []
    for i in range(len(p)):
        if motivos[i]:
            clases.append("Excluido")
            textos.append("Excluido: " + "; ".join(motivos[i]) + ".")
        elif falla[i]:
            clases.append("No apto")
            textos.append("No apto: " + "; ".join(falla[i]) + ".")
        elif pequeno[i]:
            clases.append("Pequeño")
            textos.append(f"Pequeño: {p['area_ha'].iloc[i]:.1f} ha, por debajo del "
                          f"mínimo de caracterización de {ha_minima:g} ha.")
        else:
            clases.append(CLASE_IDONEO)
            textos.append("")
    p["clasificacion"] = clases
    p["motivo"] = textos
    p["perfil"] = perfil
    p["ha_perfil"] = ha_obj
    p["ancho_minimo_m"] = ancho_min
    return p


# --------------------------------------------------------------------------
# Estorbos para adquirir el predio
# --------------------------------------------------------------------------

# La casa de la finca (mediana de lo construido, 553 m²) no cuenta; sí cuenta la
# infraestructura de una explotación en marcha.
CONSTRUIDO_MAX_M2 = 2000.0
BOSQUE_MAX_PCT = 10.0        # por encima, requiere permiso de aprovechamiento forestal
DESAJUSTE_CATASTRO = 0.10    # diferencia relativa entre área del registro y de la geometría


def añadir_gestion(p: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Señales de negociación visibles en datos abiertos: construcción en pie, bosque que
    requiere permiso de aprovechamiento, desajuste entre el área del catastro y la medida
    sobre el lindero, y destino económico sin declarar. No cambian la
    clase del lote ni lo descartan: describen lo que el comprador va a encontrar.
    """
    p = p.copy()
    construido = p.get("area_construida_m2", pd.Series(0.0, index=p.index)).fillna(0.0)
    bosque = p.get("cob_bosque_pct", pd.Series(0.0, index=p.index)).fillna(0.0)
    catastro = p.get("area_terreno_catastro_m2", pd.Series(np.nan, index=p.index)) / 1e4
    desajuste = ((catastro - p["area_ha"]).abs() / p["area_ha"].replace(0, np.nan))

    señales = [
        (construido > CONSTRUIDO_MAX_M2,
         lambda i: f"Construcción registrada de {construido.iloc[i]:,.0f} m² dentro del lote".replace(",", ".")),
        (bosque > BOSQUE_MAX_PCT,
         lambda i: (f"Cobertura de bosque sobre el {bosque.iloc[i]:.0f}% del lote, que exige "
                    f"permiso de aprovechamiento forestal ante la corporación autónoma regional")),
        (desajuste > DESAJUSTE_CATASTRO,
         lambda i: (f"El área que registra el catastro difiere un {desajuste.iloc[i] * 100:.0f}% "
                    f"de la medida sobre el lindero publicado")),
        (p.get("destino", pd.Series(np.nan, index=p.index)).isna(),
         lambda i: "El catastro no declara destino económico para el lote"),
    ]

    banderas = [[] for _ in range(len(p))]
    for marca, texto in señales:
        for i in np.flatnonzero(marca.fillna(False).values):
            banderas[i].append(texto(i))

    p["estorbos"] = [len(b) for b in banderas]
    p["gestion"] = ["; ".join(b) if b else
                    "No se detectan señales de negociación en las fuentes consultadas"
                    for b in banderas]
    return p


ORDEN = {CLASE_IDONEO: 0, CLASE_GESTION: 1, CLASE_NO_VIABLE: 2,
         "Pequeño": 3, "No apto": 4, "Excluido": 5}


def ordenar(p: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ordena por clase y, dentro de cada clase, por área de mayor a menor. El índice no
    interviene en el orden: es un descriptor de la ficha, no una jerarquía de la lista.
    """
    p = p.copy()
    p["_o"] = p["clasificacion"].map(ORDEN)
    p = p.sort_values(["_o", "area_ha"], ascending=[True, False]).drop(columns="_o")
    p.insert(0, "orden", range(1, len(p) + 1))
    return p


# --------------------------------------------------------------------------
# Justificación numérica de los cortes de forma
# --------------------------------------------------------------------------

def justificar(p: gpd.GeoDataFrame, ha_obj: float) -> None:
    """
    Imprime, sobre los predios que alcanzan ha_obj brutas, distribución y correlación de
    las tres medidas de forma y cuántos deja pasar cada corte, solo y frente al ancho útil.
    """
    g = p[p["area_ha"] >= ha_obj].copy()
    print(f"\n  Sobre los {len(g)} lotes que ya alcanzan {ha_obj:.0f} ha:")
    if g.empty:
        return
    cols = ["compacidad", "ancho_util_m", "nucleo_frac"]
    print(g[cols].describe(percentiles=[.05, .1, .25, .5, .75]).round(3).to_string())
    print("\n  Correlación entre las tres medidas de forma:")
    print(g[cols].corr().round(2).to_string())

    ancho_min = ancho_minimo(ha_obj)
    filtros = {
        f"compacidad >= 0,30": g["compacidad"] >= 0.30,
        f"ancho útil >= {ancho_min:.0f} m": g["ancho_util_m"] >= ancho_min,
        f"núcleo a {RETRANQUEO_M:.0f} m >= {ha_obj:.0f} ha": g["area_nucleo_ha"] >= ha_obj,
    }
    print("\n  Cuántos lotes deja pasar cada corte, por separado:")
    for nombre, mask in filtros.items():
        print(f"    {nombre:<34} {int(mask.sum()):>5} de {len(g)} "
              f"({mask.mean() * 100:.1f}%)")
    print("\n  Solapamiento: qué añade cada uno sobre el ancho útil")
    base = filtros[f"ancho útil >= {ancho_min:.0f} m"]
    for nombre, mask in filtros.items():
        if nombre.startswith("ancho"):
            continue
        print(f"    {nombre:<34} descarta {int((base & ~mask).sum()):>4} que el ancho "
              f"aceptaba, y acepta {int((~base & mask).sum()):>4} que el ancho descartaba")


# --------------------------------------------------------------------------

def procesar(perfil: str, p: gpd.GeoDataFrame, celdas: gpd.GeoDataFrame,
             verbose: bool = True, ha_minima: float = HA_MINIMA_CARACTERIZAR) -> gpd.GeoDataFrame:
    """
    Pasos que dependen del perfil: distancia a subestación, medida frente a los criterios,
    señales de negociación, cribado jurídico, entorno, norma urbana y contexto; con todo
    eso puesto, la clasificación por condiciones y el orden de la lista.
    """
    cfg = rg.PERFILES[perfil]
    if verbose:
        print(f"\n  Perfil {perfil}: {cfg['etiqueta']}, {cfg['ha_proyecto']:.0f} ha, "
              f"ancho mínimo {ancho_minimo(cfg['ha_proyecto']):.0f} m (referencia, no criba)")
    q = añadir_conexion(p, cfg["kv_min"], cfg["kv_max"], verbose=verbose)
    q = evaluar(q, celdas, perfil, ha_minima=ha_minima)
    q = añadir_gestion(q)
    import juridico
    import valor
    import entorno
    import pot
    import contexto
    q = juridico.cribar(q, verbose=verbose)
    q = valor.valorar(q, verbose=verbose)
    # Entorno, norma urbana y contexto (geoservicios por lote) solo para los lotes que
    # entran a clasificarse: cada consulta va a un servidor estatal y se guarda por lote.
    sel = q["clasificacion"].isin(SELECCIONABLES)
    if verbose:
        print(f"  entorno y POT para {int(sel.sum())} lotes de {ha_minima:g} ha o más")
    if sel.any():
        # Entorno, POT y contexto van a servidores distintos: se consultan a la vez.
        from concurrent.futures import ThreadPoolExecutor
        geoms = q.loc[sel].geometry.values
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_ent = ex.submit(entorno.enriquecer, q.loc[sel], geoms, verbose)
            f_pot = ex.submit(pot.enriquecer, q.loc[sel], geoms, verbose)
            f_ctx = ex.submit(contexto.enriquecer, q.loc[sel], geoms, celdas, verbose)
            q_ent, q_pot, q_ctx = f_ent.result(), f_pot.result(), f_ctx.result()
        for q_x, pref in ((q_ent, "ent_"), (q_pot, "pot_"), (q_ctx, "ctx_")):
            for c in [c for c in q_x.columns if c.startswith(pref)]:
                q[c] = q_x[c].reindex(q.index)
    q = clasificar_condiciones(q, verbose=verbose)
    return ordenar(q)


def clasificar_condiciones(q: gpd.GeoDataFrame, verbose: bool = True) -> gpd.GeoDataFrame:
    """
    Da a cada lote caracterizado su clase de aptitud a partir de las condiciones que se le
    comprobaron, y deja escrita la lista de esas condiciones con el trámite y la entidad
    que exige cada una. Una sola condición del grupo "No viable" basta para esa clase; si
    no hay ninguna pero sí alguna del grupo de gestión, el lote es "Viable con gestión";
    sin ninguna de las dos, es "Idóneo".

    Los avisos de advertencias_de (norma urbana sin cartografía publicada, capa que no
    respondió) se anotan y se muestran, pero no cambian la clase: son huecos de la fuente
    y no defectos del terreno.
    """
    q = q.copy()
    clases, textos, listas, avisos = [], [], [], []
    n_cond, n_nv, n_ge = [], [], []
    for i in q.index:
        clase_previa = q.at[i, "clasificacion"]
        if clase_previa not in SELECCIONABLES:
            clases.append(clase_previa)
            textos.append(q.at[i, "motivo"])
            listas.append("[]")
            avisos.append("")
            n_cond.append(0); n_nv.append(0); n_ge.append(0)
            continue
        r = q.loc[i]
        cond = condiciones_de(r)
        nv = [c for c in cond if c["clase"] == CLASE_NO_VIABLE]
        ge = [c for c in cond if c["clase"] == CLASE_GESTION]
        av = advertencias_de(r)

        area = _cifra(_num(r, "area_ha"), 1)
        cob = composicion_cobertura(r)
        medida = f"{area} ha de área catastral"
        if cob:
            medida += f", y su cobertura del suelo es {cob}"
        if nv:
            clase = CLASE_NO_VIABLE
            enum = "; ".join(f"{c['condicion']} ({c['detalle']})" for c in nv)
            texto = (f"No viable: {len(nv)} "
                     f"{'condición que ninguna gestión del proyecto resuelve' if len(nv) == 1 else 'condiciones que ninguna gestión del proyecto resuelve'}. "
                     f"{enum}. El lote mide {medida}.")
        elif ge:
            clase = CLASE_GESTION
            enum = "; ".join(f"{c['condicion']} ({c['detalle']})" for c in ge)
            texto = (f"Viable con gestión: {len(ge)} "
                     f"{'condición exige un trámite' if len(ge) == 1 else 'condiciones exigen un trámite'} "
                     f"antes de construir. {enum}. Cada trámite y la entidad ante la que se "
                     f"adelanta van en la ficha del lote. El lote mide {medida}.")
        else:
            clase = CLASE_IDONEO
            texto = (f"Idóneo: no se identifica ninguna condición adversa en las fuentes "
                     f"consultadas. El lote mide {medida}.")
        if av:
            texto += " " + " ".join(av)
        clases.append(clase)
        textos.append(texto)
        listas.append(json.dumps(cond, ensure_ascii=False))
        avisos.append(" ".join(av))
        n_cond.append(len(cond)); n_nv.append(len(nv)); n_ge.append(len(ge))

    q["clasificacion"] = clases
    q["motivo"] = textos
    q["condiciones"] = listas
    q["condiciones_n"] = n_cond
    q["condiciones_no_viable"] = n_nv
    q["condiciones_gestion"] = n_ge
    q["condiciones_texto"] = [
        "; ".join(c["condicion"] for c in json.loads(x)) for x in listas]
    q["advertencias"] = avisos

    if verbose:
        vistos = q[q["clasificacion"].isin(SELECCIONABLES)]
        print("  clasificación por condiciones del lote:")
        for clase in (CLASE_IDONEO, CLASE_GESTION, CLASE_NO_VIABLE):
            print(f"    {clase:<20} {int((vistos['clasificacion'] == clase).sum()):>5}")
        cuenta: dict[str, int] = {}
        for x in vistos["condiciones"]:
            for c in json.loads(x):
                cuenta[c["condicion"]] = cuenta.get(c["condicion"], 0) + 1
        if cuenta:
            print("  condiciones encontradas, lotes afectados por cada una:")
            for k, v in sorted(cuenta.items(), key=lambda t: -t[1]):
                print(f"    {v:>5}  {k}")
        n_av = int((vistos["advertencias"] != "").sum())
        if n_av:
            print(f"  {n_av} lotes con advertencia que no cambia la clase "
                  f"(norma urbana sin cartografía publicada o capa sin respuesta)")
    return q


COLUMNAS = [
    "orden", "cell_id", "CODIGO", "clasificacion", "indice_lote", "motivo",
    "departamento", "municipio", "municipio_celda", "clase_suelo", "destino", "destino_economico",
    "numero_predial_anterior",
    "area_ha", "area_nucleo_ha", "mwp_lote", "area_util_ha",
    "compacidad", "ancho_util_m", "nucleo_frac",
    "pendiente_media", "pendiente_p90", "rugosidad_m", "elevacion_media",
] + COLUMNAS_COBERTURA + [
    # Agregado ponderado con coeficientes de este estudio. No se publica en la ficha del
    # lote: es la variable de entrada del criterio de cobertura del índice de aptitud.
    "cobertura_apta_pct",
    "area_construida_m2", "area_terreno_catastro_m2",
    "dist_via_km", "dist_via_centro_km", "dist_via_principal_km",
    "conexion_km", "conexion_nombre",
    "conexion_kv", "celda_clasificacion", "celda_indice",
    "criterios_evaluados", "criterios_cumplidos", "reparos",
    "condiciones", "condiciones_texto", "condiciones_n", "condiciones_no_viable",
    "condiciones_gestion", "advertencias",
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
    "pot_proteccion_pct", "pot_zonificado_pct", "pot_rojo_pct",
    "pot_uso_prohibido", "pot_semaforo", "pot_clasificacion", "pot_acto",
    "pot_tipo", "pot_acto_municipal", "pot_anio", "pot_revision", "pot_fecha", "pot_estado",
    "pot_estado_norma", "pot_cobertura", "pot_instrumento", "pot_instrumento_anios",
    "pot_instrumento_vencido", "pot_zonificacion_municipio", "pot_nota",
    "perfil", "ha_perfil", "ancho_minimo_m",
]


#: Las tres clases de aptitud, que son las que entran en la tabla de lotes con geometría.
#: "Pequeño", "No apto" y "Excluido" se publican aparte, con su medida y su motivo.
SELECCIONABLES = (CLASE_IDONEO, CLASE_GESTION, CLASE_NO_VIABLE)


def exportar(q: gpd.GeoDataFrame, perfil: str) -> None:
    """
    Escribe lotes_<perfil>.csv, .geojson y la capa del GPKG con los predios caracterizados,
    y lotes_<perfil>_descartados.csv con el resto y su motivo, sin geometría
    (con ella el GeoJSON llegaba a 185 MB).
    """
    SALIDA.mkdir(parents=True, exist_ok=True)
    cols = [c for c in COLUMNAS if c in q.columns]
    sel = q[q["clasificacion"].isin(SELECCIONABLES)]
    resto = q[~q["clasificacion"].isin(SELECCIONABLES)]

    pd.DataFrame(sel[cols]).to_csv(SALIDA / f"lotes_{perfil}.csv",
                                   index=False, encoding="utf-8-sig")
    pd.DataFrame(resto[cols]).to_csv(SALIDA / f"lotes_{perfil}_descartados.csv",
                                     index=False, encoding="utf-8-sig")

    geo = sel[cols + ["geometry"]].copy()
    # Un metro de tolerancia: hay predios del IGAC con cientos de miles de vértices.
    geo["geometry"] = geo.geometry.to_crs(config.CRS_METRICO).simplify(1.0, preserve_topology=True)
    geo = geo.set_crs(config.CRS_METRICO, allow_override=True).to_crs(config.CRS_GEOGRAFICO)
    if geo.empty:
        print(f"  ningún lote pasa tamaño y forma en el perfil {perfil}")
        return
    # Seis decimales son unos 11 cm en el ecuador, suficiente para un lindero catastral,
    # y reducen el archivo a la mitad frente a los quince decimales por defecto.
    geo.to_file(SALIDA / f"lotes_{perfil}.geojson", driver="GeoJSON",
                COORDINATE_PRECISION=6)
    geo.to_file(SALIDA / "lotes.gpkg", layer=perfil, driver="GPKG")
    print(f"  CSV     -> {SALIDA / f'lotes_{perfil}.csv'}  ({len(sel)} lotes)")
    print(f"  GeoJSON -> {SALIDA / f'lotes_{perfil}.geojson'}")
    print(f"  descartes con su motivo -> lotes_{perfil}_descartados.csv "
          f"({len(resto)} lotes, sin geometría)")


def resumen(q: gpd.GeoDataFrame, perfil: str) -> None:
    """Imprime conteos por clasificación, los diez mejores lotes y las celdas con más."""
    print()
    print("-" * 74)
    print(f"RESULTADO  ·  perfil {perfil}")
    print("-" * 74)
    print(q["clasificacion"].value_counts().reindex(ORDEN).dropna().to_string())

    buenos = q[q["clasificacion"].isin(SELECCIONABLES)]
    print(f"\n  lotes caracterizados y clasificados : {len(buenos)}")
    if buenos.empty:
        return
    print(f"  celdas con al menos un lote    : {buenos['cell_id'].nunique()} "
          f"de {q['cell_id'].nunique()}")
    print(f"  MWp indicativos acumulados     : {buenos['mwp_lote'].sum():,.0f}"
          f" (sobre el área catastral, a {HA_POR_MWP:g} ha por MWp)"
          .replace(",", "."))
    print("\n  Los diez primeros de la lista (clase y luego área, el índice no ordena):")
    ver = ["orden", "cell_id", "municipio", "clasificacion", "condiciones_n",
           "area_ha", "mwp_lote", "indice_lote", "pendiente_media", "cob_pastizal_pct",
           "cob_bosque_pct", "dist_via_km", "conexion_km"]
    print(buenos.head(10)[[c for c in ver if c in buenos.columns]]
          .to_string(index=False))

    print("\n  Lotes por celda, las diez celdas con más:")
    t = (buenos.groupby("cell_id")
         .agg(lotes=("orden", "size"), ha=("area_ha", "sum"),
              mwp=("mwp_lote", "sum"),
              idoneos=("clasificacion", lambda x: int((x == CLASE_IDONEO).sum())))
         .sort_values("mwp", ascending=False).head(10))
    print(t.round(1).to_string())


def main(argv=None) -> int:
    """CLI: carga celdas y predios, mide, y procesa y exporta cada perfil."""
    ap = argparse.ArgumentParser(description="Selección de lotes dentro de las celdas")
    ap.add_argument("--perfil", default=None,
                    help=f"uno de {', '.join(rg.PERFILES)}; por defecto los dos")
    ap.add_argument("--celdas", default=None,
                    help="las grillas a trabajar: el GeoJSON o CSV que bajaste del reporte "
                         "de grillas (p. ej. outputs/reporte/grillas_para_predios.geojson), "
                         "o una lista de códigos separada por comas; sin esto, las cien del reporte")
    ap.add_argument("--ha-minima", type=float, default=HA_MINIMA_CARACTERIZAR,
                    help=f"área bruta mínima para caracterizar un predio (por defecto "
                         f"{HA_MINIMA_CARACTERIZAR:g} ha); el tamaño se filtra en el visor")
    ap.add_argument("--justificar", action="store_true",
                    help="imprime la comparación numérica de los cortes de forma")
    a = ap.parse_args(argv)

    perfiles = [a.perfil] if a.perfil else list(rg.PERFILES)
    for x in perfiles:
        if x not in rg.PERFILES:
            raise SystemExit(f"Perfil desconocido: {x}. Hay {', '.join(rg.PERFILES)}")

    print("=" * 74)
    print("SELECCIÓN DE LOTES")
    print("=" * 74)

    celdas = cargar_celdas(celdas=a.celdas)
    print(f"  celdas: {len(celdas)}   origen: {celdas.attrs.get('origen', '?')}")

    p = cargar_predios(celdas)
    p = asignar_celda_unica(p, celdas)
    print(f"  lotes: {len(p):,} de {p['cell_id'].nunique()} grillas".replace(",", "."))

    p = añadir_forma(p)
    p = añadir_terreno(p, celdas)
    p = añadir_dist_via(p)
    p = añadir_area_util(p)

    if a.justificar:
        for x in perfiles:
            print(f"\n{'=' * 74}\n  CORTES DE FORMA, perfil {x}\n{'=' * 74}")
            justificar(p, rg.PERFILES[x]["ha_proyecto"])

    for x in perfiles:
        q = procesar(x, p, celdas, ha_minima=a.ha_minima)
        exportar(q, x)
        resumen(q, x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
