# Avisos del rol 3 para el rol 1

**Estado al 18 de noviembre de 2026**, con lo hecho en R1 a R7 marcado. Lo que de ingesta afecta directamente a consulta. Ya figura en [Pendientes_rol_1](Pendientes_rol_1.md); aquí solo se explica el efecto en el rol 3.

- [x] **OCR de las páginas 3 y 4 de la Modificación 1 del evento 222.** Es el caso de demostración de comparación de versiones. Sin esas páginas, la respuesta sale con `coverage_status = "parcial"` y una advertencia; con ellas, la comparación es completa. Por defecto: la demo se hace con la advertencia. Hecho en R1 (`4bd2d7f`): la página 3 aporta fragmentos y la 4 sigue sin indexar; la respuesta sale con `coverage_status = "parcial"` y el aviso, y el anexo de 11 hojas no está publicado.
- [x] **`seccion` con pie de página (`Extensión: 99175`).** Rompe la detección de conflictos del rol 2 y la cita del rol 3 muestra una sección sin sentido. Por defecto: el rol 3 muestra la página como referencia principal y la sección solo si empieza por un numeral. Hecho en R6 (`7c117d9`).
- [x] **`seccion` mezclada en páginas a dos columnas.** En el cronograma del 222 (bases p. 8-9 y modificación p. 1-2), la sección mezcla las dos columnas o queda desfasada. Estado: hecho en R3 (`87c5d90`) y R5 (`7b1a31f`): tablas por celdas y secciones de las modificaciones. Las fechas del cronograma de tablas ya no dependen de JEV, sino de reglas (F7b y F7c).
  - un fragmento tiene la sección "2.2.1 hasta el día 31 de julio de 2023.", que trae la fecha dentro de la sección;
  - la solvencia patronal de la modificación queda bajo "2.2.8 Plazo para adjudicar";
  - la recepción de ofertas queda bajo "2.2.5".

  Eso confunde a `extraer_requisitos` cuando le pide a JEV la actividad de cada fecha. Por defecto: el rol 3 envía la sección como pista y exige un respaldo de JEV de al menos 0.7, de modo que una fecha mal asignada queda no verificada y pide revisión humana.
- [ ] **Diagrama de ingesta (opcional).** Si el rol 1 quiere un diagrama detallado de su flujo, puede seguir el formato de `docs/arquitectura/diagramas/` (HTML exportado a PNG). Por defecto: el diagrama general cubre la ingesta en un carril.
- [x] **`tabla_markdown` vacío.** Las tablas llegan con celdas partidas; el rol 3 no puede extraer requisitos fiables de ellas. Por defecto: `extraer_requisitos` trabaja con el texto y reporta `warnings` cuando un requisito proviene de una tabla. Hecho en R3 (`87c5d90`).
