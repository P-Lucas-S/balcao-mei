-- 006 — Fase 3: Tags de interesse, conversão PF→MEI e LGPD WhatsApp

-- Tags de interesse
CREATE TABLE IF NOT EXISTS tag_interesse (
    id        SERIAL PRIMARY KEY,
    descricao VARCHAR(100) NOT NULL,
    ativo     BOOLEAN NOT NULL DEFAULT TRUE,
    protegido BOOLEAN NOT NULL DEFAULT FALSE
);

-- Relação N:N pessoa × tag
CREATE TABLE IF NOT EXISTS pessoa_tag (
    id_pessoa INTEGER NOT NULL REFERENCES pessoa(id) ON DELETE CASCADE,
    id_tag    INTEGER NOT NULL REFERENCES tag_interesse(id) ON DELETE CASCADE,
    PRIMARY KEY (id_pessoa, id_tag)
);

-- Tags padrão protegidas (idempotente)
INSERT INTO tag_interesse (descricao, ativo, protegido)
SELECT v.descricao, TRUE, TRUE
FROM (VALUES
    ('Feira/Evento'),
    ('Box/Mercado'),
    ('Espaço Público'),
    ('MEI'),
    ('Crédito/Financiamento'),
    ('Orientação Fiscal'),
    ('Outros')
) AS v(descricao)
WHERE NOT EXISTS (SELECT 1 FROM tag_interesse WHERE descricao = v.descricao);

-- LGPD — consentimento WhatsApp
ALTER TABLE pessoa
    ADD COLUMN IF NOT EXISTS aceite_whatsapp        BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE pessoa
    ADD COLUMN IF NOT EXISTS data_aceite_whatsapp    TIMESTAMP;

ALTER TABLE pessoa
    ADD COLUMN IF NOT EXISTS data_revogacao_whatsapp TIMESTAMP;

-- Índices
CREATE INDEX IF NOT EXISTS idx_pessoa_tag_pessoa ON pessoa_tag(id_pessoa);
CREATE INDEX IF NOT EXISTS idx_pessoa_tag_tag    ON pessoa_tag(id_tag);
