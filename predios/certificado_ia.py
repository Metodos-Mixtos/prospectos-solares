"""
Lectura asistida del certificado de tradición y libertad, para la ficha del lote.

QUÉ HACE Y QUÉ NO
-----------------
El módulo `predios.certificados` ya extrae del folio, con reglas deterministas, los
hechos duros: quién figura como titular, qué anotaciones hay, cuáles están canceladas y
qué gravámenes quedan vivos. Eso no lo sustituye nada, porque es verificable línea a
línea contra el documento.

Lo que este módulo añade es la lectura: qué significan esos hechos para quien quiere
comprar o arrendar el lote para una planta solar, qué trámite exige cada uno y qué
documento hay que pedir antes de firmar. Esa lectura la produce un modelo de lenguaje al
que se le entrega el texto del folio Y la estructura ya extraída por reglas, de modo que
no tenga que reconocer nada por su cuenta y no pueda inventar una anotación que no exista.

Cada afirmación del análisis debe citar el número de anotación del que sale. Las que
citen una anotación inexistente se descartan antes de escribir nada: es la comprobación
que impide que una lectura verosímil pero falsa llegue a la ficha.

CÓMO SE CONSULTA AL MODELO
--------------------------
Con Gemini en Vertex AI, dentro del proyecto de Google Cloud del propio trabajo, usando
las credenciales de aplicación por defecto. El cargo va a la cuenta de facturación de ese
proyecto.

Costo medido el 2 de septiembre de 2026 sobre un folio real de cinco páginas y doce
anotaciones: 22.477 tokens, unos tres centavos de dólar, alrededor de 129 pesos. Casi
todo es la salida; la entrada apenas cuenta porque el grueso viaja en caché. Para
situarlo: el certificado cuesta 23.000 pesos comprarlo, de modo que el análisis es el
0,6 por ciento del gasto de cada lote.

Un folio ya leído no se vuelve a consultar: el resultado se guarda indexado por matrícula
y las corridas siguientes lo reutilizan. El costo se paga una vez por certificado, no una
vez por corrida.

Si no hay credenciales, el módulo lo dice y el procedimiento sigue sin análisis, nunca
con un análisis inventado.

USO
---
    python -m predios.certificado_ia <folio.pdf> [--lote CODIGO] [--forzar]
    python -m predios.certificado_ia --prueba

La salida se guarda en data/registro/certificados/<matricula>.json y la consume el
generador de la ficha.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_raiz), str(_raiz / "soporte"), str(_raiz / "predios")]

import config  # noqa: E402
import certificados as cert  # noqa: E402

#: Dónde queda la lectura de cada folio, indexada por matrícula.
CACHE = config.DATA_DIR / "registro" / "certificados"

#: Modelo y ubicación en Vertex AI. Se eligió el más económico de la familia con
#: capacidad suficiente: la extracción del folio no necesita más. La ubicación `global`
#: es la única por la que responde; las regionales devuelven 404 para este modelo.
MODELO = "gemini-2.5-flash"
REGION_VERTEX = "global"

#: Proyecto de Google Cloud al que se factura. Vacío toma el de las credenciales.
PROYECTO_VERTEX = "prospectos-solares"

#: Cuánto se espera a que el modelo responda. Un folio de cinco páginas se lee en
#: menos de un minuto; el margen es para folios largos con muchas anotaciones.
ESPERA_S = 420

#: Versión del prompt. Si cambia, las lecturas guardadas con la anterior se rehacen:
#: una lectura vieja hecha con otras instrucciones no es comparable con una nueva.
VERSION = "2026-08-26.3"

#: Cuánto puede ocupar cada campo, en caracteres. No es una preferencia de estilo: la
#: ficha presenta la Parte 1 como rejilla y como tabla, y un campo que se pasa de largo
#: rompe la fila y devuelve la sección al muro de prosa que este módulo dejó atrás. El
#: prompt los pide dentro de estos límites y `validar` comprueba que se cumplan, porque
#: un límite que solo vive en el prompt se apaga en silencio en cuanto el modelo cambia.
LIMITES: dict[tuple, int] = {
    ("resumen",): 320,
    ("confianza_motivo",): 140,
    ("orip",): 60,
    ("fecha_apertura",): 35,
    ("expedido",): 70,
    ("titularidad", "nota"): 170,
    ("area", "explicacion"): 210,
    ("origen_del_dominio", "detalle"): 190,
    ("origen_del_dominio", "nota"): 130,
}

#: Listas de la Parte 2: cuántos elementos como mucho y cuánto puede medir cada uno. Un
#: elemento por asunto: la lista de documentos tiene que ser una lista de documentos, no
#: un párrafo con puntos y comas dentro de una sola entrada.
LIMITES_LISTA: dict[tuple, tuple[int, int]] = {
    ("no_consta",): (12, 90),
    ("para_el_proyecto", "condiciones_previas"): (5, 125),
    ("para_el_proyecto", "riesgos_para_implantacion"): (3, 125),
    ("para_el_proyecto", "documentos_a_pedir"): (8, 130),
}

#: Campos de la Parte 1 que van dentro de una celda de tabla. La ruta es el camino hasta
#: la lista y el último nombre es el campo de cada elemento. Estos son los topes que más
#: importan: una celda que se pasa de largo no ensancha su columna, parte la fila en
#: cuatro renglones y devuelve la tabla al muro de texto del que se sacó.
LIMITES_ITEM: dict[tuple, int] = {
    ("anotaciones", "especificacion"): 45,
    ("anotaciones", "documento"): 65,
    ("cabida", "areas", "segun"): 65,
    ("matriculas_derivadas", "concepto"): 75,
    ("gravamenes_vigentes", "detalle"): 160,
    ("afectaciones_por_obra_publica", "area"): 40,
}


# --------------------------------------------------------------------------
# El prompt
# --------------------------------------------------------------------------

PROMPT = """Haces estudio de títulos para la adquisición de suelo rural destinado a proyectos de
infraestructura. Es el oficio de quien revisa folios antes de que una empresa compre o
arriende tierra: no litiga, no avalúa, no opina sobre el precio. Establece qué dice el
registro, qué falta y qué trámite exige cada cosa.

Recibes un CERTIFICADO DE TRADICIÓN Y LIBERTAD colombiano. Tu trabajo tiene dos partes,
en este orden y sin mezclarlas.


================================  PARTE 1  ================================
                        EXTRAER LO QUE EL FOLIO DICE

Todo certificado de tradición trae los mismos campos, porque su formato lo fija la
Superintendencia. Extráelos siempre, con la misma estructura, aunque el folio sea corto,
largo, limpio o problemático. Si un campo no aparece en este folio, su valor es null y su
ausencia se anota en `no_consta`. No lo deduzcas, no lo completes, no lo estimes.

Esta parte es TRANSCRIPCIÓN, no interpretación. Dos personas leyendo el mismo folio
deberían extraer exactamente lo mismo, y tú deberías extraer lo mismo si lees el folio dos
veces. Copia las cifras y las fechas tal como están escritas.

Qué extraer:

IDENTIFICACIÓN. Matrícula, oficina de registro y círculo registral, departamento,
municipio y vereda, fecha de apertura del folio, código catastral de treinta dígitos y el
anterior si figura, estado del folio, y la fecha y hora de expedición del certificado.

CABIDA Y LINDEROS. El texto de la descripción tal como está, y todas las áreas que
aparezcan en él, cada una con la escritura que la sustenta. Un folio suele traer varias
áreas de distintas épocas: recógelas todas, en el orden en que salen, sin decidir todavía
cuál vale. Las áreas también se presentan en una tabla, así que el campo `segun` es la
escritura o el acto que sustenta esa cifra, no la explicación de por qué cambió.

ANOTACIONES. Una por una, en orden: número, fecha, radicación, documento que la soporta
con su notaría u oficina, la especificación con su código, y las personas que intervienen
distinguiendo de quién sale y a quién entra. La marca junto a cada persona importa: X es
titular de derecho real de dominio, I es titular de dominio incompleto. Si una anotación
cancela a otra, dilo, y si a esta la cancelaron, también.

Estas anotaciones se presentan al lector en una TABLA, una fila por anotación, así que
cada celda tiene que caber en su columna. La `especificacion` es el código y el nombre
del acto, y nada más: «101 COMPRAVENTA», no la línea entera con el recibo del impuesto de
registro. El `documento` es el tipo de instrumento con su número, su fecha y la notaría u
oficina: «ESCRITURA 1891 DEL 17-10-2017, NOTARÍA 41 DE BOGOTÁ», sin la casilla VALOR ACTO.
En `de` y en `a` va el nombre de cada interviniente tal como aparece, con su cédula o NIT
si el folio lo trae, uno por elemento de la lista.

SALVEDADES. Las correcciones que la propia oficina anotó sobre el folio, con su texto.

MATRÍCULAS DERIVADAS. Si de este folio salieron otras matrículas por segregación o
desenglobe, cuáles y por qué anotación. También van en tabla: el `concepto` es qué se
segregó, en una línea.


================================  PARTE 2  ================================
                    QUÉ SIGNIFICA PARA UN PROYECTO SOLAR

Ahora, y solo sobre lo que extrajiste, responde lo que necesita saber quien quiere poner
módulos fotovoltaicos en ese suelo. Cada conclusión debe poder rastrearse a una anotación
concreta o a un campo de la Parte 1.

Lo que hay que responder, siempre, aunque la respuesta sea que el folio no lo dice:

CON QUIÉN SE NEGOCIA. Quién figura hoy como titular del dominio y por qué anotación. Si
son varios, cuántas firmas hacen falta. Si es una sociedad, su razón social y su NIT, y si
la sociedad cambió de tipo entre anotaciones, señálalo.

SI SE PUEDE TRANSFERIR. Hay dominio pleno, o alguien aparece con dominio incompleto. La
falsa tradición es lo más grave que puede traer un folio, porque quien vende puede no ser
dueño de lo que vende.

QUÉ PESA SOBRE EL LOTE HOY. Hipotecas, embargos, demandas inscritas, medidas cautelares,
prohibiciones de enajenar, patrimonio de familia, afectación a vivienda familiar,
usufructo, condición resolutoria, reserva de dominio. Solo las vigentes. Una anotación
cancelada no es un gravamen, y decir que lo es es un error grave.

QUÉ OCUPA EL SUELO. Servidumbres inscritas, con atención especial a las eléctricas, de
oleoducto, gasoducto o acueducto, porque ocupan franja y condicionan dónde caben los
módulos. Y ofertas de compra o expropiaciones por obra pública, que suelen haberse llevado
una faja del predio: mira si la franja salió del folio y a qué matrícula pasó.

DE DÓNDE VIENE EL DOMINIO. Si el folio muestra adjudicación de baldío por el INCORA, el
INCODER o la Agencia Nacional de Tierras, dilo expresamente: la Ley 160 de 1994 condiciona
la acumulación por encima de la Unidad Agrícola Familiar y puede exigir autorización
previa. Si el origen es privado, dilo también. Si el folio no llega hasta el origen porque
remite a una matriz anterior, di eso, y no supongas cuál era.

SI EL ÁREA CUADRA. Compara las áreas que extrajiste. Si unas se explican por otras (por
ejemplo, un área menos la franja vendida da la siguiente), demuéstralo con la resta. Si
quedan cifras que no concilian, dilo, y di cuál es la que hoy manda. Esta comparación es
aritmética, no opinión: hazla.

QUÉ TIENE QUE PASAR ANTES DE FIRMAR. La lista de lo que hay que resolver y los documentos
que hay que pedir, cada uno con la entidad ante la que se pide.


================================  REGLAS  ================================

1. CITA LA ANOTACIÓN. Toda afirmación de la Parte 2 lleva el número de anotación del que
   sale, en su campo `anotaciones`. Lo que salga del encabezado o de la descripción va con
   lista vacía y dice de dónde sale en el texto.

2. NO COMPLETES. Si el folio no lo dice, el valor es null y la ausencia va en `no_consta`.
   Un folio que no menciona hipotecas no es un folio sin hipotecas: es un folio que no las
   menciona. La diferencia importa porque el comprador va a actuar sobre esta lectura.

3. VIGENTE NO ES LO MISMO QUE INSCRITO. Antes de llamar vigente a un gravamen, comprueba
   que ninguna anotación posterior lo canceló. La estructura que recibes ya marca cuáles
   están canceladas.

4. NO OPINES SOBRE EL NEGOCIO. No digas si conviene comprar, si el precio es razonable ni
   si el lote es buena opción. Describe la situación registral y lo que exige. La decisión
   es de quien te lee.

5. LO MISMO DOS VECES. Si te dieran este folio otra vez, la Parte 1 debe salir idéntica.
   No cambies el criterio de extracción entre lecturas.

6. ESPAÑOL DE COLOMBIA, PROSA LLANA. Explica el término técnico la primera vez que lo uses.
   Sin latinismos innecesarios. Sin rayas largas. Di "lote", no "predio".

7. CADA CAMPO TIENE SU MEDIDA. Esto es una ficha de extracción, no un informe. Lo que
   escribas no se lee como un texto seguido: la identificación se presenta como rejilla
   de etiqueta y valor, las anotaciones y las áreas como tablas, y la Parte 2 como una
   línea por asunto. Un campo que se pasa de largo no se lee más despacio: se salta.

   Junto a cada campo del esquema va su máximo en caracteres, entre paréntesis. Es un
   máximo, no una meta: si el asunto se resuelve en veinte caracteres, veinte. Si no
   cabe todo, deja lo que cambia la decisión de quien compra y suprime el resto. Nunca
   alargues para justificar ni inventes para rellenar: un campo corto y cierto vale más
   que uno largo. Y si algo importante no cupo, no lo escondas en otro campo.

8. LAS LISTAS SON LISTAS. En `condiciones_previas`, `documentos_a_pedir`,
   `riesgos_para_implantacion` y `no_consta` va UN ELEMENTO POR ASUNTO, cada uno de una
   sola frase, sin numerarlos y sin viñetas dentro del texto. Nunca un párrafo con
   puntos y comas metido en un solo elemento: eso es un párrafo disfrazado de lista.
   Cada documento por pedir va con la entidad ante la que se pide, en su propio campo.


================================  SALIDA  ================================

UN SOLO objeto JSON, sin texto antes ni después, sin bloque de código:

{
  "matricula": "<...>",
  "orip": "<el nombre de la oficina de registro CON su ciudad, no la ciudad sola:
            «Oficina de Registro de Instrumentos Públicos de Melgar» (máx 60)>",
  "circulo_registral": "<número>",
  "departamento": "<...>", "municipio": "<...>", "vereda": "<... o null>",
  "codigo_catastral": "<30 dígitos o null>",
  "codigo_catastral_anterior": "<o null>",
  "fecha_apertura": "<la fecha de apertura y su radicación, nada más (máx 35)>",
  "expedido": "<fecha y hora como aparecen, con el turno (máx 70)>",
  "estado_folio": "<activo | cerrado | null>",

  "cabida": {
    "texto": "<la descripción tal como está>",
    "areas": [{"valor": "<cifra como aparece>", "unidad": "<m2 | ha | ...>",
               "segun": "<la escritura o el acto que la sustenta, no la explicación
                          de por qué cambió (máx 65)>",
               "anotaciones": [<n>]}]
  },

  "anotaciones": [
    {"nro": <n>, "fecha": "<...>", "radicacion": "<...>",
     "documento": "<instrumento con su número, fecha y notaría u oficina, sin la
                    casilla VALOR ACTO (máx 65)>",
     "especificacion": "<código y nombre del acto, y nada más (máx 45)>",
     "de": ["<un interviniente por elemento (máx 70 cada uno)>"],
     "a": ["<un interviniente por elemento (máx 70 cada uno)>"],
     "marcas": {"<nombre>": "<X | I | null>"},
     "cancelada": <true|false>, "cancela_a": [<n>], "cancelada_por": [<n>]}
  ],

  "salvedades": ["<texto de cada una>"],
  "matriculas_derivadas": [{"matricula": "<...>", "por_anotacion": <n>,
                            "concepto": "<qué se segregó, en una línea (máx 75)>"}],

  "titularidad": {
    "titulares": [{"nombre": "<...>", "identificacion": "<cédula o NIT o null>",
                   "tipo": "<persona natural | sociedad>", "marca": "<X | I>",
                   "anotaciones": [<n>]}],
    "dominio_pleno": <true|false|null>,
    "firmas_necesarias": <número o null>,
    "nota": "<copropiedad, cambio societario, dominio incompleto; null si no hay
              nada que advertir (máx 170)>"
  },

  "gravamenes_vigentes": [
    {"tipo": "<hipoteca | embargo | demanda | medida cautelar | limitación | servidumbre>",
     "detalle": "<qué dice el folio (máx 160)>", "a_favor_de": "<... o null>",
     "anotaciones": [<n>], "como_se_levanta": "<máx 110>", "ante_quien": "<máx 60>"}
  ],

  "afectaciones_por_obra_publica": [
    {"entidad": "<... (máx 70)>", "area": "<solo la cifra con su unidad (máx 40)>",
     "anotaciones": [<n>],
     "se_ejecuto": <true|false|null>, "matricula_resultante": "<o null>"}
  ],

  "origen_del_dominio": {
    "tipo": "<privado | baldío adjudicado | no consta en el folio>",
    "detalle": "<de dónde viene el dominio, sin repetir el `tipo` al principio: la
                 ficha ya lo escribe delante (máx 190)>", "anotaciones": [<n>],
    "sujeto_ley_160": <true|false|null>,
    "nota": "<si el folio remite a una matriz anterior, dilo aquí (máx 130)>"
  },

  "area": {
    "concilian": <true|false|null>,
    "explicacion": "<la aritmética, con las restas hechas, o por qué no cuadra (máx 210)>",
    "area_vigente": "<la que hoy manda, o null>"
  },

  "para_el_proyecto": {
    "puede_transferirse": <true|false|null>,
    "condiciones_previas": ["<qué hay que resolver, uno por elemento (máx 5 elementos,
                             125 caracteres cada uno)>"],
    "documentos_a_pedir": [{"documento": "<máx 80>", "a_quien": "<la entidad, máx 50>"}],
    "riesgos_para_implantacion": ["<lo que ocupa suelo o condiciona dónde van los módulos
                                   (máx 3 elementos, 125 caracteres cada uno)>"]
  },

  "resumen": "<tres frases y no más de 320 caracteres en total. Qué es este lote en el
               registro, con quién se negocia y qué es lo único que hay que resolver
               antes de seguir.>",
  "no_consta": ["<lo que se buscó y el folio no trae, un asunto por elemento
                  (máx 12 elementos, 90 caracteres cada uno)>"],
  "confianza": "<alta | media | baja>",
  "confianza_motivo": "<en una frase, máx 140: baja si el texto viene mal extraído, si
                        faltan páginas o si las anotaciones no se pudieron leer completas>"
}

`documentos_a_pedir` admite 8 elementos como mucho: los ocho que de verdad hay que pedir
primero, no el inventario entero de lo pedible. La Parte 1 no lleva tope de número de
elementos: van todas las anotaciones, todas las áreas y todas las matrículas derivadas
que traiga el folio, por largo que sea. Lo que se acota ahí es cuánto ocupa cada celda,
no cuántas filas hay.

Si el documento NO es un certificado de tradición y libertad, devuelve exactamente
{"error": "el documento no es un certificado de tradición y libertad"} y nada más.

=======================  ESTRUCTURA EXTRAÍDA POR REGLAS  =======================
%(estructura)s

=======================  TEXTO DEL FOLIO  =======================
%(texto)s
"""


# --------------------------------------------------------------------------
# Llamada al modelo
# --------------------------------------------------------------------------

def _json_del_texto(s: str) -> dict | None:
    """
    Primer objeto JSON completo que aparezca en la respuesta.

    El modelo puede envolverlo en un bloque de código o precederlo de una frase, así que
    no se confía en que la respuesta sea JSON puro: se busca el objeto equilibrando
    llaves, ignorando las que estén dentro de una cadena.
    """
    i = s.find("{")
    while i >= 0:
        prof, dentro, escapa = 0, False, False
        for j in range(i, len(s)):
            c = s[j]
            if escapa:
                escapa = False
                continue
            if c == "\\":
                escapa = True
                continue
            if c == '"':
                dentro = not dentro
                continue
            if dentro:
                continue
            if c == "{":
                prof += 1
            elif c == "}":
                prof -= 1
                if prof == 0:
                    try:
                        return json.loads(s[i:j + 1])
                    except json.JSONDecodeError:
                        break
        i = s.find("{", i + 1)
    return None


def consultar(prompt: str, espera: int = ESPERA_S) -> tuple[dict | None, str]:
    """
    Manda el prompt a Gemini en Vertex AI y devuelve (json, motivo).

    Se usa el proyecto de Google Cloud del propio trabajo, con las credenciales de
    aplicación por defecto. El cargo va a la cuenta de facturación de ese proyecto.
    Medido sobre un folio real de cinco páginas y doce anotaciones: 22.477 tokens, unos
    tres centavos de dólar. Casi todo el costo es la salida; la entrada apenas cuenta
    porque el grueso viaja en caché, que se tarifa a la décima parte.

    No levanta nunca: devuelve None con el motivo, y quien llama decide. Un folio que no
    se pudo leer se queda sin análisis, jamás con uno inventado.
    """
    try:
        import google.auth
        from google.auth.transport.requests import Request
        import requests
    except ImportError as exc:
        return None, f"falta una dependencia: {exc.name}"

    try:
        cred, proyecto = google.auth.default()
        cred.refresh(Request())
    except Exception as exc:
        return None, ("no hay credenciales de Google Cloud. Ejecute "
                      f"gcloud auth application-default login ({type(exc).__name__})")

    proyecto = PROYECTO_VERTEX or proyecto
    if not proyecto:
        return None, "no se pudo determinar el proyecto de Google Cloud"

    url = (f"https://aiplatform.googleapis.com/v1/projects/{proyecto}"
           f"/locations/{REGION_VERTEX}/publishers/google/models/{MODELO}:generateContent")
    cabeceras = {"Authorization": f"Bearer {cred.token}",
                 "Content-Type": "application/json",
                 # Sin esta cabecera el servicio responde 403 pidiendo un proyecto de
                 # cuota, porque las credenciales de aplicación no lo llevan de serie.
                 "x-goog-user-project": proyecto}
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              # temperatura cero: la extracción del folio tiene que salir igual cada vez
              "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    try:
        r = requests.post(url, headers=cabeceras, json=cuerpo, timeout=espera)
    except Exception as exc:
        return None, f"no se pudo llamar a Vertex AI: {type(exc).__name__}"

    if r.status_code != 200:
        try:
            m = r.json().get("error", {}).get("message", "")
        except Exception:
            m = r.text[:200]
        return None, f"Vertex AI devolvió {r.status_code}: {str(m)[:200]}"

    d = r.json()
    cand = (d.get("candidates") or [{}])[0]
    if cand.get("finishReason") not in (None, "STOP"):
        return None, f"la respuesta quedó truncada: {cand.get('finishReason')}"
    partes = (cand.get("content") or {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes)
    if not texto:
        return None, "la respuesta vino vacía"

    interior = _json_del_texto(texto)
    if interior is None:
        return None, "la respuesta no contenía el JSON del análisis"
    # El consumo se guarda con el análisis: es lo que permite saber qué costó cada folio
    # sin tener que esperar a que el cargo aparezca en la consola de facturación.
    interior["_uso"] = {k: v for k, v in (d.get("usageMetadata") or {}).items()
                        if isinstance(v, int)}
    return interior, "ok"


# --------------------------------------------------------------------------
# Comprobación: que nada de lo que se afirma sea inventado
# --------------------------------------------------------------------------

def _entero(n):
    """
    Numero de anotacion, venga como entero o como texto.

    El modelo escribe a veces ["9"] en vez de [9]. Descartarlos por el tipo vaciaba la
    lista de citas y con ella la comprobacion entera, en silencio: exactamente el fallo
    que este modulo existe para evitar. Los booleanos se rechazan porque en Python True
    es un entero y colaria como anotacion 1.
    """
    if isinstance(n, bool):
        return None
    if isinstance(n, int):
        return n
    s = str(n).strip()
    return int(s) if s.isdigit() else None


def _en(d: dict, ruta: tuple):
    """Valor de una ruta de claves anidadas, o None si el camino se corta."""
    v = d
    for k in ruta:
        if not isinstance(v, dict):
            return None
        v = v.get(k)
    return v


def medidas(d: dict) -> list[str]:
    """
    Avisos por los campos que se pasaron de la medida que el prompt les fija.

    No recorta nada: recortar una afirmación jurídica por la mitad la convierte en otra
    cosa. Lo que hace es dejar constancia, porque un límite que solo vive en el prompt se
    apaga en silencio en cuanto el modelo cambia de versión, y la sección vuelve a ser el
    muro de prosa que se rediseñó para evitar. Si estos avisos aparecen, hay que apretar
    el prompt, no la maquetación.
    """
    avisos: list[str] = []
    for ruta, tope in LIMITES.items():
        v = _en(d, ruta)
        if isinstance(v, str) and len(v) > tope:
            avisos.append(f"«{'.'.join(ruta)}» mide {len(v)} caracteres y el máximo es {tope}")
    for ruta, (n_max, tope) in LIMITES_LISTA.items():
        v = _en(d, ruta)
        if not isinstance(v, list):
            continue
        if len(v) > n_max:
            avisos.append(f"«{'.'.join(ruta)}» trae {len(v)} elementos y el máximo es {n_max}")
        largos = 0
        for it in v:
            # Los documentos por pedir vienen como objeto; se mide lo que se lee.
            txt = it if isinstance(it, str) else (
                " ".join(str(it.get(k) or "") for k in ("documento", "a_quien"))
                if isinstance(it, dict) else str(it))
            largos += len(txt) > tope
        if largos:
            avisos.append(f"«{'.'.join(ruta)}»: {largos} elemento(s) por encima de "
                          f"{tope} caracteres")
    for ruta, tope in LIMITES_ITEM.items():
        lst, campo = _en(d, ruta[:-1]), ruta[-1]
        if not isinstance(lst, list):
            continue
        largos = sum(1 for it in lst if isinstance(it, dict)
                     and isinstance(it.get(campo), str) and len(it[campo]) > tope)
        if largos:
            avisos.append(f"«{'.'.join(ruta)}»: {largos} de {len(lst)} por encima de "
                          f"{tope} caracteres; esa celda parte la fila de la tabla")
    return avisos


def validar(d: dict, nros: set[int], matricula: str | None,
            canceladas: set[int] | None = None) -> tuple[dict, list[str]]:
    """
    Descarta lo que no se sostiene contra el folio y devuelve (análisis, avisos).

    Lo que se comprueba:
      - que la matrícula del análisis sea la del folio
      - que toda anotación citada exista de verdad
      - que los campos obligatorios estén
    Un hallazgo que cite una anotación inexistente se retira entero. Es preferible una
    ficha con menos hallazgos que una con un hallazgo inventado.
    """
    avisos: list[str] = []
    if not isinstance(d, dict) or d.get("error"):
        return {}, [str(d.get("error", "respuesta vacía"))] if isinstance(d, dict) else ["respuesta vacía"]

    if matricula and d.get("matricula") and _norm_mat(d["matricula"]) != _norm_mat(matricula):
        avisos.append(f"el análisis dice matrícula {d['matricula']} y el folio es {matricula}")
        d["matricula"] = matricula

    canceladas = canceladas or set()
    # Listas de la parte 2: cada afirmacion cita anotaciones y se comprueba igual que un
    # hallazgo. Se recorren aqui para que la comprobacion no dependa de que el modelo
    # use un nombre u otro.
    for clave in ("gravamenes_vigentes", "afectaciones_por_obra_publica"):
        lst = d.get(clave)
        if not isinstance(lst, list):
            d[clave] = []
            continue
        buenos_c = []
        for it in lst:
            if not isinstance(it, dict):
                continue
            crudas = it.get("anotaciones")
            crudas = crudas if isinstance(crudas, list) else ([crudas] if crudas is not None else [])
            cit = [e for e in (_entero(x) for x in crudas) if e is not None]
            malas = [n_ for n_ in cit if n_ not in nros]
            if malas:
                avisos.append(f"se retiró una entrada de {clave}: cita anotación {malas} "
                              f"y el folio no la tiene")
                continue
            if clave == "gravamenes_vigentes" and cit and set(cit) <= canceladas:
                avisos.append(f"se retiró un gravamen dado por vigente: las anotaciones "
                              f"{cit} están canceladas en el folio")
                continue
            it["anotaciones"] = cit
            it["comprobado"] = bool(cit)
            buenos_c.append(it)
        d[clave] = buenos_c
    # Las anotaciones extraidas en la parte 1 deben ser las que el folio trae, ni mas.
    ext = d.get("anotaciones")
    if isinstance(ext, list):
        sobran = [a.get("nro") for a in ext if isinstance(a, dict)
                  and _entero(a.get("nro")) is not None and _entero(a.get("nro")) not in nros]
        if sobran:
            avisos.append(f"la extracción trae anotaciones que el folio no tiene: {sobran}")
            d["anotaciones"] = [a for a in ext if isinstance(a, dict)
                                and _entero(a.get("nro")) in nros]
        faltan = sorted(nros - {_entero(a.get("nro")) for a in d["anotaciones"]
                                if isinstance(a, dict)})
        if faltan:
            avisos.append(f"la extracción no trae las anotaciones {faltan} que el folio sí")
    hs = d.get("hallazgos")
    if not isinstance(hs, list):
        if hs is not None:
            avisos.append(f"los hallazgos no venían en lista sino como {type(hs).__name__}")
        hs = []
    buenos = []
    for h in hs:
        if not isinstance(h, dict):
            avisos.append("se retiró un hallazgo que no era un objeto")
            continue
        crudas = h.get("anotaciones")
        if crudas is None:
            crudas = []
        elif not isinstance(crudas, list):
            crudas = [crudas]
        cit, raras = [], []
        for x in crudas:
            e = _entero(x)
            (cit if e is not None else raras).append(e if e is not None else x)
        if raras:
            avisos.append(f"«{str(h.get('titulo'))[:50]}»: citas ilegibles {raras}")
        # Sin "and nros": si el conjunto llegara vacio, TODO estaria sin comprobar y la
        # validacion se apagaria en silencio, que es justo lo que hay que evitar.
        malas = [n for n in cit if n not in nros]
        if malas:
            avisos.append(f"se retiró «{str(h.get('titulo'))[:60]}»: cita "
                          f"anotación {malas} y el folio no la tiene")
            continue
        # Un gravamen que las reglas dan por cancelado no puede presentarse como vigente.
        if h.get("vigente") is True and cit and set(cit) <= canceladas:
            avisos.append(f"se retiró «{str(h.get('titulo'))[:60]}»: lo da por vigente y "
                          f"las anotaciones {cit} están canceladas en el folio")
            continue
        h["anotaciones"] = cit
        # Un hallazgo sin ninguna cita no se puede comprobar contra el folio. No se
        # retira, porque las afirmaciones en negativo legitimas no citan anotacion, pero
        # se marca para que la ficha pueda decirlo en vez de darlo por verificado.
        h["comprobado"] = bool(cit)
        for c in ("titulo", "detalle", "efecto", "que_hacer", "ante_quien"):
            if c in h and not isinstance(h[c], str):
                h[c] = str(h[c]) if h[c] is not None else ""
        buenos.append(h)
    d["hallazgos"] = buenos
    sin_cita = sum(1 for h in buenos if not h["comprobado"])
    if sin_cita:
        avisos.append(f"{sin_cita} hallazgo(s) sin cita de anotación: no se pudieron "
                      f"comprobar contra el folio")

    tit = d.get("titularidad")
    if not isinstance(tit, dict):
        if tit is not None:
            avisos.append(f"la titularidad no venía como objeto sino como {type(tit).__name__}")
        d["titularidad"] = tit = {}
    ts = tit.get("titulares")
    if not isinstance(ts, list):
        if ts is not None:
            avisos.append("los titulares no venían en lista")
        tit["titulares"] = ts = []
    tit["titulares"] = [x for x in ts if isinstance(x, dict)]
    for x in tit["titulares"]:
        crudas = x.get("anotaciones")
        crudas = crudas if isinstance(crudas, list) else ([crudas] if crudas is not None else [])
        x["anotaciones"] = [e for e in (_entero(y) for y in crudas)
                            if e is not None and e in nros]
    # Listas que la ficha recorre: si vienen como cadena, el visor rompe al pintarlas y
    # deja a la vista la ficha del lote anterior bajo el encabezado del nuevo.
    pp = d.get("para_el_proyecto")
    if not isinstance(pp, dict):
        d["para_el_proyecto"] = pp = {}
    for c in ("condiciones_previas", "documentos_a_pedir"):
        v_ = pp.get(c)
        pp[c] = v_ if isinstance(v_, list) else ([v_] if isinstance(v_, str) and v_ else [])
    nc = d.get("no_consta")
    d["no_consta"] = nc if isinstance(nc, list) else ([nc] if isinstance(nc, str) and nc else [])
    avisos += medidas(d)
    return d, avisos


def _norm_mat(s) -> str:
    return re.sub(r"[^0-9]", "", str(s or ""))


# --------------------------------------------------------------------------
# Lectura de un folio
# --------------------------------------------------------------------------

def leer(ruta: Path, lote: str | None = None, forzar: bool = False,
         verbose: bool = True) -> dict | None:
    """
    Lee un folio y devuelve su análisis, usando la caché si ya se leyó.

    Devuelve None si no se pudo, nunca un análisis a medias: la ficha prefiere no
    mostrar nada a mostrar algo que no se sostiene.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        if verbose:
            print(f"  no existe: {ruta}")
        return None

    texto = cert.normalizar(cert.extraer_pdf(ruta) if ruta.suffix.lower() == ".pdf"
                            else ruta.read_text(encoding="utf-8", errors="ignore"))
    base = cert.analizar_texto(texto)
    # analizar_texto devuelve el RECUENTO de anotaciones, no la lista; la lista la da
    # anotaciones(). Sin este segundo paso el conjunto de numeros validos salia vacio y
    # la comprobacion contra anotaciones inventadas no comprobaba nada.
    lista = cert.anotaciones(texto)
    matricula = base.get("matricula")
    nros = {a.get("nro") for a in lista if isinstance(a.get("nro"), int)}
    if not nros:
        if verbose:
            print(f"  {matricula}: no se pudo leer ninguna anotación; sin ellas no se "
                  f"puede comprobar el análisis, así que no se consulta al modelo")
        return None
    # Si el folio se leyó a medias, lo que el modelo vea será una parte del documento y
    # concluirá sobre ella como si fuera el todo. Probado: con el folio cortado en la
    # anotación 7 devolvió unos titulares que vendieron en 2008, con dominio pleno y sin
    # un solo aviso, porque todas las anotaciones que citó existían. No se consulta.
    if base.get("parseo_completo") is False:
        if verbose:
            print(f"  {matricula}: el folio se leyó a medias "
                  f"({base.get('anotaciones_parseadas')} de "
                  f"{base.get('anotaciones_declaradas')} anotaciones). No se consulta: "
                  f"un análisis sobre un folio incompleto concluye sobre lo que no vio")
        return None

    clave = _norm_mat(matricula) or ruta.stem
    destino = CACHE / f"{clave}.json"
    if destino.exists() and not forzar:
        try:
            g = json.loads(destino.read_text(encoding="utf-8"))
            if g.get("version_prompt") == VERSION:
                if verbose:
                    print(f"  {matricula}: ya leído el {g.get('leido')}")
                return g
            if verbose:
                print(f"  {matricula}: leído con un prompt anterior, se rehace")
        except json.JSONDecodeError:
            pass

    if verbose:
        print(f"  {matricula}: {len(nros)} anotaciones, consultando al modelo")

    estructura = json.dumps({
        "matricula": matricula,
        "titular_detectado": base.get("titular"),
        # OJO: la clave es "especificacion", no "acto". Pedir "acto" devolvia None en
        # todas y el modelo recibia numeros y fechas sin saber QUE era cada anotacion,
        # justo lo que este diseno dice evitar. Se manda tambien el texto recortado.
        "anotaciones": [{"nro": a.get("nro"), "fecha": a.get("fecha"),
                         "especificacion": a.get("especificacion"),
                         "doc": a.get("doc"),
                         "cancelada": a.get("cancelada"),
                         "texto": (a.get("texto") or "")[:400]}
                        for a in lista],
        "marca_titular_detectada": base.get("marca_titular"),
        "estado_folio_por_reglas": base.get("estado_folio"),
        "parseo_completo": base.get("parseo_completo"),
        "anotaciones_declaradas": base.get("anotaciones_declaradas"),
        "anotaciones_parseadas": base.get("anotaciones_parseadas"),
        "hallazgos_por_reglas": base.get("hallazgos"),
        "semaforo_por_reglas": base.get("color"),
    }, ensure_ascii=False, indent=1)

    d, motivo = consultar(PROMPT % {"estructura": estructura, "texto": texto})
    if d is None:
        if verbose:
            print(f"  {matricula}: sin análisis ({motivo})")
        return None

    canceladas = {a.get('nro') for a in lista if a.get('cancelada')}
    d, avisos = validar(d, nros, matricula, canceladas)
    if not d:
        if verbose:
            print(f"  {matricula}: el análisis no se sostuvo ({'; '.join(avisos)})")
        return None

    d.update({
        "version_prompt": VERSION,
        "leido": date.today().isoformat(),
        "documento": ruta.name,
        "lote": lote,
        "avisos_validacion": avisos,
        "semaforo_por_reglas": base.get("color"),
        "razon_por_reglas": base.get("razon"),
    })
    CACHE.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if verbose:
        print(f"  {matricula}: {len(d.get('hallazgos', []))} hallazgos, "
              f"confianza {d.get('confianza')}"
              + (f", {len(avisos)} descartes" if avisos else ""))
    return d


#: Carpeta donde se dejan los certificados comprados. El procedimiento la mira en cada
#: corrida, lee lo que encuentre y lo asocia al lote por la matrícula que trae el propio
#: documento. Nadie tiene que renombrar el fichero ni decir a qué lote pertenece.
ENTRADA = config.PROJECT_ROOT / "insumos" / "certificados"

#: Extensiones que se intentan leer. Lo demás se ignora sin ruido.
LEIBLES = {".pdf", ".txt"}


def _surtir_del_bucket(carpeta: Path, verbose: bool = True) -> int:
    """
    Trae a la carpeta local los certificados que alguien haya dejado en el bucket.

    Con esto se cumple lo que se acordó el 4 de septiembre de 2026: quien tenga un folio
    lo sube a `entradas/certificados/` y el procedimiento lo recoge, sin necesidad de
    tener el repositorio clonado ni de mandarse ficheros por correo.

    Si el bucket no está a mano no pasa nada: se sigue con lo que haya en disco, que es
    como funcionaba antes. Un fallo aquí nunca debe impedir leer los folios locales.
    """
    try:
        raiz = Path(__file__).resolve().parent.parent / "soporte"
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
        import bandeja as _bandeja
        filas = _bandeja.listar("certificados")
    except Exception as exc:
        if verbose:
            print("  bandeja del bucket no disponible (" + type(exc).__name__
                  + "); se usa solo la carpeta local")
        return 0

    traidos = 0
    for objeto, _tam, _fecha in filas:
        nombre = Path(objeto).name
        if Path(nombre).suffix.lower() not in LEIBLES:
            continue
        destino = carpeta / nombre
        if destino.exists():
            continue
        try:
            origen = _bandeja.resolver(nombre, carpeta="certificados", verbose=False)
            shutil.copy2(origen, destino)
            traidos += 1
            if verbose:
                print("  traído de la bandeja del bucket: " + nombre)
        except Exception as exc:
            if verbose:
                print("  no se pudo traer " + nombre + " (" + type(exc).__name__ + ")")
    return traidos


def bandeja(carpeta: Path | None = None, forzar: bool = False,
            verbose: bool = True) -> dict:
    """
    Lee todos los certificados que haya en la carpeta de entrada.

    La matrícula sale del propio folio, así que el nombre del fichero da igual: se puede
    dejar el PDF tal como lo entrega el portal. Un certificado ya leído no se vuelve a
    consultar salvo que se pida a la fuerza, de modo que la carpeta se puede dejar llena
    sin coste.

    Los folios que no se pudieron leer no se borran ni se dan por perdidos: se informan
    con su motivo, para que quien los dejó ahí sepa qué pasó con cada uno.
    """
    carpeta = Path(carpeta or ENTRADA)
    carpeta.mkdir(parents=True, exist_ok=True)

    # Primero la bandeja del bucket, para que quien dejó ahí un folio no tenga que
    # tenerlo también en esta máquina.
    _surtir_del_bucket(carpeta, verbose=verbose)

    ficheros = sorted(f for f in carpeta.iterdir()
                      if f.is_file() and f.suffix.lower() in LEIBLES)
    if not ficheros:
        if verbose:
            print(f"  sin certificados en {carpeta}")
        return {"leidos": 0, "ya_estaban": 0, "fallidos": []}

    if verbose:
        print(f"  {len(ficheros)} certificado(s) en la bandeja")
    leidos, ya, fallidos = 0, 0, []
    for f in ficheros:
        antes = set(CACHE.glob("*.json")) if CACHE.exists() else set()
        try:
            d = leer(f, forzar=forzar, verbose=verbose)
        except Exception as exc:
            # Un folio raro no puede tumbar la corrida ni llevarse por delante los que
            # vienen detrás, que pueden estar ya pagados.
            fallidos.append((f.name, f"{type(exc).__name__}: {str(exc)[:90]}"))
            if verbose:
                print(f"  {f.name}: no se pudo leer ({type(exc).__name__})")
            continue
        if d is None:
            fallidos.append((f.name, "no se pudo leer o no es un certificado"))
        elif CACHE.exists() and set(CACHE.glob("*.json")) == antes and not forzar:
            ya += 1
        else:
            leidos += 1
    if verbose:
        print(f"  certificados: {leidos} leído(s), {ya} ya estaban, {len(fallidos)} sin leer")
    return {"leidos": leidos, "ya_estaban": ya, "fallidos": fallidos}


def de_matricula(matricula: str) -> dict | None:
    """Análisis ya guardado de una matrícula, o None. Lo usa el generador de la ficha."""
    p = CACHE / f"{_norm_mat(matricula)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Autoverificación
# --------------------------------------------------------------------------

def prueba() -> int:
    """Comprueba lo que se puede comprobar sin gastar una consulta al modelo."""
    fallos = 0

    def ok(nombre, cond, detalle=""):
        nonlocal fallos
        fallos += not cond
        print(f"  {'ok ' if cond else 'FALLA'} {nombre}" + (f"  ({detalle})" if detalle else ""))

    try:
        import google.auth
        _c, _p = google.auth.default()
        ok("hay credenciales de Google Cloud", True, PROYECTO_VERTEX or _p)
    except Exception as exc:
        ok("hay credenciales de Google Cloud", False,
           f"{type(exc).__name__}: ejecute gcloud auth application-default login")
    ok("el modelo está fijado", bool(MODELO) and bool(REGION_VERTEX),
       f"{MODELO} en {REGION_VERTEX}")

    s = 'bla bla {"a": 1, "b": {"c": "}"}} cola'
    ok("extrae el JSON aunque venga con texto alrededor",
       _json_del_texto(s) == {"a": 1, "b": {"c": "}"}})
    ok("devuelve None si no hay JSON", _json_del_texto("sin llaves") is None)

    d = {"matricula": "366-35594",
         "hallazgos": [{"titulo": "real", "anotaciones": [1, 2]},
                       {"titulo": "inventado", "anotaciones": [99]}],
         "titularidad": {"titulares": [{"nombre": "X", "anotaciones": [2, 99]}]}}
    v, av = validar(dict(d), {1, 2, 3}, "366-35594")
    ok("retira el hallazgo que cita una anotación inexistente",
       len(v["hallazgos"]) == 1 and v["hallazgos"][0]["titulo"] == "real", f"{len(av)} avisos")
    ok("limpia las anotaciones inexistentes del titular",
       v["titularidad"]["titulares"][0]["anotaciones"] == [2])

    v2, av2 = validar({"matricula": "060-1174", "hallazgos": []}, {1}, "366-35594")
    ok("avisa si la matrícula no es la del folio", any("matrícula" in a for a in av2))

    # El prompt tiene dos partes: extraer lo que el folio dice, igual en todos los
    # folios, y solo despues interpretarlo. Se comprueba que esa separacion siga ahi.
    ok("el prompt separa extracción de análisis",
       "PARTE 1" in PROMPT and "PARTE 2" in PROMPT and "TRANSCRIPCIÓN" in PROMPT)
    ok("el prompt exige citar la anotación", "CITA LA ANOTACIÓN" in PROMPT)
    ok("el prompt prohíbe completar lo que falta", "NO COMPLETES" in PROMPT)
    ok("el prompt distingue vigente de inscrito",
       "VIGENTE NO ES LO MISMO QUE INSCRITO" in PROMPT)
    ok("el prompt no pide opinar sobre el negocio", "NO OPINES SOBRE EL NEGOCIO" in PROMPT)
    ok("el prompt exige la misma extracción dos veces", "LO MISMO DOS VECES" in PROMPT)
    ok("el prompt cubre dominio incompleto", "dominio incompleto" in PROMPT)
    ok("el prompt cubre servidumbres", "Servidumbres inscritas" in PROMPT)
    ok("el prompt cubre la obra pública", "obra pública" in PROMPT)
    ok("el prompt cubre el origen baldío", "baldío" in PROMPT and "160 de 1994" in PROMPT)
    ok("el prompt pide la aritmética del área", "SI EL ÁREA CUADRA" in PROMPT)
    ok("el prompt pide decir lote y no predio", 'Di "lote", no "predio"' in PROMPT)

    # La sección de la ficha presenta la extracción como rejilla y como tablas. Eso solo
    # se sostiene si el prompt acota cuánto ocupa cada campo Y si la comprobación lo
    # verifica: un límite escrito solo en el prompt se apaga en silencio.
    ok("el prompt acota la medida de cada campo", "CADA CAMPO TIENE SU MEDIDA" in PROMPT)
    ok("el prompt exige que las listas sean listas", "LAS LISTAS SON LISTAS" in PROMPT)
    ok("el prompt dice que las anotaciones van en tabla",
       "una fila por anotación" in PROMPT)

    # Cada campo con tope tiene que estar nombrado en el prompt: si se renombra uno y se
    # olvida el otro lado, el tope queda vigilando una clave que ya no existe.
    huerfanos = [".".join(r) for r in list(LIMITES) + list(LIMITES_LISTA) + list(LIMITES_ITEM)
                 if r[-1] not in PROMPT]
    ok("cada campo con tope aparece en el prompt", not huerfanos, ", ".join(huerfanos))
    # El tope escrito en el prompt y el que comprueba `medidas` tienen que ser el mismo
    # número: si se corrige uno solo, la comprobación deja de comprobar lo que se pidió.
    faltan_prompt = [".".join(r) for r, t in
                     list(LIMITES.items()) + list(LIMITES_ITEM.items())
                     + [(r, t[1]) for r, t in LIMITES_LISTA.items()]
                     if f"máx {t}" not in PROMPT and f"{t} caracteres" not in PROMPT]
    ok("cada tope está escrito con su cifra en el prompt",
       not faltan_prompt, ", ".join(faltan_prompt))

    med = {"anotaciones": [{"nro": 1, "especificacion": "x" * 90, "documento": "y" * 20}],
           "cabida": {"areas": [{"segun": "z" * 200}]}}
    ok("avisa de la celda de tabla que se pasa de largo",
       any("anotaciones.especificacion" in a for a in medidas(med))
       and any("cabida.areas.segun" in a for a in medidas(med)))

    largo = {"resumen": "x" * 500,
             "titularidad": {"titulares": [], "nota": "y" * 900},
             "para_el_proyecto": {"condiciones_previas": ["z" * 400] * 9,
                                  "documentos_a_pedir": []},
             "no_consta": ["w" * 200]}
    av_m = medidas(largo)
    ok("avisa del campo que se pasa de largo",
       any("resumen" in a for a in av_m) and any("titularidad.nota" in a for a in av_m))
    ok("avisa de la lista con demasiados elementos",
       any("9 elementos" in a for a in av_m))
    ok("avisa del elemento de lista demasiado largo",
       any("condiciones_previas" in a and "por encima" in a for a in av_m)
       and any("no_consta" in a and "por encima" in a for a in av_m))
    corto = {"resumen": "tres frases cortas.",
             "titularidad": {"titulares": [], "nota": None},
             "para_el_proyecto": {"condiciones_previas": ["pedir el certificado"],
                                  "documentos_a_pedir": [{"documento": "folio",
                                                          "a_quien": "la ORIP"}],
                                  "riesgos_para_implantacion": []},
             "no_consta": ["hipotecas: ninguna anotación las menciona"]}
    ok("no avisa cuando todo cabe en su medida", medidas(corto) == [], str(medidas(corto)))
    ok("la validación arrastra los avisos de medida",
       any("caracteres" in a for a in validar(
           {"matricula": "366-1", "hallazgos": [], **largo}, {1}, "366-1")[1]))

    print()
    print(f"  {'TODO OK' if not fallos else f'{fallos} FALLOS'}")
    return 1 if fallos else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lectura asistida del certificado de tradición y libertad.")
    ap.add_argument("folios", nargs="*", type=Path, help="certificados en PDF o TXT")
    ap.add_argument("--lote", help="código catastral del lote al que corresponde")
    ap.add_argument("--forzar", action="store_true", help="rehace la lectura aunque esté en caché")
    ap.add_argument("--bandeja", action="store_true",
                    help="lee todos los certificados de insumos/certificados")
    ap.add_argument("--prueba", action="store_true", help="autoverificación, sin consultar al modelo")
    a = ap.parse_args(argv)

    if a.prueba:
        return prueba()
    if a.bandeja:
        r = bandeja(forzar=a.forzar)
        for nombre, motivo in r["fallidos"]:
            print(f"    sin leer: {nombre}  ({motivo})")
        return 0
    if not a.folios:
        ap.error("hay que dar un certificado, o usar --bandeja, o --prueba")

    print(f"Lectura de {len(a.folios)} certificado(s)")
    n = 0
    for f in a.folios:
        if leer(f, lote=a.lote, forzar=a.forzar):
            n += 1
    print(f"\n  {n} de {len(a.folios)} leídos. Quedan en {CACHE}")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
