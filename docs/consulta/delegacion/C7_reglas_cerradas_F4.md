# Encargo C7: reglas que fallan cerrado en F4 (sexta pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C6](C6_cierre_F4.md);
- `src/licigt/consulta/validacion.py`, `generacion.py` y `orquestador.py`, con sus pruebas.

## Origen

La sexta pasada del adversario (scripts `c6_*.py` en el scratchpad del gestor) confirmó que F4 funciona con un modelo honesto:

- el barrido publica 932 de 932 citas;
- de 30 afirmaciones honestas, rechaza 1.

Lo que queda abierto sale de listas cerradas que nunca terminan: conectores, unidades, raíces de vigencia y separadores. Cada lista deja pasar variantes y, a la vez, rechaza texto honesto.

**Principio de este encargo:** cambiar listas de lo prohibido por reglas que fallan cerrado. Por defecto se exige que el tramo esté en la cita; las excepciones permitidas son pocas y explícitas.

## Archivos

Solo `validacion.py`, `generacion.py` y `orquestador.py`, y las pruebas `test_validacion.py`, `test_generacion.py` y `test_orquestador.py`.

## Correcciones (prueba en rojo primero, en cada una)

### A3 (media, sin inyección): vigencia por la evidencia, no por palabras

- **Regla nueva:** si la evidencia enviada al modelo contiene un fragmento de tipo `modificacion` o `aclaracion` del mismo evento, y la respuesta cita un documento de tipo `bases`, `needs_human_review = true`. La afirmación puede estar desactualizada, y el sistema no decide cuál documento rige.
- **Se mantienen:**
  - la regla de C4: citar una modificación o aclaración escala;
  - las raíces originales de C3 B4.
- **Se quitan** las raíces que C6 añadió y escalan de más en texto honesto (A5): `anterior`, `no aplica`, `regir`/`rige` y `actualizad`. Esos casos los cubre ahora la regla estructural.
- **Pruebas:**
  - las 14 frases de `c6_vigencia.py`, con 00047 y 00009 en la evidencia y solo 00047 citado, escalan;
  - los casos 29 y 30 de `c6_falsos.py`, en un evento sin modificaciones en la evidencia, no escalan.

### A1 y A4 (alta y baja): entre marcadores, por defecto el tramo debe estar en la cita

- **Regla:** el texto entre dos marcadores consecutivos de la misma afirmación debe aparecer, junto con los dos literales, seguido en la cita. Se compara con NFKC, sin distinguir mayúsculas y con la normalización de siempre.
- **Únicas excepciones**, para listas y rangos honestos: un texto intermedio que, tras NFKC y en minúsculas, sea exactamente uno de `, `, ` y `, ` o `, ` ni `, ` a `, ` al `, `, y ` o ` y el `.
- **Deben rechazarse:**
  - `{1} DE {2} DE {3}` y `{1} ｄｅ {2}`;
  - `día {1} del mes de {2}`;
  - `{1} ({2})`;
  - `{1}: {2}`;
  - `{1} De {2}, A LAS {3}`.
- **Deben pasar:**
  - los casos 17, 19, 20, 21 y 23 de `c6_falsos.py`;
  - `artículos {1}, {2}` con "65" y "69";
  - `{1}, a las {2}` cuando la cita dice exactamente eso.

### A2 (media): unidades con NFKC y sin distinguir mayúsculas

- La comprobación de unidades se hace sobre el texto con NFKC y en minúsculas.
- `Q`, `Q.`, `GTQ` y `US$` cuentan antes del marcador con cualquier espacio en medio.
- **La lista se amplía con:**
  - plazos: semana, semanas, trimestre, trimestres, semestre, semestres, quincena, quincenas;
  - cantidades y montos: millón, millones, mil, centavo, centavos;
  - masa: gramo, gramos, miligramo, miligramos, microgramo, microgramos, mcg;
  - presentaciones: tableta, tabletas, frasco, frascos, ampolla, ampollas;
  - medida: litro, litros, cc.
- **Riesgo residual declarado:** la lista sigue siendo cerrada. Requiere inyección, y lo cubre la revisión humana de fidelidad.

### A6 y A7 (baja): letras que parecen dígitos, sin rechazar siglas

- **Se rechaza:**
  - una palabra que contiene una `l` minúscula junto a `O`, `I`, `S`, `Z` o `B` en mayúscula ("lO", "lOO", "lS");
  - una secuencia de letras sueltas de ese conjunto unidas por `.`, `,` o `/` ("l.S", "l,S", "l/Z", "S.O").
- **Deja de rechazarse:** palabras solo en mayúsculas como "SI", "ISO", "OS" o "III".
- **Pruebas:** los seis casos de A6 se rechazan; "SI EL OFERENTE ..." e "ISO {1}" publican.
- **Mensaje de regeneración:** nombra este caso.

### A8 (baja): separador numérico por categoría, no por lista

- **Regla:** cualquier carácter que no sea letra, dígito ni espacio, puesto en el borde de la cita o del literal, con un dígito del otro lado en el fragmento, da `cita_no_literal` o `dato_no_literal`.
- **Prueba:** los nueve separadores de A8 se rechazan, y siguen pasando las citas que terminan en `)` o `.` seguido de espacio.

### A9 (baja): publicar desde el original también en `comparar_versiones`

- El mapa de originales se arma con `resultado.fragmentos` y también con los fragmentos de `documentos[]`.
- **Prueba:** el caso P1 de `c6_ataques.py` publica "<5%" y "<3%".

## Riesgos que siguen declarados

- N5: miles separados por espacio.
- Meses partidos con espacios.
- Cifras escritas con letras.
- N9: el modelo copia el prompt.
- La lista de unidades.
- Las URL y los correos en el texto, que se rechazan.

## Criterios de aceptación

- `make test-consulta` en verde.
- `c6_falsos.py`: los 30 casos publican. Solo escalan los que deben escalar: modificación citada, modificación en la evidencia y la "vigencia" de los seguros.
- `c6_barrido.py`: publica 932 de 932.
- Los ataques de `c6_cierre.py`, `c6_ataques.py` y `c6_vigencia.py` se rechazan o escalan.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo con su prueba;
- la salida resumida de los scripts `c6_*.py`;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
