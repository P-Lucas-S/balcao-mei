from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .. import db
from ..models import SolicitacaoExclusao, Pessoa, Atendimento, Solicitacao, Usuario

pendencias_bp = Blueprint('pendencias', __name__, url_prefix='/pendencias')


def _requer_admin():
    return current_user.perfil.nome == 'administrador'


@pendencias_bp.route('/')
@login_required
def index():
    if not _requer_admin():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    filtro_status      = request.args.get('status',      'pendente').strip()
    filtro_solicitante = request.args.get('solicitante', '').strip()

    query_base = SolicitacaoExclusao.query
    if filtro_status == 'resolvidas':
        query_base = query_base.filter(SolicitacaoExclusao.status.in_(['executada', 'negada']))
    else:
        query_base = query_base.filter_by(status='pendente')

    if filtro_solicitante:
        query_base = query_base.filter(
            SolicitacaoExclusao.id_usuario_solicitante == int(filtro_solicitante)
        )

    if filtro_status == 'resolvidas':
        pendentes = query_base.order_by(SolicitacaoExclusao.created_at.desc()).all()
    else:
        pendentes = query_base.order_by(SolicitacaoExclusao.created_at.asc()).all()

    impacto = {}
    for p in pendentes:
        if p.entidade == 'cadastro':
            qtd_atend = Atendimento.query.filter_by(id_pessoa=p.entidade_id).count()
            qtd_solic = Solicitacao.query.filter_by(id_pessoa=p.entidade_id).count()
            impacto[p.id] = {'atend': qtd_atend, 'solic': qtd_solic}

    ids_existentes = set()
    for p in pendentes:
        if p.entidade == 'cadastro':
            if db.session.get(Pessoa, p.entidade_id):
                ids_existentes.add(p.id)
        elif p.entidade == 'atendimento':
            if db.session.get(Atendimento, p.entidade_id):
                ids_existentes.add(p.id)
        elif p.entidade == 'solicitacao':
            if db.session.get(Solicitacao, p.entidade_id):
                ids_existentes.add(p.id)

    usuarios_filtro = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()

    return render_template('pendencias/index.html',
                           pendentes=pendentes,
                           impacto=impacto,
                           ids_existentes=ids_existentes,
                           filtro_status=filtro_status,
                           filtro_solicitante=filtro_solicitante,
                           usuarios_filtro=usuarios_filtro)


@pendencias_bp.route('/solicitar', methods=['POST'])
@login_required
def solicitar():
    entidade    = request.form.get('entidade')
    entidade_id = request.form.get('entidade_id', type=int)
    motivo      = request.form.get('motivo', '').strip() or None

    if entidade == 'cadastro':
        obj = db.get_or_404(Pessoa, entidade_id)
        desc = obj.nome_razao_social
        obj.exclusao_pendente = True
    elif entidade == 'atendimento':
        obj = db.get_or_404(Atendimento, entidade_id)
        desc = f'{obj.pessoa.nome_razao_social} em {obj.data_atendimento.strftime("%d/%m/%Y")}'
        obj.exclusao_pendente = True
    elif entidade == 'solicitacao':
        obj = db.get_or_404(Solicitacao, entidade_id)
        desc = f'#{obj.id} — {obj.pessoa.nome_razao_social} ({obj.tipo_solicitacao.descricao})'
        obj.exclusao_pendente = True
    else:
        flash('Entidade inválida.', 'danger')
        return redirect(url_for('main.dashboard'))

    sol = SolicitacaoExclusao(
        entidade=entidade,
        entidade_id=entidade_id,
        entidade_desc=desc,
        id_usuario_solicitante=current_user.id,
        motivo=motivo,
        status='pendente',
    )
    db.session.add(sol)
    db.session.commit()
    flash('Solicitação de exclusão enviada para análise. O registro será removido após aprovação da administração.', 'info')

    if entidade == 'cadastro':
        return redirect(url_for('pessoas.index'))
    elif entidade == 'atendimento':
        return redirect(url_for('atendimentos.index'))
    else:
        return redirect(url_for('solicitacoes.index'))


@pendencias_bp.route('/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar(id):
    if not _requer_admin():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    sol = db.get_or_404(SolicitacaoExclusao, id)

    if sol.entidade == 'cadastro':
        obj = db.session.get(Pessoa, sol.entidade_id)
        if obj:
            # Exclusão lógica — mesma lógica de pessoas.remover.
            # Antes do ciclo 11 aqui havia um db.session.delete(obj), que
            # levantava IntegrityError sempre que o cadastro tinha histórico.
            from .pessoas import remover_cadastro
            remover_cadastro(obj)

    elif sol.entidade == 'atendimento':
        obj = db.session.get(Atendimento, sol.entidade_id)
        if obj:
            from .pessoas import _registrar_log
            _registrar_log(
                acao='exclusao', entidade='atendimento', entidade_id=obj.id,
                descricao=f'Atendimento removido: {obj.pessoa.nome_razao_social} em {obj.data_atendimento.strftime("%d/%m/%Y")} (id={obj.id})'
            )
            db.session.delete(obj)

    elif sol.entidade == 'solicitacao':
        obj = db.session.get(Solicitacao, sol.entidade_id)
        if obj:
            from .pessoas import _registrar_log
            _registrar_log(
                acao='exclusao', entidade='solicitacao', entidade_id=obj.id,
                descricao=f'Solicitação removida: #{obj.id} — {obj.pessoa.nome_razao_social} ({obj.tipo_solicitacao.descricao})'
            )
            db.session.delete(obj)

    sol.status = 'executada'
    db.session.commit()
    flash(f'Exclusão de {sol.entidade_desc} executada com sucesso.', 'success')
    return redirect(url_for('pendencias.index'))


@pendencias_bp.route('/<int:id>/negar', methods=['POST'])
@login_required
def negar(id):
    if not _requer_admin():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    sol = db.get_or_404(SolicitacaoExclusao, id)

    if sol.entidade == 'cadastro':
        obj = db.session.get(Pessoa, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = False
    elif sol.entidade == 'atendimento':
        obj = db.session.get(Atendimento, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = False
    elif sol.entidade == 'solicitacao':
        obj = db.session.get(Solicitacao, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = False

    motivo_negacao = request.form.get('motivo_negacao', '').strip()
    sol.motivo_negacao = motivo_negacao or None
    sol.status = 'negada'
    db.session.commit()
    return redirect(url_for('pendencias.index'))


@pendencias_bp.route('/<int:id>/reabrir', methods=['POST'])
@login_required
def reabrir(id):
    if not _requer_admin():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))

    sol = db.get_or_404(SolicitacaoExclusao, id)

    if sol.status != 'negada':
        flash('Apenas solicitações negadas podem ser reabertas.', 'danger')
        return redirect(url_for('pendencias.index', status='resolvidas'))

    if sol.entidade == 'cadastro':
        obj = db.session.get(Pessoa, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = True
    elif sol.entidade == 'atendimento':
        obj = db.session.get(Atendimento, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = True
    elif sol.entidade == 'solicitacao':
        obj = db.session.get(Solicitacao, sol.entidade_id)
        if obj:
            obj.exclusao_pendente = True

    sol.status = 'pendente'
    sol.motivo_negacao = None
    db.session.commit()
    flash(f'Solicitação de exclusão de "{sol.entidade_desc}" reaberta.', 'success')
    return redirect(url_for('pendencias.index'))
