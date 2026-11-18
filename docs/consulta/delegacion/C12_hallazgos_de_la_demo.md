# Encargo C12: hallazgos de la demo real (F6e)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [`Demo_222.md`](../Demo_222.md), con su tabla de lo esperado frente a lo real;
- `herramientas.py` (`tema_comparacion`), `orquestador.py`, `validacion.py` (escalamiento por vigencia), `api.py` y `lista.py`;
- en `web/src/`: `componentes/Resultado.tsx` y `estado.ts`.

## Hallazgos

1. **"¿Qué cambió en el cronograma entre las bases y la modificación 1?" se abstiene.** `tema_comparacion` no quita "qué cambió en" ni el número tras "modificación", así que el rol 2 recibe la frase entera. Con "Compara la fecha de recepción de ofertas entre las bases y la modificación" la comparación responde bien.
2. **Una abstención sale con `needs_human_review=true`,** y la web muestra a la vez la banda "Las fuentes difieren" y la abstención sin fuentes.
3. **La respuesta devuelve el `evento_id` interno** (`69099f71…`) aunque la ruta pidió `222-IGSS-2023`.
4. **`POST /lista/propuesta` tarda 75 s y devuelve una abstención sin ítems** (`citas_no_validas`, `fechas_no_verificadas: 4`).

## Archivos

`herramientas.py`, `orquestador.py`, `api.py` y sus pruebas, más `web/src/` y Vitest. El hallazgo 4 es solo un diagnóstico.

## Cambios (prueba en rojo primero)

1. **`tema_comparacion` también quita:**
   - "qué cambió en", "qué cambia en" y "qué diferencias hay en";
   - el número o "Número N" que sigue a "modificación" o a "aclaración".

   **Prueba:** las tres formulaciones de C9 y la de la demo dan un tema corto ("cronograma" y "fecha de recepción de ofertas").
2. **Abstención y revisión humana:**
   - en una abstención, `needs_human_review` solo es verdadero si la herramienta trajo una alerta `posible_conflicto`; las reglas de vigencia del validador solo aplican a respuestas publicadas;
   - en la web, la banda de revisión dice "Requiere revisión humana" con su motivo. "Las fuentes difieren" solo aparece si hay fuentes de dos documentos o más.

   **Pruebas:** en Python y en Vitest.
3. **`evento_id` de la API:** la respuesta lleva el valor que pidió la ruta. El orquestador sigue trabajando con el id interno, y la API lo reemplaza al responder.

   **Prueba:** la respuesta a `222-IGSS-2023` lleva `222-IGSS-2023`.
4. **Diagnóstico de la propuesta de lista, sin cambiar su diseño:**
   - mide por etapa: búsquedas de `extraer_requisitos`, JEV de fechas, generación y validación;
   - registra los códigos de validación de cada intento;
   - responde si la falla es de la generación o de la recuperación.

   Para correrlo con la base y el LLM, usa el comando que arma el `Makefile`, sin leer la llave; la API real está en 127.0.0.1:8010.

## Criterios de aceptación

- `make test-consulta`, `pnpm --dir web build` y Vitest en verde.
- Con la API real, la pregunta de la demo del paso 3 responde con las dos fuentes.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- el diagnóstico del hallazgo 4, con las causas y una propuesta.

No amplíes el alcance.
