"""
LA BANDEJA DE ENTRADA DEL BUCKET.

Aquí se resuelve de dónde sale un archivo que el procedimiento necesita y que él no
produce: las candidatas del modelo, las grillas elegidas y los certificados de tradición.

El problema que resuelve es concreto. Hasta ahora, para correr la caracterización de
lotes había que tener el archivo de grillas en el disco de quien corría, en una ruta que
solo existía en esa máquina. Eso ataba el procedimiento a un computador y obligaba a
mandarse ficheros por correo. Con la bandeja, el archivo se sube una vez al bucket y
cualquiera lo lee desde donde esté.

La bandeja vive en el bucket de INSUMOS, porque es lo que entra. Lo que cada corrida
produce va al bucket de salidas y no se mezcla:

    gs://prospectos-solares-insumos/entradas/
        candidatas/     las 100 que salen del modelo (top_candidates.gpkg)
        maestra/        la tabla maestra de grillas candidatas
        grillas/        las elegidas de esas 100, insumo del paso 1
        certificados/   los folios de tradición y libertad, en PDF

Desde la línea de comandos:

    python soporte/bandeja.py ls grillas
    python soporte/bandeja.py subir grillas outputs/reporte/grillas_para_predios.geojson
    python soporte/bandeja.py bajar grillas ultima
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import gcs  # noqa: E402

#: Prefijo de la bandeja dentro del bucket de insumos.
BANDEJA = "entradas"

#: Las cuatro carpetas, con lo que se espera en cada una. El nombre corto es el que se
#: usa en la línea de comandos y en `--grillas`.
CARPETAS = {
    "candidatas": "las 100 grillas que produce el cuaderno 1 (top_candidates.gpkg)",
    "maestra": "la tabla maestra de grillas candidatas, de la que el lote hereda columnas",
    "grillas": "las grillas elegidas para caracterizar lotes",
    "certificados": "certificados de tradición y libertad, en PDF",
}

#: Palabras que piden el archivo más reciente en vez de nombrarlo.
_ULTIMA = {"ultima", "ultimo", "última", "último", "last", "reciente"}

#: Alias del bucket donde vive la bandeja, tal como lo conoce gcs.BUCKETS.
_BUCKET = "prospectos"


def _prefijo(carpeta: str) -> str:
    c = carpeta.strip("/")
    if c not in CARPETAS:
        opciones = ", ".join(CARPETAS)
        raise SystemExit(f"Bandeja desconocida: '{carpeta}'. Las que hay: {opciones}")
    return f"{BANDEJA}/{c}/"


def listar(carpeta: str) -> list[tuple[str, int, object]]:
    """Lo que hay en una bandeja, del más reciente al más antiguo."""
    pref = _prefijo(carpeta)
    nombre = gcs.BUCKETS[_BUCKET]
    filas = [(b.name, b.size or 0, b.updated)
             for b in gcs.cliente().list_blobs(nombre, prefix=pref)
             if not b.name.endswith("/")]
    return sorted(filas, key=lambda t: (t[2] is None, t[2]), reverse=True)


def subir(carpeta: str, origen, nombre: str | None = None, verbose: bool = True) -> str:
    """Deja un archivo en la bandeja y devuelve el objeto resultante."""
    origen = Path(origen)
    if not origen.exists():
        raise SystemExit(f"No existe el archivo que se quiere subir: {origen}")
    objeto = _prefijo(carpeta) + (nombre or origen.name)
    gcs.subir(_BUCKET, objeto, origen, forzar=True, verbose=verbose)
    return objeto


def resolver(referencia, carpeta: str | None = None, verbose: bool = True) -> Path:
    """
    Convierte una referencia en una ruta local, venga del disco o del bucket.

    Quien llama recibe siempre un Path y no se entera de dónde salió el archivo.
    Se admiten cuatro formas:

        ruta local        outputs/reporte/grillas.geojson    se devuelve tal cual
        objeto completo   gs://prospectos-solares-insumos/entradas/grillas/x.geojson
        nombre suelto     x.geojson                          se busca en la bandeja
        el más reciente   ultima                             el último subido ahí

    Las dos últimas necesitan `carpeta`. Cuando algo no se puede resolver se dice qué
    hay en la bandeja, en vez de fallar con un mensaje seco.
    """
    ref = str(referencia).strip()

    if ref.startswith("gs://"):
        resto = ref[5:]
        if "/" not in resto:
            raise SystemExit(f"Referencia incompleta: {ref}. Falta el objeto tras el bucket.")
        bucket, objeto = resto.split("/", 1)
        return gcs.obtener(bucket, objeto, verbose=verbose)

    local = Path(ref)
    if local.exists():
        return local

    if carpeta is None:
        raise SystemExit(
            f"No existe {local} y no se indicó bandeja. Usa una ruta local que exista, "
            f"un objeto gs://, o el nombre de un archivo de la bandeja.")

    hay = listar(carpeta)
    if not hay:
        vacia = [
            f"La bandeja gs://{gcs.BUCKETS[_BUCKET]}/{_prefijo(carpeta)} está vacía.",
            "Sube ahí el archivo con:",
            f"    python soporte/bandeja.py subir {carpeta} <archivo>",
        ]
        raise SystemExit("\n".join(vacia))

    if ref.lower() in _ULTIMA:
        objeto = hay[0][0]
        if verbose:
            print(f"  bandeja {carpeta}: se toma el más reciente, {Path(objeto).name}")
    else:
        iguales = [n for n, _t, _f in hay if Path(n).name == ref]
        if not iguales:
            lineas = [f"En la bandeja '{carpeta}' no hay ningún archivo llamado '{ref}'.",
                      "Lo que hay:"]
            lineas += [f"    {Path(n).name}" for n, _t, _f in hay[:10]]
            raise SystemExit("\n".join(lineas))
        objeto = iguales[0]

    return gcs.obtener(_BUCKET, objeto, verbose=verbose)


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n}"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("Bandejas disponibles:")
        for k, v in CARPETAS.items():
            print(f"  {k:<14} {v}")
        return 0

    orden, resto = argv[0], argv[1:]

    if orden in ("ls", "listar"):
        if not resto:
            for k in CARPETAS:
                filas = listar(k)
                print(f"  {k:<14} {len(filas)} archivo(s)")
            return 0
        filas = listar(resto[0])
        if not filas:
            print(f"  la bandeja '{resto[0]}' está vacía")
            return 0
        for n, t, f in filas:
            cuando = f.strftime("%Y-%m-%d %H:%M") if f else "sin fecha"
            print(f"  {cuando}  {_fmt(t):>10}  {Path(n).name}")
        return 0

    if orden == "subir":
        if len(resto) < 2:
            raise SystemExit("Uso: bandeja.py subir <carpeta> <archivo> [nombre]")
        objeto = subir(resto[0], resto[1], resto[2] if len(resto) > 2 else None)
        print(f"  subido a gs://{gcs.BUCKETS[_BUCKET]}/{objeto}")
        return 0

    if orden == "bajar":
        if len(resto) < 2:
            raise SystemExit("Uso: bandeja.py bajar <carpeta> <nombre|ultima>")
        ruta = resolver(resto[1], carpeta=resto[0])
        print(f"  {ruta}")
        return 0

    raise SystemExit(f"Orden desconocida: {orden}. Hay ls, subir y bajar.")


if __name__ == "__main__":
    raise SystemExit(main())
