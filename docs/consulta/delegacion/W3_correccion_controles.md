# W3: corrección de controles y cabecera

19 de noviembre de 2026. Corrección solicitada por el usuario tras revisar W3: quitar el pie institucional, sustituir los selectores nativos y mejorar la distribución adaptable. La solicitud actual sustituye la decisión anterior de conservar `NativeSelect`. Cambios locales sobre `proyecto`, sin commit ni push.

## Diseño y fundamento

- El pie de `App.tsx` añade texto que el usuario pide retirar: eliminarlo completo.
- `Tema.tsx` usa un selector con etiqueta visible. Sustituirlo por un botón de 44 px con icono cambiante que alterne Claro y Oscuro, nombre accesible que anuncie estado y siguiente acción y título descriptivo. Conservar persistencia; cuando no existe preferencia, iniciar según el aspecto del sistema. El usuario precisó después que no quiere icono ni opción Sistema.
- El selector de ejemplos usa `NativeSelect`, cuyo menú lo dibuja el navegador. Usar `Select` de Radix ya instalado, con estilo del proyecto, etiqueta visible, teclado, foco y opciones de altura mínima 44 px. No instalar dependencias.
- Cabecera con marca y botón de tema en la primera fila; datos de sesión y cierre en una fila separada en móvil. Separación explícita entre zonas y controles; menú dentro del ancho y alto disponibles.
- El aviso de ejemplos es correcto: el modo evita la API y la sesión. Conservarlo, alineado con el contenedor de lectura. No simular una sesión ni ocultar que las respuestas son fijas.
- La alternativa de estilizar más el `select` nativo no satisface la corrección del usuario. Un rediseño de navegación excede esta corrección.

## Plan

- Agente `design-ui-designer`: leer su rol y el contrato; modificar `web/src/componentes/Tema.tsx`, `App.tsx` y añadir `ui/select.tsx`; ajustar espaciado de la cabecera y controles sin cambiar respuestas, evidencia, autenticación o guardado. Consultar documentación actual antes de implementar.
- Gestor: actualizar `web/DISENO.md`, registrar cambios y límites en este documento, `Plan_rol_3.md` y `Pendientes.md`.
- Verificar `pnpm --dir web test`, `pnpm --dir web build` y navegador en 320, 768 y 1366 px, claro/oscuro: cinco ejemplos, teclado del selector, alternancia/persistencia del tema, ausencia del pie, ausencia de desbordamiento. Comprobar cabecera con sesión simulada y cierre sin tocar una sesión real.
- Agente independiente `design-ui-finish-gate-reviewer`: inspeccionar implementación y capturas, emitir PASS o HOLD. Conservar resultados previos W3 como históricos.

## Verificación

Completada sobre la versión final Claro/Oscuro. La captura citada por el usuario no estaba disponible como archivo en esta sesión; se inspeccionó la interfaz servida localmente.

- `pnpm --dir web test`: 80 pruebas aprobadas en seis archivos.
- `pnpm --dir web build`: TypeScript y Vite aprobados.
- `git diff --check`: sin errores.
- Chromium: 30 resultados (cinco ejemplos, tres anchos 320/768/1366 y dos temas), sin desbordamiento horizontal ni errores JavaScript.
- Seis menús: teclado con Enter y flechas, Escape devuelve foco, opciones de 44 px y menú dentro del ancho disponible.
- Tema: sin icono de sistema, alternancia Claro/Oscuro, persistencia tras recarga y sincronización del icono con el sistema mientras no existe preferencia.
- Sesión simulada: cabecera en los tres anchos, petición DELETE y retorno al inicio de sesión, sin desbordamiento ni errores.
- Compuerta independiente `design-ui-finish-gate-reviewer`: PASS de controles/cabecera y PASS del ajuste posterior Claro/Oscuro, tras inspección de código y capturas.

Evidencia temporal: `/tmp/licigt-w3/correccion.cjs`, `correccion-report.json` y capturas `correccion-*.png`. Los intentos iniciales del script fallaron por captura que alteraba foco, esperas insuficientes para efectos de Radix y un doble de lista con objeto en vez del array del contrato; se corrigió el script, no el producto. La matriz final pasó completa.

Context7 consultado con éxito para Radix Select y la suscripción de React a cambios del navegador. No se instaló ninguna dependencia. No se ejercitó una sesión real, ni se volvió a medir contraste o lector de pantalla. La API de autenticación no cambió.

## Inventario documental comprobado

La pregunta posterior del usuario sobre dos frente a seis documentos se contrastó con `data/consulta/corpus/inventario.json`, los PDF locales y `entregables/recuperacion/empresa_demo.zip`: seis PDF en cinco eventos; 222-IGSS-2023 tiene bases y modificación 1, y 399-IGSS-2026, 363-IGSS-2026, 327-IGSS-2023 y 368-IGSS-2026 tienen uno cada uno. `EJEMPLO_DOCUMENTOS` contiene únicamente los dos del 222; el modo API también limita el inventario al evento solicitado y la empresa autenticada. La web fija el evento mediante configuración, sin selector de eventos. No se consultó la base de datos real.
