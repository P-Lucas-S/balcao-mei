--
-- PostgreSQL database dump
--

\restrict vE1x1MhAFbTHSy4dyccaus4aFhML14oNAKTjFpUZtXhSyyglmNYiDsqghKSqdsU

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: atendimento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.atendimento (
    id integer NOT NULL,
    data_atendimento date NOT NULL,
    hora_atendimento time without time zone NOT NULL,
    observacao text,
    id_usuario integer NOT NULL,
    id_pessoa integer NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    exclusao_pendente boolean DEFAULT false,
    origem character varying(50) DEFAULT 'operacional'::character varying
);


--
-- Name: atendimento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.atendimento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: atendimento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.atendimento_id_seq OWNED BY public.atendimento.id;


--
-- Name: atendimento_tipo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.atendimento_tipo (
    id_atendimento integer NOT NULL,
    id_tipo_atendimento integer NOT NULL
);


--
-- Name: atividade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.atividade (
    id integer NOT NULL,
    descricao character varying(150) NOT NULL
);


--
-- Name: atividade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.atividade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: atividade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.atividade_id_seq OWNED BY public.atividade.id;


--
-- Name: documento_pessoa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento_pessoa (
    id integer NOT NULL,
    id_pessoa integer NOT NULL,
    tipo character varying(50) NOT NULL,
    descricao character varying(150),
    arquivo character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    id_usuario integer
);


--
-- Name: documento_pessoa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documento_pessoa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_pessoa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documento_pessoa_id_seq OWNED BY public.documento_pessoa.id;


--
-- Name: evento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evento (
    id integer NOT NULL,
    descricao character varying(150),
    data_inicio date,
    data_fim date
);


--
-- Name: evento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evento_id_seq OWNED BY public.evento.id;


--
-- Name: log_acao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_acao (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    id_usuario integer,
    acao character varying(50) NOT NULL,
    entidade character varying(50) NOT NULL,
    entidade_id integer,
    descricao text NOT NULL
);


--
-- Name: log_acao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_acao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_acao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_acao_id_seq OWNED BY public.log_acao.id;


--
-- Name: lote_importacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lote_importacao (
    id integer NOT NULL,
    data_execucao timestamp without time zone DEFAULT now() NOT NULL,
    responsavel character varying(100) NOT NULL,
    nome_arquivo character varying(255),
    hash_md5 character varying(32),
    total_linhas integer,
    linhas_importadas integer,
    linhas_ignoradas integer,
    linhas_com_erro integer,
    observacoes text
);


--
-- Name: lote_importacao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lote_importacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lote_importacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lote_importacao_id_seq OWNED BY public.lote_importacao.id;


--
-- Name: parametros_municipio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parametros_municipio (
    id integer NOT NULL,
    chave character varying(100) NOT NULL,
    valor text NOT NULL,
    descricao text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: parametros_municipio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parametros_municipio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parametros_municipio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parametros_municipio_id_seq OWNED BY public.parametros_municipio.id;


--
-- Name: perfil_acesso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfil_acesso (
    id integer NOT NULL,
    nome character varying(50) NOT NULL,
    descricao text
);


--
-- Name: perfil_acesso_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perfil_acesso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfil_acesso_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perfil_acesso_id_seq OWNED BY public.perfil_acesso.id;


--
-- Name: pessoa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoa (
    id integer NOT NULL,
    nome_razao_social character varying(150) NOT NULL,
    email character varying(150),
    cpf character varying(14),
    cnpj character varying(18),
    data_nascimento date,
    telefone character varying(20),
    endereco text,
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    sexo character varying(20),
    nome_fantasia character varying(150),
    situacao_cadastral character varying(50),
    data_situacao_cadastral date,
    data_inicio_atividade date,
    capital_social character varying(30),
    porte character varying(50),
    natureza_juridica character varying(100),
    mei boolean,
    simples_nacional boolean,
    cnae_principal character varying(200),
    cnae_secundario text,
    inscricao_estadual character varying(50),
    rg character varying(20),
    nivel_escolar character varying(50),
    num_membros_familia integer,
    renda_familiar character varying(50),
    instagram character varying(100),
    endereco_comercial text,
    principais_produtos text,
    faturamento_mensal character varying(30),
    num_funcionarios integer,
    observacoes_cadastro text,
    exclusao_pendente boolean DEFAULT false,
    origem character varying(50) DEFAULT 'operacional'::character varying,
    id_usuario_criador integer,
    aceite_whatsapp boolean DEFAULT false NOT NULL,
    data_aceite_whatsapp timestamp without time zone,
    data_revogacao_whatsapp timestamp without time zone
);


--
-- Name: pessoa_atividade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoa_atividade (
    id_pessoa integer NOT NULL,
    id_atividade integer NOT NULL
);


--
-- Name: pessoa_fisica; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoa_fisica (
    id_pessoa integer NOT NULL,
    cpf character(11) NOT NULL,
    data_nascimento date
);


--
-- Name: pessoa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pessoa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pessoa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pessoa_id_seq OWNED BY public.pessoa.id;


--
-- Name: pessoa_juridica; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoa_juridica (
    id_pessoa integer NOT NULL,
    cnpj character(14) NOT NULL,
    nome_fantasia character varying(150)
);


--
-- Name: pessoa_tag; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoa_tag (
    id_pessoa integer NOT NULL,
    id_tag integer NOT NULL
);


--
-- Name: requerimento_gerado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.requerimento_gerado (
    id integer NOT NULL,
    protocolo character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    id_usuario integer,
    id_pessoa integer,
    nome_manual character varying(150),
    cpf_manual character varying(14),
    cnpj_manual character varying(18),
    credenciamento_evento character varying(200),
    solicitacao text,
    id_solicitacao integer,
    modo_emissao character varying(20),
    status_requerimento character varying(20) DEFAULT 'gerado'::character varying,
    observacao_manual text
);


--
-- Name: requerimento_gerado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.requerimento_gerado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: requerimento_gerado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.requerimento_gerado_id_seq OWNED BY public.requerimento_gerado.id;


--
-- Name: responsabilidade_pj; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.responsabilidade_pj (
    id integer NOT NULL,
    id_pessoa_fisica integer NOT NULL,
    id_pessoa_juridica integer NOT NULL,
    data_inicio date NOT NULL,
    data_fim date,
    ativo boolean DEFAULT true NOT NULL
);


--
-- Name: responsabilidade_pj_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.responsabilidade_pj_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: responsabilidade_pj_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.responsabilidade_pj_id_seq OWNED BY public.responsabilidade_pj.id;


--
-- Name: solicitacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitacao (
    id integer NOT NULL,
    data_solicitacao date NOT NULL,
    descricao text,
    observacao text,
    id_usuario integer NOT NULL,
    id_pessoa integer NOT NULL,
    id_tipo_solicitacao integer NOT NULL,
    id_status integer NOT NULL,
    id_evento integer,
    id_atividade integer,
    exclusao_pendente boolean DEFAULT false,
    atendimento_id integer
);


--
-- Name: solicitacao_exclusao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitacao_exclusao (
    id integer NOT NULL,
    entidade character varying(20) NOT NULL,
    entidade_id integer NOT NULL,
    entidade_desc character varying(200) NOT NULL,
    id_usuario_solicitante integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    motivo text,
    motivo_negacao text,
    status character varying(20) DEFAULT 'pendente'::character varying NOT NULL
);


--
-- Name: solicitacao_exclusao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitacao_exclusao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacao_exclusao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitacao_exclusao_id_seq OWNED BY public.solicitacao_exclusao.id;


--
-- Name: solicitacao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitacao_id_seq OWNED BY public.solicitacao.id;


--
-- Name: status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.status (
    id integer NOT NULL,
    descricao character varying(50) NOT NULL
);


--
-- Name: status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.status_id_seq OWNED BY public.status.id;


--
-- Name: tag_interesse; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tag_interesse (
    id integer NOT NULL,
    descricao character varying(100) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    protegido boolean DEFAULT false NOT NULL
);


--
-- Name: tag_interesse_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tag_interesse_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tag_interesse_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tag_interesse_id_seq OWNED BY public.tag_interesse.id;


--
-- Name: telefone_pessoa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telefone_pessoa (
    id integer NOT NULL,
    id_pessoa integer NOT NULL,
    telefone character varying(20) NOT NULL
);


--
-- Name: telefone_pessoa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.telefone_pessoa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: telefone_pessoa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.telefone_pessoa_id_seq OWNED BY public.telefone_pessoa.id;


--
-- Name: tipo_atendimento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipo_atendimento (
    id integer NOT NULL,
    descricao character varying(100) NOT NULL,
    ativo boolean DEFAULT true,
    protegido boolean DEFAULT false,
    link_portal character varying(300),
    instrucao text
);


--
-- Name: tipo_atendimento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tipo_atendimento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_atendimento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tipo_atendimento_id_seq OWNED BY public.tipo_atendimento.id;


--
-- Name: tipo_solicitacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipo_solicitacao (
    id integer NOT NULL,
    descricao character varying(100) NOT NULL,
    ativo boolean DEFAULT true,
    protegido boolean DEFAULT false,
    validade date
);


--
-- Name: tipo_solicitacao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tipo_solicitacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_solicitacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tipo_solicitacao_id_seq OWNED BY public.tipo_solicitacao.id;


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    login character varying(50) NOT NULL,
    senha character varying(255) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    id_perfil integer NOT NULL,
    ultimo_login timestamp without time zone,
    supervisor_id integer
);


--
-- Name: usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_id_seq OWNED BY public.usuario.id;


--
-- Name: atendimento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento ALTER COLUMN id SET DEFAULT nextval('public.atendimento_id_seq'::regclass);


--
-- Name: atividade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atividade ALTER COLUMN id SET DEFAULT nextval('public.atividade_id_seq'::regclass);


--
-- Name: documento_pessoa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_pessoa ALTER COLUMN id SET DEFAULT nextval('public.documento_pessoa_id_seq'::regclass);


--
-- Name: evento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento ALTER COLUMN id SET DEFAULT nextval('public.evento_id_seq'::regclass);


--
-- Name: log_acao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao ALTER COLUMN id SET DEFAULT nextval('public.log_acao_id_seq'::regclass);


--
-- Name: lote_importacao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lote_importacao ALTER COLUMN id SET DEFAULT nextval('public.lote_importacao_id_seq'::regclass);


--
-- Name: parametros_municipio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_municipio ALTER COLUMN id SET DEFAULT nextval('public.parametros_municipio_id_seq'::regclass);


--
-- Name: perfil_acesso id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso ALTER COLUMN id SET DEFAULT nextval('public.perfil_acesso_id_seq'::regclass);


--
-- Name: pessoa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa ALTER COLUMN id SET DEFAULT nextval('public.pessoa_id_seq'::regclass);


--
-- Name: requerimento_gerado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado ALTER COLUMN id SET DEFAULT nextval('public.requerimento_gerado_id_seq'::regclass);


--
-- Name: responsabilidade_pj id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.responsabilidade_pj ALTER COLUMN id SET DEFAULT nextval('public.responsabilidade_pj_id_seq'::regclass);


--
-- Name: solicitacao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao ALTER COLUMN id SET DEFAULT nextval('public.solicitacao_id_seq'::regclass);


--
-- Name: solicitacao_exclusao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao_exclusao ALTER COLUMN id SET DEFAULT nextval('public.solicitacao_exclusao_id_seq'::regclass);


--
-- Name: status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.status ALTER COLUMN id SET DEFAULT nextval('public.status_id_seq'::regclass);


--
-- Name: tag_interesse id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tag_interesse ALTER COLUMN id SET DEFAULT nextval('public.tag_interesse_id_seq'::regclass);


--
-- Name: telefone_pessoa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telefone_pessoa ALTER COLUMN id SET DEFAULT nextval('public.telefone_pessoa_id_seq'::regclass);


--
-- Name: tipo_atendimento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_atendimento ALTER COLUMN id SET DEFAULT nextval('public.tipo_atendimento_id_seq'::regclass);


--
-- Name: tipo_solicitacao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_solicitacao ALTER COLUMN id SET DEFAULT nextval('public.tipo_solicitacao_id_seq'::regclass);


--
-- Name: usuario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id SET DEFAULT nextval('public.usuario_id_seq'::regclass);


--
-- Name: atendimento atendimento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_pkey PRIMARY KEY (id);


--
-- Name: atendimento_tipo atendimento_tipo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento_tipo
    ADD CONSTRAINT atendimento_tipo_pkey PRIMARY KEY (id_atendimento, id_tipo_atendimento);


--
-- Name: atividade atividade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atividade
    ADD CONSTRAINT atividade_pkey PRIMARY KEY (id);


--
-- Name: documento_pessoa documento_pessoa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_pessoa
    ADD CONSTRAINT documento_pessoa_pkey PRIMARY KEY (id);


--
-- Name: evento evento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_pkey PRIMARY KEY (id);


--
-- Name: log_acao log_acao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao
    ADD CONSTRAINT log_acao_pkey PRIMARY KEY (id);


--
-- Name: lote_importacao lote_importacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lote_importacao
    ADD CONSTRAINT lote_importacao_pkey PRIMARY KEY (id);


--
-- Name: parametros_municipio parametros_municipio_chave_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_municipio
    ADD CONSTRAINT parametros_municipio_chave_key UNIQUE (chave);


--
-- Name: parametros_municipio parametros_municipio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_municipio
    ADD CONSTRAINT parametros_municipio_pkey PRIMARY KEY (id);


--
-- Name: perfil_acesso perfil_acesso_nome_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso
    ADD CONSTRAINT perfil_acesso_nome_key UNIQUE (nome);


--
-- Name: perfil_acesso perfil_acesso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso
    ADD CONSTRAINT perfil_acesso_pkey PRIMARY KEY (id);


--
-- Name: pessoa_atividade pessoa_atividade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_atividade
    ADD CONSTRAINT pessoa_atividade_pkey PRIMARY KEY (id_pessoa, id_atividade);


--
-- Name: pessoa_fisica pessoa_fisica_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_fisica
    ADD CONSTRAINT pessoa_fisica_cpf_key UNIQUE (cpf);


--
-- Name: pessoa_fisica pessoa_fisica_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_fisica
    ADD CONSTRAINT pessoa_fisica_pkey PRIMARY KEY (id_pessoa);


--
-- Name: pessoa_juridica pessoa_juridica_cnpj_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_juridica
    ADD CONSTRAINT pessoa_juridica_cnpj_key UNIQUE (cnpj);


--
-- Name: pessoa_juridica pessoa_juridica_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_juridica
    ADD CONSTRAINT pessoa_juridica_pkey PRIMARY KEY (id_pessoa);


--
-- Name: pessoa pessoa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa
    ADD CONSTRAINT pessoa_pkey PRIMARY KEY (id);


--
-- Name: pessoa_tag pessoa_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_tag
    ADD CONSTRAINT pessoa_tag_pkey PRIMARY KEY (id_pessoa, id_tag);


--
-- Name: requerimento_gerado requerimento_gerado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado
    ADD CONSTRAINT requerimento_gerado_pkey PRIMARY KEY (id);


--
-- Name: requerimento_gerado requerimento_gerado_protocolo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado
    ADD CONSTRAINT requerimento_gerado_protocolo_key UNIQUE (protocolo);


--
-- Name: responsabilidade_pj responsabilidade_pj_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.responsabilidade_pj
    ADD CONSTRAINT responsabilidade_pj_pkey PRIMARY KEY (id);


--
-- Name: solicitacao_exclusao solicitacao_exclusao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao_exclusao
    ADD CONSTRAINT solicitacao_exclusao_pkey PRIMARY KEY (id);


--
-- Name: solicitacao solicitacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_pkey PRIMARY KEY (id);


--
-- Name: status status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.status
    ADD CONSTRAINT status_pkey PRIMARY KEY (id);


--
-- Name: tag_interesse tag_interesse_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tag_interesse
    ADD CONSTRAINT tag_interesse_pkey PRIMARY KEY (id);


--
-- Name: telefone_pessoa telefone_pessoa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telefone_pessoa
    ADD CONSTRAINT telefone_pessoa_pkey PRIMARY KEY (id);


--
-- Name: tipo_atendimento tipo_atendimento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_atendimento
    ADD CONSTRAINT tipo_atendimento_pkey PRIMARY KEY (id);


--
-- Name: tipo_solicitacao tipo_solicitacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_solicitacao
    ADD CONSTRAINT tipo_solicitacao_pkey PRIMARY KEY (id);


--
-- Name: usuario usuario_login_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_login_key UNIQUE (login);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id);


--
-- Name: idx_atendimento_data_hora; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atendimento_data_hora ON public.atendimento USING btree (data_atendimento);


--
-- Name: idx_pessoa_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pessoa_nome ON public.pessoa USING btree (nome_razao_social);


--
-- Name: idx_pessoa_tag_pessoa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pessoa_tag_pessoa ON public.pessoa_tag USING btree (id_pessoa);


--
-- Name: idx_pessoa_tag_tag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pessoa_tag_tag ON public.pessoa_tag USING btree (id_tag);


--
-- Name: idx_solicitacao_atendimento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solicitacao_atendimento_id ON public.solicitacao USING btree (atendimento_id);


--
-- Name: idx_solicitacao_data_criacao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solicitacao_data_criacao ON public.solicitacao USING btree (data_solicitacao);


--
-- Name: idx_usuario_supervisor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usuario_supervisor_id ON public.usuario USING btree (supervisor_id);


--
-- Name: atendimento atendimento_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: atendimento atendimento_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id);


--
-- Name: atendimento_tipo atendimento_tipo_id_atendimento_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento_tipo
    ADD CONSTRAINT atendimento_tipo_id_atendimento_fkey FOREIGN KEY (id_atendimento) REFERENCES public.atendimento(id);


--
-- Name: atendimento_tipo atendimento_tipo_id_tipo_atendimento_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento_tipo
    ADD CONSTRAINT atendimento_tipo_id_tipo_atendimento_fkey FOREIGN KEY (id_tipo_atendimento) REFERENCES public.tipo_atendimento(id);


--
-- Name: documento_pessoa documento_pessoa_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_pessoa
    ADD CONSTRAINT documento_pessoa_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: documento_pessoa documento_pessoa_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_pessoa
    ADD CONSTRAINT documento_pessoa_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id);


--
-- Name: usuario fk_usuario_perfil; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT fk_usuario_perfil FOREIGN KEY (id_perfil) REFERENCES public.perfil_acesso(id);


--
-- Name: log_acao log_acao_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao
    ADD CONSTRAINT log_acao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id);


--
-- Name: pessoa_atividade pessoa_atividade_id_atividade_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_atividade
    ADD CONSTRAINT pessoa_atividade_id_atividade_fkey FOREIGN KEY (id_atividade) REFERENCES public.atividade(id);


--
-- Name: pessoa_atividade pessoa_atividade_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_atividade
    ADD CONSTRAINT pessoa_atividade_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: pessoa_fisica pessoa_fisica_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_fisica
    ADD CONSTRAINT pessoa_fisica_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: pessoa pessoa_id_usuario_criador_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa
    ADD CONSTRAINT pessoa_id_usuario_criador_fkey FOREIGN KEY (id_usuario_criador) REFERENCES public.usuario(id);


--
-- Name: pessoa_juridica pessoa_juridica_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_juridica
    ADD CONSTRAINT pessoa_juridica_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: pessoa_tag pessoa_tag_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_tag
    ADD CONSTRAINT pessoa_tag_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id) ON DELETE CASCADE;


--
-- Name: pessoa_tag pessoa_tag_id_tag_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoa_tag
    ADD CONSTRAINT pessoa_tag_id_tag_fkey FOREIGN KEY (id_tag) REFERENCES public.tag_interesse(id) ON DELETE CASCADE;


--
-- Name: requerimento_gerado requerimento_gerado_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado
    ADD CONSTRAINT requerimento_gerado_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: requerimento_gerado requerimento_gerado_id_solicitacao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado
    ADD CONSTRAINT requerimento_gerado_id_solicitacao_fkey FOREIGN KEY (id_solicitacao) REFERENCES public.solicitacao(id);


--
-- Name: requerimento_gerado requerimento_gerado_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requerimento_gerado
    ADD CONSTRAINT requerimento_gerado_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id);


--
-- Name: responsabilidade_pj responsabilidade_pj_id_pessoa_fisica_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.responsabilidade_pj
    ADD CONSTRAINT responsabilidade_pj_id_pessoa_fisica_fkey FOREIGN KEY (id_pessoa_fisica) REFERENCES public.pessoa_fisica(id_pessoa);


--
-- Name: responsabilidade_pj responsabilidade_pj_id_pessoa_juridica_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.responsabilidade_pj
    ADD CONSTRAINT responsabilidade_pj_id_pessoa_juridica_fkey FOREIGN KEY (id_pessoa_juridica) REFERENCES public.pessoa_juridica(id_pessoa);


--
-- Name: solicitacao solicitacao_atendimento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_atendimento_id_fkey FOREIGN KEY (atendimento_id) REFERENCES public.atendimento(id) ON DELETE SET NULL;


--
-- Name: solicitacao_exclusao solicitacao_exclusao_id_usuario_solicitante_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao_exclusao
    ADD CONSTRAINT solicitacao_exclusao_id_usuario_solicitante_fkey FOREIGN KEY (id_usuario_solicitante) REFERENCES public.usuario(id);


--
-- Name: solicitacao solicitacao_id_atividade_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_atividade_fkey FOREIGN KEY (id_atividade) REFERENCES public.atividade(id);


--
-- Name: solicitacao solicitacao_id_evento_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_evento_fkey FOREIGN KEY (id_evento) REFERENCES public.evento(id);


--
-- Name: solicitacao solicitacao_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: solicitacao solicitacao_id_status_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_status_fkey FOREIGN KEY (id_status) REFERENCES public.status(id);


--
-- Name: solicitacao solicitacao_id_tipo_solicitacao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_tipo_solicitacao_fkey FOREIGN KEY (id_tipo_solicitacao) REFERENCES public.tipo_solicitacao(id);


--
-- Name: solicitacao solicitacao_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacao
    ADD CONSTRAINT solicitacao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id);


--
-- Name: telefone_pessoa telefone_pessoa_id_pessoa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telefone_pessoa
    ADD CONSTRAINT telefone_pessoa_id_pessoa_fkey FOREIGN KEY (id_pessoa) REFERENCES public.pessoa(id);


--
-- Name: usuario usuario_supervisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_supervisor_id_fkey FOREIGN KEY (supervisor_id) REFERENCES public.usuario(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict vE1x1MhAFbTHSy4dyccaus4aFhML14oNAKTjFpUZtXhSyyglmNYiDsqghKSqdsU

