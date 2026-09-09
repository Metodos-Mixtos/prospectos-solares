"""
Lotes catastrales de MONTERIA (Cordoba, DANE 23001) para las celdas del proyecto.

Por que existe: Monteria administra su propio catastro (gestor G0046, Resolucion IGAC
853 del 27/06/2023, en operacion desde el 17/10/2023), asi que el FeatureServer
nacional del corte vigente -Base_Catastral_Publica_del_Gestor_IGAC_06_2026- NO publica
sus terrenos: sobre la celda 0008656 devuelve cero.

Fuente que si los publica:
    https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/RTerreno/FeatureServer/0
    Item publico 8598784a652848a79e7b79f4328e82bb de la organizacion ArcGIS Online del
    IGAC (propietario ana.corredor_IGAC_OIT, acceso "public", etiqueta "catastro").
    Capa R_TERRENO nacional, 2.402.000 registros, de los cuales 19.167 son de Monteria
    (CODIGO que empieza por 23001). Campos: OBJECTID, CODIGO (30 digitos),
    VEREDA_CODIGO, NUMERO_SUBTERRANEOS, CODIGO_ANTERIOR (20 digitos), GLOBALID,
    codigo_municipio, Shape__Area, Shape__Length. Devuelve poligonos en EPSG:4686.

ADVERTENCIA DE VIGENCIA. El item se creo el 30/06/2022 y se modifico por ultima vez el
15/03/2023, es decir ANTES de que el municipio asumiera el catastro (17/10/2023). Son
los terrenos que el IGAC tenia levantados de Monteria, no el catastro municipal al dia.
Sirven para delimitar y caracterizar lotes; NO sustituyen una certificacion catastral
del gestor municipal para linderos, areas oficiales, avaluo o titularidad.

Lo que NO trae, y por eso queda vacio: la tabla alfanumerica REGISTRO_1/REGISTRO_2
(destino economico, area de terreno catastral, avaluo, direccion). El servicio nacional
no tiene esas filas para codigos 23001, comprobado.

Salida: el mismo formato crudo que produce predios/predios_igac.py, para que el resto
del procedimiento lo consuma sin cambios:
    data/igac/igac_<celda>_rural.geojson
    data/igac/igac_<celda>_urbano.geojson   (vacio: la celda es rural)
y la anotacion correspondiente en data/igac/_estado.json.

Uso:
    .venv\\Scripts\\python.exe outputs\\monteria\\monteria_lotes.py [--celdas 0008656] [--forzar]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

_RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_RAIZ), str(_RAIZ / "soporte"), str(_RAIZ / "predios")]
import config  # noqa: E402,F401
import predios_igac as pig  # noqa: E402

URL = ("https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services"
       "/RTerreno/FeatureServer/0")
ITEM = "8598784a652848a79e7b79f4328e82bb"
#: Vigencia real del dato, no el corte del servicio nacional.
FUENTE = "IGAC RTerreno (item %s), ultima modificacion 2023-03-15" % ITEM
DANE = "23001"

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
PAGINA = 1000
PAUSA = 0.4
REINTENTOS = 3

CELDAS = _RAIZ / "outputs" / "reporte" / "grillas_para_predios.geojson"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def geometrias(celdas: list[str]) -> dict[str, dict]:
    """Feature completo de cada celda pedida, leido de grillas_para_predios.geojson."""
    d = json.loads(CELDAS.read_text(encoding="utf-8"))
    out = {}
    for f in d["features"]:
        cid = str(f["properties"].get("cell_id"))
        if cid in celdas:
            out[cid] = f
    faltan = sorted(set(celdas) - set(out))
    if faltan:
        raise SystemExit("celdas no encontradas en %s: %s" % (CELDAS.name, ", ".join(faltan)))
    return out


def _bounds(geom: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def rec(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                rec(x)

    rec(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def _consultar(bounds, offset: int) -> dict:
    minx, miny, maxx, maxy = bounds
    params = {
        "geometry": json.dumps({"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
                                "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": 4326,
        "outSR": 4326,
        # Solo Monteria: la capa es nacional y el envolvente puede tocar municipios
        # vecinos que ya vienen del servicio nacional; duplicarlos ensuciaria la
        # deduplicacion posterior por CODIGO.
        "where": "CODIGO LIKE '" + DANE + "%'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": str(PAGINA),
        "resultOffset": str(offset),
    }
    ultimo = None
    for intento in range(REINTENTOS):
        try:
            r = requests.post(URL + "/query", data=params, headers=UA, timeout=180)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", "error del servicio"))
            return data
        except Exception as exc:          # noqa: BLE001
            ultimo = exc
            time.sleep(PAUSA * (intento + 2))
    raise RuntimeError("tras %d intentos: %s" % (REINTENTOS, ultimo))


def _normalizar(props: dict) -> dict:
    """
    Deja los atributos con los mismos nombres que el servicio nacional, para que
    predios_igac.py los lea sin ramas especiales.
    """
    cod = str(props.get("CODIGO") or "")
    p = dict(props)
    # En RTerreno codigo_municipio viene truncado a 4 caracteres ("2300"); el nacional
    # trae los 5 del DIVIPOLA. Se reconstruye desde el propio codigo predial.
    p["codigo_municipio"] = cod[:5] or None
    p.setdefault("CODIGO_DEPARTAMENTO", None)
    return p


def descargar(celda: str, feature: dict, forzar: bool = False) -> int:
    """Baja los terrenos de la celda y escribe los dos GeoJSON crudos. Devuelve n rural."""
    pig.CACHE.mkdir(parents=True, exist_ok=True)
    rural = pig.CACHE / ("igac_%s_rural.geojson" % celda)
    urbano = pig.CACHE / ("igac_%s_urbano.geojson" % celda)

    if rural.exists() and not forzar:
        try:
            n = len(json.loads(rural.read_text(encoding="utf-8")).get("features", []))
        except (json.JSONDecodeError, OSError):
            n = 0
        if n:
            print("  %s: ya descargada (%d lotes). Usa --forzar para repetir." % (celda, n))
            return n

    bounds = _bounds(feature["geometry"])
    acumulado = {"type": "FeatureCollection", "features": []}
    offset, paginas = 0, 0
    while True:
        data = _consultar(bounds, offset)
        feats = data.get("features", [])
        for f in feats:
            f["properties"] = _normalizar(f.get("properties") or {})
        acumulado["features"].extend(feats)
        paginas += 1
        if not data.get("properties", {}).get("exceededTransferLimit") \
           and not data.get("exceededTransferLimit"):
            break
        if len(feats) < PAGINA:
            break
        if paginas > 40:
            break
        offset += PAGINA
        time.sleep(PAUSA)

    rural.write_text(json.dumps(acumulado, ensure_ascii=False), encoding="utf-8")
    # La celda es rural; se escribe el urbano vacio para que el flujo encuentre los dos
    # archivos, igual que cuando el servicio nacional no devuelve nada urbano.
    urbano.write_text(json.dumps({"type": "FeatureCollection", "features": []},
                                 ensure_ascii=False), encoding="utf-8")

    m = pig.leer_manifiesto()
    # Se anota con el corte vigente de predios_igac para que `pendientes()` no vuelva a
    # pedir la celda al servicio nacional y la sobrescriba con cero lotes; `fuente` deja
    # constancia de que el dato no salio de ese servicio.
    for tipo, n in (("rural", len(acumulado["features"])), ("urbano", 0)):
        m.setdefault(celda, {})[tipo] = {
            "cuando": _ahora(), "ok": True, "n": n,
            "paginas": paginas if tipo == "rural" else 0,
            "truncado": False, "corte": pig.CORTE, "fuente": FUENTE,
            "gestor": "G0046 Municipio de Monteria",
        }
    pig.escribir_manifiesto(m)
    return len(acumulado["features"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Lotes catastrales de Monteria (23001).")
    ap.add_argument("--celdas", nargs="*", default=["0008656"],
                    help="cell_id a descargar (por defecto 0008656)")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()

    feats = geometrias([str(c) for c in a.celdas])
    print("Fuente: %s/query" % URL)
    print("Vigencia: %s\n" % FUENTE)
    total = 0
    for celda, f in feats.items():
        muni = f["properties"].get("municipio")
        n = descargar(celda, f, forzar=a.forzar)
        total += n
        print("  %s (%s): %d lotes rurales -> data/igac/igac_%s_rural.geojson"
              % (celda, muni, n, celda))
    print("\nTotal: %d lotes." % total)


if __name__ == "__main__":
    main()
