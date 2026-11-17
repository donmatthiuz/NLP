# Encargo C10: datos tomados de la cita por el código

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C7](C7_reglas_cerradas_F4.md) y [C9](C9_integracion_llm_real.md);
- `src/licigt/consulta/validacion.py` (`_poner_marcadores`, `_continua`, la regla de tramo corto y las unidades) y `orquestador.py` (mensaje de regeneración), con sus pruebas;
- `diag_resultados_nuevo.json` y `diag_run2.py`, en el scratchpad del gestor.

## Origen

Tras C9, con el LLM real responden 3 de 10 preguntas. Dos fallas honestas siguen abiertas:

- **Comparar y requisitos de la plica:** el modelo escribe identificadores con dígitos en el texto ("Modificación Número 1", "subnumeral 2.30") sin declararlos en `datos`, y la respuesta se rechaza con `dato_fuera_de_literal`.
- **Seguro de caución:** con alerta de conflicto, el modelo cita un solo documento y la respuesta se rechaza con `falta_segunda_fuente`. La regeneración no le dice cuál falta.

## Archivos

Solo `validacion.py` y `orquestador.py`, con sus pruebas.

## Cambios (prueba en rojo primero)

### Tramos con datos tomados de la cita

Se aplica después de `_poner_marcadores` y antes de validar.

- **Qué es un tramo:** en el texto sin marcadores, una secuencia máxima de palabras con dígitos o nombres de mes, unidas solo por tramos cortos (sin palabras de 4 o más letras), igual que la regla de C7.
- **Si el tramo aparece tal cual en una de las citas de la afirmación**, con límites de palabra y de número (`_buscar`):
  - el código crea un dato con ese literal y esa cita, y lo reemplaza por un marcador;
  - si aparece en varias citas, usa la cita de los datos que ya tiene la afirmación; si no tiene ninguno, usa la primera.
- **Si el tramo no aparece**, queda como está y las reglas actuales lo rechazan (`dato_fuera_de_literal`).
- **Lo que no cambia:** todas las reglas posteriores (una sola cita, unidades, tramo corto entre marcadores, meses, letras que parecen dígitos), aplicadas sobre el texto con los marcadores nuevos.
- **Auditoría:** el número de datos creados (`datos_desde_cita`), sin texto.
- **Pruebas:**
  - "Modificación Número 1" con la cita de la modificación que lo contiene, y "subnumeral 2.30" con su cita, publican;
  - "1 de julio de 2023" frente a una cita que dice "31 de julio de 2023" se sigue rechazando;
  - un tramo que solo existe en otra cita de la afirmación sigue cayendo en `datos_de_varias_citas` si mezcla citas;
  - siguen fallando todos los ataques de los scripts `c4_*` a `c7_*`;
  - `c5_falsos`, `c6_falsos` y `c7_falsos` siguen publicando.

### Regeneración ante un conflicto sin las dos fuentes

- Si el error es `falta_segunda_fuente`, el mensaje de regeneración nombra los alias de fragmento (F1..Fn) del documento que falta citar, sin texto del documento.
- **Prueba:** el mensaje contiene el alias del fragmento del documento que no se citó.

## Verificación real (obligatoria)

Los servicios ya están arriba. Corre `diag_run2.py` con el código nuevo y reporta la tabla de las 10 preguntas frente a la de C9. Corre también los scripts de ataques y de falsos.

## Criterios de aceptación

- `make test-consulta` en verde.
- Ningún ataque nuevo pasa.
- Responden más preguntas que en C9, o queda explicado por qué no.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- la tabla real;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
