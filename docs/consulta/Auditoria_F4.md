# Auditoría adversaria de la generación con citas (F4)

**Estado al 17 de noviembre de 2026.** Resume las siete pasadas del agente `adversario` sobre la generación y el validador del rol 3 (`src/licigt/consulta/generacion.py`, `validacion.py` y `orquestador.py`). Sirve de base para las secciones "auditoría de seguridad" y "limitaciones operativas" del informe (instrucciones del curso, entregable 1). Las reglas que se auditan están en [`AGENTS.md`](../../AGENTS.md#reglas-que-no-se-negocian).

## Método

- **Agentes:** implementó un modelo (Sonnet) y auditó otro (Opus o Kimi), con el agente de solo lectura `.agentes/adversario.md`. El gestor reprodujo los hallazgos graves antes de encargar cada corrección.
- **Contra qué:** cada pasada intenta refutar la entrega frente a su encargo y frente a `AGENTS.md`, con scripts que no usan red. Usa los 1006 fragmentos reales del paquete `entregables/recuperacion/empresa_demo.zip`.
- **Cómo se clasifica cada hallazgo:**
  - si requiere inyección en un PDF oficial o si lo produce un modelo honesto que sigue el prompt;
  - además, se cuentan los falsos rechazos, porque un validador que rechaza respuestas buenas deja el sistema en abstención.

## Pasadas

| Pasada | Encargo | Hallazgos | Severidad máxima | Qué cambió |
|---|---|---|---|---|
| 1 | [C2](delegacion/C2_correcciones_F4.md) | A1 a A8 | Alta | Fecha de otro mes publicada con cita válida; delimitadores del prompt reconstruibles |
| 2 | [C3](delegacion/C3_correcciones_F4_segunda.md) | B1 a B8 | Alta | Meses abreviados, miles con espacio, fecha armada con dos citas |
| 3 | [C4](delegacion/C4_datos_literales_F4.md) | H1 a H8 | Alta | Cambio de diseño: **seleccionar, no generar** (datos literales copiados de una cita) |
| 4 | [C5](delegacion/C5_composicion_F4.md) | N1 a N9 | Alta | Se valida la línea armada; marcadores aislados; lista blanca de caracteres |
| 5 | [C6](delegacion/C6_cierre_F4.md) | H-A1 a H-A8 | Alta (con inyección) | Marcadores compuestos, unidades, vigencia ampliada |
| 6 | [C7](delegacion/C7_reglas_cerradas_F4.md) | A1 a A9 | Alta (con inyección) | Las listas cerradas pasan a reglas que fallan cerrado; vigencia por la evidencia |
| 7 | [C8](delegacion/C8_ultimos_bajos_F4.md) | H1 a H4 | Baja | Signos con diacrítico como separador, vigencia con cualquier tipo de documento |

## Lecciones de diseño

- **Analizar datos escritos por el modelo no converge.** Tres rondas de parches al analizador de fechas y cifras abrieron variantes nuevas cada vez: formatos, caracteres invisibles, homoglifos. Ninguna lista de formatos es completa.
- **Seleccionar en vez de generar sí converge.** Es el mismo principio que F3b aplica con JEV. El modelo marca cada dato como `{n}` y lo copia literal de una sola cita, y el código lo inserta. Así, el texto que lee el usuario lleva el dato tal como está en el documento.
- **Las listas de lo prohibido abren huecos y además rechazan texto honesto.** En C7 se invirtieron: por defecto se exige que el tramo esté en la cita, y las excepciones permitidas son pocas y explícitas.
- **La vigencia no se detecta por palabras.** Se escala por la estructura de la evidencia: si trae una modificación o aclaración y la respuesta cita otro tipo de documento, pide revisión humana.

## Resultado medido (séptima pasada, antes de C8)

- `make test-consulta`: 313 pruebas en verde, con 1 fallo esperado (N5, declarado).
- Barrido de una cita honesta con un número por cada fragmento con cifras: 932 de 932 se publican.
- Afirmaciones honestas redactadas como lo haría un modelo de 9B: 30 de 30 publican en la sexta pasada (eventos 222 y 368) y 30 de 30 en la séptima (399, 363 y 327).
- Deslices honestos que el prompt desaconseja (por ejemplo, "el {1} a las {2}" sin la coma de la cita): 7 rechazados, que pasan a la única regeneración. **Hace falta medirlo con el LLM real** (`make llm-servidor` y el banco de F7).

## Cierre (C8)

- `make test-consulta`: 317 pruebas en verde, con 1 fallo esperado (N5).
- `c5_falsos`, `c6_falsos` y `c7_falsos`: publican 15 de 15, 30 de 30 y 30 de 30, sin rechazos.
- `c6_barrido`: publica 932 de 932.
- H1 a H4 de la séptima pasada quedaron rechazados o escalados.
- F4 se da por cerrada. Los riesgos que quedan están declarados abajo.

## Riesgos residuales declarados

Todos requieren inyección en un PDF oficial del IGSS o son latentes: no aparecen en el corpus actual. Tres defensas los acotan:

- el escaneo de instrucciones sospechosas de la ingesta;
- el tratamiento de los fragmentos como datos no confiables;
- la revisión humana de fidelidad (anteproyecto, línea 376).

| Riesgo | Por qué queda |
|---|---|
| Miles separados por espacio ("Q1 000" sacado de "Q1 000 000") | Indistinguible de dos números; 0 casos en el corpus |
| Meses partidos con espacios o guiones ("oc tubre") | Requiere inyección y deja texto visiblemente roto |
| Cifras escritas con letras ("ciento veinte") | Paráfrasis semántica; la revisa una persona |
| Lista de unidades cerrada (incluye monedas escritas con palabras antes del dato: "quetzales {1}", "USD {1}") | Una unidad fuera de la lista pegada a un literal requiere inyección |
| Mayúsculas que parecen cifras fuera de I y O ("ZOO", "SOO") | Requiere inyección; ampliar el conjunto rechazaría siglas honestas |
| Conector de contenido inventado entre literales fieles ("{1} hasta el año {2}") | Los datos sí están en la cita; el sentido lo revisa una persona |
| Uniones permitidas que cambian el sentido ("del {1} y {2}" para un rango) | Fidelidad semántica, sin dato falso de forma |
| El modelo copia el prompt del sistema | El prompt no contiene secretos |
| Exceso de escalamiento por la palabra "vigencia" en seguros | Escala del lado seguro |
| URL y correos en el texto | Se rechazan; el modelo debe citarlos como literal |
| Una cita de 500 caracteres puede traer otra fecha del mismo fragmento (H3, riesgo de la octava pasada) | Con el paquete nuevo (tablas contiguas) 7 de 890 fragmentos tienen dos fechas distintas a 500 caracteres o menos (con el paquete anterior era 1 de 1006), medido con `encontrar_fechas`; 6 son tablas (cronograma o parámetros) y 1 es texto OCR de la modificación 1. Un dato literal sigue exigiendo que la fecha esté en la cita y la afirmación la cita completa; el sentido lo revisa una persona |

## Pendiente

- Medir con el LLM local la tasa de regeneraciones y abstenciones por `dato_fuera_de_literal` y `dato_no_literal`. El prompt actual es `f4-v6`.
- Volver públicas las funciones que `lista.py` y `lista_escritura.py` importan como privadas (`_ejecutar`, `_original`).
