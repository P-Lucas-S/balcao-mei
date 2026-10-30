from app import marca
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from .. import db
from ..escopo import filtrar_por_escopo, no_escopo
from .atendimentos import canal_padrao_id
from ..models import (Solicitacao, Pessoa, Usuario, Status,
                      TipoSolicitacao, Evento, Atividade, Atendimento,
                      Servico, AtendimentoServico)

solicitacoes_bp = Blueprint('solicitacoes', __name__, url_prefix='/solicitacoes')

POR_PAGINA = 20

_PERFIS_REMOVER = {'administrador'}


_WORKFLOW_STATUS = {'pendente', 'em análise', 'aprovado', 'recusado'}


def _status_workflow():
    """Retorna apenas os status do workflow ativo, excluindo legados (Aberta, Em andamento, etc.)."""
    return [
        s for s in Status.query.order_by(Status.id).all()
        if s.descricao.lower() in _WORKFLOW_STATUS
    ]


def _get_form_data():
    pessoas   = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()
    usuarios  = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    status    = _status_workflow()
    tipos     = TipoSolicitacao.query.filter_by(ativo=True).order_by(TipoSolicitacao.descricao).all()
    eventos   = Evento.query.order_by(Evento.descricao).all()
    atividades = Atividade.query.order_by(Atividade.descricao).all()
    return pessoas, usuarios, status, tipos, eventos, atividades


def _valida_form(form):
    erros = []
    if not form.get('id_pessoa'):
        erros.append('Selecione uma pessoa.')
    if not form.get('id_tipo_solicitacao'):
        erros.append('Selecione o tipo de solicitação.')
    if not form.get('id_status'):
        erros.append('Selecione o status.')
    if not form.get('id_usuario'):
        erros.append('Selecione o usuário responsável.')
    if not form.get('data_solicitacao'):
        erros.append('Data é obrigatória.')
    return erros


def _salva_solicitacao(sol, form):
    sol.data_solicitacao    = date.fromisoformat(form['data_solicitacao'])
    sol.id_pessoa           = int(form['id_pessoa'])
    sol.id_tipo_solicitacao = int(form['id_tipo_solicitacao'])
    sol.id_status           = int(form['id_status'])
    sol.id_usuario          = int(form['id_usuario'])
    sol.descricao           = form.get('descricao',  '').strip() or None
    sol.observacao          = form.get('observacao', '').strip() or None
    sol.id_evento    = int(form['id_evento'])   if form.get('id_evento')   else None
    sol.id_atividade = int(form['id_atividade']) if form.get('id_atividade') else None


# ── Lista ──────────────────────────────────────────────────────────────────────
@solicitacoes_bp.route('/')
@login_required
def index():
    f_status  = request.args.get('status',   '').strip()
    f_tipo    = request.args.get('tipo',     '').strip()
    f_de      = request.args.get('data_de',  '').strip()
    f_ate     = request.args.get('data_ate', '').strip()
    f_usuario = request.args.get('usuario',  '').strip()

    from sqlalchemy.orm import joinedload as _jl2
    query = Solicitacao.query.join(Solicitacao.status).join(Solicitacao.tipo_solicitacao)
    query = query.options(
        _jl2(Solicitacao.pessoa),
        _jl2(Solicitacao.usuario),
        _jl2(Solicitacao.status),
        _jl2(Solicitacao.tipo_solicitacao),
    )

    if f_status:
        query = query.filter(Solicitacao.id_status == int(f_status))
    if f_tipo:
        query = query.filter(Solicitacao.id_tipo_solicitacao == int(f_tipo))
    if f_de:
        try:
            query = query.filter(Solicitacao.data_solicitacao >= date.fromisoformat(f_de))
        except ValueError:
            pass
    if f_ate:
        try:
            query = query.filter(Solicitacao.data_solicitacao <= date.fromisoformat(f_ate))
        except ValueError:
            pass
    if f_usuario:
        query = query.filter(Solicitacao.id_usuario == int(f_usuario))

    # Escopo por perfil — regra única em app/escopo.py
    query = filtrar_por_escopo(query, Solicitacao.id_usuario)

    if current_user.perfil.nome != 'administrador':
        query = query.filter(Solicitacao.exclusao_pendente == False)

    page = request.args.get('page', 1, type=int)
    paginacao = (
        query
        .order_by(Solicitacao.id_status.asc(),
                  Solicitacao.data_solicitacao.asc())
        .paginate(page=page, per_page=POR_PAGINA, error_out=False)
    )

    todos_status = _status_workflow()
    todos_tipos  = TipoSolicitacao.query.order_by(TipoSolicitacao.descricao).all()

    # Contagem por status em uma única query GROUP BY
    q_count = db.session.query(
        Solicitacao.id_status,
        func.count(Solicitacao.id).label('total'),
    )
    # Mesmo escopo da listagem: a contagem por status tem de bater com ela
    q_count = filtrar_por_escopo(q_count, Solicitacao.id_usuario)
    contagem_status = {s.id: 0 for s in todos_status}
    for row in q_count.group_by(Solicitacao.id_status).all():
        contagem_status[row.id_status] = row.total

    return render_template('solicitacoes/lista.html',
                           solicitacoes=paginacao.items, paginacao=paginacao,
                           todos_status=todos_status, todos_tipos=todos_tipos,
                           f_status=f_status, f_tipo=f_tipo,
                           f_de=f_de, f_ate=f_ate, f_usuario=f_usuario,
                           contagem_status=contagem_status,
                           hoje=date.today())


# ── Exportar Excel ─────────────────────────────────────────────────────────────
@solicitacoes_bp.route('/exportar/xlsx')
@login_required
def exportar_xlsx():
    import io
    from datetime import datetime
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    f_status = request.args.get('status', '').strip()
    f_tipo   = request.args.get('tipo',   '').strip()
    f_de     = request.args.get('data_de',  '').strip()
    f_ate    = request.args.get('data_ate', '').strip()

    query = Solicitacao.query.join(Solicitacao.status).join(Solicitacao.tipo_solicitacao)

    if f_status:
        query = query.filter(Solicitacao.id_status == int(f_status))
    if f_tipo:
        query = query.filter(Solicitacao.id_tipo_solicitacao == int(f_tipo))
    if f_de:
        try:
            query = query.filter(Solicitacao.data_solicitacao >= date.fromisoformat(f_de))
        except ValueError:
            pass
    if f_ate:
        try:
            query = query.filter(Solicitacao.data_solicitacao <= date.fromisoformat(f_ate))
        except ValueError:
            pass

    solicitacoes = query.order_by(Solicitacao.data_solicitacao.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Solicitações"
    ws.sheet_view.showGridLines = False

    fill_cab   = PatternFill("solid", fgColor="0f4c5c")
    fill_par   = PatternFill("solid", fgColor="F1F5F9")
    fill_impar = PatternFill("solid", fgColor="FFFFFF")
    borda_cab  = Border(
        left=Side(style="medium", color="0f4c5c"),
        right=Side(style="medium", color="0f4c5c"),
        top=Side(style="medium", color="0f4c5c"),
        bottom=Side(style="medium", color="0f4c5c"),
    )
    borda_dado = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    num_cols = 7
    status_label = ''
    if f_status:
        s_obj = db.session.get(Status, int(f_status))
        if s_obj:
            status_label = f' · Status: {s_obj.descricao}'
    periodo_label = f' · Período: {f_de} a {f_ate}' if (f_de or f_ate) else ''

    for row, (valor, fonte) in enumerate([
        (f"{marca.ORG_COMPLETO} — Solicitações",
         Font(bold=True, size=13, color="0f4c5c")),
        (f"Total: {len(solicitacoes)} registro(s){status_label}{periodo_label}",
         Font(size=9, color="64748B", italic=True)),
        (f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
         Font(size=8, color="94A3B8", italic=True)),
    ], start=1):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_cols)
        c = ws.cell(row=row, column=1, value=valor)
        c.font = fonte
        c.alignment = Alignment(horizontal="center")

    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 16
    ws.row_dimensions[3].height = 14

    colunas = ["Data", "Pessoa", "CPF / CNPJ", "Tipo", "Status", "Responsável", "Descrição"]
    for col_idx, nome in enumerate(colunas, start=1):
        c = ws.cell(row=5, column=col_idx, value=nome)
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = fill_cab
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = borda_cab
    ws.row_dimensions[5].height = 18

    for i, s in enumerate(solicitacoes, start=6):
        fill = fill_par if i % 2 == 0 else fill_impar
        doc = s.pessoa.cnpj or s.pessoa.cpf or '—'
        valores = [
            s.data_solicitacao.strftime('%d/%m/%Y'),
            s.pessoa.nome_razao_social,
            doc,
            s.tipo_solicitacao.descricao,
            s.status.descricao,
            s.usuario.nome,
            s.descricao or '—',
        ]
        for col_idx, val in enumerate(valores, start=1):
            c = ws.cell(row=i, column=col_idx, value=val)
            c.fill = fill
            c.border = borda_dado
            c.font = Font(size=9)
            c.alignment = Alignment(vertical="center", wrap_text=(col_idx == 7))

    larguras = [12, 36, 20, 28, 16, 20, 50]
    for col_idx, larg in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = larg
    ws.freeze_panes = "A6"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from app.routes.relatorios.routes import _nome_arquivo
    if f_de and f_ate:
        try:
            di = date.fromisoformat(f_de)
            df = date.fromisoformat(f_ate)
            nome = f"{_nome_arquivo('Solicitacoes', di, df)}.xlsx"
        except ValueError:
            nome = f"Solicitacoes_{datetime.now().strftime('%Y%m%d')}.xlsx"
    else:
        nome = f"Solicitacoes_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return send_file(buf,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=nome)


# ── Nova ───────────────────────────────────────────────────────────────────────
@solicitacoes_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    # Solicitação só nasce dentro de um atendimento existente
    if request.method == 'POST':
        atend_id = request.form.get('atendimento_id', type=int)
        if not atend_id:
            flash('Selecione um atendimento para criar uma solicitação.', 'warning')
            return redirect(url_for('atendimentos.index'))

        atend = db.session.get(Atendimento, atend_id)
        if not atend:
            abort(404)

        pessoas, usuarios, status, tipos, eventos, atividades = _get_form_data()
        erros = _valida_form(request.form)
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('solicitacoes/form.html',
                                   titulo='Nova Solicitação', acao='nova',
                                   atendimento=atend,
                                   pessoas=pessoas, usuarios=usuarios, status=status,
                                   tipos=tipos, eventos=eventos, atividades=atividades,
                                   form=request.form)

        sol = Solicitacao(atendimento_id=atend_id)
        _salva_solicitacao(sol, request.form)
        db.session.add(sol)
        db.session.commit()
        flash('Solicitação registrada com sucesso.', 'success')
        return redirect(url_for('solicitacoes.detalhe', id=sol.id))

    # GET — exige atendimento_id como parâmetro obrigatório
    atend_id = request.args.get('atendimento_id', type=int)
    if not atend_id:
        flash('Selecione um atendimento para criar uma solicitação.', 'warning')
        return redirect(url_for('atendimentos.index'))

    atend = db.session.get(Atendimento, atend_id)
    if not atend:
        abort(404)

    pessoas, usuarios, status, tipos, eventos, atividades = _get_form_data()
    status_pendente = Status.query.filter(Status.descricao.ilike('pendente')).first()

    form_default = {
        'data_solicitacao': date.today().isoformat(),
        'id_usuario':       str(atend.id_usuario),
        'id_status':        str(status_pendente.id) if status_pendente else '',
        'id_pessoa':        str(atend.id_pessoa),
        'atendimento_id':   str(atend_id),
    }
    return render_template('solicitacoes/form.html',
                           titulo='Nova Solicitação', acao='nova',
                           atendimento=atend,
                           pessoas=pessoas, usuarios=usuarios, status=status,
                           tipos=tipos, eventos=eventos, atividades=atividades,
                           form=form_default)


# ── Detalhe ────────────────────────────────────────────────────────────────────
@solicitacoes_bp.route('/<int:id>')
@login_required
def detalhe(id):
    from ..models import LogAcao
    sol = db.get_or_404(Solicitacao, id)
    # Ler respeita o mesmo escopo que editar — ver atendimentos.detalhe.
    if not _no_escopo(sol):
        flash('Você não tem permissão para ver esta solicitação.', 'danger')
        return redirect(url_for('solicitacoes.index'))
    historico_status = (
        LogAcao.query
        .filter_by(acao='status', entidade='solicitacao', entidade_id=id)
        .order_by(LogAcao.created_at.asc())
        .all()
    )
    todos_status = _status_workflow()
    return render_template('solicitacoes/detalhe.html',
                           sol=sol, historico_status=historico_status,
                           todos_status=todos_status)


# ── Editar ─────────────────────────────────────────────────────────────────────
def _no_escopo(sol):
    """Escopo registro a registro — a mesma regra da listagem.

    Desde 2026-08-29 vale para LER também, não só editar: `detalhe` passou a
    usá-la. Ver `app/escopo.py`.
    """
    return no_escopo(sol)


@solicitacoes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    sol = db.get_or_404(Solicitacao, id)

    if not _no_escopo(sol):
        flash('Você não tem permissão para editar esta solicitação.', 'danger')
        return redirect(url_for('solicitacoes.index'))

    pessoas, usuarios, status, tipos, eventos, atividades = _get_form_data()

    if request.method == 'POST':
        erros = _valida_form(request.form)
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('solicitacoes/form.html',
                                   titulo='Editar Solicitação', acao='editar',
                                   sol=sol, pessoas=pessoas, usuarios=usuarios,
                                   status=status, tipos=tipos, eventos=eventos,
                                   atividades=atividades, form=request.form)

        _salva_solicitacao(sol, request.form)
        db.session.commit()
        flash('Solicitação atualizada com sucesso.', 'success')
        return redirect(url_for('solicitacoes.detalhe', id=sol.id))

    form = {
        'data_solicitacao':    sol.data_solicitacao.isoformat(),
        'id_pessoa':           str(sol.id_pessoa),
        'id_tipo_solicitacao': str(sol.id_tipo_solicitacao),
        'id_status':           str(sol.id_status),
        'id_usuario':          str(sol.id_usuario),
        'descricao':           sol.descricao  or '',
        'observacao':          sol.observacao or '',
        'id_evento':           str(sol.id_evento)    if sol.id_evento    else '',
        'id_atividade':        str(sol.id_atividade) if sol.id_atividade else '',
    }
    return render_template('solicitacoes/form.html',
                           titulo='Editar Solicitação', acao='editar',
                           sol=sol, pessoas=pessoas, usuarios=usuarios,
                           status=status, tipos=tipos, eventos=eventos,
                           atividades=atividades, form=form)


# ── Troca rápida de status (JSON) ─────────────────────────────────────────────
@solicitacoes_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def trocar_status(id):
    sol = db.get_or_404(Solicitacao, id)
    novo_id = request.form.get('id_status', type=int)
    if not novo_id:
        return jsonify({'ok': False, 'erro': 'Status inválido.'}), 400

    status = db.get_or_404(Status, novo_id)
    desc_lower = status.descricao.lower()

    # Atendente não pode aprovar nem recusar — apenas Pendente e Em Análise
    if current_user.perfil.nome == 'atendente' and (
        'aprovad' in desc_lower or 'recus' in desc_lower
    ):
        return jsonify({
            'ok': False,
            'erro': 'Atendentes não podem aprovar ou recusar solicitações.',
        }), 403

    # Recusa exige motivo
    motivo_recusa = request.form.get('motivo_recusa', '').strip()
    if 'recus' in desc_lower and not motivo_recusa:
        return jsonify({'ok': False, 'erro': 'Informe o motivo da recusa.'}), 400

    status_anterior = db.session.get(Status, sol.id_status)
    descricao_log = (
        f'Status alterado: #{sol.id} — {sol.pessoa.nome_razao_social} '
        f'({status_anterior.descricao if status_anterior else "?"} → {status.descricao})'
    )
    if motivo_recusa:
        descricao_log += f' — Motivo: {motivo_recusa}'

    from .pessoas import _registrar_log
    _registrar_log(
        acao='status',
        entidade='solicitacao',
        entidade_id=id,
        descricao=descricao_log,
    )
    sol.id_status = novo_id
    db.session.commit()
    return jsonify({'ok': True, 'novo_status': status.descricao})


# ── Remover ────────────────────────────────────────────────────────────────────
@solicitacoes_bp.route('/<int:id>/remover', methods=['POST'])
@login_required
def remover(id):
    if current_user.perfil.nome not in _PERFIS_REMOVER:
        flash('Você não tem permissão para excluir solicitações. '
              'Solicite a exclusão para análise da administração.', 'danger')
        return redirect(url_for('solicitacoes.index'))

    sol = db.get_or_404(Solicitacao, id)
    info = f'#{sol.id} — {sol.pessoa.nome_razao_social}'
    from .pessoas import _registrar_log
    _registrar_log(
        acao='exclusao',
        entidade='solicitacao',
        entidade_id=id,
        descricao=f'Solicitação removida: #{sol.id} — {sol.pessoa.nome_razao_social} ({sol.tipo_solicitacao.descricao})',
    )
    db.session.delete(sol)
    db.session.commit()
    flash(f'Solicitação {info} removida com sucesso.', 'success')
    return redirect(url_for('solicitacoes.index'))


# ── Nova Solicitação Rápida (cria Atendimento + Solicitação em uma transação) ──
@solicitacoes_bp.route('/nova-rapida', methods=['GET', 'POST'])
@login_required
def nova_rapida():
    """Cria um Atendimento automaticamente e vincula à nova Solicitação."""
    from datetime import datetime as dt

    pessoas    = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()
    tipos      = TipoSolicitacao.query.filter_by(ativo=True).order_by(TipoSolicitacao.descricao).all()
    eventos    = Evento.query.order_by(Evento.descricao).all()
    atividades = Atividade.query.order_by(Atividade.descricao).all()

    def _render(form_data):
        return render_template('solicitacoes/nova_rapida.html',
                               pessoas=pessoas, tipos=tipos,
                               eventos=eventos, atividades=atividades,
                               form=form_data)

    if request.method == 'POST':
        id_pessoa    = request.form.get('id_pessoa', type=int)
        id_tipo_sol  = request.form.get('id_tipo_solicitacao', type=int)
        id_evento    = request.form.get('id_evento', type=int)
        id_atividade = request.form.get('id_atividade', type=int)
        descricao    = request.form.get('descricao', '').strip() or None

        erros = []
        if not id_pessoa:
            erros.append('Selecione uma pessoa.')
        if not id_tipo_sol:
            erros.append('Selecione o tipo de solicitação.')
        if erros:
            for e in erros:
                flash(e, 'danger')
            return _render(request.form)

        try:
            # O serviço 'Solicitação' é semeado pela migration 013. Antes do
            # ciclo canal×serviço este bloco criava 'Solicitação Formal' na
            # tabela de tipos, que na prática era o catálogo de CANAIS.
            servico_solic = Servico.query.filter(
                Servico.descricao.ilike('solicita%')
            ).first()
            if not servico_solic:
                servico_solic = Servico(descricao='Solicitação', ativo=True,
                                        protegido=True)
                db.session.add(servico_solic)
                db.session.flush()

            now = dt.now()

            atend = Atendimento(
                data_atendimento  = now.date(),
                hora_atendimento  = now.time(),
                id_pessoa         = id_pessoa,
                id_canal          = canal_padrao_id(),
                id_usuario        = current_user.id,
                observacao        = 'Gerado automaticamente — Solicitação Formal',
                exclusao_pendente = False,
            )
            db.session.add(atend)
            db.session.flush()

            db.session.add(AtendimentoServico(
                id_atendimento      = atend.id,
                id_servico = servico_solic.id,
            ))

            status_pend = Status.query.filter(Status.descricao.ilike('pendente')).first()
            sol = Solicitacao(
                data_solicitacao    = now.date(),
                id_pessoa           = id_pessoa,
                id_usuario          = current_user.id,
                id_tipo_solicitacao = id_tipo_sol,
                id_status           = status_pend.id,
                atendimento_id      = atend.id,
                descricao           = descricao,
                id_evento           = id_evento,
                id_atividade        = id_atividade,
                exclusao_pendente   = False,
            )
            db.session.add(sol)
            db.session.flush()

            from .pessoas import _registrar_log
            _registrar_log(
                acao='criacao', entidade='atendimento', entidade_id=atend.id,
                descricao=(f'Atendimento #{atend.id} gerado automaticamente '
                           f'via Solicitação Rápida — pessoa: {sol.pessoa.nome_razao_social}'),
            )
            _registrar_log(
                acao='criacao', entidade='solicitacao', entidade_id=sol.id,
                descricao=(f'Solicitação #{sol.id} criada via fluxo rápido '
                           f'(atendimento #{atend.id} gerado automaticamente)'),
            )
            db.session.commit()
            flash(
                f'Solicitação criada com sucesso. '
                f'Atendimento #{atend.id} gerado automaticamente.',
                'success',
            )
            return redirect(url_for('solicitacoes.detalhe', id=sol.id))

        except Exception:
            db.session.rollback()
            flash('Erro ao criar a solicitação. Tente novamente.', 'danger')
            return _render(request.form)

    return _render({})


# ── Pendentes por pessoa (AJAX — usado em form.html) ──────────────────────────
@solicitacoes_bp.route('/pendentes-pessoa/<int:id_pessoa>')
@login_required
def pendentes_pessoa(id_pessoa):
    ids_abertos = [s.id for s in Status.query.filter(
        db.or_(
            Status.descricao.ilike('%pendente%'),
            Status.descricao.ilike('%análise%'),
        )
    ).all()]
    sols = Solicitacao.query.filter(
        Solicitacao.id_pessoa == id_pessoa,
        Solicitacao.id_status.in_(ids_abertos)
    ).order_by(Solicitacao.data_solicitacao.desc()).all() if ids_abertos else []

    mais_recente = None
    if sols:
        s = sols[0]
        mais_recente = (
            f'{s.tipo_solicitacao.descricao} '
            f'criada em {s.data_solicitacao.strftime("%d/%m/%Y")}'
        )
    return jsonify({'total': len(sols), 'mais_recente': mais_recente})
