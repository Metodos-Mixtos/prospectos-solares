# Reporte de caracterización de grillas candidatas

Toma las candidatas que produce el notebook 1 y genera un reporte que las caracteriza,
las clasifica y las ordena por aptitud.

**No depende de que sean estas cien.** Recibe un archivo de celdas, aplica el mismo
procedimiento sea cual sea su contenido y descarga por su cuenta lo que le falte. Si el
modelo se vuelve a correr y devuelve otras candidatas, no hay nada que ajustar a mano.

---

## Puesta en marcha

Desde la raíz del proyecto.

**Windows**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS y Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

`requirements-lock.txt` fija las versiones exactas probadas, pero se generó en Windows
con Python 3.12 y tiene ruedas de plataforma. En Linux o con otra versión de Python usa
`requirements.txt`, que solo pone mínimos.

Credenciales de Google Cloud, una sola vez:

```bash
gcloud auth application-default login
```

En Vertex AI Workbench este paso sobra: la VM tiene cuenta de servicio y `gcs.py` la
toma sola. Comprobar que todo quedó en su sitio:

```bash
.venv/Scripts/python soporte/herramientas/check_setup.py
```

---

## Generar el reporte

Un solo comando:

```bash
.venv/Scripts/python -m reporte
```

Sobre otras candidatas, que es el caso cuando el modelo se vuelve a correr:

```bash
.venv/Scripts/python -m reporte --celdas ruta/a/mis_celdas.gpkg
```

Al archivo de entrada solo se le exige una columna `cell_id`, la geometría y las
covariables del panel.

Si solo quieres rehacer el HTML tras tocar el diseño, sin recalcular nada:

```bash
.venv/Scripts/python -m reporte.html
```

### Qué deja en `outputs/reporte/`

| | |
|---|---|
| `reporte_grillas.html` | el reporte, **con la carpeta `satelital/` al lado** |
| `grillas_candidatas.*` | la tabla en CSV, XLSX, GPKG, GeoJSON, KML y JSON |
| `zonas_prospeccion.csv` | las zonas agrupadas |
| `concurrencia_subestaciones.csv` | competencia por punto de conexión |

Para llevarse el reporte hay que llevar el HTML **y** la carpeta `satelital/`. Las fotos
no van embebidas porque a la resolución que hace falta para reconocer el terreno, unos
7 metros por píxel, las cien pesan 25 MB y meterlas dentro volvía el archivo inmanejable.
Con la carpeta al lado sigue funcionando sin conexión.

---

## Cómo está organizado

```
config.py              rutas del proyecto, resueltas en Windows, macOS y Vertex AI
gcs.py                 acceso al bucket
check_setup.py         verifica que el entorno esté completo
soporte/herramientas/lote_predios.py  arma el lote de grillas que se lleva a búsqueda de predios

reporte/               el reporte
  datos.py               el maestro: enriquece, clasifica y escribe las tablas
  html.py                arma el HTML
  plantilla.py           el diseño, aparte del cálculo
  python -m reporte

insumos/               todo lo que se trae de fuera, siempre crudo y cacheado
  vias · lineas · barras · restricciones · conflicto · satelital · normativa
  python -m insumos bajar | subir | estado | <fuente>

calibracion/           de dónde salen los parámetros de la matriz
  pesos · umbrales · subestaciones
  python -m soporte.calibracion <análisis>
```

`reporte/datos.py` llama a lo que necesita de `insumos/` y descarga lo que falte, así que
en el uso normal no hay que ejecutar nada de esos paquetes a mano. Los de `calibracion/`
no corren nunca solos: sus resultados se pegan a mano en `CRITERIOS` y `PERFILES`.

---

## Los insumos

Todo lo que se descargó alguna vez de un servicio externo está publicado en
`gs://prospectos_solares/insumos/`. Bajarlo evita repetir horas de consultas y garantiza
que dos personas partan del mismo dato:

```bash
.venv/Scripts/python -m insumos bajar
```

| Conjunto | Qué es | Origen |
|---|---|---|
| `osm_vias` | respuestas de Overpass por bloque de celdas | OpenStreetMap |
| `lineas_transmision` | líneas de transmisión, malla nacional | OpenStreetMap |
| `capacidad_barras` | 14 informes de capacidad por barra | UPME |
| `restricciones` | Reserva Forestal de Ley 2ª de 1959 | MinAmbiente, SIAC |
| `conflicto` | acciones bélicas desde 2022, un registro por hecho | SIEVCAC del CNMH |
| `satelital` | una imagen por grilla | Esri World Imagery |
| `normativa` | las normas completas que sustentan los criterios | ver `docs/NORMATIVA.md` |
| `igac_predios` | predios por celda y capa | FeatureServer del IGAC |

**Nada calculado por nosotros vive en el bucket.** Las distancias, las áreas, la
clasificación y el reporte se regeneran con los scripts en minutos, y publicarlos solo
crearía copias que envejecen y acaban contradiciendo al código.

### Qué hace por su cuenta cuando cambian las celdas

- **Distancia a vía.** Consulta a Overpass lo que falte. El caché se nombra por el hash
  de los bbox consultados, no por un número de lote, así que un conjunto distinto de
  celdas nunca reutiliza la respuesta de otro. Si Overpass no responde, lo dice.
- **Ley 2ª.** Se cruza en vivo contra la geometría que llega. No se lee de una tabla
  precalculada, para que no se quede corta cuando aparezcan celdas nuevas.
- **Conflicto armado.** El municipio se resuelve espacialmente contra la base veredal y
  se cruza por código DANE, no por nombre, porque el mismo municipio aparece como TUMACO
  y como SAN ANDRES DE TUMACO según la fuente.
- **Imagen satelital.** Se descarga sola la que falte.
- **Subestaciones, líneas, departamentos, municipios y veredas.** Capas nacionales, se
  recortan a las celdas que haya.
- **Porcentajes de superficie.** Sobre el área real de cada celda, no sobre un valor
  fijo, por si algún día cambia el tamaño de la grilla.

---

## Exclusiones

Se aplican **antes** de puntuar nada. Una celda excluida no compite, no recibe índice y
no suma potencial.

**Figuras jurídicas**, cualquiera basta: parque nacional natural, resguardo indígena,
consejo comunitario, área protegida del RUNAP.

**Altitud** sobre 3.000 m, donde la Ley 1930 de 2018 prohíbe las actividades de alto
impacto. **Cultivos de coca**, por riesgo operativo.

**Conflicto armado**: municipio con tres o más acciones bélicas desde 2022 **y** al menos
tres por cada mil km². Se exigen las dos porque el conteo solo castigaría a los municipios
grandes: Montería tiene tres hechos en 3.093 km², que no describe un territorio en
disputa, mientras que Bugalagrande tiene cuatro en 394 km². Va por municipio y no por
distancia porque el CNMH geocodifica los hechos a un punto de referencia municipal, y un
corte en kilómetros inventaría precisión que el dato no tiene. El umbral está calibrado
contra lo que el sector ya hace: de las diez plantas de 50 MW o más del país, ninguna
está en un municipio que caiga bajo estos filtros.

**Reserva Forestal de Ley 2ª**: solo si cubre el 90% o más de la celda. No es una
prohibición como la de un parque. Reserva el suelo para economía forestal, y darle otro
uso exige que el ministerio sustraiga esa porción, trámite de la Resolución 110 de 2022
del MADS.[^1] Esa resolución pide que la actividad sea de utilidad pública, requisito que
un proyecto solar ya cumple por el artículo 4 de la Ley 1715 de 2014.[^2] Con cobertura
parcial el lote se sitúa fuera del polígono y no hay nada que tramitar.

Queda un cabo suelto de campo: la línea de conexión puede cruzar la reserva aunque los
paneles queden fuera, y para líneas de transmisión la Resolución 110 pide sustracción
temporal.

[^1]: Resolución 110 de 2022 del MADS, que derogó la Resolución 1526 de 2012 salvo sus
    artículos 7 y 8. Fija el plazo en unos 85 días hábiles y remite las compensaciones al
    Manual del Medio Biótico, actualizado por la Resolución 0305 de 2026.

[^2]: Artículo 4 de la Ley 1715 de 2014, en la redacción de la Ley 2099 de 2021. El
    artículo 3 de esa ley es el ámbito de aplicación, no la declaratoria.

Los umbrales viven al principio de `reporte/datos.py`, en `RESTRICCIONES_EXCLUYENTES`,
`EXCLUSIONES_UMBRAL`, `CONFLICTO_DESDE` y `LEY2_EXCLUYE_PCT`.

---

## El índice de aptitud

Siete criterios en escala absoluta. Los tres puntos de cada escala se leen de la
distribución de las celdas del país que ya contienen una planta del tamaño que se busca:

| | |
|---|---|
| `tope` | percentil 10, el decil mejor de lo construido. Vale 100. |
| `bueno` | mediana. «Aquí está la mitad de lo construido». Vale 70. |
| `limite` | percentil 90. «Más allá casi nadie ha construido». Vale 0. |

La nota de cada criterio se interpola entre esos tres puntos y el índice es la suma de
las siete notas por su peso. **No es un cumple o no cumple**: una celda con la subestación
a 15 km saca 49 sobre 100, no cero ni todo. Y como los tres puntos no dependen de las
celdas que se evalúen, un índice de 78 significa lo mismo en cualquier corrida.

El peso de cada criterio es su d de Cohen dividida por la suma de las siete. Se mide
contra las 7.239 celdas que están dentro del radio de una subestación, no contra el país
entero, porque medido contra todo el territorio la cercanía a la red se contaba dos veces.

Para recalcular los parámetros cuando entren plantas nuevas al registro de XM:

```bash
.venv/Scripts/python -m soporte.calibracion umbrales
.venv/Scripts/python -m soporte.calibracion pesos
```

Imprimen los valores nuevos y hay que pegarlos a mano en `reporte/datos.py`. No se
calculan en cada corrida a propósito: obligaría a leer el panel completo y a consultar
Overpass cada vez, y un umbral que cambia solo es un umbral que nadie puede auditar.

**La limitación del método** es la contracara de su virtud. Describe dónde se ha
construido, no dónde conviene construir. Si el sector se equivocó de forma sistemática,
el índice reproduce el error.

---

## Perfiles de proyecto

El mismo terreno no sirve igual para una granja de 50 MW que para una de 1 MW. Los dos
perfiles van en el mismo reporte y se conmutan con la botonera que hay sobre la matriz de
criterios, sin regenerar nada. Cambian los siete umbrales, los pesos y el rango de tensión
del punto de conexión; las exclusiones y las capas son idénticas.

Los pesos también cambian, y no por gusto: medida por tramos de tamaño, la d crece con el
proyecto. De 0,5 a 5 MW va de 0,20 a 0,36; de 20 MW en adelante, de 0,50 a 0,56. Una
planta de 50 MW hace estudio de sitio y un autogenerador de 1 MW se pone donde hay
terreno.

**Salvedad del perfil distribuido.** Un proyecto de 1 a 2 MWp se conecta a un circuito de
media tensión de 13,2 o 34,5 kV y debe quedar a menos de 1,5 km. Esa red no está publicada
en Colombia: no está en OpenStreetMap, que devuelve cero líneas de distribución en Córdoba
y Bolívar; los geoservicios de la UPME no responden; y los portales de datos abiertos
remiten a pedírsela a cada operador. Lo que el perfil mide es la distancia a la subestación
de subtransmisión, de donde cuelgan esos circuitos. Sirve para descartar lo remoto, no para
confirmar la conexión, que exige el Estudio de Conexión Simplificado bajo CREG 174.

El perfil con el que se genera solo decide cuál sale seleccionado al abrir el archivo:

```bash
.venv/Scripts/python -m reporte --perfil distribuida
```

---

## Notas de compatibilidad

Cambios hechos para que el código corra en versiones actuales de las librerías.

- **`PdfMerger` eliminado.** `functions.py` importaba `PyPDF2`, archivado desde 2023, y
  su sucesor `pypdf` eliminó `PdfMerger` en la versión 6. Se cambió por `PdfWriter`, que
  expone la misma interfaz.
- **`import fiona` sin uso.** Retirado. `geopandas` 1.x ya usa `pyogrio`, y tener las dos
  duplica GDAL y puede dar conflictos de DLL en Windows.
- **Normalización Unicode.** macOS guarda los nombres de archivo con las tildes
  descompuestas y Windows las espera precompuestas, así que un archivo con tilde creado en
  un Mac no se encuentra desde Windows aunque el nombre se vea igual. `config.resolver()`
  salva la diferencia.
- **Consola de Windows.** `config.py` fuerza UTF-8 en la salida. Sin eso, un solo carácter
  fuera de cp1252 tumbaba el script entero con `UnicodeEncodeError`.

---

## Pendientes conocidos

**`EPSG:31818`**, que el notebook 2 usa como CRS de entrada y documenta como «UTM 18N
MAGNA-SIRGAS», **no existe** en las versiones actuales de PROJ, ni siquiera como código
retirado. El que encaja con el ejemplo es `EPSG:3117`. Sin resolver a la espera de
confirmarlo con el autor.

**El panel no es reproducible desde el repositorio.** El `.gitignore` excluye
`0. Data Downloads.ipynb` y `1. Additional Layers.ipynb`, que son los notebooks que
construyen el panel de covariables. Es decir, el repositorio contiene el análisis pero no
cómo se produjo su insumo principal. Conviene versionarlos.

**La capa de subestaciones** es un consolidado con vigencias entre 2017 y 2021 y 159 de
sus 499 registros sin fecha. Contrastada contra OpenStreetMap le faltan subestaciones, así
que el operador conviene confirmarlo antes de cualquier gestión comercial. El detalle está
en `python -m soporte.calibracion subestaciones`.

**El stack bayesiano** de los notebooks 1.1 y 1.2 va aparte, en `requirements-bayes.txt`,
porque `pytensor` necesita compilador C y en Windows la vía recomendada es conda-forge y
no pip. No lo instales hasta que se decida si esos notebooks se adaptan al caso solar.
