-- Esquema de recuperación (rol 2). Idempotente: se puede ejecutar varias veces.
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'licigt_app') THEN
    CREATE ROLE licigt_app NOLOGIN;  -- rol de consulta: sin BYPASSRLS
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS documentos (
  doc_id                text PRIMARY KEY,
  tenant_id             text NOT NULL,
  evento_id             text NOT NULL,
  numero_evento         text NOT NULL,
  tipo_documento        text NOT NULL,
  version_ingesta       int  NOT NULL,
  identificador_version_oficial text,
  status                text NOT NULL,
  paginas_no_indexadas  int[] NOT NULL DEFAULT '{}',
  inventario            jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS fragmentos (
  chunk_id        text PRIMARY KEY,
  variante        text NOT NULL CHECK (variante IN ('base', 'mejorada')),
  doc_id          text NOT NULL REFERENCES documentos,
  tenant_id       text NOT NULL,
  evento_id       text NOT NULL,
  numero_evento   text NOT NULL,
  tipo_documento  text NOT NULL,
  version_ingesta int  NOT NULL,
  pagina_inicio   int  NOT NULL,
  pagina_fin      int  NOT NULL,
  pagina_impresa  integer,       -- número impreso en la página; NULL si no lo tiene (portada, página sin pie)
  seccion         text,
  texto           text NOT NULL,
  codigos         text[] NOT NULL DEFAULT '{}',
  url_origen      text NOT NULL,
  meta            jsonb NOT NULL,
  tsv tsvector GENERATED ALWAYS AS
      (to_tsvector('spanish', coalesce(seccion, '') || ' ' || texto)) STORED,
  emb_base        vector(384),   -- paraphrase-multilingual-MiniLM-L12-v2
  emb_mejorada    vector(1024)   -- BAAI/bge-m3
);

ALTER TABLE fragmentos ADD COLUMN IF NOT EXISTS pagina_impresa INTEGER;  -- bases creadas antes de R2/I1

CREATE INDEX IF NOT EXISTS fragmentos_filtro ON fragmentos (tenant_id, evento_id, variante);
CREATE INDEX IF NOT EXISTS fragmentos_tsv ON fragmentos USING gin (tsv);
CREATE INDEX IF NOT EXISTS fragmentos_codigos ON fragmentos USING gin (codigos);
CREATE INDEX IF NOT EXISTS fragmentos_emb_base ON fragmentos
  USING hnsw (emb_base vector_cosine_ops) WITH (m = 16, ef_construction = 64)
  WHERE variante = 'base';
CREATE INDEX IF NOT EXISTS fragmentos_emb_mejorada ON fragmentos
  USING hnsw (emb_mejorada vector_cosine_ops) WITH (m = 16, ef_construction = 64)
  WHERE variante = 'mejorada';

-- Seguridad por fila: segunda barrera además del WHERE explícito de cada consulta.
ALTER TABLE documentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE fragmentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS por_empresa ON documentos;
DROP POLICY IF EXISTS por_empresa ON fragmentos;
CREATE POLICY por_empresa ON documentos TO licigt_app
  USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY por_empresa ON fragmentos TO licigt_app
  USING (tenant_id = current_setting('app.tenant_id', true));
GRANT SELECT ON documentos, fragmentos TO licigt_app;
