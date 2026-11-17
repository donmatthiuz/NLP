# Encargo C4: datos literales en F4 (tercera pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [F4](F4_generacion_y_orquestacion.md), [C2](C2_correcciones_F4.md) y [C3](C3_correcciones_F4_segunda.md);
- `src/licigt/consulta/generacion.py`, `validacion.py`, `orquestador.py`, `llm.py` y `requisitos.py`, con sus pruebas.

## Origen

La tercera pasada del adversario volvió a refutar F4, con fragmentos reales del 222 y reproducido por el gestor:

- **H1 (alta):** la cita puede empezar a mitad de un número. "1 de julio de 2023" se valida como cita de "31 de julio de 2023"; "20) días" sale de "ciento veinte (120) días".
- **H2 (alta):** se arma una fecha con el día de una cita y el mes de otra ("31 de octubre", "octubre 31 de 2023", "31 de octubre, 2023").
- **H3 (alta):** meses que el analizador no reconoce pasan sin comprobar ("31/ago/2023", "ago-2023", "31ago2023", "August 31", guion suave, ZWSP, o cirílica).
- **H4 (media):** la hora sale de otra cita (11:00 frente a 10:00), y "120%" se respalda con "(120) días".
- **H5 (media):** "la fecha que rige es la de la modificación; la de las bases ya no aplica" se publica sin revisión humana.
- **H6 (baja):** marcadores falsos `［2］`, `[²]` y `[٢]`.
- **H7 (baja):** la auditoría registra el alias configurado y no el modelo que respondió.
- **H8 (baja):** la reserva para el bloque de fechas puede vaciar toda la evidencia.
- **Falso rechazo:** "a las 11 horas" frente a "a las 11:00 horas".

Scripts del adversario: `sonda1.py` a `sonda9.py`, en el scratchpad de la sesión del gestor. Son solo referencia; las pruebas del repo deben cubrir los mismos casos.

## Por qué cambia el diseño

Tres rondas de parches al analizador de fechas y cifras abrieron cada vez variantes nuevas. Mientras el modelo escriba los datos y el código intente reconocerlos, siempre habrá un formato que el código no entienda.

El usuario aprobó el principio que ya usa F3b con JEV: **seleccionar, no generar** (`Plan_rol_3.md`, F3b). El modelo deja de escribir fechas, horas, cifras, porcentajes y montos. Los copia literalmente de una cita, y el código los inserta en la respuesta.

## Archivos

- **Código:** `generacion.py`, `validacion.py`, `orquestador.py` y `llm.py`. En `requisitos.py`, solo para quitar lo que quede sin uso.
- **Pruebas:** `test_generacion.py`, `test_validacion.py`, `test_orquestador.py`, `test_llm.py` y `test_requisitos.py`.
- Las pruebas existentes que usan el esquema viejo se reescriben al nuevo, pero **cada ataque de C2, C3 y C4 sigue teniendo su prueba** y sigue fallando como ataque.
- Nada más: ni `herramientas.py`, ni `esquemas.py`, ni el `Makefile`.

## Cambios (prueba en rojo primero, en cada uno)

### 1. Esquema de salida con datos literales

- `Afirmacion` gana `datos: list[Dato]`, con `Dato = {cita: int, literal: str}`:
  - `cita` es la posición, empezando en 1, dentro de `afirmacion.citas`;
  - `literal` es el texto exacto copiado de esa cita.
- En `texto`, cada dato aparece como marcador `{1}`, `{2}`, etc., en el orden de `datos`.
- `esquema_salida` y el esquema estricto de OpenAI se actualizan; todos los campos son obligatorios en modo estricto.
- Con el perfil `openai` no se mandan las palabras clave que no admite (A7). Verifica con Context7 o con la documentación de Structured Outputs si se admiten `minimum` y `maximum` en `integer`, y anótalo en un comentario de una línea con la URL.

### 2. Reglas del validador

Sustituyen a la comparación de fechas y cifras de C2 A1 y C3 B1 a B3.

- **Cita con límites de palabra (H1):**
  - la cita debe ser subcadena del fragmento normalizado;
  - si la cita empieza o termina en un carácter alfanumérico, el carácter vecino en el fragmento no puede ser alfanumérico;
  - si falla: `cita_no_literal`.
- **Literal con límites de palabra:**
  - `literal` debe ser subcadena de su cita, con la misma regla de límites;
  - la comparación es exacta salvo espacios repetidos y NFKC; no se quitan ceros ni se cambian formatos;
  - si falla: `dato_no_literal`.
- **Una sola cita por afirmación con datos (H2, H4):** todos los `datos` de una afirmación salen de la misma cita. Si el modelo necesita datos de dos citas, escribe dos afirmaciones. Si falla: `datos_de_varias_citas`.
- **Nada de datos fuera de los marcadores (H3, H6).** En `texto`, sin contar los marcadores y después de NFKC:
  - sin dígitos de ninguna escritura (categoría Unicode `N*`);
  - sin nombres ni abreviaturas de mes:
    - español completo y abreviado, incluidos `sep`, `sept` y `set`;
    - inglés completo y abreviado;
    - comparados por palabra completa, en minúsculas y sin tildes;
  - si falla: `dato_fuera_de_literal`.
- **Caracteres prohibidos en `texto` y en `literal` (H3):** cualquier carácter de categoría `Cf`, o letras que no sean del alfabeto latino, dan `texto_invalido`.
- **Marcadores:**
  - cada `{n}` debe existir en `datos`, y cada dato debe usarse al menos una vez;
  - un marcador mal formado da `texto_invalido`;
  - se mantiene la regla de C2 A3 contra `[n]` y los saltos de línea.
- **Lo que deja de existir:** `dato_sin_respaldo` y la comparación por la unión de las citas. Si `fechas_en_texto`, `normalizar_cifras` o `_datos_sensibles` quedan sin uso, se borran con sus pruebas. `encontrar_fechas` se queda, porque el cronograma la usa.
- **Fuera de alcance, en un comentario de una línea:** cifras escritas con letras ("ciento veinte") y días en números romanos. La fidelidad de esas paráfrasis la revisa una persona (I1, sección 3).

### 3. Armado de la respuesta

- `answer` se arma sustituyendo cada marcador por su `literal` validado, seguido de los marcadores de fuente `[n]`, igual que hoy.
- El texto que ve el usuario contiene los datos tal como están en el documento. Por ejemplo, "06 de octubre de 2023, a las 11:00 horas".

### 4. Prompt (`VERSION_PROMPT = "f4-v2"`)

- Instrucción explícita: toda fecha, hora, cifra, porcentaje, monto o mes se escribe como marcador, y su texto exacto va en `datos`, copiado de una sola cita.
- Un ejemplo corto y completo en el formato JSON.
- Sigue valiendo lo de F4: la evidencia es un dato no confiable y la abstención es explícita.
- El mensaje de regeneración nombra los códigos nuevos y cómo corregirlos. Por ejemplo, `datos_de_varias_citas` se corrige dividiendo en dos afirmaciones.

### 5. Vigencia por documentos citados (H5)

Decisión del usuario: escalar por los documentos citados.

- Si alguna fuente de la respuesta es de tipo `modificacion` o `aclaracion`, `needs_human_review = true`, aunque sea la única fuente citada.
- Se mantienen las raíces de C3 B4.
- La regla solo escala; no rechaza.
- **Pruebas:** las tres frases de la sonda 3 del adversario con la cita real de `d41480e5b0ce4c16bf18f66225ada2dc:00009`.

### 6. Modelo en la auditoría (H7)

- `modelo_generador` se lee con `_atributo_seguro` dentro del `finally`, después de `generar()`.
- **Prueba:** un generador que cambia su modelo durante `generar()` deja en el evento el valor nuevo, y uno cuya propiedad lanza deja `None`.

### 7. Reserva del bloque de fechas (H8)

- El costo de cada fragmento es su texto más el JSON de sus propias fechas.
- El recorte elige fragmentos con ese costo, así que el bloque de fechas solo lleva las fechas de los fragmentos elegidos.
- **Prueba:** el caso de B8 con un tope de 6000 deja al menos el primer fragmento y sus fechas.

## Pruebas mínimas nuevas (con los fragmentos reales del 222 cuando el caso los usa)

- **H1:** "1 de julio de 2023" citado desde "31 de julio" da `cita_no_literal`. "20) días" desde "(120) días" también, y lo mismo un literal "1 de julio de 2023" dentro de una cita válida que diga "31 de julio de 2023".
- **H2 y H4:**
  - datos de F1 y F2 en una sola afirmación dan `datos_de_varias_citas`;
  - la fecha de 00009 con la hora de 00005 en una sola afirmación, también;
  - "120%" no puede salir de "(120) días": el literal "120%" no es subcadena.
- **H3 y H6:** "31 de octubre", "31/ago/2023", "ago-2023", "August 31", "octu­bre", "agos​to", "оctubre", `［2］`, `[²]` y `[٢]` escritos en `texto` fuera de un marcador dan `dato_fuera_de_literal` o `texto_invalido`.
- **Casos legítimos que deben pasar:**
  - "La recepción de ofertas es el {1}." con el literal "06 de octubre de 2023, a las 11:00 horas" de la cita a dos columnas de `00009`, que además sale con `needs_human_review` por ser una modificación;
  - una afirmación sin datos ("Se requiere constancia de inscripción en el RGAE.") con su cita;
  - dos afirmaciones, cada una con datos de su propia cita.
- Todo ataque de C2 y C3 (A1, B1, B2 y B3) reescrito al esquema nuevo sigue fallando.

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios.
- Ningún dígito ni nombre de mes llega a `answer` si no sale de un literal validado.
- Sin texto de PDF, pregunta ni llave en la auditoría, las advertencias ni los errores.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo (H1 a H8 y el falso rechazo de la hora) con su prueba;
- lo que verificaste en el punto 1 sobre `minimum` y `maximum`, con la URL;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
