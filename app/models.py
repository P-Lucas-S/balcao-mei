from datetime import datetime, timezone
from flask_login import UserMixin
from . import db


class PerfilAcesso(db.Model):
    __tablename__ = 'perfil_acesso'

    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(50), nullable=False, unique=True)
    descricao = db.Column(db.Text)

    usuarios = db.relationship('Usuario', back_populates='perfil')


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(100), nullable=False)
    login     = db.Column(db.String(50),  nullable=False, unique=True)
    senha     = db.Column(db.String(255), nullable=False)
    ativo        = db.Column(db.Boolean, nullable=False, default=True)
    id_perfil    = db.Column(db.Integer, db.ForeignKey('perfil_acesso.id'), nullable=False)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id', ondelete='SET NULL'),
        nullable=True,
    )

    perfil       = db.relationship('PerfilAcesso', back_populates='usuarios')
    atendimentos = db.relationship('Atendimento',  back_populates='usuario')
    solicitacoes = db.relationship('Solicitacao',  back_populates='usuario')
    supervisor   = db.relationship(
        'Usuario',
        remote_side='Usuario.id',
        backref=db.backref('atendentes', lazy='dynamic'),
        foreign_keys='[Usuario.supervisor_id]',
    )

    @property
    def is_active(self):
        return self.ativo


class Pessoa(db.Model):
    __tablename__ = 'pessoa'

    id               = db.Column(db.Integer, primary_key=True)
    nome_razao_social = db.Column(db.String(150), nullable=False)
    email            = db.Column(db.String(150))
    cpf              = db.Column(db.String(14))
    cnpj             = db.Column(db.String(18))
    data_nascimento  = db.Column(db.Date)
    telefone         = db.Column(db.String(20))
    endereco         = db.Column(db.Text)
    cep              = db.Column(db.String(9))
    logradouro       = db.Column(db.String(200))
    numero           = db.Column(db.String(20))
    complemento      = db.Column(db.String(100))
    bairro           = db.Column(db.String(100))
    sexo             = db.Column(db.String(20))

    # Dados da Receita Federal
    nome_fantasia           = db.Column(db.String(150))
    situacao_cadastral      = db.Column(db.String(50))
    data_situacao_cadastral = db.Column(db.Date)
    data_inicio_atividade   = db.Column(db.Date)
    capital_social          = db.Column(db.String(30))
    porte                   = db.Column(db.String(50))
    natureza_juridica       = db.Column(db.String(100))
    mei                     = db.Column(db.Boolean)
    simples_nacional        = db.Column(db.Boolean)
    cnae_principal          = db.Column(db.String(200))
    cnae_secundario         = db.Column(db.Text)
    inscricao_estadual      = db.Column(db.String(50))
    rg                      = db.Column(db.String(20))
    nivel_escolar           = db.Column(db.String(50))
    num_membros_familia     = db.Column(db.Integer)
    renda_familiar          = db.Column(db.String(50))
    instagram               = db.Column(db.String(100))
    endereco_comercial      = db.Column(db.Text)
    principais_produtos     = db.Column(db.Text)
    faturamento_mensal      = db.Column(db.String(30))
    num_funcionarios        = db.Column(db.Integer)
    observacoes_cadastro    = db.Column(db.Text)
    exclusao_pendente       = db.Column(db.Boolean, default=False, nullable=False, server_default='false')
    origem                  = db.Column(db.String(50), nullable=False,
                                        default='operacional', server_default='operacional')
    id_usuario_criador      = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    usuario_criador         = db.relationship('Usuario', foreign_keys=[id_usuario_criador])

    atendimentos = db.relationship('Atendimento', back_populates='pessoa')
    solicitacoes = db.relationship('Solicitacao', back_populates='pessoa')
    documentos   = db.relationship('DocumentoPessoa', back_populates='pessoa',
                                   order_by='DocumentoPessoa.created_at.desc()',
                                   cascade='all, delete-orphan')
    tags = db.relationship('TagInteresse', secondary='pessoa_tag',
                           backref=db.backref('pessoas', lazy='dynamic'))

    @property
    def documentos_visiveis(self):
        """Documentos não removidos logicamente.

        `documentos` continua trazendo tudo — é dele que depende o cascade
        `delete-orphan`. Toda exibição deve usar esta propriedade, senão o
        soft-delete vaza para a interface.
        """
        return [d for d in self.documentos if d.removido_em is None]

    aceite_whatsapp         = db.Column(db.Boolean, nullable=False, default=False)
    data_aceite_whatsapp    = db.Column(db.DateTime)
    data_revogacao_whatsapp = db.Column(db.DateTime)

    # Exclusão lógica — nada é apagado; o histórico vinculado permanece
    removido_em  = db.Column(db.DateTime, nullable=True)
    removido_por = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    remotor = db.relationship('Usuario', foreign_keys=[removido_por])

    @classmethod
    def visiveis(cls):
        """Query base para uso OPERACIONAL — exclui cadastros removidos.

        Usar em: lista de pessoas, busca global, seleção de pessoa ao criar
        atendimento/solicitação, verificação de duplicidade, mesclagem.

        NÃO usar em relatórios, análise ou estatísticas: lá o cadastro
        removido continua contando, porque o atendimento aconteceu e o
        trabalho da Sala não é apagado quando o empreendedor exerce direito
        de exclusão. Ver `02_REGRAS_DE_NEGOCIO.md`.
        """
        return cls.query.filter(cls.removido_em.is_(None))

    @property
    def removida(self):
        return self.removido_em is not None


class DocumentoPessoa(db.Model):
    __tablename__ = 'documento_pessoa'

    id         = db.Column(db.Integer, primary_key=True)
    id_pessoa  = db.Column(db.Integer, db.ForeignKey('pessoa.id'), nullable=False)
    tipo       = db.Column(db.String(50),  nullable=False)
    descricao  = db.Column(db.String(150))
    arquivo    = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # `ativo` = versionamento: False marca versão anterior do mesmo tipo.
    # NÃO confundir com exclusão — para isso existem os campos abaixo.
    ativo      = db.Column(db.Boolean, nullable=False, default=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    # Exclusão lógica — o arquivo em disco é preservado
    removido_em  = db.Column(db.DateTime, nullable=True)
    removido_por = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    pessoa  = db.relationship('Pessoa',   back_populates='documentos')
    usuario = db.relationship('Usuario',  foreign_keys=[id_usuario])
    remotor = db.relationship('Usuario',  foreign_keys=[removido_por])


# ── Canal × Serviço ───────────────────────────────────────────────────────────
# Duas dimensões diferentes, que até 2026-08-16 estavam fundidas numa tabela só
# (`tipo_atendimento`, renomeada para `canal_atendimento` na migration 014):
#   CANAL   — COMO o empreendedor chegou. Um atendimento tem UM canal.
#   SERVIÇO — O QUE foi feito. Um atendimento tem VÁRIOS serviços.

class CanalAtendimento(db.Model):
    """Como o empreendedor chegou: Presencial, Telefone, E-mail, WhatsApp."""
    __tablename__ = 'canal_atendimento'

    id        = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    ativo     = db.Column(db.Boolean, nullable=False, default=True)
    protegido = db.Column(db.Boolean, nullable=False, default=False)


# Para quem o serviço se aplica
APLIC_NAO_MEI = 'nao_mei'
APLIC_MEI     = 'mei'
APLIC_TODOS   = 'todos'
APLICABILIDADES = (APLIC_NAO_MEI, APLIC_MEI, APLIC_TODOS)

# ── Tipo efetivo do atendimento ───────────────────────────────────────────────
# É um estado DO ATENDIMENTO, não do cadastro. Nasce do tipo da pessoa
# selecionada e pode mudar durante o atendimento (ex.: a pessoa abre MEI no
# balcão). Reusa os mesmos dois valores de aplicabilidade, porque a regra de
# filtragem compara um com o outro:
#     exibe o serviço se  aplicabilidade == tipo_efetivo  ou  == 'todos'
TIPOS_EFETIVOS = (APLIC_NAO_MEI, APLIC_MEI)


def tipo_efetivo_de(pessoa):
    """Tipo efetivo INICIAL de um atendimento, derivado do cadastro.

    A partir daqui o valor vive no atendimento: a conversão PF→MEI durante o
    atendimento muda o tipo efetivo sem tocar no cadastro.
    """
    if pessoa is None:
        return APLIC_NAO_MEI
    return APLIC_MEI if (pessoa.mei or pessoa.cnpj) else APLIC_NAO_MEI


class Servico(db.Model):
    """O que foi feito: Boleto DAS, Abertura de MEI, Orientação…

    `link_portal` e `instrucao` vieram de `tipo_atendimento`, onde existiam
    desde a migration 002 mas nunca foram lidas por ninguém. Aqui finalmente
    cumprem a função para a qual foram criadas: o botão da tela guiada abre
    `link_portal` em vez do link hardcoded que ficava no JavaScript.
    """
    __tablename__ = 'servico'

    id             = db.Column(db.Integer, primary_key=True)
    descricao      = db.Column(db.String(100), nullable=False)
    ativo          = db.Column(db.Boolean, nullable=False, default=True)
    protegido      = db.Column(db.Boolean, nullable=False, default=False)
    link_portal    = db.Column(db.String(300))
    instrucao      = db.Column(db.Text)
    # nao_mei | mei | todos — a FILTRAGEM da tela por tipo de pessoa ainda não
    # está implementada; por ora o dado só é carregado e exibido.
    aplicabilidade = db.Column(db.String(20), nullable=False,
                               default=APLIC_TODOS, server_default=APLIC_TODOS)


class AtendimentoServico(db.Model):
    """Vínculo N:N atendimento ↔ serviço."""
    __tablename__ = 'atendimento_servico'

    id_atendimento = db.Column(db.Integer, db.ForeignKey('atendimento.id'), primary_key=True)
    id_servico     = db.Column(db.Integer, db.ForeignKey('servico.id'),     primary_key=True)

    # Snapshot do tipo efetivo quando ESTE serviço foi marcado. Existe para o
    # histórico não mudar retroativamente — um atendimento pode ter serviços
    # com tipos diferentes. NULL nos caminhos que não têm essa noção.
    tipo_efetivo = db.Column(db.String(20), nullable=True)
    # Marcado pela válvula de escape, fora da aplicabilidade do tipo efetivo.
    forcado      = db.Column(db.Boolean, nullable=False,
                             default=False, server_default='false')

    atendimento = db.relationship('Atendimento', back_populates='servicos')
    servico     = db.relationship('Servico')


# ── Status de atendimento ─────────────────────────────────────────────────────
# Dois valores internos e fixos, no mesmo padrão de `SolicitacaoExclusao.status`
# e `RequerimentoGerado.status_requerimento`: coluna VARCHAR com default.
#
# Não usa FK para a tabela `status` de propósito — aquela é o catálogo do
# workflow de SOLICITAÇÃO (Pendente/Em Análise/Aprovado/Recusado), configurável
# pelo admin em /tabelas/. Estes aqui não são configuráveis.
ATENDIMENTO_RASCUNHO  = 'rascunho'
ATENDIMENTO_CONCLUIDO = 'concluido'
ATENDIMENTO_STATUS    = (ATENDIMENTO_RASCUNHO, ATENDIMENTO_CONCLUIDO)


class Atendimento(db.Model):
    __tablename__ = 'atendimento'

    id                = db.Column(db.Integer, primary_key=True)
    data_atendimento  = db.Column(db.Date,    nullable=False)
    hora_atendimento  = db.Column(db.Time,    nullable=False)
    observacao        = db.Column(db.Text)
    created_at        = db.Column(db.DateTime, nullable=True, server_default=db.func.now())
    id_usuario        = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_pessoa         = db.Column(db.Integer, db.ForeignKey('pessoa.id'),  nullable=False)
    # UM canal por atendimento — como o empreendedor chegou
    id_canal          = db.Column(db.Integer, db.ForeignKey('canal_atendimento.id'),
                                  nullable=False)
    exclusao_pendente = db.Column(db.Boolean, default=False, nullable=False, server_default='false')
    origem            = db.Column(db.String(50), nullable=False,
                                  default='operacional', server_default='operacional')
    # 'rascunho' | 'concluido' — ver ATENDIMENTO_STATUS acima.
    # Default 'concluido': o fluxo atual grava o atendimento já finalizado.
    status            = db.Column(db.String(20), nullable=False,
                                  default=ATENDIMENTO_CONCLUIDO,
                                  server_default=ATENDIMENTO_CONCLUIDO)

    usuario  = db.relationship('Usuario', back_populates='atendimentos')
    pessoa   = db.relationship('Pessoa',  back_populates='atendimentos')
    canal    = db.relationship('CanalAtendimento')
    servicos = db.relationship('AtendimentoServico', back_populates='atendimento',
                               cascade='all, delete-orphan')

    @property
    def rascunho(self):
        return self.status == ATENDIMENTO_RASCUNHO

    @property
    def concluido(self):
        return self.status == ATENDIMENTO_CONCLUIDO


class Status(db.Model):
    __tablename__ = 'status'

    id       = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(50), nullable=False)

    solicitacoes = db.relationship('Solicitacao', back_populates='status')


class TipoSolicitacao(db.Model):
    __tablename__ = 'tipo_solicitacao'

    id        = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    ativo     = db.Column(db.Boolean, nullable=False, default=True)
    protegido = db.Column(db.Boolean, nullable=False, default=False)
    validade  = db.Column(db.Date)

    solicitacoes = db.relationship('Solicitacao', back_populates='tipo_solicitacao')


class Evento(db.Model):
    __tablename__ = 'evento'

    id          = db.Column(db.Integer, primary_key=True)
    descricao   = db.Column(db.String(100), nullable=False)
    data_inicio = db.Column(db.Date)
    data_fim    = db.Column(db.Date)

    solicitacoes = db.relationship('Solicitacao', back_populates='evento')


class Atividade(db.Model):
    __tablename__ = 'atividade'

    id       = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)

    solicitacoes = db.relationship('Solicitacao', back_populates='atividade')


class Solicitacao(db.Model):
    __tablename__ = 'solicitacao'

    id                  = db.Column(db.Integer, primary_key=True)
    data_solicitacao    = db.Column(db.Date,    nullable=False)
    descricao           = db.Column(db.Text)
    observacao          = db.Column(db.Text)
    id_usuario          = db.Column(db.Integer, db.ForeignKey('usuario.id'),          nullable=False)
    id_pessoa           = db.Column(db.Integer, db.ForeignKey('pessoa.id'),           nullable=False)
    id_tipo_solicitacao = db.Column(db.Integer, db.ForeignKey('tipo_solicitacao.id'), nullable=False)
    id_status           = db.Column(db.Integer, db.ForeignKey('status.id'),           nullable=False)
    id_evento           = db.Column(db.Integer, db.ForeignKey('evento.id'))
    id_atividade        = db.Column(db.Integer, db.ForeignKey('atividade.id'))
    exclusao_pendente   = db.Column(db.Boolean, default=False, nullable=False, server_default='false')
    atendimento_id      = db.Column(
        db.Integer,
        db.ForeignKey('atendimento.id', ondelete='SET NULL'),
        nullable=True,
    )

    usuario          = db.relationship('Usuario',         back_populates='solicitacoes')
    pessoa           = db.relationship('Pessoa',          back_populates='solicitacoes')
    tipo_solicitacao = db.relationship('TipoSolicitacao', back_populates='solicitacoes')
    status           = db.relationship('Status',          back_populates='solicitacoes')
    evento           = db.relationship('Evento',          back_populates='solicitacoes')
    atividade        = db.relationship('Atividade',       back_populates='solicitacoes')
    atendimento      = db.relationship(
        'Atendimento',
        backref=db.backref('solicitacoes_vinculadas', lazy='dynamic'),
        foreign_keys=[atendimento_id],
    )


class LogAcao(db.Model):
    __tablename__ = 'log_acao'

    id          = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    id_usuario  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    acao        = db.Column(db.String(50),  nullable=False)   # 'exclusao', 'mesclagem', 'status'
    entidade    = db.Column(db.String(50),  nullable=False)   # 'pessoa', 'atendimento', 'solicitacao'
    entidade_id = db.Column(db.Integer,     nullable=True)    # ID do registro afetado
    descricao   = db.Column(db.Text,        nullable=False)   # texto legível do que aconteceu

    usuario = db.relationship('Usuario', foreign_keys=[id_usuario])


class SolicitacaoExclusao(db.Model):
    __tablename__ = 'solicitacao_exclusao'
    id                     = db.Column(db.Integer, primary_key=True)
    entidade               = db.Column(db.String(20), nullable=False)  # cadastro, atendimento, solicitacao
    entidade_id            = db.Column(db.Integer, nullable=False)
    entidade_desc          = db.Column(db.String(200), nullable=False)
    id_usuario_solicitante = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at             = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    motivo                 = db.Column(db.Text)
    motivo_negacao         = db.Column(db.Text, nullable=True)
    status                 = db.Column(db.String(20), default='pendente', nullable=False)
    usuario_solicitante    = db.relationship('Usuario', foreign_keys=[id_usuario_solicitante])


class RequerimentoGerado(db.Model):
    __tablename__ = 'requerimento_gerado'

    id                    = db.Column(db.Integer, primary_key=True)
    protocolo             = db.Column(db.String(20), nullable=False, unique=True)
    created_at            = db.Column(db.DateTime,
                                default=lambda: datetime.now(timezone.utc),
                                nullable=False)
    id_usuario            = db.Column(db.Integer,
                                db.ForeignKey('usuario.id'), nullable=True)
    id_pessoa             = db.Column(db.Integer,
                                db.ForeignKey('pessoa.id'), nullable=True)
    nome_manual           = db.Column(db.String(150))
    cpf_manual            = db.Column(db.String(14))
    cnpj_manual           = db.Column(db.String(18))
    credenciamento_evento = db.Column(db.String(200))
    solicitacao           = db.Column(db.Text)
    id_solicitacao        = db.Column(db.Integer,
                                db.ForeignKey('solicitacao.id'), nullable=True)
    modo_emissao          = db.Column(db.String(20), nullable=True)
    status_requerimento   = db.Column(db.String(20), default='gerado', nullable=True)
    observacao_manual     = db.Column(db.Text, nullable=True)

    usuario         = db.relationship('Usuario',     foreign_keys=[id_usuario])
    pessoa          = db.relationship('Pessoa',      foreign_keys=[id_pessoa])
    solicitacao_ref = db.relationship('Solicitacao', foreign_keys=[id_solicitacao])


class ParametroMunicipio(db.Model):
    __tablename__ = 'parametros_municipio'

    id         = db.Column(db.Integer, primary_key=True)
    chave      = db.Column(db.String(100), nullable=False, unique=True)
    valor      = db.Column(db.Text, nullable=False)
    descricao  = db.Column(db.Text)
    updated_at = db.Column(db.DateTime,
                    default=lambda: datetime.now(timezone.utc),
                    onupdate=lambda: datetime.now(timezone.utc),
                    nullable=False)


pessoa_tag = db.Table(
    'pessoa_tag',
    db.Column('id_pessoa', db.Integer, db.ForeignKey('pessoa.id',          ondelete='CASCADE'), primary_key=True),
    db.Column('id_tag',    db.Integer, db.ForeignKey('tag_interesse.id',   ondelete='CASCADE'), primary_key=True),
)


class TagInteresse(db.Model):
    __tablename__ = 'tag_interesse'

    id        = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    ativo     = db.Column(db.Boolean, nullable=False, default=True)
    protegido = db.Column(db.Boolean, nullable=False, default=False)


class LoteImportacao(db.Model):
    __tablename__ = 'lote_importacao'

    id                = db.Column(db.Integer, primary_key=True)
    data_execucao     = db.Column(db.DateTime,
                           default=lambda: datetime.now(timezone.utc),
                           nullable=False)
    responsavel       = db.Column(db.String(100), nullable=False)
    nome_arquivo      = db.Column(db.String(255))
    hash_md5          = db.Column(db.String(32))
    total_linhas      = db.Column(db.Integer)
    linhas_importadas = db.Column(db.Integer)
    linhas_ignoradas  = db.Column(db.Integer)
    linhas_com_erro   = db.Column(db.Integer)
    observacoes       = db.Column(db.Text)
