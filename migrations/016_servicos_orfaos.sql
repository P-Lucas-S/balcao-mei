-- 016_servicos_orfaos.sql
-- Completa o catálogo de serviços com três que ficaram de fora na Etapa 2.
--
-- Contexto: o array `SERVICOS` hardcoded em `iniciar.html` tinha 9 botões, e o
-- seed da migration 013 também tinha 9 serviços — mas não eram os mesmos. Três
-- botões do JS antigo não encontraram serviço correspondente e seus links
-- ficaram órfãos quando o array foi substituído pelo catálogo do banco:
--
--   * Declaração Anual (DASN-SIMEI)
--   * Alterar Dados do MEI
--   * Regularizar Débitos
--
-- São serviços reais prestados pela Sala. Os `link_portal` abaixo são
-- exatamente os que estavam no array antes da Etapa 2, recuperados do commit
-- f21038b^ — não foram reconstruídos de memória.
--
-- Todos com aplicabilidade 'mei': as três operações exigem CNPJ de MEI ativo.
--
-- Seguro para re-execução: o seed usa WHERE NOT EXISTS por descrição.

INSERT INTO servico (descricao, aplicabilidade, link_portal, ativo, protegido)
SELECT v.descricao, v.aplicabilidade, v.link_portal, TRUE, TRUE
FROM (VALUES
    ('Declaração Anual (DASN-SIMEI)', 'mei',
     'https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/dasnsimei.app/Identificacao'),
    ('Alterar Dados do MEI',          'mei',
     'https://mei.receita.economia.gov.br/alteracao/acesso'),
    ('Regularizar Débitos',           'mei',
     'https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/verificar-debitos-do-mei')
) AS v(descricao, aplicabilidade, link_portal)
WHERE NOT EXISTS (SELECT 1 FROM servico s WHERE s.descricao = v.descricao);

-- Registro no controle de versão
INSERT INTO schema_migrations (migration) VALUES
    ('016_servicos_orfaos.sql')
ON CONFLICT (migration) DO NOTHING;
