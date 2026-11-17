# Encargo C13: octava pasada del adversario (caminos de C9 a C11)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C9](C9_integracion_llm_real.md) y [C10](C10_datos_desde_la_cita.md);
- C11, en el commit `5b60b9c`;
- `validacion.py`, `orquestador.py`, `enrutador.py` y `generacion.py`, con sus pruebas.

Los scripts `c8_*.py` del adversario y su lanzador de regresión (`c8_correr.py`, `c8_regresion.sh`) están en el scratchpad del gestor.

## Hallazgos y correcciones (prueba en rojo primero, en cada uno)

### H1 (media, sin inyección): el identificador como fuente parcial

- **Hallazgo:** con el identificador "Modificación Número 1", cualquier "1" suelto del texto pasa por respaldado.
- **Regla nueva:** un tramo sale del `identificador_version_oficial` solo si el texto contiene el identificador **completo**, con límites de palabra. El dato es el identificador entero.
- **Prueba:** el bloque I1 de `c8_ataques.py` se rechaza; "En la Modificación Número 1, …" sigue publicando.

### H2 (media, sin inyección): relleno con el otro documento

- **Hallazgo:** con `falta_segunda_fuente`, el modelo repitió la misma afirmación citando un fragmento ajeno del otro documento.
- **Cambios:**
  - dos afirmaciones con el mismo texto normalizado dan `afirmacion_duplicada`;
  - cuando hay conflicto, la afirmación que cita el otro documento debe compartir con su cita al menos una palabra de contenido de 5 o más letras, sin contar las palabras vacías ni los marcadores; si no, `cita_ajena`;
  - el mensaje de regeneración de `falta_segunda_fuente` cambia. Ya no indica qué alias usar. Dice que, si el otro documento trata el mismo dato, se agregue una afirmación con lo que dice ese documento citándolo, y si no lo trata, que se abstenga.
- **Prueba:** la salida O4 de `c8_orquestador.py` no publica.

### H4 (baja): un dato de más de 200 caracteres rompe el validador

- **Cambio:** un tramo de más de 200 caracteres no se convierte en dato, y el texto falla con las reglas de siempre. `validar` nunca lanza `ValidationError`: el error se convierte en un código.
- **Prueba:** la salida O1, seguida de una salida válida, da 2 llamadas y `regenerada_ok`.

### H5 (baja): la firma de `generar`

- **Cambio:** el Protocol `ClienteGenerador.generar` incluye `semilla_extra: int = 0`. Los dobles de las pruebas (`test_lista.py` y los demás) se actualizan.
- **Prueba:** O2 de `c8_orquestador.py` regenera.

### H6 (baja): preguntas con dos fechas

- **Cambio:** la negación de `PATRON_DATO_UNICO` reconoce una segunda fecha, hora o plazo ("y la de", "y cuándo", ", la de", "y la fecha", "y la hora").
- **Prueba:** las tres preguntas de O5 van a `extraer_requisitos`.

### H7 (baja): uniones entre datos que puso el código

- **Cambio:** si un marcador puesto por `_poner_marcadores` y un dato creado desde la cita quedan contiguos, la excepción de `UNIONES` no aplica: el compuesto debe aparecer seguido en la cita.
- **Prueba:** el bloque I5 de `c8_ataques.py` se rechaza, y las listas honestas de `c6_falsos` y `c7_falsos` siguen publicando.

### Falso rechazo: la unidad queda fuera del tramo

- **Hallazgo:** con `datos=[]`, 17 de 60 casos se rechazan porque el tramo termina en el último dígito y deja fuera la unidad ("150 mg", "10:00 horas", "días").
- **Cambio:** si a la palabra con dígito la sigue una unidad de la lista de C7, y la cita trae esa misma unidad seguida, el tramo la incluye.
- **Prueba:** `c8_falsos.py` en la variante con solo texto sube de 43/60, sin abrir ningún ataque.

### H3 (baja): riesgo declarado

- Una cita larga puede traer otra fecha del mismo fragmento. Queda como riesgo medido en `Auditoria_F4.md`: 7 de 1006 fragmentos tienen dos fechas distintas que caben en una cita de 500 caracteres.
- No hay cambio de código.

### Prompt

- El prompt pide citas breves de hasta 300 caracteres, coherente con el tope de 500 del validador.
- Sube `VERSION_PROMPT`.

## Verificación

- `make test-consulta` en verde.
- La regresión con `c8_regresion.sh` sin cambios en los ataques.
- `c5_falsos`, `c6_falsos` y `c7_falsos` y el barrido siguen publicando.
- Con los servicios reales, `diag_run2.py` no baja de 5/10. Los servicios ya están arriba; usa el comando que arma el `Makefile`, sin leer la llave.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados, incluida la tabla real;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
