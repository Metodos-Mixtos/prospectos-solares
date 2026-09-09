# Del lote a la escritura: la ruta de adquisición

El bloque de predios responde qué lote puede alojar el proyecto. Este documento responde
la pregunta siguiente, que es la que decide si el proyecto se construye: **cuáles de esos
lotes se pueden comprar, cómo, a qué costo y con qué riesgos**.

Todo lo citado aquí fue verificado contra fuentes oficiales en agosto de 2026. Cada
tabla lleva su fuente y su año; donde no hay dato publicado, se dice.

---

## El hallazgo que ordena todo lo demás: la UAF

La Unidad Agrícola Familiar es el tope legal de acumulación sobre predios que alguna vez
fueron baldíos adjudicados. El artículo 72 de la Ley 160 de 1994 (exequible según la
C-536 de 1997, extendida por la jurisprudencia a adjudicaciones anteriores a 1994)
prohíbe adquirirlos por encima de una UAF municipal. La compra que viola el tope es
**nula**, y la restricción no caduca.

Lo que cambió, y casi nadie tiene en el radar: la ANT viene reemplazando los rangos de
la Resolución 041 de 1996 con acuerdos municipales por Unidades Físicas Homogéneas
(régimen del Acuerdo 167 de 2021), y los rangos nuevos son **mucho más bajos**. En el
San Jorge cordobés se pasó de 36-49 ha a máximos de 19-25 ha. De los 28 municipios donde
caen nuestros lotes, 16 ya tienen acuerdo nuevo (2023-2026) y 12 siguen bajo la 041
(régimen de transición de la Resolución ANT 202510303779576 de diciembre de 2025).

El cruce contra los 152 lotes utility da un resultado sin ambigüedad:

> **Los 152 lotes superan la UAF máxima de su municipio**, entre 4 y 165 veces.

Eso NO significa que ninguno se pueda comprar. Significa que para cada lote la pregunta
decisiva es el **origen de su tradición**, y eso lo dice el certificado:

- **Origen privado** (tradición que no arranca en adjudicación de baldío, o folio con
  anotación 0967/0970 de propiedad privada anterior): la UAF no aplica y la compra
  procede con la due diligence normal.
- **Origen en baldío adjudicado** (resolución del INCORA, INCODER o ANT en las primeras
  anotaciones): la compra por encima de la UAF es nula. No hay saneamiento; hay
  **estructuración**: arrendamiento de largo plazo, usufructo o servidumbre no
  transfieren dominio y son las vías que usa el sector, validadas caso a caso con
  concepto jurídico.

Dos consecuencias de diseño para el negocio:

1. **El certificado de tradición dejó de ser un trámite y pasó a ser LA decisión.** Por
   eso el semáforo automático (abajo) pone el origen baldío en rojo.
2. **El perfil distribuida tiene una ventaja estructural**: sus lotes de 2-4 ha caben
   dentro de cualquier UAF de la zona, así que el riesgo de acumulación casi desaparece
   a esa escala.

El cribado corre solo, con la capa oficial de la ANT como fuente viva y respaldo
documental si no hay red:

```bash
python -m predios.juridico --perfil utility
```

---

## Restitución de tierras: dónde mirar con lupa

La Ley 1448 de 2011 rige hasta 2031 (prórroga de la Ley 2078 de 2021). Las solicitudes
de restitución por municipio del predio, consultadas en la API de la URT con corte
julio de 2026, muestran dónde se concentra el riesgo:

| Municipio | Solicitudes | Microzona URT vigente |
|---|---|---|
| Sabana de Torres (Santander) | 681 | sí |
| San Alberto (Cesar) | 562 | sí |
| San José de Uré (Córdoba) | 459 | sí |
| Montelíbano (Córdoba) | 431 | sí |
| Pueblo Nuevo (Córdoba) | 430 | sí |
| Puerto Libertador (Córdoba) | 308 | sí |
| Santiago de Tolú (Sucre) | 249 | no |
| Caimito (Sucre) | 6 | sí |
| Momil (Córdoba) | 5 | no |

112 de los 152 lotes están en municipios con microzona focalizada vigente. El dato
municipal no condena al predio; obliga a dos cosas cuando el folio muestre cualquier
anotación de la URT: documentar la cancelación si la hay, y pedir a la URT certificación
de no inclusión en el registro de tierras despojadas antes de ofertar.

---

## El semáforo de certificados

`python -m predios.certificados folio1.pdf folio2.pdf ...` lee los PDF, reconstruye las
anotaciones, resuelve cuáles están canceladas encadenando los «Se cancela anotación
No:» y clasifica once riesgos en tres colores. Patrones construidos sobre la Resolución
SNR 7448 de 2021 y verificados contra dos certificados reales; autoverificación con
`--prueba`.

**Rojo, descarta la compra directa:**

| Riesgo | Por qué | ¿Se sanea? |
|---|---|---|
| Falsa tradición (grupo 06, marca I) | el vendedor no es dueño pleno | solo por pertenencia, años, la Ley 1561 de 2012 no aplica a predios grandes |
| Origen en baldío adjudicado | nulidad por art. 72 Ley 160/1994 | no se sanea; se estructura sin compra |
| No salió del dominio de la Nación | no hay propiedad que comprar | no |
| Medida de restitución vigente | fuera del comercio o riesgo extremo | solo la URT o el juez la levantan |
| Extinción de dominio, bienes SAE | fuera del mercado privado | solo compra al Estado |
| Proceso agrario de la ANT en curso | el predio puede volver a la Nación | esperar acto en firme |

**Ámbar, se gestiona antes del cierre:** embargo (pago y levantamiento), hipoteca (paz y
salvo; con acreedores liquidados como la Caja Agraria tarda más vía CISA), patrimonio de
familia y afectación a vivienda familiar (levantamiento por escritura, licencia judicial
si hay menores), usufructo (deben firmar nudo propietario y usufructuario).

**Nota:** servidumbres. Las de oleoducto, gasoducto o minera restan área instalable; la
de energía puede ser sinergia para la evacuación; la de tránsito activa puede ser el
único acceso legal.

---

## La ruta completa, con tiempos y costos

| Etapa | Tiempo | Costo |
|---|---|---|
| 1. Petición de matrículas a la SNR (`python -m predios.registro`) | 10 días hábiles, silencio positivo | gratis |
| 2. Certificados de tradición de la lista corta | inmediato, en línea | $23.000 c/u (Res. SNR 2026-001726); 39 sin estorbos $897.000 |
| 3. Semáforo automático (`predios.certificados`) | minutos | ya está hecho |
| 4. Estudio de títulos de 20 años, solo folios verdes y ámbar | 1 a 3 semanas por predio | $400.000 a $1.500.000 por predio |
| 5. Saneamientos ámbar (hipotecas, sucesiones, levantamientos) | de semanas a más de un año | del vendedor, como condición precedente |
| 6. Promesa u opción | días de negociación | prima módica en la opción |
| 7. Escritura y registro | 5 días hábiles el registro (10 si son 10+ matrículas) | ver tabla siguiente |

Costos de cierre sobre el valor del acto, régimen 2026:

| Concepto | Tarifa |
|---|---|
| Derechos notariales | 0,3% más IVA |
| Impuesto de registro departamental | 0,5% a 1% según asamblea |
| Derechos registrales ORIP | 8,67 a 12,68 por mil, progresivo |
| Impuesto de timbre | 0% hasta 20.000 UVT ($1.047 millones); 1,5% de 20.000 a 50.000; 3% arriba |
| Retención en la fuente | 1% si el vendedor es persona natural, retiene el notario |
| Corredor rural, referencia de mercado | del orden del 5% más IVA, no regulada |

El timbre importa aquí: con UVT 2026 en $52.374, un predio de 150+ ha en esta zona puede
superar el umbral de los $1.047 millones y el impuesto salta a 1,5% o 3%. Es un argumento
más para los esquemas sin transferencia de dominio.

---

## Comprar no es la única vía, y a veces no es la mejor

| Instrumento | Cuándo | La letra menuda |
|---|---|---|
| Opción (Ley 51 de 1918) | greenfield, amarra exclusividad 1-3 años con prima módica | exige término o condición; redactar el plazo con cuidado porque la condición se tiene por fallida al año salvo pacto expreso |
| Promesa de compraventa | puente durante títulos y saneamiento | es derecho personal, no se inscribe; proteger con cláusula penal fuerte |
| Compraventa | título limpio y banco que exige hipoteca de primer grado | todos los costos de cierre, incluido el timbre |
| Arriendo 30+ años | el dueño no vende, o hay origen baldío | derecho personal; los bancos piden mitigantes (escritura inscrita, acuerdos directos) |
| Usufructo | como el arriendo pero oponible a terceros | máximo 30 años para persona jurídica (art. 829 C.C.), justo frente a la vida útil |
| Fiducia mercantil | vehículo de cierre para project finance | no sanea vicios del título subyacente; hay fallos de restitución contra fiducias |
| Servidumbre (Ley 56 de 1981) | línea de evacuación y accesos, no la planta | negociada en semanas; judicial en meses |

**El derecho de superficie no existe en Colombia** como derecho real general a 2026. Su
papel lo cumplen usufructo y arriendo; los term sheets copiados de España fallan por esto.

La práctica del sector: los desarrolladores colombianos operan mayoritariamente con
**arriendo de muy largo plazo** (contratos del orden de 32 años, la vida útil del
proyecto). No hay canon solar publicado para Colombia; el piso de negociación
documentado es el canon agropecuario, del orden de $2 millones por hectárea año, y la
referencia internacional (España) equivale a $4,7 a $9,4 millones. El canon real se
negocia predio a predio.

---

## Precio de la tierra: contexto para negociar

Medianas municipales de los estudios del Observatorio de Tierras Rurales de la ANT
(modelo sobre avalúos y transacciones SNR 2015-2023 ajustadas), y rangos UPRA donde no
hay estudio ANT. Millones de COP por hectárea:

| Zona | Rango | Año y fuente |
|---|---|---|
| San Jorge cordobés | 4,0 a 16,9 (medianas municipales; Ayapel 4,0, Montelíbano 6,2, Puerto Libertador 6,8) | ANT 2025 |
| Sabanas de Sucre (San Marcos, Caimito, La Unión, El Roble) | 7,6 a 11,5 | ANT 2025 |
| Golfo de Morrosquillo (Tolú, Tolú Viejo, Palmito) | 25 a 60 | ANT 2025 |
| Magdalena Medio cesarense (San Alberto) | 20 a 40 | UPRA 2018 |
| Magdalena Medio santandereano (Sabana de Torres) | 8 a 22 | estimación, sin estadística oficial |
| Huila (Palermo, Tello) | 1 a 15, dominante 3-5 | UPRA 2018 |
| Piedemonte del Meta (Cumaral) | 30 a 60, dominante 40-50 | UPRA 2017 |
| Bolívar (Calamar, Mahates) | 3 a 20 | UPRA 2017 |

La lectura de negocio: a 6 millones por hectárea, las 150 ha del proyecto tipo en el San
Jorge cuestan unos 900 millones, alrededor del 1% del CAPEX de una planta de 50 MW. El
suelo no es el costo del proyecto; es el riesgo jurídico del proyecto.

En los portales inmobiliarios no se puede verificar si un predio específico está en
venta (los avisos rurales no traen código catastral). Las señales de disposición a
vender salen del propio folio: sucesión ilíquida, hipoteca con acreedor presionando,
predio recién heredado por varios titulares.

---

## Qué es automático y qué no

| Paso | Automático |
|---|---|
| Cribado UAF y restitución de todos los lotes | sí, `predios.juridico`, fuentes vivas con caché |
| Petición de matrículas y anexo | sí, `predios.registro` |
| Radicar la petición | no, firma y envío |
| Comprar certificados | no, pago en el portal SNR |
| Semáforo de los certificados | sí, `predios.certificados` |
| Estudio de títulos y concepto | no, abogado; el semáforo le reduce el volumen |
| Negociación y cierre | no |

---

## Fuentes principales

- Ley 160 de 1994, art. 72; Corte Constitucional C-536 de 1997; extensión
  jurisprudencial a adjudicaciones pre-1994 (CSJ).
- Acuerdos UAF por UFH del Consejo Directivo de la ANT 304 y 307 de 2023, 416 y 437 de
  2024, 506, 521, 545 y 546 de 2025, 574 de 2026; Resolución 041 de 1996 del INCORA;
  Resolución ANT 202510303779576 de 2025 (transición). Capa oficial ANT «Unidad
  Agrícola Familiar».
- Ley 1448 de 2011 y Ley 2078 de 2021; datasets URT 33hn-pgph y s87b-tjcc
  (datos.gov.co) y FeatureServer de microzonas de la URT.
- Ley 1579 de 2012; Resolución SNR 7448 de 2021 (códigos de naturaleza jurídica);
  certificados reales 060-10155 y 060-1174.
- Ley 1561 de 2012 (vigente, limitada a 1 UAF); Ley 51 de 1918; Ley 56 de 1981;
  art. 829 C.C.; Acto Legislativo 03 de 2023 (jurisdicción agraria, aún sin jueces).
- Observatorio de Tierras Rurales de la ANT, estudios de Córdoba y Sucre (2025) y
  Bolívar (2026); UPRA, precios comerciales de la tierra (2017-2022).
