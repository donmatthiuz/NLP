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
LICIGT_DB_APP_USER ?= licigt_api
LICIGT_DB_APP_PASSWORD_FILE ?= keys/database/app.password
LICIGT_API_PUERTO ?= 8000
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
# Conexión de administrador (licigt: superusuario): solo para crear esquema, importar y sembrar datos de prueba.
WITH_DB_ADMIN = LICIGT_DB_URL="postgresql://$(LICIGT_DB_USER):$$(tr -d '\r\n' < $(LICIGT_DB_PASSWORD_FILE))@$(LICIGT_DB_HOST):$(LICIGT_DB_PORT)/$(LICIGT_DB_NAME)"
# Conexión de la aplicación (licigt_api: sin superusuario ni BYPASSRLS; make db-rol-app la crea): API, banco, reporte,
# evaluación, búsqueda y pruebas que solo leen o escriben la lista.
WITH_DB = LICIGT_DB_URL="postgresql://$(LICIGT_DB_APP_USER):$$(tr -d '\r\n' < $(LICIGT_DB_APP_PASSWORD_FILE))@$(LICIGT_DB_HOST):$(LICIGT_DB_PORT)/$(LICIGT_DB_NAME)"
EVENTO ?= 222-IGSS-2023

.PHONY: help setup env-init keys-init keys-status key-set db-up db-down db-password-sync db-password-rotar db-rol-app \
        importar evaluar buscar models-status claude opencode codex test-consulta test-ingesta test-recuperacion corpus \
        diagramas llm-descargar llm-servidor llm-estado llm-detener deps-consulta sondeo-jev api banco experimento-jev experimento-llm web web-build lista-schema test-consulta-sql \
        usuarios-demo empresa-b test-plataforma reporte deps

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "%s\n\t%s\n", $$1, $$2}'

setup: env-init keys-init ## Deja listo un clon: .env, llaves generadas o vacías para llenar
	@bash scripts/keys.sh status

deps: ## Instala las dependencias de Python (requirements.txt, con el SDK de JEV) y de la web (pnpm)
	@$(PYTHON) -m pip install -r requirements.txt
	@pnpm --dir web install --frozen-lockfile

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
	@printf "%s\nALTER ROLE \"%s\" PASSWORD '%s';\n" "SET log_min_error_statement = panic; SET log_statement = none;" "$(LICIGT_DB_USER)" "$$(tr -d '\r\n' < $(LICIGT_DB_PASSWORD_FILE))" \
		| docker compose exec -T postgres psql -q -U "$(LICIGT_DB_USER)" -d "$(LICIGT_DB_NAME)" \
		&& printf 'ok\tcontraseña alineada con %s\n' "$(LICIGT_DB_PASSWORD_FILE)"

# Rol de conexión de la aplicación: LOGIN sin superusuario ni BYPASSRLS, miembro de licigt_app (que tiene las
# políticas y los grants). Idempotente; corre como administrador y lee la contraseña dentro de la receta.
db-rol-app: ## Crea o actualiza el rol licigt_api con la contraseña de keys/database/app.password (requiere db-up)
	@printf "SET log_min_error_statement = panic; SET log_statement = none;\n\
DO \$$\$$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'licigt_app') THEN CREATE ROLE licigt_app NOLOGIN; END IF; END \$$\$$;\n\
ALTER ROLE licigt_app NOLOGIN NOSUPERUSER NOBYPASSRLS;\n\
DO \$$\$$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s') THEN CREATE ROLE \"%s\" LOGIN; END IF; END \$$\$$;\n\
ALTER ROLE \"%s\" WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD '%s';\n\
GRANT licigt_app TO \"%s\";\n" \
		"$(LICIGT_DB_APP_USER)" "$(LICIGT_DB_APP_USER)" "$(LICIGT_DB_APP_USER)" "$$(tr -d '\r\n' < $(LICIGT_DB_APP_PASSWORD_FILE))" "$(LICIGT_DB_APP_USER)" \
		| docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$(LICIGT_DB_USER)" -d "$(LICIGT_DB_NAME)" \
		&& printf 'ok\trol %s listo (sin superusuario, sin BYPASSRLS)\n' "$(LICIGT_DB_APP_USER)"

# Rotación: respaldo en keys/database/dev.password.bak, contraseña nueva al azar y aplicada con la lógica de
# db-password-sync. Si la base no la acepta se restaura la anterior. Nunca imprime la contraseña.
db-password-rotar: ## Rota la contraseña de administración (respaldo .bak) y la aplica en la base
	@set -e; f="$(LICIGT_DB_PASSWORD_FILE)"; umask 077; \
	[ -s "$$f" ] || { printf 'falta\t%s; corre make keys-init\n' "$$f" >&2; exit 1; }; \
	nueva="$$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')"; \
	printf '%s' "$$nueva" > "$$f.new"; chmod 600 "$$f.new"; \
	printf "SET log_min_error_statement = panic; SET log_statement = none;\nALTER ROLE \"%s\" PASSWORD '%s';\n" "$(LICIGT_DB_USER)" "$$nueva" \
		| docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$(LICIGT_DB_USER)" -d "$(LICIGT_DB_NAME)" \
		|| { rm -f "$$f.new"; printf 'error\tno se pudo aplicar; la contraseña anterior sigue vigente\n' >&2; exit 1; }; \
	cp -p "$$f" "$$f.bak"; chmod 600 "$$f.bak"; mv -f "$$f.new" "$$f"; \
	printf 'ok\tcontraseña rotada en %s (respaldo en %s.bak)\n' "$$f" "$$f"

# --- Recuperación (rol 2) --------------------------------------------------------

importar: ## Importa el paquete de ingesta a Postgres (modelos en models/)
	@$(WITH_DB_ADMIN) PYTHONPATH=src $(PYTHON) -m licigt.recuperacion importar

evaluar: ## Hit@5, MRR@5, suficiencia y latencia de las dos variantes con los casos de desarrollo del rol 2
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m licigt.recuperacion.evaluar

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

llm-servidor: ## Arranca llama-server con el LLM local en 127.0.0.1 (nativo: en primer plano; docker: regresa al arrancar el contenedor)
	@bash scripts/llm.sh servidor

llm-estado: ## Muestra el estado del binario, el modelo, la VRAM y el servidor
	@bash scripts/llm.sh estado

llm-detener: ## Detiene y elimina el contenedor licigt-llm (modo docker)
	@bash scripts/llm.sh detener

# --- Consulta (rol 3) -----------------------------------------------------------

deps-consulta: ## Reinstala solo las dependencias del rol 3, incluido el SDK de JEV (ya vienen con make deps)
	@$(PYTHON) -m pip install -r src/licigt/consulta/requirements.txt

sondeo-jev: ## Vista previa del sondeo de JEV; CONFIRMAR=1 autoriza el envío
	@PYTHONPATH=src $(PYTHON) -m licigt.consulta.sondeo_jev $(if $(filter 1,$(CONFIRMAR)),--confirmar-envio)

experimento-jev: ## Experimento de JEV: CONJUNTO=desarrollo|prueba; CONFIRMAR=1 autoriza el envío
	@PYTHONPATH=src $(PYTHON) -m licigt.consulta.experimento correr $(CONJUNTO) $(if $(filter 1,$(CONFIRMAR)),--confirmar-envio)

experimento-llm: ## Enrutador con el LLM local (make llm-servidor): CONJUNTO=desarrollo|prueba corre; COMPARAR=1 compara (P95_RESTO_MS=...)
	@PYTHONPATH=src $(PYTHON) -m licigt.consulta.experimento $(if $(filter 1,$(COMPARAR)),comparar,correr) $(CONJUNTO) --variante llm $(if $(P95_RESTO_MS),--p95-resto-ms $(P95_RESTO_MS))

lista-schema: ## Crea las tablas de la lista de verificación (idempotente; requiere db-up e importar)
	@$(WITH_DB_ADMIN) PYTHONPATH=src $(PYTHON) -c "import os,psycopg; psycopg.connect(os.environ['LICIGT_DB_URL'], autocommit=True).execute(open('src/licigt/consulta/lista_schema.sql', encoding='utf-8').read())"

test-consulta-sql: ## Pruebas de la lista en Postgres (requieren make db-up)
	@$(WITH_DB_ADMIN) PYTHONPATH=src $(PYTHON) -m unittest licigt.consulta.tests.test_lista_sql -v

api: ## Arranca la API de consulta con sesión por cookie (requiere make usuarios-demo) en 127.0.0.1:$(LICIGT_API_PUERTO) (8000 por defecto)
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m uvicorn licigt.consulta.api:app --host 127.0.0.1 --port $(LICIGT_API_PUERTO)

banco: ## Corre el banco de casos del rol 3 con los servicios reales (requiere db-up, importar y el LLM); guarda en data/consulta/banco
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m licigt.consulta.banco correr $(RUTA)

web: ## Arranca la web de consulta en modo desarrollo (Vite; proxy de /api a 127.0.0.1:$(LICIGT_API_PUERTO))
	@LICIGT_API_PUERTO=$(LICIGT_API_PUERTO) pnpm --dir web dev

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

test-plataforma: ## Pruebas del rol 4 (las de integración requieren make db-up, db-rol-app, importar y empresa-b); la API corre como licigt_api y las verificaciones como administrador
	@$(WITH_DB) LICIGT_DB_ADMIN_URL="postgresql://$(LICIGT_DB_USER):$$(tr -d '\r\n' < $(LICIGT_DB_PASSWORD_FILE))@$(LICIGT_DB_HOST):$(LICIGT_DB_PORT)/$(LICIGT_DB_NAME)" PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/plataforma/tests -v

reporte: ## Reporte de evaluación con los servicios reales (db-up, importar, empresa-b y el LLM); BANCO_COMUN=ruta opcional; guarda en data/plataforma/reporte
	@$(WITH_DB) LICIGT_LISTA=postgres HF_HUB_OFFLINE=1 BANCO_COMUN="$(BANCO_COMUN)" PYTHONPATH=src $(PYTHON) -m licigt.plataforma.evaluacion

usuarios-demo: ## Crea, si faltan, la clave y los usuarios de la demo en keys/plataforma (no imprime contraseñas). FORZAR=1 los regenera
	@PYTHONPATH=src $(PYTHON) -m licigt.plataforma.usuarios_demo $(if $(filter 1,$(FORZAR)),--forzar)

empresa-b: ## Arma data/plataforma/empresa_b.zip (evento 363 de la empresa ficticia empresa_b) y lo importa
	@PYTHONPATH=src $(PYTHON) -m licigt.plataforma.empresa_b
	@$(WITH_DB_ADMIN) PYTHONPATH=src $(PYTHON) -m licigt.recuperacion importar data/plataforma/empresa_b.zip

test-ingesta: ## Pruebas del rol 1
	@PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/ingesta/tests -v

corpus: ## Regenera el ZIP del corpus con los mismos ids; baja los PDF del IGSS solo con CONFIRMAR=1
	@if [ "$(CONFIRMAR)" = "1" ]; then \
		PYTHONPATH=src $(PYTHON) -m licigt.ingesta.reproducir --descargar --salida entregables/recuperacion/empresa_demo.zip; \
	else \
		printf 'Haría: PYTHONPATH=src python -m licigt.ingesta.reproducir --descargar --salida entregables/recuperacion/empresa_demo.zip\n'; \
		printf 'Descarga los PDF de igssgt.org y reescribe el ZIP. Agrega CONFIRMAR=1 para ejecutarlo.\n'; \
	fi

test-recuperacion: ## Pruebas del rol 2 (las de integración requieren make db-up e importar)
	@$(WITH_DB) PYTHONPATH=src $(PYTHON) -m unittest discover -s src/licigt/recuperacion/tests -v

# --- Diagramas ---------------------------------------------------------------------

diagramas: ## Exporta los diagramas HTML a PNG con Chrome
	@bash scripts/exportar_diagramas.sh
