-- 011_pessoa_soft_delete.sql
-- Exclusão lógica de cadastro de pessoa.
--
-- Contexto: até aqui havia DOIS caminhos de exclusão de cadastro, e eles
-- divergiam:
--   * pessoas.remover      — bloqueava a exclusão se houvesse histórico
--   * pendencias.aprovar   — tentava apagar e levantava IntegrityError
--                            (NotNullViolation em atendimento.id_pessoa),
--                            porque a relação não tem cascata e o ORM tenta
--                            anular a FK
-- A partir do ciclo 11 os dois convergem para exclusão lógica.
--
-- Regra de visibilidade:
--   ESCONDER em tudo que é operacional (lista, busca, seleção de pessoa,
--   ficha) — telas que servem para AGIR sobre a pessoa.
--   MANTER em tudo que é agregado (relatórios, análise, estatísticas) — o
--   atendimento aconteceu e continua contando. O trabalho realizado pela
--   Sala não é apagado quando o empreendedor exerce direito de exclusão.
--
-- O histórico vinculado (atendimentos, solicitações, requerimentos,
-- documentos) permanece INTACTO no banco. Nada é apagado fisicamente.
--
-- Mesmo padrão da 010 (documentos): campos próprios de exclusão, separados
-- de qualquer campo com outro significado.
--
-- Seguro para re-execução:
--   ADD COLUMN IF NOT EXISTS   → sem-op se a coluna já existe
--   CREATE INDEX IF NOT EXISTS → sem-op se o índice já existe

ALTER TABLE pessoa
  ADD COLUMN IF NOT EXISTS removido_em  TIMESTAMP,
  ADD COLUMN IF NOT EXISTS removido_por INTEGER REFERENCES usuario(id);

-- As consultas operacionais filtram por removido_em IS NULL
CREATE INDEX IF NOT EXISTS idx_pessoa_removido_em
  ON pessoa(removido_em);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('011_pessoa_soft_delete.sql')
ON CONFLICT (migration) DO NOTHING;
