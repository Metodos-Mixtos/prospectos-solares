# -*- coding: utf-8 -*-
"""
Paso automático de matrícula inmobiliaria. Corre solo, para cualquier municipio, sin
listas escritas a mano.

QUÉ RESUELVE
------------
Hasta ahora la matrícula entraba al reporte por dos caminos que no eran del sistema: una
lista de tres portales municipales escrita a mano en outputs/matricula/cosechar_municipal.py
y una matrícula sembrada a mano desde un PDF. Un reporte no puede enseñar un dato que el
procedimiento no produce por sí mismo. Este módulo hace que lo produzca: recibe los lotes,
saca de ellos los municipios, descubre qué municipios tienen portal de impuesto predial
comprobándolo de verdad, cosecha ahí lo que haya y consulta la Superintendencia para el
resto. Lo único que pone un humano son las grillas.

LAS DOS VÍAS
------------
1. PORTAL DE IMPUESTO PREDIAL MUNICIPAL. Varias alcaldías publican su base predial con la
   matrícula, sin registro y sin captcha, en la plataforma softwaretributario.com. La
   dirección sigue un patrón fijo, así que no hace falta conocerla de antemano: se arma
   con el nombre del municipio y el de su departamento en minúsculas, sin tildes y sin
   espacios (ver PATRON), y se comprueba pidiéndole una consulta de verdad. Se acepta como
   portal solo el que responde 200 y devuelve JSON; el que devuelve una página HTML tiene
   dominio en la plataforma pero no el servicio (así se descartó Sabanalarga), y el que ni
   siquiera resuelve el certificado da un error de SSL, que es la forma limpia de decir
   que ese municipio no está en la plataforma. Es gratis, instantáneo y sin cupo.
2. CONSULTA DE ÍNDICE DE PROPIETARIOS DE LA SUPERINTENDENCIA (predios/matricula.py). Sirve
   para cualquier municipio, pero la cuenta tiene un tope diario de consultas gratuitas.
   Cuando la plataforma avisa de que se agotó, este paso PARA, deja los lotes que faltan
   sin marcar y la ejecución del día siguiente sigue donde esta se detuvo.

QUÉ SE ESCRIBE Y QUÉ NO
-----------------------
Quedarse sin cupo no es un resultado: es no haber preguntado. Por eso un lote sin
consultar NO se escribe como "sin dato" en la tabla del visor; simplemente no lleva fila,
que es como el visor dice "todavía no se ha consultado". El motivo queda escrito en la
tabla de auditoría (outputs/reporte/matriculas_<perfil>.csv), en el resumen de la corrida
y en outputs/matricula/COBERTURA.md, nunca en silencio.

Por la misma razón, que el portal municipal no traiga un lote tampoco se escribe como "sin
dato": el portal es una base municipal incompleta, no el registro. Ese lote queda pendiente
de la Superintendencia, que es quien puede contestar de verdad. Solo la Superintendencia
produce un "sin dato" definitivo, y lleva escrito su motivo: la Oficina de Registro no ha
incorporado la referencia catastral al folio.

MATRÍCULAS APORTADAS POR TERCEROS
---------------------------------
Una matrícula que llegó en un documento del propietario es verdadera, pero no la produce el
sistema. Nunca se borra: se conserva su fila y su fuente dice de dónde salió, para que el
visor la distinga de las obtenidas por consulta. Si más tarde una de las dos vías
automáticas devuelve la misma matrícula, la fila pasa a citar la vía automática y el
documento queda como corroboración.

IDEMPOTENCIA. Cada vía guarda su propia caché de resultados y la de portales descubiertos.
Correr dos veces no repite ninguna consulta ya resuelta.

Credenciales de la Superintendencia en .env. No se escriben en código, ni en informes, ni
en el registro de ejecución.

Uso:
  .venv\\Scripts\\python.exe -m predios.matricula_auto [--perfil utility]
      [--lotes RUTA_CSV] [--codigos 1,2,...] [--sin-snr] [--limite-snr N]
      [--revalidar-portales] [--solo-tabla]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config  # noqa: E402

RAIZ = config.PROJECT_ROOT
REGISTRO = RAIZ / "data" / "registro"
SALIDA = RAIZ / "outputs" / "reporte"

#: Tabla que lee el visor (reporte_predios/datos.py la carga desde aquí).
TABLA = REGISTRO / "matriculas.csv"
#: Qué municipios tienen portal y cuáles no, con la fecha en que se comprobó.
CACHE_PORTALES = REGISTRO / "portales_municipales.json"
#: Resultado de cada lote consultado en un portal municipal.
CACHE_PORTAL_LOTES = REGISTRO / "matriculas_portal.json"
#: Resultado de cada lote consultado en la Superintendencia (la escribe predios/matricula.py).
CACHE_SNR = REGISTRO / "matriculas.json"

#: Patrón de las direcciones de la plataforma de impuesto predial. Comprobado el 24 y el
#: 25 de agosto de 2026 contra los municipios de las grillas: los tres que ya se conocían
#: se redescubren solos y ninguno más responde el servicio.
PATRON = ("https://{mun}-{dep}.softwaretributario.com/swit/"
          "Impuestos.Publico.Predial.aNxGetPrediosXReferencia.aspx")

#: Días que vale un descubrimiento antes de volver a comprobarlo. Un municipio puede
#: entrar en la plataforma o salirse de ella, pero no de un día para otro.
VIGENCIA_DIAS = 30

#: Formato de una matrícula: círculo registral, guion, número de folio.
MATRICULA = re.compile(r"^\d{2,4}-\d+$")

FUENTE_PORTAL = "el portal de impuesto predial de {mun} ({dep})"
MOTIVO_PENDIENTE_CUPO = ("no se ha consultado todavía: se agotó el cupo diario de "
                         "consultas gratuitas de la Superintendencia y la tanda siguiente "
                         "continúa donde esta se detuvo")
MOTIVO_PENDIENTE_PORTAL = ("no se ha consultado todavía: el portal de impuesto predial del "
                           "municipio no trae este lote y queda a la espera de la consulta "
                           "a la Superintendencia")
MOTIVO_SIN_PORTAL = ("no se ha consultado todavía: el municipio no publica portal de "
                     "impuesto predial y queda a la espera de la consulta a la "
                     "Superintendencia")


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def _slug(t: str) -> str:
    """Nombre tal como lo escribe la plataforma: minúsculas, sin tildes, sin espacios."""
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return "".join(c for c in t.lower() if c.isalnum())


def _leer_json(ruta: Path) -> dict:
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _guardar_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _cosechar_municipal():
    """
    El módulo que ya cosecha los portales, cargado por ruta. Vive en outputs/, que no es
    un paquete importable, y aquí solo se le pide la función que ya funciona: consultar().
    """
    ruta = RAIZ / "outputs" / "matricula" / "cosechar_municipal.py"
    if not ruta.exists():
        return None
    spec = importlib.util.spec_from_file_location("cosechar_municipal", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# Municipios de la corrida, desde la DIVIPOLA
# --------------------------------------------------------------------------

def divipola_completa() -> dict[str, tuple[str, str]]:
    """
    Código DANE de cinco dígitos -> (municipio, departamento), de la base veredal del DANE.

    El nombre del municipio sale de predios/lotes.py, que ya lo carga y lo cachea; el del
    departamento se lee de la misma base, que es la única de las dos cosas que allí no se
    guarda. Diccionario vacío si la base no está disponible: sin ella no se puede armar
    ninguna dirección, y el paso lo dice en vez de inventarla.
    """
    import geopandas as gpd
    import lotes as lt

    nombres = lt.divipola()
    ver = RAIZ / "data" / "geoinfo" / "base_veredas" / "base_veredas.shp"
    if not ver.exists():
        return {}
    try:
        v = gpd.read_file(ver, ignore_geometry=True)
    except Exception:
        return {}
    cod = next((c for c in v.columns if c.upper() in ("DPTOMPIO", "MPIO_CDPMP", "COD_MPIO")), None)
    dep = next((c for c in v.columns if c.upper() in ("NOM_DEP", "NOMBRE_DPT", "DPTO_CNMBR")), None)
    mun = next((c for c in v.columns if c.upper() in ("NOMB_MPIO", "NOM_MUN", "MPIO_CNMBR")), None)
    if not (cod and dep):
        return {}
    t = v[[c for c in (cod, dep, mun) if c]].dropna(subset=[cod, dep]).drop_duplicates(subset=[cod])
    salida = {}
    for _, f in t.iterrows():
        c = str(f[cod]).split(".")[0].zfill(5)
        n = nombres.get(c) or (str(f[mun]).strip().title() if mun else "")
        salida[c] = (n, str(f[dep]).strip().title())
    return salida


def municipios_de(codigos) -> list[str]:
    """Códigos DANE de municipio presentes en los lotes, en orden y sin repetir."""
    vistos, out = set(), []
    for c in codigos:
        d = str(c).strip().zfill(30)[:5]
        if d.isdigit() and d not in vistos:
            vistos.add(d)
            out.append(d)
    return out


# --------------------------------------------------------------------------
# Descubrimiento del portal municipal
# --------------------------------------------------------------------------

def probar_portal(url: str, espera: int = 20) -> tuple[bool, str]:
    """
    Comprueba de verdad si esa dirección es el servicio de consulta predial.

    Solo cuenta como portal el que responde 200 y devuelve JSON. Un 200 con página HTML
    significa que el municipio tiene dominio en la plataforma pero no este servicio; un
    error de SSL o de conexión significa que el municipio no está en la plataforma.
    """
    try:
        r = requests.get(url, params={"ImpCod": "IPU", "term": "0" * 25}, timeout=espera)
    except Exception as e:
        return False, f"el municipio no está en esa plataforma ({type(e).__name__})"
    if r.status_code != 200:
        return False, f"la plataforma respondió {r.status_code} en esa dirección"
    try:
        datos = json.loads(r.text)
    except Exception:
        return False, ("la dirección existe pero devuelve una página, no el servicio de "
                       "consulta predial")
    if not isinstance(datos, list):
        return False, "la dirección responde algo que no es la lista de predios"
    return True, "el portal responde el servicio de consulta predial"


def descubrir_portales(danes: list[str], forzar: bool = False,
                       hoy: str | None = None) -> dict[str, dict]:
    """
    Para cada municipio de la corrida arma la dirección con el patrón y la comprueba.
    Guarda el resultado con la fecha para no volver a probar en cada corrida.
    """
    hoy = hoy or date.today().isoformat()
    cache = _leer_json(CACHE_PORTALES)
    div = divipola_completa()
    if not div:
        print("  No se pudo leer la DIVIPOLA (data/geoinfo/base_veredas). Sin ella no se "
              "puede descubrir ningún portal: esta corrida va entera a la Superintendencia.")
        return {}
    nuevos = 0
    for d in danes:
        previo = cache.get(d)
        if previo and not forzar:
            try:
                dias = (date.fromisoformat(hoy) - date.fromisoformat(previo["fecha"])).days
            except Exception:
                dias = VIGENCIA_DIAS + 1
            if dias < VIGENCIA_DIAS:
                continue
        par = div.get(d)
        if not par:
            cache[d] = {"municipio": None, "departamento": None, "url": None,
                        "tiene_portal": False, "fecha": hoy,
                        "motivo": "el código no aparece en la DIVIPOLA"}
            continue
        mun, dep = par
        url = PATRON.format(mun=_slug(mun), dep=_slug(dep))
        ok, motivo = probar_portal(url)
        cache[d] = {"municipio": mun, "departamento": dep, "url": url,
                    "tiene_portal": ok, "fecha": hoy, "motivo": motivo}
        nuevos += 1
        print(f"  {d}  {mun:<22.22s} {'PORTAL' if ok else 'sin portal':<11s} {motivo}")
    if nuevos:
        _guardar_json(CACHE_PORTALES, cache)
    return {d: cache[d] for d in danes if d in cache}


# --------------------------------------------------------------------------
# Vía 1: cosecha en el portal municipal
# --------------------------------------------------------------------------

def cosechar_portales(lotes: pd.DataFrame, portales: dict[str, dict],
                      hoy: str | None = None) -> dict:
    """
    Consulta en cada portal los lotes de su municipio que aún no tienen respuesta suya.

    Reutiliza consultar() de outputs/matricula/cosechar_municipal.py, que es el código que
    ya se comprobó contra estos portales. Los lotes que el portal no trae quedan como
    "sin_portal" y siguen su camino a la Superintendencia: el portal es una base municipal
    incompleta, no el registro, así que su silencio no es un "sin dato".
    """
    hoy = hoy or date.today().isoformat()
    cm = _cosechar_municipal()
    if cm is None:
        print("  No está outputs/matricula/cosechar_municipal.py: no se cosecha ningún portal.")
        return _leer_json(CACHE_PORTAL_LOTES)
    cache = _leer_json(CACHE_PORTAL_LOTES)
    codigos = lotes["CODIGO"]
    for d, p in portales.items():
        if not p.get("tiene_portal"):
            continue
        sub = [c for c in codigos if c.startswith(d)]
        pend = [c for c in sub if c not in cache]
        if not pend:
            print(f"  {p['municipio']:<22.22s} nada pendiente ({len(sub)} lotes ya resueltos)")
            continue
        ok = 0
        for i, c in enumerate(pend):
            mat, extra = cm.consultar(p["url"], c)
            if mat and MATRICULA.match(mat):
                cache[c] = {"estado": "ok", "matricula": mat, "nombre_registro": extra,
                            "fuente": FUENTE_PORTAL.format(mun=p["municipio"],
                                                           dep=p["departamento"]),
                            "fecha": hoy}
                ok += 1
            else:
                cache[c] = {"estado": "sin_portal", "motivo": extra, "fecha": hoy}
            if i and i % 40 == 0:
                _guardar_json(CACHE_PORTAL_LOTES, cache)
                time.sleep(0.5)
        _guardar_json(CACHE_PORTAL_LOTES, cache)
        print(f"  {p['municipio']:<22.22s} {ok:>4} matrículas de {len(pend)} lotes consultados")
    return cache


# --------------------------------------------------------------------------
# Vía 2: consulta a la Superintendencia
# --------------------------------------------------------------------------

def consultar_snr(pendientes: list[str], limite: int | None = None) -> tuple[dict, bool]:
    """
    Pregunta a la Superintendencia por los lotes que ninguna otra vía resolvió.

    Devuelve la caché y si se agotó el cupo diario. Reutiliza predios/matricula.py entero:
    la sesión, la lectura del aviso visible y la parada por cupo ya están resueltas allí,
    incluido el cuidado de no dar por vacía una consulta leyendo los avisos ocultos.
    """
    import matricula as snr

    cache = snr.leer_cache()
    if not pendientes:
        return cache, False
    if limite:
        pendientes = pendientes[:limite]
    usuario, clave = snr.credenciales()
    print(f"  Consultando {len(pendientes)} lotes. La cuenta tiene un tope diario de "
          "consultas gratuitas, así que la tanda puede detenerse antes.")
    import asyncio
    cache, agotada = asyncio.run(snr.recorrer(pendientes, usuario, clave, cache))
    return cache, agotada


# --------------------------------------------------------------------------
# Tabla del visor
# --------------------------------------------------------------------------

COLUMNAS = ["CODIGO", "matricula_inmobiliaria", "fuente", "fecha", "estado", "motivo"]

#: Qué gana cuando dos vías hablan del mismo lote. Una matrícula obtenida por consulta
#: automática desplaza a la misma matrícula tomada de un documento aportado, porque
#: entonces el sistema sí la produce solo; un "sin dato" nunca desplaza a una matrícula.
_RANGO = {"ok_auto": 3, "ok_aportada": 2, "sin_dato": 1}


def _rango(fila: dict) -> int:
    if fila.get("estado") == "ok":
        return _RANGO["ok_aportada"] if fila.get("aportada") else _RANGO["ok_auto"]
    return _RANGO.get(fila.get("estado"), 0)


def _leer_tabla_previa() -> dict[str, dict]:
    """
    Lo que ya había en la tabla del visor. Se conserva para no perder ninguna matrícula
    que no venga de las dos vías automáticas, como las aportadas por el propietario.
    """
    if not TABLA.exists():
        return {}
    t = pd.read_csv(TABLA, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    t.columns = [c.lstrip("﻿").strip().lower() for c in t.columns]
    out = {}
    for _, f in t.iterrows():
        c = str(f.get("codigo", "")).strip().zfill(30)
        if not c.isdigit():
            continue
        fuente = f.get("fuente") or None
        plano = (fuente or "").lower()
        automatica = ("superintendencia" in plano or "portal de impuesto predial" in plano)
        out[c] = {"matricula": f.get("matricula_inmobiliaria") or None,
                  "fuente": fuente,
                  "fecha": (f.get("fecha") or "")[:10] or None,
                  "estado": f.get("estado") or None,
                  "motivo": f.get("motivo") or None,
                  "aportada": not automatica}
    return out


def sembrar_portal_desde_tabla(previa: dict, cache: dict) -> dict:
    """
    Primera corrida después de este cambio: lo que ya había cosechado a mano el script de
    portales pasa a la caché de esa vía, para no volver a preguntar lo ya preguntado.
    """
    nuevos = 0
    for c, f in previa.items():
        if c in cache:
            continue
        if "portal de impuesto predial" not in (f.get("fuente") or "").lower():
            continue
        if f.get("matricula"):
            cache[c] = {"estado": "ok", "matricula": f["matricula"],
                        "fuente": f["fuente"], "fecha": f.get("fecha")}
        else:
            cache[c] = {"estado": "sin_portal", "fecha": f.get("fecha"),
                        "motivo": "el portal municipal no trae este lote"}
        nuevos += 1
    if nuevos:
        _guardar_json(CACHE_PORTAL_LOTES, cache)
        print(f"  {nuevos} respuestas de portal ya obtenidas antes pasan a la caché de "
              "esa vía: no se vuelven a preguntar.")
    return cache


def consolidar(codigos: list[str], previa: dict, portal: dict, snr: dict) -> dict[str, dict]:
    """
    Une lo que dice cada vía sobre cada lote y se queda con la mejor respuesta.

    Solo entran a la tabla del visor las respuestas que de verdad son respuestas: una
    matrícula, o el "sin dato" de la Superintendencia con su motivo. Que el portal no
    traiga un lote, o que la tanda se quedara sin cupo, no son respuestas y no llevan fila.
    """
    filas: dict[str, dict] = {}
    # Los lotes de corridas anteriores que no están en esta no se tocan ni se pierden:
    # esta corrida no sabe nada de ellos, y borrarlos sería borrar un dato verdadero.
    fuera = [c for c in previa if c not in set(codigos)]

    def poner(codigo: str, fila: dict):
        if not fila:
            return
        if codigo not in filas or _rango(fila) > _rango(filas[codigo]):
            filas[codigo] = fila

    for c in fuera:
        p = previa[c]
        if p.get("matricula") or (p.get("estado") == "sin_dato"
                                  and "superintendencia" in (p.get("fuente") or "").lower()):
            filas[c] = dict(p)

    for c in codigos:
        # 1. Lo que ya estaba en la tabla. Una matrícula nunca se pierde, venga de donde
        #    venga. Un "sin dato" solo se conserva si lo dijo la Superintendencia: es la
        #    única que puede afirmar que no hay folio con esa referencia catastral. Que el
        #    portal municipal no traiga un lote no es un "sin dato", y escribirlo como tal
        #    haría que la ficha dijera que se consultó el registro cuando no se consultó.
        p = previa.get(c)
        if p and p.get("matricula"):
            poner(c, dict(p))
        elif p and p.get("estado") == "sin_dato" and "superintendencia" in (p.get("fuente") or "").lower():
            poner(c, dict(p))
        # 2. Portal municipal.
        r = portal.get(c)
        if r and r.get("estado") == "ok":
            poner(c, {"matricula": r["matricula"], "fuente": r["fuente"],
                      "fecha": r.get("fecha"), "estado": "ok", "motivo": None})
        # 3. Superintendencia.
        s = snr.get(c)
        if s and s.get("estado") == "ok":
            poner(c, {"matricula": s["matricula"], "fuente": s.get("fuente"),
                      "fecha": (s.get("fecha") or "")[:10], "estado": "ok", "motivo": None})
        elif s and s.get("estado") == "sin_dato":
            poner(c, {"matricula": None, "fuente": s.get("fuente"),
                      "fecha": (s.get("fecha") or "")[:10], "estado": "sin_dato",
                      "motivo": s.get("motivo")})
    return filas


def escribir_tabla(filas: dict[str, dict]) -> Path:
    """Tabla que lee el visor, con la fuente diciendo por qué vía salió cada matrícula."""
    REGISTRO.mkdir(parents=True, exist_ok=True)
    t = pd.DataFrame([{"CODIGO": c,
                       "matricula_inmobiliaria": f.get("matricula") or "",
                       "fuente": f.get("fuente") or "",
                       "fecha": f.get("fecha") or "",
                       "estado": f.get("estado") or "",
                       # El motivo solo explica una ausencia. Donde hay matrícula la
                       # casilla va vacía: escribir ahí un motivo diría lo contrario.
                       "motivo": "" if f.get("matricula") else (f.get("motivo") or "")}
                      for c, f in sorted(filas.items())], columns=COLUMNAS)
    t.to_csv(TABLA, index=False, encoding="utf-8-sig")
    return TABLA


def escribir_auditoria(lotes: pd.DataFrame, filas: dict, portal: dict, snr_cache: dict,
                       portales: dict, perfil: str) -> Path:
    """
    Todos los lotes con su estado y, donde no hay matrícula, el motivo escrito. Aquí sí
    figuran los que quedaron pendientes, con la razón: quedarse sin cupo no se calla.
    """
    SALIDA.mkdir(parents=True, exist_ok=True)
    cols = [c for c in ("cell_id", "CODIGO", "departamento", "municipio", "nombre_predio",
                        "area_ha") if c in lotes.columns]
    out = []
    for _, f in lotes[cols].iterrows():
        c = f["CODIGO"]
        r = filas.get(c)
        fila = dict(f)
        if r and r.get("matricula"):
            fila.update(matricula_inmobiliaria=r["matricula"], estado="ok",
                        via=r.get("fuente"), motivo="")
        elif r and r.get("estado") == "sin_dato":
            fila.update(matricula_inmobiliaria="", estado="sin dato",
                        via=r.get("fuente"), motivo=r.get("motivo"))
        else:
            d = c[:5]
            fallo = snr_cache.get(c, {}).get("estado") in ("error", "sin_respuesta")
            if fallo:
                motivo = ("la consulta a la Superintendencia no se completó: "
                          + (snr_cache[c].get("motivo") or "sin aviso legible")
                          + "; se reintenta en la corrida siguiente")
            elif c in snr_cache:
                motivo = "consultado sin respuesta clasificable; se reintenta"
            elif portal.get(c, {}).get("estado") == "sin_portal":
                motivo = MOTIVO_PENDIENTE_PORTAL
            elif not portales.get(d, {}).get("tiene_portal"):
                motivo = MOTIVO_SIN_PORTAL
            else:
                motivo = MOTIVO_PENDIENTE_CUPO
            fila.update(matricula_inmobiliaria="", estado="pendiente", via="",
                        motivo=motivo)
        out.append(fila)
    ruta = SALIDA / f"matriculas_{perfil}.csv"
    pd.DataFrame(out).to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


# --------------------------------------------------------------------------
# Paso completo
# --------------------------------------------------------------------------

def ejecutar(lotes: pd.DataFrame, perfil: str = "utility", con_snr: bool = True,
             limite_snr: int | None = None, revalidar: bool = False,
             solo_tabla: bool = False) -> dict:
    """
    El paso entero, tal como lo llama el procedimiento. Devuelve el resumen de la corrida.

    Nunca levanta: si una vía falla, se anota y el procedimiento sigue. Un reporte sin
    matrícula es un reporte incompleto; un procedimiento detenido no es un reporte.
    """
    hoy = date.today().isoformat()
    lotes = lotes.copy()
    lotes["CODIGO"] = lotes["CODIGO"].astype(str).str.strip().str.zfill(30)
    codigos = list(dict.fromkeys(lotes["CODIGO"]))
    danes = municipios_de(codigos)

    resumen = {"fecha": hoy, "perfil": perfil, "lotes": len(codigos),
               "municipios": len(danes), "cupo_agotado": False, "errores": []}

    previa = _leer_tabla_previa()
    portales: dict[str, dict] = {}
    portal: dict = sembrar_portal_desde_tabla(previa, _leer_json(CACHE_PORTAL_LOTES))
    if not solo_tabla:
        print(f"\n  Municipios de la corrida: {len(danes)}. Buscando portal de impuesto "
              "predial de cada uno.")
        try:
            portales = descubrir_portales(danes, forzar=revalidar, hoy=hoy)
        except Exception as e:
            resumen["errores"].append(f"descubrimiento de portales: {e}")
            print(f"  El descubrimiento de portales falló ({e}). Se sigue sin él.")
        con_portal = [d for d, p in portales.items() if p.get("tiene_portal")]
        print(f"  Con portal: {len(con_portal)} de {len(danes)}.")
        if con_portal:
            print("\n  Cosecha en los portales municipales:")
            try:
                portal = cosechar_portales(lotes, portales, hoy=hoy)
            except Exception as e:
                resumen["errores"].append(f"cosecha en portales: {e}")
                print(f"  La cosecha en portales falló ({e}). Se sigue sin ella.")
    else:
        portales = {d: v for d, v in _leer_json(CACHE_PORTALES).items() if d in danes}

    snr_cache = _leer_json(CACHE_SNR)
    resueltos = {c for c in codigos
                 if portal.get(c, {}).get("estado") == "ok"
                 or snr_cache.get(c, {}).get("estado") in ("ok", "sin_dato")
                 or (previa.get(c, {}).get("matricula"))}
    pendientes = [c for c in codigos if c not in resueltos]

    if con_snr and not solo_tabla and pendientes:
        print(f"\n  Quedan {len(pendientes)} lotes sin matrícula. Consulta a la "
              "Superintendencia de Notariado y Registro:")
        try:
            snr_cache, agotada = consultar_snr(pendientes, limite=limite_snr)
            resumen["cupo_agotado"] = agotada
        except SystemExit as e:
            resumen["errores"].append(f"Superintendencia: {e}")
            print(f"  No se pudo consultar la Superintendencia: {e}. Se sigue sin ella.")
        except Exception as e:
            resumen["errores"].append(f"Superintendencia: {type(e).__name__}: {e}")
            print(f"  La consulta a la Superintendencia falló ({type(e).__name__}). "
                  "Se sigue sin ella.")
    elif not con_snr:
        print("\n  Consulta a la Superintendencia desactivada en esta corrida (--sin-snr).")

    filas = consolidar(codigos, previa, portal, snr_cache)
    ruta_visor = escribir_tabla(filas)
    ruta_aud = escribir_auditoria(lotes, filas, portal, snr_cache, portales, perfil)

    con = sum(1 for c in codigos if filas.get(c, {}).get("matricula"))
    sind = sum(1 for c in codigos if filas.get(c, {}).get("estado") == "sin_dato")
    resumen.update(con_matricula=con, sin_dato=sind,
                   pendientes=len(codigos) - con - sind,
                   con_portal=sum(1 for p in portales.values() if p.get("tiene_portal")),
                   tabla=str(ruta_visor), auditoria=str(ruta_aud))

    por_via: dict[str, int] = {}
    for c in codigos:
        f = filas.get(c) or {}
        if f.get("matricula"):
            por_via[f.get("fuente") or "sin fuente anotada"] = \
                por_via.get(f.get("fuente") or "sin fuente anotada", 0) + 1
    resumen["por_via"] = por_via

    print()
    print("=" * 74)
    print(f"  lotes de la corrida                {len(codigos):>5}")
    print(f"  municipios                         {len(danes):>5}")
    print(f"  municipios con portal              {resumen['con_portal']:>5}")
    print(f"  con matrícula                      {con:>5}")
    print(f"  sin dato en el registro            {sind:>5}")
    print(f"  pendientes de consulta             {resumen['pendientes']:>5}")
    print()
    for via, n in sorted(por_via.items(), key=lambda x: -x[1]):
        print(f"    {n:>5}  {via}")
    print()
    if resumen["cupo_agotado"]:
        print("  Se agotó el cupo diario gratuito de la Superintendencia. Los lotes que")
        print("  faltan quedan sin fila, con su motivo escrito en la tabla de auditoría,")
        print("  y la corrida de mañana sigue donde esta se detuvo. No se escribe 'sin")
        print("  dato' por no haber preguntado: eso sería un dato falso.")
    for e in resumen["errores"]:
        print(f"  AVISO: {e}")
    print(f"  tabla del visor -> {ruta_visor}")
    print(f"  auditoría       -> {ruta_aud}")
    return resumen


def paso(perfil: str = "utility", lotes_csv: Path | None = None, **kw) -> dict:
    """
    Punto de entrada del procedimiento. Corre después de caracterizar los lotes y antes de
    generar el visor. No levanta nunca: devuelve el resumen, con los errores dentro.
    """
    ruta = Path(lotes_csv) if lotes_csv else SALIDA / f"lotes_{perfil}.csv"
    if not ruta.exists():
        print(f"  No existe {ruta}. El paso de matrícula no corre y los lotes quedan sin "
              "dato; el motivo queda escrito aquí.")
        return {"errores": [f"no existe {ruta}"], "con_matricula": 0}
    lotes = pd.read_csv(ruta, dtype={"CODIGO": str}, encoding="utf-8-sig")
    try:
        return ejecutar(lotes, perfil=perfil, **kw)
    except Exception as e:
        print(f"  El paso de matrícula falló ({type(e).__name__}: {e}). El procedimiento "
              "sigue y los lotes quedan sin matrícula.")
        return {"errores": [f"{type(e).__name__}: {e}"], "con_matricula": 0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Matrícula inmobiliaria de cada lote, automática: portal de impuesto "
                    "predial donde exista, Superintendencia donde no.")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--lotes", default=None, help="CSV de lotes; por defecto el del perfil")
    ap.add_argument("--codigos", default=None,
                    help="lista de códigos separados por comas, en vez del CSV")
    ap.add_argument("--sin-snr", action="store_true",
                    help="no consulta la Superintendencia en esta corrida")
    ap.add_argument("--limite-snr", type=int, default=None,
                    help="consulta como mucho N lotes en la Superintendencia")
    ap.add_argument("--revalidar-portales", action="store_true",
                    help="vuelve a comprobar los portales aunque la caché esté vigente")
    ap.add_argument("--solo-tabla", action="store_true",
                    help="no consulta nada: solo rehace las tablas con lo ya guardado")
    a = ap.parse_args(argv)

    if a.codigos:
        lotes = pd.DataFrame({"CODIGO": [c.strip() for c in a.codigos.split(",") if c.strip()]})
        ejecutar(lotes, perfil=a.perfil, con_snr=not a.sin_snr, limite_snr=a.limite_snr,
                 revalidar=a.revalidar_portales, solo_tabla=a.solo_tabla)
        return 0

    r = paso(perfil=a.perfil, lotes_csv=a.lotes, con_snr=not a.sin_snr,
             limite_snr=a.limite_snr, revalidar=a.revalidar_portales,
             solo_tabla=a.solo_tabla)
    return 0 if not r.get("errores") else 0


if __name__ == "__main__":
    sys.exit(main())
