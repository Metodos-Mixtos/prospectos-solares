# Qué Puedo Saber del Código Catastral y Dónde Obtenerlo

Con el código `734490001000000010054000000000`, puedes acceder a **mucha información**. Aquí está la guía completa:

---

## **1. INFORMACIÓN DISPONIBLE POR CÓDIGO CATASTRAL**

| Información | Fuente | Formato |
|---|---|---|
| **Geometría (polygon)** | IGAC | Shapefile, GeoJSON, KML |
| **Área en hectáreas** | IGAC | Número (m², ha) |
| **Clasificación de uso** | IGAC + Municipio | Texto (rural, urbano, etc.) |
| **Valor fiscal** | IGAC / DIAN | Número (COP) |
| **Propietario** | SNR | Nombres, identificación |
| **Historial de transacciones** | SNR (Matricula Registral) | Escrituras, cambios de dueño |
| **Obligaciones tributarias** | DIAN | Impuesto predial, cartera |
| **Zoning municipal** | Municipio / PBOT | Clasificación de suelo |
| **Servicios disponibles** | Empresa de servicios | Agua, luz, alcantarillado |
| **Restricciones ambientales** | CORTOLIMA / CAR | Zonas protegidas, páramos |

---

## **2. FUENTES OFICIALES PARA DESCARGAR DATOS**

### **A. IGAC (Instituto Geográfico Agustín Codazzi)**

**Geoportal Web:**

- URL: <https://www.igac.gov.co/>
- Busca: "Consulta catastral" o "Descarga de datos"
- Ingresa: `734490001000000010054000000000`
- Descarga: Shapefile, GeoJSON

**Datos Específicos que Obtiene:**

- Polígono del predio
- Área total (m²)
- Coordenadas UTM
- Clasificación IGAC

---

### **B. SNR (Superintendencia de Notariado y Registro)**

**Para la Matrícula Registral (lo más importante):**

**Web SNR:**

- URL: <https://www.supernotariado.gov.co/>
- Sistema: "Consulta de Matrículas"
- Requiere: Número de matrícula O código catastral

**Con la Matrícula Registral (366-35594 en tu caso) obtienes:**

- ✓ Propietario registrado
- ✓ Historial completo de transacciones
- ✓ Escrituras digitales
- ✓ Embargos o gravámenes
- ✓ Cambios de propietario desde 1971

**Acceso:**

```
https://www.supernotariado.gov.co/web/guest/consulte-la-matricula
```

Ingresa: **Número de matrícula: 366-35594**

---

### **C. DIAN (Dirección de Impuestos y Aduanas Nacionales)**

**Para obligaciones tributarias:**

**Sistema MUISCA (consulta pública):**

- URL: <https://www.dian.gov.co/>
- Busca: "Consulta de predios" o "Sistema de información catastral"
- Ingresa: Código catastral o dirección

**Información disponible:**

- ✓ Valor fiscal
- ✓ Impuesto predial adeudado
- ✓ Historial de pagos
- ✓ Identificación del propietario (para tributarios)

---

### **D. ALCALDÍA DE MELGAR (Municipal)**

**Para información local:**

**Departamento Administrativo de Planeación (DAPM):**

- Email/teléfono: (ver en municipio)
- Solicita:
  - Certificado de uso del suelo
  - Clasificación en PBOT
  - Servicios municipales disponibles

**Archivos que pueden proporcionar:**

- PBOT (Plan Básico de Ordenamiento Territorial)
- Shapefile municipal completo
- Clasificación de zoning

---

### **E. CORTOLIMA (Corporación Autónoma Regional)**

**Para restricciones ambientales:**

- Sede: Melgar, Tolima (Territorial Oriente)
- Información:
  - ✓ Zona de amortiguación de páramos
  - ✓ Rondas hídricas
  - ✓ Áreas protegidas
  - ✓ Requisitos ambientales

---

## **3. FLUJO PRÁCTICO: OBTENER TODO PARA TU PREDIO**

### **Paso 1: Descarga la Ficha Catastral (IGAC)**

```bash
# Intenta nuevamente cuando la conectividad mejore
curl -X POST "https://servicios.igac.gov.co/arcgis/rest/services/Catastro/PredialNacional/FeatureServer/0/query" \
  -d "where=CODIGO_CATASTRAL='734490001000000010054000000000'" \
  -d "outFields=*" \
  -d "f=geojson"
```

**O accede vía navegador:**

- <https://www.igac.gov.co/> → Consulta catastral

---

### **Paso 2: Obtén la Matrícula Registral (SNR)**

**Ya tienes:** `Matricula: 366-35594`

Descarga el Certificado de Tradición desde:

- <https://www.supernotariado.gov.co/web/guest/consulte-la-matricula>
- Ingresa: `366-35594`
- Descarga: PDF con historial completo

---

### **Paso 3: Verifica Obligaciones Tributarias (DIAN)**

- <https://www.dian.gov.co/>
- Consulta predios
- Código: `734490001000000010054000000000`

---

### **Paso 4: Información Municipal (Alcaldía)**

**Llama o email a:**

```
DAPM Melgar
Teléfono: (57) 8-245-20-11
Solicita: 
  - Certificado de uso del suelo (ya tienes en PDFs)
  - Shapefile del municipio
  - Clasificación en PBOT vigente
```

---

### **Paso 5: Restricciones Ambientales (CORTOLIMA)**

**Contacto:**

```
CORTOLIMA - Territorial Oriente
Ubicación: Melgar, Tolima
Solicita:
  - Certificación de viabilidad ambiental
  - Análisis de restricciones
  - Zona de páramo / ronda hídrica
```

---

## **4. RESUMEN DE INFORMACIÓN QUE YA TIENES**

Basado en los PDFs que cargaste:

| Documento | Información | Estado |
|---|---|---|
| **Certificado de Tradición (SNR)** | Propietario, historial de transacciones | ✅ Completo (Torres Gómez, 2017) |
| **Uso de Suelo (Alcaldía)** | Clasificación PBOT | ✅ Completo (Agroforestal Turístico) |
| **Norma Urbanística** | Regulaciones aplicables | ✅ Completo |
| **Escritura** | Documento legal de compra/venta | ✅ Copia disponible |
| **Geometría (Shapefile)** | Polígono UTM | ❌ Pendiente (IGAC o Alcaldía) |
| **Valor fiscal actual** | Actualización 2026 | ❌ Pendiente (DIAN) |
| **Restricciones ambientales** | Páramos, rondas | ❌ Pendiente (CORTOLIMA) |

---

## **5. CONSULTA RÁPIDA SIN CURL (Alternativa Web)**

Si tu conexión a IGAC falla, **acceso directo por navegador:**

1. **IGAC:** <https://www.igac.gov.co/>
2. **SNR:** <https://www.supernotariado.gov.co/>
3. **DIAN:** <https://www.dian.gov.co/>
4. **PBOT Melgar:** Busca en Google `"PBOT Melgar" filetype:pdf`

---

## **Mi Recomendación para tu Proyecto**

**Prioridad 1 (crítico):**

- ✅ Matrícula SNR → Ya tienes (366-35594)
- ✅ Uso de suelo → Ya tienes (PDFs)
- ⚠️ Shapefile IGAC → Intenta descarga manual web

**Prioridad 2 (importante):**

- Valor fiscal actual (DIAN)
- Certificación de restricciones ambientales (CORTOLIMA)

**Prioridad 3:**

- Shapefile detallado del municipio (Alcaldía)
- Servicios disponibles (empresa de servicios)

¿Quieres que te ayude a **crear un script Python** que consolide toda esta información en una sola consulta?
