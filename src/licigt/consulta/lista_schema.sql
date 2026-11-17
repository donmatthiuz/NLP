-- Lista de verificación (rol 3). Idempotente; requiere el esquema del rol 2 (rol licigt_app).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'licigt_app') THEN
    CREATE ROLE licigt_app NOLOGIN;  -- rol de consulta: sin BYPASSRLS
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS lista_items (
  orden              bigint GENERATED ALWAYS AS IDENTITY,
  tenant_id          text NOT NULL,
  item_id            text NOT NULL,
  evento_id          text NOT NULL,
  tipo               text NOT NULL CHECK (tipo IN ('requisito', 'fecha')),
  categoria          text,
  caracter           text NOT NULL CHECK (caracter IN ('fundamental', 'no_fundamental', 'no_indicado')),
  descripcion        text NOT NULL,
  fuentes            jsonb NOT NULL,
  requiere_revision  boolean NOT NULL,
  motivo_revision    text,
  estado             text NOT NULL CHECK (estado IN ('pendiente', 'preparado', 'revisado')),
  creado_por         text NOT NULL,
  creado_en          timestamptz NOT NULL,
  actualizado_por    text NOT NULL,
  actualizado_en     timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, item_id)
);

-- Historial al que solo se agregan filas.
CREATE TABLE IF NOT EXISTS lista_cambios (
  cambio_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id        text NOT NULL,
  evento_id        text NOT NULL,
  item_id          text NOT NULL,
  accion           text NOT NULL CHECK (accion IN ('alta', 'estado')),
  estado_anterior  text,
  estado_nuevo     text NOT NULL,
  usuario          text NOT NULL,
  momento          timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS lista_items_tenant ON lista_items (tenant_id);
CREATE INDEX IF NOT EXISTS lista_items_evento ON lista_items (evento_id);
CREATE INDEX IF NOT EXISTS lista_cambios_tenant ON lista_cambios (tenant_id);
CREATE INDEX IF NOT EXISTS lista_cambios_evento ON lista_cambios (evento_id);

-- Seguridad por fila: segunda barrera además del WHERE explícito de cada consulta.
ALTER TABLE lista_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE lista_cambios ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS por_empresa ON lista_items;
DROP POLICY IF EXISTS por_empresa ON lista_cambios;
CREATE POLICY por_empresa ON lista_items TO licigt_app
  USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY por_empresa ON lista_cambios TO licigt_app
  USING (tenant_id = current_setting('app.tenant_id', true));
GRANT SELECT, INSERT, UPDATE ON lista_items TO licigt_app;
GRANT SELECT, INSERT ON lista_cambios TO licigt_app;
