"""
Prepara el derecho de petición a la SNR para obtener las matrículas inmobiliarias.

El catastro (IGAC) publica el número predial nacional pero no la matrícula, y sin
matrícula no hay certificado de tradición. La consulta web de la SNR exige cuenta y
captcha, de a un lote por vez; para una lista la vía es la petición (Ley 1755/2015).
Entrada: outputs/reporte/lotes_<perfil>.csv. Salidas en outputs/reporte/:
matriculas_solicitud_<perfil>.csv (anexo) y matriculas_peticion_<perfil>.txt (texto).
Se pide por la lista completa: la matrícula es gratuita y el costo llega al comprar los
certificados, decisión posterior. Radicar y comprar certificados queda fuera del módulo.
Uso: python -m predios.registro [--perfil utility] [--solo limpios|idoneos|<clase>] [--ha-minima N] [--lista lotes.csv]
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import date
from pathlib import Path

import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config
import reporte.datos as rg

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

#: Certificado electrónico hasta 150 anotaciones, Resolución SNR 2026-001726 (vigente
#: desde 2026-02-02); con más de 150 anotaciones son 53.100. Se actualiza cada enero.
COSTO_CERTIFICADO = 23_000

#: Columnas del anexo que se envía a la SNR.
COLUMNAS = ["orden", "CODIGO", "departamento", "municipio", "area_ha",
            "clasificacion", "indice_lote", "estorbos", "gestion"]


def matriculas_conocidas() -> set[str]:
    """
    Códigos catastrales cuya matrícula ya se obtuvo en la consulta de índice de
    propietarios. No se vuelven a pedir: la petición solo debe cubrir lo que falta.
    """
    ruta = config.PROJECT_ROOT / "data" / "registro" / "matriculas.csv"
    if not ruta.exists():
        return set()
    m = pd.read_csv(ruta, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    m.columns = [c.strip().lower() for c in m.columns]
    col = "matricula_inmobiliaria" if "matricula_inmobiliaria" in m.columns else "matricula"
    if col not in m.columns or "codigo" not in m.columns:
        return set()
    m = m.dropna(subset=[col])
    return set(m["codigo"].str.strip().str.zfill(30))


def cargar(perfil: str, solo: str | None = None, ha_minima: float | None = None,
           lista: str | None = None) -> pd.DataFrame:
    """
    Lotes de un perfil. `solo` acepta 'limpios' (estorbos == 0), 'idoneos' o una
    clasificación literal; `ha_minima` deja solo los de esa área o más; `lista` es un CSV
    con columna CODIGO (por ejemplo el que descarga el visor con el filtro puesto) y
    restringe a esos. Sin filtros van todos los caracterizados.
    """
    ruta = SALIDA / f"lotes_{perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    p = pd.read_csv(ruta, dtype={"CODIGO": str})

    if solo == "limpios":
        p = p[p["estorbos"] == 0]
    elif solo == "idoneos":
        p = p[p["clasificacion"] == "Idóneo"]
    elif solo:
        p = p[p["clasificacion"] == solo]
    if ha_minima:
        p = p[p["area_ha"] >= ha_minima]
    if lista:
        l = pd.read_csv(lista, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
        col = next((c for c in l.columns if c.strip().upper() == "CODIGO"), None)
        if col is None:
            raise SystemExit(f"{lista} no tiene columna CODIGO")
        p = p[p["CODIGO"].isin(set(l[col].str.strip().str.zfill(30)))]
    return p.reset_index(drop=True)


def tabla(p: pd.DataFrame) -> pd.DataFrame:
    """Anexo para la SNR: COLUMNAS más matrícula y ORIP vacías, que llena la SNR."""
    q = p[[c for c in COLUMNAS if c in p.columns]].copy()
    q["CODIGO"] = q["CODIGO"].str.zfill(30)
    q.insert(2, "matricula_inmobiliaria", "")
    q.insert(3, "orip", "")
    return q


PETICION = """\
Señores
SUPERINTENDENCIA DE NOTARIADO Y REGISTRO
Oficina de Atención al Ciudadano
Bogotá D.C.

Referencia: Derecho de petición de información. Solicitud de números de matrícula
inmobiliaria correspondientes a predios identificados por número predial nacional.

{peticionario}, en ejercicio del derecho fundamental de petición consagrado en el
artículo 23 de la Constitución Política y regulado por la Ley 1755 de 2015, y con
fundamento en la Ley 1712 de 2014 sobre transparencia y acceso a la información pública,
respetuosamente solicito:

ÚNICO. Que se informe el número de matrícula inmobiliaria y la Oficina de Registro de
Instrumentos Públicos competente, correspondientes a cada uno de los {n} predios
identificados con el número predial nacional relacionado en el anexo de esta solicitud.

FUNDAMENTO DE LA SOLICITUD

La información se requiere para un estudio de prefactibilidad de proyectos de generación
solar fotovoltaica. Los predios fueron identificados a partir de las capas públicas del
Instituto Geográfico Agustín Codazzi, que publican el número predial nacional pero no la
matrícula inmobiliaria, razón por la cual no es posible establecer la correspondencia
entre ambos identificadores a partir de fuentes abiertas.

{ambito}

TÉRMINO

De conformidad con el numeral 1 del artículo 14 de la Ley 1755 de 2015, las peticiones
de documentos y de información deben resolverse dentro de los diez (10) días siguientes
a su recepción.

NOTIFICACIONES

Correo electrónico: {correo}
Dirección: {direccion}

Anexo: relación de {n} predios en formato digital.

Atentamente,


{peticionario}
{identificacion}
"""


def peticion(p: pd.DataFrame, peticionario: str, identificacion: str,
             correo: str, direccion: str) -> str:
    """Texto de la petición, con el ámbito geográfico derivado de los predios."""
    pordepto = p.groupby("departamento")["municipio"].nunique()
    partes = [f"{n} municipio{'s' if n > 1 else ''} del departamento de "
              f"{d.title()}" for d, n in pordepto.items()]
    ambito = ", ".join(partes[:-1]) + (" y " + partes[-1] if len(partes) > 1 else partes[0])
    # misma anchura que el resto del texto, que se radica impreso
    ambito = textwrap.fill(f"Los predios se ubican en {ambito}.", width=88)

    return PETICION.format(n=len(p), ambito=ambito, peticionario=peticionario,
                           identificacion=identificacion, correo=correo,
                           direccion=direccion)


def main(argv=None) -> int:
    """CLI: escribe el anexo y el texto de la petición y estima el costo de los certificados."""
    ap = argparse.ArgumentParser(
        description="Prepara la solicitud de matrículas inmobiliarias a la SNR")
    ap.add_argument("--perfil", default="utility",
                    help=f"uno de {', '.join(rg.PERFILES)}")
    ap.add_argument("--solo", default=None,
                    help="'limpios' (sin estorbos), 'idoneos', o una clasificación")
    ap.add_argument("--ha-minima", type=float, default=None, help="área mínima del lote en ha")
    ap.add_argument("--lista", default=None,
                    help="CSV con columna CODIGO (p. ej. el descargado del visor con el filtro puesto)")
    ap.add_argument("--peticionario", default="MÉTODOS MIXTOS CONSULTORES S.A.S.")
    ap.add_argument("--identificacion", default="NIT [pendiente]")
    ap.add_argument("--correo", default="sblanco@metodosmixtos.com")
    ap.add_argument("--direccion", default="[pendiente]")
    ap.add_argument("--incluir-resueltos", action="store_true",
                    help="pide también los lotes cuya matrícula ya se conoce")
    a = ap.parse_args(argv)

    p = cargar(a.perfil, a.solo, a.ha_minima, a.lista)
    if p.empty:
        raise SystemExit("Ningún lote cumple ese filtro.")

    # Los lotes cuya matrícula ya devolvió la consulta de índice de propietarios no se
    # vuelven a pedir: la petición cubre solo lo que sigue sin resolverse.
    ya = matriculas_conocidas()
    resueltos = int(p["CODIGO"].str.zfill(30).isin(ya).sum())
    if resueltos and not a.incluir_resueltos:
        p = p[~p["CODIGO"].str.zfill(30).isin(ya)].reset_index(drop=True)
    if p.empty:
        raise SystemExit("Todos los lotes de ese filtro ya tienen matrícula: "
                         "no hay nada que pedir.")

    q = tabla(p)
    csv = SALIDA / f"matriculas_solicitud_{a.perfil}.csv"
    txt = SALIDA / f"matriculas_peticion_{a.perfil}.txt"
    q.to_csv(csv, index=False, encoding="utf-8-sig")
    txt.write_text(peticion(p, a.peticionario, a.identificacion, a.correo, a.direccion),
                   encoding="utf-8")

    print("=" * 74)
    print("SOLICITUD DE MATRÍCULAS INMOBILIARIAS")
    print("=" * 74)
    print(f"  fecha            : {date.today().isoformat()}")
    print(f"  perfil           : {a.perfil}" + (f", solo {a.solo}" if a.solo else ""))
    print(f"  lotes            : {len(p)}")
    if resueltos:
        print(f"  ya resueltos     : {resueltos}   "
              f"({'incluidos' if a.incluir_resueltos else 'excluidos de la petición'})")
    print(f"  departamentos    : {p['departamento'].nunique()}   "
          f"municipios: {p['municipio'].nunique()}")
    print()
    print("  Por departamento:")
    for d, n in p["departamento"].value_counts().items():
        print(f"    {d:<22} {n:>4}")
    print()
    limpios = int((p["estorbos"] == 0).sum()) if "estorbos" in p.columns else 0
    idoneos = int((p["clasificacion"] == "Idóneo").sum())
    print("  Costo de los certificados, si se compran después:")
    for etiqueta, n in (("todos los de esta lista", len(p)),
                        ("solo los Idóneos", idoneos),
                        ("solo los sin estorbos", limpios)):
        print(f"    {etiqueta:<26} {n:>4} × ${COSTO_CERTIFICADO:,} = "
              f"${n * COSTO_CERTIFICADO:>11,}".replace(",", "."))
    print()
    print(f"  anexo    -> {csv.name}")
    print(f"  petición -> {txt.name}")
    print()
    print("  Pedir la matrícula es gratis; el certificado no. Por eso la petición va")
    print("  por la lista completa y la compra se decide después, sobre los mejores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
