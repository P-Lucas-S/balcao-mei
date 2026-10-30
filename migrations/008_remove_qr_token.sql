-- 008_remove_qr_token.sql
-- Remove os resíduos do QR code de confirmação de recebimento em
-- requerimento_gerado.
--
-- Contexto: o fluxo de QR code foi adicionado e removido na mesma sessão
-- (2026-05-24, commit 18ec0dd — "refactor: remove QR code e confirmação de
-- recebimento"). A rota, o template e a dependência `qrcode[pil]` já haviam
-- sido revertidos, mas a coluna `qr_token` e o índice único criados pela
-- migration 005 permaneceram no schema, órfãos: nenhum código do sistema lê
-- ou escreve nesse campo.
--
-- Seguro: verificado antes da execução que todas as linhas de
-- requerimento_gerado têm qr_token IS NULL — nenhum dado é perdido.
--
-- Seguro para re-execução:
--   DROP INDEX IF EXISTS   → sem-op se o índice já foi removido
--   DROP COLUMN IF EXISTS  → sem-op se a coluna já foi removida

-- 1. Índice único parcial criado pela migration 005
DROP INDEX IF EXISTS idx_requerimento_qr_token;

-- 2. Coluna órfã
ALTER TABLE requerimento_gerado
  DROP COLUMN IF EXISTS qr_token;
