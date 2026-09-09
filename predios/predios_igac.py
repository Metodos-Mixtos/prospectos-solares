"""
Descarga los predios catastrales del IGAC (terreno rural y urbano, más la tabla
REGISTRO_1) para un conjunto de celdas, los repara, deduplica y recorta a la celda,
y los mide en CRS métrico. Consulta en EPSG:4326, paginada, y mide en EPSG:32618.

Entrada: celdas de outputs/reporte/grillas_candidatas.gpkg, un archivo de celdas o
una lista de cell_id (--celdas). Salida: GeoJSON crudo por celda y capa en
data/igac/, manifiesto en data/igac/_estado.json y consolidado medido en
outputs/reporte/predios.gpkg.

Uso:
    .venv\\Scripts\\python.exe -m predios.predios_igac [--clase todas] [--celdas IDs|ruta]
    .venv\\Scripts\\python.exe -m predios.predios_igac [--reintentar] [--estado]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
# La raiz y soporte/ van al path: config y gcs viven en soporte/.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

#: Corte de la base catastral pública del gestor IGAC. El IGAC publica un servicio por
#: corte mensual (Base_Catastral_Publica_del_Gestor_IGAC_MM_AAAA); al cambiar el corte aquí,
#: `pendientes()` vuelve a marcar como pendientes las celdas descargadas con el anterior.
CORTE = "06_2026"
CORTE_TEXTO = "30 de junio de 2026"
BASE = ("https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services"
        f"/Base_Catastral_Publica_del_Gestor_IGAC_{CORTE}/FeatureServer")
#: Campo que une las tablas REGISTRO_1/2 con el CODIGO del terreno. Los cortes anteriores a
#: abril de 2026 lo llamaban NUMERO_DEL_PREDIO; las cachés viejas se leen con los dos nombres.
CAMPO_PREDIO = "NUMERO_PREDIAL"
CAMPO_PREDIO_ANTERIOR = "NUMERO_DEL_PREDIO"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}

#: Capas de terreno, que delimitan el predio; las de construcción no se usan.
CAPAS = {14: "rural", 7: "urbano"}

#: Tabla alfanumérica del catastro (destino económico y áreas). Se une por
#: NUMERO_PREDIAL contra CODIGO del terreno. Cubre el 94,9% de los predios rurales,
#: así que sirve para describir y descartar, nunca para exigir presencia.
CAPA_REGISTRO = 17
#: REGISTRO_2: zonas homogéneas físicas y económicas con su área, e inventario de hasta
#: tres construcciones por predio (uso, puntaje, área). Base del avalúo catastral.
CAPA_REGISTRO2 = 18
LOTE_REGISTRO = 250        # códigos por cláusula IN; con 500 el servicio devuelve 400

PAGINA = 1000          # por debajo del maxRecordCount de 2000 que declara el servicio
PAUSA = 0.4            # entre peticiones, por cortesía con el servicio
REINTENTOS = 3

CACHE = config.PROJECT_ROOT / "data" / "igac"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
MANIFIESTO = CACHE / "_estado.json"

#: Destino económico. El servicio publica la letra sin dominio; se traducen solo las
#: cinco contrastables contra la base (medianas: D 9,0 ha, L 8,7 ha y M 16,8 ha, tamaño
#: de finca; A 0,1 ha, solar con casa). Las demás letras se dejan crudas.
DESTINO_ECONOMICO = {
    "A": "habitacional",
    "C": "comercial",
    "D": "agropecuario",
    "L": "agrícola",
    "M": "pecuario",
}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Manifiesto
# --------------------------------------------------------------------------
# Distingue celda no pedida, pedida con cero predios y descarga fallida, que en
# disco se ven igual; sobre él opera --reintentar.

def leer_manifiesto() -> dict:
    """Manifiesto de descargas (data/igac/_estado.json); vacío si no existe."""
    if not MANIFIESTO.exists():
        return {}
    try:
        return json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def escribir_manifiesto(m: dict) -> None:
    """Guarda el manifiesto de descargas."""
    CACHE.mkdir(parents=True, exist_ok=True)
    MANIFIESTO.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def _anotar(m: dict, celda: str, tipo: str, **campos) -> None:
    m.setdefault(celda, {})[tipo] = {"cuando": _ahora(), **campos}


# --------------------------------------------------------------------------
# Consulta al servicio
# --------------------------------------------------------------------------

def _consultar(layer: int, bounds, offset: int) -> dict:
    """Una página de resultados. Devuelve el GeoJSON crudo del servicio."""
    minx, miny, maxx, maxy = bounds
    params = {
        "geometry": json.dumps({"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
                                "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": str(PAGINA),
        "resultOffset": str(offset),
    }
    ultimo = None
    for intento in range(REINTENTOS):
        try:
            r = requests.post(f"{BASE}/{layer}/query", data=params, headers=UA, timeout=180)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", "error del servicio"))
            return data
        except Exception as exc:
            ultimo = exc
            time.sleep(PAUSA * (intento + 2))
    raise RuntimeError(f"tras {REINTENTOS} intentos: {ultimo}")


def _raw(celda: str, tipo: str) -> Path:
    return CACHE / f"igac_{celda}_{tipo}.geojson"


def _raw_registro2(celda: str) -> Path:
    return CACHE / f"igac_{celda}_registro2.json"


def _raw_registro(celda: str) -> Path:
    return CACHE / f"igac_{celda}_registro1.json"


def _del_corte(manifiesto: dict | None, celda: str, tipo: str) -> bool:
    """True si la descarga anotada en el manifiesto es del corte vigente (o no hay manifiesto)."""
    if manifiesto is None:
        return True
    return ((manifiesto.get(celda, {}).get(tipo) or {}).get("corte")) == CORTE


def descargar_raw(celda: str, geom_wgs84, forzar: bool = False,
                  manifiesto: dict | None = None) -> list[Path]:
    """
    Descarga y cachea el GeoJSON crudo de cada capa de terreno de una celda, paginado.
    Devuelve las rutas de los archivos. Se guarda la respuesta tal cual, sin recortar.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    rutas = []
    for layer, tipo in CAPAS.items():
        destino = _raw(celda, tipo)
        if destino.exists() and not forzar and _del_corte(manifiesto, celda, tipo):
            rutas.append(destino)
            continue

        acumulado = {"type": "FeatureCollection", "features": []}
        offset, paginas, truncado = 0, 0, False
        while True:
            data = _consultar(layer, geom_wgs84.bounds, offset)
            feats = data.get("features", [])
            acumulado["features"].extend(feats)
            paginas += 1
            # exceededTransferLimit avisa de que quedan registros; sin él la celda se truncaría.
            if not data.get("properties", {}).get("exceededTransferLimit") and \
               not data.get("exceededTransferLimit"):
                break
            if len(feats) < PAGINA:
                break
            if paginas > 40:
                truncado = True
                break
            offset += PAGINA
            time.sleep(PAUSA)

        destino.write_text(json.dumps(acumulado, ensure_ascii=False), encoding="utf-8")
        rutas.append(destino)
        if manifiesto is not None:
            _anotar(manifiesto, celda, tipo, ok=True, n=len(acumulado["features"]),
                    paginas=paginas, truncado=truncado, corte=CORTE)
        time.sleep(PAUSA)
    return rutas


def descargar_registro(celda: str, forzar: bool = False,
                       manifiesto: dict | None = None, tabla: int = CAPA_REGISTRO) -> Path | None:
    """
    Ficha alfanumérica de los predios de una celda: REGISTRO_1 (destino y áreas) o
    REGISTRO_2 (zonas homogéneas y construcciones). Se pide por lotes de códigos ya
    descargados, no por municipio. Devuelve la ruta del JSON, o None sin códigos.
    """
    destino = _raw_registro2(celda) if tabla == CAPA_REGISTRO2 else _raw_registro(celda)
    tipo = "registro1" if tabla == CAPA_REGISTRO else "registro2"
    if destino.exists() and not forzar and _del_corte(manifiesto, celda, tipo):
        return destino

    codigos = sorted(_codigos_de(celda))
    if not codigos:
        return None

    filas = []
    for i in range(0, len(codigos), LOTE_REGISTRO):
        lote = codigos[i:i + LOTE_REGISTRO]
        where = f"{CAMPO_PREDIO} IN (" + ",".join(f"'{c}'" for c in lote) + ")"
        params = {"where": where, "outFields": "*", "returnGeometry": "false",
                  "f": "json", "resultRecordCount": "2000"}
        ultimo = None
        for intento in range(REINTENTOS):
            try:
                r = requests.post(f"{BASE}/{tabla}/query", data=params,
                                  headers=UA, timeout=240)
                r.raise_for_status()
                d = r.json()
                if "error" in d:
                    raise RuntimeError(d["error"].get("message", "error del servicio"))
                filas.extend(f["attributes"] for f in d.get("features", []))
                ultimo = None
                break
            except Exception as exc:
                ultimo = exc
                time.sleep(PAUSA * (intento + 2))
        if ultimo is not None:
            raise RuntimeError(f"REGISTRO_{1 if tabla == CAPA_REGISTRO else 2}: {ultimo}")
        time.sleep(PAUSA)

    destino.write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    if manifiesto is not None:
        _anotar(manifiesto, celda, tipo, ok=True, n=len(filas), pedidos=len(codigos), corte=CORTE)
    return destino


def _codigos_de(celda: str) -> set[str]:
    """Códigos catastrales que devolvieron las capas de terreno de una celda."""
    out = set()
    for _layer, tipo in CAPAS.items():
        ruta = _raw(celda, tipo)
        if not ruta.exists():
            continue
        try:
            data = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for f in data.get("features", []):
            cod = (f.get("properties") or {}).get("CODIGO")
            if cod:
                out.add(str(cod))
    return out


# --------------------------------------------------------------------------
# Del crudo al predio medible
# --------------------------------------------------------------------------

def procesar_celda(celda: str, geom_wgs84) -> gpd.GeoDataFrame:
    """
    Lee el crudo cacheado de una celda y devuelve los predios listos para medir, con la
    ficha REGISTRO_1 unida si está descargada. Tres pasos previos:
      - Reparar: make_valid a los polígonos inválidos (2 de 4.592, con anillos anidados).
      - Deduplicar: el servicio repite CODIGO con OBJECTID distinto (100 filas de 4.592).
      - Recortar: el envolvente consultado trae predios de fuera de la celda.
    """
    from shapely import make_valid

    trozos = []
    for _layer, tipo in CAPAS.items():
        ruta = _raw(celda, tipo)
        if not ruta.exists():
            continue
        try:
            data = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        feats = data.get("features", [])
        if not feats:
            continue
        sub = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
        sub["clase_suelo"] = tipo
        trozos.append(sub)

    if not trozos:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    g = pd.concat(trozos, ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326")
    g = g[g.geometry.notna() & ~g.geometry.is_empty]

    invalidas = ~g.geometry.is_valid
    if invalidas.any():
        g.loc[invalidas, "geometry"] = make_valid(g.loc[invalidas, "geometry"])
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]

    # Mismo CODIGO con varias geometrías: se conserva la mayor, que es la que el
    # catastro reconoce como predio; las otras son restos de partición.
    if "CODIGO" in g.columns and len(g):
        g["_a"] = g.to_crs(config.CRS_METRICO).geometry.area
        g = (g.sort_values("_a", ascending=False)
               .drop_duplicates(subset=["CODIGO"], keep="first")
               .drop(columns="_a"))

    # Recorte contra la celda real: el envolvente trae predios de fuera
    g = g[g.geometry.intersects(geom_wgs84)].copy()
    g["cell_id"] = celda

    # Ficha alfanumérica, si está descargada
    reg = _raw_registro(celda)
    for col in ("destino_economico", "destino", "area_terreno_catastro_m2",
                "area_construida_m2", "numero_predial_anterior"):
        g[col] = np.nan if col.startswith("area") else None
    if reg.exists() and len(g):
        try:
            filas = json.loads(reg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            filas = []
        if filas:
            r = pd.DataFrame(filas).rename(columns={CAMPO_PREDIO_ANTERIOR: CAMPO_PREDIO})
            r = r.drop_duplicates(subset=[CAMPO_PREDIO])
            idx = r.set_index(CAMPO_PREDIO)
            cod = g["CODIGO"].astype(str)
            g["destino_economico"] = cod.map(idx.get("DESTINO_ECONOMICO", pd.Series(dtype=object)))
            g["destino"] = g["destino_economico"].map(
                lambda x: DESTINO_ECONOMICO.get(x, x) if pd.notna(x) else None)
            g["area_terreno_catastro_m2"] = pd.to_numeric(
                cod.map(idx.get("AREA_TERRENO", pd.Series(dtype=float))), errors="coerce")
            g["area_construida_m2"] = pd.to_numeric(
                cod.map(idx.get("AREA_CONSTRUIDA", pd.Series(dtype=float))), errors="coerce")
            g["nombre_predio"] = cod.map(idx.get("DIRECCION", pd.Series(dtype=object)))
            # Número predial anterior (20 dígitos): es el que suele figurar en el folio de
            # matrícula y el que acepta la consulta por referencia catastral de la SNR.
            ant = idx.get("NUMERO_PREDIAL_ANTERIOR", idx.get("NUMERO_PREDIAL_NACIONAL", pd.Series(dtype=object)))
            g["numero_predial_anterior"] = cod.map(ant)

    # REGISTRO_2: zonas homogéneas y construcciones. Un predio puede tener varias filas.
    g["zonas_economicas"] = None
    for col in ("zona_economica_dominante", "n_construcciones",
                "construccion_uso_principal", "construccion_puntaje_max"):
        g[col] = np.nan
    reg2 = _raw_registro2(celda)
    if reg2.exists() and len(g):
        try:
            filas2 = json.loads(reg2.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            filas2 = []
        if filas2:
            g = _unir_registro2(g, pd.DataFrame(filas2))
    return g


def _unir_registro2(g: gpd.GeoDataFrame, r2: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Agrega REGISTRO_2 por predio: zonas económicas con su área ("6:77.0;7:24.6;8:105.0",
    en hectáreas), la dominante por área, y el resumen de construcciones.
    """
    zonas, dominante, n_con, uso_pral, punt_max = {}, {}, {}, {}, {}
    r2 = r2.rename(columns={CAMPO_PREDIO_ANTERIOR: CAMPO_PREDIO})
    for cod, sub in r2.groupby(CAMPO_PREDIO):
        acum: dict[int, float] = {}
        n = 0; usos: dict[int, float] = {}; pmax = 0
        for _, f in sub.iterrows():
            for k in (1, 2):
                z = f.get(f"ZONA_ECONOMICA_{k}"); a = f.get(f"AREA_TERRENO_{k}")
                if z and a and float(a) > 0:
                    acum[int(z)] = acum.get(int(z), 0.0) + float(a) / 1e4
            for k in (1, 2, 3):
                a = f.get(f"AREA_CONSTRUIDA_{k}")
                if a and float(a) > 0:
                    n += 1
                    u = f.get(f"USO_{k}")
                    if u:
                        usos[int(u)] = usos.get(int(u), 0.0) + float(a)
                    p = f.get(f"PUNTAJE_{k}")
                    if p:
                        pmax = max(pmax, int(p))
        if acum:
            zonas[cod] = ";".join(f"{z}:{a:.1f}" for z, a in sorted(acum.items()))
            dominante[cod] = max(acum, key=acum.get)
        n_con[cod] = n
        if usos:
            uso_pral[cod] = max(usos, key=usos.get)
        punt_max[cod] = pmax if n else None
    cod = g["CODIGO"].astype(str)
    g["zonas_economicas"] = cod.map(zonas)
    g["zona_economica_dominante"] = pd.to_numeric(cod.map(dominante), errors="coerce")
    g["n_construcciones"] = pd.to_numeric(cod.map(n_con), errors="coerce")
    g["construccion_uso_principal"] = pd.to_numeric(cod.map(uso_pral), errors="coerce")
    g["construccion_puntaje_max"] = pd.to_numeric(cod.map(punt_max), errors="coerce")
    return g


def medir(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Añade área (ha), compacidad de Polsby-Popper (1 círculo, ~0 franja), lado equivalente
    y ancho útil (diámetro del mayor círculo inscrito), medidos en CRS métrico. El ancho
    útil no lo penaliza un borde dentado, por eso decide mejor si caben filas de módulos.
    """
    from shapely import maximum_inscribed_circle

    g = g.copy()
    m = g.to_crs(config.CRS_METRICO)
    area = m.geometry.area
    g["area_ha"] = (area / 10_000).round(2)
    perim = m.geometry.length
    g["compacidad"] = (4 * np.pi * area / perim.pow(2)).round(3)
    g["compacidad"] = g["compacidad"].clip(0, 1)

    # Lado del cuadrado de igual área, referencia rápida del tamaño útil del predio.
    g["lado_equiv_m"] = area.pow(0.5).round(0)

    anchos = []
    for geom in m.geometry:
        try:
            anchos.append(round(maximum_inscribed_circle(geom).length * 2, 1))
        except Exception:
            anchos.append(np.nan)
    g["ancho_util_m"] = anchos
    return g


# --------------------------------------------------------------------------
# Selección de celdas
# --------------------------------------------------------------------------

def _fuente_celdas() -> Path:
    for cand in (SALIDA / "grillas_candidatas.gpkg", config.TOP_CANDIDATOS_PATH):
        if cand.exists():
            return cand
    raise SystemExit("No encuentro grillas_candidatas.gpkg. Corre antes reporte_grillas.py")


#: Columnas de la tabla maestra que el lote hereda de su grilla (criterios del índice,
#: exclusiones, contexto). El archivo que baja el visor de grillas no las trae todas.
COLUMNAS_MAESTRAS = ("clasificacion", "indice_aptitud", "ranking", "restricciones", "pvout",
                     "capacidad_at_mw", "capacidad_mt_mw", "sub_nombre_subestacion",
                     "sub_distancia_km", "operador", "municipio", "departamento", "vereda",
                     "zona", "ha_aptas", "mwp_indicativo", "slope_mean", "cobertura_apta_pct")


def _completar_celdas(g: gpd.GeoDataFrame, ruta: Path) -> gpd.GeoDataFrame:
    """Añade por cell_id las columnas maestras que falten, desde grillas_candidatas.gpkg."""
    faltan = [c for c in COLUMNAS_MAESTRAS if c not in g.columns]
    maestra = SALIDA / "grillas_candidatas.gpkg"
    if not faltan or not maestra.exists() or ruta.resolve() == maestra.resolve():
        return g
    try:
        m = gpd.read_file(maestra)
    except Exception:
        return g
    m["cell_id"] = m["cell_id"].astype(str)
    cols = [c for c in faltan if c in m.columns]
    if not cols:
        return g
    orden = g.index
    g = g.merge(m[["cell_id"] + cols].drop_duplicates("cell_id"), on="cell_id", how="left")
    g.index = orden
    return g


def _leer_celdas(ruta: Path) -> gpd.GeoDataFrame:
    """
    Lee un archivo de celdas. GPKG y GeoJSON entran por GDAL; el CSV del botón "para
    predios" (punto y coma, BOM, WKT) se lee a mano y, si no trae WKT, la geometría se
    toma de la tabla maestra de candidatas por cell_id.
    """
    if ruta.suffix.lower() != ".csv":
        return gpd.read_file(ruta)
    primera = ruta.read_text(encoding="utf-8-sig").splitlines()[0]
    sep = ";" if primera.count(";") >= primera.count(",") else ","
    t = pd.read_csv(ruta, sep=sep, encoding="utf-8-sig", dtype=str)
    col = next((c for c in t.columns if c.strip().lower() in ("cell_id", "id grilla", "id")), None)
    if col is None:
        raise SystemExit(f"{ruta.name} no trae columna cell_id. Columnas: {list(t.columns)[:8]}")
    t = t.rename(columns={col: "cell_id"})
    t["cell_id"] = t["cell_id"].astype(str).str.strip().str.zfill(7)
    if "wkt" in (c.lower() for c in t.columns):
        from shapely import wkt as _wkt
        wcol = next(c for c in t.columns if c.lower() == "wkt")
        geom = t[wcol].map(lambda s: _wkt.loads(s) if isinstance(s, str) and s.strip() else None)
        return gpd.GeoDataFrame(t.drop(columns=[wcol]), geometry=geom, crs="EPSG:4326")
    # sin geometría: se toma de la tabla maestra
    m = gpd.read_file(_fuente_celdas())
    m["cell_id"] = m["cell_id"].astype(str).str.zfill(7)
    return m[m["cell_id"].isin(set(t["cell_id"]))].copy()


def resolver_celdas(celdas: str | None, clase: str | None,
                    limite: int | None = None) -> gpd.GeoDataFrame:
    """
    Devuelve las celdas a consultar. `--celdas` acepta una ruta a un archivo de celdas o
    una lista de cell_id separada por comas; se distinguen porque la ruta existe en disco.
    """
    ruta, pedidas = _fuente_celdas(), None

    if celdas:
        cand = Path(celdas)
        if not cand.is_absolute():
            cand = config.PROJECT_ROOT / celdas
        if cand.exists() and cand.is_file():
            ruta = cand
        else:
            pedidas = {c.strip() for c in celdas.split(",") if c.strip()}

    g = _leer_celdas(ruta)
    if "cell_id" not in g.columns:
        raise SystemExit(f"{ruta.name} no tiene columna cell_id")
    g["cell_id"] = g["cell_id"].astype(str)
    g.attrs["origen"] = ruta.name
    g = _completar_celdas(g, ruta)

    if pedidas is not None:
        faltan = pedidas - set(g["cell_id"])
        if faltan:
            print(f"  aviso: {len(faltan)} celdas pedidas no están en {ruta.name}: "
                  f"{', '.join(sorted(faltan)[:6])}")
        g = g[g["cell_id"].isin(pedidas)]
    elif clase and clase.lower() not in ("todas", "todo", "*"):
        if "clasificacion" not in g.columns:
            raise SystemExit(f"{ruta.name} no tiene columna clasificacion; usa --clase todas")
        g = g[g["clasificacion"] == clase]

    if "indice_aptitud" in g.columns:
        g = g.sort_values("indice_aptitud", ascending=False)
    if limite:
        g = g.head(limite)
    return g


def pendientes(g: gpd.GeoDataFrame, con_registro: bool = True) -> list[str]:
    """Celdas a las que les falta alguna descarga o cuya descarga es de un corte anterior."""
    man = leer_manifiesto()
    falta = []
    for cid in g["cell_id"].astype(str):
        # Celdas cuyo catastro NO vino del servicio nacional, porque su municipio
        # administra el suyo propio y el nacional no lo publica. Volver a pedirlas ahi
        # devuelve cero lotes y sobrescribe los que se bajaron por la via municipal, que
        # es lo que paso con Villavicencio: 157 lotes en disco y el manifiesto en cero.
        # Se reconocen por el campo `fuente`, que solo escriben los descargadores
        # municipales. Para rehacerlas hay que volver a correr su propio descargador.
        if any((man.get(cid, {}).get(t) or {}).get("fuente") for t in CAPAS.values()):
            continue
        if not all(_raw(cid, t).exists() for t in CAPAS.values()):
            falta.append(cid)
        elif any((man.get(cid, {}).get(t) or {}).get("corte") != CORTE for t in CAPAS.values()):
            falta.append(cid)
        elif con_registro and _codigos_de(cid) and not (
                _raw_registro(cid).exists() and _raw_registro2(cid).exists()):
            falta.append(cid)
    return falta


# --------------------------------------------------------------------------

def _resumen_estado(g: gpd.GeoDataFrame) -> None:
    man = leer_manifiesto()
    filas = []
    for cid in g["cell_id"].astype(str):
        r = {"cell_id": cid}
        for tipo in list(CAPAS.values()) + ["registro1"]:
            ruta = _raw(cid, tipo) if tipo in CAPAS.values() else _raw_registro(cid)
            if not ruta.exists():
                r[tipo] = "falta"
            else:
                n = (man.get(cid, {}).get(tipo) or {}).get("n")
                if n is None:
                    try:
                        d = json.loads(ruta.read_text(encoding="utf-8"))
                        n = len(d.get("features", d) if isinstance(d, dict) else d)
                    except Exception:
                        n = -1
                r[tipo] = str(n)
        filas.append(r)
    t = pd.DataFrame(filas)
    print(t.to_string(index=False))
    print()
    for tipo in list(CAPAS.values()) + ["registro1"]:
        print(f"  {tipo:<10} descargadas {int((t[tipo] != 'falta').sum())} de {len(t)}")


def main(argv=None) -> int:
    """CLI: resuelve celdas, descarga lo pendiente, procesa, mide y escribe predios.gpkg."""
    p = argparse.ArgumentParser(description="Descarga predios del IGAC por celda")
    p.add_argument("--clase", default="todas",
                   help="clase de celda a procesar, o 'todas' (por defecto Prioritaria)")
    p.add_argument("--celdas", default=None,
                   help="archivo de celdas, o lista de cell_id separada por comas")
    p.add_argument("--limite", type=int, default=None, help="procesar solo las N primeras")
    p.add_argument("--forzar", action="store_true", help="ignorar la caché")
    p.add_argument("--reintentar", action="store_true",
                   help="procesar solo las celdas a las que les falta alguna descarga")
    p.add_argument("--sin-registro", action="store_true",
                   help="no bajar REGISTRO_1 (destino económico y áreas)")
    p.add_argument("--estado", action="store_true",
                   help="solo informar de qué hay descargado y qué falta")
    a = p.parse_args(argv)

    celdas = resolver_celdas(a.celdas, a.clase, a.limite)
    if celdas.empty:
        raise SystemExit("Ninguna celda coincide con el filtro")

    if a.estado:
        print("=" * 74)
        print("ESTADO DE LA DESCARGA DE PREDIOS")
        print("=" * 74)
        _resumen_estado(celdas)
        return 0

    # Si el equipo ya publicó estas descargas, se traen del bucket en vez de volver
    # a consultar el IGAC celda por celda.
    if not a.forzar:
        try:
            import insumos
            n = insumos.asegurar("igac_predios")
            if n:
                print(f"  recuperadas {n} capas de predios desde el bucket")
        except Exception:
            pass

    if a.reintentar:
        falta = set(pendientes(celdas, con_registro=not a.sin_registro))
        celdas = celdas[celdas["cell_id"].isin(falta)]
        if celdas.empty:
            print("No hay nada pendiente: todas las celdas del conjunto están descargadas.")
            return 0

    celdas_wgs = celdas.to_crs(config.CRS_GEOGRAFICO)
    manifiesto = leer_manifiesto()

    print("=" * 74)
    print("PREDIOS CATASTRALES DEL IGAC")
    print("=" * 74)
    print(f"  celdas a procesar: {len(celdas)}   "
          f"({'reintento' if a.reintentar else a.celdas or 'clase ' + a.clase})")
    print(f"  origen           : {celdas.attrs.get('origen', '?')}")
    print(f"  corte de la base : {CORTE_TEXTO}\n")

    todos, fallos = [], []
    for i, (_, row) in enumerate(celdas_wgs.iterrows(), 1):
        celda = str(row["cell_id"])
        cacheada = (all(_raw(celda, t).exists() and _del_corte(manifiesto, celda, t) for t in CAPAS.values())
                    and not a.forzar)
        print(f"  [{i:>3}/{len(celdas)}] {celda}...", end=" ", flush=True)
        try:
            descargar_raw(celda, row.geometry, forzar=a.forzar, manifiesto=manifiesto)
            if not a.sin_registro:
                descargar_registro(celda, forzar=a.forzar, manifiesto=manifiesto)
                descargar_registro(celda, forzar=a.forzar, manifiesto=manifiesto,
                                   tabla=CAPA_REGISTRO2)
            g = procesar_celda(celda, row.geometry)
        except Exception as exc:
            print(f"error: {type(exc).__name__}: {str(exc)[:60]}")
            _anotar(manifiesto, celda, "error",
                    ok=False, tipo=type(exc).__name__, mensaje=str(exc)[:200])
            escribir_manifiesto(manifiesto)
            fallos.append(celda)
            continue
        if len(g):
            todos.append(g)
        print(f"{len(g):>4} predios{'  (caché)' if cacheada else ''}")
        escribir_manifiesto(manifiesto)

    if not todos:
        print("\nNinguna celda devolvió predios en esta corrida.")
        if fallos:
            print(f"Celdas con error: {', '.join(fallos)}")
        return 1

    g = gpd.GeoDataFrame(pd.concat(todos, ignore_index=True),
                         geometry="geometry", crs="EPSG:4326")
    g = medir(g)

    SALIDA.mkdir(parents=True, exist_ok=True)
    g.to_file(SALIDA / "predios.gpkg", driver="GPKG")
    (SALIDA / "predios.corte").write_text(CORTE, encoding="utf-8")

    print()
    print("-" * 74)
    print("RESUMEN")
    print("-" * 74)
    print(f"  predios descargados : {len(g):,}".replace(",", "."))
    print(f"  celdas con predios  : {g['cell_id'].nunique()} de {len(celdas)}")
    if fallos:
        print(f"  celdas con error    : {', '.join(fallos)}")
    print(f"  por clase de suelo  : {g['clase_suelo'].value_counts().to_dict()}")
    if g["destino"].notna().any():
        cob = g["destino_economico"].notna().mean() * 100
        print(f"  con ficha REGISTRO_1: {cob:.1f}% de los predios")
        print(f"  destinos            : "
              f"{g['destino'].value_counts().head(5).to_dict()}")
    print()
    print("  Área de los predios (ha)")
    print(g["area_ha"].describe().round(2).to_string())
    print()
    for corte in (2, 5, 10, 20, 30, 50, 100, 150):
        n = int((g["area_ha"] >= corte).sum())
        print(f"    {corte:>3} ha o más : {n:>6,}".replace(",", "."))
    print()
    print(f"  GPKG -> {SALIDA / 'predios.gpkg'}")

    falta = pendientes(celdas, con_registro=not a.sin_registro)
    if falta:
        print(f"\n  Quedan {len(falta)} celdas incompletas. Para reintentar solo esas:")
        print(f"    .venv\\Scripts\\python.exe -m predios.predios_igac --reintentar "
              f"--clase {a.clase}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
