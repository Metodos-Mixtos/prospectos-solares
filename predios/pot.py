"""
Norma urbana del lote: categoría de suelo rural y uso principal según el POT/PBOT/EOT
municipal, desde los geoservicios nacionales del IGAC (modelo LADM-COL POT).

Capas (mapas2.igac.gov.co/server/rest/services/ordenamiento/, geometría en EPSG:9377):
  zonificacionsuelorural/MapServer/0   categoría rural (16 valores) y uso principal (20),
                                       761 municipios; usos prohibido/condicionado poblados
                                       en <6%, así que la solar casi nunca se prueba
                                       prohibida por máquina: se infiere de la categoría.
  clasificacionsuelopot/FeatureServer/1  urbano/rural/expansión y el acto administrativo
                                       que lo adopta; servicio inestable, con reintento.
  datosnacionalespot/MapServer/0       tipo de instrumento, año de adopción, revisión y
                                       si hay cartografía; el municipio va en MDANMCodig.
Se cruza el polígono del lote (reparto de área por categoría), no solo el centroide.

Tres estados de la norma, porque no responder no es lo mismo que no tener instrumento:
  verificado        la zonificación rural cubre el lote y dice qué categoría le asigna.
  sin cartografía   el municipio tiene instrumento adoptado y registrado, pero su
                    zonificación rural no está publicada en el geoservicio. Si además el
                    instrumento superó su vigencia de largo plazo, se rotula "POT vencido
                    sin cartografía": la categoría del suelo no se puede leer aquí y el
                    municipio puede revisar el instrumento durante la vida del proyecto.
  sin instrumento   el municipio no aparece en la capa nacional de instrumentos.
Este hueco es de la fuente, no del terreno: se anota y se advierte, y no cambia la clase
del lote. La cobertura por municipio se comprueba contando polígonos de zonificación con
el código del municipio, no suponiéndola del campo de cartografía del instrumento, que
para San Marcos y Caimito dice "Si" y sin embargo no hay un solo polígono publicado.
Caché por lote en data/pot/<CODIGO>.json.
Uso: python -m predios.pot [--perfil utility] [--forzar]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
CACHE = config.PROJECT_ROOT / "data" / "pot"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
BASE = "https://mapas2.igac.gov.co/server/rest/services/ordenamiento"
ZONIF_URL = f"{BASE}/zonificacionsuelorural/MapServer/0/query"
CLASIF_URL = f"{BASE}/clasificacionsuelopot/FeatureServer/1/query"
DATOS_URL = f"{BASE}/datosnacionalespot/MapServer/0/query"

#: Dominios LADM-COL POT (Resolución IGAC 0058 de 2025), leídos del servicio.
CATEGORIA = {
    1: "Suelo rural productivo, agropecuario", 2: "Suelo rural productivo, forestal",
    3: "Suelo rural productivo, minería e hidrocarburos",
    4: "Desarrollo restringido, suburbano", 5: "Desarrollo restringido, corredor vial suburbano",
    6: "Desarrollo restringido, centro poblado rural", 7: "Desarrollo restringido, vivienda campestre",
    8: "Desarrollo restringido, equipamiento",
    9: "Protección, áreas del SINAP", 10: "Protección, áreas de reserva forestal",
    11: "Protección, áreas de manejo especial", 12: "Protección, áreas de importancia ecosistémica",
    13: "Protección, producción agropecuaria y explotación de recursos naturales",
    14: "Protección, sistema de servicios públicos", 15: "Protección, amenaza y riesgo no mitigable",
    16: "Protección, patrimonio cultural",
}
USO = {
    1: "Agrícola", 2: "Pecuario", 3: "Forestal", 4: "Acuicultura", 5: "Minería", 6: "Hidrocarburos",
    7: "Residencial", 8: "Dotacional institucional", 9: "Industrial", 10: "Turismo",
    11: "Comercial y servicios", 12: "Centro poblado", 13: "Conservación, preservación",
    14: "Conservación", 15: "Conservación, restauración", 16: "Conservación, conocimiento",
    17: "Conservación, uso sostenible", 18: "Conservación, disfrute", 19: "Histórico cultural",
    20: "Otro",
}
CLASIF = {1: "Urbano", 2: "Rural", 3: "Expansión urbana"}

#: Lectura para el proyecto solar por categoría: 'rojo' descarta salvo prueba documental,
#: 'ambar' condiciona (permiso o instrumento), 'verde' compatible en principio.
SEMAFORO_CATEGORIA = {
    1: "verde", 2: "ambar", 3: "ambar", 4: "verde", 5: "verde", 6: "rojo", 7: "ambar", 8: "ambar",
    9: "rojo", 10: "rojo", 11: "rojo", 12: "rojo", 13: "ambar", 14: "ambar", 15: "rojo", 16: "rojo",
}


#: Superficie del lote en categorías de protección, en porcentaje, que pone el semáforo en
#: rojo y en ámbar. Los mismos cortes que usa la clasificación del lote.
PROTECCION_ROJO_PCT = 50.0
PROTECCION_AMBAR_PCT = 10.0

#: Porcentaje del lote que la zonificación rural tiene que cubrir para dar por leída la
#: norma del lote. Por debajo, lo que hay es un roce de linderos entre capas de escala
#: distinta y la categoría del suelo se sigue pidiendo por certificado.
COBERTURA_MIN_PCT = 50.0

#: Años de vigencia del contenido de largo plazo del instrumento de ordenamiento. La
#: Ley 388 de 1997 la fija en tres periodos constitucionales de la administración
#: municipal; con periodos de cuatro años son doce, el plazo más largo posible.
VIGENCIA_LARGO_PLAZO_ANOS = 12

#: Etiquetas de los tres estados de la norma, tal como se leen en el reporte.
ESTADO_VERIFICADO = "POT verificado"
ESTADO_SIN_CARTOGRAFIA = "POT sin cartografía"
ESTADO_VENCIDO_SIN_CARTOGRAFIA = "POT vencido sin cartografía"
ESTADO_SIN_COBERTURA_LOTE = "POT sin cobertura en el lote"
ESTADO_SIN_INSTRUMENTO = "Sin instrumento de ordenamiento registrado"
ESTADO_SIN_RESPUESTA = "Consulta del POT sin respuesta"


#: Segundos por petición. El servidor del IGAC a veces se cuelga en vez de fallar; con un
#: tope corto la capa queda como error y se reintenta en la siguiente corrida.
TIMEOUT = 45


def _query(url: str, params: dict, intentos: int = 3) -> list[dict]:
    """Consulta con reintento; el servicio de clasificación devuelve 500 con frecuencia."""
    import time
    import requests
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.get(url, headers=UA, params={**params, "f": "json"}, timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"].get("message", "error"))
            return [f["attributes"] for f in d.get("features", [])]
        except Exception as exc:
            ultimo = exc
            time.sleep(2 * (i + 1))
    raise ultimo


def _a_ctm12(geom):
    """Geometría a EPSG:9377 (CTM12), que es lo que exigen estas capas."""
    from shapely.ops import transform
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 9377, always_xy=True)
    return transform(tr.transform, geom)


def _query_poligono(url: str, geom_wgs84, campos: str) -> list[dict]:
    """
    Intersección por polígono (simplificado a 5 m, por POST: la geometría no cabe en
    una URL); devuelve atributos y la geometría para repartir área.
    """
    import requests
    from entorno import anillos_esri
    esri = anillos_esri(geom_wgs84, wkid=9377, transformar=_a_ctm12)
    # maxAllowableOffset generaliza los polígonos devueltos a 5 m: cuatro veces menos bytes
    # sin cambiar el reparto de área a la escala del lote.
    r = requests.post(url, headers=UA, timeout=TIMEOUT, data={
        "geometry": json.dumps(esri), "geometryType": "esriGeometryPolygon", "inSR": 9377,
        "spatialRel": "esriSpatialRelIntersects", "outFields": campos, "returnGeometry": "true",
        "outSR": 9377, "maxAllowableOffset": 5, "f": "json"})
    r.raise_for_status()
    d = r.json()
    if "error" in d:
        raise RuntimeError(d["error"].get("message", "error"))
    return d.get("features", [])


def _zonificacion(geom_wgs84, g_ctm12, area_total: float) -> dict:
    """Zonificación rural por polígono: reparto de área por categoría y uso, usos prohibidos y condicionados."""
    from shapely.geometry import Polygon, MultiPolygon
    feats = _query_poligono(ZONIF_URL, geom_wgs84,
                            "Tipo_Categoria_Rural,Uso_Principal,Uso_Prohibido,Uso_Condicionado_Restringido,Mp_Codigo")
    from shapely.ops import unary_union
    # El servicio publica polígonos superpuestos de la misma categoría en algunos
    # municipios (en Buenavista, Córdoba, una categoría llegaba a sumar el 127% del lote).
    # Se unen antes de medir, de modo que cada metro cuadrado cuente una sola vez.
    por_cat: dict[str, list] = {}
    por_uso: dict[str, list] = {}
    prohib = set(); cond = set()
    for f in feats:
        a = f["attributes"]; geo = f.get("geometry", {})
        rings = geo.get("rings") or []
        if not rings:
            continue
        poly = MultiPolygon([Polygon(r) for r in rings if len(r) >= 4]) if len(rings) > 1 else Polygon(rings[0])
        try:
            poly = poly.buffer(0)
        except Exception:
            continue
        por_cat.setdefault(str(a.get("Tipo_Categoria_Rural")), []).append(poly)
        por_uso.setdefault(str(a.get("Uso_Principal")), []).append(poly)
        if a.get("Uso_Prohibido"): prohib.add(str(a["Uso_Prohibido"]))
        if a.get("Uso_Condicionado_Restringido"): cond.add(str(a["Uso_Condicionado_Restringido"]))

    def _area(polis):
        try:
            return unary_union(polis).intersection(g_ctm12).area
        except Exception:
            return 0.0

    reparto = {k: v for k, v in ((k, _area(ps)) for k, ps in por_cat.items()) if v > 0}
    usos = {k: v for k, v in ((k, _area(ps)) for k, ps in por_uso.items()) if v > 0}
    return {"reparto_pct": {k: round(100 * v / area_total, 1) for k, v in reparto.items()},
            "usos_pct": {k: round(100 * v / area_total, 1) for k, v in usos.items()},
            "prohibido": sorted(prohib), "condicionado": sorted(cond), "n": len(feats)}


_POT_MUNICIPAL: dict[str, list] = {}
_ZONIF_MUNICIPAL: dict[str, int | None] = {}


def zonificacion_municipal(dane: str) -> int | None:
    """
    Cuántos polígonos de zonificación rural publica el IGAC para el municipio. Cero
    significa que la capa vectorial no existe para ese municipio, que es distinto de que
    el municipio no tenga instrumento de ordenamiento. None si el servicio no responde.
    Una consulta por municipio, no por lote.
    """
    if dane not in _ZONIF_MUNICIPAL:
        import requests
        try:
            r = requests.get(ZONIF_URL, headers=UA, timeout=TIMEOUT, params={
                "where": f"Mp_Codigo='{dane}'", "returnCountOnly": "true", "f": "json"})
            r.raise_for_status()
            d = r.json()
            _ZONIF_MUNICIPAL[dane] = None if "error" in d else int(d.get("count", 0))
        except Exception:
            _ZONIF_MUNICIPAL[dane] = None
    return _ZONIF_MUNICIPAL[dane]


def _instrumento(pm: list[dict]) -> dict:
    """
    Lee la ficha del instrumento de ordenamiento del municipio tal como la publica el
    IGAC. Solo copia lo que el servicio trae; un campo ausente queda en None y nunca se
    sustituye por una aproximación.
    """
    if not pm:
        return {"hay": False}
    a = pm[0]
    def _n(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return None
    anio = _n(a.get("AprobacionAño"))
    rev = _n(a.get("RevisionAño"))
    tipo = (a.get("PotTipo") or "").strip() or None
    acto_tipo = (a.get("AprobacionTipo") or "").strip()
    numero = str(a.get("NUMERO") or "").strip()
    acto = " ".join(x for x in (acto_tipo, numero) if x) or None
    if acto and anio:
        acto = f"{acto} de {anio}"
    anios = (date.today().year - anio) if anio else None
    return {"hay": True, "municipio": (a.get("MDANMNombre") or "").strip() or None,
            "tipo": tipo, "acto": acto, "anio": anio, "revision_anio": rev,
            "revision_tipo": (a.get("Revision") or "").strip() or None,
            "anios": anios,
            "vencido": (anios is not None and anios > VIGENCIA_LARGO_PLAZO_ANOS)}


def _frase_instrumento(ins: dict) -> str:
    """Cómo se nombra el instrumento del municipio en una frase, sin siglas sueltas."""
    if not ins.get("hay"):
        return "el IGAC no registra instrumento de ordenamiento para el municipio"
    partes = []
    if ins["tipo"] and ins["acto"]:
        partes.append(f"{ins['tipo']} adoptado por {ins['acto']}")
    elif ins["tipo"] and ins["anio"]:
        partes.append(f"{ins['tipo']} de {ins['anio']}")
    elif ins["tipo"]:
        partes.append(ins["tipo"])
    elif ins["acto"]:
        partes.append(ins["acto"])
    else:
        partes.append("instrumento de ordenamiento sin acto identificado en la fuente")
    if ins["revision_anio"]:
        partes.append(f"con revisión registrada en {ins['revision_anio']}")
    return ", ".join(partes)


def _pot_municipal(dane: str) -> list[dict]:
    """Datos del POT del municipio; una consulta por DANE, no por lote."""
    if dane not in _POT_MUNICIPAL:
        _POT_MUNICIPAL[dane] = _query(DATOS_URL, {
            "where": f"MDANMCodig='{dane}'",
            "outFields": "MDANMCodig,MDANMNombre,PotTipo,Vigencia,AprobacionTipo,NUMERO,AprobacionAño,Revision,RevisionAño,CARTOGRAFIA",
            "returnGeometry": "false"})
    return _POT_MUNICIPAL[dane]


def consultar_lote(codigo: str, geom_wgs84, dane: str, forzar: bool = False) -> dict:
    """
    POT del lote: reparto de área por categoría, uso principal dominante, clasificación y
    acto, y datos del POT municipal. Cacheado; una capa que falló se reintenta sola.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"{codigo}.json"
    out = {"_fecha": date.today().isoformat()}
    pendientes = None
    if ruta.exists() and not forzar:
        e = json.loads(ruta.read_text(encoding="utf-8"))
        # Las capas que fallaron (servidor caído) se reintentan solas; el resto se conserva.
        pendientes = {k for k, v in e.items() if isinstance(v, dict) and "error" in v}
        if not pendientes:
            return e
        out = e
    def _toca(clave):
        return pendientes is None or clave in pendientes
    g = _a_ctm12(geom_wgs84)
    area_total = g.area
    if _toca("zonificacion"):
        try:
            out["zonificacion"] = _zonificacion(geom_wgs84, g, area_total)
        except Exception as exc:
            out["zonificacion"] = {"error": type(exc).__name__}
    if _toca("clasificacion"):
        # clasificación urbano/rural + acto, por centroide
        c = g.centroid
        try:
            out["clasificacion"] = _query(CLASIF_URL, {"geometry": f"{c.x},{c.y}", "geometryType": "esriGeometryPoint",
                                                       "inSR": 9377, "spatialRel": "esriSpatialRelIntersects",
                                                       "outFields": "Tipo_Clasificacion_Suelo,CS_ActoAdministrativo,CSFecha",
                                                       "returnGeometry": "false"})
        except Exception as exc:
            out["clasificacion"] = {"error": type(exc).__name__}
    if _toca("pot_municipal"):
        try:
            out["pot_municipal"] = _pot_municipal(dane)
        except Exception as exc:
            out["pot_municipal"] = {"error": type(exc).__name__}
    ruta.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def resumir(e: dict, zonif_mpio: int | None = None, municipio: str | None = None) -> dict:
    """
    Columnas planas pot_* para la tabla de lotes, con el estado de la norma resuelto en
    tres: verificado, sin cartografía (vencido o no) y sin instrumento. `zonif_mpio` es
    el número de polígonos de zonificación rural que el IGAC publica para el municipio,
    y es lo que separa "el municipio no tiene la capa" de "el lote cae en un vacío".
    """
    z = e.get("zonificacion") or {}
    # Ninguna categoría puede ocupar más superficie que el lote: se recorta al 100%. En
    # los lotes cacheados antes de unir los polígonos superpuestos del servicio, alguna
    # categoría llegaba a sumar más, y esa cifra no se puede mostrar.
    rep = {k: min(100.0, v) for k, v in (z.get("reparto_pct") or {}).items()}
    usos = {k: min(100.0, v) for k, v in (z.get("usos_pct") or {}).items()}
    rep_ok = {k: v for k, v in rep.items() if k.isdigit()}
    usos_ok = {k: v for k, v in usos.items() if k.isdigit()}
    cat_dom = max(rep_ok, key=rep_ok.get) if rep_ok else None
    uso_dom = max(usos_ok, key=usos_ok.get) if usos_ok else None
    pct_prot = sum(v for k, v in rep.items() if k.isdigit() and int(k) >= 9)
    # Cuánto del lote alcanza a cubrir la zonificación y cuánto cae en una categoría que
    # es suelo de protección. Esta segunda cifra es la que decide, no la categoría
    # dominante: un lote con la tercera parte en protección tiene esa tercera parte
    # comprometida aunque el resto sea productivo.
    pct_zonificado = min(100.0, round(sum(rep_ok.values()), 1))
    pct_rojo = round(min(100.0, sum(v for k, v in rep_ok.items()
                                    if SEMAFORO_CATEGORIA.get(int(k)) == "rojo")), 1)
    # El semáforo lee la superficie en protección, no cuál es la categoría más grande, para
    # que diga lo mismo que la clase del lote: rojo cuando la protección cubre la mitad del
    # lote o más, ámbar cuando cubre una parte que obliga a rediseñar la implantación, y el
    # color de la categoría mayor cuando la protección es un roce de linderos.
    if not rep_ok or pct_zonificado <= 0:
        # Hay categorías, pero su solape con el lote no llega ni a la décima de punto: es
        # un roce de linderos entre capas y no dice nada de la norma del lote.
        sem = "gris"
    elif pct_rojo >= PROTECCION_ROJO_PCT:
        sem = "rojo"
    elif pct_rojo >= PROTECCION_AMBAR_PCT:
        sem = "ambar"
    else:
        otras = {k: v for k, v in rep_ok.items() if SEMAFORO_CATEGORIA.get(int(k)) != "rojo"}
        mayor = max(otras, key=otras.get) if otras else None
        sem = SEMAFORO_CATEGORIA.get(int(mayor), "verde") if mayor else "verde"
    leida = bool(cat_dom) and pct_zonificado >= COBERTURA_MIN_PCT
    cl = e.get("clasificacion") if isinstance(e.get("clasificacion"), list) else []
    pm = e.get("pot_municipal") if isinstance(e.get("pot_municipal"), list) else []
    ins = _instrumento(pm)
    fallo = isinstance(e.get("zonificacion"), dict) and "error" in e["zonificacion"]

    # ---------- estado de la norma ----------
    mpio = municipio or ins.get("municipio") or "el municipio"
    if fallo:
        estado = ESTADO_SIN_RESPUESTA
        cobertura = "sin respuesta del servicio"
        texto = ("El geoservicio de ordenamiento del IGAC no respondió en la última "
                 "consulta, de modo que la categoría del suelo queda sin verificar. "
                 "Se reintenta en la siguiente corrida y, mientras tanto, la categoría "
                 "se pide a la Secretaría de Planeación del municipio mediante "
                 "certificado de uso del suelo.")
    elif leida:
        estado = ESTADO_VERIFICADO
        cobertura = "verificado"
        texto = (f"La zonificación de suelo rural del IGAC cubre el lote y le asigna la "
                 f"categoría {CATEGORIA.get(int(cat_dom), cat_dom)} sobre el "
                 f"{rep.get(cat_dom):g}% de su superficie.")
        if ins.get("hay"):
            texto += (f" El instrumento de ordenamiento registrado por el IGAC en {mpio} "
                      f"es {_frase_instrumento(ins)}.")
            if ins.get("vencido"):
                texto += (f" Han pasado {ins['anios']} años desde su adopción y la Ley 388 "
                          f"de 1997 fija la vigencia del contenido de largo plazo en tres "
                          f"periodos constitucionales de la administración municipal, así "
                          f"que el instrumento puede revisarse durante la vida del proyecto.")
    elif ins.get("hay") or pct_zonificado > 0:
        cobertura = "sin cartografía"
        base = (f"En {mpio} el instrumento de ordenamiento registrado por el IGAC es "
                f"{_frase_instrumento(ins)}, pero su zonificación de suelo rural no está "
                f"publicada en el geoservicio")
        if pct_zonificado > 0:
            estado = ESTADO_SIN_COBERTURA_LOTE
            texto = (f"En {mpio} el IGAC publica zonificación de suelo rural, pero solo "
                     f"alcanza el {pct_zonificado:g}% de este lote, por debajo del "
                     f"{COBERTURA_MIN_PCT:g}% que se exige para darla por leída, de modo que "
                     f"la categoría del suelo queda sin verificar por esta vía.")
        elif zonif_mpio is not None and zonif_mpio > 0:
            estado = ESTADO_SIN_COBERTURA_LOTE
            texto = (f"En {mpio} el IGAC publica zonificación de suelo rural, pero ninguno "
                     f"de sus polígonos cubre este lote, de modo que la categoría del suelo "
                     f"queda sin verificar por esta vía.")
        elif ins.get("vencido"):
            estado = ESTADO_VENCIDO_SIN_CARTOGRAFIA
            texto = (base + f", de modo que la categoría del suelo del lote no se puede "
                     f"verificar por esta vía. Han pasado {ins['anios']} años desde su "
                     f"adopción y la Ley 388 de 1997 fija la vigencia del contenido de "
                     f"largo plazo en tres periodos constitucionales de la administración "
                     f"municipal, así que el instrumento está vencido y el municipio puede "
                     f"revisarlo durante la vida del proyecto, con el cambio de categorías "
                     f"que esa revisión traiga.")
        else:
            estado = ESTADO_SIN_CARTOGRAFIA
            texto = base + ", de modo que la categoría del suelo del lote no se puede verificar por esta vía."
        texto += (" La categoría del suelo se pide a la Secretaría de Planeación del "
                  "municipio mediante certificado de uso del suelo, que es el documento "
                  "que decide en el trámite.")
    else:
        estado = ESTADO_SIN_INSTRUMENTO
        cobertura = "sin instrumento"
        texto = ("El IGAC no registra instrumento de ordenamiento territorial para el "
                 "municipio ni publica zonificación de suelo rural que cubra el lote. "
                 "La categoría del suelo se pide a la Secretaría de Planeación del "
                 "municipio mediante certificado de uso del suelo.")

    return {
        "pot_categoria": CATEGORIA.get(int(cat_dom)) if cat_dom and cat_dom.isdigit() else None,
        "pot_categoria_cod": int(cat_dom) if cat_dom and cat_dom.isdigit() else None,
        "pot_categoria_pct": rep.get(cat_dom) if cat_dom else None,
        "pot_reparto": "; ".join(f"{CATEGORIA.get(int(k), k) if k.isdigit() else 'sin categoría'}: {v}%"
                                 for k, v in sorted(rep.items(), key=lambda x: -x[1]))[:220] if rep else None,
        "pot_uso_principal": USO.get(int(uso_dom)) if uso_dom and uso_dom.isdigit() else None,
        "pot_proteccion_pct": round(pct_prot, 1) if rep else None,
        "pot_zonificado_pct": pct_zonificado if rep else 0.0,
        "pot_rojo_pct": pct_rojo if rep else 0.0,
        "pot_uso_prohibido": "; ".join(z.get("prohibido") or []) or None,
        "pot_semaforo": sem,
        "pot_clasificacion": CLASIF.get(cl[0].get("Tipo_Clasificacion_Suelo")) if cl else None,
        "pot_acto": (cl[0].get("CS_ActoAdministrativo") if cl else None),
        "pot_tipo": ins.get("tipo"),
        "pot_acto_municipal": ins.get("acto"),
        "pot_anio": ins.get("anio"),
        "pot_revision": ins.get("revision_anio"),
        "pot_fecha": e.get("_fecha"),
        # "ok" si la zonificación respondió (aunque venga vacía), "error" si el servicio falló.
        "pot_estado": "error" if fallo else "ok",
        # Los tres estados de la norma y su lectura en lenguaje corriente.
        "pot_estado_norma": estado,
        "pot_cobertura": cobertura,
        "pot_instrumento": _frase_instrumento(ins) if ins.get("hay") else None,
        "pot_instrumento_anios": ins.get("anios"),
        "pot_instrumento_vencido": bool(ins.get("vencido")) if ins.get("hay") else None,
        "pot_zonificacion_municipio": zonif_mpio,
        "pot_nota": texto,
    }


def enriquecer(p: pd.DataFrame, geoms=None, verbose: bool = True, hilos: int = 6) -> pd.DataFrame:
    """Añade las columnas pot_* a una tabla de lotes; `geoms` GeoSeries alineada (WGS84)."""
    import geopandas as gpd
    p = p.copy()
    if geoms is None:
        perfil = str(p["perfil"].iloc[0]) if "perfil" in p.columns and len(p) else "utility"
        g = gpd.read_file(SALIDA / f"lotes_{perfil}.geojson").to_crs(4326).set_index("CODIGO")
        geoms = g.geometry.reindex(p["CODIGO"].astype(str)).values
    tareas = []
    for (_, r), geom in zip(p.iterrows(), geoms):
        if geom is None or getattr(geom, "is_empty", True):
            tareas.append(None); continue
        tareas.append((str(r["CODIGO"]), geom, str(r["CODIGO"]).zfill(30)[:5]))
    def _una(t):
        return consultar_lote(*t) if t else {}
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        res = list(ex.map(_una, tareas))
    # Cobertura de la zonificación por municipio: una consulta por código, en paralelo,
    # para saber si el vacío es del municipio entero o solo de este lote.
    danes = sorted({t[2] for t in tareas if t})
    if danes:
        with ThreadPoolExecutor(max_workers=min(hilos, len(danes))) as ex:
            list(ex.map(zonificacion_municipal, danes))
    conteos = [zonificacion_municipal(t[2]) if t else None for t in tareas]
    nombres = (p["municipio"].tolist() if "municipio" in p.columns else [None] * len(p))
    df = pd.DataFrame([resumir(e, z, m if isinstance(m, str) else None)
                       for e, z, m in zip(res, conteos, nombres)], index=p.index)
    for c in df.columns:
        p[c] = df[c]
    if verbose:
        prot = pd.to_numeric(p["pot_rojo_pct"], errors="coerce").fillna(0.0)
        print(f"  POT: de {len(p)} lotes, {int((prot >= PROTECCION_ROJO_PCT).sum())} con la "
              f"mitad del lote o más en suelo de protección y "
              f"{int(((prot >= PROTECCION_AMBAR_PCT) & (prot < PROTECCION_ROJO_PCT)).sum())} "
              f"con una parte")
        for estado, n in p["pot_estado_norma"].value_counts().items():
            print(f"    {estado}: {n} lotes")
            sub = p[p["pot_estado_norma"] == estado]
            if estado == ESTADO_VERIFICADO or "municipio" not in sub.columns:
                continue
            for mpio, s2 in sub.groupby("municipio"):
                ins = s2["pot_instrumento"].dropna()
                cuantos = f"{len(s2)} lote" + ("" if len(s2) == 1 else "s")
                print(f"      {mpio}: {cuantos}, "
                      f"{ins.iloc[0] if len(ins) else 'sin instrumento registrado'}")
    return p


def main(argv=None) -> int:
    """CLI: enriquece los lotes de un perfil con la norma urbana e imprime un resumen."""
    ap = argparse.ArgumentParser(description="Norma urbana (POT) del lote desde el IGAC")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args(argv)
    ruta = SALIDA / f"lotes_{a.perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    p = pd.read_csv(ruta, dtype={"CODIGO": str})
    if a.forzar:
        for f in CACHE.glob("*.json"):
            f.unlink()
    q = enriquecer(p)
    print("=" * 74)
    print(f"NORMA URBANA (POT), perfil {a.perfil}")
    print("=" * 74)
    print(q.groupby(["pot_semaforo", "pot_categoria"], dropna=False).size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
