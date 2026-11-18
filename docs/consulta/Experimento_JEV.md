# Experimento de JEV en el enrutador

Parte 2 de [F7](delegacion/F7_pruebas_y_jev.md). Este documento registra lo medido; las corridas con JEV en vivo se agregan cuando el usuario las ejecute.

## Conjunto de prueba (17 de noviembre de 2026)

Congelado en `src/licigt/consulta/casos_enrutador.json`: 60 casos, 12 por clase (`buscar_documentos`, `extraer_requisitos`, `comparar_versiones`, `aclarar` y `abstener`).

### Quién redactó y quién revisó

- **Proponente (40 casos, sin trampa):** `proponente-casos` en Codex, con `codex exec -s read-only --ephemeral`.
- **Adversario (20 casos engañosos):** `adversario` en OpenCode con `opencode/deepseek-v4.1-flash-free`.
  - F7 pedía Kimi. No hubo acceso: Copilot no ofrece Kimi K3, OpenCode Go llegó a su límite mensual, y OpenRouter y Hugging Face no tenían saldo.
  - El usuario autorizó un modelo gratuito de OpenCode. DeepSeek es de otra familia que el proponente (OpenAI) y el revisor (Claude).
- **Revisor a ciegas:** `revisor-casos` con `claude -p`, en sesión aislada, sobre `ciego_enrutador.json` (solo `id`, `evento` y pregunta).
  - Leyó la guía, el archivo ciego y las preguntas de desarrollo (`casos_desarrollo.json` y `CASOS_ADICIONALES`), que su definición le pide para detectar duplicados. No leyó las etiquetas del proponente ni del adversario (verificado en el registro de su sesión).

### Acuerdo

- **Primera revisión:** 100 % sobre 60, kappa 1,000, sin desacuerdos.
  - El revisor marcó 7 casos como paráfrasis de desarrollo. El usuario decidió reemplazarlos.
  - El proponente redactó 5 y el adversario 2, en las mismas clases, con una lista de preguntas y temas que evitar (`evitar_reemplazo.txt`, sin preguntas de desarrollo ni etiquetas).
- **Segunda revisión, en sesión nueva, sobre los 60:** 100 %, kappa 1,000, sin desacuerdos.
  - Marcó 12 casos distintos como paráfrasis de desarrollo, entre ellos uno de los reemplazos. En la primera revisión esos 12 estaban limpios.
  - La marca no es estable entre corridas: en clases estrechas (inyección, aclarar una fecha) casi cualquier pregunta se parece a una de desarrollo.
- **Decisión del usuario:** congelar los 60. Cada caso guarda las marcas del revisor en `marcas_revisor`, y McNemar se reporta con los 60 y sin los 12 marcados como `duplica_desarrollo`.
- **Lectura del acuerdo:** un kappa de 1,000 dice que la guía es clara para estos casos, no que las etiquetas sean correctas. Los dos agentes etiquetan contra la misma guía.

### Conjunto de desarrollo

- Las 47 preguntas (27 de `casos_desarrollo.json` y 20 de `CASOS_ADICIONALES`) se etiquetaron con el mismo revisor a ciegas: 33 con confianza alta, 9 media y 5 baja.
- Las 5 de confianza baja son la pregunta del seguro de caución en cada evento. El usuario confirmó `buscar_documentos`.
- Las etiquetas viven en `data/consulta/agentes/etiquetas_desarrollo.json`, fuera del repositorio.

### Huecos de la guía que señaló el revisor

- No define `risk_level` ni `answerable` para el enrutador.
- No dice qué prevalece cuando una pregunta pide listar lo que cambió entre versiones (`extraer_requisitos` o `comparar_versiones`).
- No dice si el lugar de recepción "según el cronograma" va a `extraer_requisitos` o a `buscar_documentos`, ni si un plazo que no es actividad del cronograma (el de entrega) es fecha o dato.

## Corridas con JEV

Pendientes. Las ejecuta el usuario: `make experimento-jev CONJUNTO=desarrollo`, luego con `CONFIRMAR=1`, la rejilla y una sola corrida de prueba.
