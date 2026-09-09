"""
Acceso a los insumos del proyecto en Google Cloud Storage.

Los datos del proyecto viven en el proyecto de GCP `mmc-general`, repartidos en dos
buckets que corresponden a las dos raíces que antes se leían del Google Drive montado:

    geoinfo             capas geográficas base compartidas del equipo
    prospectos_solares  insumos y salidas propios de este proyecto

Este módulo descarga a una caché local (./data) y devuelve rutas de archivo normales,
de modo que los notebooks siguen trabajando con rutas locales y no hay que reescribir
la lógica de lectura.

USO DESDE LA LÍNEA DE COMANDOS
------------------------------

    python gcs.py auth                      # cómo autenticarse
    python gcs.py ls                        # lista los buckets configurados
    python gcs.py ls geoinfo                # lista el contenido de un bucket
    python gcs.py ls geoinfo Colombia/      # lista bajo un prefijo
    python gcs.py get geoinfo ruta/al.geojson
    python gcs.py tree geoinfo              # estructura de carpetas de primer nivel
    python gcs.py put prospectos salidas/general/lotes.gpkg outputs/corridas/general/lotes.gpkg
    python gcs.py sync prospectos salidas/general outputs/corridas/general "*.csv"

USO DESDE UN NOTEBOOK
---------------------

    import gcs
    ruta = gcs.obtener("geoinfo", "Colombia/Energia_electrica/Subestaciones.geojson")
    gdf = gpd.read_file(ruta)

AUTENTICACIÓN
-------------
Se usan las credenciales de aplicación por defecto (ADC). La vía recomendada es iniciar
sesión con tu propia cuenta, sin descargar claves de larga duración:

    gcloud auth application-default login

Si no tienes el CLI de Google Cloud, `python gcs.py auth` explica cómo instalarlo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Proyecto de GCP propio. Antes el trabajo vivía en mmc-general, junto a lo del resto
#: del equipo; el 26 de agosto de 2026 se migró a su propio proyecto para que corra solo
#: y no dependa de los buckets compartidos.
PROYECTO_GCP = "prospectos-solares"

#: Buckets del proyecto. La clave es el alias corto que se usa en el código.
#:
#: `geoinfo` ya no es el bucket compartido del equipo: son las capas base que este
#: procedimiento de verdad usa (base veredal, límite departamental, subestaciones y
#: registro de plantas), copiadas bajo el prefijo geoinfo/ del bucket de insumos. Son
#: 368 MB de los 71 GB que pesaba el original, y así el proyecto no depende de otro.
BUCKETS = {
    "geoinfo": "prospectos-solares-insumos",
    "prospectos": "prospectos-solares-insumos",
    "salidas": "prospectos-solares-salidas",
}

#: Prefijo que se antepone al pedir una capa del antiguo bucket compartido, porque
#: dentro del bucket de insumos vive bajo geoinfo/.
PREFIJO = {"geoinfo": "geoinfo/"}

#: Raíz del proyecto: la carpeta que contiene a soporte/, no la de este archivo.
#: Estaba mal apuntada y por eso la caché de este módulo crecía en soporte/data,
#: mientras config.py, insumos/ y el resto del proyecto buscaban en data/. Dos cachés
#: para lo mismo, y la de soporte/ invisible para todo lo demás.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

#: Compatibilidad con el nombre anterior.
PROJECT_ROOT = RAIZ_PROYECTO

#: Caché local. Replica la estructura del bucket bajo data/<bucket>/...
CACHE_DIR = RAIZ_PROYECTO / "data"


# --------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------

_cliente = None


class SinCredenciales(RuntimeError):
    """Se lanza cuando no hay credenciales de GCP configuradas."""


def _mensaje_auth() -> str:
    return (
        "No hay credenciales de Google Cloud configuradas.\n"
        "\n"
        "Opción recomendada, iniciar sesión con tu cuenta:\n"
        "\n"
        "  1. Instala el CLI de Google Cloud si no lo tienes:\n"
        "       winget install Google.CloudSDK\n"
        "     o descárgalo de https://cloud.google.com/sdk/docs/install\n"
        "\n"
        "  2. Inicia sesión. Se abre el navegador y apruebas con tu cuenta:\n"
        "       gcloud auth application-default login\n"
        "\n"
        "  3. Fija el proyecto por defecto:\n"
        f"       gcloud config set project {PROYECTO_GCP}\n"
        "\n"
        "Alternativa, si el equipo usa una cuenta de servicio, apunta la variable\n"
        "GOOGLE_APPLICATION_CREDENTIALS al archivo JSON de la clave. Evítalo si puedes,\n"
        "una clave descargada es una credencial de larga duración que hay que custodiar."
    )


def cliente():
    """Devuelve un cliente de Cloud Storage, reutilizándolo entre llamadas."""
    global _cliente
    if _cliente is not None:
        return _cliente

    try:
        from google.cloud import storage
    except ImportError as exc:
        raise SinCredenciales(
            "Falta la librería google-cloud-storage.\n"
            "  pip install google-cloud-storage"
        ) from exc

    try:
        _cliente = storage.Client(project=PROYECTO_GCP)
    except Exception as exc:
        raise SinCredenciales(f"{_mensaje_auth()}\n\nDetalle: {type(exc).__name__}: {exc}") from exc

    return _cliente


def _nombre_bucket(alias_o_nombre: str) -> str:
    """Acepta tanto el alias corto como el nombre real del bucket."""
    return BUCKETS.get(alias_o_nombre, alias_o_nombre)


# --------------------------------------------------------------------------
# Exploración
# --------------------------------------------------------------------------


def listar(bucket: str, prefijo: str = "", limite: int = 200) -> list[tuple[str, int]]:
    """Devuelve [(nombre_objeto, tamaño_bytes)] bajo un prefijo."""
    b = _nombre_bucket(bucket)
    blobs = cliente().list_blobs(b, prefix=prefijo or None, max_results=limite)
    return [(blob.name, blob.size or 0) for blob in blobs]


def carpetas(bucket: str, prefijo: str = "") -> list[str]:
    """Devuelve las 'carpetas' inmediatas bajo un prefijo, usando el delimitador /."""
    b = _nombre_bucket(bucket)
    it = cliente().list_blobs(b, prefix=prefijo or None, delimiter="/")
    list(it)  # hay que agotar el iterador para que se pueblen los prefijos
    return sorted(it.prefixes)


# --------------------------------------------------------------------------
# Descarga con caché
# --------------------------------------------------------------------------


def _fmt(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024.0
    return f"{n:.1f} GB"


def obtener(bucket: str, objeto: str, forzar: bool = False, verbose: bool = True) -> Path:
    """
    Descarga un objeto a la caché local y devuelve su ruta.

    Si ya está descargado y el tamaño coincide con el del bucket, no lo vuelve a bajar.
    Con forzar=True se descarga siempre.
    """
    b = _nombre_bucket(bucket)
    # Las capas que antes vivían en el bucket compartido ahora cuelgan de geoinfo/ dentro
    # del bucket de insumos. El prefijo se pone aquí para que las llamadas del resto del
    # proyecto sigan escritas igual y la migración no obligue a tocarlas una a una.
    objeto_real = PREFIJO.get(bucket, "") + objeto
    # La caché local conserva la ruta SIN prefijo, para que lo ya descargado siga valiendo
    # y el resto del código lo siga encontrando donde lo busca.
    destino = CACHE_DIR / bucket / objeto
    blob = cliente().bucket(b).blob(objeto_real)

    if not forzar and destino.exists():
        try:
            blob.reload()
            if blob.size is not None and destino.stat().st_size == blob.size:
                return destino
        except Exception:
            # Si no se puede consultar el remoto, se confía en la copia local
            return destino

    if not blob.exists():
        raise FileNotFoundError(f"gs://{b}/{objeto} no existe")

    destino.parent.mkdir(parents=True, exist_ok=True)
    if verbose:
        blob.reload()
        print(f"Descargando gs://{b}/{objeto}  ({_fmt(blob.size or 0)})")

    # Se escribe a un temporal y se renombra, para no dejar archivos a medias
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    blob.download_to_filename(str(tmp))
    tmp.replace(destino)
    return destino


def sincronizar(bucket: str, prefijo: str = "", verbose: bool = True) -> list[Path]:
    """Descarga todos los objetos bajo un prefijo. Devuelve las rutas locales."""
    objetos = listar(bucket, prefijo, limite=10_000)
    rutas = []
    for nombre, _tam in objetos:
        if nombre.endswith("/"):  # marcador de carpeta
            continue
        rutas.append(obtener(bucket, nombre, verbose=verbose))
    return rutas


# --------------------------------------------------------------------------
# Subida
# --------------------------------------------------------------------------


def existe(bucket: str, objeto: str) -> bool:
    """Si el objeto está en el bucket. Nunca lanza por falta de permisos de lectura."""
    try:
        return cliente().bucket(_nombre_bucket(bucket)).blob(objeto).exists()
    except Exception:
        return False


def subir(bucket: str, objeto: str, origen: Path, forzar: bool = False,
          verbose: bool = True) -> bool:
    """
    Publica un archivo local en el bucket. Devuelve True si lo subió.

    Sin forzar respeta lo que ya esté: si el objeto existe con el mismo tamaño no lo
    vuelve a subir. Eso evita reescribir insumos compartidos por accidente, que en un
    bucket de equipo es más fácil de lo que parece.
    """
    b = _nombre_bucket(bucket)
    origen = Path(origen)
    if not origen.exists():
        raise FileNotFoundError(origen)

    blob = cliente().bucket(b).blob(objeto)
    if not forzar:
        try:
            if blob.exists():
                blob.reload()
                if blob.size == origen.stat().st_size:
                    if verbose:
                        print(f"  = ya está  gs://{b}/{objeto}")
                    return False
        except Exception:
            pass

    if verbose:
        # Sin caracteres fuera de ASCII: la consola de Windows usa cp1252 por defecto
        # y una flecha basta para tumbar la subida entera con UnicodeEncodeError.
        print(f"  subiendo gs://{b}/{objeto}  ({_fmt(origen.stat().st_size)})")
    blob.upload_from_filename(str(origen))
    return True


def borrar(bucket: str, objeto: str, verbose: bool = True) -> bool:
    """Elimina un objeto del bucket. Devuelve True si existía y se borró."""
    b = _nombre_bucket(bucket)
    blob = cliente().bucket(b).blob(objeto)
    if not blob.exists():
        return False
    blob.delete()
    if verbose:
        print(f"  × borrado gs://{b}/{objeto}")
    return True


def borrar_prefijo(bucket: str, prefijo: str, verbose: bool = True) -> int:
    """Elimina todo lo que cuelgue de un prefijo. Devuelve cuántos objetos borró."""
    b = _nombre_bucket(bucket)
    n = 0
    for blob in cliente().list_blobs(b, prefix=prefijo):
        blob.delete()
        n += 1
        if verbose:
            print(f"  × borrado gs://{b}/{blob.name}")
    return n


def publicar(bucket: str, prefijo: str, archivos, forzar: bool = False,
             verbose: bool = True) -> dict:
    """
    Publica una lista concreta de archivos bajo un prefijo y devuelve el parte.

    A diferencia de `subir_carpeta`, que barre una carpeta con un patrón, aquí se dice
    exactamente qué se sube. Es lo que necesita el hilo conductor: cada paso conoce sus
    propias salidas y publica esas, no lo que se encuentre al lado.

    Nunca lanza. Si no hay credenciales o el bucket rechaza un objeto, lo deja escrito en
    `errores` y sigue con el resto. Un paso no se da por publicado si no lo está: el
    parte que devuelve es lo que acaba en el manifiesto de la corrida.

        {"subidos": [gs://...], "ya_estaban": [...], "errores": [(ruta, motivo)]}
    """
    parte = {"subidos": [], "ya_estaban": [], "errores": []}
    b = _nombre_bucket(bucket)
    for f in archivos:
        f = Path(f)
        objeto = f"{prefijo.rstrip('/')}/{f.name}"
        try:
            if subir(bucket, objeto, f, forzar=forzar, verbose=verbose):
                parte["subidos"].append(f"gs://{b}/{objeto}")
            else:
                parte["ya_estaban"].append(f"gs://{b}/{objeto}")
        except Exception as exc:
            parte["errores"].append((str(f), f"{type(exc).__name__}: {exc}"))
            if verbose:
                print(f"  AVISO sin publicar {f.name}: {type(exc).__name__}: {exc}")
    return parte


def subir_carpeta(bucket: str, prefijo: str, carpeta: Path, patron: str = "*",
                  forzar: bool = False, verbose: bool = True) -> int:
    """Sube el contenido de una carpeta bajo un prefijo. Devuelve cuántos subió."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return 0
    n = 0
    for f in sorted(carpeta.glob(patron)):
        if not f.is_file():
            continue
        destino = f"{prefijo.rstrip('/')}/{f.name}"
        if subir(bucket, destino, f, forzar=forzar, verbose=verbose):
            n += 1
    return n


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_auth() -> int:
    print(_mensaje_auth())
    print()
    try:
        c = cliente()
        list(c.list_buckets(max_results=1))
    except SinCredenciales as exc:
        print("-" * 70)
        print("Estado actual: SIN ACCESO")
        return 1
    except Exception as exc:
        print("-" * 70)
        print(f"Estado actual: ERROR  {type(exc).__name__}: {exc}")
        return 1
    print("-" * 70)
    print("Estado actual: CON ACCESO. Ya puedes usar `python gcs.py ls`.")
    return 0


def _cmd_ls(args) -> int:
    if not args:
        print(f"Buckets configurados (proyecto {PROYECTO_GCP})")
        print("-" * 70)
        for alias, nombre in BUCKETS.items():
            print(f"  {alias:<12} gs://{nombre}")
        print()
        print("Para ver el contenido:  python gcs.py ls <bucket> [prefijo]")
        return 0

    bucket = args[0]
    prefijo = args[1] if len(args) > 1 else ""
    objetos = listar(bucket, prefijo)
    if not objetos:
        print(f"Sin objetos en gs://{_nombre_bucket(bucket)}/{prefijo}")
        return 0

    total = 0
    for nombre, tam in objetos:
        total += tam
        print(f"  {_fmt(tam):>10}  {nombre}")
    print("-" * 70)
    print(f"  {len(objetos)} objetos, {_fmt(total)}")
    return 0


def _cmd_tree(args) -> int:
    if not args:
        print("Uso: python gcs.py tree <bucket> [prefijo]")
        return 2
    bucket, prefijo = args[0], (args[1] if len(args) > 1 else "")
    subs = carpetas(bucket, prefijo)
    print(f"gs://{_nombre_bucket(bucket)}/{prefijo}")
    if not subs:
        print("  (sin subcarpetas)")
    for s in subs:
        print(f"  {s}")
    sueltos = [n for n, _ in listar(bucket, prefijo, limite=50) if "/" not in n[len(prefijo):]]
    for s in sueltos:
        print(f"  {s}  (archivo)")
    return 0


def _cmd_get(args) -> int:
    if len(args) < 2:
        print("Uso: python gcs.py get <bucket> <objeto>")
        return 2
    ruta = obtener(args[0], args[1])
    print(f"Local: {ruta}")
    return 0


def _cmd_put(args) -> int:
    if len(args) < 3:
        print("Uso: python gcs.py put <bucket> <objeto> <archivo_local> [--forzar]")
        return 2
    subido = subir(args[0], args[1], Path(args[2]), forzar="--forzar" in args)
    print("subido" if subido else "ya estaba, no se reescribe (usa --forzar)")
    return 0


def _cmd_sync(args) -> int:
    if len(args) < 3:
        print("Uso: python gcs.py sync <bucket> <prefijo> <carpeta> [patron] [--forzar]")
        return 2
    patron = args[3] if len(args) > 3 and not args[3].startswith("--") else "*"
    n = subir_carpeta(args[0], args[1], Path(args[2]), patron, forzar="--forzar" in args)
    print(f"subidos {n} archivos")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd, args = argv[0], argv[1:]
    acciones = {"auth": _cmd_auth, "ls": _cmd_ls, "tree": _cmd_tree, "get": _cmd_get,
                "put": _cmd_put, "sync": _cmd_sync}

    if cmd not in acciones:
        print(f"Comando desconocido: {cmd}")
        print("Comandos: auth, ls, tree, get, put, sync")
        return 2

    try:
        return acciones[cmd]() if cmd == "auth" else acciones[cmd](args)
    except SinCredenciales as exc:
        print(exc)
        return 1
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
