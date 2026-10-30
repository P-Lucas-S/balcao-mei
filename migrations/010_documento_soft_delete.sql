-- 010_documento_soft_delete.sql
-- Exclusão lógica de documentos de pessoa.
--
-- Contexto: até aqui, remover um documento apagava a linha do banco E o
-- arquivo do disco — irreversível, e disponível a qualquer usuário
-- autenticado. A partir do ciclo 10 a remoção é lógica e restrita ao
-- administrador; o arquivo é preservado.
--
-- Por que campos novos e não o `ativo` que já existe:
--   `documento_pessoa.ativo` tem significado de VERSIONAMENTO — quando se
--   envia um novo documento de um tipo já existente, a versão anterior
--   recebe ativo=False e continua visível no histórico do tipo.
--   Sobrecarregar esse campo com o sentido de "excluído" misturaria as duas
--   coisas: uma versão antiga passaria a parecer excluída, e um documento
--   excluído reapareceria como versão antiga no histórico.
--
-- Seguro para re-execução:
--   ADD COLUMN IF NOT EXISTS   → sem-op se a coluna já existe
--   CREATE INDEX IF NOT EXISTS → sem-op se o índice já existe

ALTER TABLE documento_pessoa
  ADD COLUMN IF NOT EXISTS removido_em  TIMESTAMP,
  ADD COLUMN IF NOT EXISTS removido_por INTEGER REFERENCES usuario(id);

-- As consultas de exibição filtram por removido_em IS NULL
CREATE INDEX IF NOT EXISTS idx_documento_pessoa_removido_em
  ON documento_pessoa(removido_em);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('010_documento_soft_delete.sql')
ON CONFLICT (migration) DO NOTHING;
