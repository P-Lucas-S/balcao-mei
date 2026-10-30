"""
analise.py — Módulo de Análise de Empreendedores
Fase 1: Painel Executivo com KPIs e insights automáticos
"""
from app import marca
import json
import time
import urllib.request
import urllib.parse
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, extract, distinct
from .. import db, cache
from ..models import (Pessoa, Atendimento, AtendimentoServico, Servico,
                      Solicitacao, Status, ParametroMunicipio,
                      ATENDIMENTO_CONCLUIDO)

analise_bp = Blueprint('analise', __name__, url_prefix='/analise')


def _requer_admin_supervisor():
    return current_user.perfil.nome in ('administrador', 'supervisor')


def _get_param(chave, default='0'):
    p = ParametroMunicipio.query.filter_by(chave=chave).first()
    return p.valor if p else default


def _periodo_from_request():
    hoje = date.today()
    data_inicio = request.args.get('data_inicio')
    data_fim    = request.args.get('data_fim')
    try:
        data_inicio = date.fromisoformat(data_inicio) if data_inicio else hoje.replace(day=1)
        data_fim    = date.fromisoformat(data_fim)    if data_fim    else hoje
    except ValueError:
        data_inicio = hoje.replace(day=1)
        data_fim    = hoje
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
    return data_inicio, data_fim


def _periodo_anterior(data_inicio, data_fim):
    delta = (data_fim - data_inicio).days + 1
    fim_ant    = data_inicio - timedelta(days=1)
    inicio_ant = fim_ant - timedelta(days=delta - 1)
    return inicio_ant, fim_ant


def _em_aberto():
    """Atendimentos ainda em rascunho — indicador OPERACIONAL, não métrica.

    Não se soma a nada nesta tela: os números oficiais contam só
    `concluido`. Isto responde outra pergunta — "o que ficou pendente de
    conclusão agora" — e por isso ignora o período selecionado. Um rascunho
    aberto no mês passado continua aberto hoje.

    Devolve `None` quando não há nenhum, para a seção sumir da tela em vez de
    exibir um zero que ninguém precisa ver.
    """
    from ..models import Usuario, ATENDIMENTO_RASCUNHO

    rows = (
        db.session.query(
            Usuario.id,
            Usuario.nome,
            func.count(Atendimento.id).label('qtd'),
            func.min(Atendimento.data_atendimento).label('mais_antigo'),
        )
        .join(Atendimento, Atendimento.id_usuario == Usuario.id)
        .filter(Atendimento.status == ATENDIMENTO_RASCUNHO)
        .group_by(Usuario.id, Usuario.nome)
        .order_by(func.count(Atendimento.id).desc())
        .all()
    )
    if not rows:
        return None

    return {
        'total': sum(r.qtd for r in rows),
        'por_atendente': [
            {'id': r.id, 'nome': r.nome, 'qtd': r.qtd,
             'mais_antigo': r.mais_antigo}
            for r in rows
        ],
    }


def _kpis(data_inicio, data_fim):
    """Calcula os KPIs principais do período."""

    # Empreendedores únicos atendidos
    unicos = (
        db.session.query(func.count(distinct(Atendimento.id_pessoa)))
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .scalar() or 0
    )

    # Novos MEIs formalizados — tipo cujo nome contém "abertura de mei" (case-insensitive)
    tipo_abertura = (
        Servico.query
        .filter(Servico.descricao.ilike('%abertura%mei%'))
        .first()
    )
    novos_meis = 0
    if tipo_abertura:
        novos_meis = (
            db.session.query(func.count(distinct(AtendimentoServico.id_atendimento)))
            .join(Atendimento,
                  Atendimento.id == AtendimentoServico.id_atendimento)
            .filter(
                AtendimentoServico.id_servico == tipo_abertura.id,
                Atendimento.data_atendimento >= data_inicio,
                Atendimento.data_atendimento <= data_fim,
                Atendimento.status == ATENDIMENTO_CONCLUIDO,
            )
            .scalar() or 0
        )

    # Total de atendimentos no período
    total_atend = (
        db.session.query(func.count(Atendimento.id))
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .scalar() or 0
    )

    # Taxa de retorno — % de pessoas que tiveram 2+ atendimentos no período
    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.count(Atendimento.id).label('qtd')
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )
    com_retorno = (
        db.session.query(func.count())
        .select_from(subq)
        .filter(subq.c.qtd >= 2)
        .scalar() or 0
    )
    taxa_retorno = round(com_retorno / unicos * 100) if unicos > 0 else 0

    # Cobertura sobre total de MEIs do município
    total_meis_municipio = int(_get_param('total_meis_municipio', '0'))
    cobertura = round(unicos / total_meis_municipio * 100, 1) if total_meis_municipio > 0 else None

    # Meta anual de atendimentos
    meta_anual = int(_get_param('meta_anual_atendimentos', '0'))
    progresso_meta = round(total_atend / meta_anual * 100) if meta_anual > 0 else None

    return {
        'unicos':               unicos,
        'novos_meis':           novos_meis,
        'total_atend':          total_atend,
        'taxa_retorno':         taxa_retorno,
        'com_retorno':          com_retorno,
        'cobertura':            cobertura,
        'total_meis_municipio': total_meis_municipio,
        'meta_anual':           meta_anual,
        'progresso_meta':       progresso_meta,
    }


def _variacao(atual, anterior):
    if anterior and anterior > 0:
        return round((atual - anterior) / anterior * 100)
    return None


def _insights(data_inicio, data_fim, kpis):
    """Gera insights automáticos em linguagem natural."""
    insights = []

    if kpis['unicos'] > 0:
        insights.append(
            f"A Sala atendeu {kpis['unicos']} empreendedor(es) único(s) no período."
        )

    if kpis['cobertura'] is not None:
        insights.append(
            f"A cobertura sobre os MEIs do município foi de {kpis['cobertura']}%."
        )

    if kpis['novos_meis'] > 0:
        insights.append(
            f"{kpis['novos_meis']} novo(s) MEI(s) formalizado(s) no período."
        )

    sem_retorno = kpis['unicos'] - kpis['com_retorno']
    if sem_retorno > 0:
        insights.append(
            f"{sem_retorno} empreendedor(es) vieram apenas uma vez e não retornaram."
        )

    tipo_top = (
        db.session.query(
            Servico.descricao,
            func.count(AtendimentoServico.id_atendimento).label('total')
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
        .first()
    )
    if tipo_top:
        insights.append(
            f"O serviço mais demandado foi \"{tipo_top.descricao}\" "
            f"({tipo_top.total} ocorrência(s))."
        )

    data_corte_str = _get_param('data_corte_historico', '2025-11-01')
    try:
        data_corte = date.fromisoformat(data_corte_str)
        if data_inicio < data_corte:
            insights.append(
                f"⚠️ Atenção: dados anteriores a "
                f"{data_corte.strftime('%d/%m/%Y')} foram importados em lote "
                f"e podem conter imprecisões de data."
            )
    except ValueError:
        pass

    return insights


def _evolucao_mensal(data_inicio, data_fim):
    """Atendimentos únicos por mês no período."""
    rows = (
        db.session.query(
            extract('year',  Atendimento.data_atendimento).label('ano'),
            extract('month', Atendimento.data_atendimento).label('mes'),
            func.count(distinct(Atendimento.id_pessoa)).label('unicos'),
            func.count(Atendimento.id).label('total'),
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by('ano', 'mes')
        .order_by('ano', 'mes')
        .all()
    )
    MESES = {1:'Jan',2:'Fev',3:'Mar',4:'Abr',5:'Mai',6:'Jun',
             7:'Jul',8:'Ago',9:'Set',10:'Out',11:'Nov',12:'Dez'}
    return [
        {
            'label':  f"{MESES[int(r.mes)]}/{int(r.ano)}",
            'unicos': r.unicos,
            'total':  r.total,
        }
        for r in rows
    ]


def _top_tipos(data_inicio, data_fim, limite=5):
    """Top tipos de atendimento no período."""
    rows = (
        db.session.query(
            Servico.descricao,
            func.count(AtendimentoServico.id_atendimento).label('total')
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
        .limit(limite)
        .all()
    )
    return [{'tipo': r.descricao, 'total': r.total} for r in rows]


# ── Funções da Aba Jornada ─────────────────────────────────────────────────────

def _funil_jornada():
    """Funil: PF cadastrada → teve orientação → virou MEI → retornou."""
    total_pf = db.session.query(func.count(Pessoa.id)).scalar() or 0

    tipo_orientacao = (Servico.query
                       .filter(Servico.descricao.ilike('%orienta%'))
                       .first())

    com_orientacao = 0
    if tipo_orientacao:
        com_orientacao = (
            db.session.query(func.count(distinct(Atendimento.id_pessoa)))
            .join(AtendimentoServico)
            .filter(AtendimentoServico.id_servico == tipo_orientacao.id,
                    Atendimento.status == ATENDIMENTO_CONCLUIDO)
            .scalar() or 0
        )

    virou_mei = (
        db.session.query(func.count(Pessoa.id))
        .filter(Pessoa.mei == True)
        .scalar() or 0
    )

    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.count(Atendimento.id).label('qtd')
        )
        .filter(Atendimento.status == ATENDIMENTO_CONCLUIDO)
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )
    com_retorno = (
        db.session.query(func.count())
        .select_from(subq)
        .filter(subq.c.qtd >= 2)
        .scalar() or 0
    )

    return [
        {'label': 'Cadastrados',          'valor': total_pf,       'pct': 100},
        {'label': 'Receberam Orientação',  'valor': com_orientacao,
         'pct': round(com_orientacao / total_pf * 100) if total_pf else 0},
        {'label': 'Viraram MEI',           'valor': virou_mei,
         'pct': round(virou_mei / total_pf * 100) if total_pf else 0},
        {'label': 'Retornaram',            'valor': com_retorno,
         'pct': round(com_retorno / total_pf * 100) if total_pf else 0},
    ]


def _tempo_medio_retorno(data_inicio=None, data_fim=None):
    """Tempo médio em dias entre 1ª e 2ª visita (opcionalmente filtrado por período)."""
    from itertools import groupby as _groupby

    q = db.session.query(
        Atendimento.id_pessoa,
        Atendimento.data_atendimento,
    ).filter(
        Atendimento.status == ATENDIMENTO_CONCLUIDO
    ).order_by(Atendimento.id_pessoa, Atendimento.data_atendimento)
    if data_inicio:
        q = q.filter(Atendimento.data_atendimento >= data_inicio)
    if data_fim:
        q = q.filter(Atendimento.data_atendimento <= data_fim)

    rows = q.all()
    intervals = []
    for _pid, group in _groupby(rows, key=lambda r: r.id_pessoa):
        datas = sorted(r.data_atendimento for r in group)
        if len(datas) >= 2:
            intervals.append((datas[1] - datas[0]).days)

    return round(sum(intervals) / len(intervals)) if intervals else None


def _top10_mais_atendidos(data_inicio=None, data_fim=None):
    """Top 10 empreendedores com mais atendimentos (opcionalmente filtrado por período)."""
    q = (
        db.session.query(
            Pessoa.id,
            Pessoa.nome_razao_social,
            func.count(Atendimento.id).label('total'),
            func.max(Atendimento.data_atendimento).label('ultimo')
        )
        .join(Atendimento, Atendimento.id_pessoa == Pessoa.id)
        .filter(Atendimento.status == ATENDIMENTO_CONCLUIDO)
    )
    if data_inicio:
        q = q.filter(Atendimento.data_atendimento >= data_inicio)
    if data_fim:
        q = q.filter(Atendimento.data_atendimento <= data_fim)
    rows = (
        q.group_by(Pessoa.id, Pessoa.nome_razao_social)
        .order_by(func.count(Atendimento.id).desc())
        .limit(10)
        .all()
    )
    return [
        {
            'id':     r.id,
            'nome':   r.nome_razao_social,
            'total':  r.total,
            'ultimo': r.ultimo.strftime('%d/%m/%Y') if r.ultimo else '—',
        }
        for r in rows
    ]


def _uma_visita_apenas(data_inicio=None, data_fim=None):
    """% de pessoas que vieram apenas uma vez (opcionalmente filtrado por período)."""
    q_base = db.session.query(
        Atendimento.id_pessoa,
        func.count(Atendimento.id).label('qtd')
    ).filter(Atendimento.status == ATENDIMENTO_CONCLUIDO)
    if data_inicio:
        q_base = q_base.filter(Atendimento.data_atendimento >= data_inicio)
    if data_fim:
        q_base = q_base.filter(Atendimento.data_atendimento <= data_fim)
    subq = q_base.group_by(Atendimento.id_pessoa).subquery()

    total = (
        db.session.query(func.count()).select_from(subq).scalar() or 0
    )
    apenas_uma = (
        db.session.query(func.count())
        .select_from(subq)
        .filter(subq.c.qtd == 1)
        .scalar() or 0
    )
    pct = round(apenas_uma / total * 100) if total > 0 else 0
    return {'total': apenas_uma, 'pct': pct, 'base': total}


def _funil_conversao(data_inicio, data_fim):
    """Funil: Cadastrados → Atendidos → Com Solicitação → Aprovados."""
    total_cadastrados = db.session.query(func.count(Pessoa.id)).scalar() or 0

    total_atendidos = (
        db.session.query(func.count(distinct(Atendimento.id_pessoa)))
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .scalar() or 0
    )

    com_solic = (
        db.session.query(func.count(distinct(Solicitacao.id_pessoa)))
        .filter(
            Solicitacao.data_solicitacao >= data_inicio,
            Solicitacao.data_solicitacao <= data_fim,
        )
        .scalar() or 0
    )

    status_aprovado = Status.query.filter(Status.descricao.ilike('%aprovado%')).first()
    com_aprovado = 0
    if status_aprovado:
        com_aprovado = (
            db.session.query(func.count(distinct(Solicitacao.id_pessoa)))
            .filter(
                Solicitacao.id_status == status_aprovado.id,
                Solicitacao.data_solicitacao >= data_inicio,
                Solicitacao.data_solicitacao <= data_fim,
            )
            .scalar() or 0
        )

    base = total_cadastrados or 1
    return [
        {'label': 'Cadastrados',     'valor': total_cadastrados, 'pct': 100},
        {'label': 'Atendidos',       'valor': total_atendidos,
         'pct': round(total_atendidos / base * 100)},
        {'label': 'Com Solicitação', 'valor': com_solic,
         'pct': round(com_solic / base * 100)},
        {'label': 'Aprovados',       'valor': com_aprovado,
         'pct': round(com_aprovado / base * 100)},
    ]


def _kpis_jornada(data_inicio, data_fim):
    """KPIs de jornada para o período."""
    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.count(Atendimento.id).label('qtd')
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )

    total_unicos = (
        db.session.query(func.count()).select_from(subq).scalar() or 0
    )
    total_atend = (
        db.session.query(func.count(Atendimento.id))
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .scalar() or 0
    )
    so_uma_vez = (
        db.session.query(func.count())
        .select_from(subq)
        .filter(subq.c.qtd == 1)
        .scalar() or 0
    )
    com_retorno = (
        db.session.query(func.count())
        .select_from(subq)
        .filter(subq.c.qtd >= 2)
        .scalar() or 0
    )

    pct_uma_vez = round(so_uma_vez / total_unicos * 100) if total_unicos else 0
    pct_retorno = round(com_retorno / total_unicos * 100) if total_unicos else 0
    media_atend = round(total_atend / total_unicos, 1) if total_unicos else 0

    return {
        'total_unicos': total_unicos,
        'so_uma_vez':   so_uma_vez,
        'pct_uma_vez':  pct_uma_vez,
        'com_retorno':  com_retorno,
        'pct_retorno':  pct_retorno,
        'media_atend':  media_atend,
        'total_atend':  total_atend,
    }


def _frequencia_visitas(data_inicio, data_fim):
    """Distribuição por número de visitas no período: 1×, 2×, 3×, 4+."""
    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.count(Atendimento.id).label('n')
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )
    rows = (
        db.session.query(subq.c.n, func.count().label('pessoas'))
        .group_by(subq.c.n)
        .order_by(subq.c.n)
        .all()
    )

    contagens = {int(r.n): r.pessoas for r in rows}
    total = sum(contagens.values()) or 1

    quatro_mais = sum(v for k, v in contagens.items() if k >= 4)
    return [
        {'label': '1 visita',   'total': contagens.get(1, 0),
         'pct': round(contagens.get(1, 0) / total * 100)},
        {'label': '2 visitas',  'total': contagens.get(2, 0),
         'pct': round(contagens.get(2, 0) / total * 100)},
        {'label': '3 visitas',  'total': contagens.get(3, 0),
         'pct': round(contagens.get(3, 0) / total * 100)},
        {'label': '4+ visitas', 'total': quatro_mais,
         'pct': round(quatro_mais / total * 100)},
    ]


# ── Funções da Aba Demanda ─────────────────────────────────────────────────────

_DIAS_PT  = {0:'Domingo', 1:'Segunda', 2:'Terça', 3:'Quarta',
             4:'Quinta',  5:'Sexta',   6:'Sábado'}
_MESES_PT = ['','Jan','Fev','Mar','Abr','Mai','Jun',
             'Jul','Ago','Set','Out','Nov','Dez']


def _kpis_demanda(data_inicio, data_fim):
    """4 KPIs de destaque: tipo top, dia top, hora pico, mês mais intenso."""
    filtro = [
        Atendimento.data_atendimento >= data_inicio,
        Atendimento.data_atendimento <= data_fim,
        Atendimento.status == ATENDIMENTO_CONCLUIDO,
    ]

    tipo_top = (
        db.session.query(
            Servico.descricao,
            func.count(AtendimentoServico.id_atendimento).label('total')
        )
        .join(AtendimentoServico, AtendimentoServico.id_servico == Servico.id)
        .join(Atendimento, Atendimento.id == AtendimentoServico.id_atendimento)
        .filter(*filtro)
        .group_by(Servico.descricao)
        .order_by(func.count(AtendimentoServico.id_atendimento).desc())
        .first()
    )

    dia_top = (
        db.session.query(
            extract('dow', Atendimento.data_atendimento).label('dia'),
            func.count(Atendimento.id).label('total')
        )
        .filter(*filtro)
        .group_by('dia')
        .order_by(func.count(Atendimento.id).desc())
        .first()
    )

    hora_top = (
        db.session.query(
            extract('hour', Atendimento.hora_atendimento).label('hora'),
            func.count(Atendimento.id).label('total')
        )
        .filter(*filtro, Atendimento.hora_atendimento.isnot(None))
        .group_by('hora')
        .order_by(func.count(Atendimento.id).desc())
        .first()
    )

    mes_top = (
        db.session.query(
            extract('month', Atendimento.data_atendimento).label('mes'),
            extract('year',  Atendimento.data_atendimento).label('ano'),
            func.count(Atendimento.id).label('total')
        )
        .filter(*filtro)
        .group_by('mes', 'ano')
        .order_by(func.count(Atendimento.id).desc())
        .first()
    )

    return {
        'tipo_top':       tipo_top.descricao if tipo_top else '—',
        'tipo_top_total': tipo_top.total if tipo_top else 0,
        'dia_top':        _DIAS_PT.get(int(dia_top.dia), '—') if dia_top else '—',
        'dia_top_total':  dia_top.total if dia_top else 0,
        'hora_top':       (f"{int(hora_top.hora)}h–{int(hora_top.hora)+1}h"
                           if hora_top else '—'),
        'hora_top_total': hora_top.total if hora_top else 0,
        'mes_top':        (f"{_MESES_PT[int(mes_top.mes)]}/{int(mes_top.ano)}"
                           if mes_top else '—'),
        'mes_top_total':  mes_top.total if mes_top else 0,
    }


def _por_servico(data_inicio, data_fim):
    """Distribuição por tipo de atendimento no período, ordenado por volume."""
    rows = (
        db.session.query(
            Servico.descricao,
            func.count(AtendimentoServico.id_atendimento).label('total')
        )
        .join(AtendimentoServico, AtendimentoServico.id_servico == Servico.id)
        .join(Atendimento, Atendimento.id == AtendimentoServico.id_atendimento)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by(Servico.descricao)
        .order_by(func.count(AtendimentoServico.id_atendimento).desc())
        .all()
    )
    total = sum(r.total for r in rows) or 1
    return [
        {'tipo': r.descricao, 'total': r.total,
         'pct': round(r.total / total * 100)}
        for r in rows
    ]

def _heatmap_meses_tipos(data_inicio, data_fim):
    """Heatmap: meses × tipos de atendimento."""
    rows = (
        db.session.query(
            extract('month', Atendimento.data_atendimento).label('mes'),
            Servico.descricao.label('tipo'),
            func.count(AtendimentoServico.id_atendimento).label('total')
        )
        .join(AtendimentoServico,
              AtendimentoServico.id_atendimento == Atendimento.id)
        .join(Servico,
              Servico.id == AtendimentoServico.id_servico)
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by('mes', Servico.descricao)
        .order_by('mes')
        .all()
    )

    MESES = {1:'Jan',2:'Fev',3:'Mar',4:'Abr',5:'Mai',6:'Jun',
             7:'Jul',8:'Ago',9:'Set',10:'Out',11:'Nov',12:'Dez'}

    tipos  = sorted(set(r.tipo for r in rows))
    meses  = sorted(set(int(r.mes) for r in rows))

    matriz = {m: {t: 0 for t in tipos} for m in meses}
    max_val = 0
    for r in rows:
        matriz[int(r.mes)][r.tipo] = r.total
        if r.total > max_val:
            max_val = r.total

    return {
        'tipos':   tipos,
        'meses':   [MESES[m] for m in meses],
        'meses_n': meses,
        'matriz':  [[matriz[m][t] for t in tipos] for m in meses],
        'max_val': max_val or 1,
    }


def _dia_semana(data_inicio, data_fim):
    """Atendimentos por dia da semana."""
    rows = (
        db.session.query(
            extract('dow', Atendimento.data_atendimento).label('dow'),
            func.count(Atendimento.id).label('total')
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
        )
        .group_by('dow')
        .order_by('dow')
        .all()
    )
    DIAS = {0:'Dom',1:'Seg',2:'Ter',3:'Qua',4:'Qui',5:'Sex',6:'Sáb'}
    dados = {int(r.dow): r.total for r in rows}
    return [
        {'dia': DIAS[i], 'total': dados.get(i, 0)}
        for i in range(1, 6)
    ]


def _hora_pico(data_inicio, data_fim):
    """Atendimentos por hora do dia."""
    rows = (
        db.session.query(
            extract('hour', Atendimento.hora_atendimento).label('hora'),
            func.count(Atendimento.id).label('total')
        )
        .filter(
            Atendimento.data_atendimento >= data_inicio,
            Atendimento.data_atendimento <= data_fim,
            Atendimento.status == ATENDIMENTO_CONCLUIDO,
            Atendimento.hora_atendimento.isnot(None),
        )
        .group_by('hora')
        .order_by('hora')
        .all()
    )
    return [
        {'hora': f"{int(r.hora):02d}h", 'total': r.total}
        for r in rows
    ]


# ── Painel Executivo ───────────────────────────────────────────────────────────
@analise_bp.route('/')
@login_required
@cache.cached(timeout=300, query_string=True)
def index():
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    data_inicio, data_fim = _periodo_from_request()
    ini_ant, fim_ant      = _periodo_anterior(data_inicio, data_fim)

    kpis     = _kpis(data_inicio, data_fim)
    kpis_ant = _kpis(ini_ant, fim_ant)

    variacoes = {
        'unicos':      _variacao(kpis['unicos'],      kpis_ant['unicos']),
        'novos_meis':  _variacao(kpis['novos_meis'],  kpis_ant['novos_meis']),
        'total_atend': _variacao(kpis['total_atend'], kpis_ant['total_atend']),
    }

    insights  = _insights(data_inicio, data_fim, kpis)
    evolucao  = _evolucao_mensal(data_inicio, data_fim)
    top_tipos = _top_tipos(data_inicio, data_fim)
    em_aberto = _em_aberto()

    hoje = date.today()
    if hoje.month == 1:
        mes_ant_inicio = hoje.replace(year=hoje.year-1, month=12, day=1)
    else:
        mes_ant_inicio = hoje.replace(month=hoje.month-1, day=1)
    mes_ant_fim = hoje.replace(day=1) - timedelta(days=1)

    return render_template('analise/index.html',
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           kpis=kpis,
                           variacoes=variacoes,
                           insights=insights,
                           evolucao=evolucao,
                           top_tipos=top_tipos,
                           em_aberto=em_aberto,
                           hoje=hoje,
                           mes_ant_inicio=mes_ant_inicio,
                           mes_ant_fim=mes_ant_fim,
                           periodo_ant={'data_inicio': ini_ant, 'data_fim': fim_ant})


# ── Configuração de parâmetros ─────────────────────────────────────────────────
@analise_bp.route('/parametros', methods=['GET', 'POST'])
@login_required
def parametros():
    if current_user.perfil.nome != 'administrador':
        flash('Acesso restrito ao administrador.', 'danger')
        return redirect(url_for('analise.index'))

    params = {p.chave: p for p in ParametroMunicipio.query.all()}

    if request.method == 'POST':
        for chave, valor in request.form.items():
            if chave in params:
                params[chave].valor = valor.strip()
            else:
                db.session.add(ParametroMunicipio(chave=chave, valor=valor.strip()))
        db.session.commit()
        cache.clear()
        flash('Parâmetros atualizados com sucesso.', 'success')
        return redirect(url_for('analise.parametros'))

    return render_template('analise/parametros.html', params=params)


# ── Aba Jornada ────────────────────────────────────────────────────────────────
@analise_bp.route('/jornada')
@login_required
@cache.cached(timeout=300, query_string=True)
def jornada():
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    data_inicio, data_fim = _periodo_from_request()

    hoje = date.today()
    if hoje.month == 1:
        mes_ant_inicio = hoje.replace(year=hoje.year - 1, month=12, day=1)
    else:
        mes_ant_inicio = hoje.replace(month=hoje.month - 1, day=1)
    mes_ant_fim = hoje.replace(day=1) - timedelta(days=1)

    kpis_j      = _kpis_jornada(data_inicio, data_fim)
    funil       = _funil_conversao(data_inicio, data_fim)
    frequencia  = _frequencia_visitas(data_inicio, data_fim)
    top10       = _top10_mais_atendidos(data_inicio, data_fim)
    tempo_medio = _tempo_medio_retorno(data_inicio, data_fim)
    uma_visita  = _uma_visita_apenas(data_inicio, data_fim)

    return render_template('analise/jornada.html',
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           hoje=hoje,
                           mes_ant_inicio=mes_ant_inicio,
                           mes_ant_fim=mes_ant_fim,
                           kpis_j=kpis_j,
                           funil=funil,
                           frequencia=frequencia,
                           top10=top10,
                           tempo_medio=tempo_medio,
                           uma_visita=uma_visita)


# ── Funções da Aba Perfil ─────────────────────────────────────────────────────

def _distribuicao_tipo():
    """Distribuição PF / MEI / PJ."""
    total = db.session.query(func.count(Pessoa.id)).scalar() or 0
    mei   = db.session.query(func.count(Pessoa.id)).filter(Pessoa.mei == True).scalar() or 0
    pj    = db.session.query(func.count(Pessoa.id)).filter(
        Pessoa.cnpj != None, Pessoa.cnpj != '', Pessoa.mei != True
    ).scalar() or 0
    pf    = total - mei - pj
    return [
        {'tipo': 'MEI',             'total': mei, 'pct': round(mei/total*100) if total else 0},
        {'tipo': 'Pessoa Física',   'total': pf,  'pct': round(pf/total*100)  if total else 0},
        {'tipo': 'Pessoa Jurídica', 'total': pj,  'pct': round(pj/total*100)  if total else 0},
    ]


def _top_cnaes(limite=10):
    """Top CNAEs mais frequentes entre MEIs atendidos."""
    rows = (
        db.session.query(
            Pessoa.cnae_principal,
            func.count(distinct(Pessoa.id)).label('total')
        )
        .filter(
            Pessoa.cnae_principal != None,
            Pessoa.cnae_principal != '',
        )
        .group_by(Pessoa.cnae_principal)
        .order_by(func.count(distinct(Pessoa.id)).desc())
        .limit(limite)
        .all()
    )
    return [{'cnae': r.cnae_principal, 'total': r.total} for r in rows]


def _situacao_cadastral():
    """Distribuição por situação cadastral."""
    rows = (
        db.session.query(
            Pessoa.situacao_cadastral,
            func.count(Pessoa.id).label('total')
        )
        .filter(Pessoa.situacao_cadastral != None, Pessoa.situacao_cadastral != '')
        .group_by(Pessoa.situacao_cadastral)
        .order_by(func.count(Pessoa.id).desc())
        .all()
    )
    sem_info = db.session.query(func.count(Pessoa.id)).filter(
        db.or_(Pessoa.situacao_cadastral == None, Pessoa.situacao_cadastral == '')
    ).scalar() or 0
    return {
        'dados':    [{'situacao': r.situacao_cadastral, 'total': r.total} for r in rows],
        'sem_info': sem_info,
    }


def _distribuicao_porte():
    """Distribuição por porte (MEI / ME / EPP)."""
    rows = (
        db.session.query(
            Pessoa.porte,
            func.count(Pessoa.id).label('total')
        )
        .filter(Pessoa.porte != None, Pessoa.porte != '')
        .group_by(Pessoa.porte)
        .order_by(func.count(Pessoa.id).desc())
        .all()
    )
    return [{'porte': r.porte, 'total': r.total} for r in rows]


# ── Funções da Aba Potencial ───────────────────────────────────────────────────

def _kpis_potencial():
    """Contagem dos 4 segmentos de alerta."""
    hoje = date.today()

    # Campeões: 5+ atendimentos nos últimos 6 meses
    corte_6m = hoje - timedelta(days=180)
    subq_camp = (
        db.session.query(Atendimento.id_pessoa)
        .filter(Atendimento.data_atendimento >= corte_6m,
                Atendimento.status == ATENDIMENTO_CONCLUIDO)
        .group_by(Atendimento.id_pessoa)
        .having(func.count(Atendimento.id) >= 5)
        .subquery()
    )
    n_campeoes = db.session.query(func.count()).select_from(subq_camp).scalar() or 0

    # Em risco: solicitações abertas há +30 dias
    corte_30d = hoje - timedelta(days=30)
    status_abertos = db.session.query(Status.id).filter(
        db.or_(
            Status.descricao.ilike('%pendente%'),
            Status.descricao.ilike('%análise%'),
        )
    ).subquery()
    n_risco = (
        db.session.query(func.count(Solicitacao.id))
        .filter(
            Solicitacao.id_status.in_(status_abertos),
            Solicitacao.data_solicitacao <= corte_30d,
        )
        .scalar() or 0
    )

    # Inativos: sem atendimento há +12 meses
    corte_12m = hoje - timedelta(days=365)
    subq_ult = (
        db.session.query(
            Atendimento.id_pessoa,
            func.max(Atendimento.data_atendimento).label('ultimo')
        )
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )
    n_inativos = (
        db.session.query(func.count())
        .select_from(subq_ult)
        .filter(subq_ult.c.ultimo < corte_12m)
        .scalar() or 0
    )

    # Nunca solicitaram: atendidos sem nenhuma solicitação
    ids_com_solic = db.session.query(distinct(Solicitacao.id_pessoa)).subquery()
    n_nunca = (
        db.session.query(func.count(distinct(Atendimento.id_pessoa)))
        .filter(~Atendimento.id_pessoa.in_(ids_com_solic))
        .scalar() or 0
    )

    return {
        'n_campeoes': n_campeoes,
        'n_risco':    n_risco,
        'n_inativos': n_inativos,
        'n_nunca':    n_nunca,
    }


def _campeoes():
    """Alta recorrência: 5+ atendimentos nos últimos 6 meses."""
    corte = date.today() - timedelta(days=180)
    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.count(Atendimento.id).label('qtd'),
            func.max(Atendimento.data_atendimento).label('ultimo')
        )
        .filter(Atendimento.data_atendimento >= corte,
                Atendimento.status == ATENDIMENTO_CONCLUIDO)
        .group_by(Atendimento.id_pessoa)
        .having(func.count(Atendimento.id) >= 5)
        .subquery()
    )
    rows = (
        db.session.query(Pessoa, subq.c.qtd, subq.c.ultimo)
        .join(subq, subq.c.id_pessoa == Pessoa.id)
        .order_by(subq.c.qtd.desc())
        .limit(20)
        .all()
    )
    return [
        {
            'id':     p.id,
            'nome':   p.nome_razao_social,
            'total':  qtd,
            'ultimo': ultimo.strftime('%d/%m/%Y') if ultimo else '—',
        }
        for p, qtd, ultimo in rows
    ]


def _inativos():
    """Sem atendimento há mais de 12 meses."""
    corte = date.today() - timedelta(days=365)
    subq = (
        db.session.query(
            Atendimento.id_pessoa,
            func.max(Atendimento.data_atendimento).label('ultimo')
        )
        .filter(Atendimento.status == ATENDIMENTO_CONCLUIDO)
        .group_by(Atendimento.id_pessoa)
        .subquery()
    )
    rows = (
        db.session.query(Pessoa, subq.c.ultimo)
        .join(subq, subq.c.id_pessoa == Pessoa.id)
        .filter(subq.c.ultimo < corte)
        .order_by(subq.c.ultimo.asc())
        .limit(20)
        .all()
    )
    return [
        {
            'id':     p.id,
            'nome':   p.nome_razao_social,
            'ultimo': ultimo.strftime('%d/%m/%Y') if ultimo else '—',
            'dias':   (date.today() - ultimo).days if ultimo else None,
        }
        for p, ultimo in rows
    ]


def _nunca_solicitaram():
    """Pessoas com atendimentos mas sem nenhuma solicitação."""
    ids_com_solic = db.session.query(distinct(Solicitacao.id_pessoa)).subquery()

    rows = (
        db.session.query(
            Pessoa,
            func.max(Atendimento.data_atendimento).label('ultimo'),
            func.count(Atendimento.id).label('total_atend')
        )
        .join(Atendimento, Atendimento.id_pessoa == Pessoa.id)
        .filter(~Pessoa.id.in_(ids_com_solic), Atendimento.status == ATENDIMENTO_CONCLUIDO)
        .group_by(Pessoa.id)
        .order_by(func.count(Atendimento.id).desc())
        .limit(20)
        .all()
    )
    return [
        {
            'id':          p.id,
            'nome':        p.nome_razao_social,
            'ultimo':      ultimo.strftime('%d/%m/%Y') if ultimo else '—',
            'total_atend': total_atend,
        }
        for p, ultimo, total_atend in rows
    ]


def _em_risco():
    """Solicitação parada há +30 dias com status Pendente ou Em Análise."""
    corte = date.today() - timedelta(days=30)
    status_abertos = db.session.query(Status.id).filter(
        db.or_(
            Status.descricao.ilike('%pendente%'),
            Status.descricao.ilike('%análise%'),
        )
    ).subquery()

    rows = (
        db.session.query(
            Pessoa,
            Solicitacao,
            func.max(Atendimento.data_atendimento).label('ultimo_atend')
        )
        .join(Solicitacao, Solicitacao.id_pessoa == Pessoa.id)
        .outerjoin(Atendimento, db.and_(Atendimento.id_pessoa == Pessoa.id,
                                        Atendimento.status == ATENDIMENTO_CONCLUIDO))
        .filter(
            Solicitacao.id_status.in_(status_abertos),
            Solicitacao.data_solicitacao <= corte,
        )
        .group_by(Pessoa.id, Solicitacao.id)
        .order_by(Solicitacao.data_solicitacao.asc())
        .limit(20)
        .all()
    )
    return [
        {
            'id':           p.id,
            'nome':         p.nome_razao_social,
            'solic_id':     s.id,
            'solic_tipo':   s.tipo_solicitacao.descricao if s.tipo_solicitacao else '—',
            'solic_data':   s.data_solicitacao.strftime('%d/%m/%Y'),
            'dias_parada':  (date.today() - s.data_solicitacao).days,
            'ultimo_atend': ultimo_atend.strftime('%d/%m/%Y') if ultimo_atend else '—',
        }
        for p, s, ultimo_atend in rows
    ]


def _distribuicao_bairros(data_inicio, data_fim):
    """Top 10 bairros por empreendedores únicos atendidos no período.
    No PostgreSQL usa split_part para extrair bairro do campo endereco."""
    filtro_periodo = [
        Atendimento.data_atendimento >= data_inicio,
        Atendimento.data_atendimento <= data_fim,
        Atendimento.status == ATENDIMENTO_CONCLUIDO,
    ]

    if db.engine.dialect.name == 'postgresql':
        bairro_expr = func.trim(
            func.coalesce(
                func.nullif(func.trim(Pessoa.bairro), ''),
                func.nullif(func.trim(
                    func.split_part(Pessoa.endereco, ',', 3)
                ), ''),
            )
        )
        rows = (
            db.session.query(
                bairro_expr.label('bairro'),
                func.count(distinct(Pessoa.id)).label('unicos')
            )
            .join(Atendimento, Atendimento.id_pessoa == Pessoa.id)
            .filter(*filtro_periodo, bairro_expr.isnot(None))
            .group_by(bairro_expr)
            .order_by(func.count(distinct(Pessoa.id)).desc())
            .limit(10)
            .all()
        )
        sem_bairro = (
            db.session.query(func.count(distinct(Atendimento.id_pessoa)))
            .join(Pessoa, Pessoa.id == Atendimento.id_pessoa)
            .filter(
                *filtro_periodo,
                db.or_(Pessoa.bairro == None, Pessoa.bairro == ''),
                db.or_(
                    Pessoa.endereco == None,
                    func.trim(func.split_part(Pessoa.endereco, ',', 3)) == '',
                ),
            )
            .scalar() or 0
        )
    else:
        rows = (
            db.session.query(
                Pessoa.bairro.label('bairro'),
                func.count(distinct(Pessoa.id)).label('unicos')
            )
            .join(Atendimento, Atendimento.id_pessoa == Pessoa.id)
            .filter(
                *filtro_periodo,
                Pessoa.bairro != None,
                Pessoa.bairro != '',
            )
            .group_by(Pessoa.bairro)
            .order_by(func.count(distinct(Pessoa.id)).desc())
            .limit(10)
            .all()
        )
        sem_bairro = (
            db.session.query(func.count(distinct(Atendimento.id_pessoa)))
            .join(Pessoa, Pessoa.id == Atendimento.id_pessoa)
            .filter(
                *filtro_periodo,
                db.or_(Pessoa.bairro == None, Pessoa.bairro == ''),
            )
            .scalar() or 0
        )

    return {
        'bairros':    [{'bairro': r.bairro, 'unicos': r.unicos} for r in rows],
        'sem_bairro': sem_bairro,
    }


def _geocodificar_bairros(bairros_lista, municipio=marca.MUNICIPIO, estado=marca.UF):
    """Retorna {bairro: [lat, lng]} usando ParametroMunicipio como cache.
    Chave: 'cache_coord:{bairro}', valor: 'lat,lng' (<200 chars cada)."""
    resultado = {}
    pendentes = []

    for bairro in bairros_lista:
        param = ParametroMunicipio.query.filter_by(
            chave=f'cache_coord:{bairro}'
        ).first()
        if param and param.valor:
            try:
                lat, lng = param.valor.split(',')
                resultado[bairro] = [float(lat), float(lng)]
            except Exception:
                pendentes.append(bairro)
        else:
            pendentes.append(bairro)

    if pendentes:
        headers = {'User-Agent': f'{marca.APP_NOME} demo/1.0'}
        for bairro in pendentes:
            try:
                url = (
                    'https://nominatim.openstreetmap.org/search?'
                    + urllib.parse.urlencode({
                        'q': f'{bairro}, {municipio}, {estado}, Brasil',
                        'format': 'json',
                        'limit': 1,
                        'countrycodes': 'br',
                    })
                )
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    dados = json.loads(resp.read().decode())
                if dados:
                    lat = float(dados[0]['lat'])
                    lng = float(dados[0]['lon'])
                    resultado[bairro] = [lat, lng]
                    chave = f'cache_coord:{bairro}'
                    p = ParametroMunicipio.query.filter_by(chave=chave).first()
                    valor_str = f'{lat},{lng}'
                    if p:
                        p.valor = valor_str
                    else:
                        db.session.add(ParametroMunicipio(
                            chave=chave,
                            valor=valor_str,
                            descricao=f'Coordenadas geocodificadas — {bairro}',
                        ))
            except Exception:
                pass
            time.sleep(1)  # Nominatim: máx. 1 req/s

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return resultado


_cache_poligonos = {}


def _buscar_poligonos_bairros(municipio=marca.MUNICIPIO, estado=marca.UF):
    """GeoJSON FeatureCollection com polígonos dos bairros via Overpass API.
    Cache em memória de módulo (persiste enquanto o processo viver).
    Valor pode exceder 200 chars — impossível usar ParametroMunicipio."""
    global _cache_poligonos
    if municipio in _cache_poligonos:
        return _cache_poligonos[municipio]

    query = f"""
[out:json][timeout:30];
(
  relation["place"~"suburb|neighbourhood|quarter"]
          ["name"]
          ({marca.MAPA_BBOX});
  way["place"~"suburb|neighbourhood|quarter"]
     ["name"]
     ({marca.MAPA_BBOX});
);
out geom;
"""
    headers = {'User-Agent': f'{marca.APP_NOME} demo/1.0'}

    try:
        req = urllib.request.Request(
            'https://overpass-api.de/api/interpreter',
            data=('data=' + urllib.parse.quote(query)).encode(),
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados = json.loads(resp.read().decode())
    except Exception:
        vazio = {'type': 'FeatureCollection', 'features': []}
        _cache_poligonos[municipio] = vazio
        return vazio

    features = []
    for el in dados.get('elements', []):
        nome = el.get('tags', {}).get('name', '')
        if not nome:
            continue
        coords = None
        if el['type'] == 'way' and 'geometry' in el:
            coords = [[[p['lon'], p['lat']] for p in el['geometry']]]
        elif el['type'] == 'relation' and 'members' in el:
            outer = next(
                (m for m in el['members']
                 if m.get('role') == 'outer' and 'geometry' in m),
                None,
            )
            if outer:
                coords = [[[p['lon'], p['lat']] for p in outer['geometry']]]
        if coords:
            features.append({
                'type': 'Feature',
                'properties': {'name': nome},
                'geometry': {'type': 'Polygon', 'coordinates': coords},
            })

    geojson = {'type': 'FeatureCollection', 'features': features}
    _cache_poligonos[municipio] = geojson
    return geojson


# ── Aba Demanda ────────────────────────────────────────────────────────────────
@analise_bp.route('/demanda')
@login_required
@cache.cached(timeout=300, query_string=True)
def demanda():
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    data_inicio, data_fim = _periodo_from_request()

    hoje = date.today()
    if hoje.month == 1:
        mes_ant_inicio = hoje.replace(year=hoje.year-1, month=12, day=1)
    else:
        mes_ant_inicio = hoje.replace(month=hoje.month-1, day=1)
    mes_ant_fim = hoje.replace(day=1) - timedelta(days=1)

    kpis_d      = _kpis_demanda(data_inicio, data_fim)
    por_tipo    = _por_servico(data_inicio, data_fim)
    heatmap     = _heatmap_meses_tipos(data_inicio, data_fim)
    dias_semana = _dia_semana(data_inicio, data_fim)
    hora_pico   = _hora_pico(data_inicio, data_fim)
    bairros     = _distribuicao_bairros(data_inicio, data_fim)

    nomes_bairros  = [b['bairro'] for b in bairros['bairros'] if b.get('bairro')]
    coords_bairros  = _geocodificar_bairros(nomes_bairros)
    poligonos_bairros = _buscar_poligonos_bairros()

    return render_template('analise/demanda.html',
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           hoje=hoje,
                           mes_ant_inicio=mes_ant_inicio,
                           mes_ant_fim=mes_ant_fim,
                           kpis_d=kpis_d,
                           por_tipo=por_tipo,
                           heatmap=heatmap,
                           dias_semana=dias_semana,
                           hora_pico=hora_pico,
                           bairros=bairros,
                           coords_bairros=coords_bairros,
                           poligonos_bairros=poligonos_bairros)


# ── Aba Perfil ─────────────────────────────────────────────────────────────────

def _kpis_perfil():
    """4 KPIs da aba Perfil: MEIs, situação ativa, PF puras, sem dados RF."""
    total = db.session.query(func.count(Pessoa.id)).scalar() or 0

    total_mei = (
        db.session.query(func.count(Pessoa.id))
        .filter(Pessoa.mei == True)
        .scalar() or 0
    )

    total_com_rf = (
        db.session.query(func.count(Pessoa.id))
        .filter(Pessoa.situacao_cadastral.isnot(None), Pessoa.situacao_cadastral != '')
        .scalar() or 0
    )

    total_ativa = (
        db.session.query(func.count(Pessoa.id))
        .filter(Pessoa.situacao_cadastral == 'ATIVA')
        .scalar() or 0
    )

    total_pf = (
        db.session.query(func.count(Pessoa.id))
        .filter(
            Pessoa.cpf.isnot(None), Pessoa.cpf != '',
            db.or_(Pessoa.cnpj == None, Pessoa.cnpj == ''),
        )
        .scalar() or 0
    )

    return {
        'total':        total,
        'total_mei':    total_mei,
        'pct_mei':      round(total_mei / total * 100) if total else 0,
        'total_ativa':  total_ativa,
        'pct_ativa':    round(total_ativa / total_com_rf * 100) if total_com_rf else 0,
        'total_pf':     total_pf,
        'total_com_rf': total_com_rf,
        'pct_sem_rf':   round((total - total_com_rf) / total * 100) if total else 0,
    }


def _por_escolaridade():
    """Distribuição por nível de escolaridade."""
    rows = (
        db.session.query(
            Pessoa.nivel_escolar,
            func.count(Pessoa.id).label('total')
        )
        .filter(Pessoa.nivel_escolar.isnot(None), Pessoa.nivel_escolar != '')
        .group_by(Pessoa.nivel_escolar)
        .order_by(func.count(Pessoa.id).desc())
        .all()
    )
    sem_info = (
        db.session.query(func.count(Pessoa.id))
        .filter(db.or_(Pessoa.nivel_escolar == None, Pessoa.nivel_escolar == ''))
        .scalar() or 0
    )
    return {
        'dados':    [{'nivel': r.nivel_escolar, 'total': r.total} for r in rows],
        'sem_info': sem_info,
    }


def _distribuicao_sexo():
    """Distribuição por sexo dos cadastros."""
    rows = (
        db.session.query(
            Pessoa.sexo,
            func.count(Pessoa.id).label('total')
        )
        .filter(Pessoa.sexo != None, Pessoa.sexo != '')
        .group_by(Pessoa.sexo)
        .order_by(func.count(Pessoa.id).desc())
        .all()
    )
    total_com_sexo = sum(r.total for r in rows)
    sem_info = db.session.query(func.count(Pessoa.id)).filter(
        db.or_(Pessoa.sexo == None, Pessoa.sexo == '')
    ).scalar() or 0
    total_geral = total_com_sexo + sem_info

    LABELS = {'M': 'Masculino', 'F': 'Feminino'}
    return {
        'dados': [
            {
                'sexo':  LABELS.get(r.sexo, r.sexo),
                'total': r.total,
                'pct':   round(r.total / total_geral * 100) if total_geral else 0,
            }
            for r in rows
        ],
        'sem_info': sem_info,
        'total':    total_geral,
    }


@analise_bp.route('/perfil')
@login_required
@cache.cached(timeout=300, query_string=True)
def perfil():
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    kpis_p          = _kpis_perfil()
    dist_tipo       = _distribuicao_tipo()
    situacao        = _situacao_cadastral()
    top_cnaes       = _top_cnaes()
    dist_sexo       = _distribuicao_sexo()
    por_escolaridade = _por_escolaridade()

    return render_template('analise/perfil.html',
                           kpis_p=kpis_p,
                           dist_tipo=dist_tipo,
                           situacao=situacao,
                           top_cnaes=top_cnaes,
                           dist_sexo=dist_sexo,
                           por_escolaridade=por_escolaridade)


# ── Aba Potencial e Alertas ────────────────────────────────────────────────────
@analise_bp.route('/potencial')
@login_required
@cache.cached(timeout=300, query_string=True)
def potencial():
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    kpis_pot      = _kpis_potencial()
    campeoes      = _campeoes()
    em_risco_list = _em_risco()
    inativos      = _inativos()
    nunca_solic   = _nunca_solicitaram()

    return render_template('analise/potencial.html',
                           kpis_pot=kpis_pot,
                           campeoes=campeoes,
                           em_risco=em_risco_list,
                           inativos=inativos,
                           nunca_solic=nunca_solic)


# ── Exportações ────────────────────────────────────────────────────────────────

_ABAS_VALIDAS = ('executivo', 'jornada', 'demanda', 'perfil', 'potencial')


def _dados_exportacao(aba, data_inicio, data_fim):
    """Retorna os dados necessários para exportar a aba solicitada."""
    filtros = {'data_inicio': data_inicio, 'data_fim': data_fim}

    if aba == 'executivo':
        kpis = _kpis(data_inicio, data_fim)
        ini_ant, fim_ant = _periodo_anterior(data_inicio, data_fim)
        kpis_ant = _kpis(ini_ant, fim_ant)
        variacoes = {
            'unicos':      _variacao(kpis['unicos'],      kpis_ant['unicos']),
            'novos_meis':  _variacao(kpis['novos_meis'],  kpis_ant['novos_meis']),
            'total_atend': _variacao(kpis['total_atend'], kpis_ant['total_atend']),
        }
        return dict(kpis=kpis, variacoes=variacoes,
                    evolucao=_evolucao_mensal(data_inicio, data_fim),
                    top_tipos=_top_tipos(data_inicio, data_fim),
                    filtros=filtros)

    if aba == 'jornada':
        return dict(funil=_funil_conversao(data_inicio, data_fim),
                    top10=_top10_mais_atendidos(data_inicio, data_fim),
                    uma_visita=_uma_visita_apenas(data_inicio, data_fim),
                    tempo_medio=_tempo_medio_retorno(data_inicio, data_fim))

    if aba == 'demanda':
        return dict(heatmap=_heatmap_meses_tipos(data_inicio, data_fim),
                    dias_semana=_dia_semana(data_inicio, data_fim),
                    hora_pico=_hora_pico(data_inicio, data_fim),
                    bairros=_distribuicao_bairros(data_inicio, data_fim),
                    filtros=filtros)

    if aba == 'perfil':
        return dict(dist_tipo=_distribuicao_tipo(), top_cnaes=_top_cnaes(),
                    situacao=_situacao_cadastral(), dist_porte=_distribuicao_porte(),
                    dist_sexo=_distribuicao_sexo())

    if aba == 'potencial':
        return dict(campeoes=_campeoes(), inativos=_inativos(),
                    nunca_solic=_nunca_solicitaram(), em_risco=_em_risco())


@analise_bp.route('/exportar/xlsx/<aba>')
@login_required
def exportar_xlsx(aba):
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))
    if aba not in _ABAS_VALIDAS:
        flash('Aba inválida.', 'danger')
        return redirect(url_for('analise.index'))

    import io
    from flask import send_file
    from .relatorios.exporters import (
        gerar_xlsx_analise_executivo, gerar_xlsx_analise_jornada,
        gerar_xlsx_analise_demanda, gerar_xlsx_analise_perfil,
        gerar_xlsx_analise_potencial,
    )

    data_inicio, data_fim = _periodo_from_request()
    d = _dados_exportacao(aba, data_inicio, data_fim)

    geradores = {
        'executivo': lambda: gerar_xlsx_analise_executivo(**d),
        'jornada':   lambda: gerar_xlsx_analise_jornada(**d),
        'demanda':   lambda: gerar_xlsx_analise_demanda(**d),
        'perfil':    lambda: gerar_xlsx_analise_perfil(**d),
        'potencial': lambda: gerar_xlsx_analise_potencial(**d),
    }
    nomes = {
        'executivo': f"analise_executivo_{data_inicio}_{data_fim}.xlsx",
        'jornada':   "analise_jornada.xlsx",
        'demanda':   f"analise_demanda_{data_inicio}_{data_fim}.xlsx",
        'perfil':    "analise_perfil.xlsx",
        'potencial': "analise_potencial.xlsx",
    }

    return send_file(
        io.BytesIO(geradores[aba]()),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nomes[aba],
    )


@analise_bp.route('/exportar/pdf/<aba>')
@login_required
def exportar_pdf(aba):
    if not _requer_admin_supervisor():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))
    if aba not in _ABAS_VALIDAS:
        flash('Aba inválida.', 'danger')
        return redirect(url_for('analise.index'))

    import io
    from flask import send_file
    from .relatorios.exporters import (
        gerar_pdf_analise_executivo, gerar_pdf_analise_jornada,
        gerar_pdf_analise_demanda, gerar_pdf_analise_perfil,
        gerar_pdf_analise_potencial,
    )

    data_inicio, data_fim = _periodo_from_request()
    d = _dados_exportacao(aba, data_inicio, data_fim)

    geradores = {
        'executivo': lambda: gerar_pdf_analise_executivo(**d),
        'jornada':   lambda: gerar_pdf_analise_jornada(**d),
        'demanda':   lambda: gerar_pdf_analise_demanda(**d),
        'perfil':    lambda: gerar_pdf_analise_perfil(**d),
        'potencial': lambda: gerar_pdf_analise_potencial(**d),
    }
    nomes = {
        'executivo': f"analise_executivo_{data_inicio}_{data_fim}.pdf",
        'jornada':   "analise_jornada.pdf",
        'demanda':   f"analise_demanda_{data_inicio}_{data_fim}.pdf",
        'perfil':    "analise_perfil.pdf",
        'potencial': "analise_potencial.pdf",
    }

    return send_file(
        io.BytesIO(geradores[aba]()),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nomes[aba],
    )
