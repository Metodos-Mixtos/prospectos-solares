"""
EL HILO CONDUCTOR. Punto de entrada único del proyecto: de las grillas a los entregables.

    .venv\\Scripts\\python.exe ejecutar.py --corrida general --grillas mis_grillas.geojson

QUÉ ES ESTO Y POR QUÉ EXISTE
----------------------------
Hasta ahora el proyecto tenía tres puntos de entrada sueltos y la cadena de lotes se
invocaba módulo a módulo, a mano. Eso ya costó caro: el 25 de agosto de 2026 se lanzó
`predios.lotes` directamente contra el GeoJSON del piloto. El encadenado del piloto
redirige en memoria la constante SALIDA de los módulos que escriben; una invocación
directa no la redirige. Resultado: los lotes del reporte principal quedaron machacados y
hubo que recaracterizarlos. Con un único punto de entrada y los destinos explícitos, ese
error no es que sea improbable: es que no se puede cometer.

Aquí se recibe UN insumo obligatorio, el archivo de grillas, y se corre todo hasta el
visor y el Excel, publicando en el bucket lo que cada paso produce.

EL INSUMO
---------
Un GeoJSON, un GeoPackage o un CSV de celdas, con `cell_id` y geometría. Cualquier
número de celdas, una incluida. Es exactamente el archivo que exporta el reporte de
grillas (`outputs/reporte/grillas_para_predios.geojson`) o el botón "para predios".

Si al archivo le faltan columnas de las que el lote hereda de su celda (recurso solar,
capacidad de barra, clasificación), el paso 1 las completa cruzando por `cell_id` contra
la tabla maestra `outputs/reporte/grillas_candidatas.gpkg`, que se lee y NO se toca. Las
que sigan faltando se dicen por pantalla y quedan escritas en el manifiesto; no se
rellenan con nada inventado.

LOS PASOS
---------
  0  verificar     insumos, credenciales, acceso al bucket y destinos. No escribe nada.
  1  grillas       normaliza el archivo de entrada, completa las columnas heredadas y lo
                   deja en la carpeta de la corrida.
                   -> grillas_para_predios.geojson  (+ copia de la tabla maestra)
  2  catastro      predios.predios_igac baja del catastro público del IGAC los terrenos
                   de cada celda, los repara, deduplica, recorta y mide.
                   -> predios.gpkg, predios.corte
  3  lotes         predios.lotes mide el lote y lo caracteriza. Dentro de este paso, y no
                   como pasos aparte, corren el ENTORNO (predios.entorno: RUNAP,
                   resguardos, consejos comunitarios, páramos, minería, hidrocarburos,
                   inundación), el POT (predios.pot: zonificación rural, clasificación del
                   suelo y datos nacionales del IGAC), el contexto, el cribado jurídico y
                   el valor de referencia. Van juntos a propósito: `predios.lotes` los
                   lanza en paralelo sobre los mismos lotes en memoria y escribe una sola
                   tabla. Separarlos en pasos obligaría a releer y reescribir esa tabla
                   tres veces y a repetir consultas ya hechas. Se pueden repetir sueltos,
                   con `python -m predios.entorno` y `python -m predios.pot`, para
                   refrescar una capa sin rehacer la medición.
                   -> lotes_<perfil>.csv/.geojson, lotes_<perfil>_descartados.csv,
                      lotes.gpkg
  4  registro      predios.matricula_auto: portal de impuesto predial donde exista,
                   Superintendencia donde no, hasta donde alcance el cupo diario gratuito.
                   NO detiene el encadenado. Si falla o se agota el cupo, se dice, se
                   escribe el motivo y se sigue.
                   -> matriculas_<perfil>.csv   (y data/registro/matriculas.csv, caché
                      compartida que NO se redirige)
  5  visor         reporte_predios arma el JSON y el HTML del visor de lotes, con imagen
                   satelital y Sentinel-2 por lote.
                   -> reporte_predios.json, reporte_predios.html
                   -> entregables/<corrida>/reporte_predios.html (+ satelital/)
  6  entregables   el Excel de la corrida: una hoja con las grillas y otra con sus lotes.
                   -> lotes_<perfil>.xlsx
  7  publicar      sube al bucket lo que quede sin publicar y cierra el manifiesto.

Cada paso, al terminar bien, publica lo suyo en
`gs://prospectos-solares-salidas/corridas/<corrida>/`. Qué va a dónde se declara en
`soporte/config.py`, en CONJUNTOS_SALIDA. Con `--sin-bucket` no se publica nada.

DESTINOS: POR QUÉ NO SE PUEDEN PISAR DOS CORRIDAS
-------------------------------------------------
El nombre de la corrida es obligatorio y de él salen los tres destinos:

    outputs/corridas/<corrida>/     todo lo que se calcula
    entregables/<corrida>/          el HTML que se comparte
    gs://prospectos-solares-salidas/corridas/<corrida>/   la copia publicada

`config.destino_corrida` valida el nombre (ni separadores de ruta ni `..`) y rechaza
`outputs/reporte` y la raíz de `entregables/`. Antes de ejecutar un solo paso,
`_redirigir()` reescribe la constante SALIDA de los seis módulos que escriben y ABORTA
si alguna siguiera apuntando al proyecto real. Además, la carpeta de la corrida se
bloquea mientras dura: dos procesos no pueden escribir a la vez en el mismo destino.

Lo que NO se redirige, a propósito, porque son cachés compartidas de insumos y añadir
una celda no altera lo ya descargado: `data/igac`, `dem`, `cobertura`, `osm`,
`satelital`, `entorno`, `pot`, `valor`, `juridico`, `registro`.

REANUDAR Y NO REPETIR LO CARO
-----------------------------
    --desde N --hasta N     corre solo ese tramo. El paso 2 (catastro) y el 3 (lotes)
                            son los caros; con la corrida ya hecha, `--desde 5` rehace
                            el visor en minutos.

SI ALGO FALLA
-------------
Nada queda a medias en silencio. Cada paso se cronometra y su resultado se escribe en
`_corrida.json`: si corrió, cuánto tardó, qué produjo, si se publicó y, si falló, el
motivo con el tipo de excepción. Los pasos críticos detienen el encadenado; el de
matrícula no, porque quedarse sin cupo diario es una situación prevista y no un fallo.
Con `--seguir-tras-fallo` no para ninguno, y el manifiesto guarda la lista de lo que se
saltó.

USO
---
    ejecutar.py --corrida general --grillas outputs/reporte/grillas_para_predios.geojson
    ejecutar.py --corrida general --seco                 # imprime el plan, no ejecuta
    ejecutar.py --corrida general --desde 5              # solo visor y entregables
    ejecutar.py --corrida general --perfil ambos
    ejecutar.py --corrida prueba --grillas g.geojson --sin-satelital --sin-bucket
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

RAIZ = Path(__file__).resolve().parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "soporte"), str(RAIZ / "predios")]

import config  # noqa: E402  (necesita el sys.path de arriba)

#: Los pasos, en orden. (número, clave, etiqueta, crítico)
#: Crítico significa que su fallo detiene el encadenado, porque lo que viene detrás no
#: puede correr sin él. El de matrícula no lo es: sin matrícula el visor se genera igual,
#: con el motivo escrito en la ficha de cada lote.
PASOS = [
    (0, "verificar", "verificar insumos y destinos", True),
    (1, "grillas", "grillas de entrada", True),
    (2, "catastro", "catastro del IGAC", True),
    (3, "lotes", "medición de lotes, entorno y POT", True),
    (4, "matricula", "matrícula inmobiliaria", False),
    (5, "visor", "visor de lotes", True),
    (6, "entregables", "Excel de la corrida", False),
    (7, "publicar", "publicación en el bucket", False),
]
PRIMERO, ULTIMO = PASOS[0][0], PASOS[-1][0]

#: Columnas que el lote hereda de su celda y que ningún módulo de aguas abajo puede
#: rellenar por su cuenta. Las escribe el reporte de grillas; el paso 1 las completa
#: desde la tabla maestra si el archivo de entrada no las trae.
COLUMNAS_HEREDADAS = [
    "ranking", "clasificacion", "indice_aptitud", "restricciones", "pvout",
    "capacidad_at_mw", "capacidad_mt_mw", "sub_nombre_subestacion", "sub_distancia_km",
    "sub_tension_kv", "operador", "municipio", "departamento", "vereda",
    "dane_municipio", "zona", "ha_aptas", "mwp_indicativo", "slope_mean",
]

#: Columnas de la hoja de lotes del Excel, en el orden en que se leen. Las que no existan
#: en la corrida se omiten sin ruido.
COLS_LOTES = [
    "cell_id", "numero_predial_anterior", "matricula_inmobiliaria", "nombre_predio", "clasificacion",
    "area_ha", "cob_pastizal_pct", "cob_cultivo_pct", "cob_bosque_pct", "cob_construido_pct",
    "cob_matorral_pct", "cob_desnudo_pct", "cob_agua_pct", "cob_humedal_pct", "mwp_lote",
    "ancho_util_m", "compacidad", "pendiente_media", "rugosidad_m", "dist_via_km",
    "dist_via_principal_km", "conexion_nombre", "conexion_kv", "conexion_km", "indice_lote",
    "destino", "municipio", "departamento", "area_terreno_catastro_m2", "area_construida_m2",
    "valor_ref_cop_ha", "valor_ref_cop", "valor_confianza", "riesgo_baldio", "veces_uaf",
    "microzona_urt", "estorbos", "gestion", "pot_categoria", "pot_categoria_pct",
    "pot_semaforo", "pot_clasificacion", "ent_mineria_titulos", "ent_runap_ha", "ent_resguardo_ha",
    "ent_consejo_ha", "ent_paramo_ha", "ent_inundacion_ha_max", "ent_humedal", "ctx_linea_km",
    "ctx_poblado", "ctx_poblado_km", "motivo",
]


# --------------------------------------------------------------------------
# Salida por pantalla, con copia al registro de la corrida
# --------------------------------------------------------------------------

class _Doble:
    """Escribe a la consola y al registro de la corrida a la vez."""

    def __init__(self, flujo, archivo):
        self._flujo, self._archivo = flujo, archivo

    def write(self, texto):
        self._flujo.write(texto)
        try:
            self._archivo.write(texto)
        except Exception:
            pass
        return len(texto)

    def flush(self):
        for f in (self._flujo, self._archivo):
            try:
                f.flush()
            except Exception:
                pass

    def __getattr__(self, nombre):
        return getattr(self._flujo, nombre)


def _linea(txt: str = "") -> None:
    print(txt, flush=True)


def _titulo(txt: str) -> None:
    _linea()
    _linea("=" * 78)
    _linea(txt)
    _linea("=" * 78)


# --------------------------------------------------------------------------
# La corrida: destinos, bloqueo y manifiesto
# --------------------------------------------------------------------------

def _nombre_bucket_salidas() -> str:
    """Nombre real del bucket de salidas. Si gcs no se puede importar, el alias sirve."""
    try:
        import gcs
        return gcs.BUCKETS[config.BUCKET_SALIDAS]
    except Exception:
        return config.BUCKET_SALIDAS


class Corrida:
    """
    Una corrida y sus tres destinos. Es el objeto que hace imposible el error de agosto:
    nadie escribe sin pasar por aquí, y de aquí no salen las carpetas del proyecto real.
    """

    def __init__(self, nombre: str, perfiles: list[str], sin_bucket: bool = False):
        self.nombre = config.nombre_corrida(nombre)
        self.perfiles = perfiles
        self.sin_bucket = sin_bucket
        self.destino = config.destino_corrida(self.nombre)
        self.entregables = config.destino_entregables(self.nombre)
        self.prefijo = config.prefijo_corrida(self.nombre)
        self.manifiesto_path = self.destino / "_corrida.json"
        self.lock_path = self.destino / "_corrida.lock"
        self.manifiesto = {
            "corrida": self.nombre,
            "inicio": datetime.now().isoformat(timespec="seconds"),
            "fin": None,
            "perfiles": perfiles,
            "destino": str(self.destino),
            "entregables": str(self.entregables),
            "bucket": None if sin_bucket else f"gs://{_nombre_bucket_salidas()}/{self.prefijo}",
            "grillas_entrada": None,
            "pasos": [],
        }

    # --- bloqueo ----------------------------------------------------------

    def preparar(self) -> None:
        """Crea los destinos. Aparte del constructor, para que --seco no cree carpetas."""
        self.destino.mkdir(parents=True, exist_ok=True)
        self.entregables.mkdir(parents=True, exist_ok=True)

    def bloquear(self, forzar: bool = False) -> None:
        """
        Toma la carpeta de la corrida. Dos procesos no escriben a la vez en el mismo
        destino, que es la otra mitad de lo que pasó en agosto.
        """
        if self.lock_path.exists() and not forzar:
            try:
                d = json.loads(self.lock_path.read_text(encoding="utf-8"))
            except Exception:
                d = {}
            raise SystemExit(
                f"ABORTA: la corrida '{self.nombre}' ya está tomada por el proceso "
                f"{d.get('pid', '?')} desde {d.get('inicio', '?')}.\n"
                f"  Si aquel proceso ya no existe, borra {self.lock_path}\n"
                f"  o repite con --forzar-bloqueo. Elige otro nombre de corrida si lo que\n"
                f"  quieres es una corrida distinta: cada nombre tiene su propio destino.")
        self.lock_path.write_text(json.dumps(
            {"pid": os.getpid(), "inicio": self.manifiesto["inicio"]}), encoding="utf-8")

    def desbloquear(self) -> None:
        try:
            self.lock_path.unlink(missing_ok=True)
        except Exception:
            pass

    # --- manifiesto -------------------------------------------------------

    def anotar(self, registro: dict) -> None:
        self.manifiesto["pasos"] = [p for p in self.manifiesto["pasos"]
                                    if p["paso"] != registro["paso"]] + [registro]
        self.manifiesto["pasos"].sort(key=lambda p: p["paso"])
        self.guardar()

    def guardar(self) -> None:
        try:
            self.manifiesto_path.write_text(
                json.dumps(self.manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            _linea(f"  AVISO: no se pudo escribir el manifiesto ({type(exc).__name__})")

    # --- publicación ------------------------------------------------------

    def publicar(self, paso: int, forzar: bool = False) -> dict:
        """
        Publica en el bucket lo que ese paso produjo, según CONJUNTOS_SALIDA.

        Nunca levanta. Si no hay credenciales, lo dice y lo deja escrito: un paso no se
        da por publicado si no lo está.
        """
        if self.sin_bucket:
            return {"estado": "omitido", "motivo": "--sin-bucket"}
        salidas = config.salidas_del_paso(self.destino, paso)
        if not salidas:
            return {"estado": "nada que publicar"}
        try:
            import gcs
        except Exception as exc:
            return {"estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"}
        parte = gcs.publicar(config.BUCKET_SALIDAS, self.prefijo,
                             [r for _c, r, _d in salidas], forzar=forzar, verbose=False)
        n_ok, n_ya, n_err = (len(parte["subidos"]), len(parte["ya_estaban"]),
                             len(parte["errores"]))
        if n_err:
            _linea(f"  bucket: {n_ok} publicados, {n_ya} ya estaban, {n_err} SIN PUBLICAR")
            for ruta, motivo in parte["errores"][:3]:
                _linea(f"    {Path(ruta).name}: {motivo}")
        else:
            _linea(f"  bucket: {n_ok} publicados, {n_ya} ya estaban  -> "
                   f"{self.manifiesto['bucket']}/")
        return {"estado": "fallo" if n_err else "ok", "subidos": n_ok,
                "ya_estaban": n_ya, "errores": parte["errores"]}

    def publicar_entregables(self, forzar: bool = False) -> dict:
        """El HTML del visor, bajo salidas/<corrida>/entregables/."""
        if self.sin_bucket:
            return {"estado": "omitido", "motivo": "--sin-bucket"}
        archivos = [f for patron in config.PATRONES_ENTREGABLE
                    for f in sorted(self.entregables.glob(patron)) if f.is_file()]
        if not archivos:
            return {"estado": "nada que publicar"}
        try:
            import gcs
        except Exception as exc:
            return {"estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"}
        parte = gcs.publicar(config.BUCKET_SALIDAS, f"{self.prefijo}/entregables",
                             archivos, forzar=forzar, verbose=False)
        return {"estado": "fallo" if parte["errores"] else "ok",
                "subidos": len(parte["subidos"]), "ya_estaban": len(parte["ya_estaban"]),
                "errores": parte["errores"]}


# --------------------------------------------------------------------------
# Separación de rutas
# --------------------------------------------------------------------------

def _redirigir(c: Corrida, verbose: bool = True) -> None:
    """
    Reescribe la constante SALIDA de los módulos que escriben, para que la corrida no
    pise el proyecto real, y aborta si alguna siguiera apuntando allí.

    Qué se redirige y qué escribe cada uno:
      reporte_predios.datos.SALIDA      reporte_predios.json, satelital/
      reporte_predios.html.SALIDA       reporte_predios.html
      reporte_predios.html.ENTREGABLES  la copia que se comparte
      predios_igac.SALIDA               predios.gpkg, predios.corte
      lotes.SALIDA                      lotes_*.csv/geojson, lotes.gpkg
      matricula_auto.SALIDA             matriculas_<perfil>.csv (auditoría)

    Lo que NO se redirige y por qué:
      data/registro/matriculas.csv   caché compartida; lo aprendido de un lote vale para
                                     cualquier corrida, y el visor la lee de ahí.
      data/{igac,dem,cobertura,osm,satelital,entorno,pot,valor,juridico}
                                     insumos compartidos; añadir una celda no altera lo
                                     ya descargado.
      predios.contexto.SALIDA        de outputs/reporte solo LEE lineas_transmision.json.
      insumos.barras.SALIDA          de outputs/reporte solo LEE capacidad_barras.csv.
    """
    import matricula_auto as mau
    import predios_igac as pig
    import lotes as lt
    import reporte_predios.datos as rpd
    import reporte_predios.html as rph

    pig.SALIDA = c.destino
    lt.SALIDA = c.destino
    mau.SALIDA = c.destino
    rpd.SALIDA = c.destino
    rpd.JSON_SALIDA = c.destino / "reporte_predios.json"
    rpd.GRILLAS_DEFECTO = c.destino / "grillas_para_predios.geojson"
    rph.SALIDA = c.destino
    rph.JSON_SALIDA = rpd.JSON_SALIDA
    rph.ENTREGABLES = c.entregables

    prohibidas = {p.resolve() for p in config.DESTINOS_PROHIBIDOS}
    for nombre, valor in (("predios_igac", pig.SALIDA), ("lotes", lt.SALIDA),
                          ("matricula_auto", mau.SALIDA),
                          ("reporte_predios.datos", rpd.SALIDA),
                          ("reporte_predios.html", rph.SALIDA),
                          ("reporte_predios.html.ENTREGABLES", rph.ENTREGABLES)):
        if Path(valor).resolve() in prohibidas:
            raise SystemExit(f"ABORTA: {nombre}.SALIDA apunta al proyecto real ({valor})")

    if verbose:
        _linea(f"  trabajo    -> {c.destino}")
        _linea(f"  entregable -> {c.entregables}")
        _linea(f"  bucket     -> {c.manifiesto['bucket'] or '(no se publica, --sin-bucket)'}")
        _linea(f"  el proyecto real ({config.OUTPUTS_DIR / 'reporte'}) no se toca")


# --------------------------------------------------------------------------
# Paso 0. Verificar
# --------------------------------------------------------------------------

def _claves_env() -> dict[str, bool]:
    """Qué claves hay puestas en .env. NUNCA devuelve ni imprime un valor."""
    env = RAIZ / ".env"
    if not env.exists():
        return {}
    puestas = {}
    for linea in env.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            puestas[k.strip()] = bool(v.strip().strip('"').strip("'"))
    return puestas


def paso_0_verificar(c: Corrida, grillas: Path | None, maestra: Path) -> dict:
    """Comprueba lo que hace falta antes de empezar. No escribe nada."""
    faltan, avisos = [], []

    def _chk(etiqueta, ruta, critico=True):
        ok = Path(ruta).exists()
        _linea(f"  {'ok   ' if ok else ('FALTA' if critico else 'aviso')}  "
               f"{etiqueta:<28} {ruta}")
        if not ok:
            (faltan if critico else avisos).append(etiqueta)
        return ok

    _linea("Insumos")
    if grillas is not None:
        _chk("grillas de entrada", grillas)
    else:
        ya = c.destino / "grillas_para_predios.geojson"
        _chk("grillas de la corrida", ya)
    _chk("tabla maestra de grillas", maestra, critico=False)
    _chk("subestaciones", config.SUBESTACIONES_PATH, critico=False)
    _chk("base veredal", config.DATA_DIR / "geoinfo" / "base_veredas" / "base_veredas.shp",
         critico=False)

    _linea()
    _linea("Credenciales (.env; nunca se imprime ningún valor)")
    claves = _claves_env()
    if not claves:
        _linea("  aviso  no hay .env en la raíz. Cópialo de .env.example y rellénalo.")
        avisos.append("sin .env")
    for clave in ("SNR_USUARIO", "SNR_CLAVE"):
        puesta = claves.get(clave, False)
        _linea(f"  {'ok   ' if puesta else 'aviso'}  {clave:<28} "
               f"{'definida' if puesta else 'sin definir; el paso 4 no consultará la SNR'}")
        if not puesta:
            avisos.append(f"{clave} sin definir")

    _linea()
    _linea("Bucket")
    if c.sin_bucket:
        _linea("  aviso  publicación desactivada con --sin-bucket")
    else:
        try:
            import gcs
            list(gcs.cliente().list_buckets(max_results=1))
            gcs.listar(config.BUCKET_SALIDAS, "insumos/", limite=1)
            _linea(f"  ok     lectura de gs://{gcs.BUCKETS[config.BUCKET_SALIDAS]}. "
                   "La escritura no se prueba aquí: probarla exigiría subir un objeto")
            _linea("         de mentira. Cada paso dice, al publicar, cuántos archivos "
                   "subió y cuántos no.")
        except Exception as exc:
            _linea(f"  aviso  sin acceso al bucket: {type(exc).__name__}: "
                   f"{str(exc)[:120]}")
            _linea("         Corre:  gcloud auth application-default login")
            _linea("         La corrida sigue; lo que produzca queda en disco y se "
                   "publica después con")
            _linea(f"         python soporte/gcs.py sync {config.BUCKET_SALIDAS} {c.prefijo} "
                   f"{c.destino}")
            avisos.append("sin acceso al bucket")

    _linea()
    _linea("Destinos")
    _redirigir(c, verbose=True)

    if faltan:
        raise SystemExit(f"Faltan insumos: {', '.join(faltan)}")
    return {"avisos": avisos}


# --------------------------------------------------------------------------
# Paso 1. Grillas de entrada
# --------------------------------------------------------------------------

def _huella(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()[:16]


def paso_1_grillas(c: Corrida, grillas: Path | None, maestra: Path) -> dict:
    """
    Normaliza el archivo de grillas y lo deja en la carpeta de la corrida.

    Tres cosas, en este orden:
      1. copia la tabla maestra a la corrida, si existe, para que la carpeta se baste a
         sí misma y ningún módulo tenga que ir a leer a outputs/reporte;
      2. lee el archivo de entrada con el mismo lector del proyecto
         (`predios_igac._leer_celdas`), que acepta GPKG, GeoJSON y el CSV del botón
         "para predios", con o sin WKT;
      3. completa por `cell_id` las columnas que el lote hereda de su celda y escribe
         grillas_para_predios.geojson.

    Las columnas que no se puedan completar se dicen y quedan en el manifiesto. No se
    rellenan: un valor inventado ahí viaja hasta la ficha del lote.
    """
    import geopandas as gpd

    salida = c.destino / "grillas_para_predios.geojson"

    # 1. la tabla maestra, a la corrida
    copiadas = []
    for sufijo in (".gpkg", ".geojson", ".csv"):
        origen = maestra.with_suffix(sufijo)
        if origen.exists():
            destino = c.destino / origen.name
            if not destino.exists() or destino.stat().st_mtime < origen.stat().st_mtime:
                shutil.copy2(origen, destino)
            copiadas.append(origen.name)
    _linea(f"  tabla maestra: {', '.join(copiadas) if copiadas else 'no hay; se sigue sin ella'}")

    if grillas is None:
        if not salida.exists():
            raise SystemExit(
                f"No hay --grillas y tampoco existe {salida}. El archivo de grillas es el "
                "único insumo obligatorio del procedimiento.")
        _linea(f"  se reutiliza el archivo ya normalizado de la corrida: {salida.name}")
        g = gpd.read_file(salida)
    else:
        import predios_igac as pig
        g = pig._leer_celdas(Path(grillas))

    if "cell_id" not in g.columns:
        raise SystemExit(f"El archivo de grillas no trae columna cell_id. "
                         f"Columnas: {list(g.columns)[:10]}")
    g["cell_id"] = g["cell_id"].astype(str).str.strip().str.zfill(7)
    n_entrada = len(g)
    g = g.drop_duplicates("cell_id")
    if len(g) != n_entrada:
        _linea(f"  aviso: {n_entrada - len(g)} celdas repetidas en la entrada, se quedó una de cada")

    # 3. completar lo que el lote hereda de su celda
    faltan = [x for x in COLUMNAS_HEREDADAS if x not in g.columns]
    completadas, sin_completar = [], list(faltan)
    ruta_maestra = c.destino / maestra.name
    if faltan and ruta_maestra.exists():
        try:
            m = gpd.read_file(ruta_maestra)
            m["cell_id"] = m["cell_id"].astype(str).str.strip().str.zfill(7)
            cols = [x for x in faltan if x in m.columns]
            if cols:
                g = g.merge(m[["cell_id"] + cols].drop_duplicates("cell_id"),
                            on="cell_id", how="left")
                completadas = cols
                sin_completar = [x for x in faltan if x not in cols]
        except Exception as exc:
            _linea(f"  aviso: no se pudo leer la tabla maestra ({type(exc).__name__})")

    if g.crs is None:
        g = g.set_crs(config.CRS_GEOGRAFICO)
    g = g.to_crs(config.CRS_GEOGRAFICO)
    g.to_file(salida, driver="GeoJSON", COORDINATE_PRECISION=6)

    ids = sorted(g["cell_id"])
    _linea(f"  celdas: {len(g)}   {', '.join(ids[:8])}{' ...' if len(ids) > 8 else ''}")
    if completadas:
        _linea(f"  completadas desde la tabla maestra: {len(completadas)} columnas")
    if sin_completar:
        _linea(f"  AVISO: siguen sin dato {len(sin_completar)} columnas heredadas: "
               f"{', '.join(sin_completar)}")
        _linea("         No se rellenan. Los lotes de esas celdas saldrán sin ese dato.")
    _linea(f"  GeoJSON -> {salida}")

    c.manifiesto["grillas_entrada"] = {
        "origen": str(grillas) if grillas else str(salida),
        "sha256_16": _huella(Path(grillas) if grillas else salida),
        "celdas": len(g),
        "cell_id": ids,
        "columnas_sin_completar": sin_completar,
    }
    return {"celdas": len(g), "columnas_sin_completar": sin_completar}


# --------------------------------------------------------------------------
# Paso 2. Catastro
# --------------------------------------------------------------------------

def paso_2_catastro(c: Corrida, reintentar: bool) -> dict:
    """
    predios.predios_igac sobre las celdas de la corrida: baja los terrenos del catastro
    público del IGAC, los repara, deduplica, recorta a la celda y los mide, y les une la
    ficha alfanumérica (REGISTRO_1 y REGISTRO_2).

    Lo ya descargado se reutiliza de `data/igac`, que es caché compartida entre corridas.
    """
    import predios_igac as pig
    argv = ["--celdas", str(c.destino / "grillas_para_predios.geojson"), "--clase", "todas"]
    if reintentar:
        argv.append("--reintentar")
    codigo = pig.main(argv)
    if codigo:
        raise RuntimeError(f"predios_igac devolvió {codigo}")
    ruta = c.destino / "predios.gpkg"
    if not ruta.exists():
        raise RuntimeError(f"predios_igac no dejó {ruta}")
    return {"predios_gpkg": str(ruta)}


# --------------------------------------------------------------------------
# Paso 3. Lotes (con entorno, POT, contexto, jurídico y valor dentro)
# --------------------------------------------------------------------------

def paso_3_lotes(c: Corrida, ha_minima: float | None) -> dict:
    """
    predios.lotes sobre las celdas de la corrida.

    Mide forma, terreno, Ley 2ª, vía y área útil; y después, por perfil, la conexión, el
    índice del lote, el cribado jurídico, el valor de referencia, el ENTORNO, el POT y el
    contexto. Entorno, POT y contexto son el grueso del tiempo: van a geoservicios
    estatales lote a lote, en tres hilos, y se cachean en data/entorno y data/pot.
    """
    import lotes as lt
    entrada = c.destino / "grillas_para_predios.geojson"
    if not entrada.exists():
        raise RuntimeError(f"No existe {entrada}. Corre antes el paso 1.")
    argv = ["--celdas", str(entrada)]
    if len(c.perfiles) == 1:
        argv += ["--perfil", c.perfiles[0]]
    if ha_minima is not None:
        argv += ["--ha-minima", str(ha_minima)]
    codigo = lt.main(argv)
    if codigo:
        raise RuntimeError(f"lotes devolvió {codigo}")
    hechos = {}
    for perfil in c.perfiles:
        ruta = c.destino / f"lotes_{perfil}.csv"
        if not ruta.exists():
            raise RuntimeError(f"lotes no dejó {ruta.name}")
        import pandas as pd
        hechos[perfil] = len(pd.read_csv(ruta, encoding="utf-8-sig", dtype={"CODIGO": str}))
    return {"lotes_por_perfil": hechos}


# --------------------------------------------------------------------------
# Paso 4. Matrícula inmobiliaria
# --------------------------------------------------------------------------

def paso_4_matricula(c: Corrida, sin_snr: bool, limite_snr: int | None) -> dict:
    """
    predios.matricula_auto sobre los lotes ya caracterizados.

    No detiene el encadenado. `matricula_auto.paso` no levanta nunca: devuelve el resumen
    con los errores dentro. Aquí se recogen, se dicen y se escriben en el manifiesto. Un
    lote que no se llegó a consultar NO se escribe como "sin dato": eso sería afirmar que
    se preguntó y no había.
    """
    import matricula_auto as mau
    partes, cupo_agotado, errores = {}, False, []
    for perfil in c.perfiles:
        _linea(f"  perfil {perfil}")
        r = mau.paso(perfil=perfil, lotes_csv=c.destino / f"lotes_{perfil}.csv",
                     con_snr=not sin_snr, limite_snr=limite_snr)
        partes[perfil] = {"con_matricula": r.get("con_matricula", 0),
                          "cupo_agotado": bool(r.get("cupo_agotado")),
                          "errores": list(r.get("errores") or [])}
        cupo_agotado = cupo_agotado or bool(r.get("cupo_agotado"))
        errores += [f"{perfil}: {e}" for e in (r.get("errores") or [])]
    if cupo_agotado:
        _linea("  Se agotó el cupo diario gratuito de la Superintendencia. Los lotes que")
        _linea("  faltan quedan con el motivo escrito y el procedimiento sigue. Repetir")
        _linea("  mañana con --desde 4 continúa donde esta corrida se detuvo.")
    for e in errores:
        _linea(f"  AVISO: {e}")

    # Certificados de tradición dejados en la bandeja. El certificado no es gratuito y
    # hay que comprarlo, así que el procedimiento no lo pide: lee lo que haya. La
    # matrícula sale del propio folio, de modo que basta con dejar el PDF en la carpeta
    # tal como lo entrega el portal, sin renombrarlo ni decir a qué lote pertenece.
    cert = {}
    try:
        import certificado_ia as cia
        _linea(f"  bandeja de certificados: {cia.ENTRADA}")
        cert = cia.bandeja()
        for nombre, motivo in cert.get("fallidos", []):
            _linea(f"  AVISO: {nombre} no se pudo leer ({motivo})")
    except Exception as exc:
        # Que falle la lectura de un folio no puede detener la corrida: es un añadido a
        # la ficha, no un insumo del que dependa la clasificación.
        cert = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        _linea(f"  AVISO: no se pudo leer la bandeja de certificados ({cert['error']})")

    return {"perfiles": partes, "cupo_agotado": cupo_agotado, "errores": errores,
            "certificados": cert}


# --------------------------------------------------------------------------
# Paso 5. Visor de lotes
# --------------------------------------------------------------------------

def paso_5_visor(c: Corrida, sin_satelital: bool, imagenes: int) -> dict:
    """
    reporte_predios arma el JSON y el HTML del visor y copia el HTML y sus imágenes a
    entregables/<corrida>/.

    El módulo acepta cualquier número de grillas, una incluida.
    """
    import reporte_predios.datos as rpd
    import reporte_predios.html as rph

    argv = ["--grillas", str(c.destino / "grillas_para_predios.geojson"),
            "--imagenes", str(imagenes)]
    if len(c.perfiles) == 1:
        argv += ["--perfil", c.perfiles[0]]
    if sin_satelital:
        argv.append("--sin-satelital")
    codigo = rpd.main(argv)
    if codigo:
        raise RuntimeError(f"reporte_predios.datos devolvió {codigo}")
    codigo = rph.main()
    if codigo:
        raise RuntimeError(f"reporte_predios.html devolvió {codigo}")
    html = c.entregables / "reporte_predios.html"
    if not html.exists():
        raise RuntimeError(f"no se escribió {html}")
    return {"html": str(html), "kb": round(html.stat().st_size / 1024)}


# --------------------------------------------------------------------------
# Paso 6. Excel de la corrida
# --------------------------------------------------------------------------

def paso_6_entregables(c: Corrida) -> dict:
    """
    Un libro por perfil, con dos hojas: "Grillas", las celdas de la corrida con sus
    columnas, y "Lotes", los lotes caracterizados ordenados por área apta descendente
    (área bruta por cobertura apta), que es el orden con el que se leen.
    """
    import geopandas as gpd
    import pandas as pd

    grillas = gpd.read_file(c.destino / "grillas_para_predios.geojson")
    grillas = pd.DataFrame(grillas.drop(columns="geometry", errors="ignore"))

    hechos = {}
    for perfil in c.perfiles:
        origen = c.destino / f"lotes_{perfil}.csv"
        if not origen.exists():
            _linea(f"  aviso: no existe {origen.name}, no se hace su Excel")
            continue
        destino = c.destino / f"lotes_{perfil}.xlsx"
        lotes = pd.read_csv(origen, encoding="utf-8-sig",
                            dtype={"CODIGO": str, "cell_id": str,
                                   "numero_predial_anterior": str})
        # Se ordena por area catastral, que es dato del IGAC. Antes se ordenaba por un
        # area ponderada con coeficientes propios; se retiro el 26 de agosto de 2026 por
        # decision del cliente, que pidio conservar solo lo que se puede citar a una
        # entidad y dejar la cobertura descrita clase a clase.
        if "area_ha" in lotes.columns:
            lotes = lotes.sort_values("area_ha", ascending=False)
        lotes = lotes[[x for x in COLS_LOTES if x in lotes.columns]]

        with pd.ExcelWriter(destino, engine="openpyxl") as xl:
            grillas.to_excel(xl, sheet_name="Grillas", index=False)
            lotes.to_excel(xl, sheet_name="Lotes", index=False)
            for nombre, tabla in (("Grillas", grillas), ("Lotes", lotes)):
                hoja = xl.sheets[nombre]
                for i, col in enumerate(tabla.columns, 1):
                    largo = tabla[col].astype("string").fillna("").str.len().max()
                    largo = 0 if pd.isna(largo) else int(largo)
                    letra = hoja.cell(row=1, column=i).column_letter
                    hoja.column_dimensions[letra].width = min(
                        max(len(str(col)), largo) + 3, 46)
                hoja.freeze_panes = "C2"
        _linea(f"  {perfil}: {len(grillas)} grillas, {len(lotes)} lotes -> {destino.name}")
        hechos[perfil] = {"lotes": len(lotes), "xlsx": str(destino)}
    return {"excel": hechos}


# --------------------------------------------------------------------------
# Paso 7. Publicación y cierre
# --------------------------------------------------------------------------

def paso_7_publicar(c: Corrida, forzar: bool) -> dict:
    """
    Repasa todos los conjuntos declarados en config.CONJUNTOS_SALIDA y sube lo que falte,
    incluidos los entregables y la propia bitácora de la corrida.

    Los pasos ya publican lo suyo al terminar. Este paso existe para dos casos: una
    corrida reanudada con --desde, y una corrida que se hizo sin acceso al bucket y que
    se publica después, cuando las credenciales vuelven.
    """
    if c.sin_bucket:
        _linea("  no se publica nada: --sin-bucket")
        _linea(f"  para publicarlo más tarde:  .venv\\Scripts\\python.exe soporte\\gcs.py "
               f"sync prospectos {c.prefijo} {c.destino}")
        return {"estado": "omitido", "motivo": "--sin-bucket"}

    partes = {}
    for n in range(PRIMERO, ULTIMO):
        salidas = config.salidas_del_paso(c.destino, n)
        if salidas:
            partes[f"paso_{n}"] = c.publicar(n, forzar=forzar)
    partes["entregables"] = c.publicar_entregables(forzar=forzar)
    ok = sum(p.get("subidos", 0) for p in partes.values())
    err = sum(len(p.get("errores") or []) for p in partes.values())
    _linea(f"  total: {ok} archivos publicados, {err} sin publicar")
    return partes


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def _resumen_final(c: Corrida) -> None:
    _titulo("RESUMEN DE LA CORRIDA")
    total = 0.0
    for p in c.manifiesto["pasos"]:
        seg = p.get("segundos") or 0.0
        total += seg
        marca = {"ok": "ok     ", "fallo": "FALLO  ", "saltado": "saltado",
                 "no corrido": "  -    "}.get(p["estado"], p["estado"])
        _linea(f"  {marca} paso {p['paso']}. {p['etiqueta']:<36} {seg:7.0f} s")
        if p.get("motivo"):
            _linea(f"          motivo: {p['motivo']}")
    _linea(f"  {'total':<52} {total:7.0f} s")
    _linea()
    fallos = [p for p in c.manifiesto["pasos"] if p["estado"] == "fallo"]
    if fallos:
        _linea(f"  {len(fallos)} paso(s) fallaron. El detalle está en {c.manifiesto_path}")
    _linea(f"  trabajo    -> {c.destino}")
    _linea(f"  entregable -> {c.entregables / 'reporte_predios.html'}")
    _linea(f"  bucket     -> {c.manifiesto['bucket'] or '(no se publicó, --sin-bucket)'}")
    _linea(f"  manifiesto -> {c.manifiesto_path}")


def _resolver_entrada(ref, carpeta: str):
    """
    Ruta local, objeto del bucket o nombre en la bandeja. El detalle, en soporte/bandeja.py.

    Se importa aquí dentro y no arriba para que quien corra con --sin-bucket no necesite
    google-cloud-storage instalado. Si la referencia es una ruta que existe, ni se toca
    el bucket.
    """
    if ref is None:
        return None
    ruta = Path(ref)
    if ruta.exists():
        return ruta
    import bandeja
    return bandeja.resolver(ref, carpeta=carpeta)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Hilo conductor del proyecto: de las grillas a los entregables.")
    ap.add_argument("--corrida", required=True,
                    help="nombre de la corrida. De él salen los tres destinos: "
                         "outputs/corridas/<n>, entregables/<n> y salidas/<n> en el bucket")
    ap.add_argument("--grillas", default=None,
                    help="GeoJSON, GPKG o CSV de celdas. Único insumo obligatorio; se "
                         "puede omitir al reanudar con --desde 2 o más. Admite una "
                         "ruta local, un objeto gs://, el nombre de un archivo de la "
                         "bandeja del bucket, o la palabra ultima para tomar el más "
                         "reciente que haya en ella")
    ap.add_argument("--maestra", default=None,
                    help="tabla maestra de grillas candidatas de la que se completan las "
                         "columnas que el lote hereda de su celda "
                         "(por defecto outputs/reporte/grillas_candidatas.gpkg, solo se lee)")
    ap.add_argument("--perfil", default="utility",
                    choices=["utility", "distribuida", "ambos"])
    ap.add_argument("--desde", type=int, default=PRIMERO)
    ap.add_argument("--hasta", type=int, default=ULTIMO)
    ap.add_argument("--seco", action="store_true", help="imprime el plan y no ejecuta")
    ap.add_argument("--sin-satelital", action="store_true",
                    help="paso 5 sin descargar imágenes, mucho más rápido")
    ap.add_argument("--imagenes", type=int, default=25,
                    help="imágenes por grilla y perfil en el paso 5")
    ap.add_argument("--ha-minima", type=float, default=None,
                    help="área bruta mínima para caracterizar un lote, en hectáreas")
    ap.add_argument("--sin-snr", action="store_true",
                    help="paso 4 sin consultar la Superintendencia")
    ap.add_argument("--limite-snr", type=int, default=None,
                    help="paso 4: consulta como mucho N lotes en la Superintendencia")
    ap.add_argument("--reintentar-catastro", action="store_true",
                    help="paso 2: reintenta las celdas que fallaron en descargas previas")
    ap.add_argument("--sin-bucket", action="store_true",
                    help="no publica nada; todo queda en disco")
    ap.add_argument("--forzar-publicacion", action="store_true",
                    help="reescribe en el bucket aunque el objeto ya exista")
    ap.add_argument("--forzar-bloqueo", action="store_true",
                    help="toma la corrida aunque haya un bloqueo de otro proceso")
    ap.add_argument("--seguir-tras-fallo", action="store_true",
                    help="no detiene el encadenado aunque falle un paso crítico")
    a = ap.parse_args(argv)

    perfiles = ["utility", "distribuida"] if a.perfil == "ambos" else [a.perfil]
    maestra = (_resolver_entrada(a.maestra, "maestra") if a.maestra
               else config.OUTPUTS_DIR / "reporte" / "grillas_candidatas.gpkg")
    grillas = _resolver_entrada(a.grillas, "grillas")

    try:
        c = Corrida(a.corrida, perfiles, sin_bucket=a.sin_bucket)
    except ValueError as exc:
        raise SystemExit(f"ABORTA: {exc}")

    if a.seco:
        _titulo(f"PLAN DE LA CORRIDA '{c.nombre}'  ·  perfil(es): {', '.join(perfiles)}")
        _linea(f"  grillas    : {grillas or '(las ya normalizadas de la corrida)'}")
        _linea(f"  maestra    : {maestra}{'' if maestra.exists() else '   (no existe)'}")
        _linea(f"  trabajo    -> {c.destino}")
        _linea(f"  entregable -> {c.entregables}")
        _linea(f"  bucket     -> {c.manifiesto['bucket'] or '(no se publica)'}")
        _linea()
        for n, _clave, etiqueta, critico in PASOS:
            dentro = a.desde <= n <= a.hasta
            _linea(f"  {n}. {etiqueta:<38} {'se corre' if dentro else 'se salta':<9}"
                   f"{'' if critico else '(su fallo no detiene el encadenado)'}")
        _linea()
        _linea("  corrida en seco, no se ejecutó nada")
        return 0

    c.preparar()
    c.bloquear(forzar=a.forzar_bloqueo)
    registro = (c.destino / "_corrida.log").open("a", encoding="utf-8")
    salida_real, error_real = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Doble(salida_real, registro), _Doble(error_real, registro)

    codigo = 0
    try:
        _titulo(f"PROSPECTOS SOLARES  ·  corrida '{c.nombre}'  ·  "
                f"{datetime.now():%d-%m-%Y %H:%M}")
        _linea(f"  perfil(es): {', '.join(perfiles)}   pasos: {a.desde} a {a.hasta}")
        c.guardar()

        funciones = {
            0: lambda: paso_0_verificar(c, grillas, maestra),
            1: lambda: paso_1_grillas(c, grillas, maestra),
            2: lambda: paso_2_catastro(c, a.reintentar_catastro),
            3: lambda: paso_3_lotes(c, a.ha_minima),
            4: lambda: paso_4_matricula(c, a.sin_snr, a.limite_snr),
            5: lambda: paso_5_visor(c, a.sin_satelital, a.imagenes),
            6: lambda: paso_6_entregables(c),
            7: lambda: paso_7_publicar(c, a.forzar_publicacion),
        }

        # Si se arranca por la mitad, los módulos siguen necesitando sus destinos.
        if a.desde > 0:
            _redirigir(c, verbose=True)

        parado = False
        for n, clave, etiqueta, critico in PASOS:
            if not (a.desde <= n <= a.hasta):
                c.anotar({"paso": n, "clave": clave, "etiqueta": etiqueta,
                          "estado": "no corrido", "motivo": "fuera del tramo "
                          f"--desde {a.desde} --hasta {a.hasta}"})
                continue
            if parado:
                c.anotar({"paso": n, "clave": clave, "etiqueta": etiqueta,
                          "estado": "saltado", "motivo": "un paso crítico anterior falló"})
                continue

            _titulo(f"PASO {n}. {etiqueta.upper()}")
            t0 = time.time()
            reg = {"paso": n, "clave": clave, "etiqueta": etiqueta, "critico": critico,
                   "inicio": datetime.now().isoformat(timespec="seconds")}
            try:
                reg["detalle"] = funciones[n]() or {}
                reg["estado"] = "ok"
            except SystemExit as exc:
                reg["estado"] = "fallo"
                reg["motivo"] = f"SystemExit: {exc}"
            except BaseException as exc:  # incluye KeyboardInterrupt
                reg["estado"] = "fallo"
                reg["motivo"] = f"{type(exc).__name__}: {exc}"
            reg["segundos"] = round(time.time() - t0, 1)

            if reg["estado"] == "ok" and n < ULTIMO:
                reg["publicacion"] = c.publicar(n, forzar=a.forzar_publicacion)
                if n == 5:
                    reg["publicacion_entregables"] = c.publicar_entregables(
                        forzar=a.forzar_publicacion)
            c.anotar(reg)

            if reg["estado"] == "ok":
                _linea(f"  [paso {n} en {reg['segundos']:.0f} s]")
            else:
                _linea(f"  [paso {n} FALLÓ en {reg['segundos']:.0f} s]")
                _linea(f"  motivo: {reg['motivo']}")
                if critico and not a.seguir_tras_fallo:
                    _linea("  Es un paso crítico: el encadenado para aquí. Lo que viene")
                    _linea("  detrás no puede correr sin él. Arregla el motivo y repite")
                    _linea(f"  con --desde {n}.")
                    parado = True
                    codigo = 1
                else:
                    _linea("  El encadenado sigue. Queda escrito en el manifiesto.")
                    codigo = codigo or 2

        c.manifiesto["fin"] = datetime.now().isoformat(timespec="seconds")
        c.guardar()
        _resumen_final(c)
        # La bitácora se publica siempre al final, corriera lo que corriera y fallara
        # lo que fallara: el registro de una corrida a medias es justo el que hace falta.
        if not a.sin_bucket:
            c.publicar(7, forzar=True)
    finally:
        sys.stdout, sys.stderr = salida_real, error_real
        registro.close()
        c.desbloquear()

    return codigo


if __name__ == "__main__":
    sys.exit(main())
