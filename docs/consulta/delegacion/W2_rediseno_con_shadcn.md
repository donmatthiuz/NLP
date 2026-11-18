# Encargo W2: rediseño de la web con shadcn/ui

Rama `proyecto`. No commitees.

## Decisión del usuario (18 de noviembre)

Adoptar **shadcn/ui** (Radix más Tailwind v4) como base estándar de la interfaz, con los agentes de diseño.

El usuario pidió:

- cursor de mano en todo lo que se puede pulsar;
- una vista mejor;
- partir de un estándar en vez de CSS propio.

## Lee primero

- [`AGENTS.md`](../../../AGENTS.md);
- [`web/DISENO.md`](../../../web/DISENO.md): su contenido (estados, avisos, fuentes en conflicto, lista, contraste, 320 px, claro y oscuro, foco) se mantiene; cambia la implementación;
- `web/src` completo, las pruebas de Vitest, `web/package.json` y `web/vite.config.ts`;
- la documentación actual de shadcn/ui, de Tailwind v4 con Vite y de Radix, **con Context7** (herramientas `mcp__context7__*`), antes de instalar o escribir nada.

## Lo que no cambia

- Los estados del resultado, cómo se distinguen sin depender del color, los textos de abstención, revisión, aclaración y cobertura, y la regla de que el sistema no decide la vigencia.
- La lógica de `api.ts`, `estado.ts`, `cobertura.ts` y `lista.ts`, con sus pruebas (puedes ajustar las de render si cambian las etiquetas, sin debilitarlas).
- Sesión, rol `lector`, 401 y 403, el modo ejemplos y la copia archivada (W1).
- Contraste de al menos 4.5:1 para el texto, sin desborde horizontal a 320 px, foco visible y `prefers-reduced-motion`.

## Fase A: UX Architect (base)

- **Instalación:** Tailwind v4 y shadcn/ui en `web/`, con **pnpm** (`pnpm dlx shadcn@latest ...`, nunca npm ni npx), con alias e importaciones según la documentación vigente.
- **Tema:**
  - los tokens actuales de `base.css` (`--color-*`, espacios y bordes) pasan a las variables de tema de shadcn, en claro y oscuro;
  - el selector de tema (Sistema, Claro, Oscuro) sigue funcionando.
- **Componentes:** solo los que se usan (Button, Input, Label, Card, Badge, Alert, RadioGroup, Separator y, si hace falta, Tooltip).
- **Mapa:** de cada componente nuestro a los de shadcn.
- **Reglas de interacción:**
  - cursor de mano en lo que se pulsa y `not-allowed` en lo deshabilitado;
  - estados `hover`, `focus-visible`, `active` y `disabled`.
- **`DISENO.md`:** se actualiza con la base nueva (tema, mapa y reglas de interacción) sin perder ninguna regla de contenido.

## Fase B: UI Designer (migración)

- Migra `App`, `InicioSesion`, `Resultado`, `Fuentes`, `DocumentosEvento`, `ListaVerificacion`, `Confirmacion` y `Tema` a los componentes de la fase A.
- **Mejora visual dentro del contrato:**
  - jerarquía clara;
  - tarjetas de fuente legibles, con la cita destacada;
  - el contraste lado a lado de las fuentes en conflicto;
  - la lista agrupada y escaneable.
- **Página impresa:** cada fuente muestra "p. N del PDF" y, si la respuesta trae `printed_page` (opcional; el backend lo agrega aparte), "(impresa M)". El enlace "Ver copia archivada" sigue usando la página del PDF.
- Lo que quede sin usar de `base.css` se borra.

## Criterios de aceptación

- `pnpm --dir web test` y `pnpm --dir web build` en verde.
- Compuerta de diseño (`design-ui-finish-gate-reviewer`) en PASS, en vivo, en claro y oscuro, a 1366 y 320 px.

## Reglas

- Solo `web/` y este contrato.
- No toques el backend ni `keys/`.
- Usa pnpm.
