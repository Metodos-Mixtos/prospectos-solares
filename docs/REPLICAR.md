# Replicar el proyecto en otra máquina

Guía de puesta en marcha desde un repositorio recién clonado hasta un reporte generado.
Está escrita para alguien competente que no conoce el proyecto. Cada comando de esta
página se ejecutó tal cual está escrito antes de publicarla.

El repositorio trae **código y los HTML finales, nada más**. Los datos viven en los
buckets de Google Cloud del proyecto `prospectos-solares`. Sin acceso a esos buckets el
procedimiento no corre, y eso es lo primero que hay que resolver: el apartado 3.2 dice
qué permiso hace falta y a quién se le pide. Iniciar sesión con una cuenta de Google no
basta; la cuenta tiene que estar autorizada en los buckets.

---

## Resumen de un vistazo

| | |
|---|---|
| Python | 3.12 (3.12.10 en la máquina de referencia) |
| Sistema | Windows, macOS o Linux. Los ejemplos van en la forma de Windows |
| Instalación | `pip install -r requirements.txt` más `playwright install chromium` |
| Credenciales | cuenta de Google con lectura en dos buckets, y cuenta propia en el portal de la SNR |
| Datos a descargar | unos **1,2 GB**, no los 71 GB que ocupan los buckets enteros |
| Tiempo de puesta en marcha | entre treinta y sesenta minutos, casi todo descarga |
| Verificador | `.venv\Scripts\python.exe soporte\herramientas\check_setup.py` |

---

## 1. Requisitos previos

**Python 3.12.** Es la versión con la que se desarrolló y se probó todo. La 3.11 debería
funcionar. La 3.13 no se ha comprobado, y las ruedas precompiladas de la pila
geoespacial tardan en publicarse para cada versión nueva de Python; si no hay rueda, pip
intenta compilar y en Windows eso falla sin un compilador C. Conviene no adelantarse.

**Git.** Para clonar.

**El CLI de Google Cloud.** Hace falta para autenticarse. En Windows:

```powershell
winget install Google.CloudSDK
```

También se descarga de <https://cloud.google.com/sdk/docs/install>.

**Lo que no hace falta.** No hay que instalar GDAL, PROJ ni GEOS por separado, ni usar
conda. `geopandas`, `rasterio`, `pyogrio` y `pyproj` traen sus binarios dentro de la
rueda de pip desde hace varias versiones, y así se instalaron en la máquina de
referencia. Tampoco hace falta una base de datos ni un servidor: todo son ficheros.

---

## 2. Instalar el entorno

Desde la raíz del repositorio.

**Windows**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

**macOS y Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

Sobre el último comando: pip instala la librería `playwright`, pero **no descarga el
navegador**. El paso de matrícula lanza el chromium empaquetado de playwright en modo
headless, no el Chrome del sistema, así que sin ese comando ese paso falla al abrir el
navegador. Se hace una vez por máquina.

`requirements-lock.txt` fija las versiones exactas probadas, pero se generó en Windows
con Python 3.12 y lleva ruedas de plataforma. En otro sistema o con otra versión de
Python hay que usar `requirements.txt`, que solo pone mínimos.

`requirements-bayes.txt` es para los cuadernos 1.1 y 1.2, que son código heredado de
otro proyecto y no están adaptados a este caso. **No lo instales.**

---

## 3. Credenciales

### 3.1 Google Cloud

Es la credencial crítica. Sin ella no hay datos.

```powershell
gcloud auth application-default login
gcloud config set project prospectos-solares
gcloud auth application-default set-quota-project prospectos-solares
```

El segundo comando fija el proyecto. El tercero evita el aviso de proyecto de cuota que
por lo demás aparece en cada llamada al bucket, y hace falta de verdad al subir.

No hay ninguna clave que copiar a ningún fichero: se inicia sesión con la propia cuenta
y las credenciales de aplicación por defecto quedan en la máquina. Caducan cada cierto
tiempo, y cuando lo hacen el error es inconfundible:

```
RefreshError: Reauthentication is needed. Please run
`gcloud auth application-default login` to reauthenticate.
```

Comprobar en qué estado quedó el acceso:

```powershell
.venv\Scripts\python.exe soporte\gcs.py auth
.venv\Scripts\python.exe soporte\gcs.py ls
```

### 3.2 Permiso sobre los buckets

**Iniciar sesión no da acceso.** La cuenta tiene que estar autorizada en los buckets, y
eso lo concede quien administre el proyecto `prospectos-solares`. Hay que pedirlo explícitamente
antes de empezar. Lo que hace falta:

| Bucket | Para qué | Nivel |
|---|---|---|
| `gs://prospectos-solares-insumos`, prefijo `geoinfo/` | capas base: subestaciones, granjas de XM, límites y base veredal | lectura |
| `gs://prospectos-solares-insumos` | todo lo que entra al procedimiento | lectura |
| `gs://prospectos-solares-salidas` | `corridas/<corrida>/`, lo que publica cada corrida | lectura, y escritura si se va a publicar |

Con solo lectura el procedimiento corre entero: basta añadir `--sin-bucket` para que
nada intente publicarse, y todo queda en disco. La escritura hace falta únicamente para
que las corridas queden publicadas para el resto del equipo.

Si el permiso no está concedido, el fallo aparece al primer intento de leer, como un
error de tipo `Forbidden` o `NotFound` sobre el bucket. `check_setup.py` lo dice sin
ambigüedad en su bloque de Google Cloud.

### 3.3 Superintendencia de Notariado y Registro

```powershell
copy .env.example .env
```

Y se rellenan `SNR_USUARIO` y `SNR_CLAVE` dentro de `.env`, que no se versiona. Son las
credenciales de una cuenta propia en el portal público de certificados,
<https://certificados.supernotariado.gov.co/certificado>, que se registra con correo y
contraseña. **No se comparten las de otra persona**: el cupo diario es por cuenta, y
compartirlas significa que dos personas se lo gastan mutuamente.

`.env.example` documenta cada variable, para qué sirve, de dónde sale y qué pasa si
falta. Sin `SNR_USUARIO` y `SNR_CLAVE` el procedimiento sigue corriendo: el paso 4 no
intenta esa vía, los lotes quedan sin matrícula y el motivo queda escrito en
`matriculas_<perfil>.csv`. Nunca se escribe "sin dato" por no haber preguntado.

Para ver qué claves están puestas, sin imprimir ningún valor:

```powershell
.venv\Scripts\python.exe ejecutar.py --corrida prueba --hasta 0
```

El paso 0 imprime, entre otras cosas, un `ok` o un `aviso` por cada clave del `.env`.
Terminará diciendo que faltan las grillas de la corrida, que es lo esperado mientras no
se le haya pasado ninguna, y creará las carpetas de destino de esa corrida.

---

## 4. Traer los datos

Aquí es donde conviene ser preciso, porque el tamaño de los buckets asusta y no
corresponde a lo que hay que descargar.

| | Tamaño total del bucket | Lo que este proyecto usa |
|---|---|---|
| `gs://geoinfo` (compartido, ya no se usa) | 70,94 GiB, 264 objetos | **377 MiB**, nueve objetos |
| `gs://prospectos_solares` (anterior) | 0,86 GiB, 4 623 objetos | **0,80 GiB**, 4 602 objetos bajo `insumos/` |

Medido el 25 de agosto de 2026 recorriendo los buckets, es decir **antes de la migración del 26 de agosto** al proyecto `prospectos-solares`. Las cifras sirven de orden de magnitud, no como inventario del bucket actual; no se han vuelto a medir. De `geoinfo` **no se descarga
casi nada**: es un bucket compartido del equipo con capas de muchos proyectos, y este
solo pide cuatro cosas. De los 377 MiB, 352 son la base veredal del DANE.

### 4.1 Los insumos del proyecto

```powershell
.venv\Scripts\python.exe -m insumos bajar
```

Trae de `gs://prospectos-solares-insumos/` los diecisiete conjuntos que el procedimiento
usa: respuestas crudas del catastro del IGAC, de Overpass, de la ANT y la URT, los
informes de capacidad de la UPME, las zonas geoeconómicas, la norma urbana, las imágenes
satelitales y las normas. Unos 4 600 ficheros, 0,80 GiB.

No es obligatorio ejecutarlo por adelantado: cada script mira primero el bucket y solo
sale a la fuente original lo que no encuentre allí. Pero hacerlo de una vez evita
golpear los servicios externos, que son lentos y a veces devuelven algo distinto.

Para ver qué hay en disco frente a qué hay en el bucket:

```powershell
.venv\Scripts\python.exe -m insumos estado
```

### 4.2 Las capas base

```powershell
.venv\Scripts\python.exe -c "import sys; sys.path[:0]=['soporte']; import config; print(config.asegurar_datos())"
```

Descarga los tres insumos que el modelo y el reporte leen por ruta directa: el panel de
21 447 grillas (10 MB), las granjas de generación reportadas por XM (140 KB) y las
subestaciones del SIN (490 KB). Si ya están, no hace nada.

Este paso es fácil de olvidar porque **ningún comando lo llama solo**. Sin él,
`python -m reporte` se detiene al leer las subestaciones.

### 4.3 La base veredal

De ella salen el nombre del municipio y el de la vereda de cada grilla y de cada lote.
Sí está en el bucket, completa: los cinco ficheros del shapefile, 352 MB en total,
bajo `geoinfo/base_veredas/`. Lo que pasa es que `asegurar_datos` no la incluye, así
que es el único insumo que hay que pedir a mano:

```powershell
.venv\Scripts\python.exe soporte\gcs.py get geoinfo "base_veredas/base_veredas.shp"
.venv\Scripts\python.exe soporte\gcs.py get geoinfo "base_veredas/base_veredas.dbf"
.venv\Scripts\python.exe soporte\gcs.py get geoinfo "base_veredas/base_veredas.shx"
.venv\Scripts\python.exe soporte\gcs.py get geoinfo "base_veredas/base_veredas.prj"
.venv\Scripts\python.exe soporte\gcs.py get geoinfo "base_veredas/base_veredas.cpg"
```

Cuidado con no sincronizar la carpeta entera: `base_veredas/` contiene además dos
versiones antiguas, `desactualizada/` y `desactualizada_v2/`, que suman otros 660 MB y
no se usan.

Si falta, nada se rompe: municipio y vereda salen vacíos en el reporte y en las fichas
de lote. Es una pérdida silenciosa de calidad, y por eso `check_setup.py` la comprueba
y avisa.

### 4.4 Lo que se descarga solo, sin credenciales

El modelo de terreno y la cobertura del suelo se leen por ventana desde buckets públicos
de S3, sin firma y sin cuenta: Copernicus DEM GLO-30 y ESA WorldCover 2021. Se cachean
en `data/dem` y `data/cobertura` según hagan falta. No hay nada que preparar.

### 4.5 Comprobar que todo quedó en su sitio

```powershell
.venv\Scripts\python.exe soporte\herramientas\check_setup.py
```

Recorre, sin detenerse en el primer fallo, la versión de Python, las librerías del
núcleo, las del procedimiento de lotes, el navegador de playwright, el módulo del
modelo, el acceso a los dos buckets, la base veredal y las rutas de datos. Devuelve 0
si todo está y 1 si falta algo, y en cada bloque escribe el comando exacto que arregla
lo que falte.

---

## 5. La primera corrida

El proyecto va en dos escalas y cada una tiene su punto de entrada.

### 5.1 Escala de grilla: el reporte

El reporte parte de las candidatas que produce el cuaderno `1. Selección de grillas`,
que las deja en `data/proyectos/paneles-solares/outputs/top_candidates.gpkg`. **Ese
fichero no está en el bucket ni en el repositorio**, así que en una máquina nueva hay
que generarlo corriendo el cuaderno 1, que sí lee todo lo que necesita de los insumos
del apartado 4.2. Los cuadernos se abren desde la raíz, que es desde donde resuelven sus
importaciones.

Con las candidatas ya en disco:

```powershell
.venv\Scripts\python.exe -m reporte
```

Deja en `outputs/reporte/` el HTML, la tabla `grillas_candidatas` en seis formatos, las
zonas de prospección y la concurrencia por subestación, y copia el entregable a
`entregables/`. El detalle de qué hace cada parte y de dónde sale cada umbral está en
[REPORTE.md](REPORTE.md).

Sobre otro conjunto de celdas, que es el caso cuando el modelo se vuelve a correr:

```powershell
.venv\Scripts\python.exe -m reporte --celdas ruta\a\mis_celdas.gpkg
```

Al archivo de entrada solo se le exige `cell_id`, la geometría y las covariables del
panel.

### 5.2 Escala de lote: el hilo conductor

`ejecutar.py`, en la raíz, es el punto de entrada único de la cadena de lotes. Recibe un
insumo obligatorio, el archivo de grillas, y corre los ocho pasos hasta el visor y el
Excel, publicando en el bucket lo que cada paso produce.

Antes de nada, ver el plan sin ejecutar nada:

```powershell
.venv\Scripts\python.exe ejecutar.py --corrida mi_prueba --seco
```

Imprime los tres destinos de la corrida y la lista de pasos con cuáles se van a correr y
cuáles son críticos, y termina con `corrida en seco, no se ejecutó nada`. Es la forma
barata de comprobar que el nombre de la corrida y las rutas son las que se esperaban.

El archivo de grillas es la selección que se descarga desde el reporte con el botón
"para predios", o el que arma a mano:

```powershell
.venv\Scripts\python.exe soporte\herramientas\lote_predios.py --top 10
.venv\Scripts\python.exe soporte\herramientas\lote_predios.py --ids 0012960,0011446
```

Y la corrida completa:

```powershell
.venv\Scripts\python.exe ejecutar.py --corrida mi_prueba --grillas outputs\reporte\grillas_para_predios.geojson
```

**Para la primera vez conviene empezar pequeño.** Una o dos grillas, sin imágenes y sin
publicar nada:

```powershell
.venv\Scripts\python.exe ejecutar.py --corrida mi_prueba --grillas mis_dos_grillas.geojson --sin-satelital --sin-snr --sin-bucket
```

Así se recorre la cadena entera en minutos, sin gastar el cupo diario de la SNR y sin
escribir en el bucket del equipo.

### 5.3 Qué esperar

Los pasos 2 y 3, catastro y medición de lotes, son los caros: consultan el FeatureServer
del IGAC celda a celda y luego cruzan cada lote contra una docena de geoservicios
externos. Se cuentan en minutos por grilla, no en segundos. El paso 5 descarga una
imagen satelital por lote.

Nada queda a medias en silencio. Cada paso se cronometra y su resultado se escribe en
`_corrida.json`: si corrió, cuánto tardó, qué produjo, si se publicó y, si falló, el
motivo con el tipo de excepción. Con la corrida ya hecha se reanuda sin repetir lo caro:

```powershell
.venv\Scripts\python.exe ejecutar.py --corrida mi_prueba --desde 5
```

El nombre de la corrida es obligatorio y de él salen los tres destinos, así que dos
corridas no se pueden pisar. La carpeta se bloquea mientras dura, y dos procesos no
pueden escribir a la vez en el mismo destino. El detalle completo está en el docstring
de `ejecutar.py` y en `outputs/PROCEDIMIENTO_LOTES.md`.

---

## 6. Qué no vas a poder reproducir, y por qué

Esta sección es la que importa. Lo que sigue no es un defecto del código: son límites de
las fuentes.

### 6.1 El cupo diario de la Superintendencia

El portal de certificados de la SNR tiene un cupo diario de consultas gratuitas por
cuenta. Cuando se agota, el paso 4 lo detecta, para esa vía, escribe el motivo por lote y
deja que el encadenado siga. Al día siguiente se continúa con `--desde 4`, que retoma
donde se quedó.

Consecuencias prácticas. Primero, **hacen falta credenciales propias**: las de otra
persona no se comparten, porque el cupo se gasta entre las dos. Segundo, una corrida
grande no se resuelve en un día, y eso hay que contarlo en el plazo. Tercero, para
cualquier prueba hay que usar `--sin-snr` o `--limite-snr N`, o el cupo del día se va en
la prueba.

### 6.2 Los municipios con gestor catastral propio

Un municipio habilitado como gestor administra su propio catastro, y el servicio
nacional del IGAC no publica sus polígonos. En esos municipios el paso 2 devuelve una
cobertura parcial o nula, y no hay forma de arreglarlo desde el código.

De los dos casos que aparecieron en el trabajo hecho, uno se resolvió porque el municipio
publica su capa por su cuenta, Villavicencio, con
`outputs/catastro_municipal/bajar_villavicencio.py`, y el otro se resolvió solo en parte,
con una capa anterior a la habilitación, Montería. **No hay garantía de que un municipio
nuevo tenga alguna de las dos salidas.** Cuando no la tiene, la única vía es el derecho
de petición de información ante la alcaldía: un trámite humano, con plazo legal de diez
días hábiles prorrogable por otros diez, es decir, entre dos y cuatro semanas.
`outputs/monteria/README.md` deja escrito el modelo de esa petición.

Esto no se replica ejecutando nada. Se replica escribiendo cartas y esperando.

### 6.3 Las fuentes vivas cambian

El catastro del IGAC, Overpass, los geoservicios ambientales y mineros, la UAF de la
ANT, las solicitudes de restitución de la URT y las zonas geoeconómicas se consultan en
vivo. Una corrida de hoy no tiene por qué devolver exactamente lo mismo que una de hace
tres meses, y eso es correcto: el dato cambió.

Por eso el bucket guarda las respuestas crudas tal cual llegaron. Quien quiera reproducir
**el resultado publicado**, y no un resultado nuevo, tiene que correr con las cachés del
bucket ya descargadas y sin forzar la revisita de las fuentes. Quien quiera el estado de
hoy, borra la caché del conjunto que le interese y deja que se vuelva a pedir.

### 6.4 Las salidas de las corridas anteriores no están publicadas

`gs://prospectos-solares-salidas/corridas/` estaba vacío el 25 de agosto de 2026: ninguna corrida
se ha publicado todavía. En consecuencia, `outputs/reporte/grillas_candidatas.gpkg`, que
es la tabla maestra de la que el lote hereda las columnas de su celda, y
`grillas_para_predios.geojson`, que es la selección concreta de grillas que sostiene el
entregable actual, **existen solo en la máquina de Samuel**.

Ambas se regeneran: la maestra la escribe `python -m reporte`, y la selección se rehace
con `lote_predios.py` o marcando grillas en el reporte. Lo que no se recupera sin pedirlo
es **la selección exacta** que se usó para el entregable que hoy está en `entregables/`,
porque fue una elección manual sobre el mapa y no un criterio automático. Si el objetivo
es reproducir ese entregable y no uno equivalente, hay que pedir ese fichero.

### 6.5 Los cuadernos bayesianos

`1.1. Precisión del modelo` y `1.2. Test del modelo` son código heredado del proyecto
DHS/MPI y no están adaptados al caso de paneles solares. Además, en Windows `pytensor`
necesita un compilador C para ir a velocidad razonable y la vía recomendada es
conda-forge, no pip. No forman parte del procedimiento y no hay que instalarlos.

### 6.6 El rastro de investigación

Todo lo que cuelga de una carpeta `_exploracion/` son sondas de un solo uso que se
conservan para no repetir el mismo camino. No se ejecutan, no hacen falta para reproducir
nada y varias apuntan a páginas que ya cambiaron.

---

## 7. Problemas frecuentes

| Síntoma | Causa y arreglo |
|---|---|
| `RefreshError: Reauthentication is needed` | Las credenciales de aplicación caducaron. `gcloud auth application-default login` |
| `Cannot find a quota project to add to ADC` | `gcloud auth application-default set-quota-project prospectos-solares` |
| Aviso de proyecto de cuota en cada llamada | Lo mismo. Es un aviso, no un error, y no impide leer |
| `Forbidden` o `NotFound` sobre un bucket | La cuenta no tiene permiso. Hay que pedirlo a quien administre `prospectos-solares` |
| El paso 4 falla al abrir el navegador | Falta el binario: `.venv\Scripts\python.exe -m playwright install chromium` |
| `Falta .env con SNR_USUARIO y SNR_CLAVE` | `copy .env.example .env` y rellenarlo, o correr con `--sin-snr` |
| `No existe ... top_candidates.gpkg` | Hay que correr antes el cuaderno 1, o pasar `--celdas` con otro archivo |
| Municipio y vereda vacíos | Falta la base veredal. Apartado 4.3 |
| La Circular 054 no se lee | Falta `pymupdf`. Está en `requirements.txt`; reinstala |
| Trabajar sin conexión o con credenciales caducadas | `PROSPECTOS_SIN_BUCKET=1` en el entorno, o `--sin-bucket` |

---

## 8. Dónde seguir leyendo

| | |
|---|---|
| [REPORTE.md](REPORTE.md) | el reporte de grillas: qué calcula y de dónde sale cada umbral |
| [PREDIOS.md](PREDIOS.md) | el procedimiento de lote, paso a paso, con las comprobaciones intermedias |
| [ADQUISICION.md](ADQUISICION.md) | la ruta jurídica y de costos hasta la escritura |
| [NORMATIVA.md](NORMATIVA.md) | las normas que sustentan los criterios |
| `outputs/PROCEDIMIENTO_LOTES.md` | el procedimiento completo, con qué es automático y qué no |
| `.env.example` | cada credencial, para qué sirve, de dónde sale y qué pasa si falta |
