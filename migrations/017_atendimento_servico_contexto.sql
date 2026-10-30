-- 017_atendimento_servico_contexto.sql
-- Contexto do serviço no momento em que foi registrado.
--
-- Núcleo da filtragem dinâmica de serviços por tipo de pessoa. Dois campos
-- no vínculo atendimento ↔ serviço:
--
--   tipo_efetivo — SNAPSHOT do tipo vigente quando aquele serviço foi
--                  marcado. Existe para o histórico não mudar
--                  retroativamente: se a pessoa abriu MEI no meio do
--                  atendimento, "Abertura de MEI" fica registrada como
--                  feita quando ela ainda era 'nao_mei', e um serviço de
--                  MEI marcado depois fica como 'mei'. Um mesmo
--                  atendimento pode ter serviços com tipos diferentes.
--
--   forcado      — o serviço foi marcado pela válvula de escape ("Mostrar
--                  todos"), fora da aplicabilidade do tipo efetivo. É
--                  aceito, mas fica marcado para auditoria. Estado
--                  inconsistente na tela nunca vira registro silencioso.
--
-- `tipo_efetivo` é NULL nos vínculos anteriores a esta migration e nos
-- criados por caminhos que não têm essa noção (atendimento rápido,
-- formulário completo, upsert). NULL significa "não registrado", não
-- "desconhecido por erro".
--
-- Seguro para re-execução: ADD COLUMN IF NOT EXISTS.

ALTER TABLE atendimento_servico
  ADD COLUMN IF NOT EXISTS tipo_efetivo VARCHAR(20),
  ADD COLUMN IF NOT EXISTS forcado      BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN atendimento_servico.tipo_efetivo IS
    'Snapshot do tipo efetivo do atendimento quando este serviço foi marcado (nao_mei | mei | NULL)';
COMMENT ON COLUMN atendimento_servico.forcado IS
    'Marcado via válvula de escape, fora da aplicabilidade do tipo efetivo';

-- Auditoria de serviços forçados
CREATE INDEX IF NOT EXISTS idx_atendimento_servico_forcado
  ON atendimento_servico(forcado) WHERE forcado;

INSERT INTO schema_migrations (migration) VALUES
    ('017_atendimento_servico_contexto.sql')
ON CONFLICT (migration) DO NOTHING;
