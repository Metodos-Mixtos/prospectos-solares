"""
Imagen satelital de cada grilla, para ver qué hay de verdad en el terreno.

El panel dice que una grilla es 70% pastizal, pero no dice si ese pastizal está partido
en veinte potreros con cerca viva, si hay un caserío en medio o si la vía que figura a
400 metros es una trocha. La foto sí.

Se piden al servicio World Imagery de Esri, que es público y no exige clave. Cada
petición devuelve el recuadro exacto que se le pida, así que se toma el contorno de la
grilla con un margen alrededor para ver el entorno, y el reporte dibuja encima el límite
real de la grilla.

Las imágenes se guardan crudas en data/satelital y se publican en el bucket, porque son
respuesta de un servicio externo y no algo que calculemos nosotros.

Uso:
    .venv\\Scripts\\python.exe satelital.py
    .venv\\Scripts\\python.exe satelital.py --celdas outputs/top_candidates.gpkg --subir
    .venv\\Scripts\\python.exe satelital.py --px 600 --forzar
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
CACHE = config.PROJECT_ROOT / "data" / "satelital"
BUCKET = "prospectos"
PREFIJO = "insumos/satelital"

SERVICIO = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/export")
ATRIBUCION = "Esri World Imagery · Maxar, Earthstar Geographics"

#: Margen alrededor de la grilla, en fracción de su lado. Con un 15% se ve el borde
#: inmediato sin gastar la mitad de los píxeles en terreno que no es la grilla.
MARGEN = 0.15

#: Lado de la imagen en píxeles.
#:
#: Importa más de lo que parece. La fuente tiene 60 cm de resolución nativa, así que lo
#: que se ve depende solo de cuántos píxeles se pidan: a 400 px para una grilla de 5 km
#: con margen salen 21 metros por píxel, que emborrona todo y hace que la foto no se
#: parezca a lo que se ve en Google Earth. A 900 px sobre 6,5 km quedan 7,2 metros por
#: píxel, que ya deja distinguir potreros, cercas vivas, casas y trochas.
#:
#: El servicio admite hasta 4096 px, pero cada imagen entra embebida en el HTML y el
#: peso crece con el cuadrado del lado.
PX = 900


def fecha_imagen(lon: float, lat: float) -> str:
    """
    De cuándo es la foto de ese punto.

    El servicio publica la fecha de captura de cada escena del mosaico, y conviene
    enseñarla: World Imagery mezcla fuentes y fechas, así que dos grillas vecinas pueden
    verse distinto sin que nada esté mal. Sabiendo la fecha, la comparación con Google
    Earth o con cualquier otro visor deja de ser desconcertante.
    """
    par = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": 4326,
           "layers": "all", "tolerance": 2, "returnGeometry": "false",
           "mapExtent": f"{lon-.05},{lat-.05},{lon+.05},{lat+.05}",
           "imageDisplay": "400,400,96", "f": "json"}
    try:
        d = requests.get(SERVICIO.replace("/export", "/identify"),
                         params=par, headers=UA, timeout=60).json()
        for res in d.get("results", []):
            v = res.get("attributes", {}).get("SRC_DATE2")
            if v and str(v).lower() not in ("null", "none", ""):
                return str(v)
    except Exception:
        pass
    return ""


def recuadro(geom, margen: float = MARGEN):
    """Contorno de la grilla ensanchado, en grados."""
    minx, miny, maxx, maxy = geom.bounds
    dx, dy = (maxx - minx) * margen, (maxy - miny) * margen
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def bajar(cell_id: str, bbox, px: int = PX, forzar: bool = False) -> Path | None:
    """Pide el recuadro al servicio y lo cachea. Devuelve la ruta local."""
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"sat_{cell_id}_{px}.jpg"
    if destino.exists() and not forzar and destino.stat().st_size > 2000:
        return destino

    par = {"bbox": "%.6f,%.6f,%.6f,%.6f" % bbox, "bboxSR": 4326, "imageSR": 4326,
           "size": f"{px},{px}", "format": "jpg", "f": "image"}
    try:
        r = requests.get(SERVICIO, params=par, headers=UA, timeout=120)
        r.raise_for_status()
    except Exception as exc:
        print(f"     {cell_id}: error {type(exc).__name__}")
        return None

    # Un error del servicio llega con código 200 y cuerpo JSON, así que no basta el
    # estado: se comprueba que de verdad sea un JPEG por su firma.
    if r.content[:2] != b"\xff\xd8":
        print(f"     {cell_id}: la respuesta no es una imagen")
        return None

    destino.write_bytes(r.content)
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--celdas", help="gpkg o geojson de grillas")
    ap.add_argument("--px", type=int, default=PX)
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--subir", action="store_true")
    a = ap.parse_args(argv)

    import geopandas as gpd

    ruta = Path(a.celdas) if a.celdas else (
        config.PROJECT_ROOT / "outputs" / "reporte" / "grillas_candidatas.gpkg")
    if not ruta.is_absolute():
        ruta = config.PROJECT_ROOT / ruta
    if not ruta.exists():
        ruta = config.TOP_CANDIDATOS_PATH
    g = gpd.read_file(ruta).to_crs(config.CRS_GEOGRAFICO)

    print("=" * 74)
    print("IMAGEN SATELITAL POR GRILLA")
    print("=" * 74)
    print(f"  grillas: {len(g)} de {ruta.name}")
    print(f"  {a.px} x {a.px} px, margen del {MARGEN:.0%} alrededor de la grilla")
    print(f"  fuente: {ATRIBUCION}\n")

    # La fecha se guarda aparte, en un JSON pequeño, para no volver a preguntarla en
    # cada corrida ni tener que abrir las imágenes para saber de cuándo son.
    import json
    ruta_f = CACHE / "fechas.json"
    fechas = json.loads(ruta_f.read_text(encoding="utf-8")) if ruta_f.exists() else {}

    ok = falla = ya = 0
    for i, r in g.iterrows():
        cid = str(r["cell_id"])
        destino = CACHE / f"sat_{cid}_{a.px}.jpg"
        if destino.exists() and not a.forzar and destino.stat().st_size > 2000:
            ya += 1
        else:
            p = bajar(cid, recuadro(r.geometry), a.px, a.forzar)
            if p:
                ok += 1
                if ok % 10 == 0:
                    print(f"     {ok} descargadas...")
            else:
                falla += 1
            time.sleep(0.4)
        if cid not in fechas:
            c = r.geometry.centroid
            fechas[cid] = fecha_imagen(c.x, c.y)
            time.sleep(0.25)

    ruta_f.write_text(json.dumps(fechas, ensure_ascii=False), encoding="utf-8")
    con_fecha = sum(1 for v in fechas.values() if v)
    print(f"  con fecha de captura: {con_fecha} de {len(fechas)}")

    pesos = [f.stat().st_size for f in CACHE.glob(f"sat_*_{a.px}.jpg")]
    print()
    print(f"  descargadas ahora : {ok}")
    print(f"  ya estaban        : {ya}")
    print(f"  fallaron          : {falla}")
    if pesos:
        print(f"  en disco          : {len(pesos)} imágenes, "
              f"{sum(pesos)/1024/1024:.1f} MB  (media {sum(pesos)/len(pesos)/1024:.0f} KB)")
        print(f"  dentro del HTML   : ~{sum(pesos)*1.37/1024/1024:.1f} MB en base64")

    if a.subir:
        import gcs
        n = gcs.subir_carpeta(BUCKET, PREFIJO, CACHE, "sat_*.jpg")
        print(f"\n  subidas al bucket: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
