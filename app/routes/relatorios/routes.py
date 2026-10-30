"""
relatorios/routes.py
Blueprint de relatórios do Balcão MEI.
"""
from datetime import date, datetime, timedelta
from flask import (
    Blueprint, render_template, request,
    send_file, flash, redirect, url_for, abort
)
from flask_login import current_user, login_required
import io

from ...escopo import ids_da_equipe

from .queries import (
    atendimentos_por_periodo,
    totais_por_dia,
    desempenho_por_usuario,
    atendimentos_por_usuario_detalhe,
    listar_atendentes,
    totais_por_dia_usuario,
    tipos_mais_realizados,
    get_usuario_por_id,
    atendimentos_por_tipo,
    solicitacoes_por_status_periodo,
    solicitacoes_por_tipo_periodo,
    total_atendimentos_periodo,
    query_evolucao_mensal,
)
from .exporters import (
    gerar_pdf_atendimentos,
    gerar_pdf_desempenho,
    gerar_excel_atendimentos,
    gerar_excel_desempenho,
    gerar_pdf_executivo,
    gerar_excel_executivo,
)

MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Marco', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

CATEGORIAS_SOLIC = {
    'Cessão de Espaço': [
        'box', 'quiosque', 'trailer', 'barraca', 'espaço',
        'relocação', 'permissão', 'cessão', 'termo de permis',
        'espaço público'
    ],
    'Autorizações': [
        'autorização', 'autorizar', 'licença', 'funcionamento',
        'alvará', 'regulariz', 'atestado'
    ],
    'Eventos e Feiras': [
        'evento', 'feira', 'credenciamento', 'participação', 'inss'
    ],
    'Infraestrutura': [
        'água', 'esgoto', 'elétric', 'ligação', 'abastecimento',
        'infraestrutura', 'recurso'
    ],
}


def _categorizar_solic(solic_tipo):
    totais = {cat: 0 for cat in CATEGORIAS_SOLIC}
    totais['Administrativo'] = 0
    for r in solic_tipo:
        nome_lower = r['tipo'].lower()
        categorizado = False
        for cat, palavras in CATEGORIAS_SOLIC.items():
            if any(p in nome_lower for p in palavras):
                totais[cat] += r['total']
                categorizado = True
                break
        if not categorizado:
            totais['Administrativo'] += r['total']
    return [{'categoria': cat, 'total': total}
            for cat, total in totais.items() if total > 0]

def _nome_arquivo(prefixo: str, data_inicio, data_fim) -> str:
    """Gera nome de arquivo descritivo para exportações."""
    if data_inicio.month == data_fim.month and data_inicio.year == data_fim.year:
        return f"{prefixo}_{MESES_PT[data_inicio.month]}_{data_inicio.year}"
    else:
        return (
            f"{prefixo}"
            f"_{data_inicio.strftime('%d')}{MESES_PT[data_inicio.month][:3]}"
            f"_a_{data_fim.strftime('%d')}{MESES_PT[data_fim.month][:3]}"
            f"_{data_fim.year}"
        )

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(valor: str):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _filtros_from_request():
    data_inicio = _parse_date(request.args.get("data_inicio"))
    data_fim    = _parse_date(request.args.get("data_fim"))
    usuario_id  = request.args.get("usuario_id", type=int)

    hoje = date.today()
    if not data_inicio:
        data_inicio = hoje.replace(day=1)
    if not data_fim:
        data_fim = hoje

    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    return data_inicio, data_fim, usuario_id


def _nome_atendente(usuario_id, atendentes):
    if not usuario_id:
        return None
    for a in atendentes:
        if a["id"] == usuario_id:
            return a["nome"]
    return None


# ---------------------------------------------------------------------------
# Página principal de relatórios
# ---------------------------------------------------------------------------

_PERFIS_GESTAO = {'administrador', 'supervisor'}


@bp.route("/")
@login_required
def index():
    if current_user.perfil.nome not in _PERFIS_GESTAO:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('relatorios.desempenho_individual',
                                usuario_id=current_user.id))
    return render_template("relatorios/index.html")


# ---------------------------------------------------------------------------
# Relatório 1 – Atendimentos por período
# ---------------------------------------------------------------------------

@bp.route("/atendimentos")
@login_required
def atendimentos():
    if current_user.perfil.nome == 'atendente':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('relatorios.desempenho_individual',
                                usuario_id=current_user.id))
    data_inicio, data_fim, usuario_id = _filtros_from_request()
    atendentes = listar_atendentes()

    # Supervisor vê apenas os próprios + subordinados (atendentes)
    ids_visiveis = None
    if current_user.perfil.nome == 'supervisor':
        ids_visiveis = ids_da_equipe()
        atendentes = [a for a in atendentes if a['id'] in ids_visiveis]
        if usuario_id and usuario_id not in ids_visiveis:
            usuario_id = None

    dados  = atendimentos_por_periodo(data_inicio, data_fim, usuario_id, ids_visiveis)
    totais = totais_por_dia(data_inicio, data_fim, usuario_id, ids_visiveis)

    total = len(dados)

    pode_ver_horarios = current_user.perfil.nome == 'administrador'

    hoje = date.today()
    if hoje.month == 1:
        mes_anterior_inicio = hoje.replace(year=hoje.year - 1, month=12, day=1)
    else:
        mes_anterior_inicio = hoje.replace(month=hoje.month - 1, day=1)
    mes_anterior_fim = hoje.replace(day=1) - timedelta(days=1)

    return render_template(
        "relatorios/atendimentos.html",
        dados=dados,
        totais_dia=totais,
        atendentes=atendentes,
        filtros={
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "usuario_id": usuario_id,
            "usuario_nome": _nome_atendente(usuario_id, atendentes),
        },
        stats={
            "total": total,
        },
        pode_ver_horarios=pode_ver_horarios,
        hoje=hoje,
        mes_anterior_inicio=mes_anterior_inicio,
        mes_anterior_fim=mes_anterior_fim,
        timedelta=timedelta,
    )


@bp.route("/atendimentos/exportar/<formato>")
@login_required
def exportar_atendimentos(formato: str):
    if formato not in ("pdf", "xlsx"):
        abort(400)

    data_inicio, data_fim, usuario_id = _filtros_from_request()
    atendentes   = listar_atendentes()
    usuario_nome = _nome_atendente(usuario_id, atendentes)

    filtros = {
        "data_inicio": data_inicio,
        "data_fim":    data_fim,
        "usuario_nome": usuario_nome,
    }

    ids_visiveis = None
    if current_user.perfil.nome == 'supervisor':
        ids_visiveis = ids_da_equipe()
        if usuario_id and usuario_id not in ids_visiveis:
            usuario_id = None

    dados  = atendimentos_por_periodo(data_inicio, data_fim, usuario_id, ids_visiveis)
    totais = totais_por_dia(data_inicio, data_fim, usuario_id, ids_visiveis)
    mostrar_horarios = current_user.perfil.nome == 'administrador'

    nome_arquivo = _nome_arquivo('Atendimentos', data_inicio, data_fim)

    if formato == "pdf":
        conteudo = gerar_pdf_atendimentos(dados, filtros)
        return send_file(
            io.BytesIO(conteudo),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"{nome_arquivo}.pdf",
        )

    conteudo = gerar_excel_atendimentos(dados, totais, filtros, mostrar_horarios)
    return send_file(
        io.BytesIO(conteudo),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{nome_arquivo}.xlsx",
    )


# ---------------------------------------------------------------------------
# Relatório 2 – Desempenho por atendente
# ---------------------------------------------------------------------------

@bp.route("/desempenho")
@login_required
def desempenho():
    if current_user.perfil.nome == 'atendente':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('relatorios.desempenho_individual',
                                usuario_id=current_user.id))
    data_inicio, data_fim, usuario_id = _filtros_from_request()
    atendentes = listar_atendentes()

    dados = desempenho_por_usuario(data_inicio, data_fim, usuario_id)

    detalhes = {}
    for r in dados:
        detalhes[r["usuario_id"]] = atendimentos_por_usuario_detalhe(
            r["usuario_id"], data_inicio, data_fim
        )

    total_geral = sum(r["total"] for r in dados)

    hoje = date.today()
    if hoje.month == 1:
        mes_anterior_inicio = hoje.replace(year=hoje.year - 1, month=12, day=1)
    else:
        mes_anterior_inicio = hoje.replace(month=hoje.month - 1, day=1)
    mes_anterior_fim = hoje.replace(day=1) - timedelta(days=1)

    # ── Heatmap de evolução mensal ──────────────────────────────────────────
    from collections import defaultdict

    uid_filtro = [usuario_id] if usuario_id else None
    evolucao_raw = query_evolucao_mensal(data_inicio, data_fim, uid_filtro)

    meses_periodo = []
    cur = data_inicio.replace(day=1)
    fim_mes = data_fim.replace(day=1)
    while cur <= fim_mes:
        meses_periodo.append((cur.year, cur.month))
        cur = cur.replace(month=cur.month + 1) if cur.month < 12 \
              else cur.replace(year=cur.year + 1, month=1)

    _MESES_PT = ['','Jan','Fev','Mar','Abr','Mai','Jun',
                 'Jul','Ago','Set','Out','Nov','Dez']

    dados_dict = defaultdict(int)
    nomes_atend = {}
    for row in evolucao_raw:
        dados_dict[(row.id, int(row.ano), int(row.mes))] = row.total
        nomes_atend[row.id] = row.nome

    evolucao_mensal = []
    for uid, nome in sorted(nomes_atend.items(), key=lambda x: x[1]):
        totais = [dados_dict.get((uid, ano, mes), 0) for ano, mes in meses_periodo]
        evolucao_mensal.append({
            'nome':  nome,
            'meses': totais,
            'total': sum(totais),
        })
    evolucao_mensal.sort(key=lambda x: x['total'], reverse=True)

    labels_meses = [
        _MESES_PT[mes] + (f'/{str(ano)[2:]}' if len(meses_periodo) > 12 else '')
        for ano, mes in meses_periodo
    ]

    max_val_evolucao = max(
        (v for linha in evolucao_mensal for v in linha['meses']),
        default=1,
    ) or 1

    return render_template(
        "relatorios/desempenho.html",
        dados=dados,
        detalhes=detalhes,
        atendentes=atendentes,
        filtros={
            "data_inicio": data_inicio,
            "data_fim":    data_fim,
            "usuario_id":  usuario_id,
        },
        total_geral=total_geral,
        hoje=hoje,
        mes_anterior_inicio=mes_anterior_inicio,
        mes_anterior_fim=mes_anterior_fim,
        evolucao_mensal=evolucao_mensal,
        labels_meses=labels_meses,
        max_val_evolucao=max_val_evolucao,
    )


@bp.route("/desempenho/exportar/<formato>")
@login_required
def exportar_desempenho(formato: str):
    if formato not in ("pdf", "xlsx"):
        abort(400)

    data_inicio, data_fim, usuario_id = _filtros_from_request()

    filtros = {"data_inicio": data_inicio, "data_fim": data_fim}

    # Supervisor vê apenas os próprios + subordinados
    ids_visiveis = None
    if current_user.perfil.nome == 'supervisor':
        ids_visiveis = ids_da_equipe()
        if usuario_id and usuario_id not in ids_visiveis:
            usuario_id = None

    dados = desempenho_por_usuario(data_inicio, data_fim, usuario_id)
    if ids_visiveis is not None:
        dados = [r for r in dados if r["usuario_id"] in ids_visiveis]

    detalhes = {
        r["usuario_id"]: atendimentos_por_usuario_detalhe(
            r["usuario_id"], data_inicio, data_fim
        )
        for r in dados
    }

    nome_arquivo = _nome_arquivo('Desempenho_Atendentes', data_inicio, data_fim)

    if formato == "pdf":
        conteudo = gerar_pdf_desempenho(dados, detalhes, filtros)
        return send_file(
            io.BytesIO(conteudo),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"{nome_arquivo}.pdf",
        )

    conteudo = gerar_excel_desempenho(dados, detalhes, filtros)
    return send_file(
        io.BytesIO(conteudo),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{nome_arquivo}.xlsx",
    )


# ---------------------------------------------------------------------------
# Perfil individual de atendente
# ---------------------------------------------------------------------------

@bp.route("/desempenho/<int:usuario_id>")
@login_required
def desempenho_individual(usuario_id):
    perfis_gestao = {'administrador', 'supervisor'}
    if current_user.perfil.nome not in perfis_gestao:
        if current_user.id != usuario_id:
            flash('Você só pode visualizar seu próprio desempenho.', 'danger')
            return redirect(url_for('relatorios.desempenho_individual',
                                    usuario_id=current_user.id))
    elif current_user.perfil.nome == 'supervisor' and current_user.id != usuario_id:
        # Supervisor só pode ver a própria equipe (supervisor_id)
        if usuario_id not in ids_da_equipe():
            flash('Você não tem permissão para visualizar este perfil.', 'danger')
            return redirect(url_for('relatorios.desempenho'))

    data_inicio, data_fim, _ = _filtros_from_request()

    usuario = get_usuario_por_id(usuario_id)
    if not usuario:
        abort(404)

    atendimentos  = atendimentos_por_usuario_detalhe(usuario_id, data_inicio, data_fim)
    totais_dia    = totais_por_dia_usuario(usuario_id, data_inicio, data_fim)
    tipos         = tipos_mais_realizados(usuario_id, data_inicio, data_fim)
    total         = len(atendimentos)

    return render_template(
        "relatorios/desempenho_individual.html",
        usuario=usuario,
        atendimentos=atendimentos,
        totais_dia=totais_dia,
        tipos=tipos,
        total=total,
        filtros={
            "data_inicio": data_inicio,
            "data_fim":    data_fim,
        },
        pode_ver_todos=(current_user.perfil.nome in {'administrador', 'supervisor'}),
    )


@bp.route("/desempenho/<int:usuario_id>/exportar")
@login_required
def exportar_desempenho_individual(usuario_id):
    """Exporta o relatório individual de um atendente em PDF ou Excel."""
    perfis_gestao = {'administrador', 'supervisor'}
    if current_user.perfil.nome not in perfis_gestao:
        if current_user.id != usuario_id:
            flash('Você só pode exportar seu próprio desempenho.', 'danger')
            return redirect(url_for('relatorios.desempenho_individual',
                                    usuario_id=current_user.id))
    elif current_user.perfil.nome == 'supervisor' and current_user.id != usuario_id:
        # Supervisor só pode exportar a própria equipe (supervisor_id)
        if usuario_id not in ids_da_equipe():
            flash('Você não tem permissão para exportar este perfil.', 'danger')
            return redirect(url_for('relatorios.desempenho'))

    formato = request.args.get('formato', 'pdf')
    if formato not in ('pdf', 'xlsx'):
        abort(400)

    data_inicio, data_fim, _ = _filtros_from_request()

    usuario = get_usuario_por_id(usuario_id)
    if not usuario:
        abort(404)

    atendimentos = atendimentos_por_usuario_detalhe(usuario_id, data_inicio, data_fim)
    total        = len(atendimentos)

    filtros = {
        'data_inicio':  data_inicio,
        'data_fim':     data_fim,
        'usuario_nome': usuario['nome'],
    }

    nome_base = usuario['nome'].replace(' ', '_')[:20]
    nome_arquivo = _nome_arquivo(f"Desempenho_{nome_base}", data_inicio, data_fim)

    if formato == 'pdf':
        dados_desempenho = [{'usuario_id': usuario_id,
                             'usuario_nome': usuario['nome'],
                             'total': total}]
        detalhes = {usuario_id: atendimentos}
        conteudo = gerar_pdf_desempenho(dados_desempenho, detalhes, filtros)
        return send_file(
            io.BytesIO(conteudo),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"{nome_arquivo}.pdf",
        )

    conteudo = gerar_excel_desempenho(
        [{'usuario_id': usuario_id, 'usuario_nome': usuario['nome'], 'total': total}],
        {usuario_id: atendimentos},
        filtros,
    )
    return send_file(
        io.BytesIO(conteudo),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"{nome_arquivo}.xlsx",
    )


# ---------------------------------------------------------------------------
# Relatório Executivo
# ---------------------------------------------------------------------------

@bp.route("/executivo")
@login_required
def executivo():
    if current_user.perfil.nome != 'administrador':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('relatorios.index'))

    import datetime as dt
    data_inicio, data_fim, _ = _filtros_from_request()

    # Período anterior (mesma duração)
    delta = data_fim - data_inicio
    data_inicio_ant = data_inicio - delta - dt.timedelta(days=1)
    data_fim_ant    = data_inicio - dt.timedelta(days=1)

    # Dados do período atual
    total_atend   = total_atendimentos_periodo(data_inicio, data_fim)
    por_tipo      = atendimentos_por_tipo(data_inicio, data_fim)
    por_atendente = desempenho_por_usuario(data_inicio, data_fim)
    solic_status  = solicitacoes_por_status_periodo(data_inicio, data_fim)
    solic_tipo    = solicitacoes_por_tipo_periodo(data_inicio, data_fim)

    # Dados do período anterior (comparativo)
    total_atend_ant = total_atendimentos_periodo(data_inicio_ant, data_fim_ant)
    por_tipo_ant    = atendimentos_por_tipo(data_inicio_ant, data_fim_ant)

    # Variação percentual
    if total_atend_ant > 0:
        variacao = round((total_atend - total_atend_ant) / total_atend_ant * 100, 1)
    else:
        variacao = None

    meses_pt = {
        1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril',
        5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto',
        9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'
    }
    hoje = date.today()
    solic_categoria_lista = _categorizar_solic(solic_tipo)

    return render_template(
        "relatorios/executivo.html",
        filtros={"data_inicio": data_inicio, "data_fim": data_fim},
        total_atend=total_atend,
        total_atend_ant=total_atend_ant,
        variacao=variacao,
        por_tipo=por_tipo,
        por_tipo_ant={r['tipo']: r['total'] for r in por_tipo_ant},
        por_atendente=por_atendente,
        solic_status=solic_status,
        solic_tipo=solic_tipo,
        solic_categoria_lista=solic_categoria_lista,
        periodo_ant={"data_inicio": data_inicio_ant, "data_fim": data_fim_ant},
        meses_pt=meses_pt,
        hoje=hoje,
    )


@bp.route("/executivo/exportar/pdf")
@login_required
def exportar_executivo_pdf():
    if current_user.perfil.nome != 'administrador':
        abort(403)

    import datetime as dt

    data_inicio, data_fim, _ = _filtros_from_request()
    delta = data_fim - data_inicio
    data_inicio_ant = data_inicio - delta - dt.timedelta(days=1)
    data_fim_ant    = data_inicio - dt.timedelta(days=1)

    total_atend     = total_atendimentos_periodo(data_inicio, data_fim)
    total_atend_ant = total_atendimentos_periodo(data_inicio_ant, data_fim_ant)
    por_tipo        = atendimentos_por_tipo(data_inicio, data_fim)
    por_tipo_ant    = {r['tipo']: r['total'] for r in atendimentos_por_tipo(data_inicio_ant, data_fim_ant)}
    por_atendente   = desempenho_por_usuario(data_inicio, data_fim)
    solic_status    = solicitacoes_por_status_periodo(data_inicio, data_fim)
    solic_tipo      = solicitacoes_por_tipo_periodo(data_inicio, data_fim)

    variacao = round((total_atend - total_atend_ant) / total_atend_ant * 100, 1) if total_atend_ant > 0 else None

    conteudo = gerar_pdf_executivo(
        filtros={"data_inicio": data_inicio, "data_fim": data_fim},
        total_atend=total_atend,
        total_atend_ant=total_atend_ant,
        variacao=variacao,
        por_tipo=por_tipo,
        por_tipo_ant=por_tipo_ant,
        por_atendente=por_atendente,
        solic_status=solic_status,
        solic_tipo=solic_tipo,
    )

    nome = f"{_nome_arquivo('Relatorio_Executivo', data_inicio, data_fim)}.pdf"
    return send_file(
        io.BytesIO(conteudo),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=nome,
    )


@bp.route("/executivo/exportar/xlsx")
@login_required
def exportar_executivo_xlsx():
    if current_user.perfil.nome != 'administrador':
        abort(403)

    import datetime as dt

    data_inicio, data_fim, _ = _filtros_from_request()
    delta = data_fim - data_inicio
    data_inicio_ant = data_inicio - delta - dt.timedelta(days=1)
    data_fim_ant    = data_inicio - dt.timedelta(days=1)

    total_atend     = total_atendimentos_periodo(data_inicio, data_fim)
    total_atend_ant = total_atendimentos_periodo(data_inicio_ant, data_fim_ant)
    por_tipo        = atendimentos_por_tipo(data_inicio, data_fim)
    por_tipo_ant    = {r['tipo']: r['total'] for r in atendimentos_por_tipo(data_inicio_ant, data_fim_ant)}
    por_atendente   = desempenho_por_usuario(data_inicio, data_fim)
    solic_status    = solicitacoes_por_status_periodo(data_inicio, data_fim)
    solic_tipo      = solicitacoes_por_tipo_periodo(data_inicio, data_fim)

    variacao = round((total_atend - total_atend_ant) / total_atend_ant * 100, 1) if total_atend_ant > 0 else None

    conteudo = gerar_excel_executivo(
        filtros={"data_inicio": data_inicio, "data_fim": data_fim},
        total_atend=total_atend,
        total_atend_ant=total_atend_ant,
        variacao=variacao,
        por_tipo=por_tipo,
        por_tipo_ant=por_tipo_ant,
        por_atendente=por_atendente,
        solic_status=solic_status,
        solic_tipo=solic_tipo,
    )

    nome = f"{_nome_arquivo('Relatorio_Executivo', data_inicio, data_fim)}.xlsx"
    return send_file(
        io.BytesIO(conteudo),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nome,
    )
