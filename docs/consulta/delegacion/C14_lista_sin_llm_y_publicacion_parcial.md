# Encargo C14: lista sin LLM y publicación parcial

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [F5](F5_lista_de_verificacion.md) y [C12](C12_hallazgos_de_la_demo.md);
- `lista.py`, `lista_escritura.py`, `herramientas.py`, `orquestador.py`, `validacion.py`, `llm.py` y `api.py`, con sus pruebas;
- el diagnóstico en el scratchpad del gestor, en `c12/d4b.json`.

## Decisiones del usuario (17 de noviembre)

1. **La propuesta de lista se arma sin LLM.** Se seleccionan tramos literales de los fragmentos; nada se genera. El usuario: "hay que escoger hacer bien el código de extracción y demás cosas que el LLM no debe lidiar".
2. **Si tras la regeneración solo fallan algunas afirmaciones, se publican las válidas con aviso.**

## Cambios (prueba en rojo primero)

### 1. Propuesta de lista determinista

- **Herramienta:** `proponer_lista` llama a `extraer_requisitos` y arma los ítems sin `generador`.
- **Un ítem por fragmento recuperado con categoría** (`resultado.categorias`), en el orden de la herramienta:
  - **cita:** el primer tramo legible del fragmento que existe tal cual en su texto, con los espacios colapsados. Se toma desde el inicio hasta el primer salto de línea doble o hasta 300 caracteres, cortando en el último fin de oración o de palabra.
  - Si el fragmento tiene columnas intercaladas (líneas con 3 o más espacios seguidos dentro del texto), el tramo es la primera línea completa sin esa separación.
  - **descripción:** la misma cita, como pide `ItemPropuesto`.
  - **carácter:** el de `caracter_de_seccion`.
  - **fuente:** `fuente_desde_fragmento`.
- **Fechas:** se mantienen los ítems de `FechaCandidata`, con su verificación JEV.
- **Revisión humana:** se mantiene la regla de conflicto entre documentos. Ya no hay `needs_human_review` de una respuesta generada.
- **Sin duplicados:** se descartan los ítems con la misma huella de F5.
- **Sin ítems:** si no hay ninguno, se responde con una abstención.
- **Lo que no cambia:** guardar sigue revalidando cada cita contra el fragmento (F5).
- **Lo que se quita:** el uso del generador en la propuesta, junto con su prueba.
- **Pruebas:**
  - con los fragmentos reales del 222 (de `c12/d4b.json` o del ZIP), la propuesta tiene ítems;
  - cada cita es subcadena literal de su fragmento y pasa la revalidación de `lista_escritura`;
  - no se llama a ningún generador.

### 2. JEV en la propuesta

- `api.proponer` pasa el cliente de JEV a `proponer_lista`, como la consulta.
- **Prueba:** con un doble de JEV, las fechas se verifican.

### 3. Publicación parcial

- Si después de la regeneración quedan errores, se publican solo las afirmaciones sin error de validación, renumerando sus fuentes, con el aviso `afirmaciones_descartadas: <n>` y `coverage_status = "parcial"`.
- **Si hay conflicto:** cuando tras el descarte no quedan citados al menos dos documentos del grupo en conflicto, se abstiene.
- **Si no queda ninguna afirmación,** se abstiene, como hoy.
- **Lo que no cambia:** los errores de toda la salida (esquema, JSON, `evento_distinto`) siguen abstenido.
- **Auditoría:** el número de afirmaciones descartadas, sin texto.
- **Pruebas:** 7 afirmaciones válidas y 1 con `cita_no_literal` publican 7 con el aviso; un conflicto donde se descarta un lado se abstiene.

### 4. La regeneración cambia de verdad

- A temperatura 0 la semilla no influye y la salida se repite byte a byte.
- **Cambio:** en la regeneración, `temperature` pasa a 0.3, configurable, sin tocar el primer intento.
- **Prueba:** el cliente recibe `temperature` 0.3 en la segunda llamada.

## Verificación real

Los servicios ya están arriba: la base y `llama-server` en 127.0.0.1:8080. Con el comando del `Makefile`, sin leer la llave, corre:

- la propuesta de lista del 222, midiendo el tiempo, el número de ítems y si pasan la revalidación;
- `diag_run2.py`, que no debe bajar de 5/10.

## Criterios de aceptación

- `make test-consulta` en verde.
- Los scripts de ataques (`c4_*` a `c8_*`) sin regresión.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- la medición real;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
