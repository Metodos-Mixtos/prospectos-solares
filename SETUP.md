# Configuración del entorno

Guía para dejar el proyecto corriendo en una máquina nueva. Probado en Windows 11 con
Python 3.12.

## 1. Entorno virtual

Desde la raíz del proyecto.

**Windows (PowerShell)**

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

Para reproducir exactamente las versiones probadas, usar `requirements-lock.txt` en vez
de `requirements.txt`. **Ojo**: ese lock se generó en Windows con Python 3.12 y fija
versiones con ruedas específicas de plataforma. En Linux o con otra versión de Python
puede no resolver: ahí conviene `requirements.txt`, que solo pone mínimos.

## Los dos entornos del proyecto

Conviene saberlo porque no son el mismo y explica varias cosas del código.

| | Puesto de trabajo local | Vertex AI Workbench |
|---|---|---|
| Sistema | Windows o macOS | Linux, contenedor `workbench-notebooks:m124` |
| Python | 3.12 | 3.14 |
| Entorno | `.venv` de este repo | kernel `pymc_env` de la imagen |
| Acceso a los buckets | `gcloud auth application-default login` | automático, cuenta de servicio de la VM |

El metadata de `1. Selección de grillas.ipynb` declara el segundo, así que ese notebook
se ejecutó en Google Cloud y no en un portátil. De ahí que los insumos vivan en GCS y
no en el Drive: desde Vertex AI el bucket se lee sin configurar nada.

En Vertex AI no hace falta ni el `login_gcp.bat` ni el paso de autenticación. Basta con
clonar el repo, instalar `requirements.txt` en el kernel y correr los scripts: `gcs.py`
toma las credenciales de la máquina.

Las rutas de Google Drive que aparecían en el notebook eran un residuo de trabajo local
anterior. `config.py` las sustituye y resuelve en los tres escenarios.

## 2. Kernel de Jupyter

Para que VS Code o JupyterLab vean el entorno.

```powershell
.venv\Scripts\python.exe -m ipykernel install --user --name prospectos-solares --display-name "Python (prospectos-solares)"
```

En VS Code, abrir un notebook y elegir ese kernel arriba a la derecha.

## 3. Verificar

```powershell
.venv\Scripts\python.exe check_setup.py
```

Comprueba las librerías, que `functions.py` importe y que las rutas de datos resuelvan.
Informa de todo lo que falta en vez de detenerse en el primer error.

## 4. Datos

Los insumos del proyecto viven en **Google Cloud Storage**, en el proyecto de GCP
`mmc-general`, repartidos en dos buckets que corresponden a las dos raíces que antes se
leían del Google Drive montado.

| Bucket | Contenido | Región |
|---|---|---|
| `geoinfo` | Capas geográficas base compartidas del equipo | southamerica-west1 |
| `prospectos_solares` | Insumos y salidas propios de este proyecto | us-east1 |

### Autenticación

Se usan credenciales de aplicación por defecto, iniciando sesión con tu propia cuenta.
No hace falta descargar claves de servicio.

```powershell
winget install Google.CloudSDK
```

```powershell
gcloud auth application-default login
```

```powershell
gcloud config set project mmc-general
```

Para verificar el acceso:

```powershell
.venv\Scripts\python.exe gcs.py auth
```

### Explorar y descargar

```powershell
.venv\Scripts\python.exe gcs.py ls geoinfo
```

`gcs.py` descarga a una caché local en `./data`, replicando la estructura del bucket, y
devuelve rutas de archivo normales. Los notebooks siguen leyendo rutas locales, así que
no hay que cambiar la lógica de lectura. Un archivo ya descargado no se vuelve a bajar
salvo que cambie de tamaño en el bucket.

Desde un notebook:

```python
import gcs
ruta = gcs.obtener("geoinfo", "Colombia/Energia_electrica/Subestaciones.geojson")
```

### Otras vías

`config.py` resuelve las rutas en este orden, por si se trabaja sin acceso al bucket.

1. Variables de entorno `MMC_GEOINFO` y `MMC_PROYECTOS`
2. Archivo `paths.local.json` en la raíz del proyecto, que no se versiona
3. Google Drive para escritorio, si está montado (busca las unidades compartidas
   `Data Science` y `Projectos Activos`, en inglés o en español)
4. Carpeta local `./data`, que es donde `gcs.py` deja lo descargado

Para ver qué está resolviendo en esta máquina.

```powershell
.venv\Scripts\python.exe config.py
```

Si trabajas con copias locales de los datos, crea `paths.local.json` así.

```json
{
  "geoinfo": "D:/datos/geoinfo",
  "proyectos": "D:/datos/proyectos"
}
```

## Qué necesita datos y qué no

| Notebook | ¿Necesita los buckets? | Nota |
|---|---|---|
| 1. Selección de grillas | Sí | Panel de grillas y capas de XM y subestaciones |
| 1.1. Precisión del modelo | Sí | Además es código heredado del proyecto DHS, sin adaptar |
| 1.2. Test del modelo | Sí | Igual que el anterior |
| 2. IGAC_Consulta_Predios | No | Descarga los predios del FeatureServer del IGAC |

## Insumos derivados, en el bucket

Además de los insumos originales, el proyecto usa datos que se descargan de fuentes
externas por el camino: la red vial de OpenStreetMap y los predios del IGAC. Si viven
solo en el disco de quien los bajó, el proyecto deja de ser reproducible.

Por eso se publican en `gs://prospectos_solares/insumos/`, y los scripts los buscan
allí antes de salir a la fuente original.

```powershell
.venv\Scripts\python.exe insumos.py estado
```

```powershell
.venv\Scripts\python.exe insumos.py bajar
```

```powershell
.venv\Scripts\python.exe insumos.py subir
```

**Al bucket solo van insumos crudos**, es decir la respuesta de la fuente externa tal
cual llega y que no se puede reconstruir sin volver a ella:

| Prefijo | Qué contiene |
|---|---|
| `insumos/osm_vias/` | Respuestas de Overpass, una por lote de celdas |
| `insumos/igac_predios/` | Respuestas del FeatureServer del IGAC, por celda y capa |
| `insumos/lineas_transmision/` | Líneas de transmisión de OSM, por lote |
| `insumos/capacidad_barras/` | Los catorce informes de capacidad por barra de la UPME |

Todo lo que calculamos nosotros (distancias, áreas, clasificaciones, el consolidado de
predios, el reporte) se queda fuera. Se regenera con los scripts en segundos, y
publicarlo solo crearía copias que envejecen y acaban contradiciendo al código.

## Capacidad en barras

La UPME calcula este dato con el Modelo de Asignación de Capacidad para Conexión y lo
publica por ciclo de asignación como anexo de circular, no como servicio consultable.
Del ciclo 2023-2024 salieron catorce informes, uno por subárea operativa, publicados por
la **Circular UPME 077 de 2024**: para cada barra del STN y del STR, la capacidad en MW
año por año del horizonte 2024-2037, con el escenario crítico y el elemento que la
limita. Son PDF de varios cientos de páginas, pero traen capa de texto.

```powershell
.venv\Scripts\python.exe capacidad_barras.py descargar
```

```powershell
.venv\Scripts\python.exe capacidad_barras.py extraer
```

```powershell
.venv\Scripts\python.exe capacidad_barras.py cargar
```

`descargar` trae los catorce informes a `data/barras/upme/`, unos 100 MB, comprobando el
tamaño contra el `Content-Length` porque alguno llega truncado y un PDF a medias no falla
al bajarse sino al leerse. `extraer` los parsea, empareja las 1108 barras con la capa de
subestaciones del SIN y deja el CSV en `data/barras/`. `cargar` lo cruza con las
candidatas. Después conviene `insumos.py subir`, para que el resto del equipo no repita
los 100 MB de descarga.

El emparejamiento entre las dos fuentes es por nombre y tensión, con tres concesiones a
que son fuentes distintas: 220 y 230 kV cuentan como la misma barra, el prefijo "Nueva"
se ignora solo si nadie ocupa ya ese nombre, y hay cuatro alias comprobados a mano contra
departamento y municipio, porque hay homónimas (San Marcos es la de Sucre a 110 kV y la
de Yumbo a 115, 220 y 500). Casan 301 de las 488 subestaciones del SIN, y 32 de las 33 a
las que se conectarían las candidatas. La que falta es Tebaida 2 115 kV: el informe de
Caldas-Quindío-Risaralda solo trae las barras de 13,2 y 33 kV de esa subestación.

Las 187 que no casan son casi todas diferencias de nomenclatura del mismo tipo, con el
lugar pegado al nombre para desambiguar homónimas: `Barbosa - Antioquia 220 kV`,
`Belén - Cucutá 230 kV`, `Bavaria -Bogotá 115 kV`. No se resuelven con una regla general
a propósito: quitar el sufijo hace que `Barbosa` case con la de Antioquia o la de
Santander según el orden, y un cruce equivocado aquí mueve una decisión de localización.
Si alguna hace falta, se añade a `ALIAS` en `capacidad_barras.py` tras comprobarla contra
el departamento y el municipio, que es como se comprobaron las cuatro que hay.

### Qué mide y qué no

Es la capacidad **por barra**: cuánta generación admite el nodo según los límites de red,
antes de descontar lo que se haya asignado después en el propio ciclo. Es el techo físico
del punto de conexión, no el cupo libre de hoy, y conviene mirar el horizonte completo
antes que un año suelto: Planeta Rica 110 kV da 0,15 MW en 2026 y 80,3 en 2027, cuando
entra una obra de expansión. Por eso el CSV lleva también el mínimo y el máximo del
horizonte. Para descartar nodos saturados y ordenar candidatas sirve; para comprometer un
punto de conexión hay que confirmarlo con el operador de red.

El régimen cambió: la Resolución CREG 101 094 de 2025 y la UPME 358 de 2026 movieron esta
información al "Repositorio de Transportadores" de la Ventanilla Única, que exige
registro. Mientras eso siga cerrado, el ciclo 2023-2024 es el último dato abierto.

Si aparece una fuente mejor, `cargar` recoge cualquier CSV que se deje en `data/barras/`
con las columnas `subestacion` y `capacidad_disponible_mw`, decimales con coma.
`capacidad_barras.py plantilla` genera uno vacío con las subestaciones que hacen falta.

## Generar el reporte de caracterización

Cuatro pasos, en este orden. El primero necesita que el notebook 1 haya dejado
`top_candidates.gpkg`.

```powershell
.venv\Scripts\python.exe distancia_vias.py
```

Descarga de OpenStreetMap la red vial alrededor de cada grilla y calcula la distancia a
vía carrozable y a vía principal. Cachea en `data/osm/`, así que solo se paga una vez.

```powershell
.venv\Scripts\python.exe capacidad_barras.py descargar; .venv\Scripts\python.exe capacidad_barras.py extraer
```

Trae los informes de la UPME y deja el CSV de capacidad en `data/barras/`. Junto con el
anterior, son los dos pasos que necesitan internet abierto; los dos cachean, así que
solo se pagan una vez.

```powershell
.venv\Scripts\python.exe reporte_grillas.py
```

Cruza las candidatas con el panel, las subestaciones, los departamentos y las vías.
Deja en `outputs/reporte/` el CSV, el XLSX, el GPKG y el JSON.

```powershell
.venv\Scripts\python.exe reporte_html.py
```

Arma el reporte visual `outputs/reporte/reporte_grillas.html`, con el mapa en SVG y la
tabla filtrable. Se abre en cualquier navegador, sin servidor. El marcado vive en
`plantilla_reporte.py`, separado de la lógica de datos.

### Qué queda en outputs/reporte/

| Archivo | Para qué |
|---|---|
| `reporte_grillas.html` | Reporte navegable, con mapa, zonas y simulador de umbrales |
| `grillas_candidatas.xlsx` | Tabla con formato, para compartir y anotar |
| `grillas_candidatas.csv` | Lo mismo en plano, para cargar en cualquier herramienta |
| `grillas_candidatas.kml` | Google Earth, con ficha emergente por polígono |
| `grillas_candidatas.gpkg` | QGIS y ArcGIS, con geometría y todos los atributos |
| `grillas_candidatas.geojson` | Para web y para herramientas que no leen GeoPackage |
| `zonas_prospeccion.csv` | Resumen por zona, que es la unidad de trabajo de campo |
| `concurrencia_subestaciones.csv` | Cuántas candidatas compiten por cada punto de conexión |
| `capacidad_barras.csv` | Capacidad UPME cruzada con la concurrencia, con el veredicto de cupo |
| `distancia_vias.csv` | Salida intermedia de `distancia_vias.py`, se recoge sola |
| `grillas_candidatas.json` | Insumo del HTML, no pensado para consumo directo |

### Supuestos que se pueden discutir

Están todos como constantes con nombre al principio de `reporte_grillas.py`, para
cambiarlos sin bucear en el código.

- `PENDIENTE_BUENA` y `PENDIENTE_LIMITE`, hoy 5° y 10°
- `DIST_SUBEST_BUENA` y `DIST_SUBEST_LIMITE`, hoy 15 y 30 km
- `HA_POR_MWP`, hoy 1,5 ha por MWp, huella típica de planta en suelo con seguidor
- `FACTOR_PENDIENTE`, cuánta superficie sigue sirviendo según la inclinación
- `COBERTURAS_APTAS`, qué usos del suelo se consideran aprovechables

El reporte HTML además permite mover los cuatro umbrales de clasificación con
deslizadores y ver la reclasificación en vivo, sin volver a correr nada.

## Reproducibilidad, pendiente conocido

El `.gitignore` excluye `0. Data Downloads.ipynb` y `1. Additional Layers.ipynb`, que son
los notebooks que construyen el panel de covariables a partir de las capas base. Es decir,
el repositorio contiene el análisis pero no cómo se produjo su insumo principal, y quien
clone el proyecto no puede reconstruirlo. Conviene versionarlos.

## Stack bayesiano

Los notebooks 1.1 y 1.2 necesitan `pymc`, que va aparte porque en Windows es delicado.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-bayes.txt
```

`pytensor`, el motor de compilación de pymc, necesita un compilador C para rendir. Sin
él cae a un backend en Python puro que es mucho más lento. La vía recomendada por el
proyecto pymc en Windows es conda-forge, no pip. No instales esto hasta que se decida
si esos dos notebooks se adaptan al caso solar o se retiran.

## Notas de compatibilidad

Cambios hechos para que el código corriera en versiones actuales de las librerías.

- **`PdfMerger` eliminado.** `functions.py` importaba `PyPDF2`, archivado desde 2023.
  Su sucesor `pypdf` eliminó `PdfMerger` en la versión 6. Se cambió por `PdfWriter`,
  que expone la misma interfaz, dejando `PyPDF2` como respaldo.
- **`import fiona` sin uso.** Se retiró. `geopandas` 1.x ya usa `pyogrio`, y tener
  las dos librerías instaladas duplica GDAL y puede dar conflictos de DLL en Windows.
- **Normalización Unicode.** macOS guarda los nombres de archivo con las tildes
  descompuestas y Windows las espera precompuestas, así que un archivo con tilde creado
  en un Mac no se encuentra desde Windows aunque el nombre se vea igual. `config.resolver()`
  salva la diferencia.

## Pendiente conocido

`EPSG:31818`, que el notebook 2 usa como CRS de entrada por defecto y documenta como
"UTM 18N MAGNA-SIRGAS", **no existe** en las versiones actuales de PROJ. El notebook
falla al transformar la geometría antes de llegar a consultar nada. El código que encaja
con el ejemplo es `EPSG:3117` (MAGNA-SIRGAS / Colombia East Central zone). La tabla de
CRS del notebook también repite `3116` en dos filas con descripciones distintas. Sin
resolver a la espera de confirmarlo con el autor.
