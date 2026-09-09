# -*- coding: utf-8 -*-
"""
Reporte visual de las grillas candidatas.

Lee lo que produce reporte_grillas.py y arma un HTML autocontenido, sin servidor ni
dependencias externas: el mapa de Colombia va como SVG embebido y los datos como JSON
en línea. Se abre con doble clic y se puede mandar por correo.

Lo que trae, además de la tabla:

  - mapa con las 100 grillas, coloreables por recurso, por clasificación o por zona
  - zonas de prospección, que es como de verdad se organiza el trabajo de campo
  - simulador de umbrales: mover los criterios y ver la reclasificación en vivo
  - exportación de la selección filtrada a CSV desde el propio navegador

Uso:
    .venv\\Scripts\\python.exe reporte_html.py
"""

from __future__ import annotations

import collections
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd

warnings.filterwarnings("ignore")
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config
import gcs

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
DESTINO = SALIDA / "reporte_grillas.html"

# Lienzo del mapa y ventana geográfica de Colombia continental
W, H = 760, 900
LON0, LON1 = -79.2, -66.7
LAT0, LAT1 = -4.3, 13.6

DEPTOS_DIBUJADOS = [
    "CÓRDOBA", "SUCRE", "BOLÍVAR", "ANTIOQUIA", "VALLE DEL CAUCA", "HUILA", "CESAR",
    "SANTANDER", "ATLÁNTICO", "MAGDALENA", "NORTE DE SANTANDER", "TOLIMA", "CAUCA",
    "CUNDINAMARCA", "META", "CALDAS", "LA GUAJIRA", "QUINDIO",
]


# --------------------------------------------------------------------------
# Geometría a SVG
# --------------------------------------------------------------------------

def proyectar(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON0) / (LON1 - LON0) * W
    y = (LAT1 - lat) / (LAT1 - LAT0) * H
    return x, y


def geom_a_path(geom, tolerancia: float, area_minima: float = 0.004) -> str:
    """Convierte una geometría a un atributo d de SVG, simplificando y quitando islotes."""
    g = geom.simplify(tolerancia, preserve_topology=True)
    partes = []
    for p in (g.geoms if g.geom_type.startswith("Multi") else [g]):
        if p.is_empty or p.area < area_minima:
            continue
        pts = ["%.1f %.1f" % proyectar(lon, lat) for lon, lat in p.exterior.coords]
        if pts:
            partes.append("M" + "L".join(pts) + "Z")
    return "".join(partes)


def cargar_subestaciones() -> list[dict]:
    """
    Las 499 subestaciones del SIN, proyectadas al lienzo del mapa.

    Se llevan al reporte para poder encenderlas y apagarlas: ver dónde está la red
    explica de un vistazo por qué las candidatas se agrupan donde se agrupan, que es
    justo lo que el ranking premia.
    """
    import pandas as pd

    try:
        s = gpd.read_file(config.SUBESTACIONES_PATH)
    except Exception as exc:
        print(f"  aviso: no se pudieron cargar las subestaciones ({type(exc).__name__})")
        return []

    if s.crs is None:
        s = s.set_crs(config.CRS_GEOGRAFICO)
    s = s.to_crs(config.CRS_GEOGRAFICO)

    tension = pd.to_numeric(
        s.get("tension", pd.Series(dtype=str)).astype(str)
        .str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce")

    out = []
    for i, row in s.iterrows():
        p = row.geometry
        if p is None or p.is_empty:
            continue
        lon, lat = (p.x, p.y) if p.geom_type == "Point" else (p.centroid.x, p.centroid.y)
        if not (LON0 <= lon <= LON1 and LAT0 <= lat <= LAT1):
            continue
        x, y = proyectar(lon, lat)
        kv = tension.iloc[i] if i < len(tension) else None
        out.append({
            "x": round(x, 1), "y": round(y, 1),
            "n": str(row.get("nombre_subestacion") or "Subestación"),
            "kv": None if kv is None or kv != kv or kv <= 0 else int(kv),
        })
    return out


def cargar_lineas() -> list[dict]:
    """
    Líneas de transmisión proyectadas al lienzo, si lineas_transmision.py ya se corrió.

    Se simplifican quitando vértices casi alineados: a la escala del mapa nacional el
    detalle fino no se ve y multiplicaría el peso del archivo sin aportar nada.
    """
    ruta = SALIDA / "lineas_transmision.json"
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as fh:
        crudas = json.load(fh)

    out = []
    for l in crudas:
        pts = []
        for lon, lat in l.get("coords", []):
            if not (LON0 <= lon <= LON1 and LAT0 <= lat <= LAT1):
                continue
            x, y = proyectar(lon, lat)
            p = (round(x, 1), round(y, 1))
            if not pts or abs(p[0] - pts[-1][0]) + abs(p[1] - pts[-1][1]) > 0.6:
                pts.append(p)
        if len(pts) >= 2:
            out.append({"kv": l.get("kv"), "p": pts})
    return out


def cargar_vecinos() -> str:
    """
    Contorno de los países con los que Colombia comparte frontera.

    Sin ellos, las líneas de transmisión que cruzan hacia Venezuela o Ecuador parecen
    salirse del mapa hacia la nada. Con el vecino dibujado detrás se entiende que la
    red continúa. Fuente: Natural Earth 1:50m, dominio público.
    """
    ruta = config.PROJECT_ROOT / "data" / "paises" / "ne_50m_admin_0_countries.shp"
    if not ruta.exists():
        return ""
    try:
        g = gpd.read_file(ruta).to_crs(config.CRS_GEOGRAFICO)
    except Exception:
        return ""
    col = "ADMIN" if "ADMIN" in g.columns else g.columns[0]
    vecinos = g[g[col].isin(["Venezuela", "Ecuador", "Peru", "Brazil", "Panama"])]
    if vecinos.empty:
        return ""
    # Se recorta a la ventana del mapa: no interesa el resto de Brasil ni las Galápagos
    from shapely.geometry import box
    ventana = box(LON0, LAT0, LON1, LAT1)
    recorte = vecinos.geometry.intersection(ventana)
    recorte = recorte[~recorte.is_empty & recorte.notna()]
    if recorte.empty:
        return ""
    return geom_a_path(recorte.union_all(), 0.04, area_minima=0.002)


def cargar_divisiones() -> dict:
    """
    Límites administrativos conmutables: departamento, municipio y vereda.

    Los municipios no existen como capa propia en el bucket, así que se derivan
    disolviendo las veredas por su código municipal. Las veredas son 32.000 y dibujarlas
    todas dispararía el peso del archivo sin que se distinga nada a escala nacional, así
    que solo se incluyen las que tocan alguna celda candidata, que son las únicas donde
    ese nivel de detalle sirve para algo.
    """
    salida = {"departamento": {}, "municipio": {}, "vereda": {}}

    # --- departamentos, del MGN ---
    try:
        shp = gcs.obtener("geoinfo", "Colombia/Colombia_boundary/MGN_ADM_DPTO_POLITICO.shp",
                          verbose=False)
        d = gpd.read_file(shp).to_crs(config.CRS_GEOGRAFICO)
        col = next(c for c in d.columns if "CNMBR" in c.upper())
        for _, r in d.iterrows():
            p = geom_a_path(r.geometry, 0.02, area_minima=0.001)
            if p:
                salida["departamento"][str(r[col]).strip().title()] = p
    except Exception as exc:
        print(f"  aviso: departamentos no disponibles ({type(exc).__name__})")

    # --- veredas y municipios ---
    ver = config.PROJECT_ROOT / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    if not ver.exists():
        print("  aviso: falta base_veredas.shp, sin municipios ni veredas")
        return salida

    try:
        v = gpd.read_file(ver)
        if v.crs is None:
            v = v.set_crs(config.CRS_GEOGRAFICO)
        v = v.to_crs(config.CRS_GEOGRAFICO)
    except Exception as exc:
        print(f"  aviso: no se pudo leer base_veredas ({type(exc).__name__})")
        return salida

    cod_mpio = next((c for c in v.columns
                     if c.upper() in ("CODIGO_MUN", "COD_MPIO", "MPIO_CDPMP", "DPTOMPIO")), None)
    nom_mpio = next((c for c in v.columns
                     if c.upper() in ("NOM_MUN", "NOMBRE_MUN", "MPIO_CNMBR", "NOMB_MPIO")), None)
    nom_ver = next((c for c in v.columns
                    if c.upper() in ("NOMBRE_VER", "NOM_VER", "VEREDA")), None)

    if cod_mpio:
        try:
            m = v.dissolve(by=cod_mpio, aggfunc="first")
            for cod, r in m.iterrows():
                p = geom_a_path(r.geometry, 0.008, area_minima=0.0002)
                if p:
                    etiqueta = str(r[nom_mpio]).strip().title() if nom_mpio else str(cod)
                    salida["municipio"][f"{etiqueta}|{cod}"] = p
            print(f"  municipios derivados de veredas: {len(salida['municipio'])}")
        except Exception as exc:
            print(f"  aviso: no se pudieron disolver municipios ({type(exc).__name__})")

    # veredas solo donde hay candidatas
    try:
        celdas = gpd.read_file(SALIDA / "grillas_candidatas.gpkg").to_crs(config.CRS_GEOGRAFICO)
        cerca = gpd.sjoin(v, celdas[["cell_id", "geometry"]], how="inner", predicate="intersects")
        cerca = cerca[~cerca.index.duplicated(keep="first")]
        for i, r in cerca.iterrows():
            p = geom_a_path(r.geometry, 0.002, area_minima=0.00002)
            if p:
                etiqueta = str(r[nom_ver]).strip().title() if nom_ver else str(i)
                salida["vereda"][f"{etiqueta}|{i}"] = p
        print(f"  veredas sobre celdas candidatas: {len(salida['vereda'])}")
    except Exception as exc:
        print(f"  aviso: no se pudieron filtrar veredas ({type(exc).__name__})")

    return salida


def cargar_mapa() -> tuple[str, dict]:
    """
    Contorno nacional y de los departamentos con candidatas.

    Si el bucket no responde, por credenciales caducadas o por estar sin conexión, el
    reporte se genera igual y solo se queda sin el fondo del mapa. Antes esto tumbaba
    todo el proceso al final, después de veinte minutos de cálculo, por una capa que es
    decorativa.
    """
    try:
        shp = gcs.obtener("geoinfo", "Colombia/Colombia_boundary/MGN_ADM_DPTO_POLITICO.shp",
                          verbose=False)
    except Exception as exc:
        print(f"  aviso: sin contorno del país ({type(exc).__name__}). "
              f"El mapa queda sin fondo; el resto del reporte no cambia.")
        if "Refresh" in type(exc).__name__ or "auth" in str(exc).lower():
            print("         renueva con: gcloud auth application-default login")
        return "", {}

    d = gpd.read_file(shp).to_crs(config.CRS_GEOGRAFICO)
    col = next(c for c in d.columns if "CNMBR" in c.upper())

    pais = geom_a_path(d.geometry.union_all(), 0.035)
    deptos = {}
    for _, r in d.iterrows():
        nombre = str(r[col]).strip().upper()
        if nombre in DEPTOS_DIBUJADOS:
            p = geom_a_path(r.geometry, 0.03)
            if p:
                deptos[nombre] = p
    return pais, deptos


# --------------------------------------------------------------------------
# Fragmentos de HTML
# --------------------------------------------------------------------------

def barras(pares, total, limite=8) -> str:
    filas = []
    for nombre, c in pares[:limite]:
        corto = nombre if len(nombre) <= 34 else nombre[:32].rstrip() + "…"
        filas.append(
            '<div class="bar-row"><span class="bar-lab" title="%s">%s</span>'
            '<span class="bar-track"><span class="bar-fill" style="width:%.1f%%"></span></span>'
            '<span class="bar-num">%d</span></div>'
            % (nombre.replace('"', "&quot;"), corto, c / total * 100, c)
        )
    resto = sum(c for _, c in pares[limite:])
    if resto:
        filas.append(
            '<div class="bar-row bar-rest"><span class="bar-lab">Otros (%d)</span>'
            '<span class="bar-track"><span class="bar-fill alt" style="width:%.1f%%"></span></span>'
            '<span class="bar-num">%d</span></div>'
            % (len(pares) - limite, resto / total * 100, resto)
        )
    return "\n".join(filas)


def tarjetas_zonas(zonas: list[dict], total_grillas: int) -> str:
    if not zonas:
        return '<p class="vacio">Sin zonas agrupadas.</p>'
    out = []
    for z in zonas[:9]:
        out.append(
            '<div class="zona">'
            f'<div class="zona-top"><span class="zona-id">{z["zona"]}</span>'
            f'<span class="zona-mwp">{z["mwp"]:,.0f}<small> MWp</small></span></div>'
            f'<div class="zona-dep">{z["depto"].title()}</div>'
            '<div class="zona-datos">'
            f'<span><b>{z["grillas"]:.0f}</b> grillas</span>'
            f'<span><b>{z.get("prioritarias", 0):.0f}</b> prioritarias</span>'
            f'<span><b>{z["ha_aptas"]:,.0f}</b> ha aptas</span>'
            f'<span><b>{z["pvout"]:.0f}</b> kWh/kWp</span>'
            "</div>"
            f'<div class="zona-op" title="{z["operador"]}">{z["operador"]}</div>'
            f'<div class="zona-bar"><span style="width:{z["grillas"] / total_grillas * 100:.1f}%"></span></div>'
            "</div>"
        )
    return "\n".join(out)


def main() -> int:
    origen = SALIDA / "grillas_candidatas.json"
    if not origen.exists():
        raise SystemExit(f"Falta {origen}. Corre antes reporte_grillas.py")

    with open(origen, encoding="utf-8") as fh:
        payload = json.load(fh)

    G = payload["grillas"]
    ZONAS = payload.get("zonas", [])
    BARRAS = payload.get("barras", [])
    CRIT = payload.get("criterios", {})
    SUP = payload.get("supuestos", {})
    n = len(G)

    print("=" * 74)
    print("REPORTE HTML")
    print("=" * 74)
    print(f"  grillas: {n}   zonas: {len(ZONAS)}")

    pais, deptos = cargar_mapa()
    print(f"  contorno: {len(pais)} caracteres   departamentos: {len(deptos)}")

    subes = cargar_subestaciones()
    print(f"  subestaciones en el mapa: {len(subes)}")

    lineas = cargar_lineas()
    print(f"  tramos de línea en el mapa: {len(lineas)}")

    vecinos = cargar_vecinos()
    print(f"  contorno de países vecinos: {'sí' if vecinos else 'no disponible'}")

    div = cargar_divisiones()

    # La grilla: los polígonos de las propias candidatas, que es la única escala a la
    # que la malla de 5 km se distingue en un mapa nacional.
    grilla = {}
    try:
        celdas = gpd.read_file(SALIDA / "grillas_candidatas.gpkg").to_crs(config.CRS_GEOGRAFICO)
        for _, r in celdas.iterrows():
            p = geom_a_path(r.geometry, 0.0005, area_minima=0.0)
            if p:
                grilla[str(r["cell_id"])] = p
    except Exception as exc:
        print(f"  aviso: sin polígonos de grilla ({type(exc).__name__})")
    div["grilla"] = grilla
    print(f"  divisiones: " + ", ".join(f"{k} {len(v)}" for k, v in div.items()))

    for g in G:
        x, y = proyectar(g["lon"], g["lat"])
        g["x"], g["y"] = round(x, 1), round(y, 1)

    pv = [g["pvout"] for g in G if g.get("pvout")]
    ds = [g["dist_sub"] for g in G if g.get("dist_sub") is not None]
    vias = [g["via"] for g in G if g.get("via") is not None]
    pre = sum(1 for g in G if g["clase"] == "Prioritaria")
    via_c = sum(1 for g in G if g["clase"] == "Elegible")
    rep = sum(1 for g in G if g["clase"] == "Condicionada")
    des = sum(1 for g in G if g["clase"] == "Excluida")

    mwp_total = sum(g.get("mwp", 0) for g in G)
    ha_total = sum(g.get("ha", 0) for g in G)

    # El KPI de vía se mantiene; el bloque de estado que lo acompañaba se retiró del
    # reporte, así que ya no se arma el texto de "resuelto o pendiente".
    kpi_via = ""
    if vias:
        kpi_via = (
            '<div class="kpi"><div class="kpi-lab">A vía carrozable</div>'
            f'<div class="kpi-val">{sum(vias) / len(vias):.2f}</div>'
            f'<div class="kpi-note">km de media · {sum(1 for v in vias if v < 1)} a menos de 1 km</div></div>'
        )

    html = PLANTILLA
    reemplazos = {
        "__N__": str(n),
        "__PRE__": str(pre),
        "__VIA__": str(via_c),
        "__REP__": str(rep),
        "__DES__": str(des),
        "__UMBRAL__": "%.0f" % SUP.get("indice_prioritaria", 80),
        "__NREF__": str(SUP.get("n_referencia", "—")),
        "__PVMED__": "%d" % (sum(pv) / len(pv)),
        "__PVMIN__": "%d" % min(pv),
        "__PVMAX__": "%d" % max(pv),
        "__DSMED__": "%.1f" % (sum(ds) / len(ds)),
        "__DSMAX__": "%.1f km" % max(ds),
        "__MWP__": "%.1f" % (mwp_total / 1000),
        "__HA__": f"{ha_total:,.0f}".replace(",", "."),
        "__NZONAS__": str(len(ZONAS)),
        "__KPI_VIA__": kpi_via,
        "__VIEWBOX__": f"0 0 {W} {H}",
        "__PAIS__": pais,
        "__BARRAS_DEP__": barras(collections.Counter(g["depto"] for g in G).most_common(), n),
        "__BARRAS_OP__": barras(collections.Counter(g["operador"] for g in G).most_common(), n),
        "__ZONAS_CARDS__": tarjetas_zonas(ZONAS, n),
        "__DATOS__": json.dumps(G, ensure_ascii=False),
        "__DEPS__": json.dumps(deptos, ensure_ascii=False),
        "__ZONAS__": json.dumps(ZONAS, ensure_ascii=False),
        "__BARRAS__": json.dumps(BARRAS, ensure_ascii=False),
        "__CRIT__": json.dumps(CRIT, ensure_ascii=False),
        "__SUBES__": json.dumps(subes, ensure_ascii=False),
        "__LINEAS__": json.dumps(lineas, ensure_ascii=False),
        "__VECINOS__": vecinos,
        "__DIVISIONES__": json.dumps(div, ensure_ascii=False),
        "__VBW__": str(W),
        "__VBH__": str(H),
        "__SUP__": json.dumps(SUP, ensure_ascii=False),
        # Las fotos van en su propio marcador y no dentro de los supuestos: son varios
        # megas y meterlas ahí volvería ilegible cualquier volcado de la configuración.
        "__SAT__": json.dumps(payload.get("satelital", {}), ensure_ascii=False),
        "__SATFTE__": json.dumps(payload.get("satelital_fuente", ""), ensure_ascii=False),
    }
    for k, v in reemplazos.items():
        html = html.replace(k, v)

    # Un solo archivo. Los dos perfiles viajan dentro y se conmutan en el navegador,
    # así que no hace falta un HTML por perfil ni volver a correr nada para comparar.
    DESTINO.write_text(html, encoding="utf-8")
    perfiles = SUP.get("perfiles", {})
    print(f"\n  perfiles en el reporte: {', '.join(perfiles) or '—'}")
    print(f"  HTML -> {DESTINO}")
    print(f"  Tamaño: {len(html.encode('utf-8')) / 1024:.1f} KB")

    # Copia a entregables/: el HTML se versiona; sus imágenes son insumo (bucket) y se
    # dejan al lado para que el reporte se vea, sin entrar en git.
    import shutil
    entregables = config.PROJECT_ROOT / "entregables"
    entregables.mkdir(exist_ok=True)
    shutil.copy2(DESTINO, entregables / DESTINO.name)
    copiadas = 0
    for s in payload.get("satelital", {}).values():
        origen = SALIDA / s["src"]
        dest = entregables / s["src"]
        if origen.exists() and (not dest.exists() or dest.stat().st_mtime < origen.stat().st_mtime):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, dest)
            copiadas += 1
    print(f"  copia -> {entregables / DESTINO.name}  (+ {copiadas} imágenes a entregables/satelital/)")
    return 0


from .plantilla import PLANTILLA   # noqa: E402  (va aquí para no ensuciar la cabecera)

if __name__ == "__main__":
    sys.exit(main())
