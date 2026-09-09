# -*- coding: utf-8 -*-
"""
Del número de matrícula al PDF del certificado de tradición y libertad.

QUÉ RESUELVE Y QUÉ NO
---------------------
El procedimiento ya sabe sacar la matrícula de un lote (predios/matricula_auto.py) y ya
sabe leer un certificado en PDF y analizarlo (predios/certificados.py y
predios/certificado_ia.py). Faltaba el eslabón del medio. Este módulo lo cubre hasta
donde se puede cubrir sin pagar, y se detiene exactamente donde empieza el pago.

NO HAY API PÚBLICA. Se comprobó el 26 de agosto de 2026, abriendo:
  - certificados.supernotariado.gov.co: es una aplicación JSF/PrimeFaces 13 con sesión y
    ViewState (todo va por POST a /certificado/inicio.snr). No expone REST ni WSDL.
  - www.datos.gov.co: los conjuntos de la Superintendencia son estadística agregada por
    departamento y mes. Ninguno trae folios ni matrículas.
  - www.vur.gov.co: responde, pero el portal queda tras un inicio de sesión de entidad
    (SSO SiteMinder). El apex vur.gov.co ni siquiera resuelve en el DNS.
  - la ficha del trámite en el visor del SUIT (fi=420, actualizada el 01-07-2026): lista
    como canales el correo, el presencial y la página web. Ninguno programable.

SÍ EXISTEN SERVICIOS SOAP, PERO CERRADOS. El directorio nacional de interoperabilidad
del MinTIC (sigmi.mintic.gov.co) tiene registrados siete servicios de la Superintendencia
en estado "Publicado Nivel 3", entre ellos "Certificado de Tradición Exento" y uno de
consulta que recibe el número de matrícula y devuelve el PDF en base64. En los siete el
campo de la dirección viene vacío y la ficha técnica responde 401. Son servicios de
convenio: existen, pero no están abiertos. Esto es lo que hay de cierto en que "se puede
sacar por API": se puede, con convenio, no de entrada.

EL CANAL MASIVO OFICIAL NO ES UNA API: ES UN EXCEL. La modalidad de autoconsumo
(Resolución 03915 de 2023, con el capítulo IV que le añadió la RES-2025-006086-6 del 9 de
mayo de 2025, en desarrollo del artículo 12 de la Ley 2434 de 2024) permite pedir hasta
mil certificados diarios cargando un archivo plano en Excel, con pago anticipado a una
cuenta prepago. Exige autorización previa de la Superintendencia, la actividad económica
debe constar en el RUT, y prohíbe expresamente revender los certificados. La tarifa es la
misma: no hay descuento por volumen.

LO QUE ESTE MÓDULO HACE, ENTONCES
---------------------------------
1. COMPROBAR (gratis, sin cuenta). El portal deja consultar una matrícula sin pagar y sin
   iniciar sesión: contesta la dirección del lote, el círculo registral y si el
   certificado está disponible. Sirve para saber, antes de gastar un peso, cuáles de las
   matrículas que tenemos existen y son expedibles. Es la parte que sí queda automatizada
   de punta a punta.
2. PREPARAR LA COMPRA. Arma el carrito por tandas del tamaño que admite el portal y llega
   hasta la pantalla que muestra el valor a pagar. AHÍ PARA. No pulsa Pagar, no elige
   medio de pago y no simula ninguna compra. Devuelve el total que el portal liquidó y
   deja escrito que ese paso lo tiene que hacer una persona.
3. RECUPERAR POR PIN (gratis, sin cuenta). Todo certificado pagado lleva un PIN impreso
   en su primera página. Con ese PIN, y durante treinta días, el portal devuelve copia del
   certificado sin volver a cobrar. Pasados los treinta días sigue confirmando la
   transacción, pero ya no entrega el archivo. Por eso el PIN se guarda siempre.

NADA SE INVENTA. Si el portal no contesta, se escribe que no contestó. Un lote que no se
pudo comprobar no se escribe como "no disponible": se queda sin fila, que es como el
visor dice que todavía no se ha preguntado.

TARIFA, COMPROBADA CONTRA LA NORMA Y CONTRA EL PORTAL
-----------------------------------------------------
Resolución RES-2026-001726-6 del 29 de enero de 2026, "por la cual se actualizan las
tarifas por concepto del ejercicio de la función registral", modificada por la
RES-2026-001896-6 del 30 de enero de 2026, que fijó su vigencia a partir del 2 de febrero
de 2026 y derogó la Resolución 00179 del 10 de enero de 2025:
  - artículo 15, literal a): el certificado de tradición por medios electrónicos vale
    veintitrés mil pesos ($23.000). Es el que se descarga en PDF.
  - artículo 14, literal a): el expedido en Oficina de Registro, notaría o centro de
    atención vale veinticuatro mil trescientos pesos ($24.300).
  - artículo 14, literal b): el de un folio con más de ciento cincuenta anotaciones vale
    cincuenta y tres mil cien pesos ($53.100).
  - artículo 15, literal b): la consulta de índice de propietarios es gratuita. Es la que
    ya usa predios/matricula.py.
El 26 de agosto de 2026 el carrito del portal liquidó 23.000,00 por la matrícula
366-35594, que es la cifra de la norma. No aparece IVA ni recargo.

Credenciales de la Superintendencia en .env. Este módulo NO las necesita para nada de lo
que hace: las tres operaciones son públicas. No se escriben en código ni en informes.

Uso:
  .venv\\Scripts\\python.exe -m predios.certificado_api oficinas
  .venv\\Scripts\\python.exe -m predios.certificado_api comprobar 366-35594 [...]
  .venv\\Scripts\\python.exe -m predios.certificado_api comprobar --perfil utility [--limite N]
  .venv\\Scripts\\python.exe -m predios.certificado_api presupuesto [--perfil utility]
  .venv\\Scripts\\python.exe -m predios.certificado_api preparar 366-35594 [...]
  .venv\\Scripts\\python.exe -m predios.certificado_api recuperar 2505102431113909235
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config  # noqa: E402

RAIZ = config.PROJECT_ROOT
REGISTRO = RAIZ / "data" / "registro"
SALIDA = RAIZ / "outputs" / "reporte"
CERTIFICADOS = RAIZ / "data" / "certificados"

#: Qué círculos registrales existen y cómo se llaman, tal como los lista el portal.
CACHE_OFICINAS = REGISTRO / "oficinas_registro.json"
#: Resultado de comprobar cada matrícula en el portal.
CACHE_COMPROBACION = REGISTRO / "certificados_disponibilidad.json"
#: PIN de cada certificado ya pagado. Es la llave para volver a descargarlo.
CACHE_PIN = REGISTRO / "certificados_pin.json"
#: Tabla para el visor y para la auditoría.
TABLA = REGISTRO / "certificados_estado.csv"

PORTAL = "https://certificados.supernotariado.gov.co/certificado"
VALIDACION = PORTAL + "/external/validation/validate.snr"
RECUPERACION = PORTAL + "/external/validation/recover-certificate.snr"

#: Identificadores del formulario público. Los genera el servidor al compilar la vista,
#: así que cambian si la Superintendencia la vuelve a publicar. Comprobados el 26 de
#: agosto de 2026 contra la versión 1.60.24 del portal.
ID = {
    "oficina_boton": "formOficinas:autoCompleteOficinas_button",
    "oficina_panel": "formOficinas:autoCompleteOficinas_panel",
    "oficina_campo": "formOficinas:autoCompleteOficinas_input",
    "matricula": "formOficinas:inpMatricula",
    "buscar": "formOficinas:btnBuscar",
    "pin": "formValidation:j_idt41",
}

# --------------------------------------------------------------------------
# Tarifas. Cada cifra lleva escrito de dónde sale.
# --------------------------------------------------------------------------

#: Certificado electrónico en PDF. Artículo 15, literal a).
TARIFA_ELECTRONICO = 23_000
#: Certificado en Oficina de Registro, notaría o centro de atención. Artículo 14, a).
TARIFA_PRESENCIAL = 24_300
#: Folio de mayor extensión, más de 150 anotaciones. Artículo 14, literal b).
TARIFA_MAYOR_EXTENSION = 53_100
#: A partir de cuántas anotaciones se cobra la tarifa de mayor extensión.
ANOTACIONES_MAYOR_EXTENSION = 150

RESOLUCION = ("Resolución SNR RES-2026-001726-6 del 29 de enero de 2026, artículo 15 "
              "literal a), modificada en su vigencia por la RES-2026-001896-6 del 30 de "
              "enero de 2026; rige desde el 2 de febrero de 2026")

#: Cuántos certificados admite el portal en una sola transacción. Lo dice el propio
#: carrito: "Puedes descargar hasta 10 certificados por transacción".
POR_TRANSACCION = 10

#: Cuántos días vale el certificado y cuántos días el portal deja volver a descargarlo
#: con el PIN. Los dos plazos son de treinta días (Resolución 2968 de 2010 para la
#: validez, y el aviso del propio portal para la recuperación).
DIAS_VIGENCIA = 30

#: Canal para pedir el acceso de autoconsumo, que es la única vía masiva oficial.
CORREO_AUTOCONSUMO = "solicitud.cuposctl@supernotariado.gov.co"

MOTIVO_REQUIERE_PAGO = ("el portal liquidó el valor y espera el pago; ese paso lo tiene "
                        "que hacer una persona, este procedimiento no paga nada")
MOTIVO_SIN_RESPUESTA = ("no se ha comprobado todavía: el portal de la Superintendencia no "
                        "respondió a esta consulta")
FUENTE = ("Superintendencia de Notariado y Registro, portal de certificados, "
          "consulta pública de disponibilidad por matrícula")

# --------------------------------------------------------------------------
# JavaScript que se ejecuta dentro de la página. Se guarda aparte porque los
# identificadores de PrimeFaces llevan dos puntos y no son selectores CSS válidos.
# --------------------------------------------------------------------------

JS_VISIBLES = """()=>{const o=[];document.querySelectorAll('.ui-dialog').forEach(d=>{
  const s=getComputedStyle(d);
  if(s.display!=='none'&&s.visibility!=='hidden'&&d.innerText.trim())
    o.push({id:d.id,texto:d.innerText.trim()});});return o;}"""

JS_CERRAR = """()=>{document.querySelectorAll('.ui-widget-overlay').forEach(d=>d.remove());
  document.querySelectorAll('.ui-dialog').forEach(d=>{d.style.display='none';
  d.setAttribute('aria-hidden','true');});}"""

JS_OFICINAS = """()=>{const p=document.getElementById('formOficinas:autoCompleteOficinas_panel');
  return p?Array.from(p.querySelectorAll('li')).map(e=>e.innerText.trim()).filter(t=>t):[];}"""


def _sel(i: str) -> str:
    """Selector por identificador. Los dos puntos hay que escaparlos."""
    return "#" + i.replace(":", "\\:")


def _plano(t: str) -> str:
    """Texto comparable: sin tildes, sin espacios repetidos, en minúscula."""
    t = (t or "").lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def partir(matricula: str) -> tuple[str, str]:
    """
    Círculo registral y número de folio a partir de la matrícula. El círculo no siempre
    es numérico: Bogotá usa 50C, 50N y 50S.
    """
    m = re.match(r"^\s*([0-9A-Za-z]{2,4})\s*-\s*(\d+)\s*$", str(matricula))
    if not m:
        raise ValueError(f"matrícula mal formada: {matricula!r}; se espera 366-35594")
    return m.group(1).upper(), m.group(2)


# --------------------------------------------------------------------------
# Cachés
# --------------------------------------------------------------------------

def _leer(ruta: Path) -> dict:
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {}


def _guardar(ruta: Path, d: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def oficinas_conocidas() -> dict:
    """Los círculos registrales ya descubiertos, sin volver a abrir el portal."""
    d = _leer(CACHE_OFICINAS)
    return d.get("oficinas", d)


# --------------------------------------------------------------------------
# Navegador
# --------------------------------------------------------------------------

async def _cerrar_modales(pg) -> None:
    """
    Cierra los avisos que quedan encima sin recargar la vista. Hace falta cuando se está
    armando el carrito, porque recargar lo vaciaría.
    """
    for sel in ("#modalDialog button:has-text('Aceptar')",
                "button:has-text('Cancelar')"):
        try:
            await pg.click(sel, timeout=4_000)
            await pg.wait_for_timeout(2_000)
            break
        except Exception:
            pass
    await pg.evaluate(JS_CERRAR)
    await pg.wait_for_timeout(1_000)


async def _abrir(pg, url: str) -> None:
    """Abre una vista del portal y quita los dos avisos que tapan el formulario."""
    await pg.goto(url, wait_until="networkidle", timeout=90_000)
    await pg.wait_for_timeout(3_500)
    for sel in ("#modalAvisoPago button:has-text('Continuar')", "button:has-text('Acepto')"):
        try:
            await pg.click(sel, timeout=5_000)
            await pg.wait_for_timeout(2_000)
        except Exception:
            pass
    await pg.evaluate(JS_CERRAR)
    await pg.wait_for_timeout(1_000)


async def _leer_oficinas(pg) -> dict:
    """
    Círculos registrales que ofrece el portal, en la forma "366 - MELGAR". Es la lista
    completa de oficinas de registro del país y no cambia de un día para otro.
    """
    await pg.click(_sel(ID["oficina_boton"]))
    await pg.wait_for_timeout(7_000)
    filas = await pg.evaluate(JS_OFICINAS)
    d = {}
    for f in filas:
        m = re.match(r"^([0-9A-Za-z]{2,4})\s*-\s*(.+)$", f)
        if m:
            d[m.group(1).upper()] = m.group(2).strip()
    return d


async def _elegir_oficina(pg, circulo: str, nombre: str) -> None:
    await pg.click(_sel(ID["oficina_boton"]))
    await pg.wait_for_timeout(6_000)
    await pg.click(_sel(ID["oficina_panel"]) + " li:has-text('%s - %s')" % (circulo, nombre))
    await pg.wait_for_timeout(2_500)


def _campos(texto: str) -> dict:
    """
    Lee el cuadro que devuelve el portal. Viene como etiqueta y valor en líneas
    seguidas: Direccion / FINCA "EL POBLADO" / Circulo / MELGAR / Estado / Disponible.
    """
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    etiquetas = ("Direccion", "Dirección", "Circulo", "Círculo", "Estado")
    d = {}
    for i, l in enumerate(lineas):
        clave = l.rstrip(":")
        if clave in etiquetas and i + 1 < len(lineas):
            if lineas[i + 1].rstrip(":") not in etiquetas:
                d[clave.replace("ó", "o").replace("í", "i")] = lineas[i + 1]
    return d


async def _comprobar_una(pg, matricula: str, oficinas: dict) -> dict:
    """
    Una comprobación. Gratis y sin cuenta. Devuelve lo que el portal contesta sobre la
    matrícula: dirección, círculo y si el certificado está disponible.
    """
    circulo, folio = partir(matricula)
    nombre = oficinas.get(circulo)
    if not nombre:
        return {"estado": "error",
                "motivo": f"el círculo registral {circulo} no está en la lista de "
                          "oficinas que publica el portal"}
    await _elegir_oficina(pg, circulo, nombre)
    puesto = await pg.input_value(_sel(ID["oficina_campo"]))
    if not puesto.startswith(circulo):
        return {"estado": "error",
                "motivo": f"el formulario quedó con la oficina {puesto!r} en vez de la "
                          f"del círculo {circulo}; no se envía para no leer un resultado "
                          "que corresponde a otro lote"}
    await pg.fill(_sel(ID["matricula"]), folio)
    await pg.wait_for_timeout(600)
    escrito = await pg.input_value(_sel(ID["matricula"]))
    if escrito != folio:
        return {"estado": "error",
                "motivo": f"el formulario dejó {escrito!r} en vez de {folio!r}; no se "
                          "envía para no registrar un falso resultado"}
    await pg.click(_sel(ID["buscar"]))
    await pg.wait_for_timeout(11_000)

    for d in await pg.evaluate(JS_VISIBLES):
        t, p = d["texto"], _plano(d["texto"])
        if "informacion matricula seleccionada" in p:
            campos = _campos(t)
            est = _plano(campos.get("Estado", ""))
            return {"estado": "ok",
                    "disponible": est.startswith("disponible"),
                    "direccion": campos.get("Direccion", ""),
                    "circulo": campos.get("Circulo", nombre),
                    "estado_folio": campos.get("Estado", ""),
                    "respuesta": t[:600]}
        if "no se encontro" in p or "no existe" in p or "no fue encontrada" in p:
            return {"estado": "sin_dato",
                    "motivo": "el portal contesta que no encuentra esa matrícula en ese "
                              "círculo registral",
                    "respuesta": t[:400]}
    return {"estado": "error", "motivo": MOTIVO_SIN_RESPUESTA}


async def comprobar(matriculas, pausa: float = 1.0) -> tuple[dict, dict]:
    """
    Comprueba en el portal, gratis y sin cuenta, cuáles de estas matrículas existen y
    tienen certificado disponible. Guarda la caché lote a lote para que una caída no
    pierda lo ya preguntado. Devuelve la caché y la lista de oficinas.
    """
    from playwright.async_api import async_playwright

    cache = _leer(CACHE_COMPROBACION)
    oficinas = oficinas_conocidas()
    pendientes = [m for m in matriculas if m not in cache]
    if not pendientes and oficinas:
        return cache, oficinas

    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        ctx = await nav.new_context(locale="es-CO", viewport={"width": 1500, "height": 1250})
        pg = await ctx.new_page()
        await _abrir(pg, PORTAL)
        if not oficinas:
            oficinas = await _leer_oficinas(pg)
            if oficinas:
                _guardar(CACHE_OFICINAS, {"fecha": date.today().isoformat(),
                                          "oficinas": oficinas})
            print(f"  oficinas de registro descubiertas: {len(oficinas)}")

        for i, mat in enumerate(pendientes, 1):
            r = {"estado": "error", "motivo": "no se intentó"}
            for intento in (1, 2):
                try:
                    r = await _comprobar_una(pg, mat, oficinas)
                    break
                except Exception as e:
                    r = {"estado": "error", "motivo": str(e).splitlines()[0][:180]}
                    await pg.wait_for_timeout(6_000 * intento)
                    try:
                        await _abrir(pg, PORTAL)
                    except Exception:
                        pass
            r["fecha"] = datetime.now().isoformat(timespec="seconds")
            r["fuente"] = FUENTE
            cache[mat] = r
            _guardar(CACHE_COMPROBACION, cache)
            print(f"  [{i:>4}/{len(pendientes)}] {mat}  "
                  f"{r.get('estado_folio') or r['estado']}")
            if pausa:
                await pg.wait_for_timeout(int(pausa * 1000))
            # el portal no admite dos búsquedas seguidas en la misma vista
            await _abrir(pg, PORTAL)
        await nav.close()
    return cache, oficinas


# --------------------------------------------------------------------------
# Preparar la compra. Llega al valor a pagar y para.
# --------------------------------------------------------------------------

def _total(texto: str) -> int | None:
    """El total que liquidó el carrito, en pesos enteros. None si no lo mostró."""
    m = re.search(r"Total\s*:?\s*\$?\s*([\d\.]+),\d{2}", texto)
    if not m:
        m = re.search(r"Total\s*:?\s*\$?\s*([\d\.]+)", texto)
    return int(m.group(1).replace(".", "")) if m else None


async def preparar_compra(matriculas, capturas: Path | None = None) -> dict:
    """
    Arma el carrito con hasta POR_TRANSACCION matrículas y llega a la pantalla que
    muestra el valor a pagar. AHÍ PARA.

    No pulsa Pagar, no elige medio de pago, no escribe un correo de compra y no simula
    ninguna transacción. Devuelve lo que el portal liquidó, para que la persona que vaya
    a pagar sepa de antemano el monto exacto y por cuáles lotes.
    """
    from playwright.async_api import async_playwright

    matriculas = list(matriculas)
    if len(matriculas) > POR_TRANSACCION:
        raise ValueError(f"el portal admite {POR_TRANSACCION} certificados por "
                         f"transacción y se pidieron {len(matriculas)}; divide la lista "
                         "en tandas con presupuesto()")
    oficinas = oficinas_conocidas()
    if capturas:
        capturas.mkdir(parents=True, exist_ok=True)

    puestas, rechazadas = [], []
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        ctx = await nav.new_context(locale="es-CO", viewport={"width": 1500, "height": 1250})
        pg = await ctx.new_page()
        await _abrir(pg, PORTAL)
        if not oficinas:
            oficinas = await _leer_oficinas(pg)
            _guardar(CACHE_OFICINAS, {"fecha": date.today().isoformat(),
                                      "oficinas": oficinas})

        # AQUÍ NO SE RECARGA LA VISTA. El carrito vive en la vista JSF, no en la
        # sesión: recargar inicio.snr entre una matrícula y la siguiente lo vacía, y el
        # total vuelve a cero. Comprobado el 26 de agosto de 2026. Por eso toda la tanda
        # se arma sobre la misma página, y solo se recarga si algo falla.
        for mat in matriculas:
            try:
                r = await _comprobar_una(pg, mat, oficinas)
                if r["estado"] != "ok" or not r.get("disponible"):
                    rechazadas.append({
                        "matricula": mat,
                        "motivo": r.get("motivo") or
                                  f"el portal la reporta como "
                                  f"{r.get('estado_folio') or r['estado']}"})
                    await _cerrar_modales(pg)
                    continue
                await pg.click("button:has-text('Agregar al Carrito'), "
                               "a:has-text('Agregar al Carrito')", timeout=12_000)
                await pg.wait_for_timeout(6_000)
                for sel in ("#modalDialog button:has-text('Aceptar')",
                            "button:has-text('Aceptar')"):
                    try:
                        await pg.click(sel, timeout=5_000)
                        await pg.wait_for_timeout(3_000)
                        break
                    except Exception:
                        pass
                puestas.append(mat)
            except Exception as e:
                rechazadas.append({"matricula": mat, "motivo": str(e).splitlines()[0][:180]})
                await _cerrar_modales(pg)

        # El carrito se dibuja en la propia página en cuanto entra la primera matrícula.
        # Si viniera plegado, desplegarlo no hace daño.
        try:
            await pg.click("#panelCarrito", timeout=6_000)
            await pg.wait_for_timeout(5_000)
        except Exception:
            pass
        texto = await pg.evaluate("()=>document.body.innerText")
        if capturas:
            await pg.screenshot(path=str(capturas / "carrito.png"), full_page=True)
            (capturas / "carrito.txt").write_text(texto, encoding="utf-8")
        total = _total(texto)
        await nav.close()

    esperado = len(puestas) * TARIFA_ELECTRONICO
    return {
        "matriculas_en_carrito": puestas,
        "rechazadas": rechazadas,
        "total_liquidado_por_el_portal": total,
        "total_esperado_por_la_tarifa": esperado,
        "cuadra": (total == esperado) if total is not None else None,
        "tarifa_unitaria": TARIFA_ELECTRONICO,
        "resolucion": RESOLUCION,
        "estado": "requiere_persona",
        "motivo": MOTIVO_REQUIERE_PAGO,
        "siguiente_paso": ("una persona abre %s, repite este carrito, elige el medio de "
                           "pago y paga. El portal le devuelve un PIN por cada "
                           "certificado; ese PIN se guarda y con él se descarga el PDF "
                           "durante %d días sin volver a pagar, con la orden "
                           "'certificado_api.py recuperar'." % (PORTAL, DIAS_VIGENCIA)),
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# Recuperar por PIN. Gratis y sin cuenta.
# --------------------------------------------------------------------------

def _pares(texto: str) -> dict:
    """Lee el cuadro del PIN, que viene como 'etiqueta<tab>valor' por línea."""
    d = {}
    for l in texto.splitlines():
        if "\t" in l:
            k, v = l.split("\t", 1)
            if k.strip() and v.strip():
                d[k.strip()] = v.strip()
    return d


async def recuperar(pin: str, destino: Path | None = None) -> dict:
    """
    Con el PIN que trae impreso un certificado ya pagado, el portal devuelve sus datos y,
    dentro de los DIAS_VIGENCIA días siguientes a la compra, copia del PDF sin cobrar de
    nuevo. Pasado ese plazo sigue confirmando la transacción pero ya no entrega archivo.
    """
    from playwright.async_api import async_playwright

    destino = destino or CERTIFICADOS
    destino.mkdir(parents=True, exist_ok=True)
    bajados = []
    ruta = None
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        ctx = await nav.new_context(locale="es-CO", viewport={"width": 1500, "height": 1200},
                                    accept_downloads=True)
        pg = await ctx.new_page()
        pg.on("download", lambda d: bajados.append(d))
        await _abrir(pg, VALIDACION)
        await pg.fill(_sel(ID["pin"]), str(pin))
        await pg.wait_for_timeout(500)
        if await pg.input_value(_sel(ID["pin"])) != str(pin):
            await nav.close()
            return {"estado": "error", "motivo": "el formulario no aceptó el PIN completo"}
        await pg.click("button:has-text('Validar'), a:has-text('Validar')")
        await pg.wait_for_timeout(12_000)

        datos, texto = {}, ""
        for d in await pg.evaluate(JS_VISIBLES):
            if "informacion certificado" in _plano(d["texto"]):
                texto = d["texto"]
                datos = _pares(texto)
                break
        try:
            async with pg.expect_download(timeout=25_000):
                await pg.click("button:has-text('Descargar'), a:has-text('Descargar')",
                               timeout=8_000)
        except Exception:
            pass
        for d in bajados:
            ruta = destino / f"ctl_{pin}.pdf"
            await d.save_as(str(ruta))
        await nav.close()

    if not datos:
        return {"estado": "sin_dato",
                "motivo": "el portal no reconoció ese PIN o no devolvió información",
                "pin": pin}
    r = {"estado": "ok", "pin": pin, "datos": datos, "respuesta": texto[:800],
         "pdf": str(ruta) if ruta else None,
         "fecha": datetime.now().isoformat(timespec="seconds")}
    if not ruta:
        r["motivo_sin_pdf"] = (
            "el portal confirmó la transacción pero no ofreció el archivo. La copia por "
            "PIN solo está disponible durante los %d días siguientes a la compra; "
            "pasado ese plazo hay que volver a comprar el certificado." % DIAS_VIGENCIA)
    cache = _leer(CACHE_PIN)
    cache[str(pin)] = {k: v for k, v in r.items() if k != "respuesta"}
    _guardar(CACHE_PIN, cache)
    return r


# --------------------------------------------------------------------------
# Presupuesto
# --------------------------------------------------------------------------

def presupuesto(n_lotes: int, etiqueta: str = "lotes") -> dict:
    """Cuánto cuesta pedir el certificado de n_lotes y en cuántas tandas se pide."""
    tandas = (n_lotes + POR_TRANSACCION - 1) // POR_TRANSACCION if n_lotes else 0
    return {"que": etiqueta, "lotes": n_lotes,
            "tarifa_unitaria": TARIFA_ELECTRONICO,
            "costo": n_lotes * TARIFA_ELECTRONICO,
            "transacciones": tandas,
            "por_transaccion": POR_TRANSACCION,
            "resolucion": RESOLUCION}


def _pesos(v: int) -> str:
    return "$" + f"{v:,}".replace(",", ".")


# --------------------------------------------------------------------------
# Tabla para el visor y lecturas del reporte
# --------------------------------------------------------------------------

def escribir_tabla(cache: dict) -> Path:
    """
    Escribe lo comprobado. Solo lleva fila la matrícula sobre la que el portal contestó
    algo: la que no se pudo preguntar no se escribe como "no disponible", porque no
    haberla preguntado no es un resultado.
    """
    filas = []
    for mat, r in sorted(cache.items()):
        if r.get("estado") == "error":
            continue
        filas.append({
            "matricula_inmobiliaria": mat,
            "disponible": bool(r.get("disponible")) if r.get("estado") == "ok" else False,
            "estado_folio": r.get("estado_folio", ""),
            "direccion": r.get("direccion", ""),
            "circulo": r.get("circulo", ""),
            "costo_certificado": TARIFA_ELECTRONICO if r.get("disponible") else 0,
            "estado": r.get("estado", ""),
            "motivo": r.get("motivo", ""),
            "fecha": r.get("fecha", ""),
            "fuente": r.get("fuente", FUENTE),
        })
    REGISTRO.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(TABLA, index=False, encoding="utf-8-sig")
    return TABLA


def _es_idoneo(serie: pd.Series) -> pd.Series:
    c = serie.fillna("").str.strip().str.lower()
    return c.str.startswith("idóneo") | c.str.startswith("idoneo")


def matriculas_del_perfil(perfil: str, solo_idoneos: bool = False) -> list[str]:
    """
    Matrículas ya obtenidas para los lotes del perfil. Sin matrícula no hay certificado
    que pedir, así que esta lista es el techo real de lo que hoy se puede comprar.
    """
    ruta = REGISTRO / "matriculas.csv"
    if not ruta.exists():
        return []
    m = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    m = m[m["matricula_inmobiliaria"].notna()]
    if "estado" in m.columns:
        m = m[m["estado"].fillna("ok") == "ok"]
    if solo_idoneos:
        lotes = SALIDA / f"lotes_{perfil}.csv"
        if lotes.exists():
            d = pd.read_csv(lotes, encoding="utf-8-sig", dtype=str, low_memory=False)
            idoneos = set(d.loc[_es_idoneo(d["clasificacion"]), "CODIGO"])
            m = m[m["CODIGO"].isin(idoneos)]
    return sorted(set(m["matricula_inmobiliaria"].tolist()))


def conteo_lotes(perfil: str) -> tuple[int, int]:
    """Cuántos lotes tiene el perfil y cuántos son idóneos."""
    ruta = SALIDA / f"lotes_{perfil}.csv"
    if not ruta.exists():
        return 0, 0
    d = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str, low_memory=False)
    return len(d), int(_es_idoneo(d["clasificacion"]).sum())


# --------------------------------------------------------------------------
# Línea de órdenes
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Del número de matrícula al PDF del certificado de tradición.")
    sub = ap.add_subparsers(dest="orden", required=True)

    sub.add_parser("oficinas", help="lista los círculos registrales del portal")

    c = sub.add_parser("comprobar", help="comprueba disponibilidad, gratis y sin cuenta")
    c.add_argument("matriculas", nargs="*")
    c.add_argument("--perfil", default="utility")
    c.add_argument("--idoneos", action="store_true")
    c.add_argument("--limite", type=int)

    p = sub.add_parser("presupuesto", help="cuánto costaría pedirlos")
    p.add_argument("--perfil", default="utility")

    r = sub.add_parser("preparar", help="arma el carrito y para en el pago")
    r.add_argument("matriculas", nargs="+")

    v = sub.add_parser("recuperar", help="descarga por PIN un certificado ya pagado")
    v.add_argument("pin")

    a = ap.parse_args(argv)

    if a.orden == "oficinas":
        if not oficinas_conocidas():
            asyncio.run(comprobar([]))
        d = _leer(CACHE_OFICINAS)
        of = d.get("oficinas", d)
        print(f"{len(of)} oficinas de registro (comprobado {d.get('fecha', '')})")
        for k, v in sorted(of.items()):
            print(f"  {k:>4}  {v}")
        return 0

    if a.orden == "comprobar":
        mats = a.matriculas or matriculas_del_perfil(a.perfil, a.idoneos)
        if a.limite:
            mats = mats[:a.limite]
        if not mats:
            print("No hay matrículas que comprobar. Corre antes predios.matricula_auto.")
            return 1
        print(f"Comprobando {len(mats)} matrículas en el portal (gratis, sin cuenta)...")
        cache, _ = asyncio.run(comprobar(mats))
        ruta = escribir_tabla(cache)
        hechas = [m for m in mats if cache.get(m, {}).get("estado") == "ok"]
        disp = [m for m in hechas if cache[m].get("disponible")]
        print(f"\n  comprobadas   {len(hechas)} de {len(mats)}")
        print(f"  disponibles   {len(disp)}")
        print(f"  costarían     {_pesos(len(disp) * TARIFA_ELECTRONICO)}")
        print(f"  tabla         {ruta}")
        return 0

    if a.orden == "presupuesto":
        total, idoneos = conteo_lotes(a.perfil)
        con_mat = len(matriculas_del_perfil(a.perfil))
        con_mat_id = len(matriculas_del_perfil(a.perfil, True))
        print(f"Certificado de tradición y libertad, perfil {a.perfil}")
        print(f"Tarifa unitaria {_pesos(TARIFA_ELECTRONICO)} por certificado electrónico.")
        print(f"{RESOLUCION}.\n")
        for n, etq in ((total, "todos los lotes del reporte"),
                       (idoneos, "solo los lotes idóneos"),
                       (con_mat, "lotes con matrícula ya obtenida"),
                       (con_mat_id, "lotes idóneos con matrícula ya obtenida")):
            b = presupuesto(n, etq)
            print(f"  {etq:<38} {b['lotes']:>5} lotes   {_pesos(b['costo']):>14}   "
                  f"{b['transacciones']:>4} transacciones de {POR_TRANSACCION}")
        print(f"\nSin matrícula no hay certificado que pedir: el techo de hoy son los "
              f"{con_mat} lotes con matrícula.")
        return 0

    if a.orden == "preparar":
        cap = RAIZ / "outputs" / "certificado" / "carrito"
        res = asyncio.run(preparar_compra(a.matriculas, cap))
        print(json.dumps(res, ensure_ascii=False, indent=1))
        print("\n>>> PARA AQUÍ. " + MOTIVO_REQUIERE_PAGO)
        return 0

    if a.orden == "recuperar":
        res = asyncio.run(recuperar(a.pin))
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["estado"] == "ok" else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
