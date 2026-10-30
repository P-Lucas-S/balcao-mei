-- Migration 003: ampliar ParametrosMunicipio.valor para Text
-- Permite armazenar textos longos (modelos de requerimento, etc.)
ALTER TABLE parametros_municipio
  ALTER COLUMN valor TYPE TEXT;
