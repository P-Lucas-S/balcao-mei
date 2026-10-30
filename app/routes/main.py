import re
from datetime import date, timedelta
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required
from sqlalchemy import func, extract, distinct
from .. import db
from ..escopo import ids_da_equipe
from ..models import (Pessoa, Atendimento, Solicitacao, Status, Usuario,
                      AtendimentoServico, LogAcao, ATENDIMENTO_CONCLUIDO)

main_bp = Blueprint('main', __name__)

# Meses em português — strftime('%B') retorna em inglês no Windows
_MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março',    4: 'Abril',
    5: 'Maio',    6: 'Junho',     7: 'Julho',     8: 'Agosto',
    9: 'Setembro',10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
}


@main_bp.route('/busca')
@login_required
def busca():
    q = request.args.get('q', '').strip()

    if not q or len(q) < 2:
        return render_template('busca.html', q=q,
                               pessoas=[], atendimentos=[], solicitacoes=[],
                               total=0)

    q_digitos = re.sub(r'\D', '', q)
    like = f'%{q}%'

    query_p = Pessoa.visiveis().filter(
        db.or_(
            Pessoa.nome_razao_social.ilike(like),
            Pessoa.cpf.ilike(like),
            Pessoa.cnpj.ilike(like),
        )
    )
    if q_digitos:
        like_d = f'%{q_digitos}%'
        query_p = Pessoa.visiveis().filter(
            db.or_(
                Pessoa.nome_razao_social.ilike(like),
                Pessoa.cpf.ilike(like),
                Pessoa.cnpj.ilike(like),
                db.func.regexp_replace(Pessoa.cpf,  r'\D', '', 'g').ilike(like_d),
                db.func.regexp_replace(Pessoa.cnpj, r'\D', '', 'g').ilike(like_d),
            )
        )
    pessoas = query_p.order_by(Pessoa.nome_razao_social).limit(10).all()

    atendimentos = (
        Atendimento.query
        .join(Atendimento.pessoa)
        .filter(Pessoa.nome_razao_social.ilike(like),
                Pessoa.removido_em.is_(None))
        .order_by(Atendimento.data_atendimento.desc())
        .limit(10)
        .all()
    )

    solicitacoes = (
        Solicitacao.query
        .join(Solicitacao.pessoa)
        .filter(Pessoa.nome_razao_social.ilike(like),
                Pessoa.removido_em.is_(None))
        .order_by(Solicitacao.data_solicitacao.desc())
        .limit(10)
        .all()
    )

    total = len(pessoas) + len(atendimentos) + len(solicitacoes)

    return render_template('busca.html', q=q,
                           pessoas=pessoas,
                           atendimentos=atendimentos,
                           solicitacoes=solicitacoes,
                           total=total)


@main_bp.route('/')
@login_required
def raiz():
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    hoje = date.today()

    from flask_login import current_user
    perfil = current_user.perfil.nome

    # IDs visíveis conforme perfil — regra única em app/escopo.py.
    # `None` = administrador, sem filtro.
    ids_usuarios_visiveis = ids_da_equipe()

    # Filtro de usuário selecionado (supervisor e admin)
    filtro_usuario_id = request.args.get('filtro_usuario', type=int)
    if filtro_usuario_id and perfil != 'atendente':
        # Validar que o usuário selecionado está dentro dos visíveis
        if ids_usuarios_visiveis is None or filtro_usuario_id in ids_usuarios_visiveis:
            ids_filtro = [filtro_usuario_id]
        else:
            ids_filtro = ids_usuarios_visiveis
    else:
        ids_filtro = ids_usuarios_visiveis

    def _filtrar_atend(q):
        # Rascunho não é número oficial: um atendimento aberto e abandonado
        # não pode contar como atendimento feito. Vale para KPIs, gráfico,
        # funil e a lista de recentes — quem quer ver rascunho vai à lista
        # de atendimentos, onde eles aparecem com o selo "Em aberto".
        q = q.filter(Atendimento.status == ATENDIMENTO_CONCLUIDO)
        if ids_filtro is not None:
            q = q.filter(Atendimento.id_usuario.in_(ids_filtro))
        return q

    def _filtrar_solic(q):
        if ids_filtro is not None:
            q = q.filter(Solicitacao.id_usuario.in_(ids_filtro))
        return q

    usuarios_filtro = []
    if perfil in ['administrador', 'supervisor']:
        if ids_usuarios_visiveis is None:
            usuarios_filtro = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
        else:
            usuarios_filtro = Usuario.query.filter(
                Usuario.id.in_(ids_usuarios_visiveis),
                Usuario.ativo == True
            ).order_by(Usuario.nome).all()

    # ── Totais gerais ──────────────────────────────────────────────────────
    # Pessoas são cadastros globais — não pertencem a nenhum usuário.
    # O card "Cadastros" e o funil de conversão usam sempre o total geral.
    total_pessoas = Pessoa.query.count()

    # Atendimentos: mês atual e mês anterior
    mes_atual_inicio = hoje.replace(day=1)
    if hoje.month == 1:
        mes_ant_inicio = hoje.replace(year=hoje.year - 1, month=12, day=1)
    else:
        mes_ant_inicio = hoje.replace(month=hoje.month - 1, day=1)

    atend_mes_atual = (
        _filtrar_atend(Atendimento.query)
        .filter(Atendimento.data_atendimento >= mes_atual_inicio)
        .count()
    )
    atend_mes_ant = (
        _filtrar_atend(Atendimento.query)
        .filter(
            Atendimento.data_atendimento >= mes_ant_inicio,
            Atendimento.data_atendimento < mes_atual_inicio,
        )
        .count()
    )

    # Atendimentos hoje
    atend_hoje = (
        _filtrar_atend(Atendimento.query)
        .filter(Atendimento.data_atendimento == hoje)
        .count()
    )

    # Variação proporcional — compara atend_mes_atual com o mesmo nº de dias do mês anterior
    # Evita o "-99%" no início do mês ao comparar parciais equivalentes
    dias_passados = hoje.day
    ultimo_dia_mes_ant = mes_atual_inicio - timedelta(days=1)
    dias_mes_ant = ultimo_dia_mes_ant.day
    atend_mes_ant_proporcional = atend_mes_ant * dias_passados / dias_mes_ant
    if atend_mes_ant_proporcional > 0:
        variacao_proporcional = round(
            (atend_mes_atual - atend_mes_ant_proporcional) / atend_mes_ant_proporcional * 100
        )
    else:
        variacao_proporcional = None
    mes_ant_nome = _MESES_PT[mes_ant_inicio.month]

    # ── Solicitações por status ────────────────────────────────────────────
    # Filtra apenas os 4 status do workflow ativo — exclui legados (Aberta, Em andamento, etc.)
    _WORKFLOW_STATUS = {'pendente', 'em análise', 'aprovado', 'recusado'}
    todos_status = [
        s for s in Status.query.order_by(Status.id).all()
        if s.descricao.lower() in _WORKFLOW_STATUS
    ]
    contagens_status = (
        _filtrar_solic(
            db.session.query(
                Solicitacao.id_status,
                func.count(Solicitacao.id).label('total')
            )
        )
        .group_by(Solicitacao.id_status)
        .all()
    )
    mapa_contagens = {row.id_status: row.total for row in contagens_status}
    solic_por_status = {}
    for s in todos_status:
        solic_por_status[s.descricao] = {
            'total': mapa_contagens.get(s.id, 0),
            'id':    s.id,
        }

    # ── 5 atendimentos mais recentes ──────────────────────────────────────
    from sqlalchemy.orm import joinedload as _jl3, selectinload as _sl3
    atendimentos_recentes = (
        _filtrar_atend(Atendimento.query)
        .options(
            _jl3(Atendimento.pessoa),
            _jl3(Atendimento.usuario),
            _sl3(Atendimento.servicos).joinedload(AtendimentoServico.servico),
        )
        .order_by(Atendimento.data_atendimento.desc(),
                  Atendimento.hora_atendimento.desc())
        .limit(5)
        .all()
    )

    # ── 5 solicitações mais recentes ──────────────────────────────────────
    from sqlalchemy.orm import joinedload as _jl4
    solicitacoes_recentes = (
        _filtrar_solic(Solicitacao.query)
        .options(
            _jl4(Solicitacao.pessoa),
            _jl4(Solicitacao.usuario),
            _jl4(Solicitacao.status),
            _jl4(Solicitacao.tipo_solicitacao),
        )
        .order_by(Solicitacao.data_solicitacao.desc(), Solicitacao.id.desc())
        .limit(5)
        .all()
    )

    # Formato: "Março/2026" — usando dicionário pt-BR para garantir no Windows
    mes_atual = f"{_MESES_PT[hoje.month]}/{hoje.year}"

    ano_atual = hoje.year
    meses_passados_no_ano = hoje.month
    mes_atual_abrev = _MESES_PT[hoje.month][:3]

    # ── Atendimentos por mês no ano atual (para o gráfico) ────────────────
    q_grafico = db.session.query(
        extract('month', Atendimento.data_atendimento).label('mes'),
        func.count(Atendimento.id).label('total'),
    ).filter(extract('year', Atendimento.data_atendimento) == ano_atual,
             Atendimento.status == ATENDIMENTO_CONCLUIDO)
    if ids_filtro is not None:
        q_grafico = q_grafico.filter(Atendimento.id_usuario.in_(ids_filtro))
    atend_por_mes = (
        q_grafico
        .group_by(extract('month', Atendimento.data_atendimento))
        .order_by(extract('month', Atendimento.data_atendimento))
        .all()
    )
    grafico_meses = [0] * 12
    for row in atend_por_mes:
        grafico_meses[int(row.mes) - 1] = row.total

    # ── Top 3 atendentes do ano ───────────────────────────────────────────
    q_top = (
        db.session.query(
            Usuario.nome.label('nome'),
            func.count(Atendimento.id).label('total'),
        )
        .join(Atendimento, Atendimento.id_usuario == Usuario.id)
        .filter(extract('year', Atendimento.data_atendimento) == ano_atual,
                Atendimento.status == ATENDIMENTO_CONCLUIDO)
    )
    if ids_usuarios_visiveis is not None:
        q_top = q_top.filter(Atendimento.id_usuario.in_(ids_usuarios_visiveis))
    top_atendentes = (
        q_top
        .group_by(Usuario.id, Usuario.nome)
        .order_by(func.count(Atendimento.id).desc())
        .limit(3)
        .all()
    )
    top_atendentes = [{'nome': r.nome, 'total': r.total} for r in top_atendentes]

    # ── Solicitações paradas (Pendente ou Em Análise há mais de 30 dias) ──
    limite_paradas = date.today() - timedelta(days=30)

    status_nao_finais = (
        db.session.query(Status.id)
        .filter(
            db.or_(
                Status.descricao.ilike('%pendente%'),
                Status.descricao.ilike('%análise%'),
                Status.descricao.ilike('%analise%'),
            )
        )
        .all()
    )
    ids_nao_finais = [s.id for s in status_nao_finais]

    solic_paradas = []
    if ids_nao_finais:
        solic_paradas = (
            _filtrar_solic(Solicitacao.query)
            .filter(
                Solicitacao.id_status.in_(ids_nao_finais),
                Solicitacao.data_solicitacao <= limite_paradas,
            )
            .order_by(Solicitacao.data_solicitacao.asc())
            .limit(10)
            .all()
        )
    qtd_paradas = len(solic_paradas)

    total_nao_finais = 0
    if ids_nao_finais:
        total_nao_finais = (
            _filtrar_solic(Solicitacao.query)
            .filter(Solicitacao.id_status.in_(ids_nao_finais))
            .count()
        )
    pct_paradas = round(qtd_paradas / total_nao_finais * 100) if total_nao_finais > 0 else 0

    limite_alerta_inicio = hoje - timedelta(days=30)
    limite_alerta_fim    = hoje - timedelta(days=27)
    solic_quase_paradas  = 0
    if ids_nao_finais:
        solic_quase_paradas = (
            _filtrar_solic(Solicitacao.query)
            .filter(
                Solicitacao.id_status.in_(ids_nao_finais),
                Solicitacao.data_solicitacao > limite_alerta_inicio,
                Solicitacao.data_solicitacao <= limite_alerta_fim,
            )
            .count()
        )

    # ── Pendências de exclusão (admin) ────────────────────────────────────
    pendencias_count = 0
    if perfil == 'administrador':
        from ..models import SolicitacaoExclusao
        pendencias_count = SolicitacaoExclusao.query.filter_by(status='pendente').count()

    # ── Pendências do usuário logado ──────────────────────────────────────
    from flask_login import current_user as _cu
    minhas_pendencias = 0
    if ids_nao_finais:
        minhas_pendencias = (
            Solicitacao.query
            .filter(
                Solicitacao.id_usuario == _cu.id,
                Solicitacao.id_status.in_(ids_nao_finais),
            )
            .count()
        )

    # ── Funil de conversão ────────────────────────────────────────────────
    total_cadastrados = total_pessoas

    total_com_atendimento = (
        _filtrar_atend(
            db.session.query(func.count(distinct(Atendimento.id_pessoa)))
        )
        .scalar() or 0
    )
    total_com_solicitacao = (
        _filtrar_solic(
            db.session.query(func.count(distinct(Solicitacao.id_pessoa)))
        )
        .scalar() or 0
    )
    _ids_aprov = [
        s.id for s in Status.query.filter(Status.descricao.ilike('%aprovado%')).all()
    ]
    total_aprovadas = 0
    if _ids_aprov:
        total_aprovadas = (
            _filtrar_solic(
                db.session.query(func.count(distinct(Solicitacao.id_pessoa)))
                .filter(Solicitacao.id_status.in_(_ids_aprov))
            )
            .scalar() or 0
        )

    pct_atendimento = round(total_com_atendimento / total_cadastrados * 100) if total_cadastrados > 0 else 0
    pct_solicitacao = round(total_com_solicitacao / total_cadastrados * 100) if total_cadastrados > 0 else 0
    pct_aprovadas   = round(total_aprovadas   / total_cadastrados * 100) if total_cadastrados > 0 else 0

    # ── Top 5 bairros ─────────────────────────────────────────────────────
    # Bairro é atributo global do cadastro — não filtra por usuário.
    # Prefere Pessoa.bairro (preenchido via ViaCEP); extrai da 3ª parte
    # do campo 'endereco' quando vazio (formato padrão do cadastro:
    # "Logradouro, Nº, Bairro, Cidade - UF").
    # split_part() é PostgreSQL-only; SQLite (testes) usa apenas Pessoa.bairro.
    _is_postgres = db.engine.dialect.name == 'postgresql'
    if _is_postgres:
        _bairro_expr = func.trim(
            func.coalesce(
                func.nullif(func.trim(Pessoa.bairro), ''),
                func.nullif(func.trim(func.split_part(Pessoa.endereco, ',', 3)), ''),
            )
        )
    else:
        _bairro_expr = func.nullif(func.trim(Pessoa.bairro), '')
    top_bairros = [
        {'bairro': r.bairro, 'total': r.total}
        for r in (
            db.session.query(
                _bairro_expr.label('bairro'),
                func.count(Pessoa.id).label('total'),
            )
            .filter(_bairro_expr.isnot(None))
            .group_by(_bairro_expr)
            .order_by(func.count(Pessoa.id).desc())
            .limit(5)
            .all()
        )
    ]

    # ── Novos cadastros por mês (admin only) ──────────────────────────────
    # Usa o primeiro registro de LogAcao por pessoa como proxy de data de criação,
    # já que Pessoa não possui campo created_at mapeado no model.
    if perfil == 'administrador':
        _primeiro_log = (
            db.session.query(
                LogAcao.entidade_id,
                func.min(LogAcao.created_at).label('criado_em'),
            )
            .filter(LogAcao.entidade == 'pessoa')
            .group_by(LogAcao.entidade_id)
            .subquery()
        )
        _cad_rows = (
            db.session.query(
                extract('month', _primeiro_log.c.criado_em).label('mes'),
                func.count(_primeiro_log.c.entidade_id).label('total'),
            )
            .filter(extract('year', _primeiro_log.c.criado_em) == ano_atual)
            .group_by(extract('month', _primeiro_log.c.criado_em))
            .order_by(extract('month', _primeiro_log.c.criado_em))
            .all()
        )
        grafico_cadastros = [0] * 12
        for row in _cad_rows:
            grafico_cadastros[int(row.mes) - 1] = row.total
    else:
        grafico_cadastros = []

    return render_template(
        'dashboard.html',
        hoje=hoje,
        total_pessoas=total_pessoas,
        atend_mes_atual=atend_mes_atual,
        atend_mes_ant=atend_mes_ant,
        atend_hoje=atend_hoje,
        dias_passados=dias_passados,
        variacao_proporcional=variacao_proporcional,
        mes_ant_nome=mes_ant_nome,
        solic_por_status=solic_por_status,
        atendimentos_recentes=atendimentos_recentes,
        solicitacoes_recentes=solicitacoes_recentes,
        mes_atual=mes_atual,
        grafico_meses=grafico_meses,
        top_atendentes=top_atendentes,
        ano_atual=ano_atual,
        meses_passados_no_ano=meses_passados_no_ano,
        mes_atual_abrev=mes_atual_abrev,
        solic_paradas=solic_paradas,
        qtd_paradas=qtd_paradas,
        total_nao_finais=total_nao_finais,
        pct_paradas=pct_paradas,
        solic_quase_paradas=solic_quase_paradas,
        limite_paradas=limite_paradas,
        minhas_pendencias=minhas_pendencias,
        usuarios_filtro=usuarios_filtro,
        filtro_usuario_id=filtro_usuario_id,
        pendencias_count=pendencias_count,
        total_cadastrados=total_cadastrados,
        total_com_atendimento=total_com_atendimento,
        total_com_solicitacao=total_com_solicitacao,
        total_aprovadas=total_aprovadas,
        pct_atendimento=pct_atendimento,
        pct_solicitacao=pct_solicitacao,
        pct_aprovadas=pct_aprovadas,
        top_bairros=top_bairros,
        grafico_cadastros=grafico_cadastros,
    )


@main_bp.route('/privacidade')
def privacidade():
    return render_template('privacidade.html')