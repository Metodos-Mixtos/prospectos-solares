# Prospectos solares

Identificación y caracterización de terrenos aptos para generación solar en Colombia.

El trabajo va en dos escalas. Primero se busca **en qué cuadrícula de 5 × 5 km conviene
mirar**, que es lo que hace el modelo de similitud del notebook 1 y caracteriza el
reporte. Después se baja a **qué predio concreto de esa cuadrícula se va a visitar**, que
es el bloque de predios.

---

## Ver el reporte

Está generado y listo en [`entregables/`](entregables/). Se abre en el navegador sin
instalar nada.

> Para compartirlo hay que llevar `reporte_grillas.html` **y la carpeta `satelital/`**
> juntos. Así funciona sin conexión.

## Volver a generarlo

```bash
python -m reporte
```

La guía completa, desde instalar el entorno hasta entender de dónde sale cada umbral,
está en **[docs/REPORTE.md](docs/REPORTE.md)**.

---

## Qué hay en cada sitio

| | |
|---|---|
| **`reporte/`** | genera el reporte. `datos.py` es el maestro, `html.py` lo maqueta, `plantilla.py` guarda el diseño aparte del cálculo |
| **`insumos/`** | todo lo que se trae de fuera: vías, líneas, capacidad en barras, restricciones, conflicto, imagen satelital y normativa. Siempre crudo y cacheado |
| **`calibracion/`** | de dónde salen los parámetros de la matriz de criterios. No corre al generar el reporte |
| **`predios/`** | el bloque siguiente: de la cuadrícula al lote |
| **`herramientas/`** | utilidades sueltas, no forman parte del pipeline |
| **`docs/`** | documentación |
| **`entregables/`** | el reporte generado |
| `config.py`, `gcs.py` | base del proyecto: rutas multiplataforma y acceso al bucket |
| `functions.py` | funciones del modelo, usadas por los notebooks |
| `1.*.ipynb`, `2.*.ipynb` | los notebooks del modelo y de la consulta al IGAC |

Cada paquete tiene su propio punto de entrada y se explica solo:

```bash
python -m reporte --help
python -m insumos --help
python -m soporte.calibracion --help
```

---

## Los datos no están aquí

Ni uno. Los insumos crudos viven en `gs://prospectos_solares/insumos/` y se traen con
`python -m insumos bajar`; todo lo calculado se regenera con los scripts en minutos.

Publicar datos en git solo crea copias que envejecen y acaban contradiciendo al código,
así que el `.gitignore` los bloquea por extensión además de por carpeta. La única
excepción es `entregables/`, porque es el producto y no un dato intermedio.

---

## Empezar de cero

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
gcloud auth application-default login
.venv/Scripts/python.exe soporte/herramientas/check_setup.py
```

El verificador dice qué falta y qué se puede correr ya. El detalle de cada paso, incluido
Vertex AI, está en [docs/REPORTE.md](docs/REPORTE.md).
