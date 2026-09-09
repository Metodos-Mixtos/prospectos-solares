# Prospectos Solares

Identificación y caracterización de suelo apto para generación solar fotovoltaica en
Colombia, a partir de datos abiertos y observación de la Tierra.

El procedimiento parte del territorio nacional y termina en una ficha por lote, con su
polígono catastral, su recurso solar, su punto de conexión a la red, su norma urbana, sus
restricciones ambientales y étnicas, y el estado de su registro inmobiliario. Todo sale de
fuentes oficiales citadas y todo se puede volver a generar desde cero.

Métodos Mixtos Consultores.

---

## Índice

1. [Las tres etapas](#las-tres-etapas)
2. [Puesta en marcha, paso a paso](#puesta-en-marcha-paso-a-paso)
3. [El orden en que se corre](#el-orden-en-que-se-corre)
4. [Cómo se corre en detalle](#cómo-se-corre)
5. [La bandeja del bucket](#la-bandeja-del-bucket)
6. [Cómo quedan las carpetas](#cómo-quedan-las-carpetas)
7. [Qué no está en el repositorio](#qué-no-está-en-el-repositorio)
8. [Qué se reproduce igual y qué no](#qué-se-reproduce-igual-y-qué-no)
9. [Cuando algo falla](#cuando-algo-falla)
10. [Documentación](#documentación)

---

## Las tres etapas

El trabajo va en tres escalas. Cada una vive en un sitio distinto y se corre de otra
manera, y conviene no confundirlas.

| | Etapa | Dónde vive | Qué produce |
|---|---|---|---|
| 1 | **Modelo de similitud.** Construye el panel del país, filtra las celdas al alcance de una subestación y las puntúa por parecido con las granjas ya construidas | cuadernos `1.*.ipynb` y `modelo/` | las 100 grillas candidatas |
| 2 | **Reporte de grillas.** Cruza esas candidatas con las fuentes externas, las clasifica y las publica en un visor | `reporte/` | `reporte_grillas.html` y la selección de grillas |
| 3 | **Caracterización de lotes.** Baja el catastro de cada grilla elegida, mide cada lote y lo caracteriza | `ejecutar.py`, `predios/`, `reporte_predios/` | `reporte_predios.html` y el Excel de la corrida |

Los dos diagramas interactivos de [`docs/diagramas/`](docs/diagramas/) cuentan el flujo
completo y se abren en el navegador sin instalar nada:
[`modelo.html`](docs/diagramas/modelo.html) para las etapas 1 y 2, y
[`pipeline.html`](docs/diagramas/pipeline.html) para la 3.

**La costura entre etapas es un archivo.** La etapa 1 deja `top_candidates.gpkg`; sin él,
`reporte/datos.py` se detiene y lo dice. Los cuadernos son exploratorios; de la etapa 2 en
adelante todo es productivo. Los tres archivos de costura viven en la
[bandeja del bucket](#la-bandeja-del-bucket), así que **no hace falta que nadie se los mande
por correo**.

---

## Puesta en marcha, paso a paso

Esto se hace una vez por máquina. Al final hay una comprobación que dice si quedó bien.

### 1. Clonar

```bash
git clone https://github.com/Metodos-Mixtos/prospectos-solares.git
cd prospectos-solares
```

### 2. Python 3.12 y el entorno virtual

**El proyecto se desarrolló y se probó con Python 3.12** (3.12.10 en la máquina de
referencia). La 3.11 debería servir. La 3.13 no se ha comprobado y conviene no estrenarla
aquí: las ruedas geoespaciales tardan en publicarse para cada versión nueva, y `geopandas`,
`rasterio` y `pyogrio` son las primeras en romperse.

```bash
python --version
python -m venv .venv
```

### 3. Las dependencias

Hay **tres ficheros de requisitos y no se instalan los tres**. Esto es lo que hace cada uno:

| Fichero | Qué trae | ¿Hay que instalarlo? |
|---|---|---|
| `requirements.txt` | los 23 paquetes del núcleo: geoespacial, análisis, visualización, cliente de Google Cloud, lectura de PDF y Playwright | **Sí, siempre.** Es el único imprescindible |
| `requirements-lock.txt` | los 77 paquetes con versión exacta, incluidas las dependencias indirectas | Solo si quiere el entorno idéntico al de referencia, o si el anterior le da conflictos |
| `requirements-bayes.txt` | el stack bayesiano de los cuadernos 1.1 y 1.2 | **No, salvo que vaya a correr esos dos cuadernos.** Ver la advertencia |

Lo normal:

```bash
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si prefiere reproducir el entorno exacto en vez de resolver versiones:

```bash
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

**Sobre `requirements-bayes.txt`, dos advertencias que están en el propio fichero.** La
primera es técnica: en Windows, `pytensor`, el motor de compilación de `pymc`, necesita un
compilador de C para ir a velocidad razonable, y sin él cae a un backend de Python puro
mucho más lento. La vía que recomienda el propio proyecto `pymc` en Windows es conda-forge,
no pip. La segunda es de fondo: esos dos cuadernos siguen siendo código heredado del
proyecto DHS/MPI y no están adaptados al caso de paneles solares. No los instale hasta que
se decida adaptarlos o retirarlos.

### 4. El navegador de Playwright

**`pip` no baja este binario. Hay que pedirlo aparte, una sola vez por máquina:**

```bash
.venv\Scripts\python.exe -m playwright install chromium
```

Sin este paso, el paso 4 del procedimiento, el de matrícula inmobiliaria, falla al abrir el
navegador. El código lanza el Chromium empaquetado de Playwright en modo headless, no el
Chrome del sistema, así que no basta con tener Chrome instalado.

### 5. Las credenciales de Google Cloud

Los datos viven en dos buckets del proyecto `prospectos-solares`. Hay **dos vías y se elige
una**. Google no autentica con usuario y contraseña, así que no hay ninguna clave que pegar
en un fichero de texto.

**Vía A, con su propia cuenta.** Es la recomendada para una persona. Caduca cada cierto
tiempo y entonces hay que repetir el tercer comando:

```bash
gcloud auth login
gcloud config set project prospectos-solares
gcloud auth application-default login
gcloud auth application-default set-quota-project prospectos-solares
```

Ojo con la diferencia entre el primero y el tercero, que es donde se equivoca todo el
mundo: `gcloud auth login` autentica **el comando `gcloud`**, y
`gcloud auth application-default login` autentica **el código**. El procedimiento usa el
segundo. Si solo corre el primero, sigue fallando igual.

**Vía B, con una cuenta de servicio.** Para quien no pueda o no quiera abrir un navegador.
Quien administre el proyecto entrega un fichero JSON de clave; usted lo guarda **fuera del
repositorio** y pone su ruta en el `.env`. Con esto no hace falta correr ningún `gcloud`.
Advertencia: una clave de cuenta de servicio no caduca, así que si se pierde el equipo hay
que revocarla en la consola.

### 6. El fichero `.env`

```bash
copy .env.example .env
```

El `.env.example` explica variable por variable para qué sirve y dónde se consigue. **No
trae ningún valor real y no puede traerlo:** el `.gitignore` bloquea `.env`, `.env.*`,
`*.env`, `credenciales*`, `secretos*`, `*.key` y `*.pem`, con una única excepción para la
plantilla. Un fichero de secretos que se cuela en un commit ya no se puede retirar del
historial, y por eso el bloqueo es por patrón y no por nombre exacto.

Son ocho variables y **ninguna impide arrancar**:

| Variable | Para qué | Si falta |
|---|---|---|
| `SNR_USUARIO`, `SNR_CLAVE` | consultar matrícula en la Superintendencia | el paso 4 no consulta y lo dice. El resto corre igual |
| `GOOGLE_APPLICATION_CREDENTIALS` | la ruta al JSON de la cuenta de servicio, si usa la vía B | se usa la sesión personal de `gcloud` |
| `MMC_GEOINFO`, `MMC_PROYECTOS` | apuntar a carpetas de datos que no estén donde por defecto | se usan las rutas por defecto |
| `PROSPECTOS_SIN_BUCKET` | no publicar nada al bucket | se publica normalmente |
| `PANEL_MBG_DIR`, `SALIDA_MBG` | solo para el cuaderno 1.2 | ese cuaderno se detiene y dice cuál falta |

**Las claves de la Superintendencia son personales y no se comparten:** da once consultas
gratuitas al día **por cuenta**, así que usar las de otro no ayuda a nadie.

### 7. Comprobar que quedó bien

```bash
.venv\Scripts\python.exe ejecutar.py --corrida prueba --hasta 0
```

Ese paso **no escribe nada**. Dice qué insumos encuentra, qué claves del `.env` están
puestas sin imprimir ningún valor, si hay acceso al bucket y, si no lo hay, el comando
exacto para arreglarlo. Es lo primero que debería correr quien acaba de clonar.

> **Comprobado el 9 de septiembre de 2026.** Se clonó el repositorio en una carpeta vacía,
> sin `data/`, sin `outputs/` y sin `.env`, y se corrió desde ahí. El paso 1 bajó las
> grillas y la tabla maestra de la bandeja del bucket, y el paso 2 descargó el catastro del
> IGAC desde cero en 432 segundos. No hizo falta ningún fichero de otra máquina.

---

## El orden en que se corre

Esta es la pregunta que hay que responder primero: **qué archivo se corre, y en qué orden.**

### El caso normal: solo un comando

Si las grillas ya están elegidas, que es lo habitual, **basta con esto**:

```bash
.venv\Scripts\python.exe ejecutar.py --corrida <nombre> --grillas ultima
```

`ejecutar.py` encadena los ocho pasos y llama por dentro a `predios_igac`, `lotes`,
`matricula_auto` y `reporte_predios`. **No hay que correr esos módulos a mano**, y hacerlo
para producir un entregable es justamente el error que este punto de entrada existe para
impedir.

### La cadena completa, de principio a fin

Cada eslabón produce el insumo del siguiente. Se corren en este orden, y solo hace falta
retroceder hasta donde algo haya cambiado:

| Orden | Qué se corre | Cuándo hace falta | Produce |
|---|---|---|---|
| 1 | `1. Selección de grillas.ipynb` | solo si hay que rehacer el modelo o cambió el panel | las 100 candidatas, `top_candidates.gpkg` |
| 2 | `python -m reporte` | si cambió el modelo, las fuentes o los umbrales | `reporte_grillas.html` y la tabla maestra |
| 3 | se eligen las grillas en el visor | siempre que se quiera otro conjunto de lotes | `grillas_para_predios.geojson` |
| 4 | `ejecutar.py --corrida <nombre> --grillas ultima` | **siempre.** Es el que produce el entregable | `reporte_predios.html` y el Excel |

Los cuadernos `1.1` y `1.2` son validación del modelo y **no hacen falta** para producir
nada. No están en la cadena.

### Antes de la primera vez

```bash
.venv\Scripts\python.exe ejecutar.py --corrida prueba --hasta 0
```

No escribe nada y dice qué falta. Córralo una vez tras instalar.

### Dos caminos aparte

**El piloto no pasa por `ejecutar.py`.** Tiene su propio encadenado, porque inyecta una
celda que no está entre las 100 candidatas:

```bash
.venv\Scripts\python.exe outputs\piloto\ejecutar_piloto.py
```

**Rehacer solo una parte**, sin repetir lo caro:

```bash
ejecutar.py --corrida <nombre> --desde 5     rehace el visor en minutos
python -m reporte_predios                    solo el visor, suelto
python -m insumos bajar                      traer insumos del bucket
python soporteandeja.py ls                 ver qué hay en la bandeja
```

### Cómo se llaman entre sí

El patrón es el mismo en todo el proyecto: **el `__main__` orquesta y no calcula, `datos.py`
calcula y no maqueta, `html.py` maqueta y no calcula.** Por eso se puede rehacer el HTML tras
tocar el diseño sin recalcular nada.

```
ejecutar.py                       el hilo conductor de la etapa 3
   ├─ predios_igac.main()         paso 2, catastro
   ├─ lotes.main()                paso 3, medición y caracterización
   ├─ matricula_auto              paso 4, registro
   └─ reporte_predios.datos.main() y .html.main()    paso 5, visor

reporte/__main__.py               la etapa 2
   ├─ datos.main()                calcula
   └─ html.main()                 maqueta
```

La etapa 1 es la excepción y no tiene punto de entrada: son los cuadernos, y
`modelo/functions.py` es su librería de apoyo, no un ejecutable. Ahí está la frontera entre
lo exploratorio y lo productivo.

---

## Cómo se corre

**Un solo punto de entrada, y de él salen los ocho pasos en orden:**

```bash
.venv\Scripts\python.exe ejecutar.py --corrida general --grillas ultima
```

| Paso | Qué hace | ¿Detiene la corrida si falla? |
|---|---|---|
| 0 | verifica insumos, credenciales, acceso al bucket y destinos. No escribe nada | sí |
| 1 | normaliza las grillas y completa las columnas que el lote hereda de su celda | sí |
| 2 | baja del catastro del IGAC los terrenos de cada celda, los repara y los mide | sí |
| 3 | mide y caracteriza el lote: entorno, POT, contexto, cribado jurídico y valor | sí |
| 4 | busca la matrícula: portal predial municipal donde exista, Superintendencia donde no | **no** |
| 5 | arma el visor de lotes con su ficha navegable | sí |
| 6 | escribe el Excel de la corrida | no |
| 7 | publica en el bucket y cierra el manifiesto | no |

El paso 4 no detiene la corrida a propósito: quedarse sin cupo diario en la Superintendencia
es una situación prevista, no un fallo. Se escribe el motivo en la ficha del lote, se sigue,
y al día siguiente `--desde 4` continúa donde quedó.

### Banderas de uso diario

| Bandera | Para qué |
|---|---|
| `--corrida <nombre>` | **obligatoria.** De ella salen los tres destinos |
| `--grillas <ref>` | el archivo de celdas. Admite cuatro formas, ver la bandeja |
| `--seco` | imprime el plan y no ejecuta nada |
| `--desde N` / `--hasta N` | corre solo ese tramo. Los pasos 2 y 3 son los caros; con la corrida hecha, `--desde 5` rehace el visor en minutos |
| `--sin-bucket` | no publica nada. Todo queda en disco |
| `--sin-satelital` | se salta la descarga de imágenes, que es lo que más tarda del paso 5 |
| `--sin-snr` / `--limite-snr N` | controla el consumo del cupo diario de la Superintendencia |
| `--seguir-tras-fallo` | no se detiene en ningún paso y anota lo que se saltó |

`ejecutar.py --help` las explica todas.

### La regla que no se rompe

**No se invocan los módulos directamente para producir una corrida.** El 25 de agosto de
2026 se lanzó `python -m predios.lotes --celdas <geojson del piloto>` a mano, y como esa
invocación no redirige los destinos, los 749 lotes del reporte principal quedaron
sustituidos por los 57 del piloto y hubo que recaracterizarlos.

`ejecutar.py` existe para que ese error no se pueda cometer. Antes de ejecutar un solo paso
reescribe la constante de salida de los seis módulos que escriben y **aborta** si alguna
sigue apuntando al proyecto real. Además bloquea la carpeta de la corrida mientras dura.

Correr un módulo suelto para inspeccionarlo está bien y es útil. Correrlo para generar un
entregable, no.

---

## La bandeja del bucket

Hay tres archivos que el procedimiento necesita y **no produce él mismo**: las candidatas
del modelo, la tabla maestra y las grillas elegidas. Antes había que tenerlos en el disco de
quien corría, en rutas que solo existían en esa máquina. Ahora se suben una vez y cualquiera
los lee desde donde esté.

```
gs://prospectos-solares-insumos/entradas/
    candidatas/     las 100 del cuaderno 1 (top_candidates.gpkg)
    maestra/        la tabla maestra de grillas candidatas
    grillas/        las elegidas de esas 100, insumo del paso 1
    certificados/   los folios de tradición y libertad, en PDF
```

```bash
python soporte/bandeja.py ls                     qué hay en cada bandeja
python soporte/bandeja.py ls grillas             el detalle de una
python soporte/bandeja.py subir grillas mis_grillas.geojson
python soporte/bandeja.py bajar grillas ultima
```

`--grillas` y `--maestra` de `ejecutar.py`, y `--celdas` de `python -m reporte`,
admiten **cuatro formas** de nombrar un insumo:

```bash
--grillas outputs/reporte/grillas_para_predios.geojson                  ruta local
--grillas gs://prospectos-solares-insumos/entradas/grillas/x.geojson    objeto del bucket
--grillas x.geojson                                                     nombre en la bandeja
--grillas ultima                                                        el más reciente
```

Si la referencia es una ruta local que existe, no se toca el bucket siquiera. Si no existe,
se busca en la bandeja, y si tampoco está, se dice qué hay en ella en vez de fallar con un
mensaje seco.

**Los certificados funcionan igual.** La bandeja de `predios/certificado_ia.py` se surte del
bucket antes de mirar la carpeta local, así que quien tenga un folio lo sube a
`entradas/certificados/` y el procedimiento lo recoge sin tener el repositorio clonado. Si
el bucket no está a mano se sigue con lo que haya en disco.

---

## Cómo quedan las carpetas

Del repositorio baja **solo código y documentación**. Todo lo demás se crea al correr o se
trae del bucket.

```
prospectos-solares/
│
├── VIENE DEL REPOSITORIO ─────────────────────────────────────────────
│   ejecutar.py              punto de entrada de la etapa 3
│   requirements*.txt        los tres ficheros de dependencias
│   1.*.ipynb, 2.*.ipynb     los cuadernos del modelo y del IGAC
│   modelo/  reporte/  insumos/  predios/  reporte_predios/  soporte/
│   presentacion/  presentacion_sb/
│   docs/                    documentación y los diagramas del flujo
│   .env.example             la plantilla de credenciales, sin ningún valor
│
├── LO CREA USTED, UNA SOLA VEZ ───────────────────────────────────────
│   .venv/                   el entorno de Python
│   .env                     copia de .env.example con sus claves. NUNCA se sube
│   paths.local.json         opcional, si sus datos no están donde por defecto
│
├── SE LLENA SOLO, DESDE EL BUCKET Y LAS FUENTES ──────────────────────
│   data/                    cachés de insumos, compartidas entre corridas
│       igac/  dem/  cobertura/  osm/  satelital/  entorno/  pot/
│       valor/  juridico/  registro/  barras/  lineas/  geoinfo/
│
└── LO PRODUCE CADA CORRIDA ───────────────────────────────────────────
    outputs/
        reporte/             el reporte de grillas y su tabla maestra
        corridas/<corrida>/  todo lo que calcula esa corrida
    entregables/
        <corrida>/           el HTML que se comparte, con su carpeta satelital/
```

El nombre de la corrida es obligatorio y de él salen tres destinos que no se pisan:

| Destino | Qué recibe | ¿Se versiona? |
|---|---|---|
| `outputs/corridas/<corrida>/` | todo lo que se calcula | no |
| `entregables/<corrida>/` | el HTML que se comparte | no |
| `gs://prospectos-solares-salidas/corridas/<corrida>/` | la copia publicada | es el bucket |

**El entregable vive en dos sitios: su máquina y el bucket. En el repositorio, nunca.** Para
compartir un reporte se entrega la carpeta `entregables/<corrida>/` completa, con su
subcarpeta `satelital/` al lado, o se pasa la ruta del bucket.

---

## Qué no está en el repositorio

La regla es de una línea: **al repositorio va el código y la documentación, nada más.**

| Qué | Dónde vive en cambio | Por qué |
|---|---|---|
| `.env` | solo en su máquina | son secretos |
| `entregables/` | su máquina y el bucket | son el producto de una corrida. Pesan cientos de megas y caducan con cada corrida |
| `outputs/` | su máquina y el bucket | trabajo intermedio |
| `data/` | su máquina y el bucket | cachés de insumos, se traen solas |
| `insumos/certificados/` | su máquina y el bucket | los folios traen nombres y cédulas |
| `.venv/` | su máquina | se reconstruye con `requirements.txt` |

Nada de eso se pierde por no estar versionado: los insumos se vuelven a traer y los
entregables se vuelven a generar. Lo que sí se perdería, si se subiera, es el control sobre
unos datos personales y sobre unas credenciales.

---

## Qué se reproduce igual y qué no

Conviene saberlo antes de comparar dos corridas y asustarse.

**La selección de las 100 grillas es determinista.** El cuaderno 1 no fija ninguna semilla
porque no la necesita: no hay muestreo aleatorio en ninguna parte. Con el mismo panel y las
mismas covariables da exactamente las mismas candidatas, en cualquier máquina.

**La validación bayesiana del cuaderno 1.1 no.** Llama a `pm.sample` sin `random_seed` y ata
el número de cadenas a los núcleos de la máquina, así que devuelve resultados
estadísticamente equivalentes pero no idénticos. Si hiciera falta reproducibilidad exacta,
basta con pasarle una semilla.

**La caracterización de lotes depende de la fecha.** Las fuentes se actualizan: la capacidad
por barra de la UPME, los títulos mineros de la ANM, las áreas protegidas del RUNAP y el
catastro del IGAC cambian con el tiempo. Cada corrida deja escrito en `_corrida.json` qué
bajó y cuándo, que es lo que permite comparar dos corridas sabiendo qué se movió.

---

## Cuando algo falla

| Mensaje | Qué pasa y cómo se arregla |
|---|---|
| `RefreshError: Reauthentication is needed` | las credenciales personales caducaron. `gcloud auth application-default login` |
| `Forbidden` o `NotFound` sobre un bucket | la cuenta no tiene permiso. Lo concede quien administre `prospectos-solares` |
| `Cannot find a quota project` | `gcloud auth application-default set-quota-project prospectos-solares` |
| El paso 4 falla al abrir el navegador | falta el binario: `.venv\Scripts\python.exe -m playwright install chromium` |
| `Faltan insumos: grillas de la corrida` | no se pasó `--grillas` y la corrida no tiene uno normalizado. Use `--grillas ultima` |
| `la bandeja X está vacía` | no hay nada subido ahí. `python soporte/bandeja.py subir X <archivo>` |
| Se agotó el cupo de la Superintendencia | es lo previsto. Mañana, `--desde 4` continúa donde quedó |

Cada corrida deja dos ficheros que dicen exactamente qué pasó:
`outputs/corridas/<corrida>/_corrida.json`, el manifiesto con tiempos y resultados de cada
paso, y `_corrida.log`, la salida completa.

---

## Documentación

| | |
|---|---|
| [`docs/REPLICAR.md`](docs/REPLICAR.md) | puesta en marcha en detalle, con los permisos que hay que pedir |
| [`docs/REPORTE.md`](docs/REPORTE.md) | el reporte de grillas, de dónde sale cada umbral |
| [`docs/PREDIOS.md`](docs/PREDIOS.md) | la caracterización de lotes |
| [`docs/ADQUISICION.md`](docs/ADQUISICION.md) | la ruta jurídica y de costos hasta la escritura |
| [`docs/NORMATIVA.md`](docs/NORMATIVA.md) | el marco normativo aplicable |
| [`docs/diagramas/`](docs/diagramas/) | los dos diagramas interactivos del flujo completo |

Cada paquete se explica solo:

```bash
python ejecutar.py --help
python soporte/bandeja.py --help
python -m reporte --help
python -m insumos --help
python -m reporte_predios --help
python -m soporte.calibracion --help
```
