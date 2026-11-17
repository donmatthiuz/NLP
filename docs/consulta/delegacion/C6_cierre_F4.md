# Encargo C6: cierre de F4 (quinta pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C4](C4_datos_literales_F4.md) y [C5](C5_composicion_F4.md);
- `src/licigt/consulta/validacion.py`, `generacion.py` y `orquestador.py`, con sus pruebas.

## Origen

La quinta pasada del adversario (scripts `c5_*.py` en el scratchpad del gestor) no encontró ningún ataque que funcione con un modelo honesto. Todo lo que queda requiere inyección en un PDF oficial o es latente. De 15 respuestas honestas con datos reales del 222, el validador publicó 13 y rechazó 2 por puntuación.

El usuario decidió corregir todo y pedir una sexta pasada.

## Archivos

Solo `validacion.py`, `generacion.py` y `orquestador.py`, y las pruebas `test_validacion.py`, `test_generacion.py` y `test_orquestador.py`.

## Correcciones (prueba en rojo primero, en cada una)

### Falsos rechazos honestos (prioridad)

- **FR-a, "y/o":** se admite `/` entre dos letras. No se admite pegado a un marcador ni entre dígitos, así que siguen fallando `{1}/{2}` y `{1}/`.
  - **Prueba:** el caso 11 del adversario, con el fragmento `00101`, publica.
- **FR-b, "Punto {1}:":** después de un marcador se admite `:` seguido de un espacio o del final del texto, con las mismas reglas que `.`, `,` y `;`. Siguen fallando `{1}:{2}` y `{1}:30`.
  - **Prueba:** el caso 12 del adversario, con `00013` de la modificación, publica.

### H-A1 y N1 (alta): marcadores compuestos

- **Conector:** un tramo formado solo por espacios, `de`, `del`, `,`, `a las`, `a la`, `-`, `–` y `—`.
- **Regla:** si dos o más marcadores están unidos solo por conectores, el tramo compuesto completo (literal, conector, literal) debe aparecer seguido en su cita, con la normalización y los límites de palabra de siempre. Si no, `dato_no_literal`.
- **Fuera de la regla:** `y`, `o`, `entre` y `hasta` no son conectores, así que "entre {1} y {2}" con "1%" y "5%" sigue pasando.
- **Literal sin cifra ni letra:** un literal sin ningún carácter alfanumérico, como `%` o `-`, da `dato_no_literal`.
- **Pruebas** con `00001` y `00115`:
  - deben rechazarse:
    - "{1} de {2} de {3}" con los literales "1", "julio" y "2023";
    - "{1} de {2}" con los literales "7ª." y "julio de 2023";
    - "{1} {2}" con los literales "(120)" y "%";
    - "{1} – {2}";
  - deben pasar:
    - "entre {1} y {2}" con "1%" y "5%";
    - "{1}, a las {2}" cuando la cita dice exactamente "31 de julio de 2023, a las 11:00 horas".

### H-A2 (media): unidad fuera del literal

- **Unidades:** `día`, `días`, `mes`, `meses`, `año`, `años`, `hora`, `horas`, `minutos`, `semanas`, `por ciento`, `porcentaje`, `mg`, `ml`, `g`, `kg`, `unidades`, `viales`, `quetzales`, `dólares`.
- **Después del marcador:** si lo siguen un espacio y una de esas palabras, da `unidad_fuera_de_literal`.
- **Antes del marcador:** lo mismo si lo preceden `Q`, `US$` o `$` y un espacio.
- **Prompt:** la unidad va dentro del literal. Sube `VERSION_PROMPT`.
- **Pruebas:** "de {1} días" con "dieciocho (18)", "del {1} por ciento" y "Q {1}" se rechazan; "de {1}" con "dieciocho (18) meses" pasa.

### H-A3 (baja): letras que parecen dígitos

- Una palabra de 2 o más caracteres formada solo por `l`, `I`, `O`, `S`, `Z` y `B`, con al menos uno en mayúscula salvo la `l`, da `dato_fuera_de_literal`.
- "lo", "os" y "IGSS" no caen en la regla.
- **Pruebas:** se rechazan "lOO" y "lO días", y pasan "lo", "los" e "IGSS".

### H-A4 (media): más formas de decidir la vigencia

- Además de las raíces de C3 B4, se escala si aparecen:
  - `rige` o `regir`;
  - `ya no aplica` o `no aplica`;
  - `válid` o `validez`;
  - `correct`;
  - `queda sin`;
  - `anterior`;
  - `actualizad`.
- La regla solo escala; no rechaza.
- **Pruebas:** las tres frases del adversario con la cita de `00047` salen con `needs_human_review`.

### H-A5 (baja): raya y guion medio

- Se mantienen en la lista blanca, por la decisión del gestor anotada en C5.
- Entre marcadores cuentan como conector, así que los cubre H-A1.
- **Prueba:** "{1} – {2}" se rechaza.

### H-A7 (baja): más separadores numéricos

- `SEPARADORES` incluye además `–`, `‑`, `'`, `’`, `·` y `⁄`.
- **Pruebas:**
  - "500'000" sacado de "1'500'000" da `cita_no_literal`;
  - el literal "2" dentro de "2½" da `dato_no_literal`.

### H-A8 y Nl (baja): fragmentos con tildes combinantes, signos neutralizados y números romanos

- **Fragmentos en NFD:** el fragmento se pasa a NFC antes de mapear, y el tramo publicado conserva las marcas combinantes finales.
- **Prueba NFD:** con un fragmento NFD y el literal "31 de julio de 2023", publica, y la cita termina en "será".
- **Signos neutralizados:** la cita y el literal se publican desde el texto original del fragmento, no desde la evidencia neutralizada. La neutralización cambia carácter por carácter, así que los índices coinciden.
- **Prueba de signos:** un fragmento con "<5%" publica "<5%" en `answer` y en la cita.
- **Números romanos:** la comprobación de categoría `N*` del texto se hace también antes de NFKC, para rechazar los de categoría `Nl` (`Ⅻ`, `Ⅰ`).
- **Prueba de romanos:** "Ⅻ" en el texto da `dato_fuera_de_literal`.

## Riesgos que siguen declarados

- N5: miles separados por espacio.
- Meses partidos con espacios.
- Cifras escritas con letras.
- N9: el modelo copia el prompt.
- El exceso de escalamiento por "vigencia" de seguros: escala de más, del lado seguro.

## Criterios de aceptación

- `make test-consulta` en verde.
- Los 15 casos honestos del adversario (`c5_falsos.py`) publican.
- Los ataques de `c5_ataques.py`, `c5_n4.py` y `c5_n8.py` se rechazan o escalan según corresponda.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo con su prueba;
- la salida resumida de los scripts `c5_*.py`;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
