# Encargo R6: pies de página con número y entradas del índice

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [R5](R5_modificaciones_y_margenes.md);
- `src/licigt/ingesta/pipeline.py`:
  - `HEADING`;
  - `_without_repeated_margins`;
  - `_units`;
  - `make_chunks`;
- `reproducir.py` y `migrar_ids.py`, con sus pruebas;
- la muestra revisada en `data/consulta/agentes/muestra_ingesta.json`.

## Medido (muestreo del 18 de noviembre, paquete R5)

Un revisor independiente comparó 30 fragmentos con la página del PDF.

- **Página:** 30 de 30 correctas.
- **Fidelidad:**
  - 16 exactas;
  - 11 con un pie de página pegado;
  - 3 graves: la tabla 4.1 del 222 y dos de OCR, que quedan fuera de este encargo.
- **Sección:** 23 de 30 correctas.

**Medido en todo el corpus (893 fragmentos):**

- 177 tienen como sección un pie del tipo "9 Extensión: 99175" o "PBX: 2412…". Están en los documentos `418241`, `f1cb15` y `70a60c`.
- 98 contienen solo ese pie.
- 110 contienen un pie dentro del texto.
- 36 son entradas sueltas del índice ("1. TERMINOLOGÍA", "4. ESPECIFICACIONES TÉCNICAS"), de páginas de contenido.

**Por qué pasa:**

- `_without_repeated_margins` cuenta las líneas idénticas entre páginas. El pie lleva el número de página, así que nunca se repite igual.
- Como empieza por un número, `HEADING` lo toma como título y lo arrastra como sección a los fragmentos siguientes.

**Por qué importa:**

- La sección decide la revisión acotada (C17), el carácter y la categoría de la lista, y se muestra en el prompt.
- Ejemplos de la muestra: `418241…:00087` y `f1cb15…:00063` son literales del 2.7 y tienen como sección un pie.

## Decisión del gestor (cinco porqués, autorizado por el usuario: "sigue con el rol 1")

Se corrigen la detección de márgenes y el índice.

**Fuera de alcance, se declaran como limitación:**

- la tabla 4.1 del 222, con encabezados de varias líneas;
- los errores de OCR de la página 3 de la modificación ("1GSS").

## Archivos

Solo `src/licigt/ingesta` y sus pruebas.

## Cambios (prueba en rojo primero)

### 1. Márgenes con número

- En `_without_repeated_margins`, al contar repeticiones, cada línea candidata se compara con los dígitos enmascarados y los espacios colapsados. Por ejemplo, "9 Extensión: 99175" y "25 Extensión: 99175" cuentan como la misma línea.
- No cambian:
  - las posiciones (8 primeras y 6 últimas líneas);
  - los umbrales de R5;
  - la regla de los documentos cortos, donde una línea con `HEADING` nunca se quita.
- Se quita la línea original. Lo quitado sigue afectando solo al índice: el texto de las páginas se conserva.
- **Pruebas:**
  - sintética de 6 páginas con el pie "N Extensión: 99175", que se quita en todas;
  - una línea de contenido "2.2.1 …" que aparece en las primeras líneas de 2 páginas de un documento largo no se quita;
  - con el ZIP real:
    - 0 fragmentos con sección de pie;
    - 0 fragmentos que solo contienen un pie;
    - 0 fragmentos con "Extensión: 99175" o "PBX: 2412" en el texto, salvo los que lo tengan dentro de una oración de contenido. Reporta cuáles quedan.

### 2. Entradas del índice

- Dos o más unidades seguidas cuyo texto es solo su línea de título, sin cuerpo, se juntan en una sola unidad.
- Esa unidad lleva la sección que estaba vigente antes, no la de una de las entradas. La sección vigente después sigue siendo la que tenía antes de esas entradas.
- **Pruebas:**
  - sintética de una página de contenido con 6 títulos seguidos y luego un "1. TERMINOLOGÍA" con cuerpo en la página siguiente, que da 1 unidad de índice y la sección 1 correcta después;
  - con el ZIP real, 0 fragmentos de una sola entrada de índice en las páginas de contenido.

### 3. Lo que no debe cambiar

- La página de cada fragmento.
- El texto, salvo los pies quitados.
- Las secciones correctas de R5, en particular la modificación del 222, donde el "Punto 2" sigue con la sección 2.7.
- Las tablas de R3 y R4.
- Prueba: el número de dígitos de cada documento solo baja por los pies quitados. Repórtalo.

## Paquete candidato y migración

- Regenera el paquete sin red con `reproducir --desde-zip` y déjalo en `<scratchpad>/r6/empresa_demo_r6.zip`. **No reemplaces el ZIP del repo.**
- Escribe `equivalencias_r6.json` con todos los ids cuyo texto normalizado cambia, como en R5, y su prueba.
- Con `migrar_ids.py` en vista previa, informa qué ids citados en el repo cambian: pruebas, ejemplos de la web, documentos y `src/licigt/consulta/casos_banco.json`.
- Aplica la migración solo después de que el usuario copie el ZIP.

## Al terminar

Responde con:

- los archivos tocados;
- `make test-ingesta` (con `LICIGT_ZIP_CORPUS` apuntando al candidato) y `make test-consulta`;
- los conteos antes y después: sección de pie, fragmentos de solo pie, pies en el texto, entradas de índice y total de fragmentos;
- las secciones nuevas de los 7 fragmentos de la muestra que tenían la sección mal;
- los ids que cambian;
- el comando `cp` para el usuario.

## Reglas

- Sin `keys/` y sin git.
- Solo `src/licigt/ingesta`.
- Nada en la raíz del repo.
