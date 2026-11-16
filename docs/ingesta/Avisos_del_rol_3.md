# Avisos del rol 3 para el rol 1

**Estado al 16 de noviembre de 2026.** Lo que de ingesta afecta directamente a consulta. Ya figura en [Pendientes_rol_1](Pendientes_rol_1.md); aquí solo se explica el efecto en el rol 3.

- [ ] **OCR de las páginas 3 y 4 de la Modificación 1 del evento 222.** Es el caso de demostración de comparación de versiones. Sin esas páginas, la respuesta sale con `coverage_status = "parcial"` y una advertencia; con ellas, la comparación es completa. Por defecto: la demo se hace con la advertencia.
- [ ] **`seccion` con pie de página (`Extensión: 99175`).** Rompe la detección de conflictos del rol 2 y la cita del rol 3 muestra una sección sin sentido. Por defecto: el rol 3 muestra la página como referencia principal y la sección solo si empieza por un numeral.
- [ ] **Diagrama de ingesta (opcional).** Si el rol 1 quiere un diagrama detallado de su flujo, puede seguir el formato de `docs/arquitectura/diagramas/` (HTML exportado a PNG). Por defecto: el diagrama general cubre la ingesta en un carril.
- [ ] **`tabla_markdown` vacío.** Las tablas llegan con celdas partidas; el rol 3 no puede extraer requisitos fiables de ellas. Por defecto: `extraer_requisitos` trabaja con el texto y reporta `warnings` cuando un requisito proviene de una tabla.
