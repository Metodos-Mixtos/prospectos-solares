"""
Cribado jurídico de los lotes con datos públicos, previo al certificado de tradición.

Cruza cada lote contra la UAF máxima de su municipio (acumulación de baldíos, art. 72
Ley 160/1994) y contra las solicitudes de restitución de tierras (Ley 1448/2011).
Entrada: outputs/reporte/lotes_<perfil>.csv. Salida: la misma tabla con columnas nuevas.
Fuentes: capa ANT "Unidad Agrícola Familiar" (FeatureServer, campo Cod_Dane) y dataset
33hn-pgph de la URT (datos.gov.co, Socrata); caché en data/juridico/ y respaldo estático
en juridico_fallback.py. Clave de cruce: código DANE (5 primeros dígitos del código
catastral), no el nombre del municipio. Sin acuerdo UAF de la ANT rige la Res. 041/1996.
Uso: python -m predios.juridico [--perfil utility] [--forzar]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config
from juridico_fallback import RESTITUCION_FALLBACK, UAF_FALLBACK

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
CACHE = config.PROJECT_ROOT / "data" / "juridico"

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}

#: Capa ANT "Unidad Agrícola Familiar" (item e69b4c3567704b7e8c80301ad36da98b en
#: data-agenciadetierras.opendata.arcgis.com); solo municipios con acuerdo UAF por UFH.
UAF_URL = ("https://utility.arcgis.com/usrsvcs/servers/e69b4c3567704b7e8c80301ad36da98b"
           "/rest/services/DatosAbiertos/Unidad_Agricola_Familiar/FeatureServer/0/query")

#: URT, dataset 33hn-pgph en datos.gov.co: solicitudes de restitución por municipio.
RESTITUCION_URL = "https://www.datos.gov.co/resource/33hn-pgph.json"


# --------------------------------------------------------------------------
# Consulta viva, con caché y respaldo estático
# --------------------------------------------------------------------------

def _cache(nombre: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / nombre


def uaf_viva(danes: list[str], forzar: bool = False) -> dict[str, dict]:
    """
    Rango UAF por municipio desde la capa de la ANT: mínimo de mínimos y máximo de
    máximos entre sus UFH, que es el criterio conservador para el cribado.
    """
    ruta = _cache("uaf_ant.json")
    tabla = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    faltan = [d for d in danes if d not in tabla] if not forzar else list(danes)
    if not faltan:
        return tabla

    import requests
    for i in range(0, len(faltan), 40):
        grupo = faltan[i:i + 40]
        lista = ",".join(f"'{d}'" for d in grupo)
        try:
            r = requests.get(UAF_URL, headers=UA, timeout=120, params={
                "where": f"Cod_Dane IN ({lista})", "returnGeometry": "false",
                "outFields": "Cod_Dane,Municipio,UAF_Min,UAF_Max,Acto_Administrativo",
                "f": "json"})
            feats = r.json().get("features", [])
        except Exception as exc:
            print(f"  aviso: capa UAF de la ANT no respondió ({type(exc).__name__}), "
                  f"se usa el respaldo documental")
            return tabla
        vistos = {}
        for f in feats:
            a = f["attributes"]
            d = str(a.get("Cod_Dane"))
            v = vistos.setdefault(d, {"municipio": a.get("Municipio"),
                                      "uaf_min_ha": None, "uaf_max_ha": None,
                                      "acto": f"Acuerdo ANT {a.get('Acto_Administrativo')}"})
            for k, val, op in (("uaf_min_ha", a.get("UAF_Min"), min),
                               ("uaf_max_ha", a.get("UAF_Max"), max)):
                if val is not None:
                    v[k] = float(val) if v[k] is None else op(v[k], float(val))
        for d in grupo:
            # municipio ausente de la capa = sin acuerdo; se anota para no reconsultar
            tabla[d] = vistos.get(d, {"sin_acuerdo": True})
    ruta.write_text(json.dumps(tabla, ensure_ascii=False, indent=1), encoding="utf-8")
    return tabla


def restitucion_viva(danes: list[str], forzar: bool = False) -> dict[str, dict]:
    """Solicitudes de restitución por municipio, desde la API de la URT."""
    ruta = _cache("restitucion_urt.json")
    tabla = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    faltan = [d for d in danes if d not in tabla] if not forzar else list(danes)
    if not faltan:
        return tabla

    import requests
    lista = ",".join(f"'{d}'" for d in faltan)
    try:
        r = requests.get(RESTITUCION_URL, headers=UA, timeout=120, params={
            "$where": f"codigodanemunicipio in({lista})",
            "$select": "codigodanemunicipio, municipiodelpredio, "
                       "numerodesolicitudesenelsrtdaf, fechadecorte",
            "$limit": 5000})
        filas = r.json()
    except Exception as exc:
        print(f"  aviso: API de la URT no respondió ({type(exc).__name__}), "
              f"se usa el respaldo documental")
        return tabla
    por_dane: dict[str, dict] = {}
    for f in filas:
        d = str(f.get("codigodanemunicipio"))
        v = por_dane.setdefault(d, {"municipio": f.get("municipiodelpredio"),
                                    "solicitudes": 0, "corte": f.get("fechadecorte")})
        try:
            v["solicitudes"] += int(f.get("numerodesolicitudesenelsrtdaf") or 0)
        except (TypeError, ValueError):
            pass
    for d in faltan:
        tabla[d] = por_dane.get(d, {"solicitudes": None})
    ruta.write_text(json.dumps(tabla, ensure_ascii=False, indent=1), encoding="utf-8")
    return tabla


# --------------------------------------------------------------------------
# Resolución con respaldo
# --------------------------------------------------------------------------

def _uaf_de(dane: str, viva: dict) -> dict | None:
    v = viva.get(dane)
    if v and not v.get("sin_acuerdo") and v.get("uaf_max_ha"):
        return v
    return UAF_FALLBACK.get(dane)


def _restitucion_de(dane: str, viva: dict) -> dict | None:
    v = viva.get(dane)
    if v and v.get("solicitudes") is not None:
        r = RESTITUCION_FALLBACK.get(dane, {})
        return {**v, "microzona": r.get("microzona")}
    return RESTITUCION_FALLBACK.get(dane)


# --------------------------------------------------------------------------
# Cribado
# --------------------------------------------------------------------------

def cribar(p: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Añade a la tabla de lotes las columnas dane_predio, uaf_max_ha, uaf_fuente,
    veces_uaf, riesgo_baldio (área > UAF máxima municipal), restitucion_mpio
    (solicitudes en el municipio; -1 sin dato) y microzona_urt. Sin red usa el respaldo.
    """
    p = p.copy()
    dane = p["CODIGO"].astype(str).str.zfill(30).str[:5]
    p["dane_predio"] = dane
    danes = sorted(dane.unique())

    v_uaf = uaf_viva(danes)
    v_res = restitucion_viva(danes)

    maxs, fuentes, veces, riesgo, restit, micro = [], [], [], [], [], []
    for i, d in enumerate(dane):
        u = _uaf_de(d, v_uaf)
        area = p["area_ha"].iloc[i]
        if u and u.get("uaf_max_ha"):
            maxs.append(round(float(u["uaf_max_ha"]), 1))
            fuentes.append(u.get("acto", "sin fuente"))
            veces.append(round(float(area) / float(u["uaf_max_ha"]), 1))
            riesgo.append(bool(area > float(u["uaf_max_ha"])))
        else:
            maxs.append(np.nan)
            fuentes.append("sin dato")
            veces.append(np.nan)
            riesgo.append(False)
        r = _restitucion_de(d, v_res)
        restit.append(int(r["solicitudes"]) if r and r.get("solicitudes") is not None
                      else -1)
        micro.append(bool(r.get("microzona")) if r else False)

    p["uaf_max_ha"] = maxs
    p["uaf_fuente"] = fuentes
    p["veces_uaf"] = veces
    p["riesgo_baldio"] = riesgo
    p["restitucion_mpio"] = restit
    p["microzona_urt"] = micro

    if verbose:
        con = int(p["riesgo_baldio"].sum())
        print(f"  cribado jurídico: {con} de {len(p)} lotes superan la UAF máxima "
              f"de su municipio; {int(p['microzona_urt'].sum())} están en municipio "
              f"con microzona de restitución")
    return p


def main(argv=None) -> int:
    """CLI: cribado jurídico de los lotes de un perfil, con resumen por municipio."""
    ap = argparse.ArgumentParser(
        description="Cribado jurídico de los lotes: UAF (riesgo baldío) y restitución")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--forzar", action="store_true", help="reconsulta las fuentes vivas")
    a = ap.parse_args(argv)

    ruta = SALIDA / f"lotes_{a.perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    p = pd.read_csv(ruta, dtype={"CODIGO": str})
    if a.forzar:
        uaf_viva(sorted(p["CODIGO"].astype(str).str[:5].unique()), forzar=True)
        restitucion_viva(sorted(p["CODIGO"].astype(str).str[:5].unique()), forzar=True)
    q = cribar(p)

    print("=" * 74)
    print(f"CRIBADO JURÍDICO, perfil {a.perfil}")
    print("=" * 74)
    res = (q.groupby(["dane_predio"])
            .agg(municipio=("municipio", "first"), lotes=("CODIGO", "size"),
                 ha_max=("area_ha", "max"), uaf_max=("uaf_max_ha", "first"),
                 fuente=("uaf_fuente", "first"), veces=("veces_uaf", "max"),
                 restitucion=("restitucion_mpio", "first"),
                 microzona=("microzona_urt", "first"))
            .sort_values("veces", ascending=False))
    print(res.to_string())
    print()
    print(f"  con riesgo baldío (si el origen es baldío): {int(q['riesgo_baldio'].sum())}"
          f" de {len(q)}")
    print("  El riesgo se confirma o descarta con el certificado de tradición: si las")
    print("  primeras anotaciones traen adjudicación del INCORA, INCODER o ANT, la")
    print("  compra por encima de la UAF es nula. Ver predios/certificados.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
