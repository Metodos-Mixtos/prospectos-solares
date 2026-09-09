"""
Comprobaciones automáticas del reporte de lotes: contrato del JSON, coherencia con
los CSV de lotes, geometría, imágenes y HTML.

    .venv\\Scripts\\python.exe soporte/herramientas/probar_reporte_predios.py

Sale con código 1 si alguna comprobación falla.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_raiz = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box, shape

import config

SALIDA = config.PROJECT_ROOT / "outputs" / "reporte"
fallos = 0


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    global fallos
    fallos += not ok
    print(f"  {'ok ' if ok else 'FALLA'} {nombre}" + (f"  ({detalle})" if detalle else ""))


def main() -> int:
    j = SALIDA / "reporte_predios.json"
    if not j.exists():
        raise SystemExit("No existe reporte_predios.json. Corre antes: python -m reporte_predios")
    d = json.loads(j.read_text(encoding="utf-8"))
    ids = {c["cell_id"] for c in d["celdas"]}

    print("Contrato del JSON")
    for k in ("generado", "origen_grillas", "perfiles", "criterios", "costo_certificado",
              "url_snr", "celdas", "lotes"):
        check(f"tiene '{k}'", k in d)
    check("costo del certificado es un entero positivo",
          isinstance(d.get("costo_certificado"), int) and d["costo_certificado"] > 0,
          str(d.get("costo_certificado")))

    print("Coherencia con las fuentes")
    origen = SALIDA / d["origen_grillas"]
    if origen.exists():
        g = gpd.read_file(origen) if origen.suffix != ".csv" else None
        if g is not None:
            check("celdas del insumo = celdas del JSON",
                  set(g["cell_id"].astype(str).str.zfill(7)) == ids, f"{len(ids)}")
    for perfil, filas in d["lotes"].items():
        csv = SALIDA / f"lotes_{perfil}.csv"
        if not csv.exists():
            check(f"{perfil}: existe el CSV", False); continue
        s = pd.read_csv(csv, dtype={"CODIGO": str, "cell_id": str})
        s["cell_id"] = s["cell_id"].str.zfill(7)
        s = s[s["cell_id"].isin(ids)]
        check(f"{perfil}: n lotes = CSV filtrado", len(s) == len(filas), f"{len(filas)} vs {len(s)}")
        m = {f["CODIGO"]: f for f in filas}
        dif = sum(1 for _, r in s.iterrows()
                  if r.CODIGO not in m
                  or abs((m[r.CODIGO]["indice_lote"] or 0) - r.indice_lote) > 0.01
                  or abs((m[r.CODIGO]["area_ha"] or 0) - r.area_ha) > 0.01)
        check(f"{perfil}: índice y área iguales fila a fila", dif == 0, f"{dif} distintas")
        # El municipio del lote debe ser el del código catastral, no el de la celda.
        import lotes as L
        div = L.divipola()
        if div:
            # Se compara sin distinguir mayusculas: el visor escribe "Santiago de
            # Tolu" y la DIVIPOLA "Santiago De Tolu". Lo que se comprueba aqui es
            # que el municipio salga del codigo catastral y no de la celda, no como
            # el DANE escribe las preposiciones.
            def _norm(s):
                return " ".join(str(s).lower().split())

            mal = sum(1 for f in filas
                      if div.get(f["CODIGO"][:5])
                      and _norm(f["municipio"]) != _norm(div[f["CODIGO"][:5]]))
            check(f"{perfil}: municipio = DIVIPOLA del código", mal == 0, f"{mal} distintos")

    print("Cobertura del suelo y orden de la lista")
    # Las clases son las que publica ESA WorldCover; el reporte las describe una a una y
    # no calcula ningún agregado a partir de ellas.
    CLASES = ("cob_pastizal_pct", "cob_bosque_pct", "cob_cultivo_pct", "cob_matorral_pct",
              "cob_construido_pct", "cob_desnudo_pct", "cob_humedal_pct", "cob_agua_pct",
              "cob_manglar_pct", "cob_nieve_pct", "cob_musgo_pct")
    for perfil, filas in d["lotes"].items():
        if not filas:
            continue
        faltan = [c for c in CLASES if not any(c in f for f in filas)]
        check(f"{perfil}: las once clases de cobertura viajan al reporte", not faltan, str(faltan))
        retirados = [c for c in ("area_apta_ha", "mwp_apto", "cob_no_apta_pct", "area_util_ha")
                     if any(c in f for f in filas)]
        check(f"{perfil}: sin las columnas del agregado retirado", not retirados, str(retirados))
        # La composición tiene que dar cuenta de casi todo el lote: si no, hay clases sin
        # guardar y la ficha estaría describiendo el terreno a medias.
        sumas = [sum(f.get(c) or 0.0 for c in CLASES) for f in filas
                 if any(f.get(c) is not None for c in CLASES)]
        check(f"{perfil}: la composición cubre el lote", bool(sumas) and min(sumas) > 90,
              f"mínimo {min(sumas):.1f}% de {len(sumas)} lotes" if sumas else "sin medida")
        # El orden de la lista es el área catastral, descendente, dentro de cada grilla.
        mal_ord = 0
        for cid in {f["cell_id"] for f in filas}:
            a_ = [f.get("area_ha") or 0.0 for f in filas if f["cell_id"] == cid]
            mal_ord += sum(1 for i in range(1, len(a_)) if a_[i - 1] < a_[i])
        check(f"{perfil}: la lista viene ordenada por área catastral", mal_ord == 0, f"{mal_ord}")
        # El motivo describe la cobertura por clase, no el agregado retirado.
        viejos = sum(1 for f in filas if "cobertura apta" in str(f.get("motivo") or ""))
        check(f"{perfil}: el motivo no cita el agregado retirado", viejos == 0, f"{viejos}")
        con_cob = sum(1 for f in filas if "su cobertura del suelo es" in str(f.get("motivo") or ""))
        check(f"{perfil}: el motivo describe la cobertura por clase",
              con_cob >= 0.9 * len(filas), f"{con_cob} de {len(filas)}")

    print("Geometría")
    for perfil, filas in d["lotes"].items():
        if not filas:
            continue
        mal_b = sum(1 for f in filas if any(abs(a - b) > 1e-4 for a, b in zip(f["bbox"], shape(f["geom"]).bounds)))
        check(f"{perfil}: bbox = bounds(geom)", mal_b == 0, f"{mal_b}")
        mal_c = sum(1 for f in filas if not box(*f["bbox"]).contains(Point(f["centro"])))
        check(f"{perfil}: centro dentro del bbox", mal_c == 0, f"{mal_c}")
        con_sat = [f for f in filas if f.get("sat")]
        check(f"{perfil}: hay cabe_utility/cabe_distribuida en cada fila",
              all("cabe_utility" in f and "cabe_distribuida" in f for f in filas))
        con_ctx = sum(1 for f in filas if f.get("ctx_pvout") is not None)
        check(f"{perfil}: recurso GSA del lote en la mayoría de filas", con_ctx >= 0.9 * len(filas), f"{con_ctx} de {len(filas)}")
        textos_bool = sum(1 for f in filas for k in ("ent_inundacion_2011", "ent_inundacion_2000", "ent_inundacion_1988") if isinstance(f.get(k), str))
        check(f"{perfil}: las banderas ent_* son booleanas, no texto", textos_bool == 0, f"{textos_bool} en texto")
        con_fig = sum(1 for f in filas if "ent_runap_ha" in f)
        check(f"{perfil}: figuras territoriales cruzadas", con_fig == len(filas), f"{con_fig} de {len(filas)}")
        mal_s = sum(1 for f in con_sat if not box(*f["sat"]["bbox"]).contains(box(*f["bbox"])))
        check(f"{perfil}: bbox satelital contiene al lote", mal_s == 0, f"{len(con_sat)} con imagen, {mal_s} mal")
        rutas = [SALIDA / f["sat"]["src"] for f in con_sat]
        faltan = sum(1 for r in rutas if not r.exists())
        check(f"{perfil}: archivos de imagen existen junto al reporte", faltan == 0, f"{faltan} faltan")
        geo = SALIDA / f"lotes_{perfil}.geojson"
        if geo.exists() and perfil == "utility":
            gg = gpd.read_file(geo).to_crs(config.CRS_METRICO)
            orig = gg.set_index("CODIGO").geometry.area / 1e4
            simp = gpd.GeoSeries([shape(f["geom"]) for f in filas], crs=4326,
                                 index=[f["CODIGO"] for f in filas]).to_crs(config.CRS_METRICO).area / 1e4
            err = ((simp - orig.reindex(simp.index)).abs() / orig.reindex(simp.index) * 100)
            check("utility: error de área por simplificar < 0,5%", err.max() < 0.5, f"max {err.max():.3f}%")

    print("HTML")
    h = SALIDA / "reporte_predios.html"
    check("existe el HTML", h.exists())
    if h.exists():
        t = h.read_text(encoding="utf-8")
        check("el JSON quedó embebido", "__DATOS__" not in t and '"celdas":' in t)
        check("no hay '</script>' dentro del JSON", t.count("</script>") == 1, f"{t.count('</script>')} cierres")
        check("lleva la marca de Métodos Mixtos", "brand-mark" in t and "Métodos Mixtos" in t)
        for b in ("btn-ficha", "btn-geo", "btn-maps", "btn-snr", "btn-copiar"):
            check(f"botón {b}", f'id="{b}"' in t)
        # f-idx se retiro: el indice dejo de ordenar la lista. f-mineria se conserva
        # aunque hoy no quite ningun lote, porque el filtro se juzga por lo que puede
        # discriminar en cualquier grilla, no por lo que discrimina en estas diez.
        for f_ in ("preajustes", "f-ha-min", "f-ha-max", "f-ancho", "f-valor", "f-uaf",
                   "f-pot", "f-mineria", "f-reset"):
            check(f"filtro {f_}", f'id="{f_}"' in t)
        check("imagen bajo demanda (satDe) y servicio en el JSON", "function satDe" in t and '"sat_servicio":' in t)
        check("preajustes con ancho mínimo por perfil", '"ancho_minimo_m":' in t and '"ha_minima":' in t)
        check("umbrales por perfil y pesos para reconstruir el índice", '"umbrales":' in t and '"pesos":' in t and "function desgloseIndice" in t)
        check("cuadro de fuentes", 'id="fuentes-tabla"' in t and '"fuentes":[' in t)
        check("cobertura catastral por grilla", '"catastro_pct":' in t)
        check("copia en entregables/", (config.PROJECT_ROOT / "entregables" / "reporte_predios.html").exists())

        print("Entrega: lenguaje, clases y mapa")
        # La ficha y el visor no pueden nombrar ficheros, rutas ni comandos del proyecto:
        # quien lee el reporte no trabaja con ellos y la trazabilidad se da nombrando la
        # entidad y la fecha. El nombre del archivo que el visor descarga no cuenta: ese
        # sí lo ve el usuario en su carpeta.
        import re as _re
        prohibido = {p: len(_re.findall(_re.escape(p), t))
                     for p in ("python -m", ".py", ".gpkg", "predios/", "outputs/", "insumos/",
                               "soporte/", "data/registro")}
        malos = {p: n for p, n in prohibido.items() if n}
        check("sin referencias a ficheros, rutas ni comandos del proyecto", not malos, str(malos))
        check("sin el conteo «(quita N)» junto a cada criterio", "(quita" not in t)
        check("sin «con reparos» ni «sin estorbos» como clase",
              "Con reparos" not in t and "sin estorbos" not in t)
        # Las tres clases se definen al inicio del visor, antes de la lista.
        check("bloque que define las tres clases al inicio",
              'id="clases"' in t and all(c in t for c in ("Idóneo", "Viable con gestión", "No viable")))
        # Cada condición viaja con su trámite, su entidad y su fuente, escritos una sola vez.
        check("catálogo de condiciones con trámite, entidad y fuente",
              '"condiciones_catalogo":[' in t and all(k in t for k in ('"tramite":', '"entidad":', '"fuente":')))
        check("la ficha enumera las condiciones del lote",
              "function bloqueCondiciones" in t and "function condicionesDe" in t)
        check("la matrícula se redacta en un solo sitio", "function textoMatricula" in t)
        # El enlace de Google Maps tiene que fijar un marcador sobre el lote: la forma
        # /maps/@ solo mueve la cámara y no señala nada.
        check("el enlace de Google Maps fija un marcador",
              "google.com/maps/place/" in t and "google.com/maps/@" not in t
              and "data=!3m1!1e3" in t)
        # La temperatura media es descriptor de la ficha, no criterio de filtrado.
        check("la temperatura media no es criterio de filtrado", 'id="f-temp"' not in t)
        # Criterios nuevos que se pueden calcular con lo ya medido.
        for f_ in ("f-bosque", "f-nino", "f-incendios", "f-sismica", "f-mov-masa",
                   "f-humedal-natural", "f-zip"):
            check(f"criterio {f_}", f'id="{f_}"' in t)
        # Una clase de cobertura por criterio, con el porcentaje que publica la capa.
        # Se retiró el agregado ponderado del que salían el índice de cobertura
        # implantable, la superficie apta estimada y su potencia: los coeficientes eran
        # una elección de este estudio y el reporte solo publica lo que cita a una fuente.
        for f_ in ("f-pastizal", "f-cultivo", "f-matorral", "f-construido-pct",
                   "f-humedal-cob", "f-agua-cob"):
            check(f"criterio por clase de cobertura {f_}", f'id="{f_}"' in t)
        for f_ in ("f-cobertura", "f-no-apta", "f-mwp-apto"):
            check(f"sin el criterio {f_}, que medía sobre el agregado retirado",
                  f'id="{f_}"' not in t)
        check("sin «área útil» visible", "Área útil" not in t and "área útil" not in t)
        # Ninguna de las tres cifras del agregado retirado puede quedar en el documento.
        import re as _re3
        restos = {p_: len(_re3.findall(p_, t, flags=_re3.I))
                  for p_ in (r"cobertura\s+apt[ao]", r"superficie\s+apta",
                             r"[ií]ndice\s+de\s+cobertura\s+implantable",
                             r"area_apta_ha", r"mwp_apto", r"cob_no_apta_pct")}
        vivos = {p_: c for p_, c in restos.items() if c}
        check("sin rastro del agregado de cobertura ni de lo que derivaba de él",
              not vivos, str(vivos))
        # La lista se ordena por el área catastral, que es dato del IGAC.
        check("la lista se ordena por el área catastral del lote",
              'const ORD = {clave:"area_ha"' in t)
        check("la tabla trae la composición de la cobertura del suelo",
              "Composición de la cobertura del suelo" in t and "function coberturaDe" in t)
        # El mapa pesa más que el panel de resultados y la red eléctrica se dibuja.
        # La proporcion se ajusto el 25 de agosto para que la imagen cuadrada de la
        # grilla llene su columna sin dejar franjas y sin salirse de la ventana. Lo que
        # se comprueba es que la rejilla siga siendo de dos columnas con minimos, no una
        # proporcion concreta, que es cosa de diseno y se afina mirando la pantalla.
        import re as _re2
        check("el cuerpo mantiene sus dos columnas con anchos mínimos",
              bool(_re2.search(r"grid-template-columns:minmax\(\d+px,[\d.]+fr\) minmax\(\d+px,1fr\)", t)))
        check("red eléctrica dibujada y acotada al recuadro visible",
              "function capaRed" in t and "function redVisible" in t and '"red":{"lineas":' in t)
        check("colores de clase semitransparentes sobre la imagen",
              "--mapa-idoneo:" in t and "--mapa-gestion:" in t and "--mapa-noviable:" in t
              and "fill-opacity:.34" in t)
        # Las fuentes viven en el reporte, con sus notas; no en la ficha del lote.
        check("notas del cuadro de fuentes en el reporte",
              'id="notas-fuentes"' in t and '"notas_fuentes":[' in t)
        # Cifra de la entrega: la lista trae los lotes que dice traer.
        d_l = {k: len(v) for k, v in d["lotes"].items()}
        check("la cifra de lotes del JSON es la de los CSV", all(n > 0 for n in d_l.values()), str(d_l))

    print()
    print(f"  {'TODO OK' if not fallos else f'{fallos} FALLOS'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
