"""
Lee certificados de tradición y libertad (PDF o TXT) y emite un semáforo de compra.

Normaliza el texto (marca de agua SNR intercalada, tildes corrompidas), segmenta las
anotaciones, resuelve las canceladas encadenando "Se cancela anotación No:" y evalúa
los riesgos de RIESGOS. Salida por certificado: color (rojo, ambar, verde) con razón,
titular y hallazgos; resumen en outputs/reporte/certificados_semaforo.csv.
Patrones según la convención SNR (Res. 7448/2021, códigos legacy de 3 dígitos) y dos
certificados reales (matrículas 060-10155 y 060-1174); si una ORIP imprime distinto,
`--crudo` muestra el texto normalizado para ajustar.
Uso: python -m predios.certificados folio1.pdf ...   |   --prueba (autoverificación)
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]
import config  # noqa: F401

# --------------------------------------------------------------------------
# Normalización
# --------------------------------------------------------------------------

MARCA_AGUA = re.compile(
    r"SUPERINTENDENCIA\s+DE\s+NOTARIADO\s+Y\s+REGISTRO\s+LA\s+GUARDA\s+DE\s+LA\s+FE\s+"
    r"PUBLICA(\s+OFICINA\s+DE\s+REGISTRO\s+DE\s+INSTRUMENTOS\s+PUBLICOS\s+DE\s+\w+)?"
    r"(\s+ORIP)?")


def normalizar(texto: str) -> str:
    """Mayúsculas ASCII sin tildes, sin marca de agua, espacios colapsados por línea."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.upper().replace("Ñ", "N").replace("\\", "N")   # 'SE\OR' es SEÑOR corrompido
    t = MARCA_AGUA.sub(" ", t)
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in t.splitlines()]
    return "\n".join(ln for ln in lineas if ln)


def extraer_pdf(ruta: Path) -> str:
    """Texto del PDF con pypdf o, en su defecto, pdfplumber."""
    try:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(ruta)).pages)
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(ruta)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except ImportError:
        raise SystemExit("Instala pypdf o pdfplumber para leer PDF, o pasa el texto en .txt")


# --------------------------------------------------------------------------
# Segmentación del folio
# --------------------------------------------------------------------------

def anotaciones(texto: str) -> list[dict]:
    """
    Bloques de anotación con número, fecha, documento, especificación y vigencia. Una
    anotación queda cancelada si un bloque posterior la cita en "Se cancela anotación
    No:". La fecha 01-01-1901 es el marcador de fecha desconocida de la SNR.
    """
    partes = re.split(r"(?=ANOTACION:?\s*NRO\.?\s*\d+)", texto)
    bloques = []
    for p in partes[1:]:
        m = re.match(r"ANOTACION:?\s*NRO\.?\s*(\d+)\s*FECHA:?\s*([\d-]+)?", p)
        if not m:
            continue
        bloques.append({
            "nro": int(m.group(1)),
            "fecha": m.group(2) or "",
            "doc": (re.search(r"DOC:?\s*(.+)", p) or [None, ""])[1][:160].strip(),
            "especificacion": (re.search(r"ESPECIFICACION:?\s*(.+)", p) or [None, ""])[1][:160].strip(),
            "texto": p,
            "cancelada": False,
        })
    cancela = set()
    for b in bloques:
        for m in re.finditer(r"SE\s+CANCELA\s+ANOTACION(?:ES)?\s+NO:?\s*([\d,\s]+)", b["texto"]):
            cancela |= {int(x) for x in re.findall(r"\d+", m.group(1))}
    for b in bloques:
        b["cancelada"] = b["nro"] in cancela
    return bloques


def total_declarado(texto: str) -> int | None:
    """Total de anotaciones que declara el certificado, para cotejar con las parseadas."""
    m = re.search(r"NRO\s+TOTAL\s+DE\s+ANOTACIONES:?\s*\*?(\d+)\*?", texto)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Riesgos evaluados
# --------------------------------------------------------------------------
# gravedad: 'rojo' descarta la compra directa, 'ambar' se gestiona antes del cierre,
# 'nota' informa sin bloquear. sensible_a_cancelacion: el riesgo desaparece cuando su
# anotación está cancelada.

RIESGOS = [
    dict(clave="falsa_tradicion", nombre="Falsa tradición (dominio incompleto)",
         gravedad="rojo", sensible_a_cancelacion=False,
         patrones=[r"FALSA\s+TRADICION",
                   r"DERECHOS\s+Y\s+ACCIONES|COSA\s+AJENA|POSESION\s+CON\s+ANTECEDENTE",
                   r"MEJORAS?\s+EN\s+(PREDIO|SUELO)\s+AJENO|DERECHOS\s+HERENCIALES"],
         consecuencia="El vendedor no es dueño pleno: la compra no da propiedad ni "
                      "sirve de garantía. Saneable solo por pertenencia (años)."),
    dict(clave="origen_baldio", nombre="Origen en baldío adjudicado",
         gravedad="rojo", sensible_a_cancelacion=False,
         patrones=[r"ADJUDICACION\s+(DE\s+)?BALDIOS?",
                   r"ADJUDICACION\s+UNIDAD\s+AGRICOLA\s+FAMILIAR",
                   r"RESOLUCION\s+\d+\s+DEL?\s+[\d-]+\s+(INCORA|INCODER)",
                   r"AGENCIA\s+NACIONAL\s+DE\s+TIERRAS"],
         consecuencia="Art. 72 Ley 160/1994: comprar por encima de la UAF municipal es "
                      "nulo. No se sanea; se estructura sin compra (arriendo, usufructo, "
                      "servidumbre) con concepto jurídico caso a caso."),
    dict(clave="nunca_salio_nacion", nombre="El predio no ha salido del dominio de la Nación",
         gravedad="rojo", sensible_a_cancelacion=False,
         patrones=[r"NO\s+HA\s+SALIDO\s+DEL\s+DOMINIO\s+DEL\s+ESTADO",
                   r"PRESUNCION\s+DE\s+BALDIO", r"TERRENO\s+BALDIO\s+DE\s+LA\s+NACION"],
         consecuencia="No hay propiedad privada que comprar."),
    dict(clave="restitucion", nombre="Medida de restitución de tierras (Ley 1448)",
         gravedad="rojo", sensible_a_cancelacion=True,
         patrones=[r"RESTITUCION\s+DE\s+TIERRAS|TIERRAS\s+DESPOJADAS",
                   r"PROTECCION\s+JURIDICA\s+DEL\s+PREDIO",
                   r"SUSTRACCION\s+PROVISIONAL\s+DEL\s+COMERCIO",
                   r"NO\s+NEGOCIABLE\s+POR\s+ACTO\s+ENTRE\s+VIVOS"],
         consecuencia="Vigente bloquea o hace de altísimo riesgo la compra; cancelada, "
                      "pedir a la URT certificación de no inclusión en el RTDAF."),
    dict(clave="extincion_sae", nombre="Extinción de dominio o bienes SAE",
         gravedad="rojo", sensible_a_cancelacion=True,
         patrones=[r"EXTINCION\s+DEL?\s+(DERECHO\s+DE\s+)?DOMINIO",
                   r"SOCIEDAD\s+DE\s+ACTIVOS\s+ESPECIALES|\bSAE\b|JUSTICIA\s+Y\s+PAZ"],
         consecuencia="Fuera del mercado privado; solo compra al Estado en sus ventas."),
    dict(clave="proceso_agrario", nombre="Proceso agrario administrativo en curso",
         gravedad="rojo", sensible_a_cancelacion=True,
         patrones=[r"CLARIFICACION\s+DE\s+LA\s+PROPIEDAD", r"DESLINDE\s+DE\s+TIERRAS",
                   r"INDEBIDA\s+OCUPACION\s+DE\s+BALDIOS",
                   r"ORDENAMIENTO\s+SOCIAL\s+DE\s+LA\s+PROPIEDAD",
                   r"REVOCATORIA\s+DIRECTA.*BALDIO", r"OFERTA\s+DE\s+COMPRA\s+EN\s+BIEN\s+RURAL"],
         consecuencia="La ANT cuestiona el predio o lo quiere; no cerrar con esto abierto."),
    dict(clave="embargo", nombre="Embargo",
         gravedad="ambar", sensible_a_cancelacion=True,
         patrones=[r"\bEMBARGO\b"],
         consecuencia="Objeto ilícito mientras viva (art. 1521 C.C.); saneable con pago "
                      "y levantamiento, condición precedente del cierre."),
    dict(clave="hipoteca", nombre="Hipoteca",
         gravedad="ambar", sensible_a_cancelacion=True,
         patrones=[r"\bHIPOTECA\b"],
         consecuencia="Se cancela con paz y salvo del acreedor; si es hipoteca abierta, "
                      "exigir certificación del saldo. Acreedores liquidados (Caja "
                      "Agraria) tardan más vía CISA."),
    dict(clave="patrimonio_familia", nombre="Patrimonio de familia o afectación a vivienda familiar",
         gravedad="ambar", sensible_a_cancelacion=True,
         patrones=[r"PATRIMONIO\s+DE\s+FAMILIA", r"AFECTACION\s+A\s+VIVIENDA\s+FAMILIAR"],
         consecuencia="Levantamiento previo por escritura (ambos cónyuges; con menores, "
                      "licencia judicial)."),
    dict(clave="usufructo", nombre="Usufructo vigente o nuda propiedad",
         gravedad="ambar", sensible_a_cancelacion=True,
         patrones=[r"USUFRUCTO", r"NUDA\s+PROPIEDAD"],
         consecuencia="Dominio desmembrado: deben firmar usufructuario y nudo "
                      "propietario. Verificar consolidación (0127) si el usufructuario murió."),
    dict(clave="servidumbre", nombre="Servidumbres",
         gravedad="nota", sensible_a_cancelacion=True,
         patrones=[r"SERVIDUMBRE\s+(LEGAL\s+)?DE\s+\w+"],
         consecuencia="Oleoducto, gasoducto o minera restan área instalable; la de "
                      "energía puede ser sinergia para la evacuación; la de tránsito "
                      "activa puede ser el único acceso legal."),
]


# --------------------------------------------------------------------------
# Análisis
# --------------------------------------------------------------------------

def analizar_texto(texto: str) -> dict:
    """
    Semáforo de un certificado a partir de su texto crudo: matrícula, estado del folio,
    anotaciones parseadas frente a las declaradas, hallazgos por riesgo (anotación y
    vigencia), titular con marca de dominio, y color final con su razón.
    """
    t = normalizar(texto)
    bloques = anotaciones(t)
    total = total_declarado(t)

    m = re.search(r"NRO\s+MATRICULA:?\s*(\d{3})\s*-\s*(\d+)", t)
    matricula = f"{m.group(1)}-{m.group(2)}" if m else "no identificada"
    e = re.search(r"ESTADO\s+DEL\s+FOLIO:?\s*(\w+)", t)
    estado = e.group(1) if e else "no identificado"

    hallazgos = []
    for r in RIESGOS:
        for b in bloques:
            # la anotación cancelatoria repite el nombre de lo cancelado ("CANCELACION
            # HIPOTECA"); no constituye un riesgo nuevo
            if (re.search(r"\bCANCELACION\b", b["especificacion"])
                    or re.search(r"SE\s+CANCELA\s+ANOTACION", b["texto"])):
                continue
            if any(re.search(p, b["texto"]) for p in r["patrones"]):
                hallazgos.append({**{k: r[k] for k in ("clave", "nombre", "gravedad",
                                                       "consecuencia")},
                                  "anotacion": b["nro"], "fecha": b["fecha"],
                                  "cancelada": b["cancelada"],
                                  "activa": not (b["cancelada"] and r["sensible_a_cancelacion"])})
        if not bloques:   # sin segmentación, buscar sobre el texto plano
            if any(re.search(p, t) for p in r["patrones"]):
                hallazgos.append({**{k: r[k] for k in ("clave", "nombre", "gravedad",
                                                       "consecuencia")},
                                  "anotacion": None, "fecha": "", "cancelada": False,
                                  "activa": True})

    # titular: último "A:" (marca X o I) no cancelado; I = dominio incompleto
    titular, marca = None, None
    for b in bloques:
        if b["cancelada"]:
            continue
        for pm in re.finditer(r"^A:\s*(.+?)(?:\s+(?:CC#?|NIT)\s*[\d.\s-]+)?\s+([XI])\s*$",
                              b["texto"], re.M):
            titular, marca = pm.group(1).strip()[:80], pm.group(2)

    activos = [h for h in hallazgos if h["activa"]]
    rojos = [h for h in activos if h["gravedad"] == "rojo"]
    ambares = [h for h in activos if h["gravedad"] == "ambar"]
    if estado == "CERRADO":
        color, razon = "rojo", "folio cerrado: el predio ya no existe como tal"
    elif marca == "I":
        color, razon = "rojo", "el último titular tiene dominio incompleto (marca I)"
    elif rojos:
        color, razon = "rojo", "; ".join(sorted({h["nombre"] for h in rojos}))
    elif ambares:
        color, razon = "ambar", "; ".join(sorted({h["nombre"] for h in ambares}))
    else:
        color, razon = "verde", "sin riesgos detectados en el folio"

    return {"matricula": matricula, "estado_folio": estado,
            "anotaciones_parseadas": len(bloques), "anotaciones_declaradas": total,
            "parseo_completo": (total is None or total == len(bloques)),
            "titular": titular, "marca_titular": marca,
            "hallazgos": hallazgos, "color": color, "razon": razon}


# --------------------------------------------------------------------------
# Autoverificación con fragmentos reales documentados
# --------------------------------------------------------------------------

_PRUEBAS = [
    ("restitución vigente detectada como rojo",
     "Nro Matrícula: 060-10155\nESTADO DEL FOLIO: ACTIVO\n"
     "ANOTACION: Nro 7 Fecha: 10-04-2015\n"
     "Doc: RESOLUCION RB 0667 DEL 10-04-2015 UNIDAD DE RESTITUCION DE TIERRAS DESPOJADAS\n"
     "ESPECIFICACION: MEDIDA CAUTELAR: 0482 PROTECCIÓN JURÍDICA DEL PREDIO\n"
     "NRO TOTAL DE ANOTACIONES: *7*", "rojo"),
    ("restitución cancelada baja a verde",
     "Nro Matrícula: 060-10155\nESTADO DEL FOLIO: ACTIVO\n"
     "ANOTACION: Nro 7 Fecha: 10-04-2015\n"
     "ESPECIFICACION: MEDIDA CAUTELAR: 0482 PROTECCION JURIDICA DEL PREDIO\n"
     "ANOTACION: Nro 8 Fecha: 01-02-2019\n Se cancela anotación No: 7\n"
     "ESPECIFICACION: CANCELACION: 0846 CANCELACION PROTECCION JURIDICA DEL PREDIO\n"
     "NRO TOTAL DE ANOTACIONES: *8*", "verde"),
    ("adjudicación INCORA es rojo aunque esté antigua",
     "ANOTACION: Nro 1 Fecha: 05-08-1971\n"
     "Doc: RESOLUCION 1234 DEL 05-08-1971 INCORA\n"
     "ESPECIFICACION: MODO DE ADQUISICION: 0103 ADJUDICACION BALDIOS", "rojo"),
    ("hipoteca legacy 210 sin cancelar es ámbar",
     "ANOTACION: Nro 2 Fecha: 12-03-1985\n"
     "ESPECIFICACION: GRAVAMEN: 210 HIPOTECA", "ambar"),
    ("hipoteca cancelada con código legacy 650 queda en verde",
     "ANOTACION: Nro 2 Fecha: 12-03-1985\nESPECIFICACION: GRAVAMEN: 210 HIPOTECA\n"
     "ANOTACION: Nro 6 Fecha: 20-11-1994\n Se cancela anotación No: 2\n"
     "ESPECIFICACION: CANCELACION: 650 CANCELACION HIPOTECA", "verde"),
    ("falsa tradición por compraventa de derechos y acciones es rojo",
     "ANOTACION: Nro 3 Fecha: 09-09-2001\n"
     "ESPECIFICACION: FALSA TRADICION: 0605 COMPRAVENTA DERECHOS Y ACCIONES", "rojo"),
    ("folio limpio con marca de agua intercalada queda verde",
     "SUPERINTENDENCIA DE NOTARIADO Y REGISTRO LA GUARDA DE LA FE PUBLICA\n"
     "Nro Matrícula: 062-5501\nESTADO DEL FOLIO: ACTIVO\n"
     "ANOTACION: Nro 1 Fecha: 03-05-2010\n"
     "Doc: ESCRITURA 890 DEL 03-05-2010 NOTARIA UNICA DE MONTELIBANO\n"
     "ESPECIFICACION: MODO DE ADQUISICION: 0125 COMPRAVENTA\n"
     "PERSONAS QUE INTERVIENEN EN EL ACTO\nDE: PEDRO PEREZ CC# 123 X\n"
     "A: MARIA GOMEZ CC# 456 X\nNRO TOTAL DE ANOTACIONES: *1*", "verde"),
]


def prueba() -> int:
    """Autoverificación con fragmentos reales; devuelve 1 si alguna falla."""
    fallos = 0
    for nombre, texto, esperado in _PRUEBAS:
        r = analizar_texto(texto)
        ok = r["color"] == esperado
        fallos += not ok
        print(f"  {'ok ' if ok else 'MAL'} {nombre}  ->  {r['color']}"
              + ("" if ok else f" (esperaba {esperado}; razón: {r['razon']})"))
    print(f"\n  {len(_PRUEBAS) - fallos} de {len(_PRUEBAS)} pruebas pasan")
    return 1 if fallos else 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    """CLI: analiza los certificados dados o corre la autoverificación."""
    ap = argparse.ArgumentParser(
        description="Semáforo de compra desde certificados de tradición y libertad")
    ap.add_argument("archivos", nargs="*", help="PDF o TXT de certificados")
    ap.add_argument("--prueba", action="store_true", help="autoverificación sin archivos")
    ap.add_argument("--crudo", action="store_true", help="imprime el texto normalizado")
    a = ap.parse_args(argv)

    if a.prueba:
        return prueba()
    if not a.archivos:
        ap.print_help()
        return 0

    import pandas as pd
    filas = []
    for ruta in map(Path, a.archivos):
        texto = extraer_pdf(ruta) if ruta.suffix.lower() == ".pdf" else \
            ruta.read_text(encoding="utf-8", errors="replace")
        if a.crudo:
            print(normalizar(texto))
            continue
        r = analizar_texto(texto)
        filas.append({"archivo": ruta.name, "matricula": r["matricula"],
                      "color": r["color"], "razon": r["razon"],
                      "titular": r["titular"], "estado_folio": r["estado_folio"],
                      "parseo_completo": r["parseo_completo"]})
        print(f"\n{ruta.name}  matrícula {r['matricula']}  [{r['color'].upper()}]")
        print(f"  {r['razon']}")
        if r["titular"]:
            print(f"  titular: {r['titular']} (marca {r['marca_titular']})")
        if not r["parseo_completo"]:
            print(f"  aviso: se parsearon {r['anotaciones_parseadas']} anotaciones de "
                  f"{r['anotaciones_declaradas']} declaradas; revisar con --crudo")
        for h in r["hallazgos"]:
            marca = "cancelada" if h["cancelada"] else "VIGENTE"
            print(f"    an. {h['anotacion']} ({h['fecha'] or 's.f.'}) {marca}: {h['nombre']}")

    if filas and not a.crudo:
        salida = config.PROJECT_ROOT / "outputs" / "reporte" / "certificados_semaforo.csv"
        pd.DataFrame(filas).to_csv(salida, index=False, encoding="utf-8-sig")
        print(f"\n  resumen -> {salida.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
