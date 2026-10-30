-- 009_schema_migrations.sql
-- Cria o controle de versão de migrations aplicadas.
--
-- Contexto: até aqui não havia como saber quais migrations já tinham rodado
-- num banco. A checagem dependia de inspeção manual do schema. Todas são
-- idempotentes, o que mitigava o risco, mas não respondia à pergunta
-- "este banco está atualizado?".
--
-- Esta tabela responde. Cada linha é um arquivo de migration aplicado.
--
-- Seguro para re-execução:
--   CREATE TABLE IF NOT EXISTS  → sem-op se a tabela já existe
--   ON CONFLICT DO NOTHING      → registrar de novo não duplica nem falha

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration  VARCHAR(150) PRIMARY KEY,
    applied_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE schema_migrations IS
    'Migrations aplicadas neste banco. Uma linha por arquivo de migrations/.';

-- ── Registro do histórico ────────────────────────────────────────────────────
-- As migrations 002→008 foram aplicadas neste banco ao longo de 2026.
-- A 001 é um pg_dump do schema resultante delas, então um banco criado a
-- partir da 001 é equivalente a um banco que rodou 002→008: os dois caminhos
-- convergem para o mesmo estado, e por isso ambos registram a lista completa.
--
-- `applied_at` recebe NOW() para as linhas inseridas agora — a data real de
-- aplicação histórica não foi registrada na época e não é recuperável. O que
-- importa é o fato de estarem aplicadas, não o instante.

INSERT INTO schema_migrations (migration) VALUES
    ('001_schema_inicial.sql'),
    ('002_sync_schema.sql'),
    ('003_parametros_valor_text.sql'),
    ('004_atendimento_id_solicitacao.sql'),
    ('005_requerimento_hibrido.sql'),
    ('006_fase3.sql'),
    ('007_remove_status_legados.sql'),
    ('008_remove_qr_token.sql'),
    ('009_schema_migrations.sql')
ON CONFLICT (migration) DO NOTHING;

-- Nota: `migrations/add_campos_ficha.py` NÃO é registrado aqui de propósito.
-- Está fora da numeração e é redundante — tudo que ele faz já está na
-- 002_sync_schema.sql. Não deve ser executado em banco nenhum.
