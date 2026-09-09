# -*- coding: utf-8 -*-
"""
Obtiene la matrícula inmobiliaria de cada lote en la consulta de índice de propietarios.

La Superintendencia de Notariado y Registro publica esa consulta en su plataforma de
certificados. El formulario pide un número de documento, pero admite además el filtro
"Número Chip o Matrícula Catastral", y los dos criterios se combinan de forma que el
predio aparece si coincide por cualquiera de ellos; la columna "Vinculado a" dice por
cuál. Escribiendo el número predial nacional de 30 dígitos en ese campo, la consulta
devuelve la matrícula del predio aunque el titular no tenga relación con el documento
indicado. La respuesta llega con número de recibo, que permite verificarla después.

LO QUE LIMITA ESTA VÍA. La cuenta personal tiene un tope diario de consultas con tarifa
gratuita. Al superarlo la plataforma responde que se ha excedido la cantidad máxima de
consultas con tarifa gratuita por día, y deja de contestar hasta el día siguiente. El 24
de agosto de 2026 quedaron registradas once consultas gratuitas y la siguiente ya fue
rechazada. Por eso este módulo trabaja por tandas: cuando aparece ese aviso se detiene,
deja sin marcar los lotes que faltan y la ejecución siguiente sigue donde quedó. Para los
seiscientos cuarenta y siete lotes del perfil la vía practicable sigue siendo el derecho
de petición que arma predios/registro.py; esta consulta resuelve de inmediato los lotes
que se prioricen.

LA COBERTURA ES PARCIAL Y NO DEPENDE DE LA CONSULTA. El folio solo trae la referencia
catastral donde la Oficina de Registro ya la incorporó. Donde no la incorporó, la
consulta contesta que no encontró ningún inmueble que coincida. Ese resultado se guarda
como "sin dato" con el motivo escrito y nunca se rellena con una aproximación.

CÓMO SE DISTINGUE UNA RESPUESTA DE VERDAD. La página mantiene ocultos, siempre presentes
en el documento, los textos de todos sus avisos, incluido el de que la consulta no arrojó
ningún resultado. Leer el documento entero da por vacía cualquier consulta, incluso las
que sí devolvieron matrícula. Por eso aquí solo se lee el aviso que está efectivamente
visible, y solo se acepta como respuesta el que además trae número de recibo o repite el
predial enviado.

Credenciales en .env (SNR_USUARIO, SNR_CLAVE), que no se versiona. Nunca se escriben en
disco ni en el registro de ejecución. Caché por lote en data/registro/matriculas.json y
tabla para el visor en data/registro/matriculas.csv, las dos fuera del repositorio.

Uso: python -m predios.matricula [--perfil utility] [--limite N] [--muestra N]
                                 [--municipio NOMBRE] [--reintentar] [--solo-tabla]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
REGISTRO = config.PROJECT_ROOT / "data" / "registro"
CACHE = REGISTRO / "matriculas.json"
TABLA = REGISTRO / "matriculas.csv"

PORTAL = "https://certificados.supernotariado.gov.co/certificado"
FORMULARIO = PORTAL + "/portal/business/main-queries-advanced.snr"

#: Identificadores del formulario. Los genera el servidor al compilar la vista, así que
#: cambian si la Superintendencia la vuelve a publicar.
ID = {
    "usuario": "formLogin:inpUserLogin",
    "clave": "formLogin:inpPassLogin",
    "entrar": "formLogin:btnIngresarLogin",
    "solicitar": "formQueries:j_idt43",
    "historial": "formQueries:j_idt44",
    "documento": "formQueries:j_idt58",
    "check_chip": "formQueries:j_idt79",
    "panel_chip": "formQueries:panelContenidoCHIP",
    "consultar": "formQueries:j_idt85",
}


def _sel(i: str) -> str:
    """Selector por identificador. Los dos puntos hay que escaparlos."""
    return "#" + i.replace(":", "\\:")


#: Aviso de tope diario. No es un resultado: es la plataforma negándose a contestar.
CUOTA = ("cantidad maxima de consultas", "tarifa gratuita")

#: Las dos formas en que la plataforma dice que no hubo coincidencia.
SIN_COINCIDENCIA = ("no se ha encontrado ningun inmueble",
                    "no arrojo ningun resultado")

MOTIVO_SIN_DATO = ("la Oficina de Registro de Instrumentos Públicos no ha incorporado la "
                   "referencia catastral de este predio a su folio de matrícula")

MOTIVO_PENDIENTE = ("todavía no se ha consultado: el cupo diario de consultas gratuitas "
                    "obliga a preguntar por tandas")

FUENTE = ("Superintendencia de Notariado y Registro, consulta de índice de propietarios, "
          "buscando por el número predial nacional de 30 dígitos")


#: Predio de control, fuera del estudio, cuya matrícula se conoce por otra vía. Sirve
#: para comprobar que la consulta sigue devolviendo lo que debe antes de fiarse de una
#: tanda entera. Con --control se pregunta por él y se compara con el valor esperado.
CONTROL_PREDIAL = "734490001000000010054000000000"
CONTROL_MATRICULA = "366-35594"


def _plano(t: str) -> str:
    """Texto comparable: sin tildes, sin espacios repetidos, en minúscula."""
    t = t.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


# --------------------------------------------------------------------------
# Credenciales y caché
# --------------------------------------------------------------------------

def credenciales() -> tuple[str, str]:
    """Usuario y clave de la Superintendencia desde .env. No se imprimen ni se guardan."""
    env = _raiz / ".env"
    if not env.exists():
        raise SystemExit("Falta .env con SNR_USUARIO y SNR_CLAVE en la raíz del proyecto.")
    val = {}
    for linea in env.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            val[k.strip()] = v.strip().strip('"').strip("'")
    try:
        return val["SNR_USUARIO"], val["SNR_CLAVE"]
    except KeyError as e:
        raise SystemExit(f"Falta {e.args[0]} en .env")


def documento(usuario: str) -> str:
    """
    Número que ocupa la casilla obligatoria de documento. Se deriva del usuario, que la
    plataforma forma como tipo de documento más número. Solo llena la casilla: al predio
    lo encuentra el filtro de referencia catastral, no este número.
    """
    return re.sub(r"^[A-Za-z]+", "", usuario)


def leer_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def guardar_cache(c: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------
# Lectura de la respuesta
# --------------------------------------------------------------------------

async def _dialogos_visibles(pg):
    """Avisos efectivamente visibles. Los ocultos son plantillas y no se leen."""
    out = []
    for d in await pg.query_selector_all(".ui-dialog"):
        try:
            if not await d.is_visible():
                continue
            t = (await d.inner_text()).strip()
        except Exception:
            continue
        if t:
            out.append(((await d.get_attribute("id")) or "?", t, d))
    return out


async def _fila_matricula(dialogo):
    """
    Busca la fila de resultado. La tabla trae PIN, Oficina, Matrícula, Dirección y
    "Vinculado a"; la matrícula se escribe uniendo oficina y número, como 303-9682. Las
    columnas se localizan por su encabezado y no por su posición.
    """
    for tabla in await dialogo.query_selector_all("table"):
        encabezados = [_plano(await th.inner_text())
                       for th in await tabla.query_selector_all("thead th, thead td")]
        if not encabezados:
            continue
        idx = {}
        for i, h in enumerate(encabezados):
            for clave, etiqueta in (("oficina", "oficina"), ("matricula", "matricula"),
                                    ("direccion", "direccion"), ("vinculo", "vinculado")):
                if etiqueta in h and clave not in idx:
                    idx[clave] = i
        if "matricula" not in idx:
            continue
        for tr in await tabla.query_selector_all("tbody tr"):
            c = [(await td.inner_text()).strip()
                 for td in await tr.query_selector_all("td")]
            if not c or not any(c):
                continue
            mat = c[idx["matricula"]] if idx["matricula"] < len(c) else ""
            ofi = c[idx["oficina"]] if "oficina" in idx and idx["oficina"] < len(c) else ""
            if re.fullmatch(r"\d{2,4}-\d+", mat):
                completa = mat
            elif mat.isdigit() and ofi.isdigit():
                completa = f"{ofi}-{mat}"
            else:
                continue
            return {
                "matricula": completa,
                "orip": completa.split("-")[0],
                "nombre_registro": (c[idx["direccion"]] if "direccion" in idx
                                    and idx["direccion"] < len(c) else None),
                "vinculado_a": (c[idx["vinculo"]] if "vinculo" in idx
                                and idx["vinculo"] < len(c) else None),
            }
    return None


async def _leer_respuesta(pg, predial: str, espera: int = 90) -> dict:
    """
    Espera el aviso visible y lo clasifica. Devuelve uno de estos estados:
      ok             la consulta devolvió matrícula
      sin_dato       la consulta contestó que no hay inmueble que coincida
      cuota_agotada  la plataforma no responde más hoy por el tope diario
      sin_respuesta  no llegó ningún aviso legible en el tiempo previsto
    """
    for _ in range(max(1, espera // 2)):
        await pg.wait_for_timeout(2_000)
        for _ident, texto, nodo in await _dialogos_visibles(pg):
            p = _plano(texto)
            if all(s in p for s in CUOTA):
                return {"estado": "cuota_agotada",
                        "motivo": "se agotó el cupo diario de consultas gratuitas de la "
                                  "cuenta; la plataforma no responde más hasta mañana"}
            recibo = re.search(r"recibo[^\d]{0,20}(\d{6,})", p)
            # Solo se acepta como respuesta la que trae recibo o repite el predial
            # enviado: así no se confunde con el aviso de otra cosa.
            if not (recibo or predial in p):
                continue
            fila = await _fila_matricula(nodo)
            if fila:
                fila["estado"] = "ok"
                fila["recibo"] = recibo.group(1) if recibo else None
                return fila
            if any(s in p for s in SIN_COINCIDENCIA):
                return {"estado": "sin_dato", "motivo": MOTIVO_SIN_DATO,
                        "recibo": recibo.group(1) if recibo else None}
    return {"estado": "sin_respuesta",
            "motivo": "la plataforma no devolvió ningún aviso legible"}


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------

async def _entrar(pg, usuario: str, clave: str) -> None:
    """Inicia sesión. El aviso de la portada tapa el botón, así que se oculta antes."""
    await pg.goto(PORTAL, wait_until="networkidle", timeout=90_000)
    await pg.wait_for_timeout(2_500)
    await pg.evaluate("()=>{document.querySelectorAll('.ui-dialog,.ui-widget-overlay')"
                      ".forEach(d=>d.style.display='none')}")
    await pg.click("button:has-text('Inicia sesión')", timeout=20_000)
    await pg.wait_for_selector(_sel(ID["usuario"]), timeout=20_000)
    await pg.fill(_sel(ID["usuario"]), usuario)
    await pg.fill(_sel(ID["clave"]), clave)
    await pg.click(_sel(ID["entrar"]))
    await pg.wait_for_timeout(8_000)


async def _consultar(pg, doc: str, predial: str) -> dict:
    """
    Una consulta. Abre el formulario de cero porque la vista no admite dos envíos
    seguidos. Antes de enviar comprueba que el predial quedó completo en el campo: si el
    formulario lo recortara, la consulta devolvería un falso "sin dato".
    """
    await pg.goto(FORMULARIO, wait_until="networkidle", timeout=90_000)
    await pg.wait_for_timeout(2_500)
    await pg.wait_for_selector(_sel(ID["solicitar"]), timeout=30_000)
    await pg.click(_sel(ID["solicitar"]))
    await pg.wait_for_timeout(5_000)

    await pg.wait_for_selector(_sel(ID["check_chip"]), timeout=30_000)
    await pg.click(_sel(ID["check_chip"]) + " .ui-chkbox-box")
    await pg.wait_for_timeout(4_000)

    campo = _sel(ID["panel_chip"]) + " input[type=text]"
    await pg.wait_for_selector(campo, timeout=30_000)
    await pg.click(campo)
    await pg.type(campo, predial, delay=15)
    await pg.click(_sel(ID["documento"]))
    await pg.type(_sel(ID["documento"]), doc, delay=15)
    await pg.wait_for_timeout(800)

    escrito = await pg.input_value(campo)
    if escrito != predial:
        return {"estado": "error",
                "motivo": f"el formulario dejó {len(escrito)} dígitos en vez de "
                          f"{len(predial)}; no se envía para no registrar un falso "
                          "resultado"}

    await pg.click(_sel(ID["consultar"]))
    return await _leer_respuesta(pg, predial)


async def recorrer(prediales, usuario: str, clave: str, cache: dict, pausa: float = 1.0):
    """
    Consulta los prediales pendientes y guarda la caché lote a lote, para que una caída
    no pierda lo ya preguntado. Se detiene en cuanto la plataforma avisa del tope diario:
    los que quedan se dejan sin marcar y la próxima ejecución sigue donde esta paró.
    Devuelve la caché y si se agotó el cupo.
    """
    from playwright.async_api import async_playwright

    doc = documento(usuario)
    agotada = False
    async with async_playwright() as p:
        navegador = await p.chromium.launch(headless=True)
        ctx = await navegador.new_context(locale="es-CO",
                                          viewport={"width": 1500, "height": 1300})
        pg = await ctx.new_page()
        await _entrar(pg, usuario, clave)
        for i, predial in enumerate(prediales, 1):
            r = {"estado": "error", "motivo": "no se intentó"}
            for intento in (1, 2, 3):
                try:
                    r = await _consultar(pg, doc, predial)
                    break
                except Exception as e:
                    r = {"estado": "error", "motivo": str(e).splitlines()[0][:180]}
                    await pg.wait_for_timeout(8_000 * intento)
                    try:
                        await _entrar(pg, usuario, clave)
                    except Exception:
                        pass
            if r["estado"] == "cuota_agotada":
                agotada = True
                print(f"  [{i:>4}/{len(prediales)}] cupo diario agotado; quedan "
                      f"{len(prediales) - i + 1} lotes sin consultar")
                break
            r["fecha"] = datetime.now().isoformat(timespec="seconds")
            r["consultado_con"] = "número predial nacional de 30 dígitos"
            r["fuente"] = FUENTE
            cache[predial] = r
            guardar_cache(cache)
            print(f"  [{i:>4}/{len(prediales)}] {predial}  "
                  f"{r.get('matricula') or r['estado']}")
            if pausa:
                await pg.wait_for_timeout(int(pausa * 1000))
        await navegador.close()
    return cache, agotada


# --------------------------------------------------------------------------
# Salidas
# --------------------------------------------------------------------------

def escribir_tablas(p: pd.DataFrame, cache: dict, perfil: str):
    """
    Escribe las dos salidas: la que lee el visor, con las matrículas conocidas, y la de
    auditoría, con el estado de todos los lotes incluidos los que quedaron sin dato.
    """
    REGISTRO.mkdir(parents=True, exist_ok=True)
    SALIDA.mkdir(parents=True, exist_ok=True)

    filas = []
    for c in p["CODIGO"]:
        r = cache.get(c, {})
        filas.append({"CODIGO": c,
                      "matricula_inmobiliaria": r.get("matricula"),
                      "fuente": r.get("fuente"),
                      "fecha": (r.get("fecha") or "")[:10] or None,
                      "motivo": r.get("motivo"),
                      "estado": r.get("estado"),
                      "recibo": r.get("recibo"),
                      "nombre_registro": r.get("nombre_registro")})
    t = pd.DataFrame(filas)

    # Insumo del visor. Van los lotes ya consultados, con matrícula o sin ella: los que
    # la tienen, para que la ficha la muestre; los que no, para que la ficha pueda decir
    # por qué no la hay en vez de callar. La columna de matrícula queda vacía en estos
    # últimos, de modo que quien solo lea las matrículas conocidas sigue leyéndolas bien.
    visor = t[t["estado"].isin(["ok", "sin_dato"])][
        ["CODIGO", "matricula_inmobiliaria", "fuente", "fecha", "estado", "motivo"]]
    # La tabla no es solo de esta vía: también lleva lo que cosechan los portales de
    # impuesto predial (ver predios/matricula_auto.py). Reescribirla entera desde esta
    # caché borraría esas matrículas, que son verdaderas y costaron su consulta. Se
    # conservan las filas de lotes de los que esta vía no sabe nada.
    if TABLA.exists():
        previo = pd.read_csv(TABLA, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        previo.columns = [c.lstrip("﻿").strip() for c in previo.columns]
        if "CODIGO" in previo.columns:
            previo["CODIGO"] = previo["CODIGO"].str.strip().str.zfill(30)
            ajenas = previo[~previo["CODIGO"].isin(set(visor["CODIGO"]))]
            if len(ajenas):
                visor = pd.concat([visor, ajenas[visor.columns]], ignore_index=True)
    visor = visor.sort_values("CODIGO")
    visor.to_csv(TABLA, index=False, encoding="utf-8-sig")

    # Auditoría: todos los lotes, con el motivo escrito donde no hay dato.
    cols = [c for c in ("orden", "CODIGO", "departamento", "municipio", "nombre_predio",
                        "area_ha") if c in p.columns]
    aud = p[cols].merge(t, on="CODIGO", how="left")
    aud["estado"] = aud["estado"].fillna("sin consultar")
    # El motivo solo explica una ausencia. En los lotes que sí tienen matrícula la
    # casilla queda vacía: escribir ahí el motivo de los pendientes diría lo contrario
    # de lo que pasó.
    aud.loc[aud["estado"] == "sin consultar", "motivo"] = MOTIVO_PENDIENTE
    ruta_aud = SALIDA / f"matriculas_{perfil}.csv"
    aud.to_csv(ruta_aud, index=False, encoding="utf-8-sig")
    return TABLA, ruta_aud


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    """Consulta las matrículas pendientes y reescribe las dos tablas."""
    ap = argparse.ArgumentParser(
        description="Matrícula inmobiliaria de cada lote, en la consulta de índice de "
                    "propietarios de la Superintendencia de Notariado y Registro")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--limite", type=int, default=None,
                    help="consulta como mucho N lotes en esta tanda")
    ap.add_argument("--muestra", type=int, default=None,
                    help="reparte la tanda entre municipios, N lotes por municipio")
    ap.add_argument("--municipio", default=None, help="restringe la tanda a un municipio")
    ap.add_argument("--reintentar", action="store_true",
                    help="vuelve a preguntar por los que quedaron en error o sin respuesta")
    ap.add_argument("--solo-tabla", action="store_true",
                    help="no consulta: solo reescribe las tablas con lo ya guardado")
    ap.add_argument("--control", action="store_true",
                    help="pregunta por el predio de control y comprueba que la consulta "
                         "devuelve la matrícula que ya se le conoce")
    a = ap.parse_args(argv)

    if a.control:
        usuario, clave = credenciales()
        print(f"Predio de control {CONTROL_PREDIAL}: se espera {CONTROL_MATRICULA}.")
        # La comprobación parte de la caché real, no de un diccionario vacío: recorrer()
        # guarda en disco lo que se le pasa, así que arrancar en vacío borraría todo lo
        # ya consultado. Se comprobó el 25 de agosto de 2026, cuando pasó justo eso.
        c, _ = asyncio.run(recorrer([CONTROL_PREDIAL], usuario, clave, leer_cache()))
        r = c.get(CONTROL_PREDIAL, {})
        obtenida = r.get("matricula")
        if obtenida == CONTROL_MATRICULA:
            print(f"  Correcto: devolvió {obtenida}. La consulta es de fiar.")
            return 0
        if not c:
            print("  No se pudo comprobar: se agotó el cupo diario gratuito. "
                  "La comprobación queda pendiente para mañana.")
            return 1
        print(f"  ATENCIÓN: devolvió {obtenida or r.get('estado')}, no {CONTROL_MATRICULA}. "
              "No conviene fiarse de una tanda hasta entender por qué.")
        return 1

    ruta = SALIDA / f"lotes_{a.perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes el paso de lotes.")
    p = pd.read_csv(ruta, dtype={"CODIGO": str}, encoding="utf-8-sig")
    p["CODIGO"] = p["CODIGO"].str.zfill(30)

    cache = leer_cache()
    agotada = False
    if not a.solo_tabla:
        rehacer = {"error", "sin_respuesta"} if a.reintentar else set()
        q = p if not a.municipio else p[p["municipio"].str.lower() == a.municipio.lower()]
        if q.empty:
            raise SystemExit(f"Ningún lote en {a.municipio}.")
        pendientes = [c for c in q["CODIGO"]
                      if c not in cache or cache[c].get("estado") in rehacer]
        if a.muestra:
            porm = q[q["CODIGO"].isin(pendientes)].groupby("municipio")["CODIGO"]
            pendientes = [c for _, g in porm for c in list(g)[:a.muestra]]
        if a.limite:
            pendientes = pendientes[:a.limite]
        if pendientes:
            usuario, clave = credenciales()
            print(f"Consultando {len(pendientes)} lotes. La consulta es gratuita y la "
                  "cuenta tiene un tope diario, así que la tanda puede detenerse antes.")
            cache, agotada = asyncio.run(recorrer(pendientes, usuario, clave, cache))
        else:
            print("Nada pendiente: lo ya guardado cubre los lotes seleccionados.")

    visor, aud = escribir_tablas(p, cache, a.perfil)

    est = pd.Series([cache.get(c, {}).get("estado", "sin consultar") for c in p["CODIGO"]])
    con = int(est.eq("ok").sum())
    print()
    print("=" * 70)
    print(f"  lotes del perfil            {len(p):>5}")
    print(f"  con matrícula               {con:>5}")
    print(f"  sin dato en el registro     {int(est.eq('sin_dato').sum()):>5}")
    print(f"  sin consultar todavía       {int(est.eq('sin consultar').sum()):>5}")
    print(f"  por reintentar              {int(est.isin(['error', 'sin_respuesta']).sum()):>5}")
    print()
    if con:
        print("  Matrículas obtenidas:")
        for c in p["CODIGO"]:
            r = cache.get(c, {})
            if r.get("estado") == "ok":
                f = p[p["CODIGO"] == c].iloc[0]
                print(f"    {f['municipio']:<20} {r['matricula']:<12} "
                      f"{r.get('nombre_registro') or ''}")
        print()
    print(f"  tabla del visor -> {visor}")
    print(f"  auditoría       -> {aud}")
    print()
    if agotada:
        print("  Se agotó el cupo diario gratuito. Los lotes que faltan quedan sin marcar")
        print("  y la siguiente ejecución sigue donde esta se detuvo.")
    print("  Los lotes sin dato no se rellenan: van en el derecho de petición, que la")
    print("  Superintendencia debe resolver en diez días hábiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
