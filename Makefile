# Puerta de entrada del proyecto. Cada objetivo también se puede correr a mano.
#   make            muestra la ayuda
#   make setup      deja listo un clon: .env, llaves y base de datos

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Parámetros sin secretos (.env.example). Los secretos se leen de keys/ solo
# para el proceso que los necesita; nunca quedan en el entorno de la terminal.
-include .env
HF_HOME ?= models
LICIGT_DB_HOST ?= 127.0.0.1
LICIGT_DB_PORT ?= 5432
LICIGT_DB_NAME ?= licigt
LICIGT_DB_USER ?= licigt
LICIGT_DB_PASSWORD_FILE ?= keys/database/dev.password
LICIGT_JEV_API_KEY_FILE ?= keys/jev/api.key
# Exportar las opciones definidas; las ausentes conservan los valores de config.py.
VARIABLES_JEV := LICIGT_JEV_API_KEY_FILE LICIGT_JEV_MODELO LICIGT_JEV_REINTENTOS \
                 LICIGT_JEV_TIEMPO_ESPERA LICIGT_JEV_ESPERA_REINTENTO \
                 LICIGT_JEV_MAX_SOLICITUDES_SEG LICIGT_JEV_ESPERA_FRECUENCIA
export $(foreach variable,$(VARIABLES_JEV),$(if $(filter undefined,$(origin $(variable))),,$(variable)))
# Caché de modelos dentro del proyecto, como ruta absoluta.
export HF_HOME := $(abspath $(HF_HOME))

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CONTEXT7_TOKEN := keys/mcp/context7.token
WITH_CONTEXT7 = CONTEXT7_API_KEY="$$(tr -d '\r\n' < $(CONTEXT7_TOKEN) 2>/dev/null)"
WITH_DB = LICIGT_DB_URL="postgresql://$(LICIGT_DB_USER):$$(tr -d '\r\n' < $(LICIGT_DB_PASSWORD_FILE))@$(LICIGT_DB_HOST):$(LICIGT_DB_PORT)/$(LICIGT_DB_NAME)"
EVENTO ?= 222-IGSS-2023

.PHONY: help setup env-init keys-init keys-status key-set db-up db-down db-password-sync \
        importar buscar models-status claude opencode codex test-consulta test-ingesta test-recuperacion \
        diagramas llm-descargar llm-servidor llm-estado deps-consulta sondeo-jev api experimento-jev web web-build

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "%s\n\t%s\n", $$1, $$2}'

setup: env-init keys-init ## Deja listo un clon: .env, llaves generadas o vacías para llenar
	@bash scripts/keys.sh status

env-init: ## Crea .env desde .env.example sin pisarlo
	@if [ -e .env ]; then printf 'ok\t.env ya existe; no se tocó\n'; else cp .env.example .env && printf 'creado\t.env\n'; fi

# --- Llaves (keys/README.md) -------------------------------------------------

keys-init: ## Crea las llaves que falten: genera la contraseña de la base y deja vacías las de proveedores
	@bash scripts/keys.sh init

keys-status: ## Dice qué llaves faltan o están vacías, sin abrirlas
	@bash scripts/keys.sh status

key-set: ## Guarda una llave sin mostrarla. Uso: make key-set FILE=keys/mcp/context7.token [FORCE=1]
	@FORCE="$(FORCE)" bash scripts/keys.sh set "$(FILE)"

# --- Base de datos (docker-compose.yml) ----------------------------------------

db-up: keys-init ## Levanta Postgres con pgvector; la contraseña sale de keys/database/dev.password
	@docker compose up -d

db-down: ## Detiene Postgres sin borrar sus datos
	@docker compose down

# La contraseña de un volumen solo se fija al crearlo. Un volumen anterior
# (con la contraseña vieja) se alinea con la de keys/ sin borrar datos.
db-password-sync: ## Aplica la contraseña de keys/ a un volumen creado antes con otra
	@printf "ALTER ROLE \"%s\" PASSWORD '%s';\n" "$(LICIGT_DB_USER)" "$$(tr -d '\r\n' < $(LICIGT_DB_PASSWORD_FILE))" \
		| docker compose exec -T postgres psql -q -U "$(LICIGT_DB_USER)" -d "$(LICIGT_DB_NAME)" \
		&& printf 'ok\tcontraseña alineada con %s\n' "$(LICIGT_DB_PASSWORD_FILE)"

# --- Recuperación (rol 2) --------------------------------------------------------

importar: ## Importa el paquete de ingesta a Postgres (modelos en models/)
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m licigt.recuperacion importar

buscar: ## Búsqueda de prueba. Uso: make buscar Q="fecha de recepción de ofertas" [EVENTO=222-IGSS-2023]
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m licigt.recuperacion buscar --evento "$(EVENTO)" "$(Q)"

models-status: ## Lista los modelos descargados en models/ con su revisión exacta
	@shopt -s nullglob; found=0; for d in "$(HF_HOME)"/hub/models--*; do \
		found=1; nombre="$$(basename "$$d" | sed 's/^models--//; s/--/\//')"; \
		for s in "$$d"/snapshots/*; do \
			printf '%s\t%s\n' "$$nombre" "$$(basename "$$s")"; \
		done; \
	done; [ $$found = 1 ] || printf 'sin modelos en %s\n' "$(HF_HOME)"

# --- LLM generador (rol 3) -------------------------------------------------------

llm-descargar: ## Descarga llama.cpp b12441 y el GGUF del LLM a tools/ y models/ (unos 6 GB)
	@bash scripts/llm.sh descargar

llm-servidor: ## Arranca llama-server con el LLM local en 127.0.0.1 (en primer plano)
	@bash scripts/llm.sh servidor

llm-estado: ## Muestra el estado del binario, el modelo, la VRAM y el servidor
	@bash scripts/llm.sh estado

# --- Consulta (rol 3) -----------------------------------------------------------

deps-consulta: ## Instala las dependencias del rol 3, incluido el SDK de JEV
	@$(PYTHON) -m pip install -r src/licigt/consulta/requirements.txt

sondeo-jev: ## Vista previa del sondeo de JEV; CONFIRMAR=1 autoriza el envío
	@PYTHONPATH=src $(PYTHON) -m licigt.consulta.sondeo_jev $(if $(filter 1,$(CONFIRMAR)),--confirmar-envio)

experimento-jev: ## Experimento de JEV: CONJUNTO=desarrollo|prueba; CONFIRMAR=1 autoriza el envío
	@PYTHONPATH=src $(PYTHON) -m licigt.consulta.experimento correr $(CONJUNTO) $(if $(filter 1,$(CONFIRMAR)),--confirmar-envio)

api: ## Arranca el adaptador de consulta (demo, sin autenticación) en 127.0.0.1:8000
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m uvicorn licigt.consulta.api:app --host 127.0.0.1 --port 8000

web: ## Arranca la web de consulta en modo desarrollo (Vite; proxy de /api a 127.0.0.1:8000)
	@pnpm --dir web dev

web-build: ## Compila la web de consulta (tsc y vite build)
	@pnpm --dir web build

# --- Agentes con los MCP del proyecto -------------------------------------------

claude: ## Abre Claude Code (la llave la lee scripts/mcp/headers_context7.sh). ARGS="..."
	@exec claude $(ARGS)

opencode: ## Abre OpenCode con la llave de Context7 solo para ese proceso. ARGS="..."
	@$(WITH_CONTEXT7) exec opencode $(ARGS)

codex: ## Abre Codex sin servidor compartido y con la llave de Context7. ARGS="..."
	@$(WITH_CONTEXT7) exec codex --no-daemon $(ARGS)

# --- Pruebas -----------------------------------------------------------------------

test-consulta: ## Pruebas del rol 3, sin red ni base de datos
	@PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/consulta/tests -v

test-ingesta: ## Pruebas del rol 1
	@PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/ingesta/tests -v

test-recuperacion: ## Pruebas del rol 2 (las de integración requieren make db-up e importar)
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/recuperacion/tests -v

# --- Diagramas ---------------------------------------------------------------------

diagramas: ## Exporta los diagramas HTML a PNG con Chrome
	@bash scripts/exportar_diagramas.sh
