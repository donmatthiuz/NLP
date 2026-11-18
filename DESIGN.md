# Diseño de LiciGT

Resumen de las decisiones de diseño vigentes. La referencia completa es el [anteproyecto](docs/anteproyecto/Anteproyecto.md#9-arquitectura) y los diagramas de [`docs/arquitectura/diagramas/`](docs/arquitectura/diagramas/README.md) (`arquitectura_general.png` y `flujo_consulta.png`). Si este archivo y el anteproyecto difieren, se corrige uno de los dos y se anota en [`docs/Pendientes.md`](docs/Pendientes.md).

## Principios

- El modelo redacta, pero no decide permisos, vigencia ni suficiencia: eso lo hace código determinista o clasificadores acotados con umbral.
- El filtro por empresa y evento se aplica en SQL antes de recuperar, con seguridad por fila como segunda barrera. El modelo solo ve lo que el usuario puede ver.
- Ningún filtro de seguridad es suficiente por sí solo; se combinan capas.
- Se reporta lo que se midió. La ausencia de una condición en los documentos cargados no prueba que no exista en el expediente.

## Flujo de consulta

1. Autenticación y contexto: empresa, `evento_id` y rol (rol 4).
2. Validación de entrada: formato, alcance e indicios de ataque. Si falla, abstención.
3. Enrutador de intención hacia una de tres herramientas de solo lectura (rol 3).
4. Recuperación híbrida con reranking, alertas y suficiencia (rol 2).
5. Generación estructurada con citas.
6. Validador determinista: esquema, existencia y permisos de cada `chunk_id`, página, versión y texto citado. Una regeneración; si falla, salida controlada.
7. Respuesta con fuentes, o abstención, o revisión humana.

## Capa de decisión

Las decisiones de intención y suficiencia son clasificadores con umbral. Se comparan reglas, LLM con salida estructurada y JEV (modelo de decisión con probabilidades calibradas: `choice` para la intención y `noul` para la suficiencia). JEV se queda en cada punto solo si mejora el resultado en el banco etiquetado. La implementación está detrás de una interfaz común para poder intercambiarla. JEV se consume por su API alojada: solo recibe la pregunta y textos de documentos públicos, y el código lee su clave desde el archivo que indica `LICIGT_JEV_API_KEY_FILE` (por defecto `keys/jev/api.key`).

## Contratos entre módulos

- Rol 2 a rol 3: `buscar(ctx, evento_id, pregunta, variante, k)` y `comparar_versiones(ctx, evento_id, pregunta, k)`; ver [Contratos](docs/consulta/Contratos.md#rol-2-hacia-rol-3).
- Rol 3 a usuario: respuesta con el esquema de `AGENTS.md`. El estado de la lista de verificación es independiente y registra usuario y momento de cada cambio.
- Alertas: `posible_conflicto` lleva a `needs_human_review`; `cobertura_incompleta` lleva a `coverage_status` parcial y a `warnings`.

## Stack

- Datos: PostgreSQL con pgvector y `tsvector` en español; PDF originales en MinIO o Cloud Storage (pendiente de decisión).
- Backend: Python. API propuesta con FastAPI y Pydantic (a acordar con el rol 4).
- Frontend: propuesto React con Vite y TypeScript (a acordar con el rol 4). Streamlit descartado.
- Configuración: parámetros sin secretos en `.env` (plantilla `.env.example`), secretos como un archivo por llave en `keys/` (ver `keys/README.md`), modelos de Hugging Face en `models/` mediante `HF_HOME`. El `Makefile` carga `.env` y arma `LICIGT_DB_URL` solo para el proceso que lo usa.
- LLM generador: un solo cliente con la API compatible con OpenAI, así que cambiar de proveedor es configuración (URL, modelo y llave opcional en `keys/`), no código.
  - **Local (por defecto):** Qwen3.5-9B Q4_K_M sobre `llama-server`, con la versión y el archivo fijados ([I2](docs/consulta/investigacion/I2_llm_local.md)). Equipo de desarrollo: RTX 5070 de 12 GB y 64 GB de RAM, compartidos con los modelos del rol 2.
  - **Nube (interruptor):** OpenAI, para máquinas sin GPU. A la nube solo van la pregunta y fragmentos de documentos públicos del IGSS; nunca `tenant_id`, usuarios ni datos de la empresa.
  - Sin credenciales en el repo.

## Interfaz de usuario

Requisitos que vienen del anteproyecto; la identidad visual no está definida.

- Español, con el aviso fijo: "La respuesta se basa en los documentos cargados del evento".
- Cada dato muestra documento, página y versión, con acceso al original autorizado.
- Se distinguen visualmente respuesta, abstención y revisión humana.
- Las contradicciones muestran ambas fuentes y piden revisión; nunca eligen la vigente.
- La lista de verificación permite marcar ítems (pendiente, preparado, revisado) y se guarda solo con confirmación.
- Se muestran los documentos incorporados al evento y qué información falta.
- Los estados de la lista no certifican cumplimiento.

## Fuera de alcance

Presentar ofertas, navegar a sitios externos, modificar documentos, decidir automáticamente la vigencia, recomendaciones clínicas y expedientes confidenciales de empresas.
