-- ============================================================
-- migrations/002_sync_schema.sql
-- Sincroniza o schema do banco sistema_solicitacoes com os
-- models atuais do Balcão MEI (app/models.py).
--
-- Seguro para re-execução:
--   ADD COLUMN IF NOT EXISTS  → sem-op se coluna já existe
--   CREATE TABLE IF NOT EXISTS → sem-op se tabela já existe
--   CREATE INDEX IF NOT EXISTS → sem-op se índice já existe
-- ============================================================

-- ── perfil_acesso ────────────────────────────────────────────────────────────
ALTER TABLE perfil_acesso ADD COLUMN IF NOT EXISTS descricao TEXT;

-- ── usuario ──────────────────────────────────────────────────────────────────
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS ativo        BOOLEAN   DEFAULT TRUE;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS ultimo_login TIMESTAMP;

-- ── pessoa ───────────────────────────────────────────────────────────────────
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS email                    VARCHAR(150);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS cpf                      VARCHAR(14);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS cnpj                     VARCHAR(18);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS data_nascimento          DATE;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS telefone                 VARCHAR(20);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS endereco                 TEXT;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS cep                      VARCHAR(9);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS logradouro               VARCHAR(200);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS numero                   VARCHAR(20);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS complemento              VARCHAR(100);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS bairro                   VARCHAR(100);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS sexo                     VARCHAR(20);
-- Dados da Receita Federal
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS nome_fantasia            VARCHAR(150);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS situacao_cadastral       VARCHAR(50);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS data_situacao_cadastral  DATE;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS data_inicio_atividade    DATE;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS capital_social           VARCHAR(30);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS porte                    VARCHAR(50);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS natureza_juridica        VARCHAR(100);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS mei                      BOOLEAN;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS simples_nacional         BOOLEAN;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS cnae_principal           VARCHAR(200);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS cnae_secundario          TEXT;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS inscricao_estadual       VARCHAR(50);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS rg                       VARCHAR(20);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS nivel_escolar            VARCHAR(50);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS num_membros_familia      INTEGER;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS renda_familiar           VARCHAR(50);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS instagram                VARCHAR(100);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS endereco_comercial       TEXT;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS principais_produtos      TEXT;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS faturamento_mensal       VARCHAR(30);
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS num_funcionarios         INTEGER;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS observacoes_cadastro     TEXT;
-- Colunas de controle
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS exclusao_pendente        BOOLEAN   DEFAULT FALSE;
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS origem                   VARCHAR(50) DEFAULT 'operacional';
ALTER TABLE pessoa ADD COLUMN IF NOT EXISTS id_usuario_criador       INTEGER   REFERENCES usuario(id);

-- ── documento_pessoa ─────────────────────────────────────────────────────────
-- Tabela nova — criada apenas se ainda não existir.
CREATE TABLE IF NOT EXISTS documento_pessoa (
    id         SERIAL       PRIMARY KEY,
    id_pessoa  INTEGER      NOT NULL REFERENCES pessoa(id),
    tipo       VARCHAR(50)  NOT NULL,
    descricao  VARCHAR(150),
    arquivo    VARCHAR(255) NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    ativo      BOOLEAN      NOT NULL DEFAULT TRUE,
    id_usuario INTEGER      REFERENCES usuario(id)
);

-- ── tipo_atendimento ─────────────────────────────────────────────────────────
ALTER TABLE tipo_atendimento ADD COLUMN IF NOT EXISTS ativo       BOOLEAN      DEFAULT TRUE;
ALTER TABLE tipo_atendimento ADD COLUMN IF NOT EXISTS protegido   BOOLEAN      DEFAULT FALSE;
ALTER TABLE tipo_atendimento ADD COLUMN IF NOT EXISTS link_portal VARCHAR(300);
ALTER TABLE tipo_atendimento ADD COLUMN IF NOT EXISTS instrucao   TEXT;

-- ── atendimento ──────────────────────────────────────────────────────────────
ALTER TABLE atendimento ADD COLUMN IF NOT EXISTS observacao        TEXT;
ALTER TABLE atendimento ADD COLUMN IF NOT EXISTS created_at        TIMESTAMP DEFAULT NOW();
ALTER TABLE atendimento ADD COLUMN IF NOT EXISTS exclusao_pendente BOOLEAN   DEFAULT FALSE;
ALTER TABLE atendimento ADD COLUMN IF NOT EXISTS origem            VARCHAR(50) DEFAULT 'operacional';

-- ── tipo_solicitacao ─────────────────────────────────────────────────────────
ALTER TABLE tipo_solicitacao ADD COLUMN IF NOT EXISTS ativo     BOOLEAN DEFAULT TRUE;
ALTER TABLE tipo_solicitacao ADD COLUMN IF NOT EXISTS protegido BOOLEAN DEFAULT FALSE;
ALTER TABLE tipo_solicitacao ADD COLUMN IF NOT EXISTS validade  DATE;

-- ── evento ───────────────────────────────────────────────────────────────────
ALTER TABLE evento ADD COLUMN IF NOT EXISTS data_inicio DATE;
ALTER TABLE evento ADD COLUMN IF NOT EXISTS data_fim    DATE;

-- ── atividade ────────────────────────────────────────────────────────────────
-- Sem colunas além das já obrigatórias (id, descricao).

-- ── solicitacao ──────────────────────────────────────────────────────────────
ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS descricao          TEXT;
ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS observacao          TEXT;
ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS id_evento           INTEGER REFERENCES evento(id);
ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS id_atividade        INTEGER REFERENCES atividade(id);
ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS exclusao_pendente   BOOLEAN DEFAULT FALSE;

-- ── log_acao ─────────────────────────────────────────────────────────────────
-- Criada se não existir (tabela nova em relação ao schema original).
CREATE TABLE IF NOT EXISTS log_acao (
    id          SERIAL      PRIMARY KEY,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    id_usuario  INTEGER     REFERENCES usuario(id),
    acao        VARCHAR(50) NOT NULL,
    entidade    VARCHAR(50) NOT NULL,
    entidade_id INTEGER,
    descricao   TEXT        NOT NULL
);
ALTER TABLE log_acao ADD COLUMN IF NOT EXISTS entidade_id INTEGER;

-- ── solicitacao_exclusao ─────────────────────────────────────────────────────
-- Criada se não existir (tabela nova em relação ao schema original).
CREATE TABLE IF NOT EXISTS solicitacao_exclusao (
    id                     SERIAL       PRIMARY KEY,
    entidade               VARCHAR(20)  NOT NULL,
    entidade_id            INTEGER      NOT NULL,
    entidade_desc          VARCHAR(200) NOT NULL,
    id_usuario_solicitante INTEGER      NOT NULL REFERENCES usuario(id),
    created_at             TIMESTAMP    NOT NULL DEFAULT NOW(),
    motivo                 TEXT,
    motivo_negacao         TEXT,
    status                 VARCHAR(20)  NOT NULL DEFAULT 'pendente'
);
ALTER TABLE solicitacao_exclusao ADD COLUMN IF NOT EXISTS entidade_desc   VARCHAR(200);
ALTER TABLE solicitacao_exclusao ADD COLUMN IF NOT EXISTS motivo_negacao   TEXT;

-- ── requerimento_gerado ──────────────────────────────────────────────────────
-- Tabela nova — criada apenas se ainda não existir.
CREATE TABLE IF NOT EXISTS requerimento_gerado (
    id                    SERIAL       PRIMARY KEY,
    protocolo             VARCHAR(20)  NOT NULL UNIQUE,
    created_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
    id_usuario            INTEGER      REFERENCES usuario(id),
    id_pessoa             INTEGER      REFERENCES pessoa(id),
    nome_manual           VARCHAR(150),
    cpf_manual            VARCHAR(14),
    cnpj_manual           VARCHAR(18),
    credenciamento_evento VARCHAR(200),
    solicitacao           TEXT,
    id_solicitacao        INTEGER      REFERENCES solicitacao(id)
);

-- ── parametros_municipio ─────────────────────────────────────────────────────
-- Criada se não existir (tabela nova em relação ao schema original).
CREATE TABLE IF NOT EXISTS parametros_municipio (
    id         SERIAL       PRIMARY KEY,
    chave      VARCHAR(100) NOT NULL UNIQUE,
    valor      VARCHAR(200) NOT NULL,
    descricao  TEXT,
    updated_at TIMESTAMP    NOT NULL DEFAULT NOW()
);
ALTER TABLE parametros_municipio ADD COLUMN IF NOT EXISTS descricao  TEXT;
ALTER TABLE parametros_municipio ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- ── lote_importacao ──────────────────────────────────────────────────────────
-- Tabela nova — criada apenas se ainda não existir.
CREATE TABLE IF NOT EXISTS lote_importacao (
    id                SERIAL       PRIMARY KEY,
    data_execucao     TIMESTAMP    NOT NULL DEFAULT NOW(),
    responsavel       VARCHAR(100) NOT NULL,
    nome_arquivo      VARCHAR(255),
    hash_md5          VARCHAR(32),
    total_linhas      INTEGER,
    linhas_importadas INTEGER,
    linhas_ignoradas  INTEGER,
    linhas_com_erro   INTEGER,
    observacoes       TEXT
);

-- ── Índices de performance ────────────────────────────────────────────────────
-- Coluna de data de atendimento (filtragens frequentes no dashboard e análise)
CREATE INDEX IF NOT EXISTS idx_atendimento_data_hora
    ON atendimento(data_atendimento);

-- Coluna de data de solicitação (filtros, alertas de paradas, exportações)
CREATE INDEX IF NOT EXISTS idx_solicitacao_data_criacao
    ON solicitacao(data_solicitacao);

-- Nome do empreendedor (busca global e listagem de pessoas)
CREATE INDEX IF NOT EXISTS idx_pessoa_nome
    ON pessoa(nome_razao_social);
