"""
Las normas que sustentan los criterios del reporte, guardadas completas.

Cada criterio de exclusión o de aptitud se apoya en una norma concreta, y la norma tiene
que estar disponible entera, no en resumen. Un abecé ministerial sirve para entender pero
no para citar: dice lo que el ministerio quiere destacar, no lo que el articulado dice.

Las descargas van a data/normativa y se espejan en el bucket, igual que el resto de
insumos. Se guardan tal como las publica la fuente, sin reformatear.

Uso:
    .venv\\Scripts\\python.exe normativa.py            # descarga lo que falte
    .venv\\Scripts\\python.exe normativa.py --subir    # y lo publica en el bucket
    .venv\\Scripts\\python.exe normativa.py --listar   # solo muestra el estado
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import warnings
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
# La raiz y soporte/ van al path: config y gcs viven en soporte/, y los paquetes
# del pipeline se importan desde la raiz.
_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte")]
import config

UA = {"User-Agent": "prospectos-solares/1.0 (Metodos Mixtos Consultores)"}
CARPETA = config.PROJECT_ROOT / "data" / "normativa"
BUCKET = "prospectos"
PREFIJO = "insumos/normativa"

#: Cada entrada es una norma citada en el reporte. El campo "para" dice qué criterio
#: sostiene, que es lo que hace útil tener el archivo y no solo la referencia.
#:
#: Donde la entidad publica PDF se guarda el PDF. Donde solo hay HTML se guarda el HTML
#: del texto consolidado, que además trae las notas de vigencia y las modificaciones
#: posteriores, cosa que el PDF del diario oficial no tiene.
NORMAS = [
    {
        "clave": "ley-2-1959",
        "titulo": "Ley 2ª de 1959",
        "descripcion": "Crea las siete Zonas de Reserva Forestal nacionales.",
        "para": "Identifica la figura que cubre parte de las celdas candidatas.",
        "url": "https://www.minambiente.gov.co/wp-content/uploads/2021/08/ley-2-1959.pdf",
        "fuente": "MinAmbiente",
        "ext": "pdf",
    },
    {
        "clave": "resolucion-110-2022-mads",
        "titulo": "Resolución 110 de 2022 del MADS",
        "descripcion": ("Actividades, requisitos y procedimiento para la sustracción de "
                        "áreas de reserva forestal. Derogó la Resolución 1526 de 2012 "
                        "salvo sus artículos 7 y 8."),
        "para": ("Sustenta que la Ley 2ª condiciona pero no prohíbe, y que para líneas "
                 "de transmisión pide sustracción temporal."),
        "url": "https://www.minambiente.gov.co/wp-content/uploads/2022/02/Resolucion-110-de-2022.pdf",
        "fuente": "MinAmbiente",
        "ext": "pdf",
    },
    {
        "clave": "resolucion-0305-2026-mads",
        "titulo": "Resolución 0305 de 2026 del MADS",
        "descripcion": ("Manual para la Compensación del Medio Biótico y de la "
                        "Sustracción de Áreas de Reserva Forestal."),
        "para": "Fija las compensaciones que costea un proyecto que sustrae.",
        "url": ("https://sidn.ramajudicial.gov.co/SIDN/NORMATIVA/TEXTOS_COMPLETOS/"
                "8_RESOLUCIONES/RESOLUCIONES%202026/MADS%20Resolucion%200305%20de%202026.pdf"),
        "fuente": "Rama Judicial, SIDN",
        "ext": "pdf",
    },
    {
        "clave": "ley-1715-2014",
        "titulo": "Ley 1715 de 2014",
        "descripcion": ("Integración de las energías renovables no convencionales al "
                        "sistema energético nacional. Texto consolidado con las notas "
                        "de vigencia."),
        "para": ("Su artículo 4 declara de utilidad pública el desarrollo de FNCER, que "
                 "es el requisito que la Resolución 110 exige para pedir sustracción. "
                 "Ojo: el artículo 3 es el ámbito de aplicación, no la declaratoria."),
        "url": "http://www.secretariasenado.gov.co/senado/basedoc/ley_1715_2014.html",
        "fuente": "Secretaría del Senado",
        "ext": "html",
        "marca": "utilidad pública",
    },
    {
        "clave": "ley-2099-2021",
        "titulo": "Ley 2099 de 2021",
        "descripcion": ("Transición energética y dinamización del mercado energético. "
                        "Modificó varios artículos de la Ley 1715, entre ellos el 4."),
        "para": "Da la redacción vigente de la declaratoria de utilidad pública.",
        "url": "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=114997",
        "fuente": "Régimen Legal de Bogotá",
        "ext": "html",
        "marca": "transición energética",
    },
    {
        "clave": "ley-1930-2018",
        "titulo": "Ley 1930 de 2018",
        "descripcion": ("Gestión integral de los páramos. Texto consolidado con las "
                        "notas de vigencia y el control de constitucionalidad."),
        "para": ("Sustenta la exclusión por altitud sobre 3.000 m. Su artículo 5 "
                 "prohíbe en páramo las actividades de alto impacto."),
        "url": "https://www.minambiente.gov.co/wp-content/uploads/2021/06/ley-1930-2018.pdf",
        "fuente": "MinAmbiente. Diario Oficial 50.667 del 27 de julio de 2018",
        "ext": "pdf",
    },
]


def _plano(texto: str) -> str:
    """
    Minúsculas y sin tildes, para buscar la marca sin depender del encoding.

    Estos portales sirven latin-1 sin declararlo bien, y basta con que la detección
    falle para que «páramo» quede como «pÃ¡ramo» y una comprobación literal rechace un
    archivo que está perfecto.
    """
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _destino(n: dict) -> Path:
    return CARPETA / f"{n['clave']}.{n['ext']}"


def descargar(n: dict, forzar: bool = False) -> Path | None:
    destino = _destino(n)
    if destino.exists() and not forzar:
        return destino

    CARPETA.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(n["url"], headers=UA, timeout=180)
        r.raise_for_status()
    except Exception as exc:
        print(f"  {n['titulo']:<38} error {type(exc).__name__}")
        return None

    # Un PDF que llega como HTML suele ser una página de error con código 200
    if n["ext"] == "pdf" and not r.content.startswith(b"%PDF"):
        print(f"  {n['titulo']:<38} la respuesta no es un PDF")
        return None

    # Para el HTML no basta el código 200 ni el tamaño. Estos portales devuelven la
    # plantilla de navegación entera cuando la norma no está, y pesa más de 100 KB. Se
    # comprueba que aparezca una palabra que solo puede estar en el articulado.
    if n["ext"] == "html":
        r.encoding = r.apparent_encoding or r.encoding
        if _plano(n["marca"]) not in _plano(r.text):
            print(f"  {n['titulo']:<38} el HTML no contiene «{n['marca']}», "
                  f"parece la plantilla del portal y no la norma")
            return None

    destino.write_bytes(r.content)
    print(f"  {n['titulo']:<38} {len(r.content)/1024:7.0f} KB  bajada")
    return destino


def indice() -> str:
    """Índice legible, para que la carpeta se entienda sin abrir los archivos."""
    li = ["# Normativa que sustenta el reporte", "",
          "Los archivos están en `data/normativa`, espejados en",
          f"`gs://prospectos_solares/{PREFIJO}/`. Se bajan con `python normativa.py`.", "",
          "Cada norma está completa. No hay resúmenes ni abecés: sirven para entender,",
          "no para citar, porque recogen lo que la entidad quiso destacar y no el",
          "articulado.", ""]
    for n in NORMAS:
        d = _destino(n)
        estado = f"{d.stat().st_size/1024:.0f} KB" if d.exists() else "sin descargar"
        li += [f"## {n['titulo']}", "",
               n["descripcion"], "",
               f"**Para qué se usa.** {n['para']}", "",
               f"Archivo `{d.name}` ({estado}). Fuente: {n['fuente']}.",
               f"Origen: <{n['url']}>", ""]
    return "\n".join(li)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subir", action="store_true", help="publica en el bucket")
    ap.add_argument("--forzar", action="store_true", help="vuelve a bajar todo")
    ap.add_argument("--listar", action="store_true", help="solo muestra el estado")
    a = ap.parse_args(argv)

    print("=" * 78)
    print("NORMATIVA DEL REPORTE")
    print("=" * 78)

    if a.listar:
        for n in NORMAS:
            d = _destino(n)
            print(f"  {'ok ' if d.exists() else '-- '} {n['titulo']:<38} "
                  f"{d.stat().st_size/1024:7.0f} KB" if d.exists()
                  else f"  --  {n['titulo']:<38}   falta")
        return 0

    bajadas = [d for d in (descargar(n, a.forzar) for n in NORMAS) if d]
    print(f"\n  {len(bajadas)} de {len(NORMAS)} disponibles en {CARPETA}")

    ruta_indice = config.PROJECT_ROOT / "docs" / "NORMATIVA.md"
    ruta_indice.write_text(indice(), encoding="utf-8")
    print(f"  índice -> {ruta_indice}")

    if a.subir:
        import gcs
        n = gcs.subir_carpeta(BUCKET, PREFIJO, CARPETA, "*")
        print(f"  subidos al bucket: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
