"""
Valor de referencia del suelo por lote, nivel 1 del informe de valorización remota.

Ancla: Zonas Homogéneas Geoeconómicas rurales del IGAC vigencia 2026 (FeatureServer
Zonas_Homogeneas_Gestor_IGAC_Vigencias_2026, capa 11, campo VALOR_HECTAREA), ponderadas
por el área que el predio tiene en cada zona según REGISTRO_2 (`zonas_economicas`).
Contraste: mediana municipal del Observatorio de Tierras Rurales de la ANT (Córdoba y
Sucre 2025, Bolívar 2026), tabla estática en VALOR_ANT. Salida por lote: valor catastral
de referencia por hectárea y total, banda ANT del municipio, y una calificación de la
confianza. Es valor catastral, no precio de mercado; el sesgo se declara en la ficha.
Uso: python -m predios.valor [--perfil utility] [--forzar]
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

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
CACHE = config.PROJECT_ROOT / "data" / "valor"
UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}

#: Zonas geoeconómicas rurales del gestor IGAC, vigencia 2026. Solo cubre municipios con
#: gestor IGAC; los gestores descentralizados no están.
ZHG_URL = ("https://services2.arcgis.com/RVvWzU3lgJISqdke/ArcGIS/rest/services/"
           "Zonas_Homogeneas_Gestor_IGAC_Vigencias_2026/FeatureServer/11/query")

#: Mediana y desviación estándar municipal (COP/ha) del Observatorio de Tierras Rurales
#: de la ANT: Córdoba y Sucre nov-2025, Bolívar 2026. Salida de modelo, no observación;
#: se usa como banda de contraste, no como valor del lote.
VALOR_ANT: dict[str, dict] = {
    "23350": {"municipio": "La Apartada", "mediana": 16_352_943, "de": 3_185_241},
    "23466": {"municipio": "Montelíbano", "mediana": 6_213_674, "de": None},
    "23068": {"municipio": "Ayapel", "mediana": 3_996_264, "de": None},
    "23580": {"municipio": "Puerto Libertador", "mediana": 6_811_021, "de": None},
    "23555": {"municipio": "Planeta Rica", "mediana": 9_863_308, "de": None},
    "23570": {"municipio": "Pueblo Nuevo", "mediana": 10_332_896, "de": None},
    "23682": {"municipio": "San José de Uré", "mediana": 7_480_014, "de": None},
    "70233": {"municipio": "El Roble", "mediana": 7_572_222, "de": None},
    "70124": {"municipio": "Caimito", "mediana": 9_365_107, "de": None},
    "70400": {"municipio": "La Unión", "mediana": 10_510_878, "de": None},
    "70823": {"municipio": "Tolú Viejo", "mediana": 25_224_060, "de": None},
    "70820": {"municipio": "Santiago de Tolú", "mediana": 59_394_305, "de": None},
    "70523": {"municipio": "Palmito", "mediana": 60_077_795, "de": None},
}


def _pesos(v) -> float:
    """VALOR_HECTAREA llega como número o como texto con formato ('$9.000.000', '9.000.000,00')."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 and len(s.split(",")[1]) <= 2 else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")
    return float(s)


def zonas_municipio(dane: str, forzar: bool = False) -> dict[str, float]:
    """Tabla zona -> COP/ha del municipio, desde el geoservicio; cacheada en data/valor/."""
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"zhg_{dane}.json"
    if ruta.exists() and not forzar:
        return json.loads(ruta.read_text(encoding="utf-8"))
    import requests
    try:
        r = requests.get(ZHG_URL, headers=UA, timeout=120, params={
            "where": f"codigo_municipio='{dane}'", "returnDistinctValues": "true",
            "outFields": "CODIGO_ZONA_GEOECONOMICA,VALOR_HECTAREA",
            "returnGeometry": "false", "f": "json"})
        feats = r.json().get("features", [])
    except Exception:
        return {}
    tabla = {}
    for f in feats:
        a = f["attributes"]
        z, v = a.get("CODIGO_ZONA_GEOECONOMICA"), a.get("VALOR_HECTAREA")
        if z and v:
            try:
                tabla[str(int(z))] = _pesos(v)
            except (TypeError, ValueError):
                pass
    ruta.write_text(json.dumps(tabla), encoding="utf-8")
    return tabla


def _parsear_zonas(texto) -> dict[str, float]:
    """'6:77.0;7:24.6' -> {'6': 77.0, '7': 24.6} (hectáreas por zona)."""
    out = {}
    if not isinstance(texto, str):
        return out
    for par in texto.split(";"):
        if ":" in par:
            z, a = par.split(":", 1)
            try:
                out[str(int(z))] = float(a)
            except ValueError:
                pass
    return out


def valorar(p: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Añade valor_ref_cop_ha (ponderado por área en cada zona), valor_ref_cop (total),
    valor_ref_cobertura (fracción del área con zona valorada), ant_mediana_cop_ha,
    ant_banda y valor_confianza ('alta' si cubre >90% del área y hay contraste ANT).
    """
    p = p.copy()
    danes = sorted(p["CODIGO"].astype(str).str.zfill(30).str[:5].unique())
    tablas = {d: zonas_municipio(d) for d in danes}

    cop_ha, cop, cob, ant_m, ant_b, conf = [], [], [], [], [], []
    for _, r in p.iterrows():
        dane = str(r["CODIGO"]).zfill(30)[:5]
        tabla = tablas.get(dane, {})
        zonas = _parsear_zonas(r.get("zonas_economicas"))
        area = float(r.get("area_ha") or 0)
        valoradas = {z: a for z, a in zonas.items() if z in tabla and a > 0}
        ha_val = sum(valoradas.values())
        if valoradas and area > 0 and ha_val > 0:
            v = sum(a * tabla[z] for z, a in valoradas.items()) / ha_val
            cobertura = min(1.0, ha_val / area)
        else:
            # sin REGISTRO_2 o sin zona valorada: se usa la zona dominante o nada
            zd = r.get("zona_economica_dominante")
            v = tabla.get(str(int(zd))) if pd.notna(zd) and str(int(zd)) in tabla else np.nan
            cobertura = 0.0 if pd.isna(v) else np.nan
        cop_ha.append(v)
        cop.append(v * area if pd.notna(v) else np.nan)
        cob.append(cobertura)
        a = VALOR_ANT.get(dane)
        ant_m.append(a["mediana"] if a else np.nan)
        if a and a.get("de"):
            ant_b.append(f"{(a['mediana']-a['de'])/1e6:.1f}-{(a['mediana']+a['de'])/1e6:.1f} M")
        elif a:
            ant_b.append(f"mediana {a['mediana']/1e6:.1f} M")
        else:
            ant_b.append("sin dato ANT")
        if pd.isna(v):
            conf.append("sin dato")
        elif cobertura is not np.nan and cobertura >= 0.9 and a:
            conf.append("alta")
        elif cobertura is not np.nan and cobertura >= 0.5:
            conf.append("media")
        else:
            conf.append("baja")

    p["valor_ref_cop_ha"] = np.round(cop_ha, 0)
    p["valor_ref_cop"] = np.round(cop, 0)
    p["valor_ref_cobertura"] = np.round(cob, 2)
    p["ant_mediana_cop_ha"] = ant_m
    p["ant_banda"] = ant_b
    p["valor_confianza"] = conf
    if verbose:
        con = int(pd.notna(p["valor_ref_cop_ha"]).sum())
        print(f"  valor de referencia: {con} de {len(p)} lotes con zona geoeconómica; "
              f"confianza alta {sum(1 for c in conf if c == 'alta')}")
    return p


def main(argv=None) -> int:
    """CLI: valora los lotes de un perfil e imprime resumen por municipio."""
    ap = argparse.ArgumentParser(description="Valor de referencia del suelo por lote")
    ap.add_argument("--perfil", default="utility")
    ap.add_argument("--forzar", action="store_true", help="reconsulta el geoservicio")
    a = ap.parse_args(argv)
    ruta = SALIDA / f"lotes_{a.perfil}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta.name}. Corre antes: python -m predios.lotes")
    p = pd.read_csv(ruta, dtype={"CODIGO": str})
    if a.forzar:
        for d in sorted(p["CODIGO"].str[:5].unique()):
            zonas_municipio(d, forzar=True)
    q = valorar(p)
    print("=" * 74)
    print(f"VALOR DE REFERENCIA DEL SUELO, perfil {a.perfil}")
    print("=" * 74)
    q["dane"] = q["CODIGO"].str[:5]
    res = (q.groupby("dane").agg(municipio=("municipio", "first"), lotes=("CODIGO", "size"),
                                 cop_ha_mediana=("valor_ref_cop_ha", "median"),
                                 ant_mediana=("ant_mediana_cop_ha", "first"),
                                 confianza=("valor_confianza", lambda s: s.mode().iat[0]))
            .sort_values("cop_ha_mediana", ascending=False))
    pd.set_option("display.float_format", lambda x: f"{x:,.0f}")
    print(res.to_string())
    print()
    print("  Valor catastral de referencia (IGAC 2026), no precio de mercado. La banda ANT es")
    print("  contraste municipal. Ambos se declaran en la ficha con su sesgo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
