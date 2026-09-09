# Del cuadro de 25 km² al lote que se visita

El reporte de grillas dice en qué cuadrícula vale la pena mirar. Este bloque contesta la
pregunta siguiente, que es la que sirve para salir a campo: **cuál de los lotes de esa
cuadrícula puede alojar el proyecto**.

Igual que el reporte, no depende de que sean estas cien celdas. Lee las candidatas que
haya, consulta el catastro de cada una y aplica el mismo procedimiento.

---

## Correrlo sobre las grillas que uno elija

El insumo es **el archivo que se baja del reporte de grillas**: se marcan las grillas
que se quieren explorar, se pulsa el botón de descarga y sale
`grillas_para_predios.geojson` (o `.csv`; los dos sirven). Se guarda dentro de la
carpeta del proyecto, por ejemplo en `outputs/reporte/`, y se le pasa la ruta. Da igual
si son 5, 10 o 40 grillas.

Son dos pasos:

| Paso | Qué hace | Cuándo hace falta |
|---|---|---|
| **A. Evaluar los lotes** | baja el catastro de esas grillas, mide el terreno y clasifica | solo si las grillas son nuevas (el modelo se volvió a correr) |
| **B. Generar el visor** | arma el reporte navegable con esos lotes | siempre; tarda un minuto |

Si las grillas están entre las cien del reporte, sus lotes ya están evaluados y se va
directo al paso B.

**Paso A**, en el cuaderno `2. IGAC_Consulta_Predios.ipynb`, que es la vía recomendada
la primera vez porque muestra las comprobaciones intermedias: en la sección 2 hay una
única línea que cambiar, `CELDAS = "outputs/reporte/grillas_para_predios.geojson"`, y se
ejecuta todo. O sin abrir Jupyter:

```bash
.venv/Scripts/python -m predios.lotes --celdas outputs/reporte/grillas_para_predios.geojson
```

**Paso B**:

```bash
.venv/Scripts/python -m reporte_predios --grillas outputs/reporte/grillas_para_predios.geojson
```

Si se salta el paso A por error, el B lo detecta y dice qué comando falta y para qué
grillas. Y sin archivo (`--celdas` o `--grillas` vacíos) los dos trabajan las cien del
reporte, o una lista de códigos: `--celdas 0010222,0009539`.

La descarga del catastro se cachea en `data/igac/`, así que la segunda corrida no vuelve
a pedirle nada al IGAC. El DEM y la cobertura se cachean igual en `data/dem/` y
`data/cobertura/`.

---

## Las tres piezas

| Módulo | Qué hace |
|---|---|
| `predios/predios_igac.py` | baja los lotes del catastro nacional |
| `predios/terreno.py` | mide pendiente y cobertura de cada lote |
| `predios/lotes.py` | filtra, puntúa y clasifica |

### El catastro

Del FeatureServer público del gestor IGAC, capas 14 (rural) y 7 (urbano), más las tablas
17 (REGISTRO_1: área y destino económico) y 18 (REGISTRO_2: zonas y construcciones). El
IGAC publica **un servicio por corte mensual** (`Base_Catastral_Publica_del_Gestor_IGAC_MM_AAAA`;
hoy el de 30 de junio de 2026, constante `CORTE` en `predios_igac.py`); al cambiar el corte,
las grillas descargadas con el anterior vuelven a quedar pendientes y se bajan de nuevo. Se
pagina de a 1000 registros y se pide por códigos en lotes de 250, que es donde el
servicio deja de devolver error 400. Solo cubre municipios cuyo catastro lleva el IGAC:
donde hay gestor propio (Sabanalarga, Barranquilla, Malambo, Galapa, Puerto Colombia...)
el servicio no trae lotes y el visor lo dice, con el nombre del gestor
(`CAPA_GESTORES_10062026`).

Cada lote es lo que el catastro llama predio: una unidad de tierra continua, con un
número predial de 30 dígitos y un mismo titular (persona o comunidad), que no coincide
necesariamente con una sola escritura ni con una sola matrícula. Se toma el polígono
completo aunque cruce el borde de la grilla, y se le imputan todos los datos como uno solo.

Lo que entrega son diez campos. **Ni el propietario ni la matrícula inmobiliaria están
entre ellos**: el titular y el historial viven en la Superintendencia de Notariado y
Registro, que se consulta por matrícula y de a un lote por vez; la matrícula se obtiene
con el número predial por derecho de petición (`predios/registro.py`).

### El terreno

Copernicus DEM GLO-30 para la pendiente y ESA WorldCover 2021 para la cobertura, ambos
leídos por ventana sobre el COG, así que se descarga solo el recorte que hace falta y no
la tesela entera. La pendiente sale del gradiente del DEM con 300 m de holgura alrededor
de la celda, para que el borde no quede mal calculado.

Advertencia sobre esa pendiente: el GLO-30 es un modelo de **superficie**, no de terreno.
Sobre bosque cerrado mide la copa y la pendiente sale alta por una razón que no es el
relieve. Importa poco en la práctica, porque la cobertura arbolada ya descuenta ese
lote por otro lado; no debe leerse como pendiente del suelo.

### El filtro

Tres bloques en orden, y el primero que descarta escribe el motivo en la fila:

1. **Excluyentes.** Lote de la capa urbana, destino habitacional, o celda excluida por
   el reporte (área protegida del RUNAP, territorio en disputa). La Reserva Forestal de
   Ley 2ª se cruza y se informa pero ya no excluye: el POT del lote la trae como categoría
   propia y ahí se lee (`LEY2_EXCLUYE = False`, decisión de agosto de 2026).
2. **Tamaño y forma.** El tamaño es el **área del lote** (el polígono catastral
   completo, medido en CRS métrico) y se describe con lo que se mide dentro: fracción de
   cobertura apta, bosque y construido (WorldCover), pendiente (Copernicus DEM) y el ancho
   del mayor círculo inscrito. **El tamaño no descarta**: el área que busca el proyecto la
   define quien mira, en el visor (decisión de Samuel, agosto de 2026), para no perder
   lotes útiles por un umbral fijo. La cobertura y la pendiente se muestran, no se
   descuentan en un "área útil": ese cálculo (núcleo a 30 m × cobertura apta × factor de
   pendiente) es una heurística propia sin fuente externa y queda solo como columna
   auxiliar `area_util_ha` del CSV. La potencia indicativa es área del lote entre las
   hectáreas por MWp calibradas con las plantas del registro de XM (`mwp_lote`), y
   `mwp_apto` aplica además la fracción apta. El código anota si el lote alcanza cada
   perfil de referencia (`cabe_utility`: 150 ha y 387 m; `cabe_distribuida`: 2 ha y 45 m)
   y solo aparta, como clase **Pequeño**, los lotes con menos de 2 ha
   (`HA_MINIMA_CARACTERIZAR`, ajustable con `--ha-minima`), que no alojan ni 2 MW; esos
   quedan medidos en el CSV de descartes.
3. **Puntaje.** Los mismos criterios del reporte de grillas, con los valores medidos en
   el lote en lugar de los de la celda. El criterio sin dato no se inventa: sale del
   promedio, y la fila deja escrito con cuántos criterios se puntuó.
4. **Segunda criba**, con lo que solo se sabe tras consultar el entorno y el POT del lote
   (`recribar`): un **título minero vigente** (ANM) excluye, porque prevalece sobre el uso
   del suelo; una **figura territorial** (RUNAP, resguardo indígena, consejo comunitario,
   páramo delimitado) con solape real (≥ 1 ha o 2% del lote) excluye, como en el reporte
   de grillas pero ahora medida en el polígono; **suelo de protección dominante según el
   POT** baja el lote a Con reparos hasta que un certificado de uso del suelo diga otra
   cosa, porque los usos prohibidos no están publicados por máquina y el reparto de área
   puede dejar una porción productiva.

**Qué decide la clase.** Un criterio más allá de su límite (la columna "vale 0" de la
tabla de umbrales) deja el lote **Con reparos** y dice cuál es la gestión pendiente; sin
reparos, índice de 70 o más es **Idóneo** y por debajo **Viable**. El visor muestra para
cada lote la tabla de los siete criterios con su valor, los tres umbrales del perfil, la
nota de 0 a 100 y el peso, y el índice se reconstruye en el navegador con la misma
fórmula que en Python (coinciden al entero). El tamaño, el valor, lo jurídico y el
entorno no entran en el índice; se muestran aparte con su semáforo.

**Los umbrales del lote se calibran a escala de lote.** Los de la matriz de grillas salen
de celdas de 5 km con planta, y un lote medido en su polígono siempre sale mejor que el
promedio de su celda; compararlo contra umbrales de celda inflaba el índice. Por eso los
cinco criterios de terreno y acceso (distancia a subestación, cobertura, pendiente,
rugosidad, distancia a vía) usan percentiles 10/50/90 medidos en los **lotes catastrales
donde están las plantas reales** del registro de XM (`soporte/calibracion/umbrales_lote.py`:
se ubica el lote bajo el punto de cada planta en el catastro público, se mide con el mismo
código de `predios/`, y en municipios de gestor propio se usa una huella aproximada).
Recurso y capacidad conservan la escala de grilla: no varían dentro de ella. Los números
viven en `PERFILES[perfil]["umbrales_lote"]` (reporte/datos.py) y se regeneran con
`python -m soporte.calibracion umbrales_lote`.

De ahí salen las clases **Idóneo**, **Viable** y **Con reparos** (todas caracterizadas
por completo y visibles en el visor), **Pequeño** (menos de 2 ha brutas, solo medido),
**No apto** (sin medida de terreno) y **Excluido** (bloques 1 y 4).

---

## Los dos perfiles

Los mismos del reporte, y cambian el resultado por completo:

| | utility | distribuida |
|---|---|---|
| tamaño de referencia | 150 ha, 387 m de ancho | 2 ha, 45 m de ancho |
| proyecto | 50 MW | 2 MW |
| conexión | 57,5 a 230 kV | hasta 115 kV |

El perfil ya no criba por tamaño: cambia el punto de conexión que se busca, la capacidad
de barra que se puntúa y el preajuste inicial del filtro del visor. Los dos perfiles
caracterizan los mismos lotes.

---

## Qué sale

En `outputs/reporte/`, por cada perfil:

| Archivo | Contenido |
|---|---|
| `lotes_<perfil>.csv` | los caracterizados (≥ 2 ha brutas, no excluidos), ordenados por clase e índice |
| `lotes_<perfil>.geojson` | los mismos con su polígono, simplificado a 1 m |
| `lotes_<perfil>_descartados.csv` | Pequeños, No aptos y Excluidos, **cada uno con su motivo** |

El archivo de descartados no es un residuo. Es la defensa del método: permite responder
por qué no aparece un lote que alguien esperaba ver, sin volver a correr nada.

---

---

## Del lote al título

Tener el lote no es tenerlo comprable. Lo que decide si el proyecto se puede construir y
financiar está en el registro, no en el catastro: quién es el dueño, si hay hipoteca,
embargo, sucesión sin liquidar o **falsa tradición**, que en Córdoba y Sucre es frecuente
y deja al lote sin título pleno, así que no se puede hipotecar ni dar en garantía y el
cierre financiero no ocurre.

El catastro no publica la matrícula inmobiliaria, y sin matrícula no hay certificado. La
consulta gratuita de la SNR acepta la referencia catastral, pero exige cuenta y captcha,
o sea que está hecha para consultas de a una; y el portal de compra del certificado es un
formulario con estado en el servidor, sin enlace con la matrícula como parámetro. Para
una lista de lotes la vía es el derecho de petición:

```bash
python -m predios.registro --perfil utility
python -m predios.registro --perfil utility --lista lotes_0011446_utility.csv   # el CSV que descarga el visor con el filtro puesto
```

Cuando la SNR responda, las matrículas se anotan en `data/registro/matriculas.csv`
(`CODIGO;matricula_inmobiliaria;fuente;fecha`; es insumo y va al bucket, conjunto
`registro`) y el visor las cruza solo: la ficha muestra la matrícula y el botón la copia
al portapapeles y abre el portal de la SNR, donde se pega y se paga.

Deja dos archivos en `outputs/reporte/`: el anexo con los números prediales de 30 dígitos
y la columna de matrícula abierta para que la llene la entidad, y el texto de la petición
listo para radicar. El término legal es de **diez días hábiles**, por ser petición de
información, y vencido opera silencio positivo.

La petición va por la lista completa: la matrícula es gratuita y el costo llega al comprar
los certificados, donde sí se recorta:

```bash
python -m predios.registro --perfil utility --solo limpios
```

### Banderas de adquisición

Las columnas `estorbos` y `gestion` marcan lo que ya se ve en los datos abiertos: más de
2.000 m² construidos, bosque sobre el 10%, área del catastro que no cuadra con la
geometría, Ley 2ª, o destino económico sin declarar.

Son banderas, no exclusiones. Un lote con bosque se sigue negociando; lo que no se vale
es enterarse el día de la visita. El umbral de construcción no es «cualquier
construcción» porque la mediana son 553 m², que es la casa de la finca y no un
impedimento.

---

### La ficha del lote: qué trae y de dónde

Sobre los lotes caracterizados (≥ 2 ha brutas, no excluidos) corren cuatro módulos
más, cada uno con caché en `data/` y respaldo en el bucket, y sus columnas llegan al CSV,
al visor y a la ficha PDF. Las consultas por polígono (minería, POT) van por POST con la
geometría simplificada a 5 m, porque hay lotes del IGAC de cientos de miles de vértices;
la capa que no responde queda anotada como error en la caché y se reintenta sola en la
siguiente corrida, sin repetir las que sí respondieron.

| Sección | Módulo | Fuente probada | Qué responde |
|---|---|---|---|
| Norma urbana | `predios/pot.py` | IGAC, geoservicios LADM-COL POT (761 municipios): zonificación rural, clasificación y acto, POT municipal | categoría del suelo con reparto de área por el polígono, uso principal, semáforo, acto administrativo vigente |
| Valor de referencia | `predios/valor.py` | IGAC zonas geoeconómicas 2026 (26 de 28 municipios) ponderadas por área según REGISTRO_2; banda ANT | valor catastral por ha y total, cobertura, contraste ANT y confianza |
| Entorno | `predios/entorno.py` | IDEAM (drenajes, inundación 2011), MADS (humedales, Ley 2ª, POMCA), UPRA (frontera), IGAC (clase agrológica), ANM (minería), ANH (hidrocarburos), SGC (sísmica, movimientos en masa) | 12 cruces por lote, semáforo |
| Catastro ampliado | `predios/predios_igac.py` REGISTRO_2 | IGAC | nombre del lote (catastro), zonas económicas, construcciones (uso, puntaje, área) |
| Figuras territoriales | `predios/entorno.py` (capas runap, resguardo, consejo_comunitario, paramo) | RUNAP vivo de Parques Nacionales (WFS); resguardos y consejos comunitarios de la ANT (datos abiertos a 25-jun-2026); páramos de la capa institucional del MADS | nombre y hectáreas de solape con el polígono del lote; solape ≥ 1 ha o 2% del área excluye (`recribar`), menor se anota como desajuste de linderos |
| El Niño y La Niña | `predios/entorno.py` (inundacion_1988...2020_2022, zip_2022, nino_precip, nina_precip, sequia_retorno, incendios_5km) | IDEAM: manchas de inundación observadas en seis episodios de La Niña, zonas inundables periódicamente 2022, alteración de la lluvia en Niño y Niña típicos (1981-2010), periodo de retorno de la sequía, incendios de cobertura vegetal | en cuántos episodios se inundó el lote y cuántas hectáreas; hectáreas inundables periódicamente y de cuerpo de agua; déficit o excedente de lluvia esperado; años entre sequías; incendios en 5 km |
| Recurso y contexto | `predios/contexto.py` | Global Solar Atlas (API de largo plazo, 250 m) en el centroide; líneas de transmisión de OSM (`insumos/lineas`); nodos place de OSM por Overpass alrededor de la grilla | PVOUT, GHI, DNI, DIF, OPTA y temperatura del lote; distancia del lindero a la línea más cercana y su tensión; centro poblado y caserío más cercanos con distancia |

Regla de cribado que sale de la investigación: **la norma urbana va primero**. Si el
POT clasifica el suelo como protección, el valor y el terreno son irrelevantes hasta que
un certificado de uso del suelo diga otra cosa. Y la capacidad de barra de la Circular
UPME 054 de 2026 (`insumos/barras.py`) puede poner en cero la conexión de una zona
entera: la ficha lo muestra con su fecha de corte.

Lo que no existe por máquina y la ficha declara: usos prohibidos y condicionados del
POT (poblados en 5% de los municipios), zonificación interna del POMCA, rondas hídricas
como capa, avalúo catastral en pesos por lote, precio de transacción del lote,
líneas de media tensión, y teléfono del propietario (persona natural).

La ruta completa hacia la compra, con el cribado jurídico (UAF y baldíos, restitución),
el semáforo de certificados, los instrumentos y los costos de cierre, está en
**[ADQUISICION.md](ADQUISICION.md)**.

## Lo que este bloque no resuelve

- **El propietario.** La petición trae la matrícula, pero el titular sale del certificado
  de tradición, que es de pago y hay que comprarlo. Radicar y pagar son los dos únicos
  pasos que ningún código evita.
- **Los usos prohibidos del POT.** La categoría, el reparto de área y la clasificación
  del suelo sí salen de los geoservicios LADM-COL del IGAC (761 municipios), pero los usos
  prohibidos y condicionados casi nunca están cargados: el certificado de uso del suelo
  sigue siendo de la alcaldía. La zonificación de los POMCA sí está publicada
  (geo.minambiente.gov.co, PCA_POMCA, 78 cuencas) y queda como capa por añadir.
- **El catastro que falta.** Hay grillas con menos de la mitad de su superficie en el
  catastro público, por dos causas distintas: municipios con gestor catastral propio
  (el servicio del IGAC no los trae; el visor nombra al gestor) y zonas sin formar. En
  ninguno de los dos casos faltan lotes: falta la fuente abierta.
- **La matrícula y el certificado.** No hay servicio abierto que dé la matrícula por
  número predial ni enlace con la matrícula al portal de la SNR; se piden y se compran.

---

## El reporte de lotes

Todo lo anterior produce tablas. El reporte las vuelve navegables:

```bash
python -m reporte_predios
```

Recibe **las grillas que se seleccionaron y exportaron desde el reporte de grillas**
(botón de descarga GeoJSON o CSV; por defecto `outputs/reporte/grillas_para_predios.geojson`)
y sobre ellas monta un visor de tres paneles: la grilla con sus lotes en un mapa con
fondo satelital, la lista con su **panel de filtros**, y el detalle del lote con su
norma urbana, cribado jurídico, entorno, valor, imagen satelital y los botones para la
ficha PDF, el GeoJSON del lote, Google Maps y **la SNR para el certificado**.

El filtro es manual porque el tamaño lo decide el proyecto, no el código: tres
preajustes (≥ 150 ha y 387 m, ≥ 2 ha y 45 m, cualquier tamaño) que muestran cuántos
lotes de la grilla cumplen cada uno; rangos editables de área del lote, ancho, cobertura
apta, índice y valor catastral por hectárea; y casillas por clase, sin estorbos, dentro de
UAF, POT distinto de protección y sin título minero. La lista y el mapa responden al instante
y la ficha PDF deja escrito con qué filtro se sacó.

Da igual cuántas grillas lleguen ni cuáles: el reporte se arma sobre lo que reciba.

```bash
python -m reporte_predios --grillas otra_seleccion.geojson
python -m reporte_predios --imagenes 50          # descarga las 50 mayores por grilla y perfil
python -m reporte_predios --sin-satelital        # no descarga ninguna
```

Deja `outputs/reporte/reporte_predios.html` y su copia en `entregables/`, con las
imágenes en la carpeta `satelital/` que ya comparte con el reporte de grillas. Para que el
HTML no crezca con el número de grillas, se descargan solo las imágenes de los 25 lotes
de mayor área por grilla y perfil (una vez por lote); el resto la ficha la pide al
servicio de Esri en el momento, con el mismo recuadro. Las imágenes son insumo: se piden
primero al bucket (`gs://prospectos_solares/insumos/satelital/`) y solo si faltan allí se
descargan de Esri, y al terminar se publican las nuevas. En el repositorio va solo el
HTML; para compartirlo se entrega la carpeta `entregables/`.

Decisiones de diseño:

- **El municipio del lote es el de su código catastral**, no el de la celda. En 17 de
  152 lotes utility difieren, porque el lote cruza el límite municipal; el catastro
  decía Puerto Libertador y el lote es de San José de Uré. Para pedir un certificado o
  tocar una puerta importa el del lote, y ese es el que se muestra; el de la celda
  queda en `municipio_celda`.
- **El mapa encuadra la unión de la celda y sus lotes**, no solo la celda: un lote de
  300 ha se queda en la celda con la que más superficie comparte pero puede sobresalir
  un ancho entero, y encuadrar la celda sola lo cortaría.
- **La imagen satelital lleva su fecha de captura y avisa si tiene más de cinco años.**
  Esri World Imagery no es homogéneo: en Caimito la escena es de 2025, en Montelíbano
  de 2015 y en Sabana de Torres de 2018. Diez años en un lote ganadero cambian todo, y
  el cliente debe saberlo antes de decidir por la foto.
- **El precio del certificado de tradición se lee de un solo sitio**
  (`predios/registro.py`, hoy $23.000 según la Resolución SNR 2026-001726) y de ahí va al
  visor y a la ficha. Cuando la SNR lo actualice, en enero, se cambia una vez.

### Lo que se auditó antes de entregarlo

Cada paso se contrastó con datos, no de vista:

| Comprobación | Resultado |
|---|---|
| celdas del insumo = celdas del reporte | idénticas |
| lotes por perfil = filas del CSV maestro filtrado | 36 y 503, cero discrepancias fila a fila en índice y área |
| distorsión de área por simplificar geometría | 0,03% mediana, 0,14% máximo |
| bbox y centro de cada lote frente a su geometría | cero inconsistencias |
| recálculo independiente del mejor lote (área, ancho, MWp, DANE, UAF) | coincide al centímetro |
| UAF y restitución del JSON frente a la ANT y la URT en vivo | coincidencia exacta, corte 2026-07-31 |
| municipio mostrado frente al del código catastral | 17 de 152 diferían: **corregido** |
| insumo CSV con 3 celdas, GeoJSON con 1, celda sin evaluar | los tres casos funcionan; el último avisa qué comando falta |
| el CSV tal como lo exporta el reporte de grillas (punto y coma, BOM, WKT) | rompía el lector: **corregido**, ahora detecta el separador |
| el archivo de grillas que baja el visor no trae `pvout` ni `capacidad_*` | el índice del lote se calculaba con 5 de 7 criterios (salía 97 donde debía salir 80): **corregido**, `resolver_celdas` completa las columnas maestras desde `grillas_candidatas.gpkg` |
| capacidad de barra de la Circular UPME 054 en el criterio | entraba solo en la tabla de concurrencia, no en el índice: **corregido** en `insumos.barras.extraer_todas` |
| geometrías del IGAC de cientos de miles de vértices en las consultas por polígono | la petición GET fallaba y el lote quedaba sin minería ni POT: **corregido**, POST con geometría simplificada a 5 m |
| servicio POT del IGAC caído (HTTP 500) durante la corrida | los lotes quedaban como "sin zonificación": **corregido**, la capa queda como error, se reintenta sola y la ficha lo dice tal cual |
| banderas `ent_*` (inundación, Ley 2ª) llegaban al visor como texto "False" | en JavaScript "False" es verdadero y la ficha mostraba inundación y Ley 2ª en lotes que no las tenían: **corregido** en `_limpio` y cubierto por una comprobación |
| el archivo que baja el visor no traía `pvout` ni `capacidad_*` | ya anotado arriba |
| valor por hectárea de Atlántico con formato "$9.000.000" | se descartaba en silencio y Candelaria y Manatí quedaban sin valor: **corregido** (`valor._pesos`) |
| vigencia de 35 fuentes verificada en vivo el 19-ago-2026 | 5 no eran las más recientes (catastro, RUNAP, resguardos, consejos, Circular 042) y se actualizaron; la tabla de fuentes del visor lleva versión o corte de cada una |
| las 539 imágenes satelitales en paralelo | de 10 minutos en serie a 4 con 8 hilos; la fecha de captura se cachea |
| navegación en navegador real: perfiles, filtros, grilla vacía, ficha completa | sin errores de consola |

### Cómo reproducir la verificación

Desde la raíz del proyecto, en este orden. Cada comando debe terminar sin error.

```bash
.venv/Scripts/python.exe -m compileall -q predios reporte_predios
.venv/Scripts/python.exe -m predios.certificados --prueba
.venv/Scripts/python.exe -m predios.lotes --celdas outputs/reporte/grillas_para_predios.geojson
.venv/Scripts/python.exe -m reporte_predios
.venv/Scripts/python.exe soporte/herramientas/probar_reporte_predios.py
```

Resultados con las 10 grillas del piloto (2026-08-19, catastro corte 30-jun-2026): 2.745
lotes del catastro, de los que 749 tienen 2 ha o más y no son urbanos ni habitacionales; de
esos, 102 quedan excluidos por título minero vigente y 647 van al CSV de cada perfil. En
utility los 647 quedan **Con reparos**, todos por la misma razón: la capacidad de barra de
la Circular UPME 054 (0,02 a 28 MW en las diez grillas) está por debajo del límite de 50 MW
del criterio; en distribuida, cuya barra de media tensión sí tiene cupo, 552 son Idóneos y
95 Con reparos (POT de protección o algún criterio corto). 1.325 Pequeños y 773 Excluidos
en el CSV de descartes. `--prueba` reporta 7 de 7; la herramienta
de comprobación reporta `TODO OK` (58 controles). El cuaderno
`2. IGAC_Consulta_Predios.ipynb` con `CELDAS` apuntando al mismo GeoJSON produce las
mismas cifras.
