"""
Líneas de transmisión en el entorno de las celdas candidatas, desde OpenStreetMap.

No hay capa de líneas en el bucket del equipo: `geoinfo/Colombia/Energia_electrica`
solo tiene generación y subestaciones. OSM sí las mapea como `power=line`, con el
voltaje cuando está disponible.

Ámbito: todo el país. Una única consulta nacional de `power=line` devuelve 504 en
Overpass, así que Colombia se recorre con una malla de bloques y se unen los resultados
descartando los tramos repetidos por identificador de OSM.

Se probó antes la vía oficial. El servidor ArcGIS de la UPME (geo.upme.gov.co) publica
capas de subestaciones y líneas, pero su certificado TLS no valida y no se puede
consultar sin desactivar la verificación, cosa que no conviene hacer. La otra capa que
aparece en búsquedas, `Red_eléctrica_nacional` en services3.arcgis.com, resulta ser de
Nicaragua, publicada por ENATREL: su extensión va de 11° a 14° de latitud norte.

Uso:
    .venv\\Scripts\\python.exe lineas_transmision.py
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
# La raiz y soporte/ van al path: config y gcs viven en soporte/, y los paquetes
# del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

UA = "prospectos-solares/1.0 (Metodos Mixtos Consultores; prospeccion solar Colombia)"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
CACHE = config.PROJECT_ROOT / "data" / "lineas"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

PAUSA = 3
#: Solo transmisión y subtransmisión. Por debajo de 50 kV es distribución y satura el mapa.
VOLTAJE_MINIMO = 50_000

#: Ventana de Colombia continental, la misma que usa el mapa del reporte.
LON0, LON1 = -79.3, -66.6
LAT0, LAT1 = -4.4, 13.7
#: Malla de descarga. Bloques de unos 3° por lado: más grandes dan 504 en Overpass.
COLUMNAS, FILAS = 4, 6


def malla() -> list[tuple[float, float, float, float]]:
    """Divide el país en bloques (sur, oeste, norte, este) para consultarlo por partes."""
    dw = (LON1 - LON0) / COLUMNAS
    dh = (LAT1 - LAT0) / FILAS
    bloques = []
    for f in range(FILAS):
        for c in range(COLUMNAS):
            w = LON0 + c * dw
            s = LAT0 + f * dh
            bloques.append((s, w, s + dh, w + dw))
    return bloques


def cuartos(b: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    """Parte un bloque en cuatro. Se usa cuando Overpass no puede con él entero."""
    s, w, n, e = b
    mh, mv = (w + e) / 2, (s + n) / 2
    return [(s, w, mv, mh), (s, mh, mv, e), (mv, w, n, mh), (mv, mh, n, e)]


def consultar(bboxes, etiqueta: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / f"lineas_{etiqueta}.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))

    partes = "".join(
        f'way["power"="line"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});'
        for (s, w, n, e) in bboxes
    )
    query = f"[out:json][timeout:180];({partes});out geom;"

    data, fallos = None, []
    for url in ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query},
                              headers={"User-Agent": UA}, timeout=240)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:
            fallos.append(f"{url.split('//')[1].split('/')[0]}: {type(exc).__name__}")
            time.sleep(PAUSA)
    if data is None:
        raise RuntimeError("; ".join(fallos))

    destino.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(PAUSA)
    return data


def _voltaje(tags: dict) -> int | None:
    """OSM guarda el voltaje como texto y a veces con varios valores separados por ';'."""
    v = tags.get("voltage")
    if not v:
        return None
    trozos = [t.strip() for t in str(v).replace(",", ";").split(";") if t.strip()]
    valores = []
    for t in trozos:
        try:
            valores.append(int(float(t)))
        except ValueError:
            continue
    return max(valores) if valores else None


def main() -> int:
    try:
        from . import asegurar
        n = asegurar("lineas_transmision")
        if n:
            print(f"  recuperados {n} bloques desde el bucket")
    except Exception:
        pass

    bloques = malla()

    print("=" * 74)
    print("LÍNEAS DE TRANSMISIÓN  ·  OpenStreetMap, cobertura nacional")
    print("=" * 74)
    print(f"  malla: {COLUMNAS} x {FILAS} = {len(bloques)} bloques")
    print(f"  filtro: tensión de {VOLTAJE_MINIMO // 1000} kV o más, y sin tensión declarada\n")

    vistos, geoms, fallos = set(), [], []

    def acumular(data) -> int:
        nuevos = 0
        for el in data.get("elements", []):
            oid = el.get("id")
            if oid in vistos:
                continue
            kv = _voltaje(el.get("tags", {}))
            if kv is not None and kv < VOLTAJE_MINIMO:
                continue
            coords = [(p["lon"], p["lat"]) for p in (el.get("geometry") or [])]
            if len(coords) < 2:
                continue
            vistos.add(oid)
            geoms.append({"kv": kv, "coords": coords})
            nuevos += 1
        return nuevos

    for num, b in enumerate(bloques, 1):
        print(f"  bloque {num:>2}/{len(bloques)}  ({b[1]:.1f}..{b[3]:.1f}, {b[0]:.1f}..{b[2]:.1f})...",
              end=" ", flush=True)
        try:
            print(f"{acumular(consultar([b], str(num)))} tramos nuevos")
            continue
        except Exception:
            pass

        # Overpass no pudo con el bloque entero: se parte en cuatro y se insiste.
        # Los bloques densos, que son justo los que interesan, son los que fallan.
        print("denso, subdividiendo...", end=" ", flush=True)
        n, malos = 0, 0
        for j, q in enumerate(cuartos(b), 1):
            try:
                n += acumular(consultar([q], f"{num}_{j}"))
            except Exception:
                malos += 1
        if malos == 4:
            fallos.append(num)
            print("sigue fallando")
        else:
            print(f"{n} tramos nuevos"
                  + (f", {malos} de 4 cuartos sin respuesta" if malos else ""))

    if fallos:
        print(f"\n  bloques irrecuperables: {', '.join(map(str, fallos))}")

    if not geoms:
        print("\nNo se obtuvo ninguna línea.")
        return 1

    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SALIDA / "lineas_transmision.json", "w", encoding="utf-8") as fh:
        json.dump(geoms, fh, ensure_ascii=False)

    print()
    print("-" * 74)
    print(f"  tramos únicos : {len(geoms):,}".replace(",", "."))
    con_kv = [x["kv"] for x in geoms if x["kv"]]
    if con_kv:
        import collections
        print("  por tensión (kV):")
        for kv, n in sorted(collections.Counter(con_kv).items(), reverse=True)[:8]:
            print(f"     {kv // 1000:>4} kV : {n}")
    print(f"  sin tensión declarada: {len(geoms) - len(con_kv)}")
    print(f"\n  JSON -> {SALIDA / 'lineas_transmision.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
