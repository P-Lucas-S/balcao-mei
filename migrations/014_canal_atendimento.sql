-- 014_canal_atendimento.sql
-- Passo 2 da separação CANAL × SERVIÇO: a renomeação.
--
-- `tipo_atendimento` passa a se chamar `canal_atendimento`, refletindo o que
-- ela de fato contém. Renomeação de verdade — tabela, PK, sequence e FK — para
-- não deixar um nome enganoso no schema.
--
-- Esta migration é aplicada NO MESMO COMMIT que a religação dos ~90 pontos de
-- código. Aplicá-la sozinha quebra a aplicação.
--
-- O que sai de canal_atendimento:
--   * `link_portal` e `instrucao` — pertencem a SERVIÇO, e migraram para lá na
--     013. Nunca foram lidas em canal nenhum (só escritas por /tabelas/).
--   * 'Solicitação Formal' — não é canal nem serviço de balcão; virou o
--     serviço 'Solicitação' na 013. Verificado que tinha 0 vínculos.
--
-- O que entra em atendimento:
--   * `id_canal` NOT NULL — um atendimento tem UM canal. Backfill = Presencial
--     para todas as 879 linhas: os 877 fictícios serão regenerados logo em
--     seguida com canal sorteado, e os 2 operacionais ficam em Presencial por
--     decisão (não há como inferir o canal deles).
--
-- Seguro para re-execução: cada passo é guardado por checagem de existência.

-- ── 1. Renomear tabela, PK e sequence ────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'tipo_atendimento')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'canal_atendimento')
    THEN
        ALTER TABLE tipo_atendimento RENAME TO canal_atendimento;
        ALTER TABLE canal_atendimento RENAME CONSTRAINT tipo_atendimento_pkey
                                                    TO canal_atendimento_pkey;
        ALTER SEQUENCE tipo_atendimento_id_seq RENAME TO canal_atendimento_id_seq;
    END IF;
END $$;

-- FK de atendimento_tipo aponta para a tabela renomeada; o nome da constraint
-- não acompanha o rename automaticamente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'atendimento_tipo_id_tipo_atendimento_fkey')
    THEN
        ALTER TABLE atendimento_tipo
          RENAME CONSTRAINT atendimento_tipo_id_tipo_atendimento_fkey
                         TO atendimento_tipo_id_canal_fkey;
    END IF;
END $$;

-- ── 2. Colunas que pertencem a servico saem de canal ─────────────────────────
ALTER TABLE canal_atendimento DROP COLUMN IF EXISTS link_portal;
ALTER TABLE canal_atendimento DROP COLUMN IF EXISTS instrucao;

-- ── 3. 'Solicitação Formal' sai de canal (virou o serviço 'Solicitação') ─────
DELETE FROM canal_atendimento
 WHERE lower(descricao) LIKE 'solicita%formal'
   AND NOT EXISTS (SELECT 1 FROM atendimento_tipo t
                    WHERE t.id_tipo_atendimento = canal_atendimento.id);

-- ── 4. atendimento.id_canal ──────────────────────────────────────────────────
-- Três passos: adiciona aceitando NULL, preenche, só então NOT NULL.
ALTER TABLE atendimento
  ADD COLUMN IF NOT EXISTS id_canal INTEGER REFERENCES canal_atendimento(id);

UPDATE atendimento
   SET id_canal = (SELECT id FROM canal_atendimento
                    WHERE descricao = 'Presencial' LIMIT 1)
 WHERE id_canal IS NULL;

ALTER TABLE atendimento ALTER COLUMN id_canal SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_atendimento_canal ON atendimento(id_canal);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('014_canal_atendimento.sql')
ON CONFLICT (migration) DO NOTHING;
