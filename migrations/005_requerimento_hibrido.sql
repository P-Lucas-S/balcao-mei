-- Migration 005: campos para fluxo híbrido de requerimento
ALTER TABLE requerimento_gerado
  ADD COLUMN IF NOT EXISTS modo_emissao        VARCHAR(20),
  ADD COLUMN IF NOT EXISTS status_requerimento VARCHAR(20) DEFAULT 'gerado',
  ADD COLUMN IF NOT EXISTS qr_token            VARCHAR(64),
  ADD COLUMN IF NOT EXISTS observacao_manual   TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_requerimento_qr_token
  ON requerimento_gerado(qr_token)
  WHERE qr_token IS NOT NULL;

-- Registros legados marcados como digital
UPDATE requerimento_gerado
  SET modo_emissao = 'digital',
      status_requerimento = 'gerado'
  WHERE modo_emissao IS NULL;
