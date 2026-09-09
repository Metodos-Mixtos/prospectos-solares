"""
Imagen reciente de Sentinel-2 para un lote: estado del terreno en los últimos días.

Complementa a la foto de alta resolución (Esri, 30-60 cm pero de fecha variable) con la
última escena sin nubes de Sentinel-2 (10 m, pasa cada pocos días). Se busca en el
catálogo STAC abierto de Earth Search (AWS), se comprueba la nubosidad sobre el recuadro
con la máscara SCL y se recorta la composición en color verdadero (TCI) a un JPEG
cuadrado. Caché en data/satelital/sat_s2_lote_<clave>_<fecha>.jpg (+ .json) y bucket.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from math import cos, radians
from pathlib import Path

import numpy as np

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

CACHE = config.PROJECT_ROOT / "data" / "satelital"
STAC = "https://earth-search.aws.element84.com/v1/search"
COLECCION = "sentinel-2-l2a"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
#: Días hacia atrás que se buscan y nubosidad máxima aceptada sobre el recuadro del lote.
DIAS = 120
NUBES_MAX = 0.10
#: Clases SCL que cuentan como nube o sombra (3 sombra, 8 nube media, 9 alta, 10 cirro).
SCL_NUBE = (3, 8, 9, 10)


def escenas(bbox, dias: int = DIAS, limite: int = 12) -> list[dict]:
    """Escenas candidatas, de la más reciente a la más antigua, con poca nube en la escena."""
    import requests
    hasta = date.today()
    desde = hasta - timedelta(days=dias)
    cuerpo = {"collections": [COLECCION], "bbox": list(bbox),
              "datetime": f"{desde.isoformat()}T00:00:00Z/{hasta.isoformat()}T23:59:59Z",
              "query": {"eo:cloud_cover": {"lt": 70}}, "limit": limite,
              "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    r = requests.post(STAC, json=cuerpo, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json().get("features", [])


def _ventana(href: str, bbox):
    """Lee por ventana un COG remoto en el bbox (grados); devuelve (array, transform, crs)."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    with rasterio.open(f"/vsicurl/{href}") as src:
        b = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=5)
        win = from_bounds(*b, transform=src.transform)
        win = win.round_offsets().round_lengths()
        if win.width < 2 or win.height < 2:
            return None, None, None
        arr = src.read(window=win, boundless=True, fill_value=0)
        return arr, src.window_transform(win), src.crs


def _reducir_cache(meta: Path, d: dict) -> dict:
    """
    Deshace en la caché la ampliación que hacía la versión anterior de este módulo.

    Hasta ahora el recorte se estiraba siempre a 700 px, con lo que una escena de 10 m
    sobre un lote de 12 ha (75 px nativos) salía ampliada nueve veces: pesaba de más y
    aparentaba un detalle que el sensor no tiene. Las imágenes ya descargadas se arreglan
    aquí sin volver a pedir nada a la red — la ampliación no añadió información, así que
    reducirla la devuelve a su contenido real — y se anota la resolución verdadera.

    Si algo falla se devuelve la entrada tal cual: una imagen de más está bien, perder
    la escena por un fallo al reescalar no.
    """
    if "px" in d or not d.get("bbox"):
        return d
    try:
        from PIL import Image
        ruta = CACHE / d["src"]
        bbox = d["bbox"]
        ancho_m = (bbox[2] - bbox[0]) * 111320.0 * cos(radians((bbox[1] + bbox[3]) / 2))
        nativo = max(1, int(round(ancho_m / 10.0)))
        with Image.open(ruta) as im:
            ancho = im.width
            if ancho > nativo:
                im.convert("RGB").resize((nativo, nativo), Image.LANCZOS).save(
                    ruta, "JPEG", quality=88)
                ancho = nativo
        d = {**d, "px": ancho, "px_nativos": nativo,
             "m_por_px": round(ancho_m / ancho, 1)}
        meta.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        return d
    return d


def recorte(clave: str, bbox, px: int = 700, forzar: bool = False) -> dict | None:
    """
    JPEG cuadrado de la última escena limpia sobre el bbox. Devuelve {"src", "fecha",
    "nubes", "escena", "px", "px_nativos", "m_por_px"} o None si en DIAS no hubo escena
    con menos de NUBES_MAX de nube.

    ``px`` es un TOPE, no un destino: si la ventana nativa de la escena tiene menos
    píxeles que ``px``, la imagen sale a su tamaño nativo. A 10 m por píxel, pedir más
    es ampliar.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = CACHE / f"sat_s2_lote_{clave}.json"
    if meta.exists() and not forzar:
        d = json.loads(meta.read_text(encoding="utf-8"))
        if d.get("src") and (CACHE / d["src"]).exists():
            return _reducir_cache(meta, d)
        if d.get("sin_escena") and (date.today() - date.fromisoformat(d["consultado"])).days < 7:
            return None
    try:
        items = escenas(bbox)
    except Exception:
        return None
    from PIL import Image
    for it in items:
        a = it.get("assets", {})
        if "visual" not in a or "scl" not in a:
            continue
        try:
            scl, _, _ = _ventana(a["scl"]["href"], bbox)
            if scl is None:
                continue
            # Una escena puede cubrir el recuadro solo en parte (borde de órbita): SCL 0 es
            # sin dato y descalifica igual que la nube.
            sin_dato = float((scl[0] == 0).mean())
            nubes = float(np.isin(scl[0], SCL_NUBE).mean())
            if nubes > NUBES_MAX or sin_dato > 0.05:
                continue
            rgb, _, _ = _ventana(a["visual"]["href"], bbox)
            if rgb is None:
                continue
        except Exception:
            continue
        img = np.moveaxis(rgb[:3], 0, -1).astype(np.uint8)
        # El TCI de Sentinel-2 tiene 10 m por píxel y punto: estirar la ventana leída
        # hasta 700 px no añade un solo detalle, solo peso y una nitidez aparente que
        # el lector interpreta como resolución que no existe. Sobre un lote de 12 ha el
        # recuadro son 75 px nativos, y llevarlos a 700 es ampliar nueve veces. Así que
        # se reduce cuando sobra resolución (Lanczos, más nítido que bilineal) y no se
        # amplía nunca: el navegador ya escala la imagen al ancho de la ficha.
        nativo = int(min(img.shape[0], img.shape[1]))
        lado = max(1, min(px, nativo))
        im = Image.fromarray(img)
        if (im.width, im.height) != (lado, lado):
            im = im.resize((lado, lado), Image.LANCZOS)
        fecha = it["properties"]["datetime"][:10]
        nombre = f"sat_s2_lote_{clave}_{fecha.replace('-', '')}.jpg"
        im.save(CACHE / nombre, "JPEG", quality=88)
        # m_por_px es la resolución real sobre el terreno; se guarda para que el reporte
        # pueda decirla y para poder auditarla sin volver a abrir la imagen.
        ancho_m = (bbox[2] - bbox[0]) * 111320.0 * cos(radians((bbox[1] + bbox[3]) / 2))
        d = {"src": nombre, "fecha": fecha, "nubes": round(nubes, 3), "escena": it.get("id"),
             "bbox": [round(v, 6) for v in bbox], "consultado": date.today().isoformat(),
             "px": lado, "px_nativos": nativo, "m_por_px": round(ancho_m / lado, 1)}
        meta.write_text(json.dumps(d), encoding="utf-8")
        return d
    meta.write_text(json.dumps({"sin_escena": True, "consultado": date.today().isoformat()}), encoding="utf-8")
    return None


if __name__ == "__main__":
    # Prueba rápida: python -m insumos.sentinel minx miny maxx maxy
    b = tuple(float(x) for x in sys.argv[1:5]) if len(sys.argv) >= 5 else (-75.32, 7.99, -75.28, 8.03)
    print(recorte("prueba", b))
