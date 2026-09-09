"""
Catastro rural de Villavicencio desde el servicio de la propia alcaldia.

Villavicencio administra su catastro (gestor G0038), de modo que el FeatureServer
nacional del IGAC no publica sus lotes y la grilla 0021990 salia vacia. La alcaldia
si publica la capa, sin autenticacion, y con el mismo esquema de campos que el
servicio nacional: por eso se puede escribir en data/igac/ y el resto del
procedimiento la consume sin ningun cambio.

    python outputs/catastro_municipal/bajar_villavicencio.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import requests

RAIZ = Path(__file__).resolve().parents[2]
CELDA = "0021990"
SERVICIO = ("https://services7.arcgis.com/BHeMmpbh6URXbisP/arcgis/rest/services"
            "/Catastro_rural_vcio/FeatureServer/11")
PAGINA = 1000

#: El servicio municipal no trae GLOBALID ni CODIGO_DEPARTAMENTO; se derivan del
#: codigo predial, que es de 30 digitos igual que el nacional.
CAMPOS = ["OBJECTID", "CODIGO", "VEREDA_CODIGO", "NUMERO_SUBTERRANEOS",
          "CODIGO_ANTERIOR", "codigo_municipio", "Shape__Area", "Shape__Length"]


def bbox_celda() -> tuple[float, float, float, float]:
    g = gpd.read_file(RAIZ / "outputs" / "reporte" / "grillas_para_predios.geojson").to_crs(4326)
    g = g[g["cell_id"].astype(str).str.zfill(7) == CELDA]
    if g.empty:
        raise SystemExit(f"La celda {CELDA} no esta en la seleccion de grillas.")
    return tuple(g.total_bounds)


def descargar(bbox) -> list[dict]:
    base = {"geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(CAMPOS),
            "returnGeometry": "true", "f": "geojson"}
    rasgos, desde = [], 0
    while True:
        p = dict(base, resultOffset=desde, resultRecordCount=PAGINA)
        r = requests.get(f"{SERVICIO}/query", params=p, timeout=90)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            raise SystemExit(f"El servicio devolvio error: {d['error']}")
        f = d.get("features", [])
        rasgos += f
        print(f"  {len(rasgos)} lotes")
        if len(f) < PAGINA:
            return rasgos
        desde += PAGINA


def main() -> int:
    bbox = bbox_celda()
    print(f"Celda {CELDA}, Villavicencio (Meta)")
    print(f"  recuadro {bbox[0]:.4f} {bbox[1]:.4f} {bbox[2]:.4f} {bbox[3]:.4f}")
    rasgos = descargar(bbox)
    if not rasgos:
        print("  el servicio no devolvio ningun lote")
        return 1

    for f in rasgos:
        p = f.setdefault("properties", {})
        cod = str(p.get("CODIGO") or "")
        # Los dos campos que el servicio municipal no publica se derivan del codigo.
        p.setdefault("GLOBALID", None)
        p["CODIGO_DEPARTAMENTO"] = cod[:2] or None
        p["codigo_municipio"] = p.get("codigo_municipio") or (cod[:5] or None)

    destino = RAIZ / "data" / "igac"
    destino.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": rasgos}
    (destino / f"igac_{CELDA}_rural.geojson").write_text(
        json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    # La capa municipal es solo rural; el archivo urbano queda vacio a proposito.
    (destino / f"igac_{CELDA}_urbano.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}, ensure_ascii=False),
        encoding="utf-8")

    print(f"\n  {len(rasgos)} lotes escritos en data/igac/igac_{CELDA}_rural.geojson")
    print("  fuente: Catastro rural de Villavicencio, Alcaldia de Villavicencio")
    # Se anota en el manifiesto de predios_igac. Sin esto la celda figura como pendiente
    # y una nueva corrida del paso de catastro se la pide al servicio nacional, que para
    # Villavicencio devuelve cero, y SOBRESCRIBE estos lotes. Paso de verdad: habia 157
    # lotes en disco y el manifiesto decia cero.
    sys.path[:0] = [str(RAIZ / "predios"), str(RAIZ / "soporte")]
    import predios_igac as pig
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    m = pig.leer_manifiesto()
    for tipo, cuantos in (("rural", len(rasgos)), ("urbano", 0)):
        m.setdefault(CELDA, {})[tipo] = {
            "cuando": ahora, "ok": True, "n": cuantos, "paginas": 1, "truncado": False,
            "corte": pig.CORTE,
            "fuente": "Catastro rural de Villavicencio, Alcaldia de Villavicencio",
            "gestor": "G0038 Municipio de Villavicencio",
        }
    pig.escribir_manifiesto(m)
    print("  anotado en el manifiesto: la celda ya no figura como pendiente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
