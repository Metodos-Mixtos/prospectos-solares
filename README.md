# Prospectos Solares

Identificación y caracterización de suelo apto para generación solar fotovoltaica en
Colombia, a partir de datos abiertos y observación de la Tierra.

El procedimiento parte del territorio nacional y termina en una ficha por lote, con su
polígono catastral, su recurso solar, su punto de conexión a la red, su norma urbana, sus
restricciones ambientales y étnicas, y el estado de su registro inmobiliario. Todo sale de
fuentes oficiales citadas, y todo se puede volver a generar desde cero.

Métodos Mixtos Consultores.

---

## Las tres etapas

El trabajo va en tres escalas y conviene no confundirlas, porque cada una vive en un sitio
distinto del repositorio y se corre de otra manera.

| | Etapa | Dónde vive | Qué produce |
|---|---|---|---|
| 1 | **Modelo de similitud.** Construye el panel georreferenciado del país, filtra las celdas al alcance de una subestación y las puntúa por parecido con las granjas solares ya construidas | cuadernos `1.*.ipynb` y `modelo/` | las 100 grillas candidatas |
| 2 | **Reporte de grillas.** Cruza esas candidatas con las fuentes externas, las clasifica y las publica en un visor navegable | `reporte/` | `reporte_grillas.html` y la selección de grillas |
| 3 | **Caracterización de lotes.** Baja el catastro de cada grilla elegida, mide cada lote y lo caracteriza | `ejecutar.py`, `predios/`, `reporte_predios/` | `reporte_predios.html` y el Excel de la corrida |

Los dos diagramas interactivos de [`docs/diagramas/`](docs/diagramas/) cuentan el flujo
completo. Se abren en el navegador sin instalar nada:

- [`modelo.html`](docs/diagramas/modelo.html), del panel a las grillas, o sea las etapas 1 y 2.
- [`pipeline.html`](docs/diagramas/pipeline.html), de las grillas a los entregables, la etapa 3.

**La costura entre la etapa 1 y el resto es un archivo**, `top_candidates.gpkg`. Si no
existe, `reporte/datos.py` se detiene y lo dice: «Corre antes el notebook 1 para generar las
candidatas». Los cuadernos son exploratorios; de la etapa 2 en adelante todo es productivo.

---

## Puesta en marcha en una máquina nueva

```bash
git clone https://github.com/Metodos-Mixtos/prospectos-solares.git
cd prospectos-solares

python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Después, las credenciales de Google Cloud, que son las que dan acceso a los datos:

```bash
gcloud auth login
gcloud config set project prospectos-solares
gcloud auth application-default login
gcloud auth application-default set-quota-project prospectos-solares
```

Y por último las claves propias del proyecto:

```bash
copy .env.example .env
```

El `.env.example` explica variable por variable para qué sirve cada una y dónde se
consigue. **No trae ningún valor real y no lo puede traer:** el `.gitignore` bloquea
`.env`, `.env.*`, `*.env`, `credenciales*`, `secretos*`, `*.key` y `*.pem`, con una única
excepción para la plantilla. Un fichero de secretos que se cuela en un commit ya no se puede
retirar del historial, y por eso el bloqueo es por patrón y no por nombre exacto.

Hay dos claves que cada persona tiene que conseguirse por su cuenta, `SNR_USUARIO` y
`SNR_CLAVE`, de la Superintendencia de Notariado y Registro. No viajan en el repositorio y
no se pueden compartir: la Superintendencia da once consultas gratuitas al día **por
cuenta**.

Para comprobar que todo quedó en su sitio, sin ejecutar nada todavía:

```bash
.venv\Scripts\python.exe ejecutar.py --corrida prueba --hasta 0
```

Ese paso no escribe nada. Dice qué insumos encuentra, qué claves del `.env` están puestas
sin imprimir ningún valor, si hay acceso al bucket y, si no lo hay, el comando exacto para
arreglarlo. Es lo primero que debería correr quien acaba de clonar.

La guía larga, con los permisos que hay que pedir, cuántos datos hay que bajar y qué no se
puede reproducir, está en **[docs/REPLICAR.md](docs/REPLICAR.md)**.

---

## Cómo se corre

**Un solo punto de entrada, y de él salen los ocho pasos en orden:**

```bash
.venv\Scripts\python.exe ejecutar.py --corrida general --grillas outputs/reporte/grillas_para_predios.geojson
```

| Paso | Qué hace | Detiene la corrida si falla |
|---|---|---|
| 0 | verifica insumos, credenciales, acceso al bucket y destinos. No escribe nada | sí |
| 1 | normaliza las grillas de entrada y completa las columnas que el lote hereda de su celda | sí |
| 2 | baja del catastro del IGAC los terrenos de cada celda, los repara y los mide | sí |
| 3 | mide y caracteriza el lote: entorno, POT, contexto, cribado jurídico y valor | sí |
| 4 | busca la matrícula inmobiliaria: portal predial municipal donde exista, Superintendencia donde no | **no** |
| 5 | arma el visor de lotes con su ficha navegable | sí |
| 6 | escribe el Excel de la corrida | no |
| 7 | publica en el bucket y cierra el manifiesto | no |

El paso 4 no detiene la corrida a propósito: quedarse sin cupo diario en la Superintendencia
es una situación prevista, no un fallo. Se escribe el motivo en la ficha del lote y se sigue.

### Banderas que se usan a diario

| Bandera | Para qué |
|---|---|
| `--corrida <nombre>` | **obligatoria.** De ella salen los tres destinos de la corrida |
| `--grillas <archivo>` | el GeoJSON, GeoPackage o CSV de celdas. Solo hace falta en la primera pasada |
| `--seco` | imprime el plan y no ejecuta nada |
| `--desde N` / `--hasta N` | corre solo ese tramo. Los pasos 2 y 3 son los caros; con la corrida hecha, `--desde 5` rehace el visor en minutos |
| `--sin-bucket` | no publica nada. Todo queda en disco |
| `--sin-satelital` | se salta la descarga de imágenes, que es lo que más tarda del paso 5 |
| `--sin-snr` / `--limite-snr N` | controla el consumo del cupo diario de la Superintendencia |
| `--seguir-tras-fallo` | no se detiene en ningún paso y anota lo que se saltó |

Hay más, y `ejecutar.py --help` las explica todas.

### La regla que no se rompe

**No se invocan los módulos directamente para producir una corrida.** El 25 de agosto de
2026 se lanzó `python -m predios.lotes --celdas <geojson del piloto>` a mano, y como esa
invocación no redirige los destinos, los 749 lotes del reporte principal quedaron
sustituidos por los 57 del piloto y hubo que recaracterizarlos.

`ejecutar.py` existe para que ese error no se pueda cometer. Antes de ejecutar un solo paso
reescribe la constante de salida de los seis módulos que escriben y **aborta** si alguna
sigue apuntando al proyecto real. Además bloquea la carpeta de la corrida mientras dura, de
modo que dos procesos no pueden escribir a la vez en el mismo destino.

Correr un módulo suelto para inspeccionarlo está bien y es útil. Correrlo para generar un
entregable, no.

---

## La bandeja del bucket: nada depende de una ruta local

Hay tres archivos que el procedimiento necesita y que **no produce él mismo**: las
candidatas del modelo, la tabla maestra y las grillas elegidas. Antes había que tenerlos
en el disco de quien corría, en una ruta que solo existía en esa máquina. Eso ataba el
proyecto a un computador y obligaba a mandarse ficheros por correo.

Ahora se suben una vez a la bandeja del bucket y cualquiera los lee desde donde esté:

```
gs://prospectos-solares-insumos/entradas/
    candidatas/     las 100 que salen del cuaderno 1 (top_candidates.gpkg)
    maestra/        la tabla maestra de grillas candidatas
    grillas/        las elegidas de esas 100, insumo del paso 1
    certificados/   los folios de tradición y libertad, en PDF
```

Se maneja así:

```bash
python soporte/bandeja.py ls                      qué hay en cada bandeja
python soporte/bandeja.py ls grillas              el detalle de una
python soporte/bandeja.py subir grillas mis_grillas.geojson
python soporte/bandeja.py bajar grillas ultima
```

Y `ejecutar.py` admite las cuatro formas de nombrar un insumo, sin que cambie nada más:

```bash
ejecutar.py --corrida x --grillas outputs/reporte/grillas_para_predios.geojson
ejecutar.py --corrida x --grillas gs://prospectos-solares-insumos/entradas/grillas/melgar.geojson
ejecutar.py --corrida x --grillas melgar.geojson       por su nombre en la bandeja
ejecutar.py --corrida x --grillas ultima               el más reciente que haya
```

Si la referencia es una ruta local que existe, no se toca el bucket siquiera. Si no
existe, se busca en la bandeja, y si tampoco está se dice qué hay en ella en vez de
fallar con un mensaje seco.

**Los certificados funcionan igual.** La bandeja de `predios/certificado_ia.py` se surte
del bucket antes de mirar la carpeta local, así que quien tenga un folio lo sube a
`entradas/certificados/` y el procedimiento lo recoge, sin necesidad de tener el
repositorio clonado. Si el bucket no está a mano se sigue con lo que haya en disco, como
antes.

---

## Cómo quedan las carpetas en la máquina local

Del repositorio baja **solo código y documentación**. Todo lo demás se crea al correr, o se
trae del bucket. Así queda la carpeta de trabajo una vez montado:

```
prospectos-solares/
│
├── VIENE DEL REPOSITORIO ─────────────────────────────────────────────
│   ejecutar.py              punto de entrada de la caracterización de lotes
│   requirements.txt
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

**Ninguna de las tres últimas se versiona.** El `.gitignore` bloquea `data/`, `outputs/`,
`entregables/`, `.venv/` y todo lo que huela a credencial. Si al clonar no ve esas carpetas
es porque todavía no ha corrido nada, y está bien.

### Dónde queda cada cosa cuando corre

El nombre de la corrida es obligatorio y de él salen tres destinos que no se pisan:

| Destino | Qué recibe | ¿Se versiona? |
|---|---|---|
| `outputs/corridas/<corrida>/` | todo lo que se calcula | no |
| `entregables/<corrida>/` | el HTML que se comparte | no |
| `gs://prospectos-solares-salidas/corridas/<corrida>/` | la copia publicada | es el bucket |

`config.destino_corrida` valida el nombre, rechaza separadores de ruta y `..`, y prohíbe
expresamente escribir en `outputs/reporte` o en la raíz de `entregables/`.

**El entregable vive en dos sitios: su máquina y el bucket.** En el repositorio, nunca. Para
compartir un reporte se entrega la carpeta `entregables/<corrida>/` completa, con su
subcarpeta `satelital/` al lado, o se pasa la ruta del bucket. Nunca el enlace al
repositorio, porque ahí no está.

---

## Mapa del repositorio

| | |
|---|---|
| **`ejecutar.py`** | el hilo conductor. Punto de entrada único de la etapa 3 |
| **`modelo/`** | las funciones del modelo de similitud que usan los cuadernos 1, 1.1 y 1.2 |
| **`reporte/`** | el reporte de grillas. `datos.py` calcula, `html.py` maqueta, `plantilla.py` guarda el diseño aparte |
| **`insumos/`** | todo lo que se trae de fuera: vías, líneas, capacidad en barras, restricciones, conflicto, imagen satelital y normativa. Siempre crudo y cacheado |
| **`predios/`** | de la grilla al lote. `predios_igac.py` baja el catastro, `terreno.py` mide, `lotes.py` filtra y clasifica, `entorno.py` y `pot.py` cruzan capas, `juridico.py` mira UAF y restitución, `matricula*.py` buscan la matrícula, `certificado_ia.py` lee el folio con un modelo de lenguaje |
| **`reporte_predios/`** | el visor de lotes: mapa por grilla, lista con filtros y ficha descargable por lote |
| **`soporte/`** | lo que sostiene a los demás. `config.py` resuelve rutas y destinos, `gcs.py` habla con el bucket. `calibracion/` documenta de dónde sale cada umbral y `herramientas/` son utilidades sueltas |
| **`presentacion/`, `presentacion_sb/`** | las presentaciones en LaTeX, con sus figuras y su verificador |
| **`docs/`** | la documentación, y en `docs/diagramas/` los dos diagramas interactivos |
| **`entregables/`** | lo que ve el cliente. **No se versiona:** lo produce cada corrida en la máquina de quien la lanza |
| `1.*.ipynb`, `2.*.ipynb` | los cuadernos del modelo y de la consulta al IGAC. Se abren desde la raíz, que es desde donde resuelven sus importaciones |
| **`outputs/`**, **`data/`** | carpetas de trabajo. **No van al repositorio** |

Cada paquete se explica solo:

```bash
python -m reporte --help
python -m insumos --help
python -m reporte_predios --help
python -m soporte.calibracion --help
python ejecutar.py --help
```

---

## Qué no está en el repositorio, y por qué

La regla es de una línea: **al repositorio va el código y la documentación, nada más.**

| Qué | Dónde vive en cambio | Por qué |
|---|---|---|
| `.env` | solo en su máquina | son secretos. Se copia de `.env.example` y se rellena en cada máquina. Un fichero de credenciales que entra en un commit ya no se puede sacar del historial |
| `entregables/` | su máquina y el bucket | son el producto de una corrida. Pesan cientos de megas, caducan con cada corrida y dos personas nunca tendrían la misma copia |
| `outputs/` | su máquina y el bucket | trabajo intermedio de cada corrida |
| `data/` | su máquina y el bucket | cachés de insumos. Se traen con el propio procedimiento |
| `insumos/certificados/` | su máquina y el bucket | los folios de matrícula traen nombres y cédulas |
| `.venv/` | su máquina | se reconstruye con `requirements.txt` |

Nada de eso se pierde por no estar versionado: los insumos se vuelven a traer del bucket y
los entregables se vuelven a generar. Lo que sí se perdería, si se subiera, es el control
sobre unos datos personales y sobre unas credenciales.

---

## Qué se reproduce igual y qué no

Esto conviene saberlo antes de comparar dos corridas y asustarse.

**La selección de las 100 grillas es determinista.** El cuaderno 1 no fija ninguna semilla
porque no la necesita: no hay muestreo aleatorio en ninguna parte. Es aritmética. Con el
mismo panel y las mismas covariables da exactamente las mismas candidatas, en cualquier
máquina.

**La validación bayesiana del cuaderno 1.1 no.** Llama a `pm.sample` sin `random_seed` y ata
el número de cadenas a los núcleos de la máquina, así que devuelve resultados
estadísticamente equivalentes pero no idénticos. Si hiciera falta reproducibilidad exacta,
basta con pasarle una semilla.

**La caracterización de lotes depende de la fecha.** Las fuentes se actualizan: la capacidad
por barra de la UPME, los títulos mineros de la ANM, las áreas protegidas del RUNAP y el
catastro del IGAC cambian con el tiempo. Cada corrida deja escrito en `_corrida.json` qué
bajó y cuándo, que es lo que permite comparar dos corridas sabiendo qué se movió.

---

## Documentación

| | |
|---|---|
| [`docs/REPLICAR.md`](docs/REPLICAR.md) | puesta en marcha en una máquina nueva, permisos incluidos |
| [`docs/REPORTE.md`](docs/REPORTE.md) | el reporte de grillas en detalle, de dónde sale cada umbral |
| [`docs/PREDIOS.md`](docs/PREDIOS.md) | la caracterización de lotes |
| [`docs/ADQUISICION.md`](docs/ADQUISICION.md) | la ruta jurídica y de costos hasta la escritura |
| [`docs/NORMATIVA.md`](docs/NORMATIVA.md) | el marco normativo aplicable |
| [`docs/CONTINUIDAD.md`](docs/CONTINUIDAD.md) | estado del trabajo y qué sigue |
| [`docs/diagramas/`](docs/diagramas/) | los dos diagramas interactivos del flujo completo |
