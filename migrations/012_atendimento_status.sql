-- 012_atendimento_status.sql
-- Status de atendimento: rascunho / concluido.
--
-- Contexto: Fase 1 de 4 da mudança no fluxo de atendimento. Hoje o
-- atendimento só existe no banco depois de finalizado — é montado inteiro no
-- navegador e gravado de uma vez. Para permitir criar uma solicitação de
-- dentro da tela de atendimento, o atendimento precisará existir antes de ser
-- concluído. Este campo é a fundação disso.
--
-- Esta migration é INVISÍVEL para o usuário: nada muda na interface, e todo
-- atendimento criado pelo fluxo atual nasce 'concluido' — comportamento
-- idêntico ao de hoje, só que com o status agora explícito.
--
-- Padrão reutilizado: coluna VARCHAR(20) NOT NULL com DEFAULT, igual a
-- `solicitacao_exclusao.status` e `requerimento_gerado.status_requerimento`.
-- Não usa FK para a tabela `status` porque aquela é o catálogo configurável do
-- workflow de SOLICITAÇÃO (Pendente/Em Análise/Aprovado/Recusado), editável
-- pelo admin em /tabelas/. Aqui são dois valores internos e fixos.
--
-- Backfill em três passos, seguro para tabela com linhas:
--   1. adiciona a coluna aceitando NULL
--   2. preenche as linhas existentes
--   3. só então aplica DEFAULT e NOT NULL
-- Fazer NOT NULL de uma vez falharia com as 879 linhas já existentes.
--
-- Seguro para re-execução: ADD COLUMN IF NOT EXISTS é sem-op; o UPDATE só
-- alcança linhas com status NULL; DEFAULT e NOT NULL são idempotentes.

-- 1. Coluna, inicialmente aceitando NULL
ALTER TABLE atendimento
  ADD COLUMN IF NOT EXISTS status VARCHAR(20);

-- 2. Todo atendimento já existente é um registro real e finalizado no modelo
--    antigo — migra como 'concluido'
UPDATE atendimento
   SET status = 'concluido'
 WHERE status IS NULL;

-- 3. Default para novos registros e trava de integridade
ALTER TABLE atendimento
  ALTER COLUMN status SET DEFAULT 'concluido';

ALTER TABLE atendimento
  ALTER COLUMN status SET NOT NULL;

-- As consultas da Fase 2 filtrarão por status
CREATE INDEX IF NOT EXISTS idx_atendimento_status
  ON atendimento(status);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('012_atendimento_status.sql')
ON CONFLICT (migration) DO NOTHING;
