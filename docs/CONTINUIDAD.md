# Estado del trabajo y cómo continuarlo

Documento de traspaso. Si una sesión se corta, quien la retome (persona o agente) lee esto
primero. Última actualización: 2026-08-25 (reordenación del repositorio; ver la última sección).

---

## Reglas del proyecto que no se negocian

Fijadas por Samuel (Métodos Mixtos Consultores). Se aplican siempre.

- **Nada de datos en el repositorio.** Solo código, documentación y los HTML de
  `entregables/`. Datos crudos, cachés e imágenes van al bucket
  `gs://prospectos_solares/insumos/` (alias `prospectos` en `soporte/gcs.py`).
- **Sin push ni pull sin permiso explícito**, siempre a la rama `caracterizacion-grillas`,
  nunca a `main`. Sin marca de Claude en los mensajes de commit. Sin secretos.
- **Agnóstico al insumo.** Todo debe funcionar con las grillas que lleguen (5, 10, 100 u
  otras 100 de una nueva corrida del modelo de Daniel).
- **Comentarios y docstrings breves y profesionales.** Módulo ≤12 líneas, función 1 a 3,
  en línea solo si hace falta. Sin narrativa ni tono coloquial. Sin guiones largos.
- **Toda cifra que se cite en código, doc o cuaderno debe coincidir con la salida real.**
- **El tamaño del lote no descarta.** Lo define el cliente en el visor (área del lote,
  ancho, cobertura apta, índice, valor, POT, minería). Decisión de Samuel, 2026-08-19.
- **Se dice "lote", no "predio"** en visor, fichas, documentos y mensajes (Samuel,
  2026-08-19). Los nombres de módulos y comandos (`predios/`, `reporte_predios`) se
  conservan para no romper rutas; "predio" solo cuando se cita el término del catastro.
- **Sin "área útil" en lo que se muestra.** La cobertura y la pendiente se describen como
  fracciones; el cálculo de área útil es heurística propia y queda solo como columna
  auxiliar del CSV. Potencia indicativa = área del lote / ha por MWp (calibrado con XM).

---

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Reporte de grillas (paso 1) | `reporte/`, salida `entregables/reporte_grillas.html` |
| Bloque de predios (paso 2) | `predios/` (`predios_igac`, `terreno`, `lotes`, `juridico`, `valor`, `entorno`, `pot`, `registro`, `certificados`) |
| Visor de predios por grilla | `reporte_predios/`, salida `entregables/reporte_predios.html` |
| Cuaderno del paso 2 | `2. IGAC_Consulta_Predios.ipynb` (única línea a cambiar: `CELDAS = "ruta"`) |
| Comprobación automática | `soporte/herramientas/probar_reporte_predios.py` |
| Documentación | `README.md`, `docs/REPORTE.md`, `docs/PREDIOS.md`, `docs/ADQUISICION.md`, `docs/NORMATIVA.md` |
| Matrícula inmobiliaria | `predios/matricula.py` y `predios/matricula_auto.py`; el cosechador municipal, en `outputs/matricula/cosechar_municipal.py`; cobertura en `outputs/matricula/COBERTURA.md` |
| Funciones del modelo (cuadernos 1.x) | `modelo/functions.py` (estuvo en la raíz hasta el 25-ago-2026) |
| Carpeta de trabajo | `outputs/`, con su propio `README.md` que la mapea por propósito. No va al repositorio |
| Rastro de investigación | las carpetas `_exploracion/` de `outputs/` y de `outputs/matricula/`, cada una con su `README.md` |
| Insumos crudos | bucket, se traen con `python -m insumos bajar`; estado con `python -m insumos estado` |

Flujo de uso: en el reporte de grillas se filtran las mejores y se descarga
`grillas_para_predios.geojson`; luego `python -m predios.lotes --celdas <archivo>` y
`python -m reporte_predios --grillas <archivo>`.

---

## Verificación rápida (debe pasar todo)

```bash
.venv/Scripts/python.exe -m compileall -q predios reporte reporte_predios insumos soporte
.venv/Scripts/python.exe -m predios.certificados --prueba          # 7 de 7
.venv/Scripts/python.exe -m reporte_predios --sin-satelital        # construye con lo que haya
.venv/Scripts/python.exe soporte/herramientas/probar_reporte_predios.py   # TODO OK
.venv/Scripts/python.exe -m insumos estado                          # local = bucket
```

---

## Cómo funciona hoy el paso 2 (predio → lote)

1. `predios_igac`: baja del IGAC todos los predios de cada grilla (terreno + REGISTRO_1 +
   REGISTRO_2) a `predios.gpkg`.
2. `lotes.py`: mide forma, terreno (Copernicus DEM, WorldCover), vías, conexión; calcula
   área del lote y fracciones de cobertura; ancho del mayor círculo inscrito.
   - Bloque 1 excluye: grilla excluida, suelo urbano, uso habitacional. (Ley 2ª ya NO
     excluye: `LEY2_EXCLUYE = False`.)
   - Bloque 2 ya NO descarta por tamaño. Anota `cabe_utility` / `cabe_distribuida` /
     `cabe_perfil`. Los predios con menos de `HA_MINIMA_CARACTERIZAR` (2 ha brutas,
     `--ha-minima`) quedan como clase "Pequeño" en el CSV de descartes con su medida.
   - Bloque 3 puntúa (índice 0-100 con los 7 criterios del reporte de grillas).
   - Luego `añadir_gestion`, `juridico.cribar` (UAF, restitución), `valor.valorar` (IGAC
     zonas geoeconómicas 2026 + banda ANT), y para todo seleccionable `entorno.enriquecer`
     (12 geoservicios) y `pot.enriquecer` (LADM-COL POT del IGAC).
   - Bloque 4 `recribar`: título minero vigente (cruce con el polígono real, ANM) →
     Excluido; POT protección dominante → Con reparos.
   - Exporta `lotes_<perfil>.csv/.geojson` (geometría simplificada a 1 m) y
     `lotes_<perfil>_descartados.csv`.
3. `reporte_predios`: visor con desplegable de grillas, mapa con fondo satelital, **panel
   de filtros manuales** (preajustes ≥150 ha/387 m utility, ≥2 ha/45 m distribuida,
   cualquier tamaño; rangos de área del lote, ancho, cobertura apta, índice, valor; casillas de clase, sin
   estorbos, dentro de UAF, POT no protección, sin título minero), lista, detalle y ficha
   PDF. Imágenes: se descargan las 25 mayores por grilla y perfil (`--imagenes N`); el
   resto se carga del servicio Esri al abrir la ficha (`satDe()` en la plantilla).

---

## Lo hecho en la sesión del 18-19 de agosto (resumen)

- REGISTRO_2 integrado (zonas económicas, construcciones, nombre del predio).
- `predios/valor.py`, `predios/entorno.py`, `predios/pot.py` nuevos e integrados.
- `insumos/barras.py` ingiere la Circular UPME 054 de 2026 (solo tablas con "Variable
  limitante"; 645 barras) y prevalece barra a barra también en `extraer_todas`, que es la
  tabla que lee el criterio de capacidad de los reportes (antes solo entraba en la
  concurrencia). Reporte de grillas regenerado con la 054: de 10 Prioritarias quedan 1
  (Montería, Planeta Rica 219 MW); Sabanalarga 110 = 0,00 MW, Caucasia y Cerromatoso 0,08;
  29 grillas cambian de clase. Verificado contra las páginas del PDF (274, 285, 798, 893,
  952). Las 10 grillas de trabajo se mantienen como piloto (decisión de Samuel) y su
  archivo `grillas_para_predios.geojson` se regeneró con el ranking nuevo (mismos códigos).
- Circular 042 de 2026 (obras urgentes por cortocircuito) descargada a `data/barras/upme/`
  con su proyecto de resolución, memoria y matriz. La versión definitiva es la
  **Resolución UPME 567 del 6 de agosto de 2026** (con la Circular 082 de respuesta a
  comentarios; ambas en `data/barras/upme/`): Cerromatoso 110 kV renovación 2034 (y
  mitigación 2030), Cerromatoso 220 kV 2035, Chinú 110 kV 2034, Termoflores 110 kV 2027,
  Oasis y Las Flores 110 kV 2029, Sabanalarga 220 kV 2026. Es la fuente para saber cuándo
  se recupera cupo; no se ingiere como dato.
- Ley 2ª deja de excluir; segunda criba por minería y POT.
- Filtro manual de tamaño (visor) y clase "Pequeño" (lotes.py).
- Consultas por polígono (minería, POT) van por POST con geometría simplificada a 5 m
  (había predios de 640.000 vértices que no cabían en la URL); las capas que fallan quedan
  anotadas como error en la caché y se reintentan solas en la siguiente corrida.
- Auditorías: precio del certificado $23.000; municipio por DANE del código; CSV del
  reporte 1 con `;`; encuadre del mapa; default peligroso `predios_igac --clase`.

---

## Estado al cierre de la sesión (2026-08-19, 02:45)

**Piloto: 10 grillas** (`outputs/reporte/grillas_para_predios.geojson`, las primeras del
ranking anterior; Samuel decidió mantenerlas aunque con la Circular 054 bajaron a
Condicionadas). Corrida definitiva de `predios.lotes` hecha: 2.700 lotes del catastro,
749 caracterizados (≥ 2 ha, no excluidos; catastro corte 30-jun-2026: 2.745 lotes), 647
en `lotes_<perfil>.csv` (102 salen por título minero vigente de la ANM), 1.325 Pequeños,
773 Excluidos por urbano/habitacional. Utility: los 647 Con reparos por capacidad de barra
(Circular 054, 0,02 a 28 MW < 50 MW del criterio); distribuida: 552 Idóneos, 95 Con
reparos. Visor construido y verificado (`probar_reporte_predios.py`: TODO OK, 58
controles; 5,4 MB; 243 imágenes descargadas, el resto bajo demanda). En La Apartada 28 de
34 lotes se inundaron en algún episodio de La Niña.
Todas las cachés llenas y en el bucket (entorno con 16 capas, POT, contexto GSA,
poblados, valor, jurídico, satelital, barras con 054 y 042; `python -m insumos subir`
corrido dos veces, la última al cierre).

Para reproducir desde cero en otra máquina (después de `python -m insumos bajar`):

```bash
.venv/Scripts/python.exe -m predios.lotes --celdas outputs/reporte/grillas_para_predios.geojson   # ~10 min con caché
.venv/Scripts/python.exe -m reporte_predios                                                     # imágenes cacheadas, ~3 min
.venv/Scripts/python.exe soporte/herramientas/probar_reporte_predios.py                          # TODO OK
.venv/Scripts/python.exe -m insumos subir                                                       # sube lo nuevo
```

y actualiza las cifras de `docs/PREDIOS.md` (sección "Cómo reproducir la verificación") con
lo que impriman esos comandos. El cuaderno `2. IGAC_Consulta_Predios.ipynb` tiene el texto
al día pero no se ha re-ejecutado; ejecutarlo de punta a punta con `CELDAS` apuntando al
GeoJSON de las 10 y guardar las salidas.

**Hallazgo del piloto para el decisor:** con la capacidad oficial de la Circular UPME 054
de 2026, el cuello de botella es la red, no la tierra: Sabanalarga 110 = 0,00 MW,
Caucasia y Cerromatoso 0,08, Toluviejo 0,02, San Marcos 19,4; solo Planeta Rica (219 MW)
y Calamar (48 MW) tienen holgura en las cien grillas. La Circular 042 de 2026 (obras
urgentes por cortocircuito) es la que dirá cuándo se recupera cupo (Cerromatoso 230 kV y
Chinú 110 hacia 2030, Termoflores/Oasis/Las Flores 110 hacia 2027).

---

## Sesión del 19 de agosto, 03:30 a 05:30 (tras revisar Samuel el visor)

Pedidos de Samuel y estado:
- **Cuadro de fuentes al final del reporte**: HECHO (`FUENTES` en `reporte_predios/datos.py`,
  sección al pie del visor y lista en la ficha; 24 fuentes con versión o corte).
- **Que se vea de dónde sale el índice**: HECHO. Detalle y ficha traen la tabla de los
  siete criterios (valor del lote, límite/bueno/tope del perfil, nota, peso, reparo) y el
  índice se reconstruye en JS con la misma fórmula (coincide al entero). El JSON lleva
  `criterios`, `umbrales` por perfil, `pesos`, `indice_prioritaria`.
- **Vigencia de fuentes** (workflow de 4 agentes, verificado en vivo): catastro IGAC pasó
  al corte 30-jun-2026 (`CORTE = "06_2026"`, servicio mensual; campo de unión ahora
  NUMERO_PREDIAL); RUNAP ahora por WFS vivo de Parques Nacionales; resguardos y consejos
  de la ANT (25-jun-2026); páramos de Ecosistema_Estrategico/1; clase agrológica
  multiescalar 2024 (con estudio y año); Circular 042 → **Resolución UPME 567 del 6-ago-2026**
  (definitiva; PDF y Circular 082 en `data/barras/upme/`): FPO Cerromatoso 110 y Chinú 110
  en 2034, Termoflores 110 en 2027, Oasis/Las Flores 110 en 2029, Sabanalarga 220 en 2026.
  Siguen vigentes: WorldCover 2021 v200 (último), Copernicus DEM, GSA 1.7, Circular 054,
  CREG 101 071/094 (con modificación 101 106 de 2026), SNR $23.000, ZHG 2026, POT LADM,
  UAF, URT, IDEAM, humedales, Ley 2ª, POMCA, UPRA 2024, ANM, ANH, SGC. **Pendiente de
  decisión**: recalibrar el índice con la capa viva de XM (351 plantas solares al
  18-ago-2026 frente a 232 de enero); cambia umbrales y pesos, Samuel decide.
- **Temperatura como criterio**: NO se añadió. Está dentro del PVOUT (pérdidas térmicas
  ya descontadas); añadirla contaría dos veces. Se muestra TEMP y el rendimiento PR =
  PVOUT/GTI con su explicación. Si Samuel insiste, calibrar con percentiles de XM.
- **El Niño / La Niña**: HECHO con el IDEAM (workflow, 21 datasets probados): por lote,
  manchas observadas de seis episodios de La Niña (1988, 2000, 2011, 2012, 2016,
  2020-2022) con hectáreas de solape, zonas inundables periódicamente 2022, alteración de
  la lluvia en Niño y Niña típicos, retorno de la sequía, incendios en 5 km. Filtro "sin
  inundación Niña" en el visor. Ejemplo: lote A de La Apartada se inundó en 2000 y 2011
  (133 ha de 206 en un evento).
- **Grilla de Sabanalarga "rara"**: el catastro público cubre 25% porque Sabanalarga
  tiene gestor catastral propio desde 2021 (Res. IGAC 1224/2021); los 71 lotes son de
  Candelaria y Manatí. El visor ahora lo dice con el nombre del gestor.
- Bug corregido: `valor.py` no parseaba VALOR_HECTAREA con formato '$9.000.000'
  (Atlántico quedaba sin valor).
- Cachés: VERSION_CAPA en entorno.py re-consulta solo las capas cuya definición cambió.

## En curso al cierre (2026-08-19, 06:30), aprobado por Samuel

1. **Umbrales del índice a escala de lote** (`soporte/calibracion/umbrales_lote.py`,
   `python -m soporte.calibracion umbrales_lote`). Motivo: los umbrales de CRITERIOS se
   calibraron con celdas de 5 km (promedios) y un lote medido en su polígono sale mejor que
   su celda, así que el índice de lote quedaba inflado. Método: 335 plantas solares del
   registro de XM (18-ago-2026, OPERACIÓN y PRUEBAS, ≥0,5 MW) → lote catastral bajo el
   punto (IGAC 06_2026; 220 rurales, 4 urbanos, 111 sin catastro público por gestor propio)
   → para las ≥5 MW sin catastro, huella aproximada (círculo de MW × ha/MWp) marcada
   "aprox" → se miden las siete variables con predios/ (terreno, conexión por perfil, vías,
   GSA) → percentiles 10/50/90 por perfil (utility ≥10 MW, distribuida 0,5-5 MW), lotes
   únicos. Salidas: `outputs/reporte/umbrales_lote.json`, `calibracion_lotes_xm.csv`,
   caché `data/calibracion/lotes_xm_06_2026.geojson`. **Falta**: pegar los números en
   `PERFILES[perfil]["umbrales_lote"]` (reporte/datos.py; `rg.umbrales_de(nombre,
   "lote")` y `aplicar_perfil(..., escala="lote")` ya están, `lotes.evaluar` ya pide la
   escala lote y el visor ya lee `D.umbrales`), rerun `predios.lotes` (también para la
   columna nueva `numero_predial_anterior`) y `reporte_predios`, y documentar en
   PREDIOS.md (sección del índice) con n de referencia y cuántas huellas aproximadas.
2. **Sentinel-2 reciente por lote** (`insumos/sentinel.py`, integrado en
   `reporte_predios.datos.sentinel_lote` y en detalle y ficha como "Estado reciente"):
   Earth Search STAC, última escena con <10% nube y cobertura completa sobre el recuadro
   del lote (SCL), recorte TCI 10 m a JPEG 700 px, caché `data/satelital/sat_s2_lote_*`,
   bucket. Probado en La Apartada y Santiago de Tolú (escena 2026-08-10, 0% nubes). Se
   genera para los mismos lotes que tienen imagen Esri descargada (25 por grilla y perfil).
3. Número predial anterior (20 dígitos) por lote y guía de consulta inmediata en la SNR
   (código hecho; aparece al rerun de `predios.lotes`).

## Hoja de ruta aprobada por Samuel (2026-08-19, 02:40)

Los seis puntos, en el orden en que se harán. Cada uno sigue el mismo patrón: módulo en
`predios/`, caché por lote en `data/<conjunto>/`, conjunto en `insumos.CONJUNTOS`,
columnas en `lotes.COLUMNAS` y `reporte_predios.CAMPOS_LOTE`, sección en el visor y en la
ficha, párrafo en `docs/PREDIOS.md`, comprobación en `probar_reporte_predios.py`.

1. **Valorización nivel 2, automatizada** (`predios/mercado.py`). Ofertas de portales
   (Fincaraíz, Metrocuadrado, Properati, OLX, Mercado Libre) por municipio, guardadas
   crudas en el bucket, consultadas despacio y con caché; por lote: COP/ha comparable
   (mediana, p25-p75, n, distancia media de los comparables, fecha). Estimador de precio del
   lote = valor catastral × factor de actualización municipal (mediana oferta/catastro),
   ajustado por distancia a vía y a poblado, cobertura, pendiente, agua, tamaño y zona
   económica; siempre como rango con confianza. Añadir el precio de las compraventas
   históricas del propio lote cuando llegue el certificado (el lector ya las extrae) y
   ofertas de arriendo para energía como comparación compra vs arriendo. Piso: catastral;
   mediana: ANT; techo: ofertas.
2. **Recurso solar completo** (HECHO en esta sesión): las 8 capas del GSA por lote (PVOUT,
   GHI, DNI, DIF, GTI, OPTA, TEMP, ELE) con definición completa en la ficha. Pendiente
   opcional: serie horaria/TMY (PVGIS o Solargis) para simular producción.
3. **Variables geoespaciales adicionales al lote**, a elegir con Samuel: ronda hídrica de
   30 m descontada del lote (IDEAM), tipo de vía de acceso (OSM), periodicidad de
   inundación (IDEAM), aeropuertos y radares (Aerocivil, deslumbramiento), población en
   2 km (WorldPop), proyectos de generación XM en 20 km (ya en `data/geoinfo`), red de media
   tensión cuando el OR la publique. Quedan sin servicio abierto: privación relativa
   (SEDAC) y coca (rásteres del panel de Daniel; se pueden muestrear si Daniel entrega el
   ráster).
4. **Contacto del propietario**: del certificado (nombre e identificación) y, si es
   persona jurídica, RUES (NIT, dirección, teléfono, representante legal): módulo
   `predios/contacto.py` que lea el certificado ya procesado y consulte RUES. Para
   personas naturales, preparar la petición de la ficha predial a la alcaldía (nombre y
   dirección de notificación) y anotar UMATA/JAC como vía de campo. No hay base abierta de
   propietarios (habeas data).
5. **Código predial y matrícula**: no son uno a uno (englobes sin registrar, segregaciones
   sin desenglobe, posesión sin folio). `data/registro/matriculas.csv` admite varias filas
   por código y el visor las junta y avisa (HECHO); la petición a la SNR va por número
   predial y hay que comprar el certificado de cada matrícula que devuelva. Pendiente:
   plantilla de promesa/opción de compraventa (condición suspensiva de conexión y licencia,
   arras, servidumbre de línea) para revisión de abogado; y guía del trámite de conexión
   (≥10 MW UPME, <10 MW OR, CREG 075/2021 y modificaciones) más la cola de proyectos por
   barra (geo.upme.gov.co capacidad_asignada) en la ficha.
6. **Aproximación al precio del lote**: además del punto 1, pedir el avalúo catastral
   oficial a la alcaldía (hoy se calcula su referencia por zonas), tarifa y recaudo predial,
   valor por hectárea de las últimas transacciones registradas (certificado), y ofertas de
   arriendo para energía; todo en la ficha como rango: catastral (piso), ANT (mediana
   municipal), comparables de oferta (techo), histórico del propio lote.

Decisiones que siguen pendientes de Samuel: si el POT de protección debe excluir del todo
(hoy baja a Con reparos); si la ronda hídrica se descuenta o solo se muestra; logo real de
Métodos Mixtos (hoy isotipo redibujado); si se corre la caracterización de las 87 grillas
evaluadas o solo de las seleccionadas (flujo normal).

Pendiente de permiso de Samuel: commit y push a `caracterizacion-grillas` (incluye
`git rm --cached` de las 100 imágenes de `entregables/satelital/` que quedaron rastreadas
en una sesión anterior).

---

## Reordenación del repositorio (2026-08-25)

Se separó el código vivo del rastro de la investigación. No se borró nada: todo lo
exploratorio está movido y documentado.

- `functions.py` pasó de la raíz a **`modelo/functions.py`**, con `modelo/__init__.py`.
  Los cuadernos 1, 1.1 y 1.2 ahora hacen `from modelo import functions`. De paso se
  corrigió `soporte/herramientas/check_setup.py`, que calculaba la raíz del proyecto un
  nivel corto y por eso siempre daba `ModuleNotFoundError: No module named 'functions'`;
  ahora comprueba `modelo.functions` y pasa.
- **`outputs/matricula/`** deja a la vista solo `cosechar_municipal.py` y `COBERTURA.md`.
  Las 298 sondas de la investigación de la matrícula están en
  `outputs/matricula/_exploracion/`, repartidas en seis tandas (`snr_portal`, `municipal`,
  `catastro_cc`, `normativa_tarifas`, `datos_abiertos`, `otros`) y explicadas en su
  `README.md`. `cosechar_municipal.py` no se movió porque `predios/matricula_auto.py` lo
  carga por ruta.
- **`outputs/`** queda ordenada por propósito y con un `README.md` que la mapea:
  documentos del trabajo, datos generados, código vivo, análisis con su salida, y rastro.
  Los scripts sueltos de la raíz de `outputs/` están en `outputs/_exploracion/`
  (`geoservicios`, `edicion_codigo`, `capturas_y_enlaces`, `verif3`, `parches`,
  `salidas_sueltas`).
- La comprobación de la ficha de Melgar está en **`outputs/evidencia/ficha_el_poblado/`**
  con su script, su HTML, su texto y su captura.

Comprobado después de mover: `compileall` de `predios reporte reporte_predios soporte
insumos`, `soporte/herramientas/probar_reporte_predios.py` (TODO OK) y
`soporte/herramientas/check_setup.py`.
