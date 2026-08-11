"""
Configuración de rutas del proyecto, multiplataforma.

Sustituye las rutas escritas a mano en los notebooks, que apuntaban al Google Drive
montado en el Mac de Daniel y por eso no resuelven en ninguna otra máquina.

Uso en un notebook:

    import config
    gdf = gpd.read_file(config.PANEL_PATH)

Para ver el estado de todas las rutas:

    python config.py

ORDEN DE RESOLUCIÓN
-------------------
Cada raíz se resuelve con esta prioridad:

  1. Variable de entorno  (MMC_GEOINFO, MMC_PROYECTOS)
  2. Archivo paths.local.json en la raíz del proyecto (no versionado)
  3. Autodetección del Google Drive montado (Windows y macOS)
  4. Carpeta local ./data como último recurso

Así el mismo código corre en el Mac de Daniel, en Windows con Google Drive Desktop,
y en una máquina sin Drive que trabaje con copias locales.
"""

from __future__ import annotations

import json
import os
import platform
import string
import sys
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------
# Consola
# --------------------------------------------------------------------------
#
# La consola de Windows sigue usando cp1252, y basta con que un mensaje lleve una
# flecha o un guion largo para que el script muera con UnicodeEncodeError en mitad
# de una subida. En macOS y Linux la salida ya es UTF-8 y esto no hace nada.
#
# Va aquí porque todos los scripts importan config, así que se arregla en un sitio
# en vez de tener que vigilar cada print.

def _consola_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            if flujo is not None and getattr(flujo, "encoding", "").lower() not in (
                    "utf-8", "utf8"):
                flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_consola_utf8()

# --------------------------------------------------------------------------
# Raíz del proyecto y carpetas locales
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TEMP_DIR = PROJECT_ROOT / "temp_files"

_LOCAL_PATHS_FILE = PROJECT_ROOT / "paths.local.json"

# Nombres de las unidades compartidas de Google Drive, según los usa el equipo.
# Google Drive Desktop traduce "Shared drives" a "Unidades compartidas" cuando la
# interfaz está en español, por eso se prueban las dos variantes.
_SHARED_DRIVE_DIRS = ("Shared drives", "Unidades compartidas")
_GEOINFO_REL = ("Data Science", "geoinfo")
_PROYECTOS_REL = ("Projectos Activos",)


def _load_local_overrides() -> dict:
    """Lee paths.local.json si existe. Nunca lanza excepción."""
    if not _LOCAL_PATHS_FILE.exists():
        return {}
    try:
        with open(_LOCAL_PATHS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


_OVERRIDES = _load_local_overrides()


def _drive_roots():
    """Devuelve las posibles raíces de Google Drive según el sistema operativo."""
    system = platform.system()
    roots = []

    if system == "Windows":
        # Google Drive Desktop monta una letra de unidad, por defecto G:
        for letter in string.ascii_uppercase[6:]:  # G en adelante
            roots.append(Path(f"{letter}:/"))
        roots.append(Path.home() / "Google Drive")

    elif system == "Darwin":
        cloud = Path.home() / "Library" / "CloudStorage"
        if cloud.is_dir():
            try:
                roots.extend(p for p in cloud.iterdir() if p.name.startswith("GoogleDrive-"))
            except OSError:
                pass
        roots.append(Path("/Volumes/GoogleDrive"))

    else:  # Linux, montajes manuales
        roots.append(Path.home() / "Google Drive")
        roots.append(Path.home() / "GoogleDrive")

    return roots


def _find_in_drive(*relative_parts) -> Path | None:
    """Busca una subcarpeta dentro de cualquier unidad compartida de Drive."""
    for root in _drive_roots():
        try:
            if not root.is_dir():
                continue
        except OSError:
            # Unidades de red desconectadas pueden lanzar error al consultarlas
            continue
        for shared in _SHARED_DRIVE_DIRS:
            candidate = root.joinpath(shared, *relative_parts)
            try:
                if candidate.is_dir():
                    return candidate
            except OSError:
                continue
    return None


def _resolve(env_var: str, override_key: str, *drive_parts, fallback: Path) -> Path:
    """Resuelve una raíz siguiendo el orden de prioridad documentado arriba."""
    value = os.environ.get(env_var)
    if value:
        return Path(value).expanduser()

    value = _OVERRIDES.get(override_key)
    if value:
        return Path(value).expanduser()

    found = _find_in_drive(*drive_parts)
    if found is not None:
        return found

    return fallback


# --------------------------------------------------------------------------
# Raíces de datos
# --------------------------------------------------------------------------

#: Capas geográficas base compartidas del equipo (antes: ".../Data Science/geoinfo")
GEOINFO = _resolve(
    "MMC_GEOINFO", "geoinfo", *_GEOINFO_REL, fallback=DATA_DIR / "geoinfo"
)

#: Carpeta de proyectos activos (antes: ".../Projectos Activos")
PROYECTOS = _resolve(
    "MMC_PROYECTOS", "proyectos", *_PROYECTOS_REL, fallback=DATA_DIR / "proyectos"
)

#: Carpeta de este proyecto dentro de Proyectos Activos
PANELES_SOLARES = PROYECTOS / "paneles-solares"


# --------------------------------------------------------------------------
# Tolerancia a la normalización Unicode
# --------------------------------------------------------------------------
#
# macOS guarda los nombres de archivo en forma descompuesta (NFD): la "ó" se almacena
# como "o" seguida de un acento combinante. Windows y Linux usan la forma precompuesta
# (NFC), donde la "ó" es un solo carácter. NTFS compara nombres byte a byte, así que un
# archivo creado en el Mac de Daniel con tilde en el nombre NO se encuentra desde Windows
# buscándolo en NFC, aunque en pantalla se vea idéntico.
#
# Esto no es teórico: el propio notebook 1 mezclaba las dos formas en la misma celda.
# resolver() salva la diferencia buscando por nombre normalizado dentro de la carpeta.


def resolver(ruta: Path) -> Path:
    """
    Devuelve la ruta real en disco, tolerando diferencias de normalización Unicode.

    Si la ruta existe tal cual, la devuelve sin más. Si no, busca en la carpeta padre
    un archivo cuyo nombre coincida una vez normalizado. Si tampoco lo encuentra,
    devuelve la ruta original para que el mensaje de error señale lo que se buscaba.
    """
    try:
        if ruta.exists():
            return ruta
        padre = ruta.parent
        if not padre.is_dir():
            return ruta
        objetivo = unicodedata.normalize("NFC", ruta.name)
        for candidato in padre.iterdir():
            if unicodedata.normalize("NFC", candidato.name) == objetivo:
                return candidato
    except OSError:
        pass
    return ruta


# --------------------------------------------------------------------------
# Archivos concretos que usan los notebooks
# --------------------------------------------------------------------------

_ENERGIA = GEOINFO / "Colombia" / "Energia_electrica"

# Cada insumo puede estar en dos sitios. La ruta heredada del Google Drive montado,
# que es la que usaba Daniel, o la caché local que alimenta gcs.py desde los buckets
# de GCP. Se prueban en ese orden y gana la primera que exista.
#
# Ojo con los nombres: en el Drive el archivo se llamaba
#   Colombia-Energia_electrica-Proyectos de generación (XM).geojson
# y en el bucket esa misma jerarquía son carpetas de verdad
#   Colombia/Energia_electrica/Proyectos de generación (XM).geojson

_CACHE_GEOINFO = DATA_DIR / "geoinfo"
_CACHE_PROSPECTOS = DATA_DIR / "prospectos_solares"

#: (ruta_en_drive, bucket, objeto_en_bucket) para cada insumo
_INSUMOS = {
    "panel": (
        PANELES_SOLARES / "fuentes" / "datos" / "Panel-VF-panel_final.gpkg",
        "prospectos_solares",
        "Panel/VF/panel_final.gpkg",
    ),
    "granjas": (
        _ENERGIA / "Colombia-Energia_electrica-Proyectos de generación (XM).geojson",
        "geoinfo",
        "Colombia/Energia_electrica/Proyectos de generación (XM).geojson",
    ),
    "subestaciones": (
        _ENERGIA / "Colombia-Energia_electrica-Subestaciones.geojson",
        "geoinfo",
        "Colombia/Energia_electrica/Subestaciones.geojson",
    ),
}


def _ruta_insumo(clave: str) -> Path:
    """Ruta del insumo: la del Drive si existe, si no la de la caché del bucket."""
    drive, bucket, objeto = _INSUMOS[clave]
    en_drive = resolver(drive)
    if en_drive.exists():
        return en_drive
    return DATA_DIR / bucket / objeto


#: Panel georreferenciado de grillas (21.447 grillas, 43 columnas)
PANEL_PATH = _ruta_insumo("panel")

#: Proyectos de generación solar reportados por XM (232 registros)
GRANJAS_PATH = _ruta_insumo("granjas")

#: Subestaciones del SIN (499 registros)
SUBESTACIONES_PATH = _ruta_insumo("subestaciones")


def asegurar_datos(verbose: bool = True) -> dict[str, Path]:
    """
    Descarga de los buckets los insumos que falten y devuelve {clave: ruta_local}.

    Pensado para llamarse al principio de un notebook:

        import config
        config.asegurar_datos()
        gdf = gpd.read_file(config.PANEL_PATH)

    Si los datos ya están (por el Drive o por una descarga previa) no hace nada.
    """
    import gcs  # import diferido: config no debe exigir google-cloud-storage

    rutas = {}
    for clave in _INSUMOS:
        ruta = _ruta_insumo(clave)
        if ruta.exists():
            rutas[clave] = ruta
            continue
        _drive, bucket, objeto = _INSUMOS[clave]
        rutas[clave] = gcs.obtener(bucket, objeto, verbose=verbose)
    return rutas

# Salidas del notebook 1
SALIDAS = PANELES_SOLARES / "outputs"
BUFFER_SUBESTACIONES_PATH = SALIDAS / "substations_buffer.gpkg"
GRIDS_EN_BUFFER_PATH = SALIDAS / "grids_within_buffer.gpkg"
TOP_CANDIDATOS_PATH = SALIDAS / "top_candidates.gpkg"


# --------------------------------------------------------------------------
# CRS usados en el proyecto
# --------------------------------------------------------------------------

CRS_GEOGRAFICO = "EPSG:4326"      # WGS84, lat/lon. Formato de entrega del IGAC.
CRS_METRICO = "EPSG:32618"        # UTM 18N WGS84. Para distancias, buffers y áreas.
CRS_MAGNA_18N = "EPSG:31818"      # UTM 18N MAGNA-SIRGAS. Catastro colombiano.
CRS_WEB = "EPSG:3857"             # Web Mercator. Solo para mapas de fondo.


# --------------------------------------------------------------------------
# Diagnóstico
# --------------------------------------------------------------------------

# Insumos que hacen falta para correr el notebook 1. Su ausencia sí es un problema.
_INSUMOS_REQUERIDOS = [
    ("Panel de grillas", PANEL_PATH),
    ("Granjas solares XM", GRANJAS_PATH),
    ("Subestaciones", SUBESTACIONES_PATH),
]

# Salidas que produce el propio notebook 1. Que no estén es normal antes de correrlo.
_SALIDAS_ESPERADAS = [
    ("Buffer de subestaciones", BUFFER_SUBESTACIONES_PATH),
    ("Grillas dentro del buffer", GRIDS_EN_BUFFER_PATH),
    ("Top candidatos", TOP_CANDIDATOS_PATH),
]


def estado() -> list[tuple[str, bool, Path]]:
    """Devuelve [(etiqueta, existe, ruta)] para cada insumo requerido."""
    out = []
    for etiqueta, ruta in _INSUMOS_REQUERIDOS:
        try:
            existe = ruta.exists()
        except OSError:
            existe = False
        out.append((etiqueta, existe, ruta))
    return out


def check(verbose: bool = True) -> bool:
    """Imprime el estado de las rutas. Devuelve True si están todas disponibles."""
    filas = estado()
    ancho = max(len(e) for e, _, _ in filas)
    todo_ok = True

    if verbose:
        print("Rutas del proyecto")
        print("=" * 70)
        print(f"Raíz del proyecto : {PROJECT_ROOT}")
        print(f"Sistema           : {platform.system()}")
        if _OVERRIDES:
            print(f"Overrides         : {_LOCAL_PATHS_FILE.name} ({len(_OVERRIDES)} claves)")
        print("-" * 70)

    for etiqueta, existe, ruta in filas:
        if not existe:
            todo_ok = False
        if verbose:
            marca = "OK   " if existe else "FALTA"
            print(f"[{marca}] {etiqueta.ljust(ancho)}  {ruta}")

    if verbose:
        print("-" * 70)
        print("Salidas del notebook 1 (normal que falten si aún no se ha corrido)")
        for etiqueta, ruta in _SALIDAS_ESPERADAS:
            try:
                existe = ruta.exists()
            except OSError:
                existe = False
            print(f"[{'OK   ' if existe else '  -  '}] {etiqueta.ljust(ancho)}  {ruta}")

    if verbose and todo_ok:
        print("-" * 70)
        print("Insumos completos. El notebook 1 se puede correr.")

    if verbose and not todo_ok:
        print("-" * 70)
        print(
            "Faltan datos locales. Opciones, de más a menos recomendable:\n"
            "\n"
            "  1. Traerlos de los buckets del proyecto GCP 'mmc-general', que es donde\n"
            "     viven los insumos. Ver gcs.py:\n"
            "       python gcs.py auth      # cómo autenticarse\n"
            "       python gcs.py ls        # explorar los buckets\n"
            "\n"
            "  2. Copiar los datos a una carpeta local y declararla en paths.local.json:\n"
            '       {"geoinfo": "D:/datos/geoinfo", "proyectos": "D:/datos/proyectos"}\n'
            "\n"
            "  3. Definir las variables de entorno MMC_GEOINFO y MMC_PROYECTOS.\n"
            "\n"
            "  4. Montar Google Drive para escritorio con las unidades compartidas\n"
            "     'Data Science' y 'Projectos Activos'. Es como estaba antes.\n"
            "\n"
            "El notebook 2 (consulta al IGAC) no necesita ninguna de estas rutas,\n"
            "porque descarga los predios directamente del FeatureServer."
        )

    return todo_ok


if __name__ == "__main__":
    check()
