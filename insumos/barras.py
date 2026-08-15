"""
Capacidad en barras: cuántos megavatios admite todavía el punto de conexión.

QUÉ ES Y POR QUÉ IMPORTA
------------------------
Sabemos a qué subestación se conectaría cada celda, con qué tensión y con qué
configuración de barras. Falta cuántos megavatios acepta ese nodo, que es el dato que
decide si un proyecto se puede conectar o no.

La UPME lo calcula con el Modelo de Asignación de Capacidad para Conexión (MACC),
adoptado por la Circular 057 de 2022, y lo publica por ciclo de asignación como anexo
de circular, no como servicio consultable. Del ciclo 2023-2024 salieron catorce
informes, uno por subárea operativa, publicados por la Circular UPME 077 de 2024: para
cada barra del STN y del STR, la capacidad en MW año por año del horizonte 2024-2037,
con el escenario crítico y el elemento que la limita.

Este módulo los descarga y los lee. Son PDF de varios cientos de páginas, pero traen
capa de texto y las tablas se dejan parsear.

    python capacidad_barras.py descargar   # trae los 14 informes a data/barras/upme
    python capacidad_barras.py extraer     # los lee y escribe el CSV de data/barras
    python capacidad_barras.py cargar      # cruza lo que haya con las candidatas
    python capacidad_barras.py estado      # lo mismo, es un alias

QUÉ MIDE, EXACTAMENTE
---------------------
Capacidad **por barra**: cuánta generación admite el nodo según los límites de red,
antes de descontar lo que se haya asignado después en el propio ciclo. Es el techo
físico del punto de conexión, no el cupo libre a día de hoy. Para descartar nodos
saturados y ordenar candidatas sirve; para comprometer un punto de conexión hay que
confirmarlo con el operador de red.

El régimen cambió: la Resolución CREG 101 094 de 2025 y la UPME 358 de 2026 movieron
esta información al "Repositorio de Transportadores" de la Ventanilla Única, que exige
registro. Mientras eso siga cerrado, el ciclo 2023-2024 es el último dato abierto.

CARGA MANUAL
------------
Si aparece una fuente mejor, `cargar` recoge cualquier CSV que se deje en data/barras/
con estas columnas, y da igual de dónde salga:

    subestacion;capacidad_disponible_mw;capacidad_asignada_mw;ciclo;fuente
    Caucasia 110 kV;12,5;48,0;2026-2;Circular UPME 000052 de 2026

Solo 'subestacion' y 'capacidad_disponible_mw' son obligatorias, y los decimales van
con coma. El nombre se cruza contra el de la capa de subestaciones del SIN, tolerando
mayúsculas, tildes y espacios.

    python capacidad_barras.py plantilla   # genera un CSV de ejemplo para rellenar
"""

from __future__ import annotations

import argparse
import datetime
import logging
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# La raiz y soporte/ van al path: config y gcs viven en soporte/, y los paquetes
# del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

CARPETA = config.PROJECT_ROOT / "data" / "barras"
CARPETA_PDF = CARPETA / "upme"
SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
DESTINO = SALIDA / "capacidad_barras.csv"

OBLIGATORIAS = ["subestacion", "capacidad_disponible_mw"]
OPCIONALES = ["capacidad_asignada_mw", "ciclo", "fuente", "operador", "tension_kv"]

# --------------------------------------------------------------------------
# Los informes de capacidad por barra de la UPME
# --------------------------------------------------------------------------

BASE_UPME = ("https://docs.upme.gov.co/ServicioCiudadano/Documents"
             "/Informes%20Asignaci%C3%B3n%20Final%20por%20Areas/2023_2024")

CICLO = "2023-2024"
FUENTE = "UPME, informe de capacidad por barra del ciclo 2023-2024 (Circular 077 de 2024)"

#: Un informe por subárea operativa. El sufijo _2 es la revisión publicada tras los
#: comentarios de los transportadores, que es la que vale.
INFORMES = {
    "Antioquia": "1_Informe_cap_barra_Antioquia_2",
    "Arauca": "2_Informe_cap_barra_Arauca_2",
    "Atlántico": "3_Informe_cap_barra_Atlantico_2",
    "Bolívar": "4_Informe_cap_barra_Bolivar_2",
    "Boyacá-Casanare": "5_Informe_cap_barra_Boyaca-Casanare_2",
    "Caldas-Quindío-Risaralda": "6_Informe_cap_barra_CQR_2",
    "Cauca-Nariño": "7_Informe_cap_barra_Cauca-Narino_2",
    "Córdoba-Sucre": "8_Informe_cap_barra_Cordoba-Sucre_2",
    "Guajira-Cesar-Magdalena": "9_Informe_cap_barra_Guajira-Cesar-Magdalena_2",
    "Huila-Tolima": "10_Informe_cap_barra_Huila-Tolima_2",
    "Norte de Santander": "11_Informe_cap_barra_Norte_de_Santander_2",
    "Oriental": "12_Informe_cap_barra_Oriental_2",
    "Santander": "13_Informe_cap_barra_Santander_2",
    "Valle": "14_Informe_cap_barra_Valle_2",
}

#: Cabecera de cada tabla, que es lo que delimita el bloque de una barra.
_MARCADOR = re.compile(r"Datos de capacidad por barra resultante de\s+(.+?)\s+para cada a")
#: Una fila de la tabla: año, capacidad y escenario crítico. Exigir el escenario evita
#: confundir la fila con cualquier otra pareja de número y año del cuerpo del informe.
_FILA = re.compile(r"(20\d{2})\s+(-?\d+(?:[.,]\d+)?)\s+(G\d)\s*-\s*(Min|Med|Max)")

#: Diferencias de nomenclatura entre la capa de subestaciones del SIN y los informes.
#: Comprobadas una a una contra el departamento y el municipio de la capa, porque hay
#: homónimas: "San Marcos" es la de Sucre a 110 kV y la de Yumbo a 115, 220 y 500.
ALIAS = {
    "san marcos -cesar": "san marcos",
    "planeta rica": "planeta",
    "sabana torres": "sabana de torres",
    "sierraflor": "sierra flor",
}


def normalizar(s: str) -> str:
    """Clave de cruce: sin tildes, sin dobles espacios, en minúscula."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(
        serie.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce")


def _partir(nombre: str) -> tuple[str, float | None]:
    """Separa 'Caucasia 110 kV' en ('caucasia', 110.0). La UPME escribe '34,5'."""
    s = normalizar(nombre)
    s = re.sub(r"\bk\s*v\b", " ", s)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = " ".join(s.split())
    m = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)$", s)
    if not m:
        return s, None
    return m.group(1).strip(), float(m.group(2))


def _clase(kv: float | None) -> float | None:
    """220 y 230 kV son la misma barra con dos nombres según quién la escriba."""
    return 220.0 if kv == 230.0 else kv


# --------------------------------------------------------------------------
# Descarga de los informes
# --------------------------------------------------------------------------

def descargar(forzar: bool = False, verbose: bool = True) -> list[Path]:
    """
    Trae los catorce informes a data/barras/upme.

    Son unos 100 MB en total. Se comprueba el tamaño contra el Content-Length porque
    al menos uno de ellos llegó truncado en la primera pasada y un PDF a medias no
    falla al descargarse, falla al leerse.
    """
    import requests

    CARPETA_PDF.mkdir(parents=True, exist_ok=True)
    ses = requests.Session()
    ses.headers.update({"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"})

    salidas = []
    for subarea, stem in INFORMES.items():
        url = f"{BASE_UPME}/{stem}.pdf"
        destino = CARPETA_PDF / f"{stem}.pdf"

        esperado = None
        try:
            cabecera = ses.head(url, timeout=60, allow_redirects=True)
            esperado = int(cabecera.headers.get("Content-Length") or 0) or None
        except Exception:
            pass

        completo = destino.exists() and (esperado is None or destino.stat().st_size == esperado)
        if completo and not forzar:
            if verbose:
                print(f"  {subarea:26s} ya está ({destino.stat().st_size / 1e6:.1f} MB)")
            salidas.append(destino)
            continue

        for intento in (1, 2, 3):
            try:
                r = ses.get(url, timeout=300, stream=True)
                r.raise_for_status()
                with open(destino, "wb") as fh:
                    for trozo in r.iter_content(1 << 16):
                        fh.write(trozo)
            except Exception as exc:
                if verbose:
                    print(f"  {subarea:26s} intento {intento} falló ({type(exc).__name__})")
                continue
            if esperado is None or destino.stat().st_size == esperado:
                break
            if verbose:
                print(f"  {subarea:26s} intento {intento} llegó incompleto")
        else:
            print(f"  aviso: {subarea} no se pudo descargar entero")
            continue

        if verbose:
            print(f"  {subarea:26s} {destino.stat().st_size / 1e6:5.1f} MB")
        salidas.append(destino)

    return salidas


# --------------------------------------------------------------------------
# Lectura de los informes
# --------------------------------------------------------------------------

def barras_upme(verbose: bool = True) -> pd.DataFrame:
    """Todas las barras de los informes, una fila por barra y año del horizonte."""
    import pypdf

    logging.getLogger("pypdf").setLevel(logging.ERROR)

    filas = []
    for subarea, stem in INFORMES.items():
        pdf = CARPETA_PDF / f"{stem}.pdf"
        if not pdf.exists():
            if verbose:
                print(f"  falta {pdf.name}")
            continue
        try:
            lector = pypdf.PdfReader(str(pdf))
            texto = "\n".join((p.extract_text() or "") for p in lector.pages)
        except Exception as exc:
            print(f"  aviso: {pdf.name} no se pudo leer ({type(exc).__name__}); "
                  f"vuelve a bajarlo con 'descargar --forzar'")
            continue

        marcas = list(_MARCADOR.finditer(texto))
        for i, m in enumerate(marcas):
            fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
            barra = m.group(1).strip()
            for anio, mw, gen, dem in _FILA.findall(texto[m.end():fin]):
                filas.append({"subarea": subarea, "barra": barra, "anio": int(anio),
                              "mw": float(mw.replace(",", ".")), "escenario": f"{gen}-{dem}"})
        if verbose:
            print(f"  {subarea:26s} {len(marcas):4d} barras")

    return pd.DataFrame(filas)


def extraer(anio: int | None = None, verbose: bool = True) -> pd.DataFrame:
    """
    Empareja las barras de los informes con la capa de subestaciones del SIN y deja
    el CSV que recoge `cargar`.

    El emparejamiento es por nombre y tensión, con tres concesiones a la realidad de
    que son dos fuentes distintas: 220 y 230 kV cuentan como la misma barra, el
    prefijo "Nueva" se ignora solo si nadie ocupa ya ese nombre, y hay un puñado de
    alias comprobados a mano. Lo que no case se informa en vez de silenciarse.
    """
    import geopandas as gpd

    d = barras_upme(verbose=verbose)
    if d.empty:
        raise SystemExit("No hay informes legibles en data/barras/upme. "
                         "Corre antes 'python capacidad_barras.py descargar'.")

    horizonte = sorted(d["anio"].unique())
    if anio is None:
        anio = min(max(datetime.date.today().year, horizonte[0]), horizonte[-1])

    try:
        sin = gpd.read_file(config.SUBESTACIONES_PATH)
    except Exception as exc:
        raise SystemExit(f"No se pudo leer la capa de subestaciones ({type(exc).__name__}). "
                         f"Revisa config.py o corre 'python gcs.py auth'.") from exc
    nombres = sorted({str(n) for n in sin["nombre_subestacion"].dropna()})

    # Índice de barras. Dos pasadas: primero el nombre tal cual, y solo después la
    # variante sin "Nueva", para que "Toluviejo 110" no se lo quede "Nva Toluviejo 110".
    exactas: dict[tuple, list] = {}
    variantes: dict[tuple, list] = {}
    for (subarea, barra), grupo in d.groupby(["subarea", "barra"], sort=True):
        base, kv = _partir(barra)
        # Un puñado de barras aparece con la tabla repetida dentro del mismo informe,
        # con cifras distintas y sin decir cuál manda. Se toma la menor.
        tabla = grupo.sort_values("mw").groupby("anio").first()[["mw", "escenario"]]
        entrada = (barra, subarea, tabla)
        exactas.setdefault((base, _clase(kv)), []).append(entrada)
        corto = re.sub(r"^(nva?|nueva|nuevo)\s+", "", base)
        if corto != base:
            variantes.setdefault((corto, _clase(kv)), []).append(entrada)
    indice = dict(exactas)
    for k, v in variantes.items():
        indice.setdefault(k, v)

    filas, sin_datos, ambiguas = [], [], []
    for nombre in nombres:
        base, kv = _partir(nombre)
        candidatas = indice.get((ALIAS.get(base, base), _clase(kv)))
        if not candidatas:
            sin_datos.append(nombre)
            continue

        # Una barra en el borde de dos subáreas aparece en los dos informes. Cuando
        # coinciden da igual cuál se tome; cuando no, se toma la menor y se deja dicho.
        valores = {sa: (t["mw"].get(anio), t) for _, sa, t in candidatas}
        presentes = {sa: v for sa, (v, _) in valores.items() if v is not None}
        if not presentes:
            sin_datos.append(nombre)
            continue
        if len({round(v, 2) for v in presentes.values()}) > 1:
            ambiguas.append((nombre, presentes))
        elegida = min(presentes, key=lambda sa: presentes[sa])
        mw, tabla = valores[elegida]
        barra = next(b for b, sa, _ in candidatas if sa == elegida)

        filas.append({
            "subestacion": nombre,
            "capacidad_disponible_mw": round(float(mw), 2),
            "anio": anio,
            "capacidad_min_horizonte_mw": round(float(tabla["mw"].min()), 2),
            "capacidad_max_horizonte_mw": round(float(tabla["mw"].max()), 2),
            "escenario_critico": str(tabla["escenario"].get(anio, "")),
            "barra_upme": barra,
            "subarea": elegida,
            "ciclo": CICLO,
            "fuente": FUENTE,
        })

    t = pd.DataFrame(filas)
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / f"capacidad_upme_{CICLO.replace('-', '_')}.csv"
    t.to_csv(destino, index=False, sep=";", decimal=",", encoding="utf-8-sig")

    if verbose:
        print()
        print(f"  horizonte del informe    : {horizonte[0]}-{horizonte[-1]}")
        print(f"  año tomado como referencia: {anio}")
        print(f"  barras leídas            : {d['barra'].nunique()}")
        print(f"  subestaciones del SIN    : {len(nombres)}")
        print(f"  emparejadas              : {len(t)}")
        print(f"  sin equivalente           : {len(sin_datos)}")
        if ambiguas:
            print(f"  en dos subáreas con cifras distintas (se toma la menor): {len(ambiguas)}")
            for nombre, v in ambiguas[:8]:
                print(f"     {nombre}: " + ", ".join(f"{sa} {x:.1f}" for sa, x in v.items()))
        print(f"\n  CSV -> {destino}")
    return t


#: Por debajo de esto es media tensión, que es donde se conecta la generación
#: distribuida. La UPME reporta estas barras igual que las de transmisión.
KV_MEDIA_TENSION = 50.0


def extraer_todas(anio: int | None = None, verbose: bool = True) -> pd.DataFrame:
    """
    Todas las barras de los informes, sin exigir que existan en la capa del SIN.

    `extraer` recorre las subestaciones georreferenciadas y busca la barra de cada una,
    así que se queda con las que emparejan y descarta el resto. Eso deja fuera dos
    cosas que hacen falta: las barras de subestaciones que la capa no tiene, y sobre
    todo las de media tensión, que son 434 de las 1.116 que declaran los informes y son
    justo donde se conecta un proyecto de 1 a 2 MW.

    Aquí se guarda todo, con el nombre base y la tensión separados, para poder buscar
    después por subestación sin depender de que coincida el nivel de tensión.
    """
    d = barras_upme(verbose=verbose)
    if d.empty:
        raise SystemExit("No hay informes legibles en data/barras/upme.")

    horizonte = sorted(d["anio"].unique())
    if anio is None:
        anio = min(max(datetime.date.today().year, horizonte[0]), horizonte[-1])

    filas = []
    for (subarea, barra), grupo in d.groupby(["subarea", "barra"], sort=True):
        base, kv = _partir(barra)
        tabla = grupo.sort_values("mw").groupby("anio").first()[["mw", "escenario"]]
        mw = tabla["mw"].get(anio)
        if mw is None:
            continue
        filas.append({
            "barra": barra,
            "base": ALIAS.get(base, base),
            "kv": kv,
            "media_tension": bool(kv is not None and kv < KV_MEDIA_TENSION),
            "capacidad_disponible_mw": round(float(mw), 2),
            "anio": anio,
            "escenario_critico": str(tabla["escenario"].get(anio, "")),
            "subarea": subarea,
            "ciclo": CICLO,
            "fuente": FUENTE,
        })

    t = pd.DataFrame(filas)
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / f"capacidad_upme_todas_{CICLO.replace('-', '_')}.csv"
    t.to_csv(destino, index=False, sep=";", decimal=",", encoding="utf-8-sig")

    if verbose and len(t):
        mt = t[t.media_tension]
        print()
        print(f"  barras con dato para {anio}   : {len(t)}")
        print(f"  de media tensión (<50 kV) : {len(mt)}")
        if len(mt):
            print("  reparto de la media tensión:")
            for kv, n in mt.kv.value_counts().sort_index().items():
                print(f"     {kv:>6.1f} kV : {n:4d} barras")
        print(f"  subestaciones distintas   : {t.base.nunique()}")
        print(f"\n  CSV -> {destino}")
    return t


def cargar_todas(verbose: bool = True) -> pd.DataFrame:
    """Lee el CSV de extraer_todas, generándolo si no está."""
    ruta = CARPETA / f"capacidad_upme_todas_{CICLO.replace('-', '_')}.csv"
    if not ruta.exists():
        return extraer_todas(verbose=verbose)
    t = pd.read_csv(ruta, sep=";", decimal=",", encoding="utf-8-sig")
    t["media_tension"] = t["media_tension"].astype(str).str.lower().isin(["true", "1", "sí", "si"])
    return t


def capacidad_por_subestacion(verbose: bool = False) -> pd.DataFrame:
    """
    Capacidad de alta y de media tensión de cada subestación, en una fila.

    Se agrupa por el nombre base, así que la subestación de Caucasia junta su barra de
    110 kV con la de 34,5 si el informe trae las dos. Para cada nivel se toma la barra
    con más capacidad libre, que es la que un proyecto intentaría usar.
    """
    t = cargar_todas(verbose=verbose)
    if t.empty:
        return pd.DataFrame()
    g = t.groupby("base")
    out = pd.DataFrame({
        "capacidad_at_mw": g.apply(
            lambda x: x.loc[~x.media_tension, "capacidad_disponible_mw"].max()),
        "capacidad_mt_mw": g.apply(
            lambda x: x.loc[x.media_tension, "capacidad_disponible_mw"].max()),
        "kv_mt": g.apply(lambda x: x.loc[x.media_tension, "kv"].max()),
        "n_barras": g.size(),
    }).reset_index()
    return out


def plantilla() -> Path:
    """Escribe un CSV de ejemplo con las subestaciones que de verdad hacen falta."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / "capacidad_barras_plantilla.csv"

    conc = SALIDA / "concurrencia_subestaciones.csv"
    if conc.exists():
        c = pd.read_csv(conc)
        filas = c.head(40)[["sub_nombre_subestacion", "tension_kv", "operador"]].copy()
        filas.columns = ["subestacion", "tension_kv", "operador"]
    else:
        filas = pd.DataFrame({"subestacion": ["Caucasia 110 kV"], "tension_kv": [110],
                              "operador": [""]})

    filas["capacidad_disponible_mw"] = ""
    filas["capacidad_asignada_mw"] = ""
    filas["ciclo"] = ""
    filas["fuente"] = ""
    filas = filas[["subestacion", "capacidad_disponible_mw", "capacidad_asignada_mw",
                   "ciclo", "fuente", "tension_kv", "operador"]]
    filas.to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
    return destino


def cargar(verbose: bool = True) -> pd.DataFrame:
    """Lee todos los CSV de data/barras, valida y devuelve la tabla consolidada."""
    if not CARPETA.is_dir():
        return pd.DataFrame()

    archivos = [f for f in sorted(CARPETA.glob("*.csv"))
                if "plantilla" not in f.name.lower()]
    if not archivos:
        return pd.DataFrame()

    trozos = []
    for f in archivos:
        for sep in (";", ","):
            try:
                d = pd.read_csv(f, sep=sep, encoding="utf-8-sig")
                if len(d.columns) > 1:
                    break
            except Exception:
                d = None
        if d is None or d.empty:
            if verbose:
                print(f"  aviso: {f.name} no se pudo leer o está vacío")
            continue
        d.columns = [normalizar(c).replace(" ", "_") for c in d.columns]
        faltan = [c for c in OBLIGATORIAS if c not in d.columns]
        if faltan:
            if verbose:
                print(f"  aviso: {f.name} no trae {', '.join(faltan)}, se omite")
            continue
        d["_origen"] = f.name
        trozos.append(d)

    if not trozos:
        return pd.DataFrame()

    t = pd.concat(trozos, ignore_index=True)
    t["capacidad_disponible_mw"] = _num(t["capacidad_disponible_mw"])
    if "capacidad_asignada_mw" in t.columns:
        t["capacidad_asignada_mw"] = _num(t["capacidad_asignada_mw"])
    t = t[t["subestacion"].notna() & t["capacidad_disponible_mw"].notna()]
    t["clave"] = t["subestacion"].map(normalizar)
    t = t.drop_duplicates("clave", keep="last")
    return t


def cruzar(verbose: bool = True) -> pd.DataFrame:
    """Cruza la capacidad con la concurrencia de candidatas por subestación."""
    cap = cargar(verbose=verbose)
    conc_path = SALIDA / "concurrencia_subestaciones.csv"
    if not conc_path.exists():
        raise SystemExit(f"Falta {conc_path}. Corre antes reporte/datos.py")

    conc = pd.read_csv(conc_path)
    conc["clave"] = conc["sub_nombre_subestacion"].map(normalizar)

    if cap.empty:
        conc["capacidad_disponible_mw"] = pd.NA
        conc["holgura"] = "sin dato"
        return conc

    cols = ["clave", "capacidad_disponible_mw"] + \
           [c for c in ("capacidad_asignada_mw", "ciclo", "fuente") if c in cap.columns]
    # reporte/datos.py ya deja capacidad_disponible_mw en el archivo, vacía mientras
    # no haya dato. Si sobrevive al merge, pandas la renombra a _x y _y y el veredicto
    # acaba leyendo la vacía. No se notó hasta que hubo algo que cruzar.
    conc = conc.drop(columns=[c for c in cols if c != "clave" and c in conc.columns])
    j = conc.merge(cap[cols], on="clave", how="left")

    # Lectura práctica: lo que se puede conectar frente a lo que se pretende
    def veredicto(r):
        d = r.get("capacidad_disponible_mw")
        if pd.isna(d):
            return "sin dato"
        if d <= 0:
            return "sin cupo"
        pretendido = r.get("mwp_pretendido")
        if pd.isna(pretendido) or pretendido <= 0:
            return "con cupo"
        return "cupo holgado" if d >= pretendido else "cupo limitado"

    j["holgura"] = j.apply(veredicto, axis=1)
    return j


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Capacidad en barras")
    p.add_argument("accion", choices=["descargar", "extraer", "plantilla", "cargar", "estado"])
    p.add_argument("--forzar", action="store_true",
                   help="vuelve a bajar los informes aunque ya estén")
    p.add_argument("--anio", type=int, default=None,
                   help="año del horizonte que se toma como capacidad (por defecto, el actual)")
    a = p.parse_args(argv)

    if a.accion == "descargar":
        print("=" * 74)
        print(f"INFORMES DE CAPACIDAD POR BARRA, CICLO {CICLO}")
        print("=" * 74)
        hechos = descargar(forzar=a.forzar)
        print()
        print(f"  {len(hechos)} de {len(INFORMES)} informes en {CARPETA_PDF}")
        print("  Ahora: python capacidad_barras.py extraer")
        return 0 if len(hechos) == len(INFORMES) else 1

    if a.accion == "extraer":
        print("=" * 74)
        print("LECTURA DE LOS INFORMES")
        print("=" * 74)
        extraer(anio=a.anio)
        print("  Ahora: python capacidad_barras.py cargar")
        return 0

    if a.accion == "plantilla":
        d = plantilla()
        print("=" * 74)
        print("PLANTILLA PARA CARGAR LA CAPACIDAD")
        print("=" * 74)
        print(f"  {d}")
        print()
        print("  Trae ya las subestaciones a las que se conectarían las candidatas,")
        print("  ordenadas por cuántas compiten por cada una. Rellena la columna")
        print("  capacidad_disponible_mw con el dato de la UPME y guárdalo en")
        print(f"  {CARPETA} con cualquier nombre que no lleve 'plantilla'.")
        return 0

    t = cruzar()
    con_dato = int(t["capacidad_disponible_mw"].notna().sum()) if "capacidad_disponible_mw" in t else 0

    print("=" * 74)
    print("CAPACIDAD DISPONIBLE EN BARRAS")
    print("=" * 74)
    print(f"  subestaciones de conexión : {len(t)}")
    print(f"  con dato de capacidad     : {con_dato}")

    if con_dato == 0:
        print()
        print("  Todavía no hay ningún dato cargado. El reporte muestra el hueco")
        print("  explícito en vez de inventarlo.")
        print()
        print("  Para cargarlo desde los informes de la UPME:")
        print("     python capacidad_barras.py descargar")
        print("     python capacidad_barras.py extraer")
        print("     python capacidad_barras.py cargar")
        print("     python -m insumos subir      (para que lo tenga todo el equipo)")
        print()
        print("  O a mano, si aparece una fuente mejor:")
        print("     python capacidad_barras.py plantilla")
        print("     rellenar el CSV y guardarlo en data/barras/")
        return 0

    SALIDA.mkdir(parents=True, exist_ok=True)
    t.to_csv(DESTINO, index=False, encoding="utf-8-sig")

    print()
    print(t["holgura"].value_counts().to_string())
    print()
    cols = [c for c in ["sub_nombre_subestacion", "candidatas", "mwp_pretendido",
                        "capacidad_disponible_mw", "holgura"] if c in t.columns]
    print(t.sort_values("candidatas", ascending=False).head(12)[cols].to_string(index=False))
    print()
    print(f"  CSV -> {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
