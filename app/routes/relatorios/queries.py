"""
relatorios/queries.py
Consultas centralizadas para os relatórios do Balcão MEI.
Adaptado para o schema do projeto (campos id_pessoa, id_usuario, nome_razao_social).
"""
from datetime import date
from sqlalchemy import func, extract
from app import db
from app.models import ATENDIMENTO_CONCLUIDO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dates(data_inicio, data_fim):
    if not data_inicio:
        data_inicio = date(date.today().year, 1, 1)
    if not data_fim:
        data_fim = date.today()
    return data_inicio, data_fim


# ---------------------------------------------------------------------------
# Relatório 1 – Atendimentos por período
# ---------------------------------------------------------------------------

def atendimentos_por_periodo(data_inicio=None, data_fim=None, usuario_id=None, ids_usuarios=None):
    """
    Retorna lista de dicts com os atendimentos no intervalo.

    Colunas retornadas:
        id, data_atendimento, hora_atendimento, pessoa_nome, pessoa_cpf,
        usuario_nome, observacoes
    """
    from app.models import Atendimento, Pessoa, Usuario

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    q = (
        db.session.query(
            Atendimento.id,
            Atendimento.data_atendimento,
            Atendimento.hora_atendimento,
            Atendimento.created_at,
            Pessoa.nome_razao_social.label("pessoa_nome"),
            Pessoa.cpf.label("pessoa_cpf"),
            Usuario.nome.label("usuario_nome"),
            Atendimento.observacao.label("observacoes"),
        )
        .join(Pessoa,   Atendimento.id_pessoa   == Pessoa.id)
        .join(Usuario,  Atendimento.id_usuario  == Usuario.id)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
    )

    if usuario_id:
        q = q.filter(Atendimento.id_usuario == usuario_id)
    elif ids_usuarios is not None:
        q = q.filter(Atendimento.id_usuario.in_(ids_usuarios))

    q = q.order_by(Atendimento.data_atendimento.desc(), Atendimento.hora_atendimento.desc())

    rows = q.all()
    return [r._asdict() for r in rows]


def totais_por_dia(data_inicio=None, data_fim=None, usuario_id=None, ids_usuarios=None):
    """
    Agrupamento diário — usado nos relatórios de período.
    Retorna lista de {data, total}.
    """
    from app.models import Atendimento

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    q = (
        db.session.query(
            Atendimento.data_atendimento.label("data"),
            func.count(Atendimento.id).label("total"),
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Atendimento.data_atendimento)
        .order_by(Atendimento.data_atendimento)
    )

    if usuario_id:
        q = q.filter(Atendimento.id_usuario == usuario_id)
    elif ids_usuarios is not None:
        q = q.filter(Atendimento.id_usuario.in_(ids_usuarios))

    rows = q.all()
    return [r._asdict() for r in rows]


# ---------------------------------------------------------------------------
# Relatório 2 – Desempenho por usuário/atendente
# ---------------------------------------------------------------------------

def desempenho_por_usuario(data_inicio=None, data_fim=None, usuario_id=None):
    """
    Totais consolidados por atendente no período.
    Retorna lista de {usuario_id, usuario_nome, total}.
    """
    from app.models import Atendimento, Usuario

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    q = (
        db.session.query(
            Usuario.id.label("usuario_id"),
            Usuario.nome.label("usuario_nome"),
            func.count(Atendimento.id).label("total"),
        )
        .join(Atendimento, Atendimento.id_usuario == Usuario.id)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Usuario.id, Usuario.nome)
        .order_by(func.count(Atendimento.id).desc())
    )

    if usuario_id:
        q = q.filter(Usuario.id == usuario_id)

    rows = q.all()
    result = []
    for r in rows:
        d = r._asdict()
        d["concluidos"]          = 0
        d["pendentes"]           = 0
        d["em_andamento"]        = 0
        d["percentual_conclusao"] = 0.0
        result.append(d)
    return result


def query_evolucao_mensal(data_inicio, data_fim, usuario_ids=None):
    """
    Retorna linhas (id, nome, mes, ano, total) para o heatmap de evolução mensal.
    """
    from app.models import Atendimento, Usuario

    q = (
        db.session.query(
            Usuario.id,
            Usuario.nome,
            extract('month', Atendimento.data_atendimento).label('mes'),
            extract('year',  Atendimento.data_atendimento).label('ano'),
            func.count(Atendimento.id).label('total'),
        )
        .join(Atendimento, Atendimento.id_usuario == Usuario.id)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
    )
    if usuario_ids:
        q = q.filter(Usuario.id.in_(usuario_ids))

    return (
        q.group_by(
            Usuario.id, Usuario.nome,
            extract('month', Atendimento.data_atendimento),
            extract('year',  Atendimento.data_atendimento),
        )
        .order_by(
            Usuario.nome,
            extract('year',  Atendimento.data_atendimento),
            extract('month', Atendimento.data_atendimento),
        )
        .all()
    )


def atendimentos_por_usuario_detalhe(usuario_id, data_inicio=None, data_fim=None):
    """
    Lista detalhada dos atendimentos de um único atendente.
    """
    from app.models import Atendimento, Pessoa

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    q = (
        db.session.query(
            Atendimento.id,
            Atendimento.data_atendimento,
            Atendimento.hora_atendimento,
            Pessoa.nome_razao_social.label("pessoa_nome"),
            Atendimento.observacao.label("observacoes"),
        )
        .join(Pessoa, Atendimento.id_pessoa == Pessoa.id)
        .filter(
            Atendimento.id_usuario == usuario_id,
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .order_by(Atendimento.data_atendimento.desc())
    )

    rows = q.all()
    return [r._asdict() for r in rows]


# ---------------------------------------------------------------------------
# Utilitário – lista de atendentes (para o <select> dos filtros)
# ---------------------------------------------------------------------------

def listar_atendentes():
    """Retorna todos os usuários ativos para popular o filtro de atendente."""
    from app.models import Usuario

    rows = (
        db.session.query(Usuario.id, Usuario.nome)
        .filter(Usuario.ativo == True)          # noqa: E712
        .order_by(Usuario.nome)
        .all()
    )
    return [{"id": r.id, "nome": r.nome} for r in rows]


# ---------------------------------------------------------------------------
# Relatório individual – Perfil de atendente
# ---------------------------------------------------------------------------

def totais_por_dia_usuario(usuario_id, data_inicio=None, data_fim=None):
    """
    Atendimentos por dia de um único atendente — para o gráfico de barras.
    Retorna lista de {data, total}.
    """
    from app.models import Atendimento

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    rows = (
        db.session.query(
            Atendimento.data_atendimento.label("data"),
            func.count(Atendimento.id).label("total"),
        )
        .filter(
            Atendimento.id_usuario == usuario_id,
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Atendimento.data_atendimento)
        .order_by(Atendimento.data_atendimento)
        .all()
    )
    return [r._asdict() for r in rows]


def tipos_mais_realizados(usuario_id, data_inicio=None, data_fim=None):
    """
    Contagem de tipos de atendimento mais realizados por um atendente.
    Retorna lista de {tipo_descricao, total} ordenada por total desc.
    """
    from app.models import Atendimento, AtendimentoServico, Servico

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    rows = (
        db.session.query(
            Servico.descricao.label("tipo_descricao"),
            func.count(AtendimentoServico.id_atendimento).label("total"),
        )
        .join(AtendimentoServico,
              AtendimentoServico.id_servico == Servico.id)
        .join(Atendimento,
              Atendimento.id == AtendimentoServico.id_atendimento)
        .filter(
            Atendimento.id_usuario == usuario_id,
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Servico.descricao)
        .order_by(func.count(AtendimentoServico.id_atendimento).desc())
        .all()
    )
    return [r._asdict() for r in rows]


def get_usuario_por_id(usuario_id):
    """Retorna dict {id, nome} de um usuário ou None."""
    from app.models import Usuario
    u = db.session.get(Usuario, usuario_id)
    if not u:
        return None
    return {"id": u.id, "nome": u.nome}


# ---------------------------------------------------------------------------
# Relatório Executivo
# ---------------------------------------------------------------------------

def atendimentos_por_tipo(data_inicio=None, data_fim=None):
    """Contagem de atendimentos agrupados por tipo no período."""
    from app.models import Atendimento, AtendimentoServico, Servico

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    rows = (
        db.session.query(
            Servico.descricao.label("tipo"),
            func.count(AtendimentoServico.id_atendimento).label("total"),
        )
        .join(AtendimentoServico,
              AtendimentoServico.id_servico == Servico.id)
        .join(Atendimento,
              Atendimento.id == AtendimentoServico.id_atendimento)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Servico.descricao)
        .order_by(func.count(AtendimentoServico.id_atendimento).desc())
        .all()
    )
    return [r._asdict() for r in rows]


def solicitacoes_por_status_periodo(data_inicio=None, data_fim=None):
    """Contagem de solicitações por status no período."""
    from app.models import Solicitacao, Status

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    rows = (
        db.session.query(
            Status.descricao.label("status"),
            func.count(Solicitacao.id).label("total"),
        )
        .join(Solicitacao, Solicitacao.id_status == Status.id)
        .filter(
            Solicitacao.data_solicitacao >= data_inicio,
            Solicitacao.data_solicitacao <= data_fim,
        )
        .group_by(Status.descricao)
        .order_by(func.count(Solicitacao.id).desc())
        .all()
    )
    return [r._asdict() for r in rows]


def solicitacoes_por_tipo_periodo(data_inicio=None, data_fim=None):
    """Contagem de solicitações por tipo no período."""
    from app.models import Solicitacao, TipoSolicitacao

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    rows = (
        db.session.query(
            TipoSolicitacao.descricao.label("tipo"),
            func.count(Solicitacao.id).label("total"),
        )
        .join(Solicitacao,
              Solicitacao.id_tipo_solicitacao == TipoSolicitacao.id)
        .filter(
            Solicitacao.data_solicitacao >= data_inicio,
            Solicitacao.data_solicitacao <= data_fim,
        )
        .group_by(TipoSolicitacao.descricao)
        .order_by(func.count(Solicitacao.id).desc())
        .all()
    )
    return [r._asdict() for r in rows]


def total_atendimentos_periodo(data_inicio=None, data_fim=None):
    """Retorna o total de atendimentos no período."""
    from app.models import Atendimento

    data_inicio, data_fim = _parse_dates(data_inicio, data_fim)

    return (
        db.session.query(func.count(Atendimento.id))
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .scalar() or 0
    )
