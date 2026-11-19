# Encargo F7b: experimento de adopción de JEV en las fechas de la lista

Rama `proyecto`. No commitees.

## Por qué (revisión retrospectiva; decisión del usuario del 18 de noviembre)

- **Uso no evaluado:** `DESIGN.md:24` dice que JEV se queda en cada punto solo si mejora el resultado en un banco etiquetado. En el enrutador se midió (`Experimento_JEV.md`). En las fechas de la lista, JEV se usa sin experimento: `api.py` lo inyecta en la propuesta.
- **Para qué sirve JEV ahí:** asigna cada fecha candidata a una actividad del cronograma (`herramientas.py:310-336`). Las fechas verificadas alimentan la detección de `fechas_distintas`, el conflicto entre bases y modificación. Sin JEV, todas salen `no_verificada` y ese conflicto no se detecta en la lista.
- **Alternativas a comparar:** asignar con reglas deterministas a partir de la descripción de la fila del cronograma, o no verificar.

## Regla de adopción (fijada antes de correr; no se cambia después)

- **Crítico:** una fecha marcada `verificada` con una actividad distinta de la etiqueta.
- **Acierto:** `verificada` con la actividad correcta.
- **JEV se queda** si no tiene más críticos que las reglas y su número de aciertos supera al de las reglas con McNemar p < 0,05.
- **Si no se cumple:**
  - si las reglas tienen 0 críticos, se adoptan las reglas, que no salen de la máquina ni cuestan;
  - si las dos tienen críticos, las fechas quedan `no_verificada` y la detección de conflictos de fechas se declara como limitación.
- **La latencia** se reporta, pero no decide: la propuesta de lista no tiene la meta de 15 s.

## Conjuntos

- **Candidatas:** todas las que produce `extraer_requisitos` en los 5 eventos del corpus R6.
  - Desarrollo: los eventos 399 y 363, para ajustar las reglas.
  - Prueba: los eventos 368, 327 y 222.
  - Si una partición queda con menos de 15 candidatas, repórtalo antes de seguir.
- **Etiqueta de oro:** la actividad, de la lista de actividades de `preguntas_jev.py`, o `ninguna`.
  - El gestor la obtiene con el proponente (Codex) y el revisor a ciegas (Claude), como en F7, con la adjudicación del usuario.
  - Tú solo preparas los archivos.

## Archivos

- `src/licigt/consulta/experimento.py`, o un módulo nuevo `experimento_fechas.py`, y sus pruebas.
- `herramientas.py`: solo para extraer la asignación por reglas como función reutilizable, sin cambiar el comportamiento actual.
- `Makefile`: objetivos nuevos.
- **No toques** `orquestador.py`, `validacion.py`, `config.py` ni `llm.py` (C21 trabaja ahí), ni `src/licigt/plataforma`.

## Qué construir (prueba en rojo primero)

1. **`make fechas-preparar`:** exporta las candidatas por partición a `data/consulta/agentes/fechas_ciego_<particion>.json`, con id, evento, fecha, pasaje (antes, literal y después, como lo arma `herramientas.py`) y sección, sin etiquetas. Además deja el mapa con `chunk_id` y página aparte.
2. **Variante de reglas:** asigna la actividad por coincidencia de palabras clave de cada actividad en el texto de la fila o en el contexto anterior. Si no hay coincidencia única, `no_verificada`.
   - Las palabras clave salen de las definiciones de `preguntas_jev.py`.
   - Se ajustan solo con desarrollo.
3. **`make experimento-jev-fechas CONJUNTO=… [CONFIRMAR=1]`:** sin `CONFIRMAR` solo hace la vista previa, sin crear el cliente. Con `CONFIRMAR=1` llama a JEV con las mismas preguntas que la propuesta y graba las respuestas crudas en `data/consulta/experimentos/fechas_<conjunto>_<UTC>.json`. Lo corre el usuario.
4. **`make fechas-comparar CONJUNTO=…`:** con las etiquetas (`data/consulta/agentes/etiquetas_fechas_<conjunto>.json`), la corrida de JEV y la variante de reglas, reporta por variante:
   - aciertos, críticos y `no_verificada`;
   - McNemar de JEV contra reglas sobre los aciertos;
   - si cada variante detecta los dos conflictos conocidos del 222 (adquisición de documentos y recepción de ofertas);
   - el veredicto con la regla de arriba.
5. **Pruebas con dobles:**
   - la vista previa no crea el cliente;
   - el cálculo de críticos y aciertos;
   - el veredicto en sus tres ramas;
   - la variante de reglas sobre filas sintéticas del cronograma.

## Al terminar

- **Corre:** `make fechas-preparar` y la variante de reglas sobre desarrollo, sin JEV.
- **Reporta:**
  - el número de candidatas por partición;
  - los archivos generados;
  - las pruebas;
  - las decisiones.

## Reglas

- Sin `keys/`.
- No llames a JEV.
- No uses `make … PYTHON=…`.
