-- Migration 004: vínculo formal Atendimento → Solicitação + supervisor_id em Usuario

ALTER TABLE solicitacao
  ADD COLUMN IF NOT EXISTS atendimento_id INTEGER
  REFERENCES atendimento(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_solicitacao_atendimento_id
  ON solicitacao(atendimento_id);

ALTER TABLE usuario
  ADD COLUMN IF NOT EXISTS supervisor_id INTEGER
  REFERENCES usuario(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_usuario_supervisor_id
  ON usuario(supervisor_id);
