# Encargo R4: orden de las palabras en las tablas (novena pasada, H1)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [R3](R3_tablas_dos_columnas.md);
- `src/licigt/ingesta/pdf.py` (`_con_tablas`, la salvaguarda por multiconjunto y la condición `len(filas) == 1 and efectivas >= 3` en la línea 201) y `pipeline.py`, con sus pruebas;
- en el scratchpad del gestor, `c9_ataques.py` (sección S2) y `c9_lista.py` (`fila_225`).

## Hallazgo

R3 trata como tabla de una fila el párrafo numerado 2.25 "VIGENCIA DEL CONTRATO", sangrado en dos columnas, en los 5 eventos. Las palabras de cada celda quedan desordenadas: "a partir del día Resolución de aprobación del CONTRATO, hasta UNIDAD SOLICITANTE extienda…", cuando el original dice "a partir del día siguiente de la notificación de la Resolución…".

La salvaguarda solo compara el multiconjunto de palabras, así que no lo detecta. El validador y la lista publican el texto desordenado como si fuera literal.

## Cambios (prueba en rojo primero)

1. **Orden dentro de cada celda:** las palabras de cada celda deben conservar el orden de lectura del texto actual de la región, restringido a la franja de esa columna. Si una celda no lo cumple, toda la tabla vuelve al texto actual. La salvaguarda pasa a comprobar el multiconjunto **y** el orden por celda.
2. **Tabla de una fila:** no se reescribe, salvo que su primera celda sea un numeral o literal y las otras celdas cumplan el orden del punto 1. Si hay duda, se deja el texto actual.
3. **Pruebas:**
   - un PDF sintético con un párrafo numerado sangrado en dos columnas, cuyas palabras deben conservar el orden;
   - con el ZIP real en memoria, el fragmento del 2.25 de los 5 eventos contiene "día siguiente de la notificación de la Resolución";
   - el cronograma sigue con sus filas unidas;
   - ningún dígito cambia.

## Paquete candidato

- Regenera el candidato sin red con `reproducir --desde-zip` y déjalo en `<scratchpad>/r4/empresa_demo_r4.zip`. **No reemplaces el ZIP del repo.**
- Actualiza `equivalencias_r3.json`, o crea `equivalencias_r4.json`, para los ids que cambien. Usa `migrar_ids.py` en vista previa sobre las pruebas, los ejemplos de la web y los documentos.
- Informa qué ids citados en el repo cambian.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados de `make test-ingesta` (con `LICIGT_ZIP_CORPUS` apuntando al candidato) y de `make test-consulta`;
- el texto del 2.25 antes y después;
- los ids que cambian;
- el comando `cp` para el usuario.

## Reglas

Sin `keys/`, sin git. Solo `src/licigt/ingesta`.
