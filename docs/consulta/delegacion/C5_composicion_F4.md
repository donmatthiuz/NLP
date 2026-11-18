# Encargo C5: composición de la línea en F4 (cuarta pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C4](C4_datos_literales_F4.md);
- `src/licigt/consulta/validacion.py`, `generacion.py` y `orquestador.py`, con sus pruebas.

## Origen

La cuarta pasada del adversario confirmó que el diseño de datos literales funciona. H5, H7, H8 y el falso rechazo de la hora quedaron cerrados. El problema está en el armado.

- El validador comprueba el texto sin marcadores y cada literal por separado, pero nunca la línea ya armada (`validacion.py:186-188`).
- El texto del modelo controla lo que rodea a cada marcador.

Los scripts `c4_*.py` del adversario están en el scratchpad de la sesión del gestor.

## Archivos

Solo `validacion.py`, `generacion.py` y `orquestador.py`, y las pruebas `test_validacion.py`, `test_generacion.py` y `test_orquestador.py`.

## Correcciones (prueba en rojo primero, en cada una)

### N1, N2 y N6 (alta): cada marcador va aislado

- **Antes del marcador:** el inicio del texto, un espacio o `(`.
- **Después del marcador:** el final del texto, un espacio, o uno de `.`, `,`, `;` y `)`. Si sigue uno de esos signos, después solo puede venir un espacio o el final del texto.
- **Además:**
  - no puede haber dos marcadores contiguos;
  - no se puede repetir un marcador;
  - cada dato se usa exactamente una vez.
- **Si falla:** `marcador_pegado`.
- **Pruebas** con los fragmentos reales `00115` y `00001`. Deben rechazarse:
  - `{1}%`, `{1}{2}%`, `{1}/{2}/{3}`, `{1}:{2}`, `{1}{1}` y `[{1}]`;
  - `ma{2}o`, `octu{1}re` y `a{1}ril`.
- **Como segunda barrera:** sobre la línea armada, antes de agregar los `[n]` reales, se aplican `FALSO_FUENTE` y la búsqueda de meses fuera de los tramos de literal.

### N3 (media): lista blanca de caracteres en el texto

El texto fuera de los marcadores solo puede llevar:

- letras ASCII, `áéíóúüñ` y `ÁÉÍÓÚÜÑ`;
- espacios;
- la puntuación `.,;:()¿?¡!"'-`.

Cualquier otro carácter da `texto_invalido`. Esto cierra `ɡ`, `ı`, `ȷ`, `ɑ`, las versalitas, U+2800 y las letras que parecen dígitos.

- **Prueba:** cada variante de N3.
- **Riesgo residual, declarado en un comentario de una línea:** un mes partido con espacios o guiones ("oc tubre", "o-c-t-u-b-r-e"). Requiere inyección y deja un texto visiblemente roto.

### N4 (media): la cita no puede empezar ni terminar dentro de un número

- Si el borde de la cita es un carácter de `.,/:-` y del otro lado, en el fragmento, hay un dígito, da `cita_no_literal`.
- Lo mismo con un dígito en el borde y un separador seguido de un dígito al otro lado.
- **Pruebas** con `00001`: `límite 11:`, `:30), en Salones` y `-72 Zona 1` se rechazan, y la cita completa `11:00 horas` pasa.

### N7 y N8 (baja): se publica el texto del documento

- **N7:** el literal se inserta en `answer` sin NFKC; solo se colapsan los espacios. La comparación sigue siendo con NFKC.
- **N8:** en `sources[].cita` se publica el tramo correspondiente del fragmento, no el texto que escribió el modelo.
  - Usa un mapa de posiciones entre el texto normalizado y el original.
  - Si no se puede mapear, `cita_no_literal`.
- **Pruebas:**
  - "10⁶ UI" se publica tal cual;
  - una cita escrita por el modelo con otra capitalización o sin tildes publica el texto original del fragmento.

### FR1 y FR2 (media): falsos rechazos del diseño a dos columnas

- **FR1:**
  - los espacios del literal se colapsan antes de comprobar los saltos de línea;
  - un literal copiado fiel del fragmento, con salto y 60 espacios, pasa;
  - un `[n]` dentro del literal sigue siendo inválido.
- **FR2:**
  - el largo máximo de la cita se mide después de colapsar los espacios, y el validador local lo aplica (en el esquema queda sin `maxLength`);
  - el prompt pide colapsar los espacios al citar;
  - `esquema_invalido` entra en la guía del mensaje de regeneración.
- **Prueba:** la cita fiel de `00009` de 276 caracteres crudos pasa.

### FR4 (prompt): ejemplos de cifras que no son plazos

- El prompt amplía el ejemplo:
  - también se marcan los códigos IGSS, los numerales, las concentraciones, el NOG y el número de evento;
  - un ejemplo corto con un código y una concentración.
- Sube `VERSION_PROMPT`.
- Esto no se puede medir sin el LLM real. Queda para el banco con `make llm-servidor`.

## Fuera de alcance

- **N5:** miles separados por espacio. El corpus no tiene ninguno; queda una prueba marcada como riesgo conocido.
- **N9:** que el modelo copie el prompt del sistema. No contiene secretos.

## Criterios de aceptación

- `make test-consulta` en verde.
- Ningún carácter de `answer` fuera de los tramos de literal puede ser un dígito, ni formar un nombre de mes, ni pegarse a un literal.
- Siguen pasando los casos legítimos de C4 y la cita a dos columnas de `00009`.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo con su prueba;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
