-- 015_drop_atendimento_tipo.sql
-- Passo 3 (final) da separação CANAL × SERVIÇO.
--
-- `atendimento_tipo` era o vínculo N:N atendimento ↔ tipo_atendimento. Como
-- `tipo_atendimento` continha CANAIS e canal virou um campo único em
-- `atendimento` (`id_canal`, migration 014), esta tabela perdeu a razão de
-- existir. O papel N:N passou para `atendimento_servico` (migration 013).
--
-- Executada SEPARADAMENTE e só após a validação completa:
--   * dados fictícios regenerados no formato novo
--   * 119 testes passando
--   * smoke test em 22 telas, todas 200
--   * os 2 KPIs que estavam zerados (Novos MEIs, Orientação) recuperados
--
-- As linhas remanescentes eram resíduo dos 2 atendimentos operacionais, cujo
-- canal já foi preservado em `atendimento.id_canal` = Presencial. Nenhuma
-- informação é perdida: o que a tabela guardava era canal, e canal agora tem
-- lugar próprio.
--
-- Backup: backups/pre_canal_servico_*.sql (pg_dump completo, pré-migração).
--
-- Seguro para re-execução: DROP TABLE IF EXISTS.

DROP TABLE IF EXISTS atendimento_tipo;

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('015_drop_atendimento_tipo.sql')
ON CONFLICT (migration) DO NOTHING;
