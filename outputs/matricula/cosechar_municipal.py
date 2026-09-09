"""Matricula inmobiliaria desde los portales de impuesto predial municipal.

Varias alcaldias publican su base predial con la matricula, sin registro y sin
captcha. Donde existe, resuelve en minutos lo que por el portal de la
Superintendencia costaria semanas, porque alli el cupo gratuito son once consultas
por cuenta y dia.

Comprobado el 24 de agosto de 2026: San Marcos devuelve matricula en 133 de sus 161
lotes.

El campo PrdMat llega a veces con un valor que no es una matricula (se vio un
14 digitos corrido). Solo se acepta lo que encaja en el formato ORIP-numero.

DESDE EL 25 DE AGOSTO DE 2026 ESTE MODULO YA NO ES EL PASO. El paso automatico es
predios/matricula_auto.py, que descubre solo que municipios tienen portal armando la
direccion con el patron de la plataforma y comprobandola de verdad, y que llama aqui a
consultar() para cosechar. El diccionario PORTALES de abajo queda como registro de los
tres portales que se encontraron a mano; el descubrimiento automatico redescubre esos
mismos tres y no depende de esta lista.

Uso:  python outputs/matricula/cosechar_municipal.py [--escribir]
Sin --escribir solo informa y no toca la cache.
"""
import argparse
import json
import pathlib
import re
import sys
import time

import pandas as pd
import requests

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CACHE = RAIZ / "data" / "registro" / "matriculas.csv"
LOTES = RAIZ / "outputs" / "reporte" / "lotes_utility.csv"

#: Portales verificados. La clave es el codigo DANE del municipio.
PORTALES = {
    "70708": ("San Marcos",
              "https://sanmarcos-sucre.softwaretributario.com/swit/"
              "Impuestos.Publico.Predial.aNxGetPrediosXReferencia.aspx"),
    "08436": ("Manatí",
              "https://manati-atlantico.softwaretributario.com/swit/"
              "Impuestos.Publico.Predial.aNxGetPrediosXReferencia.aspx"),
    "08141": ("Candelaria",
              "https://candelaria-atlantico.softwaretributario.com/swit/"
              "Impuestos.Publico.Predial.aNxGetPrediosXReferencia.aspx"),
}

MATRICULA = re.compile(r"^\d{2,4}-\d+$")
HOY = "2026-08-24"


def consultar(url, npn, espera=15):
    """Devuelve (matricula, nombre_predio) o (None, motivo)."""
    try:
        r = requests.get(url, params={"ImpCod": "IPU", "term": npn[5:]}, timeout=espera)
        filas = json.loads(r.text)
    except Exception as e:
        return None, f"el portal municipal no respondió ({type(e).__name__})"
    if not filas:
        return None, "el portal municipal no tiene este predio"
    m = (filas[0].get("PrdMat") or "").strip()
    nombre = (filas[0].get("PrdDir") or "").strip()
    if not MATRICULA.match(m):
        return None, "el portal municipal no registra matrícula para este predio"
    return m, nombre


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--escribir", action="store_true",
                    help="añade lo obtenido a la caché de matrículas")
    a = ap.parse_args(argv)

    lotes = pd.read_csv(LOTES, sep=None, engine="python", dtype=str)
    previo = (pd.read_csv(CACHE, sep=None, engine="python", dtype=str)
              if CACHE.exists() else pd.DataFrame())
    if not previo.empty:
        previo.columns = [c.lstrip("﻿") for c in previo.columns]
    ya = set(previo["CODIGO"]) if "CODIGO" in previo else set()

    nuevas = []
    for dane, (nombre_mun, url) in PORTALES.items():
        sub = lotes[lotes.CODIGO.str.startswith(dane)]
        if sub.empty:
            continue
        ok = 0
        for i, (_, r) in enumerate(sub.iterrows()):
            if r.CODIGO in ya:
                continue
            mat, extra = consultar(url, r.CODIGO)
            nuevas.append({
                "CODIGO": r.CODIGO,
                "matricula_inmobiliaria": mat or "",
                "fuente": f"portal de impuesto predial de {nombre_mun}",
                "fecha": HOY,
                "estado": "ok" if mat else "sin_dato",
                "motivo": (f"Matrícula {mat}. Fuente: portal de impuesto predial de "
                           f"{nombre_mun}, consultado el 24 de agosto de 2026."
                           if mat else
                           f"Sin dato. {extra[0].upper() + extra[1:]}. Se solicita a la "
                           f"Superintendencia de Notariado y Registro por derecho de "
                           f"petición, sin costo y con respuesta en diez días hábiles."),
            })
            ok += bool(mat)
            if i and i % 40 == 0:
                time.sleep(0.5)
        print(f"  {nombre_mun:14s} {ok:3d} de {len(sub):3d} con matrícula")

    if not nuevas:
        print("nada nuevo que añadir")
        return 0

    df = pd.DataFrame(nuevas)
    con = int((df.estado == "ok").sum())
    print(f"\ntotal nuevo: {con} matrículas de {len(df)} lotes consultados")

    if a.escribir:
        salida = pd.concat([previo, df], ignore_index=True) if not previo.empty else df
        salida = salida.drop_duplicates(subset=["CODIGO"], keep="first")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        salida.to_csv(CACHE, index=False, encoding="utf-8-sig")
        print(f"caché -> {CACHE.relative_to(RAIZ)}  ({len(salida)} filas)")
    else:
        print("no se escribió nada. Repetir con --escribir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
