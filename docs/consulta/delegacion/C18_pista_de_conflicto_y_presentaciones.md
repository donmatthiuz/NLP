# Encargo C18: pista del conflicto en toda regeneración y presentaciones reales

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C17](C17_revision_acotada_y_decima_pasada.md);
- `orquestador.py` (el mensaje de regeneración y `_conflictos`), `validacion.py` y `lista.py` (`tramo_literal`, `_es_basura` y el tramo de relevo), con sus pruebas;
- la medición con R5, en el scratchpad del gestor:
  - `r5m/diag.txt`;
  - `r5m/diag_resultados.json`;
  - `r5m/prop.txt`.

## Archivos

`orquestador.py` y `lista.py`, con sus pruebas. Nada más.

## Cambios (prueba en rojo primero)

### 1. La pista del conflicto en cualquier regeneración

- **Medido:** en la plica (pregunta 9), el primer intento falla por `texto_invalido`. El modelo cita la solvencia patronal de las bases ("31 de mayo de 2023") y no la de la modificación (`d41480…:00006`, sección 2.7, "31 de julio de 2023"). Como el primer error no es `falta_segunda_fuente`, el mensaje de regeneración no nombra los alias del documento que falta, y el segundo intento falla por `falta_segunda_fuente`.
- **Cambio:** en cualquier regeneración, si hay un grupo en conflicto con al menos dos documentos en la evidencia y la salida del primer intento no cita alguno de ellos, el mensaje agrega la línea de C17 con los alias de ese documento, junto con la instrucción de citarlo si trata el mismo dato o abstenerse. Si la salida no se pudo leer, se agrega la línea de todos los documentos del grupo.
- **Lo que no cambia:** las demás instrucciones, y que el mensaje no lleva texto de los fragmentos.
- **Prueba:** un primer intento con `texto_invalido` que no cita la modificación produce un mensaje con su alias.

### 2. Los dos puntos dentro de una oración no la cortan

- **Medido:** `03791a…:00047` empieza con "Los OFERENTES deben presentar los documentos requeridos en original y copia, en PLICAS separadas, rotuladas con la siguiente información del OFERENTE: Nombre, razón social…". El tramo se corta en ":", se descarta como presentación y el ítem se queda solo con la cola ("Nombre, razón social…").
- **Cambio:** una presentación es basura solo si lo que sigue a los dos puntos en el fragmento empieza una lista: un salto de línea seguido de un literal, numeral o viñeta (`a)`, `1.`, `•`, `▪`, `-`), o el fin del fragmento. Si después de los dos puntos sigue texto de la misma oración, el tramo no se corta ahí y llega hasta el fin de oración o el tope de C14.
- **Pruebas:**
  - `:00047` da un ítem que empieza en "Los OFERENTES deben presentar";
  - "2.8 REQUISITOS FUNDAMENTALES Se consideran Requisitos Fundamentales los siguientes:" sigue descartado;
  - `c9_cortes` no sube de 5.

## Verificación real

- La base tiene el paquete R5 y la API en 8010 está arriba. No los toques.
- Corre en proceso, con `c16/run.sh`:
  - `c16/diag.py`;
  - `c16/prop2.py`.
- Copia las salidas a `c18m/`.
- **Reporta:**
  - de las 10 preguntas, sobre todo la plica y el seguro de caución, con los errores de cada intento;
  - de la lista, los ítems, cuántos piden revisión y si está el de `:00047`.

## Criterios de aceptación

- `make test-consulta` en verde.
- Los ataques `c4_*` a `c9_*` y los scripts de `c17/` sin regresión.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las mediciones;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
