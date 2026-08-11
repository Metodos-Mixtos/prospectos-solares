# Cómo reproducir el reporte

El reporte no depende de las cien celdas actuales. Recibe un archivo de candidatas,
aplica el mismo procedimiento sea cual sea su contenido y escribe las salidas. Si el
modelo se vuelve a correr y devuelve otras celdas, no hay nada que ajustar a mano.

## Preparar la máquina

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt    # en macOS: .venv/bin/pip
```

Credenciales de Google Cloud, una sola vez:

```bash
gcloud auth application-default login
```

Comprobar que todo quedó en su sitio:

```bash
.venv/Scripts/python check_setup.py
```

## Traer los insumos

Todo lo que se descargó alguna vez de un servicio externo está publicado en
`gs://prospectos_solares/insumos/`. Bajarlo evita repetir horas de consultas y, sobre
todo, garantiza que dos personas partan del mismo dato:

```bash
.venv/Scripts/python insumos.py bajar
```

Son cinco conjuntos, todos crudos, tal como los devolvió la entidad:

| Conjunto | Qué es | Origen |
|---|---|---|
| `osm_vias` | respuestas de Overpass por bloque de celdas | OpenStreetMap |
| `lineas_transmision` | líneas de transmisión, malla nacional fija | OpenStreetMap |
| `igac_predios` | predios por celda y capa | FeatureServer del IGAC |
| `capacidad_barras` | informes de capacidad por barra | UPME |
| `restricciones` | Reserva Forestal de Ley 2ª de 1959 | MinAmbiente, SIAC |
| `conflicto` | acciones bélicas desde 2022, un registro por hecho | SIEVCAC del CNMH |
| `normativa` | las normas completas que sustentan los criterios | ver `NORMATIVA.md` |

Nada calculado por nosotros vive en el bucket. Las distancias, las áreas, la
clasificación y el reporte se regeneran con los scripts en minutos, y publicarlos solo
crearía copias que envejecen y acaban contradiciendo al código.

## Generar el reporte

```bash
.venv/Scripts/python reporte_grillas.py
.venv/Scripts/python reporte_html.py
```

El primero lee `outputs/top_candidates.gpkg`, el archivo que deja el notebook 1, y
escribe la tabla enriquecida en CSV, XLSX, GPKG, GeoJSON, KML y JSON. El segundo arma
el HTML interactivo a partir de ese JSON.

Para correrlo sobre otras candidatas basta con apuntar al archivo:

```bash
.venv/Scripts/python reporte_grillas.py --celdas ruta/a/mis_celdas.gpkg
```

Lo único que se le exige a ese archivo es una columna `cell_id`, la geometría y las
covariables del panel. Todo lo demás lo deriva el script.

## Qué hace por su cuenta cuando cambian las celdas

Esto es lo que hace que el procedimiento sea el mismo con cualquier conjunto:

- **Distancia a vía.** Si el CSV previo no cubre alguna celda, la consulta a Overpass y
  completa lo que falte. El caché se nombra por el hash de los bbox consultados, no por
  un número de lote, así que un conjunto distinto de celdas nunca reutiliza la respuesta
  de otro. Si Overpass no responde, lo dice; no deja la columna vacía en silencio.
- **Ley 2ª.** Se cruza en vivo contra la geometría que llega, bajando la capa del
  bucket. No se lee de una tabla precalculada, precisamente para que no se quede corta
  cuando aparezcan celdas nuevas.
- **Conflicto armado.** El municipio de cada celda se resuelve espacialmente contra la
  base veredal y se cruza por código DANE, no por nombre, porque el mismo municipio
  aparece como TUMACO y como SAN ANDRES DE TUMACO según la fuente.
- **Imagen satelital.** Se pide una foto por grilla al servicio World Imagery de Esri, que
  no exige clave, y se descarga sola la que falte. Las fotos no van embebidas en el HTML
  sino en `outputs/reporte/satelital/`: a la resolución que hace falta para reconocer el
  terreno, unos 7 metros por píxel, las cien pesan 30 MB y meterlas dentro volvía el
  archivo inmanejable. **Para llevarse el reporte hay que llevar el HTML y esa carpeta
  juntos**; así sigue funcionando sin conexión.
- **Subestaciones, líneas, departamentos, municipios y veredas.** Son capas nacionales;
  se recortan a las celdas que haya.
- **Porcentajes de superficie.** Se calculan sobre el área real de cada celda, no sobre
  un valor fijo, por si algún día cambia el tamaño de la grilla.

## Exclusiones

Se aplican antes de puntuar nada. Una celda excluida no compite, no recibe índice y no
suma potencial. El orden importa: primero se descarta y solo sobre lo que sobrevive se
calcula la aptitud.

**Figuras jurídicas**, cualquiera basta: parque nacional natural, resguardo indígena,
consejo comunitario, área protegida del RUNAP.

**Umbrales**: altitud media sobre 3.000 m, donde la Ley 1930 de 2018 prohíbe las
actividades de alto impacto; y presencia de cultivos de coca, por riesgo operativo.

**Conflicto armado**: descarta la celda cuyo municipio acumula tres o más acciones
bélicas desde 2022 **y** al menos tres por cada mil km². Se exigen las dos porque el
conteo solo castigaría a los municipios grandes: Montería tiene tres hechos en 3.093 km²,
que es un evento por mil km² y no describe un territorio en disputa, mientras que
Bugalagrande tiene cuatro en 394 km².

Va por municipio y no por distancia porque la fuente no da para más. El CNMH geocodifica
los hechos a un punto de referencia municipal, la mediana es que el 58% de los hechos de
un municipio caigan en la misma coordenada, y el radio equivalente del municipio mediano
con hechos es de 15 km. Un corte en kilómetros inventaría precisión que el dato no tiene.

El umbral está calibrado contra lo que el sector ya hace y no contra una preferencia. De
las diez plantas solares de 50 MW o más en operación en el país, ninguna está en un
municipio que caiga bajo estos filtros, y de las veintitrés de 10 MW o más solo tres. El
método es el mismo que se usó para fijar el rango de tensión de las subestaciones.

Con las cien candidatas actuales descarta diez celdas, cinco en Cáceres, dos en
Bugalagrande, dos en Río de Oro y una en María La Baja.

**Reserva Forestal de Ley 2ª de 1959**: descarta solo cuando cubre el 90% o más de la
celda. No es una prohibición como la de un parque. Reserva el suelo para economía
forestal, así que darle otro uso exige que el ministerio sustraiga primero esa porción,
trámite regulado hoy por la Resolución 110 de 2022 del MADS.[^1] Esa resolución pide que
la actividad sea de utilidad pública o interés social, requisito que un proyecto solar ya
cumple porque el artículo 4 de la Ley 1715 de 2014 declara de utilidad pública el
desarrollo de fuentes no convencionales de energía renovable.[^2] La puerta legal existe;
lo que añade es tiempo y compensaciones. Con cobertura parcial el lote se sitúa fuera del
polígono y no hay nada que tramitar, así que la celda sigue compitiendo y la ficha lo
advierte.

Queda un cabo suelto que el reporte no resuelve. La línea de conexión hasta la
subestación puede cruzar la reserva aunque los paneles queden fuera, y para líneas de
transmisión la Resolución 110 pide sustracción temporal. Es una verificación de campo,
no de escritorio.

[^1]: Resolución 110 de 2022 del MADS, que derogó la Resolución 1526 de 2012 salvo sus
    artículos 7 y 8 sobre términos de referencia. Fija el plazo de decisión en unos 85
    días hábiles y remite las compensaciones al Manual del Medio Biótico, actualizado por
    la Resolución 0305 de 2026 del MADS.

[^2]: Artículo 4 de la Ley 1715 de 2014, en la redacción que le dio la Ley 2099 de 2021.
    El artículo 3 de esa ley es el ámbito de aplicación, no la declaratoria.

Los umbrales viven en `reporte_grillas.py`, arriba del todo, en
`RESTRICCIONES_EXCLUYENTES`, `EXCLUSIONES_UMBRAL` y `LEY2_EXCLUYE_PCT`.

## Perfiles de proyecto

El mismo terreno no sirve igual para una granja de 50 MW que para una de 1 MW, así que
los umbrales se rederivan contra plantas del tamaño que se busca. **Los dos perfiles van
en el mismo reporte** y se conmutan con la botonera que hay sobre la matriz de criterios,
sin regenerar nada. El pipeline calcula el punto de conexión de ambos en la misma corrida.

Lo que cambia entre perfiles es el rango de tensión del punto de conexión y los seis
umbrales. Las exclusiones, las capas y el resto del pipeline son idénticos.

El perfil con el que se genera solo decide cuál sale seleccionado al abrir el archivo:

```bash
.venv/Scripts/python reporte_grillas.py                        # abre en utility
.venv/Scripts/python reporte_grillas.py --perfil distribuida   # abre en distribuida
```

**Salvedad importante del perfil distribuido.** Un proyecto de 1 a 2 MWp se conecta a un
circuito de media tensión de 13,2 o 34,5 kV y debe quedar a menos de 1,5 km. Esa red no
está publicada en Colombia: no está en OpenStreetMap, que devuelve cero líneas de
distribución en Córdoba y Bolívar; los geoservicios de la UPME no responden; y los
portales de datos abiertos remiten a pedírsela a cada operador. Lo que el perfil mide es
la distancia a la subestación de subtransmisión, de donde cuelgan esos circuitos, y por
eso su mediana da 16,2 km y no 1,5. Sirve para descartar lo remoto, no para confirmar la
conexión, que exige el Estudio de Conexión Simplificado ante el operador bajo CREG 174.

Los umbrales del perfil distribuido son más laxos en los seis criterios. No es un error:
las plantas pequeñas del país están más lejos de la red, en más pendiente y con peor
cobertura, porque son autogeneradores que se ponen donde está la finca o la fábrica y no
eligen el mejor terreno disponible.

## De dónde salen los umbrales del índice

Los tres umbrales de cada criterio se leen de la distribución de las 53 celdas del país
que ya contienen una planta solar de 10 MW o más, que es la escala que se prospecta.

| | |
|---|---|
| `tope` | percentil 10, el decil mejor de lo construido. Vale 100. |
| `bueno` | mediana. «Aquí está la mitad de lo que ya se construyó». Vale 70. |
| `limite` | percentil 90. «Más allá casi nadie ha construido». Vale 0. |

Como los tres puntos son fijos y no dependen de las celdas que se estén evaluando, un
índice de 78 significa lo mismo en cualquier corrida y dos carteras se pueden comparar.

Para recalcularlos, por ejemplo cuando entren plantas nuevas al registro de XM:

```bash
.venv/Scripts/python umbrales_referencia.py
```

Imprime los valores nuevos y hay que pegarlos a mano en `CRITERIOS`, dentro de
`reporte_grillas.py`. No se calculan en cada corrida a propósito: obligaría a leer el
panel completo y a consultar Overpass cada vez, y un umbral que cambia solo es un umbral
que nadie puede auditar.

El corte de 10 MW importa. Con todas las plantas, los límites de terreno se van al doble,
porque las de 1 MW son autogeneradores en techos industriales que no eligen el terreno.

La limitación del método es la contracara de su virtud. Describe dónde se ha construido,
no dónde conviene construir. Si el sector se equivocó de forma sistemática, el índice
reproduce el error.

## De la grilla al lote

El reporte de grillas dice en qué cuadrado de 5 x 5 km conviene mirar. El segundo bloque
dice qué predio de ese cuadrado se va a visitar. Son tres scripts encadenados:

```bash
.venv/Scripts/python predios_igac.py --clase todas   # baja el catastro
.venv/Scripts/python lotes.py --justificar           # mide, filtra y ordena
```

`predios_igac.py` acepta lo mismo que `reporte_grillas.py`: un archivo de celdas, una
lista de identificadores separada por comas, o una clase del reporte. Con `--estado`
informa de qué hay descargado, y con `--reintentar` vuelve solo sobre lo que quedó a
medias, apoyándose en el manifiesto que deja en `data/igac/_estado.json`. Sin ese
manifiesto no hay forma de distinguir una celda que nunca se pidió de una que se pidió y
devolvió cero predios, y las dos cosas se ven igual en disco.

`terreno.py` no se corre a mano; lo llama `lotes.py`. Es lo que remide pendiente,
rugosidad y cobertura **dentro de cada predio**, leyendo por ventana el Copernicus DEM de
30 m y el ESA WorldCover de 10 m directamente por HTTP, sin credenciales. Los recortes se
cachean en `data/dem/` y `data/cobertura/` y no se publican en el bucket: lo que se guarda
es un recorte reescrito por GDAL, no el byte que devolvió el servicio, y allí solo va el
insumo crudo tal cual llega.

### Por qué no basta con el panel

Porque a escala de lote la media de la celda deja de describir nada. La celda 0011452
tiene en el panel 2,52° de pendiente y 89,6% de cobertura apta; sus predios, medidos uno a
uno, van de 0,12° a 7,52° y del 0% al 100% de cobertura. Elegir un predio con el valor de
su celda no es aproximar, es no medir.

### Qué trae el catastro y qué no

El FeatureServer del IGAC entrega diez campos por predio y ninguno es el propietario. Lo
que sí se puede añadir es la tabla `REGISTRO_1` del mismo servicio, que trae destino
económico, área de terreno y área construida, y que responde por el 98% de los predios
descargados. Se pide por lotes de códigos catastrales, no por municipio, porque tiene 6,8
millones de filas.

Lo que no hay, y no se puede rodear con más código:

- **El titular.** Está en la Superintendencia de Notariado y Registro, se consulta por
  matrícula inmobiliaria y una a una. Sin eso no hay contacto.
- **El uso del suelo del POT.** El destino económico dice a qué se dedica hoy el predio,
  no qué permite el municipio. La clasificación del POT se pide a cada alcaldía.
- **La ronda hídrica.** No hay capa nacional publicada.
- **El catastro que no existe.** Trece de las cien celdas no devolvieron ni un predio, y
  hay ocho más con menos de la mitad de su superficie catastrada; la peor, 0029005, con
  el 3,2%. Ahí no faltan lotes, falta formalización, y el conteo de lotes no se puede
  leer como el total del territorio.

### Los criterios

Tres bloques, y el orden importa igual que arriba: primero se descarta y solo sobre lo que
sobrevive se puntúa. Están documentados uno a uno, con su justificación, en la cabecera de
`lotes.py`.

**Excluyentes.** Celda excluida, predio de la capa urbana del catastro, Reserva de Ley 2ª
sobre más del 10% del predio, destino económico habitacional.

El corte de Ley 2ª es del 10% y no del 90% que se usa en la celda, y el cambio tiene
razón: a escala de celda el argumento era que el lote se sitúa en la parte libre, pero el
predio ya es el lote y no se puede mover dentro de sí mismo.

**Tamaño y forma.** Área útil frente a lo que pide el perfil, 150 ha para utility y 2 para
la distribuida, y ancho útil mínimo. El área útil parte del predio retranqueado 30 m, no
del bruto, y descuenta después por cobertura y por pendiente con la misma tabla que usa el
reporte de grillas, para que las hectáreas del lote y las de la celda se puedan sumar.

**Puntuación.** Los mismos criterios, umbrales y función de utilidad del reporte de
grillas, alimentados con los valores del predio. Cinco se remiden dentro del polígono
(conexión, cobertura, pendiente, rugosidad, vía) y dos se heredan de la celda porque no
son del terreno: la irradiación, que no varía apreciablemente en 5 km, y la capacidad
libre de la barra, que es del nodo eléctrico.

### Dos criterios que no sobrevivieron al contraste

Se dejan escritos porque el criterio de forma es el más fácil de poner a ojo y el más
difícil de defender después. `lotes.py --justificar` imprime los números.

**La compacidad de Polsby-Popper se calcula pero no filtra.** Era el candidato obvio.
Sobre los 378 predios de las cien celdas que alcanzan las 150 ha del perfil utility, un
corte en 0,30 descartaría 80, el 21%, y su correlación con el ancho útil es de 0,18 aquí
y de −0,01 en el perfil distribuido. Penaliza el perímetro dentado, que tiene el lindero
de cualquier finca que siga una quebrada o una cerca vieja, no la forma inservible. Se
publica como descriptor, no decide.

**La distancia a vía se conserva aunque casi no separe.** Medida desde el lindero, que es
donde se construye el acceso, se comprime contra el cero: la mediana es de 166 m, el 39%
de los predios queda dentro de los 100 m que el criterio marca como tope y solo el 6% pasa
del límite de 1,5 km. Sigue penalizando al predio sin acceso, que es para lo que está,
pero ya no ordena la lista. No se sustituye por la distancia desde el centroide, que sí
dispersaría, porque penalizaría al predio grande por ser grande.

### Lo que sale

Por perfil, en `outputs/reporte/`:

| Archivo | Qué lleva |
|---|---|
| `lotes_<perfil>.csv` y `.geojson` | los lotes que pasan tamaño y forma, con geometría |
| `lotes_<perfil>_descartados.csv` | el resto, sin geometría, con el motivo del descarte |
| `lotes.gpkg` | una capa por perfil, para QGIS |

El descarte va aparte y sin geometría porque son decenas de miles de polígonos, pero no se
tira: un descarte sin registro es un descarte que no se puede discutir.

Con las cien candidatas actuales, sobre 22.658 predios de 85 celdas:

| | utility | distribuida |
|---|---|---|
| Idóneos | 67 | 2.836 |
| Viables | 10 | 263 |
| Con reparos | 75 | 844 |
| Celdas con al menos un lote | 49 de 85 | 79 de 85 |
| Hectáreas útiles | 44.532 | 109.504 |
| MWp indicativos | 29.688 | 73.002 |

Los MWp son indicativos y no una cartera: suponen 1,5 ha por MWp, no descuentan que dos
lotes de la misma celda competirían por la misma barra, y el perfil distribuido cuenta
predios enteros de decenas de hectáreas donde el proyecto solo necesita dos.

## Volver a bajar una capa de restricción

Solo si hace falta una versión más reciente que la publicada:

```bash
.venv/Scripts/python capas_restriccion.py --refrescar --subir
```

Baja del FeatureServer del MADS y republica en el bucket, para que el resto del equipo
tome exactamente la misma.

## Verificación hecha

Se borró el caché local de vías y de restricciones, se recuperó todo desde el bucket y
se regeneró el reporte de cero. El CSV resultante salió idéntico al de referencia:
100 filas y 42 columnas sin una sola diferencia.

También se corrió sobre un subconjunto de 12 celdas distintas para comprobar que el
pipeline no arrastra nada del conjunto anterior. Recalculó subestación, municipio,
vereda, capacidad en barras, zonas y distancias a vía para las celdas nuevas, sin
tocar a mano ninguna constante.

Del bloque de lotes: se descargó el catastro de las cien celdas, no de las dieciocho
prioritarias que había, y el mismo pipeline se corrió sobre subconjuntos de dos y de tres
celdas para comprobar que no depende de cuáles sean. El notebook 2 se ejecuta de punta a
punta sin errores.

Dos avisos sobre lo que se descargó. Trece de las cien celdas no devolvieron ni un predio,
y no es un fallo de la consulta: el catastro no llega ahí. Y hay un predio en Calamar con
más de seiscientos mil vértices, unas cuatro mil veces la mediana, que llega así del IGAC
y aparece en cuatro celdas porque cruza los linderos de la grilla.
