# Encargo C3: segunda corrección de F4 (segunda pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C2](C2_correcciones_F4.md);
- `src/licigt/consulta/validacion.py`, `generacion.py`, `orquestador.py`, `llm.py` y `requisitos.py`, con sus pruebas.

## Origen

La segunda pasada del adversario confirmó que A4 a A8 cerraron y que no hay falsos rechazos en los fragmentos reales del 222. Pero A1 no cerró la clase de ataque. Hallazgos B1 a B8, reproducidos con scripts.

## Archivos

Solo `validacion.py`, `generacion.py`, `orquestador.py`, `llm.py` y `requisitos.py`, y las pruebas `test_validacion.py`, `test_generacion.py`, `test_orquestador.py`, `test_llm.py` y `test_requisitos.py`.

## Correcciones (prueba en rojo primero, en cada una)

### B1 y B3 (alta y media): las fechas se comparan como fechas, y cada una sale de una sola cita

- **Extraer fechas** en `requisitos.py` (un solo lugar para las fechas del proyecto):
  - amplía `encontrar_fechas`, o añade una función hermana, para que reconozca el mes completo o abreviado, con o sin punto: `ene`, `feb`, `mar`, `abr`, `may`, `jun`, `jul`, `ago`, `sep`, `sept`, `set`, `oct`, `nov` y `dic`;
  - y también las fechas numéricas `dd/mm/aaaa`, `dd-mm-aaaa` y `dd.mm.aaaa`, interpretadas como día y mes en el uso de Guatemala.
- **Fecha incompleta en la afirmación:** si menciona un mes (completo o abreviado) sin año, igual debe aparecer en una cita.
- **Regla del validador, un paso nuevo dentro de `dato_sin_respaldo`:** cada fecha que aparezca en `afirmacion.texto` debe ser igual, como `date`, a una fecha encontrada en **una sola** de sus citas. No vale armarla con el día de una cita y el mes de otra.
- **Formatos equivalentes:** "31 de julio de 2023" en la afirmación con "31/07/2023" en la cita pasa, porque es la misma fecha. Esto quita un falso rechazo.
- **Meses sueltos:** se reconocen por su número de mes, no por el texto. "ago." y "agosto" son el mismo mes y "julio" no lo es.
- **Fuera de alcance, declarado en un comentario de una línea:** días en números romanos y cifras con letras.
- **Pruebas:**
  - se rechazan "31 de ago. de 2023", "31 de oct de 2023" y "31 de sept. de 2023" frente a una cita de julio;
  - se rechaza una fecha armada con el día de una cita y el mes de otra;
  - se acepta "31 de julio de 2023" frente a la cita "31/07/2023";
  - se acepta "6 de octubre" frente a "06 de octubre de 2023".

### B2 (media): separadores de miles y dígitos no ASCII

- **Antes de extraer números:**
  - une los grupos de dígitos separados por espacio, NBSP (U+00A0), U+202F o espacio fino (U+2009) cuando el grupo siguiente tiene exactamente 3 dígitos;
  - convierte a ASCII cualquier dígito decimal Unicode (`unicodedata.decimal`).
- **Equivalencia de separadores:** "Q1 000 000.00" y "Q1,000,000.00" son el mismo número para comparar.
- **Pruebas:**
  - se rechaza "Q1 000" frente a "Q1 000 000.00", también con NBSP y con U+202F;
  - se rechaza "٣٠ de julio" frente a "31 de julio";
  - se acepta "Q1,000,000.00" frente a "Q1 000 000.00".

### B4 (baja): vigencia por raíces

- **Raíces:** `vigent`, `vigenc`, `prevalec`, `sustitu`, `reemplaz`, `deroga`, `anula` y "sin efecto".
- **Antes de comparar:** quita los caracteres de formato (categoría Unicode `Cf`, como el espacio de ancho cero).
- **Pruebas:** "vigentes", "prevalecen", "queda sin efecto", "derogada" y "vi​gente" escalan a `needs_human_review`.

### B5 (baja): signos de menor y mayor confundibles

- `_neutralizar` aplica NFKC y luego cambia `<`, `>`, `＜`, `＞`, `﹤` y `﹥` por `‹` y `›`.
- **Prueba:** ninguno de esos caracteres de origen no confiable llega al prompt.

### B6 (baja): auditoría con un generador raro

- `modelo_generador` se lee con la misma función segura de A5.
- **Prueba:** un generador cuya propiedad lanza una excepción produce igual un evento, con `modelo_generador = None`.

### B7 (baja): host del perfil `openai`

- Con `LICIGT_LLM=openai`, el host debe ser `api.openai.com`.
- Otro proveedor, por ejemplo OpenRouter, sería un perfil nuevo con su propio host; no entra ahora.
- **Prueba:** se rechaza `https://evil.example/v1` con `config_insegura`.

### B8 (baja): el tope de evidencia cuenta el bloque de fechas

- El presupuesto de caracteres incluye el JSON de `<fechas>`.
- El literal de cada fecha se recorta a 60 caracteres.
- **Prueba:** 50 fechas con literales de 10 000 caracteres no inflan el prompt por encima del presupuesto más los protegidos.

## Criterios de aceptación

- `make test-consulta` en verde.
- Los casos legítimos siguen pasando: el 222 con "06 de octubre de 2023, a las 11:00 horas" y la cita continua a dos columnas de `d41480e5b0ce4c16bf18f66225ada2dc:00009`.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo (B1 a B8) con su prueba;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
