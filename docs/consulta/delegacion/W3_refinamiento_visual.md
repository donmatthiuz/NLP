# W3: refinamiento visual de la web

Estado: diseño aprobado por el usuario con «aplicalo» el 19 de noviembre de 2026; implementado y verificado, con compuerta independiente PASS. Rama `proyecto`; sin commits ni push.

## Encargo y fundamento

El usuario solicita usar los agentes de diseño para modificar la web: favicon genérico, selectores y tarjetas consistentes, menos texto, información ordenada y animaciones/transiciones CSS. Se mejora la interfaz de consulta prometida en el anteproyecto y registrada en F6 del [plan del rol 3](../Plan_rol_3.md), sobre la base de W2.

Se consultaron los roles `design-ux-architect`, `design-ui-designer` y `design-visual-storyteller` con sus instrucciones de `.agentes/`. Sus observaciones proceden de lectura del código; todavía no constituyen una revisión en navegador.

## Enfoques considerados

- Refinar los componentes actuales: conserva React, Tailwind y shadcn/ui, reduce altura y mejora jerarquía sin cambiar el flujo. Recomendación del gestor y los agentes aprobada por el usuario.
- Rediseñar como panel con navegación lateral: añade estructura y cambia el recorrido de una herramienta de una sola página; no se justifica para este encargo.
- Plegar documentos y advertencias: reduce altura, pero oculta información necesaria para evaluar la evidencia; se descarta.

## Diseño propuesto

- Favicon SVG local: hoja blanca sobre fondo grafito, esquina doblada y dos trazos; legible a 16 px. Sin marca institucional ni símbolo de aprobación.
- Mantener una columna principal de 60rem. Cabecera compacta, con nombre y evento agrupados; sesión y tema a la derecha cuando caben, apilados en móvil.
- Mantener el orden documentos, consulta, aviso fijo, resultado, fuentes y lista. Compactar las tarjetas de documentos con una cabecera y metadatos agrupados, en dos columnas solo cuando quepan. Tipo, versiones, identificador completo, páginas, estado y advertencias siguen visibles.
- Consulta destacada con título breve. Selector de ejemplo de ancho acotado en escritorio y completo en móvil; tema compacto. Conservar selectores nativos, etiquetas visibles, teclado del sistema y objetivos de al menos 44 px.
- Unificar espaciado y anatomía de tarjetas: cabecera, contenido y acciones. Las tarjetas informativas no simulan botones al pasar el cursor. Las fuentes en conflicto conservan igual peso y todas sus referencias.
- Lista con acciones agrupadas en su cabecera y metadatos ordenados. Estados con borde de grosor constante para que la selección no cambie sus dimensiones.
- Recortar texto auxiliar: ayuda inicial a «La respuesta aparecerá aquí con sus fuentes» y lista vacía a «Proponga una lista para comenzar. Solo se guarda al confirmar». No reescribir respuestas, citas ni advertencias recibidas.
- Transiciones de color, fondo y borde de 150 ms en controles. Apertura del diálogo de confirmación de 160 ms con desplazamiento máximo de 4 px, sin retrasar su disponibilidad ni alterar el foco. Sin animaciones de entrada sobre resultados o advertencias. Todos los efectos se anulan con `prefers-reduced-motion: reduce`.
- Conservar la paleta clara y oscura existente y el foco visible. Actualizar `web/DISENO.md` para permitir explícitamente la animación acotada del diálogo.

```text
LiciGT · Evento 222-IGSS-2023                Tema [Sistema]

Documentos del evento                    resumen de cobertura
[Tipo y versión | metadatos compactos | advertencias visibles]

Consulta                                  Ejemplo [selección]
[Pregunta sobre el evento                                    ]
                                             0/500 [Consultar]
Aviso fijo sobre los documentos cargados

[Estado | respuesta | cobertura y advertencias]
Fuentes
[Documento y versiones | cita literal | enlaces]

Lista de verificación                     [Proponer] [Guardar]
Aviso de no certificación
[Categoría | cita | metadatos | estados]
```

## Cinco porqués e inventario de impacto

- Compactar porque todas las tarjetas documentales preceden a la consulta (`web/src/App.tsx:156`).
- Agrupar metadatos porque documentos e ítems reparten datos relacionados en varias líneas y frases extensas (`DocumentosEvento.tsx:38`, `ListaVerificacion.tsx:78`).
- Conservar evidencia abierta porque citas y advertencias completas forman parte de `web/DISENO.md`, apartados de fuentes y cobertura.
- Mantener selectores nativos porque ya tienen etiquetas y altura de 44 px (`ui/native-select.tsx:7`); no se ha reproducido un fallo funcional que exija reemplazarlos.
- Actualizar y verificar el contrato porque fija orden, movimiento y accesibilidad; el [flujo del rol 3](../Flujo_de_trabajo.md) exige visto bueno y compuerta visual.

Archivos previstos: `web/index.html`, nuevo `web/public/favicon.svg`, `App.tsx`, componentes de documentos, fuentes, lista, tema y confirmación; primitivas `card`, `native-select` y radios cuando corresponda; `tema.css`, `web/DISENO.md` y registro en el plan del rol 3. Los datos siguen entrando por los contratos existentes; no se modifican backend, autenticación ni peticiones.

## Límites y aceptación

- Citas, identificadores, versiones, páginas, texto documental y warnings íntegros. Avisos de cobertura, abstención, revisión y no certificación visibles. Guardado solo tras confirmación explícita.
- Sin dependencias nuevas, fuentes remotas ni imágenes generadas. No leer `keys/`.
- Consultar documentación actual con Context7 antes de escribir código contra las librerías utilizadas.
- Ejecutar pruebas web y compilación. Base medida antes del cambio: 80 pruebas aprobadas en seis archivos; compilación aprobada.
- Revisar en navegador cinco ejemplos, estado inicial, lista y diálogo; claro y oscuro; 320, 768 y 1366 px; teclado, foco, selectores largos, movimiento reducido y ausencia de desbordamiento horizontal.
- `design-ui-finish-gate-reviewer` debe revisar la implementación en vivo y emitir PASS o HOLD. W3 obtuvo PASS; evidencia y límites en [W3_verificacion](W3_verificacion.md).
- Ejecución completada según [W3_plan](W3_plan.md): agentes de diseño, integración, contrato actualizado y verificación del gestor.

## Consulta de documentación

Context7 se intentó con el CLI fuera del sandbox. Rechazó la credencial configurada con `Invalid API key`, también al retirar la variable `CONTEXT7_API_KEY` del proceso. No se leyeron secretos. Se informó al usuario y se verificó la documentación oficial como alternativa: [transiciones](https://tailwindcss.com/docs/transition-property), [animaciones y movimiento reducido](https://tailwindcss.com/docs/animation) y [diseño adaptable](https://tailwindcss.com/docs/responsive-design). No se cambian APIs React/Radix ni dependencias.
