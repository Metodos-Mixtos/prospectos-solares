# -*- coding: utf-8 -*-
"""
Plantilla HTML/CSS/JS del visor de lotes. Misma paleta y marca que el reporte de
grillas. Autónoma: datos embebidos como JSON, imágenes en satelital/, sin CDN.

Cuatro zonas: el bloque que define las tres clases del lote, la banda de criterios de
filtrado, los resultados (mapa de la grilla, considerablemente mayor, y la lista
ordenable) y la ficha del lote, que solo aparece al elegir uno.

Los catálogos que siguen (clases, criterios de filtrado y glosario) se
escriben una sola vez aquí y de ellos salen a la vez los controles del HTML y las
constantes que lee el JavaScript, de modo que etiqueta, ayuda y cálculo no puedan
desincronizarse.
"""
from __future__ import annotations

import json as _json


def _js(valor) -> str:
    """Serializa a JSON para incrustarlo dentro de <script> sin cerrar la etiqueta."""
    return _json.dumps(valor, ensure_ascii=False).replace("</", "<\\/")


def _e(texto) -> str:
    """Escapa el texto que va como contenido o como atributo del HTML generado."""
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------------
# Las tres clases del lote. Se muestran al inicio del visor, antes de la lista, con
# la condición exacta que pone un lote en cada una.
# --------------------------------------------------------------------------------
CLASES_DEF = [
    {
        "clase": "Idóneo",
        "css": "c1",
        "glifo": "●",
        "color": "azul",
        "definicion": (
            "Ninguna de las condiciones adversas que el estudio comprueba se presenta en "
            "este lote. Cuando alguna de las fuentes no cubre el lote, la ficha lo dice."),
        "condicion": (
            "No se cumple ninguna de las condiciones de las otras dos clases."),
    },
    {
        "clase": "Viable con gestión",
        "css": "c2",
        "glifo": "◆",
        "color": "ámbar",
        "definicion": (
            "El lote presenta una o varias condiciones que sí tienen un trámite conocido "
            "ante una entidad determinada. Ninguna impide el proyecto: todas añaden tiempo, "
            "costo o documentación."),
        "condicion": (
            "Al menos una de estas, y ninguna de las que no admiten gestión: supera la "
            "Unidad Agrícola Familiar del municipio; quedó bajo agua en episodios de La "
            "Niña; el municipio tiene microzona de restitución de tierras; hay humedal "
            "dentro del lote; o entre el diez y el cincuenta por ciento de su superficie "
            "está en suelo de protección."),
    },
    {
        "clase": "No viable",
        "css": "c3",
        "glifo": "▲",
        "color": "rojo",
        "definicion": (
            "El lote presenta al menos una condición que ninguna gestión del proyecto "
            "resuelve dentro de un horizonte razonable: un derecho de un tercero que "
            "prevalece, o una figura territorial que el proyecto no puede ocupar."),
        "condicion": (
            "Al menos una de estas: la mitad del lote o más en suelo de protección; título "
            "minero vigente; o solape con área protegida del RUNAP, resguardo indígena, "
            "consejo comunitario o páramo delimitado, por encima del umbral de verificación "
            "de una hectárea o el dos por ciento del lote."),
    },
]

# --------------------------------------------------------------------------------
# Las cuatro verificaciones previas a la escritura que cuenta la columna homónima. No excluyen el
# lote ni cambian su clasificación: la compra la decide el título.
# --------------------------------------------------------------------------------
VERIFICACIONES_PREVIAS = [
    ("Edificación en pie por encima de 2.000 metros cuadrados",
     "Hay que negociarla, demolerla o rodearla, y suele venir con propiedad fragmentada."),
    ("Cobertura boscosa por encima del 10 por ciento del lote",
     "Exige permiso de aprovechamiento forestal ante la Corporación Autónoma Regional y su compensación."),
    ("Diferencia mayor al 10 por ciento entre el área que declara el catastro y la que mide la geometría del lote",
     "Obliga a sanear área y linderos antes de escriturar."),
    ("Destino económico sin declarar en el catastro",
     "Deja sin verificar el uso registrado del lote."),
]

# --------------------------------------------------------------------------------
# Criterios de filtrado de la lista. Cada criterio retira de la lista los lotes que no
# lo cumplen; ninguno modifica la clasificación del lote ni su ficha.
#
#   tipo   "umbral"  compara un campo numérico del lote contra el valor que escribe
#                    quien mira. dir "max" conserva los menores o iguales; dir "min"
#                    conserva los mayores o iguales. El lote sin dato nunca se retira.
#          "casilla" prueba una condición del lote, definida en PRUEBAS del JavaScript.
#          "rango"   el par de área, que lleva dos campos en una sola línea.
#   Ninguno se retira por marcar cero en estas grillas: un criterio se juzga por lo que
#   puede discriminar en cualquier archivo de grillas que se cargue después.
# --------------------------------------------------------------------------------
GRUPOS = [
    ("dim", "Dimensiones y forma del lote",
     "Definen el proyecto que se busca y si el campo solar cabe. El tamaño por sí solo no descarta ningún lote."),
    ("suelo", "Uso y cobertura del suelo",
     "Lo que ya ocupa el terreno y hay que retirar, comprar o rodear. Cada clase de cobertura se filtra por su cuenta, con el porcentaje que publica ESA WorldCover; este estudio retiró el agregado ponderado que antes las combinaba en una sola cifra."),
    ("terreno", "Terreno, relieve y amenaza geológica",
     "Lo que decide el movimiento de tierras y el tipo de estructura de soporte."),
    ("conexion", "Conexión eléctrica y acceso",
     "Lo que decide si la energía sale del lote y si la obra entra."),
    ("recurso", "Recurso solar y clima",
     "El rendimiento del sitio y su exposición a los dos fenómenos del Pacífico."),
    ("valor", "Valor del suelo y norma urbanística",
     "El avalúo catastral de referencia y la categoría que el POT municipal asigna al suelo."),
    ("juridico", "Condiciones jurídicas y de adquisición",
     "Lo que puede impedir que la compra se cierre aunque el terreno cumpla todos los criterios técnicos."),
    ("ambiental", "Ambiental, agua y riesgo",
     "Lo que la autoridad ambiental o el clima pueden convertir en un sobrecosto."),
]

FILTROS = [
    # ---- dimensiones y forma -----------------------------------------------------
    {"id": "f-ha", "grupo": "dim", "tipo": "rango", "campo": "area_ha",
     "etiqueta": "Área catastral del lote, entre", "unidad": "hectáreas", "paso": 1,
     "ayuda": "Retira los lotes cuya área queda fuera del rango. El tamaño por sí solo no descarta ningún lote: el rango lo define el proyecto que se quiere construir. La cifra es la que declara el catastro, no una medición propia."},
    {"id": "f-ancho", "grupo": "dim", "tipo": "umbral", "campo": "ancho_util_m", "dir": "min",
     "etiqueta": "Diámetro del mayor círculo inscrito mínimo", "unidad": "metros", "paso": 10,
     "ayuda": "Diámetro del mayor círculo que cabe dentro del lote. Un lote alargado puede tener área suficiente y aun así no admitir las filas de módulos ni la maniobra de los equipos de montaje."},
    {"id": "f-compacidad", "grupo": "dim", "tipo": "umbral", "campo": "compacidad", "dir": "min",
     "etiqueta": "Compacidad de la forma, como mínimo", "unidad": "de 0 a 1", "paso": 0.05,
     "ayuda": "El valor 1 corresponde a un círculo. Cuanto más baja, más alargado o más irregular es el lote, y más lindero hay que cercar por hectárea aprovechada."},
    {"id": "f-alargamiento", "grupo": "dim", "tipo": "umbral", "campo": "alargamiento", "dir": "max",
     "etiqueta": "Alargamiento del lote, como máximo", "unidad": "largo entre ancho", "paso": 0.5,
     "ayuda": "Relación entre el largo y el ancho del rectángulo envolvente. Un lote con relación de 25 a 1 no admite un campo solar aunque su área y su compacidad pasen."},
    {"id": "f-llenado", "grupo": "dim", "tipo": "umbral", "campo": "llenado_rect", "dir": "min",
     "etiqueta": "Llenado del rectángulo envolvente, como mínimo", "unidad": "fracción", "paso": 0.05,
     "ayuda": "Fracción del rectángulo envolvente que el lote ocupa de verdad. Distingue el lote rectangular limpio del polígono dentado que desperdicia el trazado."},
    {"id": "f-nucleo", "grupo": "dim", "tipo": "umbral", "campo": "area_nucleo_ha", "dir": "min",
     "etiqueta": "Área del núcleo del lote, como mínimo", "unidad": "hectáreas", "paso": 5,
     "ayuda": "Superficie que queda tras retirar del polígono los apéndices demasiado estrechos para implantar módulos."},
    {"id": "f-parche", "grupo": "dim", "tipo": "umbral", "campo": "parche_mayor_frac", "dir": "min",
     "etiqueta": "Terreno abierto concentrado en el mayor parche continuo, como mínimo", "unidad": "fracción", "paso": 0.05,
     "ayuda": "Terreno abierto son las clases de ESA WorldCover que no llevan arbolado ni edificación: matorral, pastizal, cultivo y suelo desnudo. Repartido en trozos separados obliga a multiplicar zanjas, caminos internos y cableado de corriente continua."},
    {"id": "f-reunir", "grupo": "dim", "tipo": "umbral", "campo": "lotes_para_150ha", "dir": "max",
     "etiqueta": "Lotes contiguos que hay que reunir para alcanzar el objetivo de superficie, como máximo", "unidad": "lotes", "paso": 1,
     "ayuda": "Mide la fragmentación de la tenencia alrededor del lote. Cada lote adicional es otra negociación, otro folio de registro y otro punto de fallo."},
    {"id": "f-pegadas", "grupo": "dim", "tipo": "umbral", "campo": "ha_pegadas", "dir": "min",
     "etiqueta": "Superficie de los lotes colindantes, como mínimo", "unidad": "hectáreas", "paso": 10,
     "ayuda": "Suma del área de los lotes que tocan el lindero, según el catastro. Marca el techo de una segunda fase si esos lotes llegaran a adquirirse; no dice quién es su propietario ni que estén en venta."},

    # ---- uso y cobertura del suelo ----------------------------------------------
    {"id": "f-bosque", "grupo": "suelo", "tipo": "umbral", "campo": "cob_bosque_pct", "dir": "max",
     "etiqueta": "Cobertura boscosa, como máximo", "unidad": "% del lote", "paso": 5,
     "ayuda": "El bosque no es aprovechable sin permiso de aprovechamiento forestal ante la Corporación Autónoma Regional y su compensación. Es la cobertura que más tiempo añade al cronograma."},
    {"id": "f-construido-m2", "grupo": "suelo", "tipo": "umbral", "campo": "area_construida_m2", "dir": "max",
     "etiqueta": "Superficie construida, como máximo", "unidad": "metros cuadrados", "paso": 500,
     "ayuda": "Edificaciones en pie dentro del lote. Hay que negociarlas, demolerlas o rodearlas, y suelen venir con propiedad fragmentada."},
    {"id": "f-construido-pct", "grupo": "suelo", "tipo": "umbral", "campo": "cob_construido_pct", "dir": "max",
     "etiqueta": "Cobertura construida, como máximo", "unidad": "% del lote", "paso": 1,
     "ayuda": "La misma señal en proporción del lote, medida sobre imagen satelital. Complementa a la cifra en metros cuadrados, que viene del catastro."},
    {"id": "f-cultivo", "grupo": "suelo", "tipo": "umbral", "campo": "cob_cultivo_pct", "dir": "max",
     "etiqueta": "Suelo en cultivo, como máximo", "unidad": "% del lote", "paso": 5,
     "ayuda": "El suelo en cultivo es apto para la planta, pero puede activar restricción de cambio de uso en el POT y suele elevar la expectativa de precio del vendedor."},
    {"id": "f-pastizal", "grupo": "suelo", "tipo": "umbral", "campo": "cob_pastizal_pct", "dir": "min",
     "etiqueta": "Pastizal, como mínimo", "unidad": "% del lote", "paso": 5,
     "ayuda": "Terreno abierto sin nada que retirar. Es la cobertura que menos obra de habilitación exige y la que abarata el movimiento de tierras."},
    {"id": "f-humedal-cob", "grupo": "suelo", "tipo": "umbral", "campo": "cob_humedal_pct", "dir": "max",
     "etiqueta": "Humedal herbáceo, como máximo", "unidad": "% del lote", "paso": 1,
     "ayuda": "Clase de humedal herbáceo de ESA WorldCover medida dentro del lote. Es distinta del cruce con la capa de humedales del inventario nacional, que se filtra aparte: esta se lee sobre la imagen y aquella sale del acto que declara la figura."},
    {"id": "f-agua-cob", "grupo": "suelo", "tipo": "umbral", "campo": "cob_agua_pct", "dir": "max",
     "etiqueta": "Agua permanente, como máximo", "unidad": "% del lote", "paso": 1,
     "ayuda": "Lámina de agua permanente dentro del lote. Arrastra ronda hídrica y reduce la superficie sobre la que se puede implantar."},
    {"id": "f-matorral", "grupo": "suelo", "tipo": "umbral", "campo": "cob_matorral_pct", "dir": "max",
     "etiqueta": "Matorral, como máximo", "unidad": "% del lote", "paso": 5,
     "ayuda": "Vegetación arbustiva abierta. No exige permiso de aprovechamiento forestal como el bosque, pero sí desmonte previo al movimiento de tierras."},
    {"id": "f-construcciones", "grupo": "suelo", "tipo": "casilla",
     "etiqueta": "Solo lotes sin construcciones registradas en el catastro",
     "ayuda": "Una vivienda o una edificación en pie obliga a negociar el desalojo o la demolición antes de construir."},
    {"id": "f-agrologica", "grupo": "suelo", "tipo": "casilla",
     "etiqueta": "Retirar los lotes en clase agrológica I a III",
     "ayuda": "Clases de mayor capacidad productiva según el IGAC. Pueden activar restricción al cambio de uso del suelo en el POT del municipio."},
    {"id": "f-frontera", "grupo": "suelo", "tipo": "casilla",
     "etiqueta": "Retirar los lotes en zona condicionada de la frontera agrícola",
     "ayuda": "La frontera agrícola de la UPRA marca zonas donde la conversión de uso está condicionada."},

    # ---- terreno -----------------------------------------------------------------
    {"id": "f-pendiente", "grupo": "terreno", "tipo": "umbral", "campo": "pendiente_media", "dir": "max",
     "etiqueta": "Pendiente media, como máximo", "unidad": "grados", "paso": 0.5,
     "ayuda": "Define el movimiento de tierras y el tipo de estructura de soporte."},
    {"id": "f-p90", "grupo": "terreno", "tipo": "umbral", "campo": "pendiente_p90", "dir": "max",
     "etiqueta": "Pendiente del percentil 90, como máximo", "unidad": "grados", "paso": 0.5,
     "ayuda": "Captura el sector empinado que la pendiente media esconde: nueve décimas partes del lote quedan por debajo de esta cifra."},
    {"id": "f-rugosidad", "grupo": "terreno", "tipo": "umbral", "campo": "rugosidad_m", "dir": "max",
     "etiqueta": "Rugosidad del relieve, como máximo", "unidad": "metros", "paso": 0.5,
     "ayuda": "Desviación de la elevación dentro del lote. Una pendiente media baja puede esconder terreno ondulado que la media no revela."},
    {"id": "f-desnivel", "grupo": "terreno", "tipo": "umbral", "campo": "desnivel_total_m", "dir": "max",
     "etiqueta": "Desnivel total dentro del lote, como máximo", "unidad": "metros", "paso": 5,
     "ayuda": "Altura que hay que salvar de un extremo al otro del lote. Es lo que fija el movimiento de tierra y la longitud de las mesas de seguidores."},
    {"id": "f-elevacion", "grupo": "terreno", "tipo": "umbral", "campo": "elevacion_media", "dir": "max",
     "etiqueta": "Elevación media del lote, como máximo", "unidad": "metros sobre el nivel del mar", "paso": 100,
     "ayuda": "En una grilla andina separa de inmediato por temperatura, acceso y proximidad a páramo. En terreno de sabana no discrimina, y esa es información igualmente."},
    {"id": "f-mov-masa", "grupo": "terreno", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con amenaza alta o muy alta por movimientos en masa",
     "ayuda": "Clasificación municipal del Servicio Geológico Colombiano. Obliga a estudio de amenaza y riesgo de detalle."},
    {"id": "f-sismica", "grupo": "terreno", "tipo": "casilla",
     "etiqueta": "Retirar los lotes en zona de amenaza sísmica alta",
     "ayuda": "Clasificación del Servicio Geológico Colombiano según la norma NSR-10. Encarece la estructura de soporte y la cimentación."},

    # ---- conexión y acceso -------------------------------------------------------
    {"id": "f-conexion", "grupo": "conexion", "tipo": "umbral", "campo": "conexion_km", "dir": "max",
     "etiqueta": "Distancia a la subestación de conexión, como máximo", "unidad": "kilómetros", "paso": 1,
     "ayuda": "Determina la longitud de la línea de conexión y sus servidumbres, que suelen decidir la viabilidad económica antes que el terreno."},
    {"id": "f-linea", "grupo": "conexion", "tipo": "umbral", "campo": "ctx_linea_km", "dir": "max",
     "etiqueta": "Distancia a línea de transmisión, como máximo", "unidad": "kilómetros", "paso": 1,
     "ayuda": "Alternativa de conexión por derivación de una línea existente en lugar de construir una línea nueva hasta la subestación."},
    {"id": "f-via", "grupo": "conexion", "tipo": "umbral", "campo": "dist_via_km", "dir": "max",
     "etiqueta": "Distancia a vía carrozable, como máximo", "unidad": "kilómetros", "paso": 0.5,
     "ayuda": "Condiciona el ingreso de equipos pesados durante la obra y el costo de la vía de acceso. Se mide desde el lindero del lote."},
    {"id": "f-via-centro", "grupo": "conexion", "tipo": "umbral", "campo": "dist_via_centro_km", "dir": "max",
     "etiqueta": "Distancia del centro del lote a la vía, como máximo", "unidad": "kilómetros", "paso": 0.5,
     "ayuda": "Un lote puede tocar la vía por una punta y tener el campo a dos kilómetros de ella."},
    {"id": "f-via-principal", "grupo": "conexion", "tipo": "umbral", "campo": "dist_via_principal_km", "dir": "max",
     "etiqueta": "Distancia a vía principal, como máximo", "unidad": "kilómetros", "paso": 1,
     "ayuda": "Transporte pesado del transformador de potencia y de la estructura de soporte."},
    {"id": "f-poblado", "grupo": "conexion", "tipo": "umbral", "campo": "ctx_poblado_km", "dir": "max",
     "etiqueta": "Distancia al centro poblado, como máximo", "unidad": "kilómetros", "paso": 1,
     "ayuda": "Mano de obra, logística de obra y vigilancia durante la construcción."},
    {"id": "f-caserio", "grupo": "conexion", "tipo": "umbral", "campo": "ctx_caserio_km", "dir": "min",
     "etiqueta": "Distancia al caserío más cercano, como mínimo", "unidad": "kilómetros", "paso": 0.5,
     "ayuda": "Al revés que el anterior: separación mínima frente al vecino que puede oponerse al campo solar."},
    {"id": "f-kv", "grupo": "conexion", "tipo": "casilla",
     "etiqueta": "Solo lotes con subestación de conexión de 110 kV o más",
     "ayuda": "Una subestación de tensión insuficiente no puede evacuar la potencia de una planta de escala utility."},

    # ---- recurso solar y clima ---------------------------------------------------
    {"id": "f-pvout", "grupo": "recurso", "tipo": "umbral", "campo": "ctx_pvout", "dir": "min",
     "etiqueta": "Producción fotovoltaica específica anual, como mínimo", "unidad": "kilovatios hora por kilovatio pico al año", "paso": 10,
     "ayuda": "Energía que produciría al año una planta de referencia por cada kilovatio pico instalado. Multiplicada por la potencia instalada da la energía anual estimada del proyecto."},
    {"id": "f-ghi", "grupo": "recurso", "tipo": "umbral", "campo": "ctx_ghi", "dir": "min",
     "etiqueta": "Irradiación global horizontal anual, como mínimo", "unidad": "kilovatios hora por metro cuadrado al año", "paso": 10,
     "ayuda": "Toda la energía solar que llega a una superficie horizontal. Es la magnitud con la que se compara un sitio contra cualquier otra región del mundo."},
    {"id": "f-dni", "grupo": "recurso", "tipo": "umbral", "campo": "ctx_dni", "dir": "min",
     "etiqueta": "Irradiación directa normal anual, como mínimo", "unidad": "kilovatios hora por metro cuadrado al año", "paso": 10,
     "ayuda": "La que llega en línea recta desde el disco solar. Decide si el seguimiento en un eje se paga solo."},
    {"id": "f-gti", "grupo": "recurso", "tipo": "umbral", "campo": "ctx_gti", "dir": "min",
     "etiqueta": "Irradiación anual sobre plano inclinado óptimo, como mínimo", "unidad": "kilovatios hora por metro cuadrado al año", "paso": 10,
     "ayuda": "Es la irradiación que de verdad recibe el módulo montado en estructura fija bien orientada."},
    {"id": "f-indice", "grupo": "recurso", "tipo": "umbral", "campo": "indice_lote", "dir": "min",
     "etiqueta": "Índice de aptitud del lote, como mínimo", "unidad": "sobre 100", "paso": 5,
     "ayuda": "Promedio ponderado de los siete criterios técnicos, en escala de 0 a 100. Permite fijar un mínimo propio de calidad técnica. El índice no clasifica ningún lote y no ordena la lista: la clase sale de las condiciones comprobadas sobre el polígono y el orden lo pone el área catastral del lote."},
    {"id": "f-sequia", "grupo": "recurso", "tipo": "umbral", "campo": "_sequia_anios", "dir": "min",
     "etiqueta": "Periodo de retorno de la sequía meteorológica, como mínimo", "unidad": "años", "paso": 1,
     "ayuda": "Cada cuánto vuelve el año sin agua para lavar los módulos. La cifra es el límite inferior de la banda que publica el IDEAM."},
    {"id": "f-nina", "grupo": "recurso", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con excedente de lluvia en una Niña típica",
     "ayuda": "Un excedente sostenido sobre lo normal es el escenario que anega los caminos internos y retrasa la obra civil."},
    {"id": "f-nino", "grupo": "recurso", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con déficit de lluvia en un Niño típico",
     "ayuda": "Un déficit del 40 al 80 por ciento en temporada lluviosa pone presión sobre el agua de lavado de módulos y sobre la obra."},

    # ---- valor del suelo y norma urbanística -------------------------------------
    {"id": "f-valor", "grupo": "valor", "tipo": "umbral", "campo": "_valor_millones", "dir": "max",
     "etiqueta": "Valor catastral de referencia del lote, como máximo", "unidad": "millones de pesos", "paso": 10,
     "ayuda": "Avalúo catastral del IGAC ponderado por área, no precio de mercado. Sirve para descartar lotes fuera del presupuesto; en municipios con catastro desactualizado queda muy por debajo del valor comercial."},
    {"id": "f-valor-ha", "grupo": "valor", "tipo": "umbral", "campo": "_valor_millones_ha", "dir": "max",
     "etiqueta": "Valor catastral de referencia por hectárea, como máximo", "unidad": "millones de pesos por hectárea", "paso": 1,
     "ayuda": "Precio unitario del suelo, comparable entre lotes de tamaño distinto."},
    {"id": "f-valor-conf", "grupo": "valor", "tipo": "casilla",
     "etiqueta": "Retirar los lotes cuyo valor de referencia tiene confianza baja o sin dato",
     "ayuda": "La confianza baja cuando el avalúo se apoya en muy poca superficie del lote con zona geoeconómica publicada."},
    {"id": "f-pot", "grupo": "valor", "tipo": "casilla",
     "etiqueta": "Retirar los lotes que el POT clasifica como suelo de protección",
     "ayuda": "El suelo de protección impide la planta en suelo mientras el certificado de uso del suelo de la alcaldía no acredite lo contrario."},
    {"id": "f-pot-proteccion", "grupo": "valor", "tipo": "umbral", "campo": "pot_proteccion_pct", "dir": "max",
     "etiqueta": "Superficie del lote en categorías de protección del POT, como máximo", "unidad": "% del lote", "paso": 5,
     "ayuda": "Gradúa el criterio anterior: una franja de protección en un borde no equivale al lote entero protegido."},
    {"id": "f-pot-rural", "grupo": "valor", "tipo": "casilla",
     "etiqueta": "Retirar los lotes que el POT no clasifica como suelo rural",
     "ayuda": "En suelo urbano o de expansión la planta en suelo no cabe y el valor del terreno se dispara."},
    {"id": "f-pot-carto", "grupo": "valor", "tipo": "casilla",
     "etiqueta": "Retirar los lotes sin cartografía del POT publicada",
     "ayuda": "Sin zonificación publicada por el IGAC el uso del suelo no se puede verificar en gabinete y hay que pedirlo a la alcaldía."},

    # ---- condiciones jurídicas y de adquisición ----------------------------------
    {"id": "f-limpios", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Solo lotes sin ninguna verificación pendiente",
     "ayuda": "Número de circunstancias observables en datos abiertos que obligan a un permiso, un saneamiento documental o una negociación adicional antes de que el lote pueda comprarse y construirse. Se cuentan cuatro: edificación en pie por encima de 2.000 metros cuadrados; cobertura boscosa por encima del 10 por ciento del lote; diferencia mayor al 10 por ciento entre el área que declara el catastro y la que mide la geometría; y destino económico sin declarar en el catastro. No excluyen el lote ni cambian su clasificación: la compra la decide el título."},
    {"id": "f-uaf", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Solo lotes que no superan la Unidad Agrícola Familiar del municipio",
     "ayuda": "La Unidad Agrícola Familiar es el área máxima que la ley permite adjudicar a una familia campesina. Un lote que la supera puede tener origen en baldío adjudicado, lo que haría nula la compraventa; se confirma con el certificado de tradición y libertad."},
    {"id": "f-veces-uaf", "grupo": "juridico", "tipo": "umbral", "campo": "veces_uaf", "dir": "max",
     "etiqueta": "Relación con la Unidad Agrícola Familiar, como máximo", "unidad": "veces el tope", "paso": 0.5,
     "ayuda": "Gradúa el criterio anterior: permite tolerar una vez y media el tope en lugar de exigir el tope exacto."},
    {"id": "f-restitucion", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Retirar los lotes en municipio con microzona de restitución de tierras vigente",
     "ayuda": "Un lote dentro de microzona activa queda en suspenso hasta que el proceso de restitución concluya."},
    {"id": "f-restitucion-n", "grupo": "juridico", "tipo": "umbral", "campo": "_restitucion_n", "dir": "max",
     "etiqueta": "Solicitudes de restitución en el municipio, como máximo", "unidad": "solicitudes", "paso": 50,
     "ayuda": "Presión de restitución en el municipio. El municipio sin dato no se retira, porque la ausencia de dato no es una cifra baja."},
    {"id": "f-mineria", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con título minero vigente",
     "ayuda": "El título minero prevalece sobre el uso del suelo. Es el criterio que primero descarta en las regiones mineras del país."},
    {"id": "f-solicitud-minera", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con solicitud minera vigente",
     "ayuda": "Una solicitud en trámite puede convertirse en título sobre el mismo polígono."},
    {"id": "f-hidrocarburos", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Retirar los lotes dentro de un bloque de hidrocarburos",
     "ayuda": "Implica servidumbres y actividad del operador petrolero sobre el mismo suelo."},
    {"id": "f-desajuste", "grupo": "juridico", "tipo": "umbral", "campo": "desajuste_catastro_pct", "dir": "max",
     "etiqueta": "Diferencia entre el área del catastro y la de la geometría, como máximo", "unidad": "% del área", "paso": 5,
     "ayuda": "Un desajuste alto obliga a sanear área y linderos antes de escriturar."},
    {"id": "f-destino", "grupo": "juridico", "tipo": "casilla",
     "etiqueta": "Retirar los lotes sin destino económico declarado en el catastro",
     "ayuda": "Sin destino declarado el registro catastral está incompleto y el avalúo no es defendible."},

    # ---- ambiental, agua y riesgo ------------------------------------------------
    {"id": "f-inund", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Solo lotes sin inundación registrada en episodios de La Niña",
     "ayuda": "Manchas de inundación observadas por el IDEAM en seis episodios entre 1988 y 2022. Condiciona cimentación, acceso, altura de estructuras y prima de seguro."},
    {"id": "f-zip", "grupo": "ambiental", "tipo": "umbral", "campo": "pct_zip", "dir": "max",
     "etiqueta": "Superficie del lote en zona inundable periódica, como máximo", "unidad": "% del lote", "paso": 5,
     "ayuda": "Área que se inunda de forma recurrente en la temporada de lluvias, aun sin La Niña. No sirve para módulos ni para la subestación."},
    {"id": "f-agua", "grupo": "ambiental", "tipo": "umbral", "campo": "pct_cuerpo_agua", "dir": "max",
     "etiqueta": "Superficie del lote ocupada por cuerpos de agua, como máximo", "unidad": "% del lote", "paso": 1,
     "ayuda": "Ciénaga o laguna dentro del lindero. Un uno por ciento en un borde no equivale a una quinta parte del lote bajo lámina de agua."},
    {"id": "f-drenajes", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con drenaje cartografiado en su envolvente",
     "ayuda": "Cada cauce lleva una ronda hídrica de protección legal que no admite módulos ni subestación."},
    {"id": "f-humedal", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con humedal inventariado en su envolvente",
     "ayuda": "Ecosistema protegido dentro del polígono: obliga a sustracción o a rediseñar el campo."},
    {"id": "f-humedal-natural", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con humedal natural, no transformado",
     "ayuda": "Versión estricta del criterio anterior: el humedal no transformado es el que no se negocia."},
    {"id": "f-runap", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con solape en área protegida del RUNAP",
     "ayuda": "Área inscrita en el Registro Único Nacional de Áreas Protegidas: uso incompatible con la planta."},
    {"id": "f-resguardo", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con solape en resguardo indígena",
     "ayuda": "Territorio colectivo, inalienable e imprescriptible. En La Guajira, el Cauca o la Sierra Nevada es el criterio dominante."},
    {"id": "f-consejo", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con solape en consejo comunitario",
     "ayuda": "Territorio colectivo de comunidades negras, con la misma consecuencia jurídica."},
    {"id": "f-paramo", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con solape en páramo delimitado",
     "ayuda": "Ecosistema de páramo con prohibición expresa. Cualquier grilla andina lo activa de inmediato."},
    {"id": "f-incendios", "grupo": "ambiental", "tipo": "umbral", "campo": "ent_incendios_5km", "dir": "max",
     "etiqueta": "Incendios registrados en cinco kilómetros, como máximo", "unidad": "incendios", "paso": 1,
     "ayuda": "Historial de quema en el entorno del lote, reportado por el IDEAM."},
    {"id": "f-incendios-ha", "grupo": "ambiental", "tipo": "umbral", "campo": "ent_incendios_ha_5km", "dir": "max",
     "etiqueta": "Superficie quemada en cinco kilómetros, como máximo", "unidad": "hectáreas", "paso": 100,
     "ayuda": "No es lo mismo un conato que un incendio de dos mil quinientas hectáreas junto al lote a la hora de contratar el seguro."},
    {"id": "f-incendio-anios", "grupo": "ambiental", "tipo": "umbral", "campo": "_incendio_anios", "dir": "min",
     "etiqueta": "Antigüedad del último incendio registrado, como mínimo", "unidad": "años", "paso": 1,
     "ayuda": "La recurrencia reciente pesa más que la histórica. El lote sin incendio registrado no se retira."},
    {"id": "f-pomca", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes en cuenca con plan de ordenación y manejo sin aprobar",
     "ayuda": "La zonificación ambiental de un POMCA aprobado es vinculante para el uso del suelo; la de un POMCA en formulación puede cambiar durante el desarrollo del proyecto."},
    {"id": "f-capas", "grupo": "ambiental", "tipo": "casilla",
     "etiqueta": "Retirar los lotes con alguna capa ambiental sin respuesta",
     "ayuda": "Alguna capa del servicio no respondió en la última consulta y la ficha de ese lote está incompleta."},
]

#: El criterio o los criterios de cada grupo que se muestran desplegados al abrir la banda:
#: uno por grupo como mínimo, para que ningún grupo aparezca vacío. Los demás quedan dentro
#: del grupo, que se abre con un clic.
DESTACADOS = {"f-ha", "f-ancho", "f-bosque", "f-limpios", "f-uaf",
              "f-pendiente", "f-conexion", "f-pvout", "f-pot", "f-inund"}


def _control(f: dict) -> str:
    """HTML de un criterio. El identificador va literal para poder rastrearlo."""
    ay = f'<span class="cri-ayuda">{_e(f["ayuda"])}</span>'
    if f["tipo"] == "rango":
        return (f'<div class="cri-linea"><label for="{f["id"]}-min">{_e(f["etiqueta"])} '
                f'<span class="campo" id="c-ha-min"><input type="number" id="f-ha-min" min="0" step="{f["paso"]}" '
                f'aria-label="área mínima en hectáreas"><span class="uni">ha</span></span> y '
                f'<span class="campo" id="c-ha-max"><input type="number" id="f-ha-max" min="0" step="{f["paso"]}" '
                f'placeholder="sin tope" aria-label="área máxima en hectáreas"><span class="uni">ha</span></span> '
                f'{_e(f["unidad"])}</label>{ay}</div>')
    if f["tipo"] == "umbral":
        return (f'<div class="cri-linea"><label for="{f["id"]}">{_e(f["etiqueta"])} '
                f'<span class="campo" id="c-{f["id"][2:]}"><input type="number" id="{f["id"]}" step="{f["paso"]}" '
                f'placeholder="sin límite"><span class="uni">{_e(f["unidad"])}</span></span></label>{ay}</div>')
    return (f'<div class="cri-linea"><label for="{f["id"]}">'
            f'<input type="checkbox" id="{f["id"]}"> {_e(f["etiqueta"])}</label>{ay}</div>')


def criterios_html() -> str:
    """Banda completa de criterios, agrupada por naturaleza y con el rótulo de cada grupo."""
    out = []
    for clave, rotulo, descripcion in GRUPOS:
        fs = [f for f in FILTROS if f["grupo"] == clave]
        if not fs:
            continue
        destacados = [f for f in fs if f["id"] in DESTACADOS]
        resto = [f for f in fs if f["id"] not in DESTACADOS]
        cuerpo = "".join(_control(f) for f in destacados)
        extra = "".join(_control(f) for f in resto)
        det = (f'<details class="cri-mas"><summary>Los otros {len(resto)} criterios de '
               f'{_e(rotulo.lower())}</summary><div class="cri-lineas">{extra}</div></details>'
               if resto else "")
        out.append(f'<section class="cri-grupo" data-g="{clave}">'
                   f'<h3>{_e(rotulo)}</h3><p class="cri-desc">{_e(descripcion)}</p>'
                   f'<div class="cri-lineas">{cuerpo}</div>{det}</section>')
    return "".join(out)


# --------------------------------------------------------------------------------
# Cómo se construye la ficha: el orden de consulta y la fuente de cada dato. Se nombra
# la entidad, nunca el módulo ni el fichero: quien lee el reporte no trabaja con ellos.
# Lo que no viene de una entidad sino de un cálculo de este estudio va marcado, porque
# es la distinción que permite defender una cifra ante un tercero.
# --------------------------------------------------------------------------------
PROCESO = [
    # (paso, qué aporta, fuente, corte, formato, cómo se cruza, cálculo propio)
    ("Selección de grillas",
     "El insumo. Celdas de cinco por cinco kilómetros; se acepta cualquier número, una incluida.",
     "Reporte de grillas de este mismo estudio", "la de la corrida que la produjo",
     "GeoJSON o GPKG de polígonos", "es el punto de partida", False),
    ("Catastro del lote",
     "Polígono, número predial, área registrada y destino económico declarado.",
     "IGAC, catastro público. Alcaldías con gestor catastral propio",
     "corte de 30 de junio de 2026", "servicio de mapas en línea",
     "por intersección: se piden los lotes que caen dentro de la celda", False),
    ("Geometría",
     "Área, compacidad, alargamiento y diámetro del mayor círculo inscrito.",
     "Cálculo sobre el polígono del IGAC", "la del catastro",
     "operación geométrica", "sobre el propio polígono, sin cruzar nada", True),
    ("Cobertura del suelo",
     "Qué porcentaje del lote es pastizal, cultivo, bosque, construido, agua o humedal. "
     "Once clases, tal como las publica la fuente, sin agregar ni ponderar.",
     "ESA WorldCover, programa Copernicus", "versión 2021",
     "ráster de 10 metros por píxel, en teselas de 3 por 3 grados",
     "se cuentan los píxeles de cada clase dentro del polígono", False),
    ("Terreno",
     "Pendiente media, rugosidad y elevación.",
     "Copernicus DEM GLO-30", "GLO-30, versión vigente",
     "ráster de 30 metros por píxel",
     "se promedian las celdas que caen dentro del lote", False),
    ("Recurso solar",
     "Producción específica anual, irradiación global, directa y difusa, y ángulo óptimo.",
     "Global Solar Atlas, Banco Mundial y Solargis", "versión 2.0 de la capa",
     "ráster global", "se toma el valor en el punto central del lote", False),
    ("Conexión eléctrica",
     "Subestación más cercana, tensión, distancia y capacidad disponible en esa barra.",
     "UPME, Circular 054 de 2026, y capa de subestaciones del sistema",
     "circular del 10 de junio de 2026, con corte de información al 5 de mayo",
     "anexo en PDF y capa de puntos",
     "por distancia en línea recta al centro del lote, y por nombre de barra", False),
    ("Figuras del territorio",
     "Áreas protegidas, resguardos, consejos comunitarios, páramos, humedales, cuencas, "
     "frontera agrícola, títulos mineros, bloques de hidrocarburos, amenazas e inundaciones.",
     "Parques Nacionales, ANT, ANM, ANH, SGC, IDEAM, MADS y UPRA",
     "cada capa con su corte, declarado en la tabla de fuentes",
     "servicios de mapas en línea, uno por entidad",
     "por solape del polígono, midiendo las hectáreas que toca cada figura", False),
    ("Norma urbanística",
     "Categoría del suelo rural del plan de ordenamiento y qué parte del lote queda en "
     "categorías de protección. Si el municipio no la ha publicado, la ficha lo dice.",
     "IGAC, datos nacionales de ordenamiento territorial",
     "zonificación publicada para 761 de los 1.103 municipios",
     "servicio de mapas, con los dominios del modelo LADM-COL",
     "por solape, y se reparte la superficie del lote entre categorías", False),
    ("Matrícula inmobiliaria",
     "El número de folio del lote. Un lote sin consultar queda pendiente, no como sin dato.",
     "Portal de impuesto predial del municipio, cuando existe. Si no, índice de "
     "propietarios de la Superintendencia de Notariado y Registro",
     "consulta en vivo, con su fecha guardada",
     "consulta web por número predial",
     "por el número predial de treinta dígitos, no por posición", False),
    ("Certificado de tradición",
     "Titular, gravámenes, servidumbres y origen del dominio, con el trámite que exige cada uno.",
     "Oficina de Registro de Instrumentos Públicos", "la fecha de expedición del folio",
     "documento en PDF que hay que comprar",
     "por la matrícula, que se lee del propio documento", False),
    ("Clasificación",
     "El lote recibe una de las tres clases según las condiciones encontradas, no según "
     "ninguna nota. El índice de aptitud se calcula aparte y no interviene.",
     "Catálogo de condiciones descrito arriba", "el de la corrida",
     "regla sobre los datos anteriores", "no cruza: aplica el catálogo a lo ya medido", False),
]


def proceso_html() -> str:
    """Cada paso con lo que aporta, su fuente, su corte, su formato y cómo se cruza."""
    filas = []
    for n, (paso, aporta, fuente, corte, formato, cruce, propio) in enumerate(PROCESO, 1):
        marca = ('<span class="proc-calc">cálculo de este estudio</span>' if propio else "")
        filas.append(
            f'<div class="proc-paso"><div class="proc-n">{n}</div><div>'
            f'<p class="proc-t">{paso}{marca}</p>'
            f'<p class="proc-d">{aporta}</p>'
            f'<div class="proc-meta">'
            f'<span><b>Fuente</b> {fuente}</span>'
            f'<span><b>Corte</b> {corte}</span>'
            f'<span><b>Formato</b> {formato}</span>'
            f'<span><b>Cruce</b> {cruce}</span>'
            f'</div></div></div>')
    return "".join(filas)


def clases_html() -> str:
    """Bloque de apertura del visor: qué hace idóneo, viable con gestión o no viable a un lote."""
    tarjetas = "".join(
        f'<article class="clase-tarjeta {c["css"]}">'
        f'<h3><span class="gl">{c["glifo"]}</span>{_e(c["clase"])}'
        f'<span class="clase-color">{_e(c["color"])} en el mapa</span></h3>'
        f'<p class="clase-def">{_e(c["definicion"])}</p>'
        f'<p class="clase-cond"><b>Condición que lo pone en esta clase.</b> {_e(c["condicion"])}</p>'
        f'</article>' for c in CLASES_DEF)
    return tarjetas

# --------------------------------------------------------------------------------
# Glosario al pie del visor. Cada término se usa aquí con este significado y con
# ningún otro.
# --------------------------------------------------------------------------------
GLOSARIO = [
    ("Lote", "Unidad de terreno con código predial en el catastro. Es el objeto que se compra o se arrienda y la unidad de trabajo de este visor."),
    ("Grilla", "Cuadro del territorio evaluado en la fase anterior del estudio, del cual se extraen los lotes que caen dentro. El visor lee el archivo de grillas que se le cargue, sea cual sea su tamaño y su número."),
    ("Clasificación del lote", "Resultado en tres niveles: Idóneo, Viable con gestión y No viable. Sale de las condiciones comprobadas sobre el polígono del lote y no de ninguna nota ni promedio. Describe el resultado del análisis; no retira ningún lote de la lista."),
    ("Condición del lote", "Circunstancia comprobada sobre el polígono del lote que fija su clase. Cada una se nombra, se dice qué se midió en ese lote, qué trámite exige, ante qué entidad se surte y de qué fuente salió el dato. Las que ninguna gestión resuelve dejan el lote No viable; las que tienen trámite conocido lo dejan Viable con gestión."),
    ("Verificaciones previas a la escritura", "Número de circunstancias observables en datos abiertos que añaden un permiso, un saneamiento documental o una negociación antes de poder comprar y construir. No cambian la clasificación del lote."),
    ("Cobertura del suelo", "Porcentaje del lote que ocupa cada clase de la clasificación de ESA WorldCover 2021, a 10 metros de resolución, recortada con el polígono del lote. Son las clases que publica la capa (pastizal, bosque, cultivo, matorral, suelo construido, suelo desnudo, humedal herbáceo, agua permanente, manglar, nieve y musgo) y las cifras van tal como salen de ella, sin ponderar y sin combinarse en ningún agregado. Describen lo que hoy ocupa el terreno; no dicen qué superficie es implantable, cosa que decide el diseño de la planta y el permiso ambiental."),
    ("Área catastral del lote", "Superficie del polígono que el Instituto Geográfico Agustín Codazzi registra para el lote. Es la cifra que ordena la lista y la base de la potencia instalable indicativa."),
    ("Potencia instalable indicativa", "Área catastral del lote dividida entre 1,5 hectáreas por megavatio pico. Esa huella es una referencia de ingeniería para planta en suelo con seguidor de un eje, no un valor que publique ninguna entidad colombiana ni un valor medido en plantas del país. Sirve para comparar lotes en la misma unidad con la que se habla del negocio; la potencia real la fija el diseño."),
    ("Diámetro del mayor círculo inscrito", "Diámetro del mayor círculo que cabe dentro del lote. Mide si la forma admite filas de módulos y la maniobra de los equipos de montaje, cosa que el área por sí sola no revela."),
    ("Índice de aptitud", "Promedio ponderado de las notas de siete criterios técnicos, en escala de 0 a 100. Los umbrales de cada criterio son percentiles medidos en los lotes donde están las plantas fotovoltaicas ya construidas del registro de XM. Es un descriptor que vive dentro de la ficha: no clasifica el lote ni determina el orden de la lista."),
    ("Criterio del índice por debajo de su límite", "Criterio cuyo valor medido en el lote queda peor que el límite de referencia de su perfil. Recibe nota cero dentro del índice. No es un obstáculo administrativo ni cambia la clase del lote: describe una condición del sitio que encarece o condiciona la ingeniería."),
    ("Perfil", "Tipo de proyecto para el que se evalúa el lote: escala utility, de 10 MW en adelante, o generación distribuida, de 1 a 2 MWp. Cada perfil tiene sus propios umbrales, pesos y tamaño de proyecto."),
    ("Subestación de conexión", "Instalación de la red eléctrica donde el proyecto entregaría su energía. Su distancia al lote determina la longitud de la línea de conexión y sus servidumbres."),
    ("Capacidad de conexión disponible", "Cupo de transporte que la subestación puede aceptar. Si no hay cupo, no hay proyecto por bueno que sea el terreno. Se solicita a la UPME."),
    ("Producción fotovoltaica específica", "Energía anual que produciría una planta de referencia por cada kilovatio pico instalado, expresada en kilovatios hora por kilovatio pico. Multiplicada por la potencia instalada da la energía anual estimada del proyecto."),
    ("POT", "Plan de Ordenamiento Territorial del municipio. Define qué se puede construir en cada suelo. El suelo de protección impide la planta mientras el certificado de uso del suelo de la alcaldía no acredite lo contrario."),
    ("Unidad Agrícola Familiar (UAF)", "Área máxima que la ley permite adjudicar a una familia campesina en cada municipio. Un lote que la supera puede tener origen en baldío adjudicado, caso en el cual la compraventa sería nula."),
    ("Matrícula inmobiliaria", "Número que identifica el folio del lote en el registro. Es distinta del número predial del catastro y es la que se necesita para comprar el certificado. El catastro no la publica: se obtiene consultando el índice de propietarios de la Superintendencia de Notariado y Registro con el número predial, o presentando un derecho de petición ante la misma entidad, que no tiene costo y se responde en diez días hábiles."),
    ("Certificado de tradición y libertad", "Documento del registro que muestra quién es el propietario, la cadena completa de actos sobre el lote y si el origen es baldío adjudicado. Es el único documento que cierra la verificación jurídica."),
    ("Valor catastral de referencia", "Avalúo del IGAC ponderado por área, no precio de mercado. En municipios con catastro desactualizado queda muy por debajo del valor comercial."),
    ("Sin dato", "El dato no está disponible en la fuente consultada, o la consulta no obtuvo respuesta. No significa que el valor sea cero."),
]

ENTIDADES = [
    ("UPME", "Unidad de Planeación Minero Energética: asigna la capacidad de conexión."),
    ("IGAC", "Instituto Geográfico Agustín Codazzi: catastro, avalúos y cartografía."),
    ("SNR", "Superintendencia de Notariado y Registro: certificado de tradición y libertad."),
    ("ANT", "Agencia Nacional de Tierras: baldíos y Unidad Agrícola Familiar."),
    ("ANM", "Agencia Nacional de Minería: títulos y solicitudes mineras."),
    ("ANH", "Agencia Nacional de Hidrocarburos: bloques petroleros."),
    ("CAR", "Corporación Autónoma Regional: permisos ambientales, aprovechamiento forestal y rondas hídricas."),
    ("URT", "Unidad de Restitución de Tierras: microzonas y certificaciones de restitución."),
    ("IDEAM", "Instituto de Hidrología, Meteorología y Estudios Ambientales: inundaciones, clima e incendios."),
    ("SGC", "Servicio Geológico Colombiano: amenaza sísmica y por movimientos en masa."),
    ("UPRA", "Unidad de Planificación Rural Agropecuaria: frontera agrícola."),
    ("XM", "Operador del mercado eléctrico: registro de plantas de generación con el que se calibran los umbrales."),
]


def glosario_html() -> str:
    """Glosario y entidades citadas, a dos columnas, al pie del visor."""
    terminos = "".join(
        f'<div class="gl-item"><b>{_e(t)}.</b> {_e(d)}</div>' for t, d in GLOSARIO)
    entidades = "".join(
        f'<div class="gl-item"><b>{_e(s)}.</b> {_e(d)}</div>' for s, d in ENTIDADES)
    condiciones = "".join(
        f'<div class="gl-item"><b>{_e(t)}.</b> {_e(d)}</div>' for t, d in VERIFICACIONES_PREVIAS)
    return (f'<p class="fuentes-sub">Definiciones de los términos que aparecen en la lista y '
            f'en la ficha. Cada uno se usa aquí con este significado y con ningún otro.</p>'
            f'<div class="glosario">{terminos}</div>'
            f'<h3 class="gl-h3">Las cuatro verificaciones previas a la escritura que se cuentan</h3>'
            f'<div class="glosario">{condiciones}</div>'
            f'<h3 class="gl-h3">Entidades citadas</h3>'
            f'<div class="glosario">{entidades}</div>')


#: Estilos de la sección del certificado de tradición y libertad. Se escriben UNA vez y
#: se insertan en las dos hojas, la del visor y la del documento imprimible, porque la
#: sección se pinta en las dos con la misma función. Antes el imprimible no traía ni una
#: de estas reglas, así que la ficha en PDF sacaba la sección sin formato. Solo se usan
#: variables de color que existan en las dos hojas.
_CERT_CSS = r"""
/* La Parte 1 del análisis es EXTRACCIÓN y se presenta como extracción: rejilla de
   etiqueta y valor para la identificación, y tabla para las anotaciones, las áreas y las
   matrículas segregadas. Doce filas se leen de un vistazo; doce párrafos, no. Antes cada
   campo se volcaba como párrafo, uno detrás de otro, y la sección medía 2.300 px: un
   documento de texto pegado dentro de la ficha en vez de una ficha. La Parte 2, la
   lectura para el proyecto, es lo único que va en prosa, y a una línea por asunto. */
.cert{font-size:11.5px; line-height:1.45; color:var(--ink-2)}
.cert .c-rot{font-size:9px; letter-spacing:.09em; text-transform:uppercase; font-weight:700;
  color:var(--ink-3); margin:11px 0 4px; padding-top:5px; border-top:1px solid var(--line)}
.cert .c-rot em{font-style:normal; font-weight:400; letter-spacing:.02em; text-transform:none}
.cert .c-primero{margin-top:0; border-top:0; padding-top:0}
.cert .datos{grid-template-columns:repeat(4,1fr); gap:6px 12px; margin-top:0}
.cert .dato{padding-top:4px}
.cert .dk{font-size:8.5px}
.cert .dv{font-size:12px; line-height:1.35; overflow-wrap:anywhere}
.cert .d2{grid-column:span 2}
.cert .c-res{margin:8px 0 0; color:var(--ink); font-size:12px}

/* Tablas de la extracción. Ancho fijo: una celda larga ensancha su columna y descuadra
   la tabla entera, y estas tienen que caber en el ancho de la ficha. Las dos columnas
   estrechas, el número y la fecha, se miden en em y no en porcentaje: en la hoja A4 la
   tabla es más angosta que en el visor, y con porcentaje la fecha se quedaba sin sitio
   y se montaba encima del acto. */
.cert table{width:100%; border-collapse:collapse; table-layout:fixed; font-size:10px; line-height:1.3}
.cert th{text-align:left; font-size:8.5px; letter-spacing:.05em; text-transform:uppercase;
  color:var(--ink-3); font-weight:700; padding:2px 5px 3px; border-bottom:1px solid var(--borde-control)}
.cert td{padding:2px 5px 3px; border-bottom:1px solid var(--line); vertical-align:top; overflow-wrap:anywhere}
.cert td.c-n, .cert td.c-f{font-variant-numeric:tabular-nums; white-space:nowrap}
.cert td.c-n{text-align:right; color:var(--ink); font-weight:700}
.cert .c-acto{color:var(--ink); font-weight:600}
.cert .c-doc{display:block; color:var(--ink-3); font-size:8.5px; line-height:1.2}
.cert .c-per{display:block}
.cert .c-vac{color:var(--ink-3)}
.cert tr.c-can td{background:var(--surface-2); color:var(--ink-3)}
.cert tr.c-can .c-acto{text-decoration:line-through}
.cert .c-bad{display:inline-block; margin-left:5px; font-size:8px; letter-spacing:.05em;
  text-transform:uppercase; font-weight:700; border-radius:3px; padding:0 4px;
  background:var(--surface-2); color:var(--ink-3); white-space:nowrap}
.cert .c-bad-can{background:var(--alerta-fondo); color:var(--alerta)}
.cert .c-mx,.cert .c-mi{display:inline-block; margin-left:4px; min-width:12px; text-align:center;
  font-size:8.5px; font-weight:700; border-radius:2px; padding:0 2px}
.cert .c-mx{background:var(--surface-2); color:var(--ink-2)}
.cert .c-mi{background:var(--alerta-fondo); color:var(--alerta)}
.cert .c-leg{margin:3px 0 0; font-size:9.5px; color:var(--ink-3); line-height:1.4}

/* Dos columnas para las tablas cortas y para las listas de acción. */
.cert .c-2col{display:grid; grid-template-columns:1.5fr 1fr; gap:0 18px; align-items:start}
.cert .c-2col.c-igual{grid-template-columns:1fr 1fr}

/* Parte 2: una línea por asunto, con la etiqueta alineada en su propia columna. */
.cert .c-lineas{display:grid; grid-template-columns:108px 1fr; gap:4px 12px; margin-top:2px}
.cert .c-li{display:contents}
.cert .c-lk{font-size:8.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3);
  font-weight:700; padding-top:2px}
.cert .c-lv b{color:var(--ink)}
.cert .c-ojo{color:var(--aviso); font-weight:700}
.cert .c-mal{color:var(--alerta); font-weight:700}
.cert .c-anot{font-size:9.5px; color:var(--ink-3); white-space:nowrap}
.cert .c-nover{font-size:9.5px; color:var(--aviso)}

/* Un punto por asunto, nunca un párrafo con puntos y comas dentro. */
.cert ul.c-lista{margin:0; padding:0; list-style:none}
.cert ul.c-lista li{padding:1px 0 2px 10px; position:relative; line-height:1.38}
.cert ul.c-lista li:before{content:"·"; position:absolute; left:1px; font-weight:700; color:var(--ink-3)}

/* Lo que el folio NO dice es una lista larga de negaciones: se pliega, como la
   definición de las clases, y en la ficha imprimible sale desplegada. */
.cert details{margin:7px 0 0}
.cert details + details{margin-top:3px}
.cert summary{cursor:pointer; color:var(--accent); font-size:10.5px; font-weight:600}
.cert details ul{margin:4px 0 0; padding:0; list-style:none; columns:2; column-gap:18px}
.cert details li{padding:1px 0 1px 10px; position:relative; font-size:10px; line-height:1.35;
  color:var(--ink-3); break-inside:avoid}
.cert details li:before{content:"·"; position:absolute; left:1px}
.cert .c-pie{margin:8px 0 0; font-size:9.5px; color:var(--ink-3); line-height:1.4}

/* En la ficha imprimible la tabla de anotaciones no se parte entre páginas si cabe
   entera, y si no cabe repite su encabezado en la siguiente. */
@media print{
  .cert table,.cert tr{break-inside:avoid; page-break-inside:avoid}
  .cert thead{display:table-header-group}
}
"""


_TPL = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lotes por grilla · Prospectos solares</title>
<style>
/* Sistema de color verificado: neutrales de matiz teal, acento tipográfico y cuatro
   tokens de clase. El color acompaña a texto y forma; nunca los sustituye. */
:root{
  --fondo:#F4F6F6; --superficie:#FFFFFF; --superficie-2:#EAEFF0; --superficie-3:#E4EAEA; --hover:#F3F6F6;
  --borde-sutil:#DCE2E2; --borde-control:#7A8889;
  --texto:#1E2829; --texto-2:#49585A; --texto-3:#5C6B6D;
  --marca:#18919C; --acento:#0F6A72; --acento-fuerte:#0B5057; --acento-suave:#E3EFF0;
  --sobre-acento:#FFFFFF; --foco:#0B5057;
  --inerte-fondo:#EAEFF0; --inerte-texto:#5C6B6D; --inerte-borde:#AEB9BA;
  --ok:#2F6B4C; --ok-fondo:#E6F1EA; --aviso:#8A5C17; --aviso-fondo:#F8EFDC;
  --alerta:#9C3A1F; --alerta-fondo:#F8E7E1;
  /* Tres clases, tres colores: azul Idóneo, ámbar Viable con gestión, rojo No viable. */
  --clase-1:#1F5FA8; --clase-1-texto:#17457A; --clase-1-fondo:#E4EBF6;
  --clase-2:#B0741A; --clase-2-texto:#794D0C; --clase-2-fondo:#F8EEDC;
  --clase-3:#B03A1E; --clase-3-texto:#7E2712; --clase-3-fondo:#F8E6E0;
  --clase-4:#879596; --clase-4-texto:#4C5A5C; --clase-4-fondo:#E9ECEC;
  /* Sobre la imagen satelital el color no puede depender del tema: la foto es la misma
     de día y de noche. Estos tres tonos se leen con relleno al 34 % y trazo del mismo
     tono a plena opacidad sobre pasto, suelo desnudo y agua. */
  --mapa-idoneo:#2F6FD8; --mapa-gestion:#E3A02A; --mapa-noviable:#DC4526;
  --mapa-red:#D07BFF; --mapa-sub:#FF7A3D; --mapa-planta:#FFE04D;
  --marcador-trazo:#49585A; --mapa-tierra:#EDF0F0; --mapa-linea:#C3CCCC;
  --rad:8px; --sombra:0 1px 2px rgba(30,40,41,.06), 0 4px 14px rgba(30,40,41,.05);
  /* Nombres heredados: apuntan a los tokens nuevos, sin hex propio. */
  --brand:var(--marca); --accent:var(--acento); --accent-2:var(--acento-fuerte); --accent-soft:var(--acento-suave);
  --ground:var(--fondo); --surface:var(--superficie); --surface-2:var(--superficie-2);
  --ink:var(--texto); --ink-2:var(--texto-2); --ink-3:var(--texto-3);
  --line:var(--borde-sutil); --line-2:var(--borde-control);
  --good:var(--ok); --warn:var(--aviso); --bad:var(--alerta); --mute:var(--texto-3);
  --good-bg:var(--ok-fondo); --warn-bg:var(--aviso-fondo); --bad-bg:var(--alerta-fondo);
  --on-accent:var(--sobre-acento); --shadow:var(--sombra);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --fondo:#121819; --superficie:#1A2223; --superficie-2:#222C2D; --superficie-3:#2A3435; --hover:#202A2B;
    --borde-sutil:#303A3B; --borde-control:#6C7A7B;
    --texto:#E6EAEA; --texto-2:#B4BEBF; --texto-3:#93A1A2;
    --marca:#22A4B0; --acento:#4FBAC4; --acento-fuerte:#7FD4DC; --acento-suave:#123539;
    --sobre-acento:#0E1516; --foco:#7FD4DC;
    --inerte-fondo:#222C2D; --inerte-texto:#93A1A2; --inerte-borde:#4A5859;
    --ok:#71B593; --ok-fondo:#183028; --aviso:#DCA950; --aviso-fondo:#2E2617;
    --alerta:#D87F66; --alerta-fondo:#33201C;
    --clase-1:#6E9AE0; --clase-1-texto:#6E9AE0; --clase-1-fondo:#17243A;
    --clase-2:#EDC582; --clase-2-texto:#EDC582; --clase-2-fondo:#2E2617;
    --clase-3:#E08C72; --clase-3-texto:#E08C72; --clase-3-fondo:#33201C;
    --clase-4:#ADB8B9; --clase-4-texto:#ADB8B9; --clase-4-fondo:#252E2F;
    --marcador-trazo:#B4BEBF; --mapa-tierra:#2A3435; --mapa-linea:#3E4A4B;
    --sombra:0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"]{
  --fondo:#121819; --superficie:#1A2223; --superficie-2:#222C2D; --superficie-3:#2A3435; --hover:#202A2B;
  --borde-sutil:#303A3B; --borde-control:#6C7A7B;
  --texto:#E6EAEA; --texto-2:#B4BEBF; --texto-3:#93A1A2;
  --marca:#22A4B0; --acento:#4FBAC4; --acento-fuerte:#7FD4DC; --acento-suave:#123539;
  --sobre-acento:#0E1516; --foco:#7FD4DC;
  --inerte-fondo:#222C2D; --inerte-texto:#93A1A2; --inerte-borde:#4A5859;
  --ok:#71B593; --ok-fondo:#183028; --aviso:#DCA950; --aviso-fondo:#2E2617;
  --alerta:#D87F66; --alerta-fondo:#33201C;
  --clase-1:#6E9AE0; --clase-1-texto:#6E9AE0; --clase-1-fondo:#17243A;
  --clase-2:#EDC582; --clase-2-texto:#EDC582; --clase-2-fondo:#2E2617;
  --clase-3:#E08C72; --clase-3-texto:#E08C72; --clase-3-fondo:#33201C;
  --clase-4:#ADB8B9; --clase-4-texto:#ADB8B9; --clase-4-fondo:#252E2F;
  --marcador-trazo:#B4BEBF; --mapa-tierra:#2A3435; --mapa-linea:#3E4A4B;
  --sombra:0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0; background:var(--fondo); color:var(--texto);
  font:14px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,sans-serif}
button{font:inherit; cursor:pointer}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--foco); outline-offset:2px}

/* cabecera */
/* Cabecera apretada a proposito: cada pixel que se ahorra aqui es un pixel de mapa. */
header{background:var(--surface); border-bottom:1px solid var(--line); padding:6px 22px}
.head{display:flex; align-items:center; justify-content:space-between; gap:20px; flex-wrap:wrap}
.brand{display:flex; align-items:center; gap:14px; margin-bottom:5px}
.brand-mark{width:44px; height:48px; flex:none}
.brand-text{display:flex; flex-direction:column; line-height:1.05}
.brand-name{font-weight:700; font-size:19px; letter-spacing:.01em; color:var(--brand)}
.brand-sub{font-size:11px; color:var(--ink-3); letter-spacing:.14em; text-transform:uppercase; margin-top:2px}
h1{font-size:19px; margin:2px 0 0; letter-spacing:-.01em}
.eyebrow{font-size:10.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:700}
.sub{color:var(--ink-2); margin:1px 0 0; font-size:12.5px; max-width:78ch}
.controles{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.seg{display:inline-flex; border:1px solid var(--line-2); border-radius:20px; overflow:hidden; background:var(--surface-2)}
.seg button{border:0; background:transparent; padding:6px 14px; color:var(--ink-2); font-size:12.5px; font-weight:600}
.seg button.on{background:var(--accent); color:var(--on-accent)}
select{padding:7px 10px; border:1px solid var(--line-2); border-radius:6px; background:var(--surface); color:var(--ink); font-size:13px; min-width:260px}
.origen{font-size:11.5px; color:var(--ink-3)}

/* banda de criterios: zona propia, hundida, entre la cabecera y los resultados */
.criterios{background:var(--superficie-2); border-top:1px solid var(--borde-sutil);
  border-bottom:2px solid var(--acento); border-left:3px solid var(--acento);
  padding:5px 22px; position:sticky; top:0; z-index:30}
.cri-cab{display:flex; align-items:center; gap:10px; flex-wrap:wrap; min-height:28px}
.cri-cab h2{font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--texto-3); margin:0; font-weight:700}
.cri-pastillas{display:flex; gap:6px; flex-wrap:wrap; flex:1 1 auto}
.cri-chip{display:inline-flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600;
  padding:3px 9px; border-radius:4px; background:var(--acento-suave); border:1.5px solid var(--acento); color:var(--acento)}
.cri-chip::before{content:""; width:6px; height:6px; border-radius:50%; background:var(--acento); flex:none}
.cri-chip .deja{font-size:10px; letter-spacing:.06em; text-transform:uppercase; font-weight:600}
.cri-chip.cero{background:var(--alerta-fondo); border-color:var(--alerta); color:var(--alerta)}
.cri-chip.cero::before{background:var(--alerta)}
.cri-chip button{border:0; background:none; color:inherit; padding:0 0 0 2px; font-size:13px; line-height:1}
.cri-ninguno{font-size:11.5px; color:var(--texto-3)}
.cri-contador{font-size:12.5px; color:var(--texto); font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap}
.btn-sec{border:1px solid var(--borde-control); background:var(--superficie); color:var(--texto-2);
  border-radius:4px; padding:4px 10px; font-size:11.5px; font-weight:600}
.btn-sec:hover{color:var(--acento-fuerte); border-color:var(--acento-fuerte)}
.btn-sec[aria-disabled="true"]{background:var(--inerte-fondo); color:var(--inerte-texto); border-color:var(--inerte-borde); cursor:default}
.cri-cuerpo{display:flex; flex-direction:column; gap:9px; padding:10px 0 4px}
.cri-cuerpo[hidden]{display:none}
.cri-grupo{display:flex; gap:8px 14px; flex-wrap:wrap; align-items:center}
.cri-rot{font-size:9.5px; letter-spacing:.11em; text-transform:uppercase; color:var(--texto-3); font-weight:700; width:150px; flex:none}
.cri-resumen{font-size:11.5px; color:var(--texto-3)}
.cri-resumen b{color:var(--texto); font-variant-numeric:tabular-nums}

/* cuerpo: mapa y resultados; la ficha del lote solo existe si hay lote elegido */
/* El mapa de la grilla es la pieza principal y ocupa el doble que la lista. */
/* La imagen de la grilla es CUADRADA: el ancho que sobre por encima de su alto se ve
   como banda gris a los lados. La columna se estrecha para acercarla a ese cuadrado, y
   lo que se quita aqui lo gana la ficha, que es texto y agradece el ancho. */
.cuerpo{display:grid; grid-template-columns:minmax(400px,.65fr) minmax(330px,1fr);
  gap:14px; padding:5px 22px 10px; align-items:start}
.col3{display:none}
.cuerpo.con-lote .col3{display:block}
/* La ficha se superpone; NO reordena la pagina. Antes, al pulsar un lote la rejilla
   pasaba de dos columnas a tres y el mapa se encogia de 2.4fr a 2.2fr: elegir un lote
   movia de sitio todo lo que se estaba mirando. Ahora el mapa y la lista se quedan
   donde estan y la ficha entra por la derecha como una capa que se cierra. */
.cuerpo.con-lote .col3{position:fixed; top:0; right:0; bottom:0; width:440px; max-width:94vw;
  z-index:40; overflow:auto; border-radius:0; border-right:0;
  box-shadow:-10px 0 30px rgba(30,40,41,.16)}
/* La ficha OCUPA EL SITIO de la lista, no se pone encima. Superponerla tapaba el panel
   de resultados, que mide justo lo mismo, de modo que abrir un lote escondia la lista.
   Y encogerla en una tercera columna movia el mapa. Asi no ocurre ninguna de las dos:
   la columna derecha muestra la lista o la ficha, y el mapa no se entera. */
.cuerpo.con-lote .col2{display:none}
.cuerpo.con-lote .col3{grid-column:2; position:static; width:auto; max-height:none;
  box-shadow:var(--sombra); border-radius:var(--rad)}
#velo-ficha{display:none}
@media (max-width:760px){ .cuerpo.con-lote .col3{grid-column:1} }
@media (max-width:760px){ .cuerpo{grid-template-columns:1fr} }
.panel{background:var(--superficie); border:1px solid var(--borde-sutil); border-radius:var(--rad); box-shadow:var(--sombra)}
.panel h2{font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--acento);
  margin:0; padding:6px 14px; border-bottom:1px solid var(--borde-sutil); display:flex; justify-content:space-between; align-items:center; gap:10px}
.panel h2 span{font-weight:400; text-transform:none; letter-spacing:0; color:var(--texto-3); font-size:11.5px}
.cerrar{border:1px solid var(--borde-control); white-space:nowrap; background:var(--superficie); color:var(--texto-2); border-radius:4px; padding:2px 8px; font-size:12px}

/* mapa de la celda */
/* En bloque, no en fila. Puesto en flex, los controles de capas se colocaban AL LADO
   del mapa y le robaban la mitad del ancho, que es lo que se veia como dos rectangulos
   grises a los lados de la imagen. */
.mapa-caja{position:relative; padding:6px}
__CERT_CSS__
/* La definicion de las clases se lee una vez. Abierta ocupaba 374 px por encima del
   mapa, que es la pieza que el lector viene a mirar, asi que arranca plegada. */
.clases .clases-grid, .clases .proc-grid{display:none}
.clases.abierta .proc-grid{display:block}
.proc-paso{display:grid; grid-template-columns:26px 1fr; gap:12px; padding:9px 0;
  border-top:1px solid var(--borde-sutil); align-items:start}
.proc-paso:first-child{border-top:0}
.proc-n{width:24px; height:24px; border-radius:50%; background:var(--acento-suave);
  color:var(--acento); font-size:11px; font-weight:700; display:flex; align-items:center;
  justify-content:center}
.proc-t{font-weight:600; font-size:13px; margin:0 0 2px}
.proc-d{font-size:12.5px; color:var(--texto-2); margin:0 0 3px; line-height:1.5}
.proc-meta{display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:2px 18px; margin-top:4px; font-size:11.5px; color:var(--texto-3)}
.proc-meta b{color:var(--acento); font-weight:600; text-transform:uppercase;
  font-size:9.5px; letter-spacing:.07em; margin-right:5px}
.proc-f b{color:var(--texto-2); font-weight:600}
.proc-calc{display:inline-block; font-size:10px; letter-spacing:.06em; text-transform:uppercase;
  color:#7E4E12; background:#F8EEDC; border-radius:3px; padding:1px 6px; margin-left:6px;
  font-weight:700; vertical-align:1px}
.clases.abierta .clases-grid{display:grid}
.clases .intro{display:none}
.clases.abierta .intro{display:block}
.plegar{margin-left:auto; font-size:11px; padding:3px 9px; border:1px solid var(--borde-control);
  border-radius:4px; background:var(--superficie); color:var(--texto-2); text-transform:none;
  letter-spacing:0; font-weight:400}
/* El mapa se acota a la pantalla. Con height:auto crecia hasta 1.600 px y habia que
   arrastrar el raton para verlo entero, cuando es la pieza principal del visor. */
.mapa{width:100%; height:auto; max-height:calc(100vh - 320px); display:block;
  background:var(--mapa-tierra); border-radius:6px; object-fit:contain; margin:0 auto}
.mapa .celda{fill:none; stroke:var(--marca); stroke-width:1.4; stroke-dasharray:4 3}
/* Trazo obligatorio en todo polígono: el relleno distingue clases, el trazo sostiene el contraste. */
/* Relleno semitransparente para no tapar la foto, trazo del mismo tono a plena
   opacidad para que el lindero se lea, y un halo blanco debajo del trazo para que el
   lindero no se pierda sobre suelo claro. */
.mapa .halo{fill:none; stroke:#FFFFFF; stroke-opacity:.55; stroke-width:3.2; pointer-events:none}
.mapa .lote{fill:var(--mapa-idoneo); fill-opacity:.34; stroke:var(--mapa-idoneo);
  stroke-width:1.8; stroke-opacity:1; cursor:pointer; transition:fill-opacity .12s}
.mapa .lote.c1{fill:var(--mapa-idoneo); stroke:var(--mapa-idoneo)}
.mapa .lote.c2{fill:var(--mapa-gestion); stroke:var(--mapa-gestion)}
.mapa .lote.c3{fill:var(--mapa-noviable); stroke:var(--mapa-noviable)}
.mapa .lote.c4{fill:var(--clase-4); stroke:var(--clase-4); fill-opacity:.2}
.mapa .lote:hover{fill-opacity:.52}
.mapa .lote.sel{fill-opacity:.62; stroke-width:3.4}
.mapa .lote.atenuado{fill-opacity:.06; stroke-opacity:.42}
.mapa .lote.atenuado + .halo,.mapa .halo.atenuado{stroke-opacity:.18}
.mapa .celda{fill:none}
.mapa.con-fondo .celda{stroke:#FFFFFF; stroke-width:2.2; stroke-dasharray:6 4}
/* red eléctrica sobre la grilla */
.mapa .linea-halo{fill:none; stroke:#141A1A; stroke-opacity:.55; stroke-width:5; stroke-linecap:round}
.mapa .linea{fill:none; stroke:var(--mapa-red); stroke-width:2.4; stroke-linecap:round}
.mapa .sub-punto{fill:var(--mapa-sub); stroke:#141A1A; stroke-width:1.4}
.mapa .planta-punto{fill:var(--mapa-planta); stroke:#141A1A; stroke-width:1.4}
.mapa .red-rot{font-size:10px; fill:#FFFFFF; paint-order:stroke; stroke:#141A1A;
  stroke-width:2.6; stroke-opacity:.75; font-weight:600}
.fondo-toggle{display:flex; align-items:center; gap:6px; font-size:11.5px; color:var(--texto-3); padding:6px 4px 0}
.fondo-toggle input{accent-color:var(--acento)}
.leyenda{display:flex; gap:12px; flex-wrap:wrap; padding:0 14px 12px; font-size:11.5px; color:var(--texto-2)}
.leyenda i{display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px}
.gl{font-size:11px; margin-right:4px}
.celda-datos{display:grid; grid-template-columns:repeat(2,1fr); gap:8px 14px; padding:0 14px 14px; font-size:12.5px}
.cd{border-top:1px solid var(--line); padding-top:5px}
.cd .k{font-size:9.5px; letter-spacing:.07em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.cd .v{font-variant-numeric:tabular-nums}

/* controles de la banda de criterios: campo blanco sobre superficie hundida */
.cri-cuerpo label{font-size:11px; color:var(--texto-2); display:flex; align-items:center; gap:5px; white-space:nowrap}
.cri-cuerpo input[type=checkbox]{accent-color:var(--acento); width:14px; height:14px;
  border:1px solid var(--borde-control)}
.campo{display:inline-flex; align-items:center; gap:3px; border:1px solid var(--borde-control);
  border-radius:4px; background:var(--superficie); padding:2px 7px}
.campo input{width:60px; padding:2px 0; border:0; background:transparent; font:inherit; font-size:12px;
  font-variant-numeric:tabular-nums; color:var(--texto)}
.campo input:focus{outline:none}
.campo:focus-within{border-color:var(--acento); box-shadow:0 0 0 1px var(--acento)}
.campo .uni{font-size:10.5px; color:var(--texto-3)}
.campo.act{border-color:var(--acento); border-width:1.5px; background:var(--acento-suave)}
.campo.act input{font-weight:600; color:var(--acento)}
.quita{font-size:10px; letter-spacing:.05em; color:var(--texto-3)}
.preajustes{display:flex; gap:5px; flex-wrap:wrap; align-items:center}
.preajustes .pre{font-size:11.5px; padding:4px 9px; border:1px solid var(--borde-control); border-radius:4px; background:var(--superficie); color:var(--texto-2)}
.preajustes .pre.on{border-color:var(--acento); border-width:1.5px; color:var(--acento); background:var(--acento-suave); font-weight:600}
.preajustes .pre small{color:var(--texto-3); font-weight:400}
.preajustes .pre.on small{color:var(--acento)}
.cri-cuerpo .ayuda{font-size:11px; color:var(--texto-3); line-height:1.45}

/* resultados: superficie blanca, sin tinte de control */
.res-cab{display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:9px 14px; border-bottom:1px solid var(--borde-sutil)}
.res-orden{font-size:11.5px; color:var(--texto-3); flex:1 1 auto}
.res-orden b{color:var(--texto); font-variant-numeric:tabular-nums}
.facetas{display:flex; gap:5px; flex-wrap:wrap}
.faceta{font-size:11px; font-weight:600; padding:2px 9px; border-radius:10px; border:1px solid var(--borde-control); background:var(--superficie); color:var(--texto-2)}
.faceta.on.c1{background:var(--clase-1-fondo); border-color:var(--clase-1); color:var(--clase-1-texto)}
.faceta.on.c2{background:var(--clase-2-fondo); border-color:var(--clase-2); color:var(--clase-2-texto)}
.faceta.on.c3{background:var(--clase-3-fondo); border-color:var(--clase-3); border-style:dashed; color:var(--clase-3-texto)}
.faceta[aria-disabled="true"]{background:var(--inerte-fondo); border-color:var(--inerte-borde); color:var(--inerte-texto); cursor:default}
.lista{max-height:640px; overflow:auto}
.tabla-lotes{width:100%; border-collapse:collapse; font-size:12.5px}
.tabla-lotes thead th{position:sticky; top:0; z-index:2; background:var(--superficie-2); color:var(--texto-3);
  font-size:9.5px; letter-spacing:.07em; text-transform:uppercase; font-weight:700; text-align:right;
  padding:0; border-bottom:1px solid var(--borde-sutil); white-space:nowrap}
.tabla-lotes thead th:nth-child(1),.tabla-lotes thead th:nth-child(2){text-align:left}
.tabla-lotes th button{border:0; background:none; color:inherit; font:inherit; padding:7px 8px; width:100%; text-align:inherit}
.tabla-lotes th span{display:inline-block; padding:7px 8px}
.tabla-lotes th[aria-sort] button{color:var(--acento)}
.tabla-lotes td{padding:7px 8px; border-bottom:1px solid var(--borde-sutil); text-align:right;
  font-variant-numeric:tabular-nums; vertical-align:top; white-space:nowrap}
.tabla-lotes td.t-lote,.tabla-lotes td.t-n{text-align:left}
/* Composición de la cobertura: una clase por línea, el porcentaje alineado a la derecha,
   de modo que la mezcla del lote se lea de un vistazo sin sumar nada. */
.tabla-lotes td.t-cob{text-align:left; white-space:nowrap}
.cob-cl{display:flex; justify-content:space-between; gap:10px; font-size:11.5px;
  color:var(--texto-2); line-height:1.5}
.cob-cl b{color:var(--texto); font-weight:600; font-variant-numeric:tabular-nums}
.tabla-lotes tbody tr{cursor:pointer}
.tabla-lotes tbody tr:hover td{background:var(--hover)}
.tabla-lotes tbody tr.sel td{background:var(--acento-suave)}
.tabla-lotes tbody tr.sel td.t-n{box-shadow:inset 3px 0 0 var(--acento)}
.tabla-lotes td small{display:block; font-size:10.5px; color:var(--texto-3); font-weight:400}
.tabla-lotes .mal{color:var(--alerta)}
.tabla-lotes td.t-lote b{font-weight:600}
.tabla-lotes td .cod{font-family:ui-monospace,Consolas,monospace; font-size:10px; color:var(--texto-3)}
.pill{display:inline-block; padding:1px 8px; border-radius:10px; font-size:10px; font-weight:700;
  letter-spacing:.04em; text-transform:uppercase; border:1px solid transparent}
.pill.c1{background:var(--clase-1-fondo); color:var(--clase-1-texto); border-color:var(--clase-1)}
.pill.c2{background:var(--clase-2-fondo); color:var(--clase-2-texto); border-color:var(--clase-2)}
.pill.c3{background:var(--clase-3-fondo); color:var(--clase-3-texto); border-color:var(--clase-3); border-style:dashed}
.pill.c4{background:var(--clase-4-fondo); color:var(--clase-4-texto); border-color:var(--clase-4); text-decoration:line-through}
.vacio{padding:26px 14px; color:var(--texto-3); text-align:center; font-size:13px}

/* detalle */
.detalle{padding:14px}
.det-cab{display:flex; justify-content:space-between; gap:12px; align-items:flex-start}
.det-cab h3{margin:0; font-size:16px}
.det-cab .cod{font-family:ui-monospace,Consolas,monospace; font-size:11px; color:var(--ink-3); word-break:break-all}
.det-cifra{text-align:right; flex:none}
.det-cifra b{font-size:28px; line-height:1; display:block; color:var(--texto); font-variant-numeric:tabular-nums}
.det-cifra span{font-size:9.5px; color:var(--texto-3); letter-spacing:.06em; text-transform:uppercase; display:block}
.det-cifra em{font-size:11.5px; color:var(--texto-3); font-style:normal; font-variant-numeric:tabular-nums}
.det-motivo{font-size:12.5px; color:var(--texto-2); margin:8px 0 12px; padding:8px 10px; background:var(--superficie-2); border-radius:6px}
.datos{display:grid; grid-template-columns:repeat(3,1fr); gap:9px 12px}
.dato{border-top:1px solid var(--line); padding-top:5px}
.dk{font-size:9.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.dv{font-size:14px; font-variant-numeric:tabular-nums; margin-top:1px}
.dv small{font-size:10.5px; color:var(--ink-3)}
h4{font-size:10.5px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); margin:16px 0 7px; padding-bottom:4px; border-bottom:1px solid var(--line)}
.jur{display:flex; flex-direction:column; gap:6px}
.jur .fila{display:grid; grid-template-columns:auto 1fr; gap:8px; font-size:12.5px; align-items:start}
.sem{width:9px; height:9px; border-radius:50%; margin-top:6px}
.sem.rojo{background:var(--bad)} .sem.ambar{background:var(--warn)} .sem.verde{background:var(--good)} .sem.gris{background:var(--ink-3)}
.jur b{font-weight:600}
.jur span{color:var(--ink-2)}
.sat-caja{position:relative; border:1px solid var(--line); border-radius:6px; overflow:hidden; line-height:0; margin-top:10px}
.sat-img{width:100%; height:auto; display:block}
.sat-svg{position:absolute; inset:0; width:100%; height:100%}
.sat-cred{position:absolute; right:4px; bottom:3px; font-size:8px; color:#fff; background:rgba(0,0,0,.45); padding:1px 4px; border-radius:2px; line-height:1.4; text-shadow:0 1px 2px rgba(0,0,0,.7)}
.sat-aviso{font-size:11.5px; color:var(--warn); background:var(--warn-bg); border-radius:0 0 6px 6px; padding:5px 9px; margin-top:-1px; line-height:1.4}
.acciones{display:flex; gap:8px; margin-top:14px; flex-wrap:wrap}
.btn{border:1px solid var(--line-2); background:var(--surface); color:var(--ink); border-radius:6px; padding:7px 12px; font-size:12.5px; font-weight:600}
.btn.p{background:var(--accent); border-color:var(--accent); color:var(--on-accent)}
.btn:hover{filter:brightness(.97)}
.nada{color:var(--ink-3); font-size:13px; padding:30px 14px; text-align:center}
.pot-dot{display:inline-block; width:8px; height:8px; border-radius:50%; margin:0 3px 0 1px; vertical-align:0}
.pot-dot.rojo{background:var(--bad)} .pot-dot.ambar{background:var(--warn)} .pot-dot.verde{background:var(--good)}
.valor{border:1px solid var(--line); border-radius:6px; padding:9px 11px; font-size:12.5px}
.valor.alta{border-color:var(--good)} .valor.media{border-color:var(--warn)} .valor.baja,.valor.sin{border-color:var(--line-2)}
.v-cab{display:flex; justify-content:space-between; align-items:baseline}
.v-conf{font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3)}
.v-num{font-size:20px; font-weight:700; color:var(--brand); margin:4px 0 2px; font-variant-numeric:tabular-nums}
.v-num small{font-size:11px; font-weight:400; color:var(--ink-3)} .v-num em{color:var(--ink-3); font-style:normal; margin:0 4px}
.v-det{color:var(--ink-2)} .v-nota{color:var(--ink-3); font-size:11.5px; margin-top:4px}
.valor.sin span{color:var(--ink-3); display:block; margin-top:2px}
.idx-tabla{width:100%; border-collapse:collapse; font-size:11.5px; margin:6px 0 4px}
.idx-tabla th{font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600; text-align:left; padding:4px 6px; border-bottom:1px solid var(--line)}
.idx-tabla td{padding:4px 6px; border-bottom:1px solid var(--line); font-variant-numeric:tabular-nums; vertical-align:top}
.idx-tabla tr.reparo td{background:var(--bad-bg)} .idx-tabla tr.corto td{background:var(--warn-bg)}
.idx-tabla tr.total td{border-bottom:none; color:var(--ink-2)} .idx-tabla small{color:var(--ink-3)}
.tag-rep{font-size:9.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--bad); font-weight:700; margin-left:4px}
.idx-nota{font-size:11.5px; color:var(--ink-2); margin:4px 0 6px; line-height:1.45}
.aviso-cat{grid-column:1 / -1; font-size:11.5px; color:var(--warn); background:var(--warn-bg); border-radius:6px; padding:7px 9px; line-height:1.45}
.fuentes{max-width:1480px; margin:0 auto; padding:10px 22px 36px}
.fuentes h2{font-size:12px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); margin:18px 0 4px}
.fuentes-sub{font-size:12.5px; color:var(--ink-2); margin:0 0 10px; max-width:900px}
.tabla-scroll{overflow-x:auto}
.fuentes-tabla{width:100%; border-collapse:collapse; font-size:12px; background:var(--surface); border:1px solid var(--line); border-radius:var(--rad)}
.fuentes-tabla th{text-align:left; font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); padding:8px 10px; border-bottom:1px solid var(--line)}
.fuentes-tabla td{padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--ink-2)}
.fuentes-tabla td b{color:var(--ink)} .fuentes-tabla a{color:var(--accent); word-break:break-all}
.fuentes-tabla td.ver{white-space:nowrap} .fuentes-tabla td.ver a{word-break:normal}
.mini-nota{font-size:11.5px; color:var(--ink-3); margin:4px 0 0; line-height:1.45}
.notas-fuentes{display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px 26px; margin-top:16px}
.nota-bloque{border-top:2px solid var(--borde-sutil); padding-top:9px}
.nota-bloque h3{font-size:12.5px; margin:0 0 6px; color:var(--texto)}
.nota-bloque p{font-size:12px; color:var(--texto-2); line-height:1.55; margin:0 0 7px; max-width:92ch}
.origen-nota{font-size:12px; color:var(--texto-2); line-height:1.55; margin:10px 0 0; max-width:104ch;
  background:var(--superficie-2); border-left:3px solid var(--borde-control); border-radius:4px; padding:9px 12px}
.defs{margin:6px 0 2px; font-size:12px} .defs summary{cursor:pointer; color:var(--accent); font-size:12px} .defs .jur{margin-top:6px}
.paso-cert{background:var(--accent-soft); border-radius:6px; padding:10px 12px; font-size:12.5px; color:var(--ink-2)}
.paso-cert p{margin:0 0 8px}
.paso-cert .mini{margin:8px 0 0; font-size:11.5px; color:var(--ink-3)}
.paso-cert code{font-family:ui-monospace,Consolas,monospace; font-size:11px; background:var(--surface); padding:1px 5px; border-radius:3px}

/* bloque de apertura: qué hace idóneo, viable con gestión o no viable a un lote */
/* Plegada es una linea con un boton, asi que apenas necesita aire; desplegada
   recupera el suyo. Lo que se ahorra aqui va al alto de la imagen de la grilla. */
.clases{background:var(--superficie); border-bottom:1px solid var(--borde-sutil); padding:3px 22px}
.clases.abierta{padding:14px 22px 16px}
.clases h2{display:flex; align-items:center; gap:12px}
.clases h2{font-size:11px; letter-spacing:.13em; text-transform:uppercase; color:var(--acento); margin:0 0 3px; font-weight:700}
.clases .intro{font-size:12.5px; color:var(--texto-2); margin:0 0 11px; max-width:104ch}
.clases-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px}
.clase-tarjeta{border:1px solid var(--borde-sutil); border-left-width:5px; border-radius:var(--rad);
  padding:10px 13px 12px; background:var(--superficie)}
.clase-tarjeta.c1{border-left-color:var(--clase-1); background:var(--clase-1-fondo)}
.clase-tarjeta.c2{border-left-color:var(--clase-2); background:var(--clase-2-fondo)}
.clase-tarjeta.c3{border-left-color:var(--clase-3); background:var(--clase-3-fondo)}
.clase-tarjeta h3{margin:0 0 5px; font-size:14px; display:flex; align-items:baseline; gap:7px; flex-wrap:wrap}
.clase-tarjeta.c1 h3{color:var(--clase-1-texto)}
.clase-tarjeta.c2 h3{color:var(--clase-2-texto)}
.clase-tarjeta.c3 h3{color:var(--clase-3-texto)}
.clase-color{font-size:10px; letter-spacing:.07em; text-transform:uppercase; font-weight:600; color:var(--texto-3)}
.clase-def{margin:0 0 6px; font-size:12px; color:var(--texto-2); line-height:1.5}
.clase-cond{margin:0; font-size:11.5px; color:var(--texto-2); line-height:1.5;
  border-top:1px solid var(--borde-sutil); padding-top:6px}
.clase-cond b{color:var(--texto)}

/* banda de criterios: grupos con rótulo formal */
.cri-nota{font-size:11.5px; color:var(--texto-2); margin:6px 0 2px; max-width:110ch}
.cri-cuerpo{display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:10px 18px; padding:8px 0 4px}
.cri-grupo{border-top:2px solid var(--acento); padding-top:7px}
.cri-grupo h3{display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin:0; font-size:11px; letter-spacing:.09em; text-transform:uppercase; color:var(--acento); font-weight:700}
.cri-desc{margin:2px 0 7px; font-size:11px; color:var(--texto-3); line-height:1.45}
.cri-lineas{display:flex; flex-direction:column; gap:8px}
.cri-linea label{font-size:11.5px; color:var(--texto); display:block; white-space:normal; line-height:1.6}
.cri-linea .cri-ayuda{display:block; font-size:10.5px; color:var(--texto-3); line-height:1.45; margin-top:2px}
.cri-mas{margin-top:9px}
.cri-mas summary{font-size:11px; color:var(--acento); cursor:pointer; font-weight:600}
.cri-mas .cri-lineas{margin-top:8px; padding-left:9px; border-left:2px solid var(--borde-sutil)}
.cri-resumen{font-size:12px; color:var(--texto-2); padding:6px 0 0; border-top:1px solid var(--borde-sutil)}
.cri-vacio{color:var(--alerta); font-weight:600}

/* leyenda del mapa, con la red eléctrica */
.leyenda-tit{font-size:9.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--texto-3); font-weight:700; width:100%; margin-top:2px}
.leyenda .sinred{color:var(--texto-3); font-style:normal}
.red-lista{padding:0 14px 10px; font-size:11.5px; color:var(--texto-2); line-height:1.55}
.red-lista b{color:var(--texto)}

/* reparos enumerados en la ficha */
.reparos{display:flex; flex-direction:column; gap:9px}
.reparo{border:1px solid var(--clase-2); border-left-width:4px; border-radius:6px;
  padding:8px 10px; background:var(--clase-2-fondo); font-size:12px; line-height:1.5}
.reparo.grave{border-color:var(--clase-3); background:var(--clase-3-fondo)}
.reparo b{display:block; font-size:12.5px; color:var(--texto); margin-bottom:3px}
.reparo .rk{font-size:9.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--texto-3); font-weight:700}
.reparo p{margin:3px 0 0; color:var(--texto-2)}
.sin-reparos{font-size:12.5px; color:var(--texto-2); background:var(--clase-1-fondo);
  border:1px solid var(--clase-1); border-left-width:4px; border-radius:6px; padding:9px 11px; line-height:1.5}
.cond-adq{display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--texto-2)}
.cond-adq div{border-top:1px solid var(--line); padding-top:4px}

/* glosario al pie */
.glosario{columns:2; column-gap:26px; font-size:12px; color:var(--ink-2); line-height:1.5}
@media (max-width:820px){ .glosario{columns:1} }
.gl-item{break-inside:avoid; margin:0 0 7px}
.gl-item b{color:var(--ink)}
.gl-h3{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent); margin:16px 0 6px}
</style>
</head>
<body>
<header>
  <div class="head">
    <div>
      <div class="brand">
        <svg class="brand-mark" viewBox="0 0 92 100" aria-hidden="true">
          <g fill="var(--brand)">
            <rect x="0"  y="27.0" width="8.4" height="46.0" rx="4.2"></rect>
            <rect x="14" y="21.5" width="8.4" height="57.0" rx="4.2"></rect>
            <rect x="28" y="16.0" width="8.4" height="68.0" rx="4.2"></rect>
            <rect x="42" y="11.0" width="8.4" height="78.0" rx="4.2"></rect>
            <rect x="56" y="6.0"  width="8.4" height="88.0" rx="4.2"></rect>
            <rect x="70" y="2.5"  width="8.4" height="95.0" rx="4.2"></rect>
            <rect x="83.6" y="0"  width="8.4" height="100"  rx="4.2"></rect>
          </g>
        </svg>
        <span class="brand-text"><span class="brand-name">Métodos Mixtos</span><span class="brand-sub">Consultores</span></span>
      </div>
      <div class="eyebrow">Prospectos solares · lotes por grilla</div>
      <h1>De la grilla seleccionada al lote que se visita</h1>
      <p class="sub">Elija una grilla, aplique los criterios del proyecto y abra la ficha de cada lote. La lista se ordena por el área catastral del lote.</p>
    </div>
    <div class="controles">
      <select id="sel-celda" aria-label="Grilla"></select>
      <span class="origen" id="origen"></span>
    </div>
  </div>
</header>

<section class="clases" id="clases">
  <h2>Qué hace que un lote sea idóneo, viable con gestión o no viable
    <button class="plegar" id="clases-plegar" aria-expanded="false">Mostrar la definición de las tres clases</button></h2>
  <p class="intro">Cada lote de la lista recibe una de estas tres clases. La clase describe el resultado del análisis y no retira ningún lote de la lista: los tres se muestran siempre. El color acompaña siempre al nombre escrito, de modo que la lectura no dependa de distinguir tonos.</p>
  <div class="clases-grid">__CLASES__</div>
</section>

<section class="clases proc" id="proceso">
  <h2>Cómo se construye la ficha de cada lote
    <button class="plegar" id="proceso-plegar" aria-expanded="false">Mostrar el proceso y las fuentes</button></h2>
  <p class="intro">El orden en que se consulta cada fuente y qué aporta. Todo lo que aparece
    en la ficha sale de alguno de estos pasos. Donde una cifra no viene de una entidad sino
    de un cálculo de este estudio, se dice aquí y se dice en la ficha.</p>
  <div class="proc-grid">__PROCESO__</div>
</section>

<section class="criterios" id="criterios">
  <div class="cri-cab">
    <h2>Criterios de filtrado de la lista</h2>
    <div class="cri-pastillas" id="cri-pastillas"></div>
    <span class="cri-contador" id="cri-contador"></span>
    <button class="btn-sec" id="f-reset">Restablecer todos los criterios</button>
    <button class="btn-sec" id="cri-plegar" aria-expanded="false" aria-controls="cri-cuerpo">Mostrar los criterios de filtrado</button>
  </div>
  <div class="cri-cuerpo" id="cri-cuerpo" hidden>
    <p class="cri-nota">Cada criterio retira de la lista los lotes que no lo cumplen. Ninguno modifica la clasificación del lote ni su ficha. Un lote sin dato en el criterio no se retira: la ausencia de dato no es un incumplimiento. Los criterios se agrupan por naturaleza y se conservan todos, incluidos los que en las grillas cargadas hoy no retiran ningún lote, porque el visor recibe cualquier archivo de grillas.</p>
    <div class="cri-grupo" style="grid-column:1/-1; border-top-color:var(--borde-sutil)">
      <h3>Escala del proyecto y preajustes de tamaño
        <span class="seg" id="seg-perfil"></span></h3>
      <p class="cri-desc">Fijan de una vez el área y el diámetro del mayor círculo inscrito mínimos que exige cada perfil. El tamaño no descarta ningún lote por sí solo: acota la búsqueda al proyecto que se quiere construir.</p>
      <div class="preajustes" id="preajustes"></div>
    </div>
    <div class="cri-grupo" style="grid-column:1/-1">
      <h3>Clasificación del lote</h3>
      <p class="cri-desc">Retira de la lista las clases que no se quieran ver. La clase
        describe el resultado del análisis; retirarla aquí no la cambia. Vivía junto a la
        lista y desaparecía al abrir una ficha, de modo que se movió a los criterios.</p>
      <div class="facetas" id="facetas"></div>
    </div>
    __CRITERIOS__
    <div class="cri-resumen" id="cri-resumen" style="grid-column:1/-1"></div>
    <div class="ayuda" id="f-ayuda" style="grid-column:1/-1"></div>
  </div>
</section>

<div id="velo-ficha"></div>
<div class="cuerpo" id="cuerpo">
  <div class="panel col1">
    <h2>Grilla seleccionada <span id="celda-titulo"></span></h2>
    <div class="mapa-caja" id="mapa-caja"></div>
    <div class="leyenda" id="leyenda"></div>
    <div class="red-lista" id="red-lista"></div>
    <div class="celda-datos" id="celda-datos"></div>
  </div>

  <div class="panel col2">
    <h2>Lotes que cumplen los criterios <span id="lotes-conteo"></span></h2>
    <div class="res-cab">
      <div class="res-orden" id="res-orden"></div>
      <button class="btn-sec" id="f-csv">Descargar la lista filtrada como hoja de cálculo</button>
      <button class="btn-sec" id="f-fichas">Descargar en PDF las fichas de los lotes filtrados</button>
    </div>
    <div class="lista" id="lista"></div>
  </div>

  <div class="panel col3">
    <h2>Ficha del lote <span id="det-sub"></span><button class="cerrar" id="det-cerrar" title="Volver a la lista de lotes">Volver a la lista</button></h2>
    <div class="detalle" id="detalle"></div>
  </div>
</div>

<section class="fuentes" id="fuentes">
  <h2>Fuentes de información</h2>
  <p class="fuentes-sub">De dónde sale cada dato del visor y de la ficha, con la versión o el corte usado. La columna «Servicio» es la dirección técnica del geoservicio del que se toma el dato, pensada para máquinas; la columna «Ver» abre el visor oficial para personas. Cada consulta se guarda con la fecha en que se hizo, de modo que la ficha muestra el dato del día de la corrida y no el del día en que se lee.</p>
  <div class="tabla-scroll"><table class="fuentes-tabla" id="fuentes-tabla"></table></div>
  <div class="notas-fuentes" id="notas-fuentes"></div>
  <p class="origen-nota" id="origen-nota"></p>
  <h2>Glosario</h2>
  __GLOSARIO__
</section>
<script>
const D = __DATOS__;
// Los textos largos que se repiten palabra por palabra en muchos lotes (la nota de la
// norma urbana es casi la misma dentro de un municipio) se escriben una sola vez en una
// tabla común y cada lote guarda su posición en ella. Aquí vuelven a su sitio.
(function(){
  const T = D.textos || [], campos = D.textos_campos || [];
  if(!T.length || !campos.length) return;
  for(const filas of Object.values(D.lotes || {}))
    for(const l of filas)
      for(const c of campos) if(typeof l[c] === "number") l[c] = T[l[c]] ?? null;
})();
const PERFILES = Object.keys(D.perfiles);
let PERFIL = PERFILES[0], CELDA = null, LOTE = null, FONDO_SAT = true, RED_SAT = true;
// Catálogos escritos una sola vez del lado de Python; de ellos salen a la vez los
// controles del HTML y el cálculo, para que etiqueta y aritmética no se separen.
const CAT_FILTROS = __CAT_FILTROS__;
const CAT_GRUPOS = __CAT_GRUPOS__;
const CAT_CLASES = __CAT_CLASES__;
const COND_ADQ = __CAT_ADQUISICION__;
// Catálogo de condiciones del lote: enunciado, trámite, entidad y fuente de cada una,
// escritos una sola vez. En cada lote viajan solo el código y lo medido en ese lote.
const COND_CAT = D.condiciones_catalogo || [];
const COND_DE = Object.fromEntries(COND_CAT.map(c => [c.codigo, c]));
// Valor activo de cada umbral y estado de cada casilla, por identificador del control.
const V = {}, C = {};
const F = {preajuste:null};
// Clave de orden de la lista: área catastral descendente, la que registra el IGAC.
const ORD = {clave:"area_ha", dir:-1};
// Las tres clases describen el resultado; no son reglas de descarte y viven en la lista.
const CLASES = {"Idóneo":true, "Viable con gestión":true, "No viable":true};

// Un umbral del catálogo se aplica a un campo del lote; el par de área lleva dos.
const UMBRALES = CAT_FILTROS.flatMap(f => f.tipo==="rango"
  ? [{id:f.id+"-min", campo:f.campo, dir:"min", etiqueta:f.etiqueta+" (mínimo)", unidad:"ha"},
     {id:f.id+"-max", campo:f.campo, dir:"max", etiqueta:f.etiqueta+" (máximo)", unidad:"ha"}]
  : f.tipo==="umbral" ? [{id:f.id, campo:f.campo, dir:f.dir, etiqueta:f.etiqueta, unidad:f.unidad}] : []);
const CASILLAS = CAT_FILTROS.filter(f => f.tipo==="casilla");

// Campos que el visor deriva de otros para poder filtrar por ellos.
const ANIO = new Date().getFullYear();
const bandaMin = t => { const m = String(t||"").match(/(\d+(?:[.,]\d+)?)/); return m ? parseFloat(m[1].replace(",", ".")) : null; };
const DERIVA = {
  _valor_millones: l => l.valor_ref_cop==null ? null : l.valor_ref_cop/1e6,
  _valor_millones_ha: l => l.valor_ref_cop_ha==null ? null : l.valor_ref_cop_ha/1e6,
  _sequia_anios: l => bandaMin(l.ent_sequia_retorno),
  _incendio_anios: l => l.ent_incendios_ultimo==null ? null : ANIO - Number(l.ent_incendios_ultimo),
  _restitucion_n: l => (l.restitucion_mpio==null || l.restitucion_mpio < 0) ? null : l.restitucion_mpio,
};
const campoDe = (l, k) => DERIVA[k] ? DERIVA[k](l) : l[k];

// Cada prueba devuelve verdadero cuando la casilla RETIRA ese lote de la lista.
const claseAgro = l => /^[1-3]/.test(String(l.ent_clase_agrologica||""));
const PRUEBAS = {
  "f-construcciones": l => (l.n_construcciones||0) > 0,
  "f-agrologica": claseAgro,
  "f-frontera": l => /Condicionada/.test(String(l.ent_frontera_agricola||"")) && !/^No condicionada$/.test(String(l.ent_frontera_agricola||"")),
  "f-mov-masa": l => ["A","MA"].includes(String(l.ent_mov_masa||"")),
  "f-sismica": l => /^alta$/i.test(String(l.ent_sismica||"")),
  "f-kv": l => l.conexion_kv!=null && l.conexion_kv < 110,
  "f-nina": l => /Excedente/i.test(String(l.ent_nina_precip||"")),
  "f-nino": l => /Déficit|Deficit/i.test(String(l.ent_nino_precip||"")),
  "f-valor-conf": l => ["baja","sin dato"].includes(String(l.valor_confianza||"")),
  "f-pot": l => l.pot_semaforo==="rojo",
  "f-pot-rural": l => !!l.pot_clasificacion && l.pot_clasificacion!=="Rural",
  "f-pot-carto": l => !l.pot_categoria,
  "f-limpios": l => (l.estorbos||0) !== 0,
  "f-uaf": l => !!l.riesgo_baldio,
  "f-restitucion": l => !!l.microzona_urt,
  "f-mineria": l => (l.ent_mineria_titulos||0) > 0,
  "f-solicitud-minera": l => (l.ent_mineria_solicitudes||0) > 0,
  "f-hidrocarburos": l => !!l.ent_hidrocarburos,
  "f-destino": l => !l.destino_economico,
  "f-inund": l => (l.ent_inundaciones_nina||0) > 0,
  "f-drenajes": l => (l.ent_drenajes_n||0) > 0,
  "f-humedal": l => !!l.ent_humedal,
  "f-humedal-natural": l => !!l.humedal_natural || /natural/i.test(String(l.ent_humedal||"")),
  "f-runap": l => (l.ent_runap_ha||0) > 0,
  "f-resguardo": l => (l.ent_resguardo_ha||0) > 0,
  "f-consejo": l => (l.ent_consejo_ha||0) > 0,
  "f-paramo": l => (l.ent_paramo_ha||0) > 0,
  "f-pomca": l => !!l.pomca_fase && l.pomca_fase!=="Aprobado",
  "f-capas": l => !!l.ent_capas_sin_respuesta,
};

const $ = s => document.querySelector(s);
const fmt = (v, d=1) => v==null ? "sin dato" : Number(v).toLocaleString("es-CO",{maximumFractionDigits:d, minimumFractionDigits:d});
const fmt0 = v => fmt(v,0);
// Muchos nombres de subestación ya llevan la tensión ("Lanceros 115 kV"). Repetirla
// produce "Lanceros 115 kV · 115 kV": la tensión solo se añade cuando el nombre no la dice.
const kvSuelto = (nombre, kv) => {
  if(kv == null) return "";
  const txt = fmt0(kv) + " kV";
  if(!nombre) return txt;
  // Se compara sin espacios ni mayusculas: "Lanceros 115 kV" contiene "115kv".
  const plano = String(nombre).toLowerCase().split(" ").join("");
  const aguja = fmt0(kv).toLowerCase().split(" ").join("") + "kv";
  return plano.indexOf(aguja) >= 0 ? "" : txt;
};
const kvSub = c => kvSuelto(c.sub_nombre_subestacion, c.sub_tension_kv);
const fmtCop = v => v==null ? "de pago" : "$"+Number(v).toLocaleString("es-CO");
const fmtM = v => v==null ? "sin dato" : (Number(v)/1e6).toLocaleString("es-CO",{maximumFractionDigits:1})+" M";
// "2026-08-24" -> "24 de agosto de 2026". Las fechas se guardan en formato internacional
// para que no sean ambiguas y se escriben en prosa donde las lee una persona.
const fmtFecha = s => {
  const m = String(s||"").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if(!m) return String(s||"");
  const mes = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
               "septiembre","octubre","noviembre","diciembre"][Number(m[2])-1];
  return `${Number(m[3])} de ${mes} de ${m[1]}`;
};
// "6:77.0;7:24.6" -> "zona 6: 77 ha · zona 7: 25 ha"
const fmtZonas = s => !s ? "sin dato" : String(s).split(";").map(x=>{const [z,a]=x.split(":"); return `zona ${z}: ${fmt0(a)} ha`;}).join(" · ");
// Rótulos de los cinco estados posibles de la norma urbanística. Ninguno baja la clase
// del lote: un hueco de la fuente no es un defecto del terreno.
const NORMA_ESTADO = {
  "POT verificado": ["verde", "Categoría del suelo verificada contra la zonificación publicada"],
  "POT vencido sin cartografía": ["gris", "Sin zonificación publicada y con el instrumento de ordenamiento vencido"],
  "POT sin cobertura en el lote": ["gris", "La zonificación publicada no cubre este lote"],
  "Sin instrumento de ordenamiento registrado": ["gris", "Sin instrumento de ordenamiento registrado para el municipio"],
  "Consulta del POT sin respuesta": ["gris", "La consulta de ordenamiento no obtuvo respuesta"],
};
const PROT_TXT = pct => pct == null ? "sin dato"
  : pct >= 50 ? "la mitad del lote o más en suelo de protección"
  : pct >= 10 ? "una parte del lote en suelo de protección"
  : pct > 0 ? "una fracción menor del lote en suelo de protección"
  : "sin suelo de protección sobre el lote";
function normaUrbana(l){
  const out = [];
  const est = NORMA_ESTADO[l.pot_estado_norma];
  if(est) out.push([est[0], est[1], l.pot_nota ? esc(l.pot_nota) : ""]);
  else if(!l.pot_fecha) out.push(["gris", "Norma urbanística sin consultar para este lote", "La consulta a la cartografía de ordenamiento no se ha hecho para este lote."]);
  if(l.pot_rojo_pct != null)
    out.push([l.pot_rojo_pct >= 50 ? "rojo" : l.pot_rojo_pct >= 10 ? "ambar" : "verde",
      `Superficie del lote en categorías de protección: ${fmt(l.pot_rojo_pct, 1)} %`,
      `${PROT_TXT(l.pot_rojo_pct)}. Por encima del cincuenta por ciento el lote queda No viable; entre el diez y el cincuenta queda Viable con gestión, porque la parte protegida se excluye de la implantación; por debajo del diez solo se anota. La medida es de superficie, no de categoría dominante.`]);
  if(l.pot_categoria)
    out.push(["nota", `Categoría que ocupa más superficie del lote: ${esc(l.pot_categoria)} (${fmt0(l.pot_categoria_pct)} % del lote)`,
      l.pot_zonificado_pct != null ? `La zonificación publicada cubre el ${fmt(l.pot_zonificado_pct, 1)} % de la superficie del lote.` : ""]);
  if(l.pot_reparto && String(l.pot_reparto).includes(";"))
    out.push(["nota", `Reparto de la superficie del lote por categoría: ${esc(l.pot_reparto)}`, ""]);
  if(l.pot_uso_principal)
    out.push(["nota", `Uso principal asignado: ${esc(l.pot_uso_principal)}`,
      l.pot_uso_prohibido ? "Uso prohibido declarado: " + esc(l.pot_uso_prohibido) : "El municipio no publica por medios automáticos los usos prohibido y condicionado."]);
  if(l.pot_clasificacion)
    out.push([l.pot_clasificacion === "Rural" ? "verde" : "rojo",
      `Clasificación del suelo: ${esc(l.pot_clasificacion)}${l.pot_acto ? " (" + esc(l.pot_acto) + ")" : ""}`,
      l.pot_clasificacion === "Rural" ? "" : "Suelo urbano o de expansión: una planta en suelo no cabe en esa clasificación."]);
  if(l.pot_instrumento)
    out.push([l.pot_instrumento_vencido ? "ambar" : "nota",
      `Instrumento del municipio: ${esc(l.pot_instrumento)}`,
      l.pot_instrumento_anios != null
        ? `Han pasado ${fmt0(l.pot_instrumento_anios)} años desde su adopción. La Ley 388 de 1997 fija la vigencia del contenido de largo plazo en doce años y deja vigente el plan adoptado mientras el concejo no apruebe otro: un plan antiguo sigue siendo la norma exigible.`
        : ""]);
  const vp = (D.vigencia_pot || {})[String(l.CODIGO).slice(0, 5)];
  if(vp) out.push([vp.estado === "vigente" ? "verde" : "ambar",
    vp.estado === "vigente"
      ? `Vigencia verificada contra alcaldía, concejo y corporación autónoma el ${fmtFecha(D.vigencia_pot_fecha)}`
      : `El plan mostrado puede no ser el vigente, según la verificación del ${fmtFecha(D.vigencia_pot_fecha)}`,
    esc(vp.nota)]);
  if(!out.length) out.push(["gris", "Sin dato de norma urbanística para este lote", "La categoría del suelo se pide a la Secretaría de Planeación del municipio mediante certificado de uso del suelo."]);
  return out;
}
function entorno(l){
  if(!l.ent_fecha) return [["gris","Entorno sin consultar","La consulta a los geoservicios ambientales no se ha hecho para este lote."]];
  const out = [];
  if(l.ent_capas_sin_respuesta) out.push(["gris",`Capas sin respuesta en la última corrida: ${esc(l.ent_capas_sin_respuesta)}`,"Se vuelven a consultar en la próxima actualización del reporte."]);
  // La Niña: manchas observadas de seis episodios (IDEAM) cruzadas con el polígono del lote.
  const ninas = [["ent_inundacion_1988","1988"],["ent_inundacion_2000","2000"],["ent_inundacion_2011","2010-2011"],["ent_inundacion_2012","2012"],["ent_inundacion_2016","2016"],["ent_inundacion_2020_2022","2020-2022"]].filter(([k])=>l[k]).map(([,a])=>a);
  const pctMax = (l.ent_inundacion_ha_max!=null && l.area_ha) ? 100*l.ent_inundacion_ha_max/l.area_ha : null;
  if(ninas.length) out.push([ninas.length>=2||(pctMax!=null&&pctMax>=25)?"rojo":"ambar",`La Niña: el lote se inundó en ${ninas.length} de 6 episodios (${ninas.join(", ")}); hasta ${fmt(l.ent_inundacion_ha_max,1)} ha${pctMax!=null?" ("+fmt0(pctMax)+" % del lote)":""} en un mismo evento (IDEAM)`, ninas.length>=2 ? "Zona inundable recurrente en años Niña: condiciona cimentación, seguros, acceso y la altura de las estructuras; pedir cota de inundación en campo." : "Verificar cota y drenaje; condiciona cimentación y seguros."]);
  else if(l.ent_inundacion_2011!=null) out.push(["verde","La Niña: fuera de las manchas de inundación observadas de 1988, 2000, 2010-2011, 2012, 2016 y 2020-2022 (IDEAM)",""]);
  if(l.ent_zip_ha>0 || l.ent_cuerpo_agua_ha>0) out.push([l.ent_zip_ha>0?"ambar":"nota",`Zona inundable periódicamente (IDEAM 2022): ${fmt(l.ent_zip_ha,1)} ha del lote${l.ent_cuerpo_agua_ha>0?" · cuerpo de agua "+fmt(l.ent_cuerpo_agua_ha,1)+" ha":""}`,"Área que se inunda de forma recurrente en la temporada de lluvias, aun sin Niña; no sirve para módulos ni subestación."]);
  if(l.ent_nina_precip || l.ent_nino_precip) out.push(["nota",`Clima ENSO (IDEAM 1981-2010): en una Niña típica la lluvia de la zona es ${l.ent_nina_precip?esc(l.ent_nina_precip)+" % de lo normal":"sin dato publicado"}; en un Niño, ${l.ent_nino_precip?esc(l.ent_nino_precip)+" % de lo normal en temporada lluviosa":"sin dato publicado"}${l.ent_sequia_retorno?"; sequía meteorológica cada "+esc(l.ent_sequia_retorno)+" años":""}`,"Describe la exposición climática del sitio a los dos fenómenos; el recurso solar sube en años Niño y baja en años Niña."]);
  if(l.ent_incendios_5km>0) out.push([l.ent_incendios_5km>=5?"ambar":"nota",`Incendios de cobertura vegetal reportados en 5 km: ${l.ent_incendios_5km} (${fmt0(l.ent_incendios_ha_5km)} ha${l.ent_incendios_ultimo?", último "+l.ent_incendios_ultimo:""}) (IDEAM)`,"Riesgo típico de años Niño sobre pastizales secos; pesa en el plan de cortafuegos y en el seguro."]);
  if(l.ent_humedal) out.push(["ambar",`Humedal ${l.ent_humedal} (MADS/Humboldt) toca el envolvente`,"Restricción ambiental probable; confirmar con la CAR y con el polígono exacto."]);
  if(l.ent_drenajes_n) out.push(["nota",`${l.ent_drenajes_n} drenaje${l.ent_drenajes_n>1?"s":""} del IDEAM en el envolvente${l.ent_drenajes&&l.ent_drenajes!=="sin nombre"?": "+l.ent_drenajes:""}`,"Ronda hídrica de 30 m a cada lado (Decreto 1076/2015); no hay capa nacional de rondas."]);
  for(const [k,nom] of [["runap","Área protegida del RUNAP"],["resguardo","Resguardo indígena"],["consejo","Consejo comunitario"],["paramo","Páramo delimitado"]]){
    const ha = l["ent_"+k+"_ha"], nm = l["ent_"+k];
    if(nm) out.push([ha>=1?"rojo":"ambar", `${nom}: ${esc(nm)} (${fmt(ha,1)} ha del lote)`, ha>=1 ? "Figura territorial que el proyecto no puede ocupar." : "Solape menor de una hectárea: desajuste probable de linderos entre capas; verificar."]);
  }
  if(l.ent_mineria_titulos>0) out.push(["rojo",`${l.ent_mineria_titulos} ${l.ent_mineria_titulos===1?"título minero vigente":"títulos mineros vigentes"} (ANM): ${l.ent_mineria_detalle}`,"Conflicto de uso del suelo; el título prevalece."]);
  else if(l.ent_mineria_solicitudes>0) out.push(["ambar",`${l.ent_mineria_solicitudes} solicitud minera vigente (ANM)`,"Puede convertirse en título."]);
  else out.push(["verde","Sin títulos ni solicitudes mineras (ANM)",""]);
  if(l.ent_hidrocarburos) out.push(["ambar",`Bloque de hidrocarburos (ANH): ${l.ent_hidrocarburos}`,"Servidumbres y actividad petrolera posibles; revisar con el operador."]);
  if(l.ent_clase_agrologica) out.push([/^[1-3]/.test(String(l.ent_clase_agrologica))?"ambar":"verde",`Clase agrológica ${l.ent_clase_agrologica} (IGAC${l.ent_clase_agrologica_fuente?", "+esc(l.ent_clase_agrologica_fuente):""})`,/^[1-3]/.test(String(l.ent_clase_agrologica))?"Clases I a III: posible restricción al cambio de uso.":"Sin restricción agrológica al cambio de uso."]);
  if(l.ent_frontera_agricola) out.push(["nota",`Frontera agrícola UPRA: ${l.ent_frontera_agricola}`,""]);
  if(l.ent_pomca) out.push(["nota",`POMCA ${l.ent_pomca}`,"La zonificación interna no está publicada; pedirla a la CAR."]);
  if(l.ent_mov_masa) out.push([l.ent_mov_masa==="A"||l.ent_mov_masa==="MA"?"ambar":"verde",`Amenaza por movimientos en masa: ${({B:"baja",M:"media",A:"alta",MA:"muy alta"})[l.ent_mov_masa]||l.ent_mov_masa} (SGC, municipal)`,""]);
  if(l.ent_sismica) out.push(["nota",`Amenaza sísmica ${String(l.ent_sismica).toLowerCase()} (SGC, NSR-10)`,""]);
  return out;
}
// Desglose del índice: los mismos siete criterios, la misma escala y los mismos pesos
// con que se calcula en el análisis. Recurso y capacidad se heredan de la grilla, que es
// donde se miden. El redondeo previo a puntuar es el mismo, de modo que el índice que
// muestra la ficha coincide al decimal con el que trae el lote.
const rnd = (v, d) => v==null ? null : Math.round(v * 10**d) / 10**d;
function valorCriterio(l, c, k){
  switch(k){
    case "dist_sub": return rnd(l.conexion_km, 2);
    case "cobertura": return rnd(l.cobertura_apta_pct, 1);
    case "pendiente": return rnd(l.pendiente_media, 1);
    case "rugosidad": return rnd(l.rugosidad_m, 1);
    case "dist_via": return rnd(l.dist_via_km, 2);
    case "recurso": return rnd(c.pvout, 0);
    case "capacidad": return rnd(PERFIL==="distribuida" ? c.capacidad_mt_mw : c.capacidad_at_mw, 1);
  }
  return null;
}
function notaCriterio(cr, v){
  const s = cr.mayor_mejor ? 1 : -1, v_=s*v, lim=s*cr.limite, bue=s*cr.bueno, top=s*cr.tope;
  if(v_ <= lim) return 0;
  if(v_ <= bue) return 70*(v_-lim)/Math.max(1e-9, bue-lim);
  const h = top-bue; if(h <= 1e-9) return 70;
  return 70 + 30*Math.min(1, (v_-bue)/h);
}
function desgloseIndice(l){
  const c = celdaActual()||{}, pesos = D.pesos[PERFIL]||{}, umb = (D.umbrales||{})[PERFIL]||{};
  const filas = []; let suma=0, peso=0;
  for(const [k,cr0] of Object.entries(D.criterios)){
    const cr = {...cr0, ...(umb[k]||{})};
    const v = valorCriterio(l, c, k);
    if(v==null){ filas.push({k, cr, v:null, nota:null, peso:pesos[k], reparo:false, corto:false}); continue; }
    const nota = notaCriterio(cr, v), w = pesos[k]||cr.d_cohen;
    const reparo = cr.mayor_mejor ? v < cr.limite : v > cr.limite;
    const corto = cr.mayor_mejor ? v < cr.bueno : v > cr.bueno;
    suma += nota*w; peso += w;
    filas.push({k, cr, v, nota, peso:w, reparo, corto});
  }
  return {filas, indice: peso ? suma/peso : null};
}
function tablaIndice(l){
  const {filas, indice} = desgloseIndice(l);
  const f = (cr, x) => x==null ? "sin dato" : fmt(x, cr.unidad==="km" ? 1 : (cr.unidad==="°"||cr.unidad==="m"||cr.unidad==="MW") ? 1 : 0);
  return `<table class="idx-tabla"><thead><tr><th>Criterio</th><th>Valor medido en el lote</th><th>Límite, nota 0</th><th>Bueno, nota 70</th><th>Tope, nota 100</th><th>Nota</th><th>Peso</th></tr></thead><tbody>
    ${filas.map(r=>`<tr class="${r.reparo?"reparo":r.corto?"corto":""}"><td>${esc(r.cr.etiqueta)}${["recurso","capacidad"].includes(r.k)?" <small>(de la grilla)</small>":""}</td><td><b>${f(r.cr,r.v)}</b> ${esc(r.cr.unidad)}${r.reparo?' <span class="tag-rep">fuera de límite</span>':""}</td><td>${f(r.cr,r.cr.limite)}</td><td>${f(r.cr,r.cr.bueno)}</td><td>${f(r.cr,r.cr.tope)}</td><td>${r.nota==null?"no puntúa":fmt0(r.nota)}</td><td>${r.peso!=null?fmt(r.peso,2):""}</td></tr>`).join("")}
    <tr class="total"><td colspan="5">Índice de aptitud del lote: promedio de las notas ponderado por el peso de cada criterio</td><td><b>${indice==null?"sin dato":fmt0(indice)}</b></td><td></td></tr></tbody></table>
    ${bloqueCriteriosBajoLimite(l)}
    <p class="idx-nota">Límite, bueno y tope son los percentiles 90, 50 y 10 medidos en los lotes donde están las plantas fotovoltaicas ya construidas del registro de XM; no son metas fijadas a criterio del consultor.</p>
    <p class="idx-nota">El criterio de cobertura del suelo se puntúa sobre una escala compuesta de este estudio, que es aquella sobre la que se midieron esos percentiles. Esa escala vive dentro del índice y no se publica como cifra del lote: la cobertura del lote se reporta clase a clase, con el porcentaje de ESA WorldCover, en el cuadro de cobertura del suelo de esta ficha.</p>
    <p class="idx-nota">El índice no clasifica el lote y no ordena la lista. La clase sale de las condiciones comprobadas sobre el polígono del lote, que se enumeran arriba con su trámite. El orden de la lista lo pone el área catastral del lote: el recurso solar y la capacidad de conexión se heredan de la grilla y son iguales para todos sus lotes, de modo que el índice apenas separa un lote de otro dentro de una misma grilla.</p>`;
}


// ---------- clase del lote y condiciones que la fijan ----------
// La clase la fija el análisis y viaja con el lote. Aquí no se recalcula, de modo que la
// lista, el mapa, la ficha y el reporte no puedan discrepar entre sí.
const CLASE_NOMBRES = ["Idóneo", "Viable con gestión", "No viable"];
const claseDe = l => CLASE_NOMBRES.includes(l.clasificacion) ? l.clasificacion : "Idóneo";

// Las condiciones comprobadas sobre el polígono del lote. Cada una llega con su código y
// con lo medido en ese lote; el enunciado, el trámite, la entidad y la fuente están
// escritos una sola vez en el catálogo y se vuelven a unir aquí.
function condicionesDe(l){
  return (l.condiciones || [])
    .map(([codigo, detalle]) => ({...(COND_DE[codigo] || {}), detalle}))
    .filter(c => c.condicion);
}

// Criterios del índice que quedaron por debajo de su límite de referencia. No cambian la
// clase del lote ni exigen trámite: describen una condición del sitio que encarece o
// condiciona la ingeniería.
function criteriosBajoLimite(l){
  return desgloseIndice(l).filas.filter(f => f.reparo).map(f => {
    const u = f.cr.unidad ? " " + f.cr.unidad : "";
    return {etiqueta: f.cr.etiqueta, valor: fmt(f.v, 1) + u, limite: fmt(f.cr.limite, 1) + u};
  });
}

// Bloque de la ficha: las condiciones del lote, una por una, con su trámite.
function bloqueCondiciones(l){
  const cs = condicionesDe(l);
  if(!cs.length)
    return `<div class="sin-reparos">Ninguna de las condiciones que este estudio comprueba se presenta en el lote. No hay suelo de protección, ni título minero vigente, ni área protegida, resguardo, consejo comunitario o páramo, ni área por encima de la Unidad Agrícola Familiar del municipio, ni inundación registrada en episodios de La Niña, ni microzona de restitución, ni humedal dentro del lote. El lote pasa directamente a la verificación del título.</div>`;
  const noV = cs.filter(c => c.clase === "No viable");
  const ges = cs.filter(c => c.clase !== "No viable");
  const tarjeta = (c, i, n, grave) => `<div class="reparo${grave ? " grave" : ""}">
      <span class="rk">${grave ? "Condición que ninguna gestión resuelve" : "Condición con trámite conocido"} ${i + 1} de ${n}</span>
      <b>${esc(c.condicion)}</b>
      ${c.detalle ? `<p><b>Lo que se midió en este lote.</b> ${esc(c.detalle)}</p>` : ""}
      ${c.tramite ? `<p><b>Qué exige.</b> ${esc(c.tramite)}</p>` : ""}
      ${c.entidad ? `<p><b>Ante quién se surte.</b> ${esc(c.entidad)}</p>` : ""}
      ${c.fuente ? `<p class="rf"><b>De dónde sale el dato.</b> ${esc(c.fuente)}</p>` : ""}</div>`;
  return `<div class="reparos">`
    + noV.map((c, i) => tarjeta(c, i, noV.length, true)).join("")
    + ges.map((c, i) => tarjeta(c, i, ges.length, false)).join("")
    + `</div>`
    + (noV.length
        ? `<p class="mini-nota">El lote se muestra en la lista y no se oculta, para dejar constancia de que fue evaluado y de por qué quedó fuera. Antes de descartarlo conviene pedir el documento que cada condición nombra: la cartografía publicada puede estar desactualizada y el certificado de la entidad es el que tiene valor legal.</p>`
        : `<p class="mini-nota">Ninguna de estas condiciones impide el proyecto. Todas añaden tiempo, costo o documentación, y cada una se levanta con el trámite que se indica.</p>`);
}

// Avisos que no bajan la clase del lote porque son huecos de la fuente y no defectos del
// terreno: la norma urbana sin cartografía publicada y las capas que no respondieron.
function bloqueAvisos(l){
  if(!l.advertencias) return "";
  return `<p class="aviso-fuente"><b>Lo que no se pudo verificar.</b> ${esc(l.advertencias)}</p>`;
}

// Criterios del índice por debajo de su límite, listados con su cifra. Van dentro del
// desglose del índice, no entre las condiciones: no exigen trámite ante ninguna entidad.
function bloqueCriteriosBajoLimite(l){
  const cs = criteriosBajoLimite(l);
  if(!cs.length)
    return `<p class="idx-nota">Ningún criterio del índice queda por debajo de su límite de referencia en este lote.</p>`;
  return `<p class="idx-nota"><b>Criterios del índice por debajo de su límite de referencia: ${cs.length}.</b> `
    + cs.map(c => `${esc(c.etiqueta.toLowerCase())}, ${esc(c.valor)} frente a un límite de ${esc(c.limite)}`).join("; ")
    + `. Cada uno recibe nota cero dentro del índice. No cambian la clase del lote ni exigen trámite ante ninguna entidad: describen una condición del sitio que encarece o condiciona la ingeniería.</p>`;
}

// Matrícula inmobiliaria del lote. O está el número, con la entidad y la fecha en que se
// obtuvo, o se dice que no está y por qué, y cómo se pide. Nunca se rellena con un
// aproximado. El mismo texto se usa en el visor y en la ficha imprimible.
function textoMatricula(l){
  if(l.matricula_inmobiliaria){
    const varias = String(l.matricula_inmobiliaria).includes(";");
    return `<b>Matrícula${varias?"s":""} inmobiliaria${varias?"s":""}: ${esc(l.matricula_inmobiliaria)}.</b>`
      + (l.matricula_fuente ? ` Obtenida en ${esc(String(l.matricula_fuente).replace(/\.$/,""))}` : "")
      + (l.matricula_fecha ? `, el ${fmtFecha(l.matricula_fecha)}` : "")
      + (l.matricula_fuente || l.matricula_fecha ? "." : "")
      + (varias ? " Un mismo número predial puede corresponder a varias matrículas, y hay que pedir el certificado de cada una." : "")
      + " Con ella se compra el certificado de tradición y libertad en el portal de la Superintendencia de Notariado y Registro.";
  }
  const consultado = l.matricula_motivo
    ? `<b>Matrícula inmobiliaria: sin dato.</b> Se consultó el índice de propietarios de la Superintendencia de Notariado y Registro${l.matricula_fecha?" el "+fmtFecha(l.matricula_fecha):""} y no devolvió folio: ${esc(String(l.matricula_motivo).replace(/\.$/,""))}. `
    : `<b>Matrícula inmobiliaria: sin dato.</b> El catastro no la publica y este lote todavía no se ha consultado una a una. `;
  return consultado
    + `Hay tres vías para obtenerla. La primera es el índice de propietarios de la Superintendencia de Notariado y Registro, que se consulta por referencia catastral`
    + (l.numero_predial_anterior ? `, con el número predial anterior <b>${esc(l.numero_predial_anterior)}</b>, que es el que suele figurar en el folio, y si no responde con el número predial de treinta dígitos` : ` con el número predial`)
    + `; requiere cuenta y admite un número limitado de consultas gratuitas al día. La segunda es la factura del impuesto predial en el portal de la alcaldía, que casi siempre trae la matrícula. La tercera, para una lista completa de lotes, es un derecho de petición ante la Superintendencia de Notariado y Registro: no tiene costo y la respuesta llega en diez días hábiles.`;
}

// Las cuatro verificaciones previas a la escritura del lote, enumeradas una a una.
function bloqueAdquisicion(l){
  const n = l.estorbos||0;
  if(!n) return `<p class="sin-reparos">Sin verificaciones previas a la escritura detectadas. Sin edificación mayor, cobertura boscosa por debajo del 10 por ciento, área catastral coherente con la geometría y destino económico declarado.</p>`;
  const detectadas = String(l.gestion||"").split(";").map(t => t.trim()).filter(Boolean);
  return `<p class="mini-nota">Verificaciones previas a la escritura detectadas: <b>${n}</b>. Añaden un permiso, un saneamiento documental o una negociación antes de poder comprar y construir. No cambian la clasificación del lote: la compra la decide el título.</p>
    <div class="cond-adq">${detectadas.map(t => `<div>${esc(t.charAt(0).toUpperCase()+t.slice(1))}</div>`).join("")}</div>`;
}

// Variables de la grilla medidas en el lote (GSA, OSM): recurso en el punto, línea y poblado.
// Definiciones de las capas del Global Solar Atlas (promedios anuales de largo plazo,
// modelo Solargis, resolución 250 m en el centroide del lote); se imprimen en la ficha.
const RECURSO_DEF = [
  ["ctx_pvout","PVOUT","kWh/kWp","Producción específica anual de una planta fotovoltaica de referencia (módulos c-Si en estructura fija al ángulo óptimo, pérdidas típicas). Es la cifra con la que se estima la energía del proyecto: MWp × PVOUT = MWh/año."],
  ["ctx_ghi","GHI","kWh/m²","Irradiación global horizontal anual: toda la energía solar que llega a una superficie horizontal (directa + difusa). Base de cualquier cálculo de recurso."],
  ["ctx_dni","DNI","kWh/m²","Irradiación normal directa anual: la que llega en línea recta desde el disco solar a una superficie perpendicular. Alta cuando el cielo es despejado; importa para seguidores y concentración."],
  ["ctx_dif","DIF","kWh/m²","Irradiación difusa horizontal anual: la dispersada por nubes y atmósfera. Alta en zonas nubosas y húmedas; reduce la ventaja de los seguidores."],
  ["ctx_gti","GTI","kWh/m²","Irradiación global sobre el plano inclinado al ángulo óptimo: lo que de verdad reciben los módulos fijos bien orientados. Siempre igual o mayor que GHI."],
  ["ctx_opta","OPTA","°","Ángulo de inclinación óptimo de los módulos fijos para maximizar la energía anual. Cerca del ecuador es bajo (5 a 12°)."],
  ["ctx_temp","TEMP","°C","Temperatura media anual del aire a 2 m. Cada grado por encima de 25 °C resta cerca de 0,4% de potencia a los módulos c-Si; en el Caribe explica parte de la diferencia entre GHI y PVOUT."],
  ["ctx_ele","ELE","m","Elevación del terreno en el punto según el modelo del GSA; contraste con la del DEM medida en el lote."],
  ["_pr","PR","adim.","Rendimiento del sistema = PVOUT / GTI: fracción de la irradiación sobre el plano que la planta de referencia convierte en energía. Resume todas las pérdidas (temperatura, suciedad, cableado, inversor); en el Caribe la temperatura es la mayor. Por eso la temperatura no es un criterio aparte del índice: ya está descontada en el PVOUT."],
];
function contexto(l){
  const c = celdaActual()||{};
  const pr = (l.ctx_pvout!=null && l.ctx_gti) ? l.ctx_pvout / l.ctx_gti : null;
  const out = RECURSO_DEF.map(([k,sig,u,d]) => [`${sig}`, k==="_pr" ? (pr!=null ? fmt(pr,2)+" (pérdidas "+fmt0((1-pr)*100)+" %)" : "sin dato") : l[k]!=null ? fmt(l[k], k==="ctx_temp"?1:0)+" "+u + (k==="ctx_pvout"&&c.pvout!=null?" (grilla "+fmt0(c.pvout)+")":"") : "sin dato"]);
  out.push(["Línea de transmisión más cercana", l.ctx_linea_km!=null?fmt(l.ctx_linea_km,1)+" km"+(l.ctx_linea_kv?", de "+l.ctx_linea_kv+" kV":""):"sin dato"]);
  out.push(["Centro poblado más cercano", l.ctx_poblado?`${l.ctx_poblado} (${({city:"ciudad",town:"pueblo",village:"corregimiento"})[l.ctx_poblado_tipo]||l.ctx_poblado_tipo}), a ${fmt(l.ctx_poblado_km,1)} km`:"sin dato"]);
  out.push(["Caserío más cercano", l.ctx_caserio?`${l.ctx_caserio}, a ${fmt(l.ctx_caserio_km,1)} km`:"sin dato"]);
  out.push(["Excedente de lluvia en una Niña típica", l.ent_nina_precip ? String(l.ent_nina_precip)+" % de lo normal" : "sin dato"]);
  out.push(["Alteración de la lluvia en un Niño típico", l.ent_nino_precip ? String(l.ent_nino_precip)+" % de lo normal en temporada lluviosa" : "sin dato"]);
  out.push(["Periodo de retorno de la sequía meteorológica", l.ent_sequia_retorno ? String(l.ent_sequia_retorno)+" años" : "sin dato"]);
  return out;
}
function definicionesRecurso(){
  return `<div class="jur">${RECURSO_DEF.map(([k,sig,u,d])=>`<div class="fila"><div class="sem gris"></div><div><b>${sig} (${u})</b><br><span>${d}</span></div></div>`).join("")}</div>`;
}
function bloqueValor(l){
  if(l.valor_ref_cop_ha==null) return `<div class="valor sin"><b>Valor de referencia</b><span>sin zona geoeconómica del IGAC para este lote (${esc(l.ant_banda||"sin dato ANT")}).</span></div>`;
  const conf = l.valor_confianza||"sin dato";
  return `<div class="valor ${conf}"><div class="v-cab"><b>Valor catastral de referencia</b><span class="v-conf">confianza ${conf}</span></div>
    <div class="v-num">${fmtM(l.valor_ref_cop_ha)}<small>/ha</small> <em>·</em> ${fmtM(l.valor_ref_cop)}<small> total, ${fmt0(l.area_ha)} ha</small></div>
    <div class="v-det">IGAC 2026, ponderado por área: ${fmtZonas(l.zonas_economicas)}${l.valor_ref_cobertura!=null&&l.valor_ref_cobertura<0.95?` (cubre ${fmt0(l.valor_ref_cobertura*100)}% del área)`:""}. Contraste ANT municipal: ${esc(l.ant_banda||"sin dato")}.</div>
    <div class="v-nota">Es avalúo catastral, no precio de mercado; en municipios con catastro desactualizado queda muy por debajo del comercial. Para negociar, la banda ANT y los comparables del entorno.</div></div>`;
}
// Cada clase lleva tres códigos: color, glifo y nombre escrito. Ninguno va solo.
const CLASE_CSS = {"Idóneo":"c1", "Viable con gestión":"c2", "No viable":"c3"};
const CLASE_GLIFO = {"Idóneo":"●", "Viable con gestión":"◆", "No viable":"▲"};
const claseCss = c => CLASE_CSS[c] || "c4";
const pastilla = c => `<span class="pill ${claseCss(c)}"><span class="gl">${CLASE_GLIFO[c]||"○"}</span>${esc(c)}</span>`;
const esc = s => String(s??"").replace(/[&<>"]/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));

// ---------- geometría a SVG ----------
function anillos(geom){
  if(!geom) return [];
  if(geom.type==="Polygon") return geom.coordinates;
  if(geom.type==="MultiPolygon") return geom.coordinates.flat();
  return [];
}
function pathDe(geom, proy){
  return anillos(geom).map(r => "M" + r.map(p => { const q=proy(p); return q[0].toFixed(1)+" "+q[1].toFixed(1); }).join("L") + "Z").join("");
}
function proyector(bbox, W, H, margen=0.04){
  const [x0,y0,x1,y1] = bbox;
  const dx=(x1-x0)*margen, dy=(y1-y0)*margen;
  const bx0=x0-dx, by0=y0-dy, bx1=x1+dx, by1=y1+dy;
  const k = Math.min(W/(bx1-bx0), H/((by1-by0)*Math.cos((y0+y1)/2*Math.PI/180)) );
  const kx = k, ky = k*Math.cos((y0+y1)/2*Math.PI/180);
  const ox = (W - (bx1-bx0)*kx)/2, oy = (H - (by1-by0)*ky)/2;
  return p => [ox + (p[0]-bx0)*kx, oy + (by1-p[1])*ky];
}

// ---------- estado ----------
function celdaActual(){ return D.celdas.find(c => c.cell_id===CELDA); }
function lotesCelda(){ return (D.lotes[PERFIL]||[]).filter(l => l.cell_id===CELDA); }
const num = v => { const x = parseFloat(v); return Number.isFinite(x) ? x : null; };
// Clases de cobertura del suelo de ESA WorldCover, con el nombre con que se escriben.
// Se describen una a una y con la cifra de la capa: aquí no se combina ninguna con otra.
const CLASES_COB = [["cob_pastizal_pct","pastizal"],["cob_bosque_pct","bosque"],
  ["cob_cultivo_pct","cultivo"],["cob_matorral_pct","matorral"],
  ["cob_construido_pct","suelo construido"],["cob_desnudo_pct","suelo desnudo"],
  ["cob_humedal_pct","humedal herbáceo"],["cob_agua_pct","agua permanente"],
  ["cob_manglar_pct","manglar"],["cob_nieve_pct","nieve y hielo"],
  ["cob_musgo_pct","musgo y liquen"]];
// Clases presentes en el lote, de mayor a menor porcentaje; `minimo` deja fuera las trazas.
function coberturaDe(l, minimo=0){
  return CLASES_COB.map(([c,nom]) => [l[c], nom])
    .filter(([v]) => v!=null && Number.isFinite(Number(v)) && Number(v) > minimo)
    .sort((a,b) => b[0]-a[0]);
}
// Composición en una línea: «pastizal 63 %, bosque 36 %». Vacía si el lote no tiene medida.
function composicionCobertura(l, minimo=1, maximo=3){
  const c = coberturaDe(l, minimo);
  return c.length ? c.slice(0,maximo).map(([v,nom]) => `${nom} ${fmt0(v)} %`).join(", ") : "";
}
function leerFiltro(){
  for(const u of UMBRALES){ const e = $("#"+u.id); if(e) V[u.id] = num(e.value); }
  for(const c of CASILLAS){ const e = $("#"+c.id); if(e) C[c.id] = e.checked; }
}
function escribirFiltro(){
  for(const u of UMBRALES){ const e = $("#"+u.id); if(e) e.value = V[u.id] ?? ""; }
  for(const c of CASILLAS){ const e = $("#"+c.id); if(e) e.checked = !!C[c.id]; }
}
// Un umbral solo retira lotes con dato: la ausencia de dato no es un incumplimiento.
function pasaUmbral(l, u){
  const v = V[u.id]; if(v==null) return true;
  const x = campoDe(l, u.campo); if(x==null || !Number.isFinite(Number(x))) return true;
  return u.dir==="max" ? Number(x) <= v : Number(x) >= v;
}
// Reglas de la banda de criterios; `salvo` deja una fuera para medir cuánto retira ella sola.
function pasaCriterios(l, salvo){
  for(const u of UMBRALES){ if(u.id!==salvo && !pasaUmbral(l, u)) return false; }
  for(const c of CASILLAS){ if(c.id!==salvo && C[c.id] && PRUEBAS[c.id] && PRUEBAS[c.id](l)) return false; }
  return true;
}
// La clasificación describe el resultado: es faceta de la lista, no regla de descarte.
const pasaClase = l => !!CLASES[claseDe(l)];
const GRAVEDAD_POT = {rojo:0, ambar:1, gris:2, verde:3};
function claveOrden(l, k){
  if(k==="pot") return GRAVEDAD_POT[l.pot_semaforo] ?? 2;
  if(k==="agua") return l.ent_inundacion_ha_max ?? (l.ent_inundaciones_nina>0 ? null : 0);
  return l[k] ?? null;
}
const desempate = (a,b) => String(a.CODIGO).localeCompare(String(b.CODIGO));
function ordenarLotes(ls){
  return ls.slice().sort((a,b)=>{
    const va = claveOrden(a, ORD.clave), vb = claveOrden(b, ORD.clave);
    if(va==null && vb==null) return desempate(a,b);
    if(va==null) return 1;
    if(vb==null) return -1;
    if(va!==vb) return (va<vb ? -1 : 1) * ORD.dir;
    return desempate(a,b);
  });
}
function lotesFiltrados(){
  return ordenarLotes(lotesCelda().filter(l => pasaCriterios(l) && pasaClase(l)));
}
// Preajustes: el proyecto de cada perfil (área y ancho mínimos) o cualquier tamaño.
function preajustes(){
  const out = PERFILES.map(p => ({id:p, texto:`Desde ${fmt0(D.perfiles[p].ha_proyecto)} ha y ${fmt0(D.perfiles[p].ancho_minimo_m)} m de ancho`, sub:D.perfiles[p].etiqueta.split(",")[0], haMin:D.perfiles[p].ha_proyecto, anchoMin:D.perfiles[p].ancho_minimo_m}));
  out.push({id:"todos", texto:"Sin restricción de tamaño", sub:`desde ${fmt0(D.ha_minima)} ha, el mínimo de caracterización`, haMin:0, anchoMin:0});
  return out;
}
function aplicarPreajuste(id){
  const pr = preajustes().find(x=>x.id===id); if(!pr) return;
  V["f-ha-min"] = pr.haMin || null; V["f-ha-max"] = null;
  V["f-ancho"] = pr.anchoMin || null; F.preajuste = id;
  escribirFiltro(); refrescar();
}
// Un solo punto de repintado, para que criterios, faceta y orden no se desincronicen.
function refrescar(){ pintarCriterios(); pintarTabla(); pintarMapa(); }

// Criterios aplicados, cada uno con el enunciado con el que se lee en la pastilla.
const _limpiaRotulo = t => String(t).replace(/ \((máximo|mínimo)\)$/, "").replace(/, como (máximo|mínimo)$/, "");
function reglasActivas(){
  const r = [];
  for(const u of UMBRALES){
    if(V[u.id]==null) continue;
    const rel = u.dir==="max" ? "como máximo" : "como mínimo";
    r.push({id:u.id, txt:`${_limpiaRotulo(u.etiqueta)}: ${rel} ${fmt(V[u.id], Math.abs(V[u.id])<10 ? 2 : 0)} ${u.unidad}`});
  }
  for(const c of CASILLAS){ if(C[c.id]) r.push({id:c.id, txt:c.etiqueta}); }
  return r;
}
function pintarCriterios(){
  const todos = lotesCelda();
  $("#preajustes").innerHTML = preajustes().map(pr => {
    const n = todos.filter(l => (l.area_ha??0) >= pr.haMin && (l.ancho_util_m==null || l.ancho_util_m >= pr.anchoMin)).length;
    return `<button class="pre ${F.preajuste===pr.id?"on":""}" data-p="${pr.id}">${esc(pr.texto)} <small>· ${esc(pr.sub)} · ${n} lote${n===1?"":"s"}</small></button>`;
  }).join("");
  $("#preajustes").querySelectorAll(".pre").forEach(b => b.onclick = () => aplicarPreajuste(b.dataset.p));
  // El campo del criterio aplicado se destaca; el que no lo está queda neutro.
  for(const u of UMBRALES){ const caja = $("#c-"+u.id.slice(2)); if(caja) caja.classList.toggle("act", V[u.id]!=null); }
  const reglas = reglasActivas(), n = lotesFiltrados().length, total = todos.length;
  $("#cri-pastillas").innerHTML = reglas.length
    ? reglas.map(r=>`<span class="cri-chip ${n===0?"cero":""}" data-r="${esc(r.id)}">${esc(r.txt)}<button data-q="${esc(r.id)}" title="Retirar este criterio" aria-label="Retirar el criterio ${esc(r.txt)}">✕</button></span>`).join("")
    : `<span class="cri-ninguno">Sin criterios aplicados: se muestran los ${total} lotes caracterizados de la grilla</span>`;
  $("#cri-pastillas").querySelectorAll("button[data-q]").forEach(b => b.onclick = () => quitarRegla(b.dataset.q));
  $("#cri-contador").textContent = `${n} de ${total} lotes cumplen los criterios aplicados`;
  $("#cri-resumen").innerHTML = reglas.length
    ? `<b>${reglas.length}</b> criterio${reglas.length===1?"":"s"} aplicado${reglas.length===1?"":"s"} sobre los <b>${total}</b> lotes caracterizados de esta grilla; <b class="${n?"":"cri-vacio"}">${n}</b> los cumplen todos.`
    : `Ningún criterio aplicado. Se muestran los <b>${total}</b> lotes caracterizados de esta grilla.`;
  $("#f-ayuda").textContent = `Esta grilla trae ${total} lotes caracterizados, de ${fmt0(D.ha_minima)} hectáreas o más. Solo quedan fuera de esta lista los lotes de la capa urbana del catastro, los de destino habitacional declarado y los que no alcanzan el mínimo de superficie. El título minero vigente y las figuras territoriales ya no retiran el lote: lo dejan No viable, con su ficha y el motivo escrito. El tamaño no descarta: acota la búsqueda al proyecto que se quiere construir. La clasificación del lote describe el resultado y tampoco descarta.`;
}
// El aspa de cada pastilla retira ese criterio solo, sin tocar los demás.
function quitarRegla(id){
  if(UMBRALES.some(u => u.id===id)){ V[id] = null; if(["f-ha-min","f-ha-max","f-ancho"].includes(id)) F.preajuste = null; }
  else C[id] = false;
  escribirFiltro(); refrescar();
}

// ---------- pintar ----------
function pintarControles(){
  $("#seg-perfil").innerHTML = PERFILES.map(p => `<button data-p="${p}" class="${p===PERFIL?"on":""}">${esc(D.perfiles[p].etiqueta.split(",")[0])}</button>`).join("");
  $("#seg-perfil").querySelectorAll("button").forEach(b => b.onclick = () => { PERFIL=b.dataset.p; LOTE=null; F.preajuste=PERFIL; const pr=preajustes().find(x=>x.id===PERFIL); V["f-ha-min"]=pr.haMin||null; V["f-ancho"]=pr.anchoMin||null; V["f-ha-max"]=null; for(const k in CLASES) CLASES[k]=true; escribirFiltro(); pintarTodo(); });
  const sel = $("#sel-celda");
  const orden = [...D.celdas].sort((a,b)=>(a.ranking??999)-(b.ranking??999));
  sel.innerHTML = orden.map(c => {
    const n = (D.lotes[PERFIL]||[]).filter(l=>l.cell_id===c.cell_id).length;
    return `<option value="${c.cell_id}" ${c.cell_id===CELDA?"selected":""}>${c.ranking!=null?"#"+c.ranking+" · ":""}${c.cell_id} · ${esc(c.municipio||"")} · ${n?n+" lote"+(n===1?"":"s"):"sin lotes caracterizados en esta grilla"}</option>`;
  }).join("");
  sel.onchange = () => { CELDA=sel.value; LOTE=null; pintarTodo(); };
  // Una sola grilla, como en el piloto, pide el singular: "1 grillas" se lee como fallo.
  const nCel = D.celdas.length;
  $("#origen").textContent = `${nCel} ${nCel === 1 ? "grilla" : "grillas"} del archivo cargado · datos del ${fmtFecha(D.generado)}`;
}

// Encuadre = unión de la grilla y sus lotes; un lote grande puede sobresalir un ancho
// de celda entero y encuadrar solo la celda lo cortaría.
function bboxUnion(c, lotes){
  let [x0,y0,x1,y1] = c.bbox;
  for(const l of lotes){ x0=Math.min(x0,l.bbox[0]); y0=Math.min(y0,l.bbox[1]); x1=Math.max(x1,l.bbox[2]); y1=Math.max(y1,l.bbox[3]); }
  return [x0,y0,x1,y1];
}

// Qué parte de la red eléctrica consultada cae dentro del recuadro que se dibuja. El
// recuadro es la unión de la grilla y sus lotes; la consulta abarca un entorno mayor, así
// que lo que queda fuera no se dibuja y la leyenda no lo puede anunciar como visible.
function dentroDelRecuadro(bbox, p){
  return p[0] >= bbox[0] && p[0] <= bbox[2] && p[1] >= bbox[1] && p[1] <= bbox[3];
}
// Un tramo entra en el recuadro si tiene un vértice dentro o si alguno de sus segmentos
// lo cruza. El cruce se resuelve con códigos de región, que es la prueba exacta.
function codigo(bbox, p){
  return (p[0] < bbox[0] ? 1 : 0) | (p[0] > bbox[2] ? 2 : 0)
       | (p[1] < bbox[1] ? 4 : 0) | (p[1] > bbox[3] ? 8 : 0);
}
function segmentoEntra(bbox, a, b){
  let ca = codigo(bbox, a), cb = codigo(bbox, b);
  let [x0, y0] = a, [x1, y1] = b;
  for(let i = 0; i < 8; i++){
    if(!(ca | cb)) return true;
    if(ca & cb) return false;
    const c = ca || cb;
    let x, y;
    if(c & 8){ x = x0 + (x1 - x0) * (bbox[3] - y0) / (y1 - y0); y = bbox[3]; }
    else if(c & 4){ x = x0 + (x1 - x0) * (bbox[1] - y0) / (y1 - y0); y = bbox[1]; }
    else if(c & 2){ y = y0 + (y1 - y0) * (bbox[2] - x0) / (x1 - x0); x = bbox[2]; }
    else { y = y0 + (y1 - y0) * (bbox[0] - x0) / (x1 - x0); x = bbox[0]; }
    if(c === ca){ x0 = x; y0 = y; ca = codigo(bbox, [x0, y0]); }
    else { x1 = x; y1 = y; cb = codigo(bbox, [x1, y1]); }
  }
  return false;
}
function redVisible(c, bbox){
  const r = c.red || {};
  const lineas = (r.lineas||[]).filter(t => {
    const cs = t.coords || [];
    for(let i = 1; i < cs.length; i++) if(segmentoEntra(bbox, cs[i-1], cs[i])) return true;
    return false;
  });
  return {lineas,
          subestaciones: (r.subestaciones||[]).filter(x => dentroDelRecuadro(bbox, x.punto)),
          plantas: (r.plantas||[]).filter(x => dentroDelRecuadro(bbox, x.punto))};
}

// Red eléctrica sobre la grilla: líneas de transmisión que la cruzan, subestaciones y
// plantas de generación registradas dentro de ella o en su entorno inmediato.
function capaRed(c, proy, vis){
  const r = vis || c.red; if(!r) return "";
  const lineas = (r.lineas||[]).map(t => {
    const d = "M" + t.coords.map(q => { const v = proy(q); return v[0].toFixed(1)+" "+v[1].toFixed(1); }).join("L");
    return `<path class="linea-halo" d="${d}"/><path class="linea" d="${d}"><title>Línea de transmisión${t.kv?" de "+fmt0(t.kv)+" kV":""}</title></path>`;
  }).join("");
  const subs = (r.subestaciones||[]).map(x => {
    const [px,py] = proy(x.punto);
    return `<g><circle class="sub-punto" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="6"><title>Subestación ${esc(x.nombre||"")}${x.kv?" · "+fmt0(x.kv)+" kV":""}${x.operador?" · "+esc(x.operador):""}</title></circle>`
         + `<text class="red-rot" x="${(px+9).toFixed(1)}" y="${(py+4).toFixed(1)}">${esc(x.nombre||"subestación")}</text></g>`;
  }).join("");
  const plantas = (r.plantas||[]).map(x => {
    const [px,py] = proy(x.punto);
    return `<g><rect class="planta-punto" x="${(px-5).toFixed(1)}" y="${(py-5).toFixed(1)}" width="10" height="10" transform="rotate(45 ${px.toFixed(1)} ${py.toFixed(1)})"><title>${esc(x.nombre||"")}${x.mw!=null?" · "+fmt(x.mw,2)+" MW":""}${x.estado?" · "+esc(x.estado):""}</title></rect></g>`;
  }).join("");
  return `<g class="red">${lineas}${plantas}${subs}</g>`;
}

function leyendaMapa(c, vis){
  const r = c.red || {lineas:[], subestaciones:[], plantas:[]};
  const v = vis || {lineas:r.lineas||[], subestaciones:r.subestaciones||[], plantas:r.plantas||[]};
  const clases = CAT_CLASES.map(x => `<span><i style="background:var(--mapa-${x.clase==="Idóneo"?"idoneo":x.clase==="No viable"?"noviable":"gestion"}); opacity:.75"></i>${esc(x.clase)} (${esc(x.color)})</span>`).join("");
  const nL = v.lineas.length, nS = v.subestaciones.length, nP = v.plantas.length;
  const fuera = (r.lineas||[]).length - nL + (r.subestaciones||[]).length - nS + (r.plantas||[]).length - nP;
  const nota = fuera
    ? `<span class="sinred">Hay ${fuera} elemento${fuera===1?"":"s"} más de la red eléctrica en el entorno de la grilla, fuera del recuadro del mapa; se describen debajo.</span>`
    : "";
  const red = nL+nS+nP
    ? [nL ? `<span><i style="background:var(--mapa-red); border:1px solid #141A1A"></i>Línea de transmisión</span>` : "",
       nS ? `<span><i style="background:var(--mapa-sub); border-radius:50%"></i>Subestación</span>` : "",
       nP ? `<span><i style="background:var(--mapa-planta); transform:rotate(45deg)"></i>Planta de generación registrada</span>` : "",
       nota].filter(Boolean).join("")
    : ((r.lineas||[]).length + (r.subestaciones||[]).length + (r.plantas||[]).length
        ? `<span class="sinred">Ninguna línea de transmisión, subestación ni planta de generación del inventario entra en el recuadro de este mapa. Las que hay en el entorno de la grilla se describen debajo.</span>`
        : `<span class="sinred">Ninguna línea de transmisión, subestación ni planta de generación del inventario cruza esta grilla ni su entorno de ${fmt(D.margen_red_km||0,0)} km.</span>`);
  return `<span class="leyenda-tit">Clasificación del lote</span>${clases}
    <span><i style="border:1.5px dashed var(--marca); background:transparent"></i>Perímetro de la grilla</span>
    <span><i style="background:var(--mapa-idoneo); opacity:.18"></i>Lote fuera de los criterios aplicados</span>
    <span class="leyenda-tit">Red eléctrica</span>${red}`;
}

function textoRed(c){
  const r = c.red; if(!r) return "";
  const kvs = [...new Set((r.lineas||[]).map(t => t.kv).filter(v => v!=null))].sort((a,b)=>b-a);
  const partes = [];
  if((r.lineas||[]).length)
    partes.push(`<b>${(r.lineas||[]).length} tramo${(r.lineas||[]).length===1?"":"s"} de línea de transmisión</b> ${kvs.length?"de "+kvs.map(v=>fmt0(v)+" kV").join(", "):"sin tensión declarada"}${(r.lineas||[]).some(t=>t.dentro)?", uno de ellos dentro de la grilla":", ninguno dentro de la grilla"}.`);
  for(const x of (r.subestaciones||[]))
    partes.push(`<b>Subestación ${esc(x.nombre||"sin nombre")}</b>${kvSuelto(x.nombre, x.kv)?", "+kvSuelto(x.nombre, x.kv):""}${x.operador?", operada por "+esc(x.operador):""}${x.dentro?", dentro de la grilla":", en el entorno de la grilla"}.`);
  for(const x of (r.plantas||[]))
    partes.push(`<b>${esc(x.nombre||"planta sin nombre")}</b>${x.mw!=null?", "+fmt(x.mw,2)+" MW":""}${x.tipo?", "+esc(String(x.tipo).toLowerCase()):""}${x.estado?", "+esc(String(x.estado).toLowerCase()):""}${x.dentro?", dentro de la grilla":", en el entorno de la grilla"}.`);
  const sub = c.sub_nombre_subestacion
    ? `Subestación de conexión asignada a esta grilla: <b>${esc(c.sub_nombre_subestacion)}</b>${kvSuelto(c.sub_nombre_subestacion, c.sub_tension_kv)?", "+kvSuelto(c.sub_nombre_subestacion, c.sub_tension_kv):""}${c.operador?", operador de red "+esc(c.operador):""}${c.sub_distancia_km!=null?", a "+fmt(c.sub_distancia_km,1)+" km del centro de la grilla":""}.`
    : "";
  if(!partes.length)
    return `<p style="margin:0">Ninguna línea de transmisión, subestación ni planta de generación del inventario cae dentro de esta grilla ni en los ${fmt(D.margen_red_km||0,0)} km de su entorno. ${sub}</p>`;
  return `<p style="margin:0">${partes.join(" ")} ${sub}</p>`;
}

function pintarMapa(){
  const c = celdaActual(); if(!c) return;
  const W=760, H=760;
  const lotes = lotesCelda(), filtrados = new Set(lotesFiltrados().map(l=>l.CODIGO));
  const enc = bboxUnion(c, lotes);
  const proy = proyector(enc, W, H);
  // El proyector añade un margen del 4 % al encuadre; el recuadro que de verdad se ve es
  // ese, y es contra él contra el que se decide qué red se dibuja y qué anuncia la leyenda.
  const mx = (enc[2]-enc[0])*0.04, my = (enc[3]-enc[1])*0.04;
  const vis = redVisible(c, [enc[0]-mx, enc[1]-my, enc[2]+mx, enc[3]+my]);
  // Cada lote se dibuja dos veces: un halo blanco debajo sostiene el lindero sobre la
  // foto y encima va el relleno semitransparente del color de su clase.
  const halos = lotes.map(l => `<path class="halo ${filtrados.has(l.CODIGO)?"":"atenuado"}" d="${pathDe(l.geom,proy)}"/>`).join("");
  const paths = lotes.map(l => { const k = claseDe(l);
    return `<path class="lote ${claseCss(k)} ${l.CODIGO===LOTE?"sel":""} ${filtrados.has(l.CODIGO)?"":"atenuado"}" data-c="${l.CODIGO}" d="${pathDe(l.geom,proy)}"><title>${esc(l.municipio)} · ${fmt0(l.area_ha)} ha de área catastral · ${esc(composicionCobertura(l)||"cobertura sin dato")} · ${esc(k)}</title></path>`;
  }).join("");
  // Fondo: la imagen satelital de la grilla, colocada por su bbox en el mismo proyector.
  let fondo = "";
  if (c.sat && FONDO_SAT) {
    const [x0,y0,x1,y1] = c.sat.bbox, a = proy([x0,y1]), b = proy([x1,y0]);
    fondo = `<image href="${c.sat.src}" x="${a[0].toFixed(1)}" y="${a[1].toFixed(1)}" width="${(b[0]-a[0]).toFixed(1)}" height="${(b[1]-a[1]).toFixed(1)}" preserveAspectRatio="none" opacity=".92"/>`;
  }
  $("#mapa-caja").innerHTML = `<svg class="mapa ${fondo?"con-fondo":""}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Lotes de la grilla ${c.cell_id} sobre imagen satelital, con la red eléctrica del entorno">
    ${fondo}<path class="celda" d="${pathDe(c.geom,proy)}"/>${halos}${paths}${RED_SAT?capaRed(c,proy,vis):""}</svg>
    <div class="fondo-toggle">
      ${c.sat ? `<label><input type="checkbox" id="chk-fondo" ${FONDO_SAT?"checked":""}> Imagen satelital de alta resolución${c.sat.fecha?", captura del "+fmtFecha(c.sat.fecha):""}</label>` : ""}
      <label><input type="checkbox" id="chk-red" ${RED_SAT?"checked":""}> Red eléctrica</label>
    </div>`;
  const chk = $("#chk-fondo"); if (chk) chk.onchange = () => { FONDO_SAT = chk.checked; pintarMapa(); };
  const chkr = $("#chk-red"); if (chkr) chkr.onchange = () => { RED_SAT = chkr.checked; pintarMapa(); };
  $("#mapa-caja").querySelectorAll(".lote").forEach(p => p.onclick = () => { LOTE=p.dataset.c; pintarTabla(); pintarMapa(); pintarDetalle(); });
  $("#celda-titulo").textContent = `${c.cell_id} · ${c.municipio||""}${c.vereda?" · "+c.vereda:""}`;
  $("#leyenda").innerHTML = leyendaMapa(c, vis);
  $("#red-lista").innerHTML = textoRed(c);
  const cap = (PERFIL==="distribuida" ? c.capacidad_mt_mw : c.capacidad_at_mw);
  const datos = [
    ["Clasificación de la grilla", c.clasificacion],
    ["Índice de aptitud de la grilla, sobre 100", fmt(c.indice_aptitud,1)],
    ["Posición en el orden de prioridad", c.ranking!=null?"#"+c.ranking:"sin dato"],
    ["Agrupación geográfica de grillas", c.zona||"sin dato"],
    ["Departamento", c.departamento||"sin dato"],
    ["Subestación de conexión", c.sub_nombre_subestacion ? c.sub_nombre_subestacion + (kvSub(c)?" · "+kvSub(c):"") : "sin dato"],
    ["Distancia del centro de la grilla a la subestación de conexión", c.sub_distancia_km!=null?fmt(c.sub_distancia_km,1)+" km":"sin dato"],
    ["Operador de red de la subestación", c.operador||"sin dato"],
    ["Producción fotovoltaica específica anual", c.pvout!=null?fmt0(c.pvout)+" kWh/kWp":"sin dato"],
    ["Capacidad de conexión disponible en la subestación", cap!=null?fmt(cap,1)+" MW":"sin dato"],
    ["Cobertura del catastro público del IGAC en la grilla", c.catastro_pct!=null?fmt0(c.catastro_pct)+" % de la grilla":"sin dato"],
  ];
  $("#celda-datos").innerHTML = datos.map(([k,v])=>`<div class="cd"><div class="k">${k}</div><div class="v">${esc(v)}</div></div>`).join("")
    + (c.catastro_pct!=null && c.catastro_pct < 60 ? `<div class="cd aviso-cat">El catastro público del IGAC solo cubre el ${fmt0(c.catastro_pct)} % de esta grilla. ${c.gestor_catastral && !/igac/i.test(c.gestor_catastral) ? "El catastro de "+esc(c.municipio||"este municipio")+" lo lleva <b>"+esc(c.gestor_catastral)+"</b> y no está en el servicio abierto del IGAC: esos lotes se piden a ese gestor o se consultan por matrícula ante la Superintendencia de Notariado y Registro." : "El resto no está en el servicio abierto del IGAC. Los lotes que faltan existen, pero no se pueden caracterizar con datos abiertos."}</div>` : "");
}

// Tabla de resultados. El encabezado de cada columna declara la fuente o la magnitud;
// las columnas ordenables cambian la clave de orden de la lista.
// Rótulo corto de la superficie del lote en categorías de protección del ordenamiento.
const POT_TXT = {rojo:"protección sobre la mitad o más", ambar:"protección parcial",
                 verde:"sin suelo de protección", gris:"sin cartografía publicada"};
const COLS_TABLA = [
  {t:"#",               orden:null,                 extra:false, cls:"t-n",    cel:(l,i)=>`${i+1}`},
  {t:"Lote",            orden:null,                 extra:false, cls:"t-lote", cel:l=>`<b>${esc(l.municipio||"")}</b> ${pastilla(claseDe(l))}<small>${esc(l.nombre_predio||"sin nombre en el catastro")}</small><small class="cod">${esc(l.CODIGO)}</small>${l.matricula_inmobiliaria?`<small class="cod">matrícula ${esc(l.matricula_inmobiliaria)}</small>`:""}`},
  {t:"Área catastral del lote", orden:"area_ha", extra:false, dir:-1, cel:l=>`<b>${fmt(l.area_ha,1)}</b> ha<small>${fmt(l.mwp_lote,1)} MWp indicativos</small>`},
  {t:"Composición de la cobertura del suelo", orden:null, extra:false, cls:"t-cob", cel:l=>{
    const c = coberturaDe(l, 0.5);
    if(!c.length) return "sin dato";
    return c.slice(0,4).map(([v,nom]) => `<span class="cob-cl">${esc(nom)} <b>${fmt0(v)} %</b></span>`).join("");
  }},
  {t:"Diámetro del mayor círculo inscrito", orden:"ancho_util_m",    extra:true,  dir:-1, cel:l=>`${fmt0(l.ancho_util_m)} m`},
  {t:"Pendiente media", orden:"pendiente_media",    extra:true,  dir:1,  cel:l=>`${fmt(l.pendiente_media,1)}°`},
  {t:"Valor catastral de referencia", orden:"valor_ref_cop", extra:true, dir:1, cel:l=>l.valor_ref_cop==null?"sin dato":fmtM(l.valor_ref_cop)+"$"},
  {t:"Suelo de protección en el ordenamiento", orden:"pot",  extra:false, dir:1,  cel:l=>`<i class="pot-dot ${l.pot_semaforo||"gris"}"></i>${POT_TXT[l.pot_semaforo]||"sin cartografía publicada"}${l.pot_rojo_pct?`<small>${fmt(l.pot_rojo_pct,1)} % del lote</small>`:""}`},
  {t:"Verificaciones previas a la escritura", orden:"estorbos", extra:true, dir:1,  cel:l=>`${l.estorbos??0}`},
  // Sin UAF publicada no cabe decir "dentro del tope": no hay tope contra el que medir.
  {t:"Relación con la UAF municipal", orden:"veces_uaf", extra:true, dir:1, cel:l=>l.riesgo_baldio?`<b class="mal">supera el tope ${fmt(l.veces_uaf,1)} veces</b>`:(l.uaf_max_ha==null?"sin UAF publicada":"dentro del tope")},
  {t:"Inundación en episodios de La Niña", orden:"agua", extra:true, dir:1, cel:l=>(l.ent_inundaciones_nina||0)===0?"sin episodios":`${l.ent_inundaciones_nina} de 6<small>hasta ${fmt(l.ent_inundacion_ha_max,1)} ha</small>`},
];
// Nota al pie de la tabla: lo que un encabezado de una línea no puede decir.
const NOTA_TABLA = "Área catastral del lote: superficie del polígono que registra el IGAC; ordena la lista. Potencia instalable indicativa: esa misma área entre 1,5 hectáreas por megavatio pico, huella de referencia de ingeniería para planta en suelo con seguidor de un eje que no publica ninguna entidad colombiana. Composición de la cobertura del suelo: porcentaje del lote en cada clase de ESA WorldCover 2021, de mayor a menor y tal como la publica la capa, hasta cuatro clases; el resto de las clases del lote va en la ficha. Diámetro del mayor círculo inscrito: diámetro del mayor círculo inscrito en el lote. Valor catastral de referencia: avalúo del IGAC ponderado por área, no precio de mercado.";
function pintarTabla(){
  const ls = lotesFiltrados(), col = COLS_TABLA.find(c=>c.orden===ORD.clave);
  $("#lotes-conteo").textContent = `${ls.length} de ${lotesCelda().length}`;
  $("#res-orden").innerHTML = `<b>${ls.length}</b> lote${ls.length===1?"":"s"} · ordenados por <b>${esc((col||COLS_TABLA[2]).t.toLowerCase())}</b>, de ${ORD.dir<0?"mayor a menor":"menor a mayor"}`;
  pintarFacetas();
  if(!ls.length){ $("#lista").innerHTML = `<div class="vacio">Ningún lote de esta grilla cumple los criterios aplicados. Amplíe el rango de área o de ancho, restablezca todos los criterios, o vuelva a incluir alguna de las tres clases en la lista.</div>`; return; }
  const th = COLS_TABLA.map(c => {
    if(!c.orden) return `<th class="${c.extra?"col-extra":""}"><span>${esc(c.t)}</span></th>`;
    const act = ORD.clave===c.orden;
    return `<th class="${c.extra?"col-extra":""}" ${act?`aria-sort="${ORD.dir<0?"descending":"ascending"}"`:""}><button data-o="${c.orden}">${esc(c.t)}${act?(ORD.dir<0?" ↓":" ↑"):""}</button></th>`;
  }).join("");
  const filas = ls.map((l,i) => `<tr class="${l.CODIGO===LOTE?"sel":""}" data-c="${l.CODIGO}">` +
    COLS_TABLA.map(c => `<td class="${c.extra?"col-extra ":""}${c.cls||""}">${c.cel(l,i)}</td>`).join("") + `</tr>`).join("");
  $("#lista").innerHTML = `<table class="tabla-lotes"><thead><tr>${th}</tr></thead><tbody>${filas}</tbody></table>`
    + `<p class="mini-nota" style="padding:8px 12px 12px">${esc(NOTA_TABLA)}</p>`;
  $("#lista").querySelectorAll("th button").forEach(b => b.onclick = () => cambiarOrden(b.dataset.o));
  $("#lista").querySelectorAll("tbody tr").forEach(f => f.onclick = () => { LOTE=f.dataset.c; pintarTabla(); pintarMapa(); pintarDetalle(); });
}
function cambiarOrden(clave){
  const c = COLS_TABLA.find(x=>x.orden===clave); if(!c) return;
  ORD.dir = ORD.clave===clave ? -ORD.dir : (c.dir||-1);
  ORD.clave = clave;
  pintarTabla();
}
function pintarFacetas(){
  const base = lotesCelda().filter(l => pasaCriterios(l));
  $("#facetas").innerHTML = Object.keys(CLASES).map(k => {
    const n = base.filter(l => claseDe(l)===k).length;
    const nula = !lotesCelda().some(l => claseDe(l)===k);
    return `<button class="faceta ${claseCss(k)} ${CLASES[k]&&!nula?"on":""}" data-f="${esc(k)}" ${nula?'aria-disabled="true" title="ningún lote de este perfil queda en esta clase"':""}><span class="gl">${CLASE_GLIFO[k]}</span>${esc(k)} ${n}</button>`;
  }).join("");
  $("#facetas").querySelectorAll(".faceta").forEach(b => b.onclick = () => {
    if(b.getAttribute("aria-disabled")==="true") return;
    CLASES[b.dataset.f] = !CLASES[b.dataset.f]; pintarTabla(); pintarMapa();
  });
}

function semaforo(l){
  const out = [];
  if(l.riesgo_baldio) out.push(["rojo","Supera la UAF del municipio ×"+fmt(l.veces_uaf,0), `UAF máxima ${fmt(l.uaf_max_ha,1)} ha (${esc(l.uaf_fuente||"")}). Si el origen del lote es baldío adjudicado, el artículo 72 de la Ley 160 de 1994 sanciona con nulidad la adquisición que acumule por encima de la Unidad Agrícola Familiar (art. 72 Ley 160/1994): se confirma con el certificado.`]);
  // Sin UAF publicada no se puede afirmar que el lote quede dentro de ella: la casilla
  // queda neutra y dice por qué, en vez de escribir "UAF máxima sin dato ha".
  else if(l.uaf_max_ha == null) out.push(["gris","Relación con la UAF del municipio: sin dato",
    "La Agencia Nacional de Tierras no publica Unidad Agrícola Familiar para este municipio, de modo que no se puede comparar el área del lote con ella. Se pide a la Agencia antes de negociar."]);
  else out.push(["verde","Dentro de la UAF del municipio", `UAF máxima ${fmt(l.uaf_max_ha,1)} ha.`]);
  if(l.microzona_urt) out.push(["ambar","Municipio con microzona de restitución vigente", `${fmt0(l.restitucion_mpio)} solicitudes de restitución en el municipio. Pedir certificación de la URT antes de ofertar.`]);
  else if((l.restitucion_mpio||0)>100) out.push(["ambar","Restitución activa en el municipio", `${fmt0(l.restitucion_mpio)} solicitudes; sin microzona vigente.`]);
  // Sin recuento publicado no se puede decir que la restitución sea baja.
  else if(!(l.restitucion_mpio >= 0)) out.push(["gris","Solicitudes de restitución en el municipio: sin dato",
    "La Unidad de Restitución de Tierras no publica el recuento de este municipio. Se pide la certificación a la entidad antes de ofertar."]);
  else out.push(["verde","Restitución baja en el municipio", `${fmt0(l.restitucion_mpio)} solicitudes.`]);
  if((l.estorbos||0)>0) out.push(["ambar",`Verificaciones previas a la escritura detectadas: ${l.estorbos}`, esc(l.gestion||"")]);
  else out.push(["verde","Sin verificaciones previas a la escritura detectadas", "Sin edificación mayor, cobertura boscosa por debajo del 10 por ciento, área catastral coherente con la geometría y destino económico declarado."]);
  out.push(["gris","Título y propietario", "Solo en el certificado de tradición. Ver ruta de adquisición."]);
  return out;
}

// La imagen descargada si la hay; si no, la misma petición al servicio desde el navegador
// (recuadro cuadrado con margen), que se resuelve al abrir la ficha.
function satDe(l){
  if(l.sat) return l.sat;
  let [x0,y0,x1,y1] = l.bbox;
  const m = D.sat_margen, dx=(x1-x0)*m, dy=(y1-y0)*m;
  x0-=dx; y0-=dy; x1+=dx; y1+=dy;
  const lado = Math.max(x1-x0, y1-y0), cx=(x0+x1)/2, cy=(y0+y1)/2;
  const bbox = [cx-lado/2, cy-lado/2, cx+lado/2, cy+lado/2];
  const px = D.sat_px;
  const src = `${D.sat_servicio}?bbox=${bbox.map(v=>v.toFixed(6)).join(",")}&bboxSR=4326&imageSR=4326&size=${px},${px}&format=jpg&f=image`;
  return {src, bbox, fecha:"", vivo:true};
}
// Estado reciente: Sentinel-2 (10 m) del mismo recuadro, con la fecha de la escena.
function vistaReciente(l){
  const s = l.sat2; if(!s) return "";
  const [x0,y0,x1,y1] = s.bbox, lado=700;
  const proy = p => [((p[0]-x0)/(x1-x0))*lado, ((y1-p[1])/(y1-y0))*lado];
  const d = pathDe(l.geom, proy);
  return `<div class="sat-caja"><img class="sat-img" src="${s.src}" alt="Imagen reciente Sentinel-2 del lote">
    <svg class="sat-svg" viewBox="0 0 ${lado} ${lado}" preserveAspectRatio="none">
      <path d="${d}" fill="none" stroke="#fff" stroke-width="4" opacity=".7"/>
      <path d="${d}" fill="none" stroke="var(--brand)" stroke-width="2.2"/></svg>
    <span class="sat-cred">Sentinel-2 · ESA/Copernicus · ${fmtFecha(s.fecha)}${s.nubes!=null?" · nubes "+fmt0(s.nubes*100)+" %":""} · 10 m</span></div>`;
}
function vistaSatelital(l){
  const s = satDe(l);
  const [x0,y0,x1,y1] = s.bbox, lado=700;
  const proy = p => [((p[0]-x0)/(x1-x0))*lado, ((y1-p[1])/(y1-y0))*lado];
  const d = pathDe(l.geom, proy);
  return `<div class="sat-caja"><img class="sat-img" src="${s.src}" alt="Imagen satelital del lote">
    <svg class="sat-svg" viewBox="0 0 ${lado} ${lado}" preserveAspectRatio="none">
      <path d="${d}" fill="none" stroke="#fff" stroke-width="4" opacity=".7"/>
      <path d="${d}" fill="none" stroke="var(--brand)" stroke-width="2.2"/></svg>
    <span class="sat-cred">Esri World Imagery · Vantor (antes Maxar)${s.fecha?" · captura del "+fmtFecha(s.fecha):s.vivo?" · cargada del servicio":""}</span></div>${avisoAntiguedad(s.fecha)}`;
}
// Fecha de captura en formato M/D/AAAA; se avisa si la imagen supera los cinco años.
function avisoAntiguedad(fecha){
  if(!fecha) return "";
  const m = fecha.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/); if(!m) return "";
  const anios = (Date.now() - new Date(+m[3], +m[1]-1, +m[2]).getTime())/3.15576e10;
  if(anios < 5) return "";
  return `<div class="sat-aviso">La imagen tiene ${anios.toFixed(0)} años. Verificar el estado actual del lote en campo o con una imagen reciente antes de decidir.</div>`;
}

// Las diez variables de la lista, repetidas en la ficha con el rótulo completo.
function loQueSeDecide(l){
  return [
    ["Área catastral del lote", fmt(l.area_ha,1)+" ha"],
    ["Potencia instalable indicativa", fmt(l.mwp_lote,1)+" MWp"],
    ["Composición de la cobertura del suelo", composicionCobertura(l,0.5,4)||"sin dato"],
    ["Diámetro del mayor círculo inscrito", fmt0(l.ancho_util_m)+" m"],
    ["Pendiente media", fmt(l.pendiente_media,1)+"°"],
    ["Valor catastral de referencia", l.valor_ref_cop!=null?fmtM(l.valor_ref_cop)+"$":"sin dato"],
    ["Suelo de protección en el ordenamiento", (POT_TXT[l.pot_semaforo]||"sin cartografía publicada")+(l.pot_rojo_pct?", "+fmt(l.pot_rojo_pct,1)+" % del lote":"")],
    ["Verificaciones previas a la escritura", String(l.estorbos??0)],
    ["Relación con la UAF municipal", l.riesgo_baldio?"supera el tope "+fmt(l.veces_uaf,1)+" veces":(l.uaf_max_ha==null?"sin UAF publicada para el municipio":"dentro del tope")],
    ["Inundación en episodios de La Niña", (l.ent_inundaciones_nina||0)===0 ? "sin episodios" : `${l.ent_inundaciones_nina} de 6, hasta ${fmt(l.ent_inundacion_ha_max,1)} ha`],
  ];
}
// Constancia de los cruces cartograficos: cada uno se redacta segun lo que dijo el dato.
// Lectura del certificado de tradicion y libertad. Solo se pinta si ese lote tiene
// folio leido: un lote sin certificado no lleva la seccion, en vez de llevarla vacia.
// Cada afirmacion de la Parte 2 cita la anotacion de la que sale, y esas citas ya se
// comprobaron contra las anotaciones del propio folio antes de guardarse; lo que no se
// pudo comprobar se marca aqui como no comprobado, no se calla.
//
// LA EXTRACCION SE VE COMO EXTRACCION. La identificacion va en la misma rejilla de
// etiqueta y valor que usan las variables de decision, y las anotaciones, las areas y
// las matriculas segregadas van en tabla, una fila cada una. Antes esta seccion volcaba
// cada campo del analisis como parrafo, uno detras de otro, y medía 2.300 px de alto:
// parecia un documento de texto pegado dentro del reporte. La unica parte en prosa es la
// lectura para el proyecto, y va a una linea por asunto.
//
// Esta funcion pinta LAS DOS versiones, la del visor y la de la ficha imprimible, con la
// misma hoja de estilos, para que no se separen. Lo unico que cambia entre ellas es el
// nivel del titulo, que en cada documento tiene su propio rango, y que en la imprimible
// lo plegable sale desplegado, porque en papel nadie puede pulsar nada.
function bloqueCertificado(l, paraImprimir){
  const c = l.certificado;
  if(!c) return "";
  const H  = paraImprimir ? "h2" : "h4";
  const ti = c.titularidad || {};
  const tit = ti.titulares || [];
  const grav = c.gravamenes_vigentes || [];
  const obra = c.afectaciones_por_obra_publica || [];
  const org = c.origen_del_dominio || {};
  const ar  = c.area || {};
  const pp  = c.para_el_proyecto || {};
  const der = c.matriculas_derivadas || [];
  const anots = c.anotaciones || [];
  const areas = (c.cabida && c.cabida.areas) || [];
  const salv = c.salvedades || [];
  const nc   = c.no_consta || [];
  const docs = pp.documentos_a_pedir || [];
  const cita = ns => (ns && ns.length) ? ` <span class="c-anot">anot. ${ns.join(", ")}</span>` : "";
  const noComp = x => x && x.comprobado === false
      ? ` <span class="c-nover">sin cita, no comprobado</span>` : "";
  const rot = (t, primero) => `<div class="c-rot${primero?" c-primero":""}">${t}</div>`;

  // ---- Parte 1: identificacion, en la misma rejilla que el resto de la ficha ----
  const ident = [
    ["Matrícula", c.matricula, 0],
    ["Círculo registral", c.circulo_registral, 0],
    ["Estado del folio", c.estado_folio, 0],
    ["Apertura del folio", c.fecha_apertura, 0],
    ["Municipio", [c.municipio, c.departamento].filter(Boolean).join(", "), 0],
    ["Vereda", c.vereda, 0],
    ["Código catastral", c.codigo_catastral, 1],
    ["Oficina de registro", c.orip, 1],
    ["Expedido", c.expedido, 1],
  ].map(([k, v, doble]) => `<div class="dato${doble?" d2":""}"><div class="dk">${esc(k)}</div>`
      + `<div class="dv">${v ? esc(v) : `<span class="c-vac">no consta</span>`}</div></div>`).join("");

  // ---- Parte 1: la tabla de anotaciones ----
  // El folio escribe el nombre del interviniente con su cedula o NIT dentro de la
  // anotacion, y la marca en una casilla aparte donde el nombre va sin identificacion.
  // Por eso la marca se empareja por el nombre contenido y no por igualdad exacta: con
  // igualdad exacta no casaba ninguna, y la marca I, que es la falsa tradicion, no se
  // habria visto nunca.
  const marcaDe = (a, nombre) => {
    const ms = a.marcas || {};
    if(nombre in ms) return ms[nombre];
    const n = String(nombre||"").toUpperCase();
    for(const k in ms){
      const K = String(k||"").toUpperCase();
      if(K && (n.indexOf(K) >= 0 || K.indexOf(n) >= 0)) return ms[k];
    }
    return null;
  };
  const marca = m => m === "I"
      ? ` <span class="c-mi" title="titular de dominio incompleto: falsa tradición">I</span>`
      : m === "X" ? ` <span class="c-mx" title="titular de derecho real de dominio">X</span>` : "";
  const partes = (a, lado) => {
    const ns = a[lado] || [];
    if(!ns.length) return `<span class="c-vac">no aplica</span>`;
    return ns.map(n => `<span class="c-per">${esc(n)}${marca(marcaDe(a, n))}</span>`).join("");
  };
  const filaAnot = a => `<tr class="${a.cancelada?"c-can":""}">`
    + `<td class="c-n">${esc(a.nro)}</td><td class="c-f">${esc(a.fecha||"")}</td>`
    + `<td><span class="c-acto">${esc(a.especificacion||"")}</span>`
      + (a.cancelada ? `<span class="c-bad c-bad-can">cancelada${(a.cancelada_por||[]).length?" por "+a.cancelada_por.join(", "):""}</span>` : "")
      + ((a.cancela_a||[]).length ? `<span class="c-bad">cancela ${a.cancela_a.join(", ")}</span>` : "")
      + (a.documento ? `<span class="c-doc">${esc(a.documento)}</span>` : "")
    + `</td><td>${partes(a,"de")}</td><td>${partes(a,"a")}</td></tr>`;

  const tablaAnot = anots.length ? `<table>
    <colgroup><col style="width:2.6em"><col style="width:6em"><col style="width:30%"><col style="width:27.5%"><col style="width:27.5%"></colgroup>
    <thead><tr><th>N.º</th><th>Fecha</th><th>Acto y documento</th><th>Sale de</th><th>Entra a</th></tr></thead>
    <tbody>${anots.map(filaAnot).join("")}</tbody></table>
    <p class="c-leg"><b>X</b> titular de derecho real de dominio · <b>I</b> titular de dominio incompleto, que es la falsa tradición · las filas atenuadas están canceladas por una anotación posterior.</p>` : "";

  const tablaAreas = areas.length ? `<table>
    <colgroup><col style="width:22%"><col><col style="width:13%"></colgroup>
    <thead><tr><th>Área</th><th>Según</th><th>Anot.</th></tr></thead>
    <tbody>${areas.map(a=>`<tr><td class="c-acto">${esc(a.valor||"")}${a.unidad?" "+esc(a.unidad):""}</td>`
      + `<td>${esc(a.segun||"")}</td><td>${(a.anotaciones||[]).join(", ")}</td></tr>`).join("")}</tbody></table>` : "";

  const tablaDer = der.length ? `<table>
    <colgroup><col style="width:26%"><col><col style="width:14%"></colgroup>
    <thead><tr><th>Matrícula</th><th>Concepto</th><th>Anot.</th></tr></thead>
    <tbody>${der.map(x=>`<tr><td class="c-acto">${esc(x.matricula||"")}</td><td>${esc(x.concepto||"")}</td>`
      + `<td>${x.por_anotacion!=null?esc(x.por_anotacion):""}</td></tr>`).join("")}</tbody></table>` : "";

  // ---- Parte 2: la lectura, una linea por asunto ----
  const lineas = [];
  lineas.push(["Titulares", tit.length
    ? tit.map(x=>`<b>${esc(x.nombre||"")}</b>${x.identificacion?` ${esc(x.identificacion)}`:""}`
        + `${x.marca==="I"?` <span class="c-mal">dominio incompleto</span>`:""}${cita(x.anotaciones)}`).join(" · ")
      + (ti.firmas_necesarias ? `. Hacen falta <b>${esc(ti.firmas_necesarias)} firmas</b>` : "")
      + (ti.dominio_pleno===false ? `. <span class="c-mal">El folio no muestra dominio pleno</span>` : "")
      + (pp.puede_transferirse===false ? `. <span class="c-mal">No se puede transferir hasta resolver lo anterior</span>` : "")
      + ". " + (ti.nota ? esc(ti.nota) : "")
    : `<span class="c-vac">El análisis no identificó titulares en el folio.</span>`]);
  lineas.push(["Gravámenes vigentes", grav.length
    ? grav.map(g=>`<span class="c-per"><b>${esc(g.tipo||"")}.</b> ${esc(g.detalle||"")}`
        + `${g.a_favor_de?` A favor de ${esc(g.a_favor_de)}.`:""}${cita(g.anotaciones)}${noComp(g)}`
        + `${g.como_se_levanta?` Se levanta: ${esc(g.como_se_levanta)}${g.ante_quien?`, ante ${esc(g.ante_quien)}`:""}.`:""}</span>`).join("")
    : "Ninguno inscrito. El folio no registra hipotecas, embargos, demandas ni medidas cautelares vigentes; que no consten no equivale a que no existan obligaciones, porque el folio solo recoge lo inscrito."]);
  if(obra.length) lineas.push(["Obra pública", obra.map(o=>`<span class="c-per">${esc(o.entidad||"")}`
    + `${o.area?`, ${esc(o.area)}`:""}.${o.se_ejecuto===true?" La transferencia se ejecutó.":o.se_ejecuto===false?" No se ejecutó.":""}`
    + `${o.matricula_resultante?` La franja pasó a la matrícula ${esc(o.matricula_resultante)}.`:""}${cita(o.anotaciones)}${noComp(o)}</span>`).join("")]);
  // El tipo de origen se escribe delante, en negrita, así que si el detalle vuelve a
  // empezar por él se quita la repetición. Se ve como "privado. Privado. Folio abierto
  // por desenglobe", que es el modelo contestando dos veces lo mismo, no un dato nuevo.
  const detOrg = String(org.detalle||"").replace(
      new RegExp("^\\s*" + String(org.tipo||"").replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*[.:,]?\\s*", "i"), "");
  if(org.tipo) lineas.push(["Origen del dominio", `<b>${esc(org.tipo)}.</b> ${esc(detOrg)}${cita(org.anotaciones)}`
    + (org.sujeto_ley_160===true ? ` <span class="c-ojo">Sujeto a la Ley 160 de 1994:</span> la acumulación por encima de la Unidad Agrícola Familiar está condicionada.` : "")
    + (org.nota ? ` ${esc(org.nota)}` : "")]);
  if(ar.explicacion || ar.area_vigente) lineas.push(["Área", ""
    + (ar.concilian===true ? `<b>Las cifras del folio concilian entre sí.</b> `
       : ar.concilian===false ? `<span class="c-ojo">Las cifras del folio no concilian.</span> ` : "")
    + esc(ar.explicacion||"")
    + (ar.area_vigente ? ` <b>Área vigente: ${esc(ar.area_vigente)}.</b>` : "")]);

  const lista = xs => `<ul class="c-lista">${xs.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
  const cond = pp.condiciones_previas || [];
  const ries = pp.riesgos_para_implantacion || [];
  const accion = (cond.length || ries.length || docs.length) ? rot("Antes de firmar") + `
    <div class="c-2col c-igual">
      <div>${cond.length ? lista(cond) : `<p class="c-vac">El análisis no dejó condiciones previas.</p>`}
        ${ries.length ? rot("Para la implantación") + lista(ries) : ""}</div>
      <div>${docs.length ? `<table>
        <colgroup><col style="width:58%"><col></colgroup>
        <thead><tr><th>Documento por pedir</th><th>A quién se pide</th></tr></thead>
        <tbody>${docs.map(x => typeof x === "string"
          ? `<tr><td>${esc(x)}</td><td class="c-vac">sin entidad indicada</td></tr>`
          : `<tr><td>${esc(x.documento||"")}</td><td>${x.a_quien?esc(x.a_quien):`<span class="c-vac">sin entidad indicada</span>`}</td></tr>`).join("")}</tbody></table>` : ""}</div>
    </div>` : "";

  return `
  <${H}>Lo que dice el certificado de tradición y libertad</${H}>
  <div class="cert">
    ${rot("Identificación del folio", true)}
    <div class="datos">${ident}</div>
    ${c.resumen ? `<p class="c-res">${esc(c.resumen)}</p>` : ""}

    ${anots.length ? rot(`Anotaciones <em>${anots.length} en el folio</em>`) + tablaAnot : ""}

    ${(areas.length || der.length) ? `<div class="c-2col">
      <div>${areas.length ? rot("Áreas que trae el folio") + tablaAreas : ""}</div>
      <div>${der.length ? rot("Matrículas segregadas") + tablaDer : ""}</div>
    </div>` : ""}

    ${rot("Qué significa para el proyecto")}
    <div class="c-lineas">${lineas.map(([k,v])=>`<div class="c-li"><div class="c-lk">${esc(k)}</div><div class="c-lv">${v}</div></div>`).join("")}</div>

    ${accion}

    ${nc.length ? `<details${paraImprimir?" open":""}><summary>Mostrar lo que el folio no dice: ${nc.length} punto${nc.length===1?"":"s"} que se buscaron y no constan</summary>
      <ul>${nc.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
    ${salv.length ? `<details${paraImprimir?" open":""}><summary>Mostrar ${salv.length===1?"la salvedad que el registro anotó":`las ${salv.length} salvedades que el registro anotó`} sobre el folio</summary>
      <ul>${salv.map(s=>`<li>${esc(s)}</li>`).join("")}</ul></details>` : ""}
    <p class="c-pie">Extracción y lectura del folio, hecha el ${esc(c.leido||"")}; confianza ${esc(c.confianza||"")}${(c.confianza!=="alta" && c.confianza_motivo)?`, ${esc(c.confianza_motivo)}`:""}. La identificación, las anotaciones y las áreas se transcriben del documento; la lectura se deriva de ellas y no sustituye el estudio de títulos ni el concepto de un abogado.</p>
  </div>`;
}
function verificado(l){
  // Cada cruce lleva SU PROPIA redaccion para el hallazgo. Antes la etiqueta era
  // siempre afirmativa ("Sin titulos mineros") aunque la casilla estuviera en ambar,
  // de modo que el texto decia lo contrario del dato y solo el color lo desmentia. El
  // reporte declara que el color acompana al nombre escrito, no que lo sustituya.
  const items = [
    [(l.ent_mineria_titulos||0)===0, "Sin títulos mineros vigentes (ANM)", "Con título minero vigente (ANM)"],
    [!(l.ent_runap_ha>0),    "Fuera del RUNAP",                      "Dentro de un área protegida del RUNAP"],
    [!(l.ent_resguardo_ha>0),"Fuera de resguardo indígena",          "Sobre resguardo indígena"],
    [!(l.ent_consejo_ha>0),  "Fuera de consejo comunitario",         "Sobre consejo comunitario"],
    [!(l.ent_paramo_ha>0),   "Fuera de páramo delimitado",           "Sobre páramo delimitado"],
    [String(l.clase_suelo||"rural")==="rural", "Suelo rural",        "Suelo urbano o de expansión"],
  ];
  return `<div class="jur">${items.map(([ok,tOk,tNo])=>`<div class="fila"><div class="sem ${ok?"verde":"ambar"}"></div><div><b>${ok?tOk:tNo}</b></div></div>`).join("")}</div>
    <p class="mini-nota">Constancia del cruce cartográfico${l.ent_fecha?", consultado el "+esc(fmtFecha(l.ent_fecha)):""}. Una casilla en ámbar significa que la figura sí toca el lote: en ese caso aparece arriba, entre las condiciones del lote, con su trámite. Ninguna de estas figuras retira el lote de la lista: los lotes que las tocan se muestran clasificados como No viable.</p>`;
}
// Unidad pegada a la cifra, y "sin dato" solo cuando de verdad no hay dato.
const fmtU = (v, d, u) => v==null ? "sin dato" : fmt(v, d) + (u ? " " + u : "");

// Grupos de la ficha. Cada uno declara de dónde sale el dato, porque una cifra sin
// fuente no se puede verificar.
function fichaGrupos(l, c){
  return [
    ["Dimensiones y forma del lote", "Catastro público del IGAC para el polígono y el área; geometría medida sobre ese polígono.", [
      ["Área catastral del lote", fmtU(l.area_ha,1,"ha")],
      ["Área registrada en el catastro", fmtU(l.area_terreno_catastro_m2!=null?l.area_terreno_catastro_m2/1e4:null,1,"ha")],
      ["Diferencia entre el área del catastro y la de la geometría", fmtU(l.desajuste_catastro_pct,1,"%")],
      ["Área del núcleo del lote", fmtU(l.area_nucleo_ha,1,"ha")],
      ["Fracción del lote en el núcleo", fmtU(l.nucleo_frac,2,"")],
      ["Diámetro del mayor círculo inscrito", fmtU(l.ancho_util_m,0,"m")],
      ["Compacidad de la forma, de 0 a 1", fmtU(l.compacidad,2,"")],
      ["Alargamiento del rectángulo envolvente", fmtU(l.alargamiento,2,"a 1")],
      ["Llenado del rectángulo envolvente", fmtU(l.llenado_rect,2,"")],
      ["Largo del rectángulo envolvente", fmtU(l.rect_largo_m,0,"m")],
      ["Ancho del rectángulo envolvente", fmtU(l.rect_ancho_m,0,"m")],
      ["Potencia instalable indicativa", fmtU(l.mwp_lote,1,"MWp")],
    ], "Compacidad: el valor 1 es un círculo; cuanto más baja, más alargado o irregular es el lote. Potencia instalable indicativa: área catastral del lote entre "+fmt(D.ha_por_mwp,2)+" hectáreas por megavatio pico. Esa huella es una referencia de ingeniería para planta en suelo con seguidor de un eje: no la publica ninguna entidad colombiana y no está medida en plantas del país. No descuenta la cobertura ni la pendiente, que se describen aparte."],

    ["Tenencia del entorno", "Catastro público del IGAC, medido sobre los lotes contiguos.", [
      ["Superficie de los lotes colindantes", fmtU(l.ha_pegadas,1,"ha")],
      ["Lotes contiguos al lote", fmtU(l.lotes_pegados,0,"lotes")],
      ["Lotes que hay que reunir para alcanzar "+fmt0(D.objetivo_agregacion_ha||150)+" ha", fmtU(l.lotes_para_150ha,0,"lotes")],
      ["Superficie de catastro público en un kilómetro alrededor", fmtU(l.ha_catastro_1km,0,"ha")],
    ], "Cada lote adicional que hay que reunir es otra negociación, otro folio de registro y otro punto de fallo. Un lote sin vecindad útil no admite una segunda fase."],

    ["Terreno y relieve", "Modelo digital de elevación Copernicus DEM GLO-30, medido dentro del polígono del lote.", [
      ["Pendiente media", fmtU(l.pendiente_media,1,"°")],
      ["Pendiente del percentil 90", fmtU(l.pendiente_p90,1,"°")],
      ["Rugosidad del relieve", fmtU(l.rugosidad_m,1,"m")],
      ["Desnivel total dentro del lote", fmtU(l.desnivel_total_m,1,"m")],
      ["Elevación media", fmtU(l.elevacion_media,0,"m sobre el nivel del mar")],
      ["Amenaza por movimientos en masa", l.ent_mov_masa?({B:"baja",M:"media",A:"alta",MA:"muy alta"})[l.ent_mov_masa]||String(l.ent_mov_masa):"sin dato"],
      ["Amenaza sísmica", l.ent_sismica?String(l.ent_sismica).toLowerCase():"sin dato"],
    ], "La amenaza por movimientos en masa y la amenaza sísmica son clasificaciones municipales del Servicio Geológico Colombiano."],

    ["Cobertura del suelo", "ESA WorldCover 2021, 10 metros de resolución, recortado con el polígono del lote. Cifras de la propia clasificación, sin transformar.", [
      ...(coberturaDe(l).length
          ? coberturaDe(l).map(([v,nom]) => [nom.charAt(0).toUpperCase()+nom.slice(1), fmt(v,1)+" %"])
          : [["Clases medidas en el lote", "sin dato"]]),
      ["Superficie construida registrada en el catastro", fmtU(l.area_construida_m2,0,"m²")],
      ["Terreno abierto concentrado en el mayor parche continuo", fmtU(l.parche_mayor_frac,2,"")],
      ["Parches continuos de terreno abierto", fmtU(l.n_parches_utiles,0,"")],
      ["Clase agrológica", l.ent_clase_agrologica?String(l.ent_clase_agrologica)+(l.ent_clase_agrologica_fuente?" ("+l.ent_clase_agrologica_fuente+")":""):"sin dato"],
      ["Frontera agrícola", l.ent_frontera_agricola||"sin dato"],
    ], "Cada cifra es el porcentaje del lote en esa clase de ESA WorldCover, de la capa de 2021, y no se combina con las demás en ningún índice. Describen lo que hoy ocupa el terreno; qué parte es implantable lo deciden el diseño de la planta y el permiso ambiental. Terreno abierto, en las dos filas de parches, son las clases sin arbolado ni edificación: matorral, pastizal, cultivo y suelo desnudo. La clase agrológica la publica el IGAC y la frontera agrícola la UPRA."],

    ["Acceso y conexión eléctrica", "Vías de OpenStreetMap; subestación de conexión y tensión del inventario del sistema interconectado.", [
      ["Distancia a vía carrozable", fmtU(l.dist_via_km,2,"km")],
      ["Distancia del centro del lote a la vía", fmtU(l.dist_via_centro_km,2,"km")],
      ["Distancia a vía principal", fmtU(l.dist_via_principal_km,1,"km")],
      ["Subestación de conexión", l.conexion_nombre||"sin dato"],
      ["Tensión de la subestación de conexión", fmtU(l.conexion_kv,0,"kV")],
      ["Distancia a la subestación de conexión", fmtU(l.conexion_km,1,"km")],
      ["Operador de red de la subestación", c.operador||"sin dato"],
      ["Capacidad de conexión disponible en la subestación", fmtU(PERFIL==="distribuida"?c.capacidad_mt_mw:c.capacidad_at_mw,1,"MW")],
      ["Línea de transmisión más cercana", l.ctx_linea_km!=null?fmt(l.ctx_linea_km,1)+" km"+(l.ctx_linea_kv?", de "+l.ctx_linea_kv+" kV":""):"sin dato"],
    ], "La distancia a la subestación y la capacidad disponible se miden en la grilla o en su punto de conexión, no en el lindero del lote, de modo que son prácticamente iguales para todos los lotes de la misma grilla."],

    ["Agua, inundación y clima", "IDEAM: hidrografía, manchas de inundación observadas, zonas inundables, climatología del Niño y de la Niña, e incendios de cobertura vegetal.", [
      ["Inundación en episodios de La Niña", (l.ent_inundaciones_nina||0)===0?"sin episodios registrados":`${l.ent_inundaciones_nina} de 6 episodios`],
      ["Superficie máxima inundada en un episodio", fmtU(l.ent_inundacion_ha_max,1,"ha")],
      ["Zona inundable periódica dentro del lote", fmtU(l.ent_zip_ha,1,"ha")],
      ["Superficie del lote en zona inundable periódica", fmtU(l.pct_zip,1,"%")],
      ["Cuerpo de agua dentro del lote", fmtU(l.ent_cuerpo_agua_ha,1,"ha")],
      ["Superficie del lote bajo lámina de agua", fmtU(l.pct_cuerpo_agua,1,"%")],
      ["Drenajes cartografiados en el envolvente", fmtU(l.ent_drenajes_n,0,"")],
      ["Humedal inventariado", l.ent_humedal||"ninguno"],
      ["Cuenca con plan de ordenación y manejo", l.ent_pomca||"sin dato"],
      ["Excedente de lluvia en una Niña típica", l.ent_nina_precip?String(l.ent_nina_precip)+" % de lo normal":"sin dato"],
      ["Alteración de la lluvia en un Niño típico", l.ent_nino_precip?String(l.ent_nino_precip)+" % de lo normal":"sin dato"],
      ["Periodo de retorno de la sequía meteorológica", l.ent_sequia_retorno?String(l.ent_sequia_retorno)+" años":"sin dato"],
      ["Incendios registrados en cinco kilómetros", fmtU(l.ent_incendios_5km,0,"")],
      ["Superficie quemada en cinco kilómetros", fmtU(l.ent_incendios_ha_5km,0,"ha")],
      ["Último incendio registrado", l.ent_incendios_ultimo?String(Math.round(l.ent_incendios_ultimo)):"ninguno registrado"],
    ], "La ronda hídrica de cada cauce es franja de protección legal y no admite módulos ni subestación; su delimitación exacta la fija la Corporación Autónoma Regional y no está publicada en cartografía nacional."],

    ["Catastro y registro del lote", "Catastro público del IGAC, corte mensual publicado por el instituto.", [
      ["Nombre del lote en el catastro", l.nombre_predio||"sin nombre en el catastro"],
      ["Número predial", String(l.CODIGO)],
      ["Número predial anterior", l.numero_predial_anterior||"sin dato"],
      ["Destino económico declarado en el catastro", l.destino||"sin dato"],
      ["Clasificación del suelo", l.clase_suelo||"sin dato"],
      ["Construcciones registradas en el catastro", l.n_construcciones!=null?String(l.n_construcciones)+(l.construccion_puntaje_max?", puntaje máximo "+l.construccion_puntaje_max:""):"sin dato"],
      ["Uso principal de la construcción", l.construccion_uso_principal||"sin dato"],
      ["Zona geoeconómica dominante del IGAC", l.zona_economica_dominante!=null?String(l.zona_economica_dominante):"sin dato"],
      ["Matrícula inmobiliaria", l.matricula_inmobiliaria
        || (l.matricula_motivo ? "sin dato: " + l.matricula_motivo : "sin dato: el catastro no la publica y el lote no se ha consultado una a una")],
    ], "El catastro no publica el nombre ni el número de propietarios: eso lo da el certificado de tradición y libertad."],
  ];
}

function pintarDetalle(){
  const l = lotesCelda().find(x => x.CODIGO===LOTE);
  $("#cuerpo").classList.toggle("con-lote", !!l);
  document.body.classList.toggle("con-lote", !!l);
  if(!l){ $("#detalle").innerHTML = ""; $("#det-sub").textContent=""; return; }
  $("#det-sub").textContent = `${l.municipio}, ${l.departamento||""}`;
  const c = celdaActual()||{};
  const clase = claseDe(l);
  const cond = condicionesDe(l);
  const grupos = fichaGrupos(l, c);
  $("#detalle").innerHTML = `
    <div class="det-cab"><div><h3>${esc(l.municipio)}, ${esc(l.departamento||"")}</h3>
      <div>${esc(l.nombre_predio||"sin nombre en el catastro")}</div>
      <div class="cod">${l.CODIGO}</div>
      <div class="cod">predial anterior ${esc(l.numero_predial_anterior||"sin dato")}</div>
      <div class="cod">matrícula inmobiliaria ${l.matricula_inmobiliaria
        ? `<b>${esc(l.matricula_inmobiliaria)}</b>` : "sin dato"}</div>
      ${pastilla(clase)}</div>
      <div class="det-cifra"><b>${fmt(l.area_ha,1)}</b><span>ha de área catastral</span><em>${fmt(l.mwp_lote,1)} MWp indicativos</em></div></div>
    <div class="det-motivo">${esc(l.motivo||"")}</div>
    <h4>${clase==="No viable" ? "Por qué el lote no es viable: "+cond.filter(x=>x.clase==="No viable").length+" condición"+(cond.filter(x=>x.clase==="No viable").length===1?"":"es")+" que ninguna gestión resuelve" : clase==="Idóneo" ? "Condiciones del lote" : "Condiciones del lote y trámite que exige cada una: "+cond.length}</h4>
    ${bloqueCondiciones(l)}
    ${bloqueAvisos(l)}
    <h4>Variables de decisión</h4>
    <div class="datos">${loQueSeDecide(l).map(([k,v])=>`<div class="dato"><div class="dk">${k}</div><div class="dv">${esc(v)}</div></div>`).join("")}</div>
    <details class="defs"><summary>Índice de aptitud del lote: ${fmt0(l.indice_lote)} sobre 100. Descriptor técnico; no clasifica el lote ni ordena la lista</summary>${tablaIndice(l)}
      <p class="idx-nota">Criterios en nivel bueno o superior: ${l.criterios_cumplidos!=null&&l.criterios_evaluados!=null?l.criterios_cumplidos+" de "+l.criterios_evaluados+" evaluados":"sin dato"}. Índice de aptitud de la grilla ${esc(c.cell_id||"")}: ${fmt(c.indice_aptitud,1)} sobre 100${c.ranking!=null?", posición #"+c.ranking+" en el orden de prioridad":""}. Es un dato de la grilla, idéntico para todos sus lotes.</p></details>
    <h4>Verificaciones previas a la escritura</h4>
    ${bloqueAdquisicion(l)}
    ${grupos.map(([tit, fuente, filas, nota]) => `<h4>${esc(tit)}</h4>
      <p class="mini-nota">Fuente: ${esc(fuente)}</p>
      <div class="datos">${filas.map(([k,v])=>`<div class="dato"><div class="dk">${esc(k)}</div><div class="dv">${esc(v)}</div></div>`).join("")}</div>
      ${nota?`<p class="mini-nota">${esc(nota)}</p>`:""}`).join("")}
    <h4>Recurso solar en el punto del lote</h4>
    <div class="datos">${contexto(l).map(([k,v])=>`<div class="dato"><div class="dk">${esc(k)}</div><div class="dv">${esc(v)}</div></div>`).join("")}</div>
    <p class="mini-nota">Fuente: Global Solar Atlas (modelo Solargis), promedios anuales de largo plazo con 250 metros de resolución, tomados en el centroide del lote. La grilla mide 5 kilómetros de lado, de modo que estas cifras son prácticamente iguales para todos sus lotes.</p>
    <details class="defs"><summary>Definición de cada variable de recurso solar</summary>${definicionesRecurso()}</details>
    <h4>Valor catastral de referencia del suelo</h4>
    ${bloqueValor(l)}
    <h4>Norma urbanística municipal (Plan de Ordenamiento Territorial)</h4>
    <div class="jur">${normaUrbana(l).map(([c,t,d])=>`<div class="fila"><div class="sem ${c==="nota"?"gris":c}"></div><div><b>${t}</b>${d?"<br><span>"+d+"</span>":""}</div></div>`).join("")}</div>
    <h4>Verificación jurídica preliminar</h4>
    <div class="jur">${semaforo(l).map(([c,t,d])=>`<div class="fila"><div class="sem ${c}"></div><div><b>${t}</b><br><span>${d}</span></div></div>`).join("")}</div>
    <h4>Entorno ambiental y de riesgo</h4>
    <div class="jur">${entorno(l).map(([c,t,d])=>`<div class="fila"><div class="sem ${c==="nota"?"gris":c}"></div><div><b>${t}</b>${d?"<br><span>"+d+"</span>":""}</div></div>`).join("")}</div>
    <h4>Cruces cartográficos verificados</h4>${verificado(l)}
    ${bloqueCertificado(l, false)}
    <h4>Imagen satelital de alta resolución</h4>${vistaSatelital(l)}
    
    <h4>Siguiente paso: verificación del título</h4>
    <div class="paso-cert">
      <p>El catastro no dice de quién es el lote ni si tiene hipoteca, embargo, sucesión, falsa tradición u origen en baldío. Eso lo desbloquea el <b>certificado de tradición y libertad</b> de la Superintendencia de Notariado y Registro (${fmtCop(D.costo_certificado)} el electrónico, Resolución 2026-001726): propietarios actuales con su identificación, la cadena completa de actos sobre el lote y si el origen es baldío adjudicado.</p>
      <p>${textoMatricula(l)}</p>
      ${l.matricula_inmobiliaria ? `<p class="mini">El portal de la Superintendencia no admite enlaces que lleven la matrícula incluida: el botón la copia y abre el portal, donde se pega en el campo de matrícula inmobiliaria.</p>` : ""}
      <div class="acciones">
        <button class="btn p" id="btn-snr">${l.matricula_inmobiliaria?"Copiar matrícula e ir a la Superintendencia por el certificado":"Ir a la Superintendencia por el certificado"}</button>
        <button class="btn" id="btn-copiar">Copiar número predial</button>
        ${l.numero_predial_anterior?`<button class="btn" id="btn-copiar-ant">Copiar número predial anterior</button>`:""}
      </div>
      <p class="mini">Con el certificado en la mano se hace el estudio de títulos de veinte años, que es el que cierra la verificación jurídica.</p>
    </div>
    <div class="acciones">
      <button class="btn p" id="btn-ficha">Descargar ficha PDF</button>
      <button class="btn" id="btn-geo">Descargar el polígono del lote para un programa de mapas</button>
      <button class="btn" id="btn-maps">Abrir en Google Maps</button>
    </div>`;
  $("#btn-ficha").onclick = () => {
    if(ficha(l) === false)
      alert("El navegador bloqueó la ventana. Permite las ventanas emergentes de esta página para abrir la ficha.");
  };
  // El polígono con sus atributos. Se excluyen las claves internas del visor y la escala
  // de calibración del índice, que no es una cifra del lote: la cobertura va clase a clase.
  $("#btn-geo").onclick = () => descargar(`lote_${l.CODIGO}.geojson`, JSON.stringify({type:"FeatureCollection",features:[{type:"Feature",properties:Object.fromEntries(Object.entries(l).filter(([k])=>!["geom","sat","sat2","bbox","centro","cobertura_apta_pct"].includes(k)).concat([["clase",clase]])),geometry:l.geom}]}));
  // La forma /maps/place/ fija un marcador sobre el lote; /maps/@ solo mueve la cámara.
  // El acercamiento se gradúa con el área: un lote de 200 ha necesita menos que uno de 5.
  $("#btn-maps").onclick = () => {
    const a = l.area_ha||10, z = a > 300 ? 14 : a > 100 ? 15 : a > 25 ? 16 : 17;
    const [lon, lat] = l.centro;
    window.open(`https://www.google.com/maps/place/${lat},${lon}/@${lat},${lon},${z}z/data=!3m1!1e3`, "_blank", "noopener");
  };
  $("#btn-snr").onclick = () => { if(l.matricula_inmobiliaria) navigator.clipboard?.writeText(l.matricula_inmobiliaria); window.open(D.url_snr,"_blank","noopener"); };
  $("#btn-copiar").onclick = (e) => { navigator.clipboard?.writeText(l.CODIGO).then(()=>{ e.target.textContent="Copiado"; setTimeout(()=>e.target.textContent="Copiar número predial",1400); }); };
  const ba = $("#btn-copiar-ant"); if(ba) ba.onclick = (e) => { navigator.clipboard?.writeText(l.numero_predial_anterior).then(()=>{ e.target.textContent="Copiado"; setTimeout(()=>e.target.textContent="Copiar número predial anterior",1400); }); };
}

function descargar(nombre, contenido, tipo="application/geo+json"){
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([contenido],{type:tipo})); a.download=nombre; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
// Lista filtrada a tabla separada por punto y coma, en UTF-8 con marca de orden, para
// abrirla en una hoja de cálculo. Cada columna lleva por encabezado el nombre de la
// variable escrito como se lee en la ficha, no la abreviatura con que viaja el dato.
const COLS_DESCARGA = [
  ["clase", "Clase del lote"],
  ["condiciones_del_lote", "Condiciones del lote que fijan su clase"],
  ["condiciones_tramites", "Trámite que exige cada condición"],
  ["cell_id", "Grilla"],
  ["CODIGO", "Número predial"],
  ["numero_predial_anterior", "Número predial anterior"],
  ["matricula_inmobiliaria", "Matrícula inmobiliaria"],
  ["municipio", "Municipio"],
  ["departamento", "Departamento"],
  ["nombre_predio", "Nombre del lote en el catastro"],
  ["destino", "Destino económico declarado en el catastro"],
  ["area_ha", "Área catastral del lote (ha)"],
  ["ancho_util_m", "Diámetro del mayor círculo inscrito (m)"],
  ["mwp_lote", "Potencia instalable indicativa a 1,5 ha por MWp (MWp)"],
  ["cabe_utility", "Cabe un proyecto de escala utility"],
  ["cabe_distribuida", "Cabe un proyecto de generación distribuida"],
  ["pendiente_media", "Pendiente media (grados)"],
  ["cob_pastizal_pct", "Pastizal, ESA WorldCover (%)"],
  ["cob_bosque_pct", "Bosque, ESA WorldCover (%)"],
  ["cob_cultivo_pct", "Cultivo, ESA WorldCover (%)"],
  ["cob_matorral_pct", "Matorral, ESA WorldCover (%)"],
  ["cob_construido_pct", "Suelo construido, ESA WorldCover (%)"],
  ["cob_desnudo_pct", "Suelo desnudo, ESA WorldCover (%)"],
  ["cob_humedal_pct", "Humedal herbáceo, ESA WorldCover (%)"],
  ["cob_agua_pct", "Agua permanente, ESA WorldCover (%)"],
  ["cob_manglar_pct", "Manglar, ESA WorldCover (%)"],
  ["dist_via_km", "Distancia a vía carrozable (km)"],
  ["conexion_nombre", "Subestación de conexión"],
  ["conexion_kv", "Tensión de la subestación (kV)"],
  ["conexion_km", "Distancia a la subestación de conexión (km)"],
  ["valor_ref_cop", "Valor catastral de referencia del lote (pesos)"],
  ["valor_ref_cop_ha", "Valor catastral de referencia por hectárea (pesos)"],
  ["valor_confianza", "Confianza del valor catastral"],
  ["ant_banda", "Banda de valor de la Agencia Nacional de Tierras"],
  ["riesgo_baldio", "Indicio de origen en baldío"],
  ["veces_uaf", "Veces la Unidad Agrícola Familiar del municipio"],
  ["microzona_urt", "Microzona focalizada de restitución de tierras"],
  ["pot_categoria", "Categoría del suelo en el plan de ordenamiento"],
  ["pot_categoria_pct", "Superficie del lote en esa categoría (%)"],
  ["pot_rojo_pct", "Superficie del lote en suelo de protección (%)"],
  ["pot_estado_norma", "Estado de la norma urbanística del municipio"],
  ["pot_clasificacion", "Clasificación del suelo"],
  ["ent_mineria_titulos", "Títulos mineros vigentes sobre el lote"],
  ["ent_inundaciones_nina", "Episodios de La Niña que inundaron el lote"],
  ["ent_inundacion_ha_max", "Superficie inundada en el mayor episodio (ha)"],
  ["ent_zip_ha", "Superficie en zona inundable periódica (ha)"],
  ["ent_nino_precip", "Alteración de la lluvia en un Niño típico (% de lo normal)"],
  ["ent_nina_precip", "Excedente de lluvia en una Niña típica (% de lo normal)"],
  ["ent_sequia_retorno", "Periodo de retorno de la sequía meteorológica (años)"],
  ["ent_incendios_5km", "Incendios de cobertura vegetal en cinco kilómetros"],
  ["ent_humedal", "Humedal dentro del lote"],
  ["ent_hidrocarburos", "Bloque de hidrocarburos"],
  ["ent_runap", "Área protegida del Registro Único Nacional"],
  ["ent_resguardo", "Resguardo indígena"],
  ["ent_consejo", "Consejo comunitario titulado"],
  ["ent_paramo", "Páramo delimitado"],
  ["ent_mov_masa", "Amenaza por movimientos en masa"],
  ["ent_sismica", "Amenaza sísmica"],
  ["ctx_pvout", "Producción específica anual del recurso solar (kWh/kWp)"],
  ["ctx_linea_km", "Distancia a la línea de transmisión más cercana (km)"],
  ["ctx_linea_kv", "Tensión de esa línea (kV)"],
  ["ctx_poblado", "Centro poblado más cercano"],
  ["ctx_poblado_km", "Distancia al centro poblado más cercano (km)"],
  ["indice_lote", "Índice de aptitud del lote, descriptor"],
];
function csvFiltrado(){
  const ls = lotesFiltrados();
  const celda = (v) => { const s = v==null ? "" : String(v); return /[;"\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s; };
  const valor = (l, c) => c === "clase" ? claseDe(l)
    : c === "condiciones_del_lote" ? condicionesDe(l).map(x => x.condicion).join(" | ")
    : c === "condiciones_tramites" ? condicionesDe(l).map(x => x.tramite).filter(Boolean).join(" | ")
    : typeof l[c] === "boolean" ? (l[c] ? "sí" : "no")
    : l[c];
  const filas = [COLS_DESCARGA.map(([, r]) => r).join(";")]
    .concat(ls.map(l => COLS_DESCARGA.map(([c]) => celda(valor(l, c))).join(";")));
  descargar(`lotes_${CELDA}_${PERFIL}.csv`, "\ufeff" + filas.join("\n"), "text/csv;charset=utf-8");
}

// ---------- ficha imprimible ----------
function mapaSituacionLote(l, c){
  // Grilla con sus lotes en gris, el lote resaltado y una lupa sobre él.
  const W=520, H=300;
  const todos = lotesCelda();
  const proy = proyector(bboxUnion(c, todos), W, H, 0.06);
  const dCel = pathDe(c.geom, proy), dLot = pathDe(l.geom, proy);
  const otros = todos.filter(x=>x.CODIGO!==l.CODIGO).map(x=>`<path d="${pathDe(x.geom,proy)}" fill="var(--surface-2)" stroke="var(--borde-control)" stroke-width=".6"/>`).join("");
  const cx=(l.bbox[0]+l.bbox[2])/2, cy=(l.bbox[1]+l.bbox[3])/2;
  const [px,py] = proy([cx,cy]);
  const lr=74, lx = px < W/2 ? W-lr-12 : lr+12, ly = py < H/2 ? H-lr-12 : lr+12;
  // La lupa usa un proyector propio; lote y vecinos se pintan en ese sistema.
  const bw=(l.bbox[2]-l.bbox[0]), bh=(l.bbox[3]-l.bbox[1]), r=Math.max(bw,bh)*0.9;
  const proyL = proyector([cx-r, cy-r, cx+r, cy+r], lr*2, lr*2, 0);
  const vecinos = todos.filter(x=>x.CODIGO!==l.CODIGO).map(x=>`<path d="${pathDe(x.geom,proyL)}" fill="var(--surface-2)" stroke="var(--borde-control)" stroke-width=".8"/>`).join("");
  const dLupa = pathDe(l.geom, proyL);
  const zoom = Math.max(1, Math.round((c.bbox[2]-c.bbox[0])/(2*r)));
  return `<svg class="mapa-sit" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    <path d="${dCel}" fill="var(--mapa-tierra)" stroke="var(--borde-control)" stroke-width="1"/>${otros}
    <path d="${dLot}" fill="var(--brand)" fill-opacity=".85" stroke="var(--accent)" stroke-width="1"/>
    <line x1="${px}" y1="${py}" x2="${lx}" y2="${ly}" stroke="var(--brand)" stroke-width=".8" stroke-dasharray="3 2.5" opacity=".55"/>
    <defs><clipPath id="lupa"><circle cx="${lx}" cy="${ly}" r="${lr}"/></clipPath></defs>
    <g clip-path="url(#lupa)"><circle cx="${lx}" cy="${ly}" r="${lr}" fill="#fff"/>
      <g transform="translate(${lx-lr},${ly-lr})">${vecinos}<path d="${dLupa}" fill="var(--brand)" fill-opacity=".85" stroke="var(--accent)" stroke-width="1.2"/></g></g>
    <circle cx="${lx}" cy="${ly}" r="${lr}" fill="none" stroke="var(--brand)" stroke-width="1.8"/>
    <text x="${lx}" y="${ly+lr+13}" text-anchor="middle" class="sit-cap">lote · ×${zoom}</text>
    <text x="10" y="${H-8}" class="sit-cap">grilla ${c.cell_id} · ${esc((c.municipio||"").toLowerCase())}</text></svg>`;
}

// Contexto comun de una ficha, y su cuerpo. Separado del documento que lo envuelve para
// que el cuadernillo pueda repetirlo tantas veces como lotes haya.
function ctxFicha(l){
  const c = celdaActual();
  const marca = document.querySelector(".brand-mark")?.outerHTML || "";
  const hoy = new Date().toLocaleDateString("es-CO",{year:"numeric",month:"long",day:"numeric"});
  const perfil = D.perfiles[PERFIL].etiqueta;
  const reglas = reglasActivas();
  const filtroTxt = reglas.length ? reglas.map(r => r.txt).join("; ") : "ningún criterio aplicado";
  const clase = claseDe(l);
  // La ficha se imprime: usa los valores claros del sistema, los mismos que el visor.
  const pill = ({"Idóneo":{f:"#E4EBF6",t:"#17457A",b:"#1F5FA8",g:"●"},
                 "Viable con gestión":{f:"#F8EEDC",t:"#794D0C",b:"#B0741A",g:"◆"},
                 "No viable":{f:"#F8E6E0",t:"#7E2712",b:"#B03A1E",g:"▲"}})[clase]
                || {f:"#E9ECEC",t:"#4C5A5C",b:"#879596",g:"○"};
  const sem = semaforo(l);
  const col = {rojo:"#9C3A1F", ambar:"#8A5C17", verde:"#2F6B4C", gris:"#5C6B6D"};
  const filas = (pares) => pares.map(([k,v])=>`<div class="dato"><div class="dk">${k}</div><div class="dv">${esc(v)}</div></div>`).join("");
  return fichaCuerpo(l, c, marca, hoy, filtroTxt, clase, pill, sem, col, filas, perfil);
}

// El documento imprimible que envuelve uno o varios cuerpos de ficha.
function docFicha(cuerpo, cuantas){
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>${cuantas>1?`${cuantas} fichas de lote`:"Ficha de lote"} · Métodos Mixtos Consultores</title>
<style>
:root{--brand:#18919C; --accent:#0F6A72; --ink:#1E2829; --ink-2:#49585A; --ink-3:#5C6B6D;
  --line:#DCE2E2; --surface-2:#EAEFF0; --superficie-3:#E4EAEA; --borde-control:#7A8889;
  --aviso:#8A5C17; --aviso-fondo:#F8EFDC; --alerta:#9C3A1F; --alerta-fondo:#F8E7E1; --mapa-tierra:#EDF0F0}
*{box-sizing:border-box}
body{margin:0; padding:26px 30px; font-family:"Segoe UI",system-ui,sans-serif; color:var(--ink); font-size:12px; line-height:1.5; -webkit-print-color-adjust:exact; print-color-adjust:exact}
.cab{display:flex; align-items:flex-start; justify-content:space-between; gap:20px; border-bottom:2px solid var(--brand); padding-bottom:12px; margin-bottom:16px}
.cab-izq{display:flex; align-items:center; gap:11px}
.brand-mark{width:26px; height:28px; flex:none}
.n1{font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--brand); font-weight:700; margin:0}
.n2{font-size:10.5px; color:var(--ink-3); margin:1px 0 0}
h1{font-size:19px; margin:9px 0 2px; letter-spacing:-.01em}
.sub{color:var(--ink-2); margin:0; font-size:12px}
.cod{font-family:ui-monospace,Consolas,monospace; font-size:10px; color:var(--ink-3)}
.chip{display:inline-block; padding:3px 10px; border-radius:11px; font-size:10.5px; font-weight:700; letter-spacing:.05em; text-transform:uppercase}
.idx{text-align:right}
.idx b{font-size:30px; line-height:1; display:block; color:var(--ink)}
.idx span{font-size:10px; color:var(--ink-3); letter-spacing:.06em; text-transform:uppercase; display:block}
.idx em{font-size:11px; color:var(--ink-3); font-style:normal}
h2{font-size:10px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); margin:16px 0 7px; padding-bottom:4px; border-bottom:1px solid var(--line)}
.cols{display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start}
.mapa-sit{width:100%; height:auto; background:#fff; border:1px solid var(--line); border-radius:4px}
.sit-cap{font-size:8px; fill:var(--ink-3); font-family:"Segoe UI",sans-serif; letter-spacing:.04em; text-transform:uppercase}
.sat-caja{position:relative; border:1px solid var(--line); border-radius:4px; overflow:hidden; line-height:0}
.sat-img{width:100%; height:auto; display:block}
.sat-svg{position:absolute; inset:0; width:100%; height:100%}
.sat-cred{position:absolute; right:4px; bottom:3px; font-size:7px; color:#fff; background:rgba(0,0,0,.45); padding:1px 4px; border-radius:2px; text-shadow:0 1px 2px rgba(0,0,0,.7)}
.sat-aviso{font-size:9.5px; color:var(--aviso); background:var(--aviso-fondo); padding:4px 8px; border-radius:0 0 4px 4px; line-height:1.4}
.datos{display:grid; grid-template-columns:repeat(3,1fr); gap:9px 16px; margin-top:3px}
.dato{border-top:1px solid var(--line); padding-top:5px}
.dk{font-size:8.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.dv{font-size:13px; font-variant-numeric:tabular-nums; margin-top:1px}
.motivo{background:var(--surface-2); border-radius:4px; padding:8px 10px; color:var(--ink-2); font-size:11.5px}
.jur{display:grid; grid-template-columns:1fr; gap:6px}
.jf{display:grid; grid-template-columns:10px 1fr; gap:8px; font-size:11px; align-items:start}
.sem{width:9px; height:9px; border-radius:50%; margin-top:4px}
.jf b{font-weight:600} .jf span{color:var(--ink-2)}
.idx-tabla{width:100%; border-collapse:collapse; font-size:10px; margin:4px 0 6px}
.idx-tabla th{font-size:8px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); text-align:left; padding:3px 5px; border-bottom:1px solid var(--line)}
.idx-tabla td{padding:3px 5px; border-bottom:1px solid var(--line)} .idx-tabla tr.reparo td{background:var(--alerta-fondo)} .idx-tabla tr.corto td{background:var(--aviso-fondo)}
.tag-rep{font-size:8px; text-transform:uppercase; color:var(--alerta); font-weight:700} .idx-nota{font-size:9.5px; color:var(--ink-2); margin:2px 0 6px}
.ruta{display:grid; grid-template-columns:1fr 1fr; gap:8px 16px}
.rp{font-size:10.5px; color:var(--ink-2); border-top:1px solid var(--line); padding-top:5px; line-height:1.45}
.rp b{color:var(--ink); font-weight:600}
.pie{margin-top:18px; padding-top:8px; border-top:1px solid var(--line); font-size:9.5px; color:var(--ink-3); display:flex; justify-content:space-between}
__CERT_CSS__
@page{size:A4; margin:12mm}
@media print{.noprint{display:none}}
/* El botón de guardar se queda a la vista al desplazar, y la cabecera reserva su sitio
   para que no se monte sobre la cifra del área catastral. Al imprimir desaparece. */
.noprint{position:fixed; top:10px; right:10px; z-index:5}
.noprint button{padding:8px 14px; border:1px solid var(--line); background:#fff; border-radius:6px;
  cursor:pointer; font-weight:600; box-shadow:0 1px 4px rgba(20,26,26,.18)}
.cab{padding-top:44px}
@media print{.cab{padding-top:0}}
/* Una ficha por pagina en el cuadernillo. */
.salto{break-after:page; page-break-after:always; height:0}
</style></head><body>
<div class="noprint"><button onclick="window.print()">Guardar como PDF</button></div>
${cuerpo}
</body></html>`;
}

// Ficha suelta: un cuerpo dentro del documento, en su propia ventana.
function ficha(l){
  const w = window.open("", "_blank", "width=900,height=1100");
  // Devuelve false y no avisa: quien llama decide si es una ficha suelta o un
  // cuadernillo, y en un cuadernillo un aviso por ficha seria insufrible.
  if(!w) return false;
  w.document.write(docFicha(ctxFicha(l), 1));
  w.document.close();
}

// El cuerpo de una ficha, sin el documento que la envuelve. Se usa para la ficha suelta
// y para el cuadernillo de varias, que es un solo documento con una ficha por pagina.
function fichaCuerpo(l, c, marca, hoy, filtroTxt, clase, pill, sem, col, filas, perfil){
  return `<div class="cab">
  <div><div class="cab-izq">${marca}<div><p class="n1">Métodos Mixtos Consultores</p><p class="n2">Prospectos solares · ficha de lote · ${esc(perfil)}</p></div></div>
    <h1>${esc(l.municipio)}, ${esc(l.departamento||"")}</h1>
    <p class="sub">Grilla ${c.cell_id}${c.vereda?" · vereda "+esc(c.vereda):""} · ${esc(l.destino||"sin destino declarado")}</p>
    <div class="cod">código catastral ${l.CODIGO}</div>
    <div class="cod">predial anterior ${esc(l.numero_predial_anterior||"sin dato")}</div>
    <span class="chip" style="background:${pill.f};color:${pill.t};border:1px solid ${pill.b}">${pill.g} ${clase}</span></div>
  <div class="idx"><b>${fmt(l.area_ha,1)}</b><span>ha de área catastral</span><em>${fmt(l.mwp_lote,1)} MWp indicativos</em></div>
</div>
<div class="cols">
  <div><h2>Dónde está</h2>${mapaSituacionLote(l,c)}</div>
  <div><h2>Imagen satelital de alta resolución</h2>${vistaSatelital(l)}</div>
</div>

<h2>${clase==="No viable" ? "Por qué el lote no es viable" : "Condiciones del lote y trámite que exige cada una"}</h2>
${bloqueCondiciones(l)}
${bloqueAvisos(l)}
<h2>Variables de decisión</h2>
<div class="datos">${filas(loQueSeDecide(l))}</div>
<div class="motivo">${esc(l.motivo||"")} ${l.cabe_utility?"El área y el ancho alcanzan la referencia de escala utility ("+fmt0(D.perfiles.utility?.ha_proyecto)+" ha).":l.cabe_distribuida?"El área y el ancho alcanzan la referencia de generación distribuida ("+fmt0(D.perfiles.distribuida?.ha_proyecto)+" ha), no la de escala utility.":"No alcanza el área de referencia de ninguno de los dos perfiles."}</div>
<h2>Dimensiones y forma del lote</h2>
<div class="datos">${filas([["Área catastral del lote",fmt(l.area_ha,1)+" ha"],["Potencia instalable indicativa",fmt(l.mwp_lote,1)+" MWp"],["Diámetro del mayor círculo inscrito",fmt0(l.ancho_util_m)+" m"],["Compacidad de la forma, de 0 a 1",fmt(l.compacidad,2)],["Área registrada en el catastro",fmt(l.area_terreno_catastro_m2/1e4,1)+" ha"],["Alargamiento del lote",fmt(l.alargamiento,2)+" a 1"],["Llenado del rectángulo envolvente",fmt(l.llenado_rect,2)],["Superficie de los lotes colindantes",fmt(l.ha_pegadas,0)+" ha"]])}</div>
<div class="motivo">Potencia instalable indicativa: el área catastral del lote entre ${fmt(D.ha_por_mwp,2)} ha por MWp. Esa huella es una referencia de ingeniería para planta en suelo con seguidor de un eje; no la publica ninguna entidad colombiana. La cobertura y la pendiente se describen aparte, no se descuentan de esta cifra.</div>
<h2>Terreno</h2>
<div class="datos">${filas([["Pendiente media",fmt(l.pendiente_media,1)+"°"],["Pendiente p90",fmt(l.pendiente_p90,1)+"°"],["Rugosidad del relieve",fmt(l.rugosidad_m,1)+" m"],["Desnivel total dentro del lote",fmt(l.desnivel_total_m,1)+" m"],["Elevación media",fmt0(l.elevacion_media)+" m"],["Superficie construida registrada en el catastro",fmt0(l.area_construida_m2)+" m²"]])}</div>
<h2>Cobertura del suelo</h2>
<div class="datos">${filas(coberturaDe(l).length ? coberturaDe(l).map(([v,nom]) => [nom.charAt(0).toUpperCase()+nom.slice(1), fmt(v,1)+" %"]) : [["Clases medidas en el lote","sin dato"]])}</div>
<div class="motivo">Porcentaje del lote en cada clase de ESA WorldCover 2021, a 10 m de resolución, recortada con el polígono del lote. Cifras de la propia clasificación: no se ponderan ni se combinan en ningún índice.</div>
<h2>Acceso y conexión eléctrica</h2>
<div class="datos">${filas([["Distancia a vía carrozable",fmt(l.dist_via_km,2)+" km"],["Distancia a vía principal",fmt(l.dist_via_principal_km,1)+" km"],["Subestación de conexión",l.conexion_nombre||"sin dato"],["Tensión de la subestación",l.conexion_kv?fmt0(l.conexion_kv)+" kV":"sin dato"],["Distancia a la subestación de conexión",fmt(l.conexion_km,1)+" km"],["Operador de red de la subestación",c.operador||"sin dato"]])}</div>
<div class="motivo">Estas variables son prácticamente iguales para todos los lotes de esta grilla: se miden en la celda o en su punto de conexión, no en el lindero del lote.</div>
<h2>Recurso solar y clima en el punto del lote</h2>
<div class="datos">${filas(contexto(l))}</div>
<div class="motivo">Recurso solar y clima: prácticamente iguales para todos los lotes de esta grilla; el modelo tiene 250 m de resolución y la celda mide 5 km de lado.</div>
<div class="motivo">Recurso del Global Solar Atlas (modelo Solargis, promedios anuales de largo plazo, 250 m, en el centroide del lote): ${RECURSO_DEF.map(([k,sig,u,d])=>"<b>"+sig+"</b> ("+u+"): "+d).join(" ")}</div>
<h2>Valor catastral de referencia del suelo</h2>
<div class="datos">${filas([["Valor catastral de referencia del lote", l.valor_ref_cop!=null?fmtM(l.valor_ref_cop)+"$":"sin dato"],["Valor catastral por hectárea, de la zona geoeconómica", l.valor_ref_cop_ha!=null?fmtM(l.valor_ref_cop_ha)+"$":"sin zona geoeconómica"],["Confianza del valor", l.valor_confianza||"sin dato"],["Zonas geoeconómicas del IGAC", fmtZonas(l.zonas_economicas)],["Banda de la ANT para el municipio", l.ant_banda||"sin dato"],["Nombre del lote en el catastro", l.nombre_predio||"sin nombre en el catastro"]])}</div>
<div class="motivo">Avalúo catastral de referencia, no precio de mercado. En municipios con catastro desactualizado queda muy por debajo del comercial; la banda ANT es el contraste. La valorización comercial se hace sobre la lista corta.</div>
<h2>Norma urbanística municipal (Plan de Ordenamiento Territorial)</h2>
<div class="jur">${normaUrbana(l).map(([k,t,d])=>`<div class="jf"><div class="sem" style="background:${col[k]||col.gris}"></div><div><b>${t}</b>${d?"<br><span>"+d+"</span>":""}</div></div>`).join("")}</div>
<h2>Verificación jurídica preliminar</h2>
<div class="jur">${sem.map(([k,t,d])=>`<div class="jf"><div class="sem" style="background:${col[k]}"></div><div><b>${t}</b><br><span>${d}</span></div></div>`).join("")}</div>
<h2>Entorno ambiental y de riesgo</h2>
<div class="jur">${entorno(l).map(([k,t,d])=>`<div class="jf"><div class="sem" style="background:${col[k]||col.gris}"></div><div><b>${t}</b>${d?"<br><span>"+d+"</span>":""}</div></div>`).join("")}</div>
<h2>Cruces cartográficos verificados</h2>
<div class="jur">${[[(l.ent_mineria_titulos||0)===0,"Sin títulos mineros vigentes (ANM)","Con título minero vigente (ANM)"],[!(l.ent_runap_ha>0),"Fuera del RUNAP","Dentro de un área protegida del RUNAP"],[!(l.ent_resguardo_ha>0),"Fuera de resguardo indígena","Sobre resguardo indígena"],[!(l.ent_consejo_ha>0),"Fuera de consejo comunitario","Sobre consejo comunitario"],[!(l.ent_paramo_ha>0),"Fuera de páramo delimitado","Sobre páramo delimitado"],[String(l.clase_suelo||"rural")==="rural","Suelo rural","Suelo urbano o de expansión"]].map(([ok,tOk,tNo])=>`<div class="jf"><div class="sem" style="background:${ok?col.verde:col.ambar}"></div><div><b>${ok?tOk:tNo}</b></div></div>`).join("")}</div>
<div class="motivo">Constancia del cruce cartográfico${l.ent_fecha?", consultado el "+esc(fmtFecha(l.ent_fecha)):""}. Una casilla en ámbar significa que la figura sí toca el lote: en ese caso aparece arriba, entre las condiciones del lote, con su trámite.</div>
<h2>Índice de aptitud del lote: descriptor técnico</h2>${tablaIndice(l)}
${bloqueCertificado(l, true)}
<h2>Ruta de adquisición</h2>
<div class="ruta">
  <div class="rp"><b>1. Matrícula inmobiliaria.</b> ${textoMatricula(l)}</div>
  <div class="rp"><b>2. Certificado de tradición y libertad.</b> ${fmtCop(D.costo_certificado)} el electrónico, Resolución 2026-001726 de la Superintendencia de Notariado y Registro. Se lee con el semáforo automático: propietario, hipotecas, embargos, sucesiones, falsa tradición y, decisivo aquí, si el origen es baldío adjudicado.</div>
  <div class="rp"><b>3. Instrumento.</b> ${l.riesgo_baldio ? "El lote supera la UAF ×"+fmt(l.veces_uaf,0)+": si el certificado muestra origen en baldío, el artículo 72 de la Ley 160 de 1994 sanciona con nulidad la adquisición que acumule por encima de la Unidad Agrícola Familiar y se estructura con arriendo de largo plazo o usufructo. Si el origen es privado, compra directa con el estudio de títulos ordinario." : "Dentro de la UAF: la compra directa es viable si el certificado de tradición y libertad no muestra gravámenes ni limitaciones al dominio. El arriendo de largo plazo es la alternativa habitual, y cuál conviene se decide con el certificado a la vista."}</div>
  <div class="rp"><b>4. Cierre.</b> Estudio de títulos de 20 años sobre folios verdes y ámbar. Los costos del cierre se calculan sobre el valor del acto: como referencia de mercado se manejan notariales del orden del 0,3%, registro del 0,5 al 1%, derechos de la ORIP entre 8,7 y 12,7 por mil e impuesto de timbre del 0 al 3% según cuantía. Estas cifras no se han contrastado con la resolución de tarifas del año en curso y se confirman con el notario y la oficina de registro antes de presupuestar. El plazo de escritura y registro depende de la oficina y no se ha medido en estos municipios.</div>
</div>
<div class="pie"><span>Métodos Mixtos Consultores · ficha generada el ${hoy} · filtro del visor: ${filtroTxt}</span><span>catastro IGAC · Copernicus DEM · ESA WorldCover · Global Solar Atlas · OSM · UPME · ANT · URT · IGAC POT · SIAC · ANM · SNR · Esri World Imagery</span></div>
`;
}

// Cuadernillo: todas las fichas filtradas en UN solo documento, una por pagina, y el
// dialogo de impresion se abre solo. Antes se abria una pestaña por lote, y el navegador
// bloqueaba a partir de la segunda; asi sale un unico PDF con todos.
function fichasPDF(){
  const ls = lotesFiltrados();
  if(!ls.length){ alert("No hay lotes que cumplan los criterios."); return; }
  if(ls.length > 60 && !confirm(
      `Se va a preparar un documento con ${ls.length} fichas, una por página.

`
      + `Con muchas fichas puede tardar y pesar bastante. ¿Continuar?`)) return;

  const btn = $("#f-fichas"), txt = btn.textContent;
  btn.disabled = true; btn.textContent = `Preparando ${ls.length} fichas`;
  const w = window.open("", "_blank");
  if(!w){
    btn.disabled = false; btn.textContent = txt;
    alert("El navegador bloqueó la ventana. Permite las ventanas emergentes de esta página.");
    return;
  }
  const cuerpos = ls.map(l => ctxFicha(l)).join('<div class="salto"></div>');
  w.document.write(docFicha(cuerpos, ls.length));
  w.document.close();
  btn.disabled = false; btn.textContent = txt;
  // Se espera a que carguen las imágenes; si no, el PDF sale con recuadros vacíos.
  w.addEventListener("load", () => setTimeout(() => w.print(), 600));
}

// ---------- arranque ----------
function pintarFuentes(){
  $("#fuentes-tabla").innerHTML = `<thead><tr><th>Fuente</th><th>Qué aporta</th><th>Versión o corte</th><th>Ver</th><th>Dirección técnica del geoservicio</th></tr></thead><tbody>` +
    (D.fuentes||[]).map(f=>`<tr><td><b>${esc(f.fuente)}</b></td><td>${esc(f.aporta)}</td><td>${esc(f.version)}</td><td class="ver">${f.portal?`<a href="${esc(f.portal)}" target="_blank" rel="noopener">visor oficial</a>`:"sin visor público"}</td><td><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.url.replace(/^https?:\/\//,""))}</a></td></tr>`).join("") + `</tbody>`;
}
// Lo que una tabla de una línea por fuente no puede decir: cómo se clasifica un lote,
// cómo se lee la norma urbanística y dónde no hay dato. Va bajo el cuadro de fuentes.
function pintarNotasFuentes(){
  const n = $("#notas-fuentes"); if(!n) return;
  n.innerHTML = (D.notas_fuentes||[]).map(b =>
    `<div class="nota-bloque"><h3>${esc(b.titulo)}</h3>`
    + (b.parrafos||[]).map(p => `<p>${esc(p)}</p>`).join("") + `</div>`).join("");
  const o = $("#origen-nota");
  if(o){ o.textContent = D.origen_nota || ""; o.hidden = !D.origen_nota; }
}
function pintarTodo(){ pintarControles(); pintarCriterios(); pintarMapa(); pintarTabla(); pintarDetalle(); pintarFuentes(); pintarNotasFuentes(); }
// Los controles se cablean desde el catálogo, de modo que añadir un criterio no obliga
// a tocar el arranque.
for(const c of CASILLAS){ const e = $("#"+c.id); if(e) e.onchange = () => { leerFiltro(); refrescar(); }; }
for(const u of UMBRALES){
  const e = $("#"+u.id); if(!e) continue;
  e.oninput = () => { leerFiltro(); if(["f-ha-min","f-ha-max","f-ancho"].includes(u.id)) F.preajuste = null; refrescar(); };
}
$("#f-csv").onclick = csvFiltrado;

// Fichas en tanda. El navegador limita cuantas ventanas se abren de golpe y las
// trata como emergentes, asi que se espacian y se avisa si el navegador corta.
const TANDA_MAX = 25;      // por encima de esto conviene filtrar antes
const TANDA_PAUSA = 700;   // ms entre fichas: sin pausa el navegador descarta las ultimas

async function fichasEnTanda(){
  const ls = lotesFiltrados();
  if(!ls.length){ alert("No hay lotes que cumplan los criterios. Suelta algún criterio y vuelve a intentarlo."); return; }
  if(ls.length > TANDA_MAX && !confirm(
      `Se van a abrir ${ls.length} fichas, una por pestaña. El navegador puede bloquear las últimas.\n\n`
      + `Conviene filtrar hasta dejar ${TANDA_MAX} o menos. ¿Continuar de todos modos?`)) return;

  const btn = $("#f-fichas");
  const txt = btn.textContent;
  btn.disabled = true;
  let abiertas = 0;
  for(let i = 0; i < ls.length; i++){
    btn.textContent = `Abriendo ficha ${i+1} de ${ls.length}`;
    const antes = ficha(ls[i]);
    if(antes === false){ break; }      // el navegador bloqueo la ventana
    abiertas++;
    if(i < ls.length - 1) await new Promise(r => setTimeout(r, TANDA_PAUSA));
  }
  btn.disabled = false;
  btn.textContent = txt;
  if(abiertas < ls.length)
    alert(`Se abrieron ${abiertas} de ${ls.length} fichas. El navegador bloqueó el resto.\n\n`
        + `Permite las ventanas emergentes de esta página y vuelve a intentarlo, o filtra para reducir la lista.`);
}
$("#f-fichas").onclick = fichasPDF;

// La definicion de las tres clases se pliega. Se recuerda en el navegador para que
// quien la despliegue no tenga que hacerlo en cada grilla que abra.
function plegable(idSec, idBtn, clave, abrir, cerrar){
  const sec = $(idSec), btn = $(idBtn);
  if(!sec || !btn) return;
  let abierta = false;
  try { abierta = localStorage.getItem(clave) === "1"; } catch(e){}
  const pintar = () => {
    sec.classList.toggle("abierta", abierta);
    btn.setAttribute("aria-expanded", String(abierta));
    btn.textContent = abierta ? cerrar : abrir;
  };
  btn.onclick = () => {
    abierta = !abierta;
    try { localStorage.setItem(clave, abierta ? "1" : "0"); } catch(e){}
    pintar();
  };
  pintar();
}
plegable("#proceso", "#proceso-plegar", "proceso-abierto",
         "Mostrar el proceso y las fuentes", "Ocultar el proceso y las fuentes");
(function(){
  const sec = $("#clases"), btn = $("#clases-plegar");
  if(!sec || !btn) return;
  let abierta = false;
  try { abierta = localStorage.getItem("clases-abierta") === "1"; } catch(e){}
  const pintar = () => {
    sec.classList.toggle("abierta", abierta);
    btn.setAttribute("aria-expanded", String(abierta));
    btn.textContent = abierta ? "Ocultar la definición de las tres clases"
                              : "Mostrar la definición de las tres clases";
  };
  btn.onclick = () => {
    abierta = !abierta;
    try { localStorage.setItem("clases-abierta", abierta ? "1" : "0"); } catch(e){}
    pintar();
  };
  pintar();
})();
$("#det-cerrar").onclick = () => { LOTE=null; pintarTabla(); pintarMapa(); pintarDetalle(); };
// La ficha es una capa: se cierra pulsando fuera o con Escape, como cualquier otra.
$("#velo-ficha").onclick = () => { if(LOTE){ LOTE=null; pintarTabla(); pintarMapa(); pintarDetalle(); } };
document.addEventListener("keydown", e => {
  if(e.key === "Escape" && LOTE){ LOTE=null; pintarTabla(); pintarMapa(); pintarDetalle(); }
});
$("#f-reset").onclick = () => {
  for(const u of UMBRALES) V[u.id] = null;
  for(const c of CASILLAS) C[c.id] = false;
  F.preajuste = "todos"; escribirFiltro(); refrescar();
};
// La banda de criterios arranca plegada: la lista empieza arriba de la pantalla.
$("#cri-plegar").onclick = () => {
  const abierto = $("#cri-cuerpo").hidden;
  $("#cri-cuerpo").hidden = !abierto;
  $("#cri-plegar").setAttribute("aria-expanded", String(abierto));
  $("#cri-plegar").textContent = abierto ? "Ocultar los criterios de filtrado" : "Mostrar los criterios de filtrado";
};
(function(){
  for(const u of UMBRALES) V[u.id] = null;
  for(const c of CASILLAS) C[c.id] = false;
  // Se abre SIN restriccion de tamano. Arrancar con el preajuste del perfil dejaba 8
  // lotes a la vista, y quien abre el reporte por primera vez no tiene modo de
  // saber que esta viendo una fraccion. El tamano acota la busqueda al proyecto que se
  // quiere construir, asi que lo elige quien lee, no el reporte por el.
  F.preajuste = "todos"; escribirFiltro();
  const orden = [...D.celdas].sort((a,b)=>(a.ranking??999)-(b.ranking??999));
  // Arranca en la primera grilla con lotes en el perfil inicial.
  const con = orden.find(c => (D.lotes[PERFIL]||[]).some(l=>l.cell_id===c.cell_id));
  CELDA = (con||orden[0]||{}).cell_id || null;
  pintarTodo();
})();
</script>
</body>
</html>
"""


HTML = (_TPL
        .replace("__CERT_CSS__", _CERT_CSS)
        .replace("__CRITERIOS__", criterios_html())
        .replace("__CLASES__", clases_html())
        .replace("__PROCESO__", proceso_html())
        .replace("__GLOSARIO__", glosario_html())
        .replace("__CAT_FILTROS__", _js(FILTROS))
        .replace("__CAT_GRUPOS__", _js([{"clave": c, "rotulo": r} for c, r, _d in GRUPOS]))
        .replace("__CAT_CLASES__", _js(CLASES_DEF))
        .replace("__CAT_ADQUISICION__", _js([{"titulo": t, "detalle": d}
                                             for t, d in VERIFICACIONES_PREVIAS])))
