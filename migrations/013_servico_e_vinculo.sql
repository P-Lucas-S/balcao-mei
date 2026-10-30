-- 013_servico_e_vinculo.sql
-- Passo 1 da separação CANAL × SERVIÇO: parte aditiva.
--
-- Contexto: `tipo_atendimento` acumulava duas dimensões diferentes. Hoje ela
-- contém CANAIS de contato (Presencial, Telefone, E-mail, WhatsApp), enquanto
-- o JavaScript da tela guiada a trata como catálogo de SERVIÇOS (DAS, MEI…)
-- usando ids que não existem no banco. Os links dos portais estão hardcoded
-- no JS, e as colunas `link_portal`/`instrucao` de `tipo_atendimento` nunca
-- foram lidas por ninguém.
--
-- Esta migration é ADITIVA PURA: cria o que falta, não mexe em nada existente.
-- O sistema continua funcionando normalmente depois dela. A renomeação de
-- `tipo_atendimento` e a religação do código vêm na 014.
--
-- APLICABILIDADE: de quem é o serviço.
--   'nao_mei' → só para quem ainda não é MEI (ex.: Abertura de MEI)
--   'mei'     → só para quem já é MEI (ex.: Boleto DAS)
--   'todos'   → qualquer empreendedor
-- O dado é semeado aqui; a FILTRAGEM da tela por tipo de pessoa não é escopo
-- desta etapa — a tela mostra todos os serviços por ora.
--
-- Seguro para re-execução: CREATE TABLE/INDEX IF NOT EXISTS, e o seed usa
-- WHERE NOT EXISTS por descrição.

-- ── Catálogo de serviços ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS servico (
    id             SERIAL       PRIMARY KEY,
    descricao      VARCHAR(100) NOT NULL,
    ativo          BOOLEAN      NOT NULL DEFAULT TRUE,
    protegido      BOOLEAN      NOT NULL DEFAULT FALSE,
    link_portal    VARCHAR(300),
    instrucao      TEXT,
    aplicabilidade VARCHAR(20)  NOT NULL DEFAULT 'todos'
);

COMMENT ON TABLE servico IS
    'O que foi feito no atendimento. Um atendimento tem VÁRIOS serviços.';
COMMENT ON COLUMN servico.aplicabilidade IS
    'nao_mei | mei | todos — para quem o serviço se aplica';
COMMENT ON COLUMN servico.link_portal IS
    'Portal externo que o botão abre. Migrado do array hardcoded em iniciar.html.';

-- ── Vínculo N:N atendimento ↔ serviço ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atendimento_servico (
    id_atendimento INTEGER NOT NULL REFERENCES atendimento(id),
    id_servico     INTEGER NOT NULL REFERENCES servico(id),
    PRIMARY KEY (id_atendimento, id_servico)
);

CREATE INDEX IF NOT EXISTS idx_atendimento_servico_atendimento
    ON atendimento_servico(id_atendimento);
CREATE INDEX IF NOT EXISTS idx_atendimento_servico_servico
    ON atendimento_servico(id_servico);

-- ── Seed dos 9 serviços ──────────────────────────────────────────────────────
-- Os links vêm do array SERVICOS de app/templates/atendimentos/iniciar.html.
-- Todos são `protegido` — são o catálogo operacional da Sala, não devem ser
-- removidos por engano pelo CRUD de /tabelas/.
INSERT INTO servico (descricao, aplicabilidade, link_portal, ativo, protegido)
SELECT v.descricao, v.aplicabilidade, v.link_portal, TRUE, TRUE
FROM (VALUES
    ('Abertura de MEI',            'nao_mei',
     'https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/quero-ser-mei'),
    ('Boleto DAS',                 'mei',
     'https://www8.receita.fazenda.gov.br/simplesnacional/aplicacoes/atspo/pgmei.app/identificacao'),
    ('Parcelamento DAS',           'mei',
     'https://www8.receita.fazenda.gov.br/SimplesNacional/Servicos/Grupo.aspx?grp=19'),
    ('Baixa de MEI',               'mei',
     'https://mei.receita.economia.gov.br/baixa/login'),
    ('Emissão de Documento',       'mei',
     'https://mei.receita.economia.gov.br/certificado/login'),
    -- A consulta de CNPJ recebe o número na própria URL; o JS concatena os
    -- dígitos ao final deste link.
    ('Consulta Cadastral',         'mei',
     'https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj='),
    ('Orientação ao Empreendedor', 'todos', NULL),
    ('Cadastro de Box/Quiosque',   'todos', NULL),
    ('Solicitação',                'todos', NULL)
) AS v(descricao, aplicabilidade, link_portal)
WHERE NOT EXISTS (SELECT 1 FROM servico s WHERE s.descricao = v.descricao);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('013_servico_e_vinculo.sql')
ON CONFLICT (migration) DO NOTHING;
