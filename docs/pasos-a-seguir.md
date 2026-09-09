# Pasos a seguir

Plan del proyecto con el estado de cada punto a 2026-08-19. El detalle técnico y cómo
continuar están en `docs/CONTINUIDAD.md`; el método, en `docs/REPORTE.md` (grillas) y
`docs/PREDIOS.md` (lotes).

## Caracterización de las grillas — hecho

- Reporte por grilla (`entregables/reporte_grillas.html`): distancia a vía, radiación,
  jurisdicciones especiales, conflicto, Ley 2ª, siete criterios en escala absoluta, dos
  perfiles (utility y distribuida), zonas de prospección, descarga de la selección.
- Identificación del operador de red y de la subestación de conexión: hecho.
- Confirmación de capacidades (barras) de las subestaciones: hecho con los 14 informes del
  ciclo 2023-2024 y, desde hoy, con la **Circular UPME 054 de 2026** (capacidad por barra
  2026-2039), que prevalece. Efecto: solo una grilla queda Prioritaria (Montería, Planeta
  Rica); la Costa cordobesa y Atlántico quedan sin cupo. La Circular 042 de 2026 (obras
  urgentes) dice cuándo se recupera; está descargada para revisión.
  Referencia original: https://docs.google.com/document/d/1dt4tdpNRjbSNA2TukIvCmdMkjba627wGFN97pVQ-THs?usp=drive_fs

## Ubicación de lotes — hecho

- Notebook 2 refinado y automatizable: recibe cualquier archivo de grillas, baja el catastro
  del IGAC, mide cada lote en su polígono completo.
- Criterios de discriminación: excluyentes (urbano, habitacional, grilla excluida), tamaño
  y forma como datos (el tamaño lo filtra el usuario en el visor), puntuación con los siete
  criterios, segunda criba (título minero, figuras territoriales, POT de protección).
- Selección de lotes: visor `entregables/reporte_predios.html` con filtro manual por área,
  ancho, cobertura, índice, valor, POT, minería, UAF; ficha PDF por lote.

## Caracterizar y seleccionar los lotes — hecho

- Clasificación urbano rural: catastro (capa) y POT (clasificación del suelo).
- Norma urbana: geoservicios LADM-COL POT del IGAC (categoría, reparto de área, uso
  principal, acto, POT municipal), semáforo por lote.
- Radiación: ocho capas del Global Solar Atlas por lote con definición.
- Valor por medios remotos: nivel 1 hecho (valor catastral de referencia por zonas
  geoeconómicas IGAC 2026 + banda ANT + confianza).
  Referencia original: https://docs.google.com/document/d/122csAu3SyVDDniDLzf9FSNlkPHs7vQFA?rtpof=true&usp=drive_fs
- Además, por lote: entorno (16 capas: hidrografía, inundación, humedales, Ley 2ª, POMCA,
  frontera agrícola, clase agrológica, minería, hidrocarburos, movimientos en masa,
  sísmica, RUNAP, resguardos, consejos comunitarios, páramos), UAF y restitución, línea de
  transmisión y centro poblado más cercanos, catastro ampliado (zonas, construcciones).

## Caracterización de lotes individuales — en curso (hoja de ruta aprobada, ver CONTINUIDAD)

- Valorización detallada: nivel 1 hecho; **nivel 2 (comparables de mercado y estimador
  de precio) es el siguiente módulo**.
- Tradición y libertad: hecho hasta el límite legal (petición de matrículas por lista,
  CSV de matrículas conocidas, botón a la SNR, lector automático del certificado con
  semáforo). La matrícula y la compra del certificado no son automatizables.
- Confirmación de radiación a detalle: hecho (GSA por lote); serie horaria opcional.
- Contacto al propietario: por construir (certificado + RUES; petición de ficha predial).
- Promesa de compraventa: documentada en `docs/ADQUISICION.md`; falta plantilla.
- Gestión de punto de conexión: subestación, distancia, tensión, capacidad 054 y línea
  más cercana por lote; falta cola de proyectos por barra y guía del trámite.

## Plan de inversión y estructuración del proyecto — no iniciado

- Modelo financiero
- Financiador
- Selección de equipos
