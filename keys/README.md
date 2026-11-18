# Llaves locales

Todo lo sensible del proyecto, una carpeta por servicio. Solo se versionan este README, `.gitignore` y los `.gitkeep`; nada de lo que se ponga aquí viaja en el repositorio. Basado en el esquema de llaves de intelligence-radar.

```text
keys/
  mcp/
    context7.token    documentación actualizada de librerías para los agentes
  jev/
    api.key           clave de TypeSafe para JEV (rol 3)
  database/
    dev.password      contraseña de Postgres de desarrollo; la genera make keys-init    
  llm/
    openai.key        # opcional: solo si LICIGT_LLM=openai (máquinas sin GPU)    
```

## Uso

```bash
make keys-init                              # crea los archivos que falten, vacíos y con permisos 600
make key-set FILE=keys/mcp/context7.token   # pega la llave sin que se vea ni quede en el historial
make keys-status                            # dice cuáles faltan o están vacías, sin abrirlas
```

## Cómo la leen los agentes

| Herramienta | Cómo abrirla | Cómo recibe la llave |
| --- | --- | --- |
| Claude Code | `make claude` o `claude` | `.mcp.json` llama a `scripts/mcp/headers_context7.sh`, que lee el archivo en cada conexión |
| OpenCode | `make opencode` | el Makefile exporta `CONTEXT7_API_KEY` solo para ese proceso; `opencode.json` la usa con `{env:...}` |
| Codex | `make codex` | igual, con `bearer_token_env_var` en `.codex/config.toml` (el proyecto debe estar marcado como confiable) |

Sin llave, Context7 responde igual con límites anónimos.

## Reglas

- Ningún agente debe leer esta carpeta; Claude Code lo tiene bloqueado en `.claude/settings.json`.
- No pegar llaves en código, documentos, prompts ni consultas.
- Si una llave se filtra, revocarla en su proveedor y guardar la nueva con `make key-set FILE=... FORCE=1`.
