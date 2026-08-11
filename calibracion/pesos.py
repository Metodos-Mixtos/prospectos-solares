"""
Qué covariables separan de verdad las celdas con generación solar de las demás.

La pregunta práctica es cuáles merecen ser criterio de decisión y cuáles son ruido o
contexto. Se responde de dos maneras que se contrastan entre sí:

  1. Tamaño del efecto (d de Cohen). Cuánto se separan las medias de los dos grupos
     en unidades de desviación típica. Es transparente y no depende de ningún modelo.

  2. Importancia por permutación sobre un bosque aleatorio. Cuánto empeora la
     capacidad de distinguir los grupos al barajar una sola variable. Recoge efectos
     no lineales y relaciones entre variables que la d de Cohen no ve.

Se calcula dos veces: contra todas las plantas registradas y contra las de escala
utility, porque más de la mitad de los registros de XM son instalaciones de un
megavatio o menos, que son tejados y no compran lotes.

Uso:
    .venv\\Scripts\\python.exe -m calibracion pesos
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
# La raiz del proyecto va al path para poder importar config y gcs, que viven
# un nivel arriba de este paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import gcs

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"

# No son covariables: son el objetivo, identificadores o derivados del objetivo.
EXCLUIR = {
    "cell_id", "geometry", "tiene_granja", "n_granjas",
    "n_subestaciones", "tiene_subestacion",
}

NOMBRES = {
    "pvout": "Producción fotovoltaica",
    "gti": "Irradiación en plano inclinado",
    "ghi": "Irradiación horizontal",
    "dni": "Irradiación directa",
    "dif": "Irradiación difusa",
    "opta": "Ángulo óptimo",
    "temp": "Temperatura media",
    "slope_mean": "Pendiente media",
    "elevation_mean": "Elevación media",
    "elevation_std": "Rugosidad del relieve",
    "dist_subestacion_km": "Distancia a subestación",
    "travel_time": "Tiempo de viaje a centro poblado",
    "pop_density_mean": "Densidad de población",
    "deprivation": "Privación socioeconómica",
    "coca_density_2023": "Densidad de coca",
    "tree_cover_2000_pct": "Cobertura arbórea 2000",
    "%trees": "Bosque",
    "%crops": "Cultivos",
    "%rangeland": "Pastizal",
    "%builtarea": "Área construida",
    "%water": "Agua",
    "%baregnd": "Suelo desnudo",
    "%flood_veg": "Vegetación inundable",
    "%snow_ice": "Nieve y hielo",
    "%clouds": "Nubosidad",
    "area_protegida": "Área protegida",
    "en_parque_nacional": "Parque nacional",
    "territorio_indigena": "Resguardo indígena",
    "consejo_comunitario": "Consejo comunitario",
    "EVOA_2019_": "EVOA 2019",
}


def cohen_d(a: pd.Series, b: pd.Series) -> float:
    """Diferencia de medias en desviaciones típicas, con varianza agrupada."""
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    na, nb = len(a), len(b)
    s = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return np.nan if s == 0 else (a.mean() - b.mean()) / s


def celdas_utility(gdf: gpd.GeoDataFrame) -> set[str]:
    """cell_id de las celdas que contienen al menos una planta de 10 MW o más."""
    xm = gpd.read_file(gcs.obtener(
        "geoinfo", "Colombia/Energia_electrica/Proyectos de generación (XM).geojson",
        verbose=False))
    cap = pd.to_numeric(
        xm["capacidad_efectiva_neta_mw"].astype(str).str.replace(",", "."), errors="coerce")
    xm = xm.assign(cap_mw=cap)
    grandes = xm[(xm["clasificacion"] == "NORMAL") & (xm["cap_mw"] >= 10)]
    if grandes.crs is None:
        grandes = grandes.set_crs(config.CRS_GEOGRAFICO)
    j = gpd.sjoin(grandes.to_crs(gdf.crs), gdf[["cell_id", "geometry"]],
                  how="inner", predicate="within")
    return set(j["cell_id"].astype(str))


def tabla_efectos(gdf, positivas: pd.Series, cols) -> pd.DataFrame:
    con = gdf[positivas]
    sin = gdf[~positivas]
    filas = []
    for c in cols:
        d = cohen_d(con[c], sin[c])
        if pd.isna(d):
            continue
        filas.append({
            "variable": c,
            "nombre": NOMBRES.get(c, c),
            "d_cohen": d,
            "efecto": abs(d),
            "media_con": con[c].mean(),
            "media_sin": sin[c].mean(),
        })
    return pd.DataFrame(filas).sort_values("efecto", ascending=False)


def importancia_permutacion(gdf, positivas, cols, semilla=0) -> pd.Series:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import train_test_split

    X = gdf[cols].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    y = positivas.astype(int).values

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=semilla, stratify=y)
    m = RandomForestClassifier(
        n_estimators=400, min_samples_leaf=3, class_weight="balanced",
        random_state=semilla, n_jobs=-1).fit(Xtr, ytr)
    r = permutation_importance(m, Xte, yte, n_repeats=12,
                               random_state=semilla, scoring="roc_auc", n_jobs=-1)
    return pd.Series(r.importances_mean, index=cols).sort_values(ascending=False)


def main() -> int:
    gdf = gpd.read_file(config.PANEL_PATH)
    gdf["cell_id"] = gdf["cell_id"].astype(str)

    cols = [c for c in gdf.columns
            if c not in EXCLUIR and pd.api.types.is_numeric_dtype(gdf[c])]
    cols = [c for c in cols if not c.startswith("gdp_") or c.endswith("2020")]

    print("=" * 78)
    print("QUÉ COVARIABLES SEPARAN LAS CELDAS CON GENERACIÓN SOLAR")
    print("=" * 78)
    print(f"  celdas: {len(gdf)}   covariables evaluadas: {len(cols)}")

    escenarios = {"todas las plantas": gdf["tiene_granja"] > 0}
    try:
        ids = celdas_utility(gdf)
        escenarios["solo utility, 10 MW o más"] = gdf["cell_id"].isin(ids)
        print(f"  celdas con planta: {int((gdf['tiene_granja'] > 0).sum())}"
              f"   de ellas utility: {len(ids)}")
    except Exception as exc:
        print(f"  aviso: no se pudo separar utility ({type(exc).__name__})")

    resultados = {}
    for etiqueta, pos in escenarios.items():
        print()
        print("-" * 78)
        print(f"ESCENARIO: {etiqueta}   ({int(pos.sum())} celdas positivas)")
        print("-" * 78)

        t = tabla_efectos(gdf, pos, cols)
        imp = importancia_permutacion(gdf, pos, cols)
        t["importancia"] = t["variable"].map(imp)
        t["rango_efecto"] = t["efecto"].rank(ascending=False).astype(int)
        t["rango_import"] = t["importancia"].rank(ascending=False).astype(int)
        resultados[etiqueta] = t

        print("%-34s %8s %6s %10s %6s" % ("VARIABLE", "d COHEN", "PUESTO", "IMPORT.", "PUESTO"))
        for _, r in t.head(14).iterrows():
            print("%-34s %8.2f %6d %10.4f %6d"
                  % (r["nombre"][:34], r["d_cohen"], r["rango_efecto"],
                     r["importancia"], r["rango_import"]))

        print()
        pen = t[t["variable"] == "slope_mean"]
        if len(pen):
            p = pen.iloc[0]
            print("  Pendiente media: d = %.2f (puesto %d de %d por efecto), "
                  "importancia puesto %d"
                  % (p["d_cohen"], p["rango_efecto"], len(t), p["rango_import"]))

    if resultados:
        clave = "solo utility, 10 MW o más" if "solo utility, 10 MW o más" in resultados else "todas las plantas"
        SALIDA.mkdir(parents=True, exist_ok=True)
        resultados[clave].round(4).to_csv(SALIDA / "influencia_covariables.csv",
                                          index=False, encoding="utf-8-sig")
        print(f"\n  CSV -> {SALIDA / 'influencia_covariables.csv'}  ({clave})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
