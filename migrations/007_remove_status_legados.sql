-- 007_remove_status_legados.sql
-- Remove os 4 status legados que são resquícios de versão anterior.
-- O banco contém 8 status; apenas 4 são válidos operacionalmente:
--   Pendente, Em Análise, Aprovado, Recusado
-- Os legados (Aberta, Em andamento, Concluída, Cancelada) não deveriam
-- existir no workflow atual. Este script migra eventuais solicitações
-- que tenham um desses status e depois deleta as linhas da tabela status.
--
-- Mapeamento de migração:
--   Aberta        → Pendente
--   Em andamento  → Em Análise
--   Concluída     → Aprovado
--   Cancelada     → Recusado
--
-- Executar uma vez. Idempotente: DELETEs não encontrarão as linhas
-- na segunda execução; UPDATEs não encontrarão solicitações legadas.

-- 1. Migrar solicitações com status "Aberta" → "Pendente"
UPDATE solicitacao
SET id_status = (SELECT id FROM status WHERE descricao = 'Pendente' LIMIT 1)
WHERE id_status IN (
    SELECT id FROM status WHERE LOWER(descricao) = 'aberta'
);

-- 2. Migrar solicitações com status "Em andamento" → "Em Análise"
UPDATE solicitacao
SET id_status = (SELECT id FROM status WHERE descricao = 'Em Análise' LIMIT 1)
WHERE id_status IN (
    SELECT id FROM status WHERE LOWER(descricao) = 'em andamento'
);

-- 3. Migrar solicitações com status "Concluída" → "Aprovado"
UPDATE solicitacao
SET id_status = (SELECT id FROM status
                 WHERE LOWER(descricao) = 'aprovado' LIMIT 1)
WHERE id_status IN (
    SELECT id FROM status
    WHERE LOWER(descricao) IN ('concluída', 'concluida', 'concluído', 'concluido')
);

-- 4. Migrar solicitações com status "Cancelada" → "Recusado"
UPDATE solicitacao
SET id_status = (SELECT id FROM status WHERE descricao = 'Recusado' LIMIT 1)
WHERE id_status IN (
    SELECT id FROM status WHERE LOWER(descricao) = 'cancelada'
);

-- 5. Deletar os status legados (FK já migrada — nenhuma solicitação os referencia)
DELETE FROM status
WHERE LOWER(descricao) IN (
    'aberta',
    'em andamento',
    'concluída',
    'concluida',
    'concluído',
    'concluido',
    'cancelada'
);
