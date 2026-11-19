# D3: diagramas vigentes y preparación del cierre

19 de noviembre de 2026. Autorizado por el usuario: aplicar la revisión de diagramas sobre sus HTML, conservar el estilo, regenerar imágenes y actualizar el estado para preparar video e informe y demás entregables.

## Diseño y alcance

- Conservar `fuente/estilos.css` y `fuente/diagrama.js` sin cambios: mismas formas, colores, tipografía, insignias, leyenda y reglas geométricas. Modificar textos, nodos, rutas y posiciones declaradas en los dos HTML. Ampliar el lienzo solo si lo exige la legibilidad, sin reducir fuentes.
- Actualizar implementación de autenticación, auditoría, LLM y lista. Separar experimentos JEV de la ruta por defecto con reglas. Representar propuesta de lista independiente, confirmación, autenticación, regeneración acotada y publicación parcial. El informe de revisión es la evidencia de partida.
- Sin nuevas funcionalidades del producto ni cambios en resultados medidos. No repetir el banco de evaluación para mejorar cifras ni declarar cerradas métricas humanas sin medir.
- Sin commits, push ni publicación. Preservar cambios locales previos. No leer credenciales ni archivos de `keys/`.
- Revisar los entregables ya existentes antes de crear otros: el repositorio contiene guion y diapositivas, pese al estado antiguo de Pendientes.md.

## Plan de ejecución

- [ ] Agente de diseño: actualizar únicamente `fuente/arquitectura_general.html` y verificar su geometría.
- [ ] Agente de diseño: actualizar únicamente `fuente/flujo_consulta.html` y verificar su geometría.
- [ ] Gestor: contrastar requisitos del curso, reconciliar README de diagramas y pendientes/planes con evidencia vigente.
- [ ] Gestor: regenerar los dos PNG con el exportador existente; comprobar que CSS y motor permanecen iguales e inspeccionar imágenes.
- [ ] Revisor independiente: contrastar diagramas finales con código, estilo anterior y encargo; emitir PASS/HOLD.
- [ ] Sincronizar informe y material de presentación, generar artefactos que permitan preparar la entrega y verificar número de páginas/diapositivas y referencias.
- [ ] Ejecutar verificaciones pertinentes y producir una lista de cierre que distinga listo, pendiente humano y limitación declarada.

## Criterio de cierre

La actualización documental se cierra al pasar verificaciones y revisión. El proyecto no se declara entregado por generar archivos: grabación, aceptación académica, datos del equipo y mediciones no realizadas se enumeran con su estado real.

## Confirmación académica

El usuario confirmó el 19/11/2026 que el docente autoriza video en lugar de presentación en vivo, con límite de 15 minutos. Fecha de entrega: 19/11/2026. La demostración funcional corresponde a la web del proyecto. No se requiere otra confirmación sobre esta modalidad.

## Estilo conservado

SHA-256 antes del cambio: `estilos.css` = `88ed24923aa3f812a2d47dc06d89b2ea8207fcd9ac43cd24b0274cf26358adb5`; `diagrama.js` = `c5328f0f0a3f5c8a836a3d09fa3f9016b38fed78c96fc2108b0268de5e502478`.
