from datetime import date
from difflib import SequenceMatcher
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from .. import db
from ..models import (Servico, CanalAtendimento, TipoSolicitacao,
                      Evento, Atividade, AtendimentoServico, Solicitacao, LogAcao,
                      ParametroMunicipio, TagInteresse)

tabelas_bp = Blueprint('tabelas', __name__, url_prefix='/tabelas')

_PERFIS = {'administrador'}


def _checar_acesso():
    if not current_user.is_authenticated or current_user.perfil.nome not in _PERFIS:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.dashboard'))
    return None


def _log_tabela(acao, entidade, entidade_id, descricao):
    log = LogAcao(
        id_usuario=current_user.id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        descricao=descricao,
    )
    db.session.add(log)


def _em_uso_servico(item_id):
    return AtendimentoServico.query.filter_by(id_servico=item_id).count()


def _em_uso_canal(item_id):
    from ..models import Atendimento
    return Atendimento.query.filter_by(id_canal=item_id).count()


def _em_uso_tipo_solicitacao(item_id):
    return Solicitacao.query.filter_by(id_tipo_solicitacao=item_id).count()


def _em_uso_evento(item_id):
    return Solicitacao.query.filter_by(id_evento=item_id).count()


def _em_uso_atividade(item_id):
    return Solicitacao.query.filter_by(id_atividade=item_id).count()


def _em_uso_tag(item_id):
    tag = db.session.get(TagInteresse, item_id)
    return tag.pessoas.count() if tag else 0


_TABELAS = {
    'canal': {
        'model':     CanalAtendimento,
        'titulo':    'Canais de Atendimento',
        'campos':    ['descricao'],
        'labels':    ['Descrição'],
        'tem_datas': False,
        'check_uso': _em_uso_canal,
        'tem_ativo': True,
    },
    'servico': {
        'model':     Servico,
        'titulo':    'Serviços',
        'campos':    ['descricao'],
        'labels':    ['Descrição'],
        'tem_datas': False,
        'check_uso': _em_uso_servico,
        'tem_ativo': True,
    },
    'tipo-solicitacao': {
        'model':     TipoSolicitacao,
        'titulo':    'Tipos de Solicitação',
        'campos':    ['descricao'],
        'labels':    ['Descrição'],
        'tem_datas': False,
        'check_uso': _em_uso_tipo_solicitacao,
        'tem_ativo': True,
    },
    'evento': {
        'model':     Evento,
        'titulo':    'Eventos',
        'campos':    ['descricao', 'data_inicio', 'data_fim'],
        'labels':    ['Descrição', 'Data Início', 'Data Fim'],
        'tem_datas': True,
        'check_uso': _em_uso_evento,
        'tem_ativo': False,
    },
    'atividade': {
        'model':     Atividade,
        'titulo':    'Atividades',
        'campos':    ['descricao'],
        'labels':    ['Descrição'],
        'tem_datas': False,
        'check_uso': _em_uso_atividade,
        'tem_ativo': False,
    },
    'tag-interesse': {
        'model':     TagInteresse,
        'titulo':    'Tags de Interesse',
        'campos':    ['descricao'],
        'labels':    ['Descrição'],
        'tem_datas': False,
        'check_uso': _em_uso_tag,
        'tem_ativo': True,
    },
}


def _get_cfg(chave):
    return _TABELAS.get(chave)


def _salvar_item(item, cfg, form, chave=None):
    for campo in cfg['campos']:
        valor = form.get(campo, '').strip()
        if campo in ('data_inicio', 'data_fim'):
            setattr(item, campo, date.fromisoformat(valor) if valor else None)
        else:
            setattr(item, campo, valor or None)

    if chave == 'servico':
        item.link_portal = form.get('link_portal', '').strip() or None
        item.instrucao   = form.get('instrucao', '').strip() or None
    elif chave == 'tipo-solicitacao':
        val_val = form.get('validade', '').strip()
        item.validade = date.fromisoformat(val_val) if val_val else None


def _similar_existe(model, descricao, excluir_id=None):
    """Retorna item similar (ratio >= 0.65) ou None."""
    todos = model.query.all()
    for item in todos:
        if excluir_id and item.id == excluir_id:
            continue
        ratio = SequenceMatcher(None, descricao.lower(), item.descricao.lower()).ratio()
        if ratio >= 0.65:
            return item
    return None


# ── Novo Rápido (AJAX/JSON) ────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/novo-rapido', methods=['POST'])
@login_required
def novo_rapido(chave):
    bloqueio = _checar_acesso()
    if bloqueio:
        return jsonify({'ok': False, 'erro': 'Acesso restrito.'}), 403

    cfg = _get_cfg(chave)
    if cfg is None:
        return jsonify({'ok': False, 'erro': 'Tabela inválida.'}), 400

    body = request.get_json(silent=True, force=True) or {}
    descricao = (body.get('descricao') or '').strip()
    if not descricao:
        return jsonify({'ok': False, 'erro': 'Descrição obrigatória.'}), 422

    existente = cfg['model'].query.filter(
        db.func.lower(cfg['model'].descricao) == descricao.lower()
    ).first()
    if existente:
        return jsonify({'ok': True, 'id': existente.id,
                        'descricao': existente.descricao, 'duplicata': True})

    item = cfg['model']()
    item.descricao = descricao
    db.session.add(item)
    db.session.commit()
    return jsonify({'ok': True, 'id': item.id,
                    'descricao': item.descricao, 'duplicata': False})


# ── Hub ────────────────────────────────────────────────────────────────────────
@tabelas_bp.route('/')
@login_required
def index():
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    contagens = {}
    for chave, cfg in _TABELAS.items():
        model = cfg['model']
        total = model.query.count()
        if cfg.get('tem_ativo'):
            ativos   = model.query.filter_by(ativo=True).count()
            inativos = model.query.filter_by(ativo=False).count()
        else:
            ativos   = total
            inativos = 0
        contagens[chave] = {'total': total, 'ativos': ativos, 'inativos': inativos}

    modelos_count = (ParametroMunicipio.query
                     .filter(ParametroMunicipio.chave.like('modelo_requerimento_%'))
                     .count())

    return render_template('tabelas/index.html', tabelas=_TABELAS, contagens=contagens,
                           modelos_count=modelos_count)


# ── Modelos de Requerimento ────────────────────────────────────────────────────
@tabelas_bp.route('/requerimento')
@login_required
def requerimento():
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    modelos = (ParametroMunicipio.query
               .filter(ParametroMunicipio.chave.like('modelo_requerimento_%'))
               .order_by(ParametroMunicipio.chave)
               .all())
    return render_template('tabelas/requerimento.html', modelos=modelos)


@tabelas_bp.route('/requerimento/<int:id>/editar', methods=['POST'])
@login_required
def editar_requerimento(id):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    param = db.session.get(ParametroMunicipio, id)
    if not param or not param.chave.startswith('modelo_requerimento_'):
        flash('Modelo não encontrado.', 'danger')
        return redirect(url_for('tabelas.requerimento'))

    novo_valor = request.form.get('valor', '').strip()
    param.valor = novo_valor
    db.session.commit()
    flash('Modelo atualizado com sucesso.', 'success')
    return redirect(url_for('tabelas.requerimento'))


# ── Lista ──────────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/')
@login_required
def lista(chave):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None:
        flash('Tabela não encontrada.', 'danger')
        return redirect(url_for('tabelas.index'))

    filtro = request.args.get('filtro', 'ativos')
    q      = request.args.get('q', '').strip()

    query = cfg['model'].query.order_by(cfg['model'].descricao)

    if cfg.get('tem_ativo'):
        if filtro == 'inativos':
            query = query.filter_by(ativo=False)
        else:
            query = query.filter_by(ativo=True)

    if q:
        query = query.filter(cfg['model'].descricao.ilike(f'%{q}%'))

    itens = query.all()

    uso_map = {item.id: cfg['check_uso'](item.id) for item in itens}

    return render_template('tabelas/lista.html',
                           chave=chave, cfg=cfg, itens=itens,
                           filtro=filtro, q=q, uso_map=uso_map)


# ── Novo ───────────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/novo', methods=['GET', 'POST'])
@login_required
def novo(chave):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None:
        flash('Tabela não encontrada.', 'danger')
        return redirect(url_for('tabelas.index'))

    if request.method == 'POST':
        descricao = request.form.get('descricao', '').strip()
        if not descricao:
            flash('Descrição é obrigatória.', 'danger')
            return render_template('tabelas/form.html',
                                   chave=chave, cfg=cfg,
                                   titulo=f'Novo — {cfg["titulo"]}',
                                   acao='novo', item=None, form=request.form)

        similar = _similar_existe(cfg['model'], descricao)
        if similar and not request.form.get('confirmar_similar'):
            flash(
                f'Já existe um item similar: "{similar.descricao}". '
                f'Se quiser salvar mesmo assim, marque a confirmação abaixo.',
                'warning'
            )
            return render_template('tabelas/form.html',
                                   chave=chave, cfg=cfg,
                                   titulo=f'Novo — {cfg["titulo"]}',
                                   acao='novo', item=None,
                                   form=request.form,
                                   similar=similar)

        item = cfg['model']()
        _salvar_item(item, cfg, request.form, chave=chave)
        db.session.add(item)
        db.session.commit()
        _log_tabela('criacao', chave, item.id, f'Criado: {descricao}')
        db.session.commit()
        flash(f'"{descricao}" adicionado com sucesso.', 'success')
        return redirect(url_for('tabelas.lista', chave=chave))

    return render_template('tabelas/form.html',
                           chave=chave, cfg=cfg,
                           titulo=f'Novo — {cfg["titulo"]}',
                           acao='novo', item=None, form={}, similar=None)


# ── Editar ─────────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(chave, id):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None:
        flash('Tabela não encontrada.', 'danger')
        return redirect(url_for('tabelas.index'))

    item = db.get_or_404(cfg['model'], id)

    if request.method == 'POST':
        descricao = request.form.get('descricao', '').strip()
        if not descricao:
            flash('Descrição é obrigatória.', 'danger')
            return render_template('tabelas/form.html',
                                   chave=chave, cfg=cfg,
                                   titulo=f'Editar — {cfg["titulo"]}',
                                   acao='editar', item=item, form=request.form)

        similar = _similar_existe(cfg['model'], descricao, excluir_id=item.id)
        if similar and not request.form.get('confirmar_similar'):
            flash(
                f'Já existe um item similar: "{similar.descricao}". '
                f'Se quiser salvar mesmo assim, marque a confirmação abaixo.',
                'warning'
            )
            return render_template('tabelas/form.html',
                                   chave=chave, cfg=cfg,
                                   titulo=f'Editar — {cfg["titulo"]}',
                                   acao='editar', item=item,
                                   form=request.form,
                                   similar=similar)

        nome_anterior = item.descricao
        _salvar_item(item, cfg, request.form, chave=chave)
        _log_tabela('edicao', chave, item.id,
                    f'Editado: "{nome_anterior}" → "{descricao}"')
        db.session.commit()
        flash(f'"{descricao}" atualizado com sucesso.', 'success')
        return redirect(url_for('tabelas.lista', chave=chave))

    form = {}
    for campo in cfg['campos']:
        val = getattr(item, campo, None)
        if val is None:
            form[campo] = ''
        elif hasattr(val, 'isoformat'):
            form[campo] = val.isoformat()
        else:
            form[campo] = str(val)

    # Campos extras
    if chave == 'servico':
        form['link_portal'] = item.link_portal or ''
        form['instrucao']   = item.instrucao or ''
    elif chave == 'tipo-solicitacao':
        form['validade'] = item.validade.isoformat() if item.validade else ''

    return render_template('tabelas/form.html',
                           chave=chave, cfg=cfg,
                           titulo=f'Editar — {cfg["titulo"]}',
                           acao='editar', item=item, form=form, similar=None)


# ── Desativar ──────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/<int:id>/desativar', methods=['POST'])
@login_required
def desativar(chave, id):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None or not cfg.get('tem_ativo'):
        flash('Operação não permitida.', 'danger')
        return redirect(url_for('tabelas.index'))

    item = db.get_or_404(cfg['model'], id)

    if getattr(item, 'protegido', False):
        flash(f'"{item.descricao}" é protegido e não pode ser desativado.', 'danger')
        return redirect(url_for('tabelas.lista', chave=chave))

    motivo = request.form.get('motivo', '').strip()
    item.ativo = False
    _log_tabela('desativacao', chave, item.id,
                f'Desativado: {item.descricao}' + (f' — Motivo: {motivo}' if motivo else ''))
    db.session.commit()
    flash(f'"{item.descricao}" desativado.', 'warning')
    return redirect(url_for('tabelas.lista', chave=chave))


# ── Reativar ───────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/<int:id>/reativar', methods=['POST'])
@login_required
def reativar(chave, id):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None or not cfg.get('tem_ativo'):
        flash('Operação não permitida.', 'danger')
        return redirect(url_for('tabelas.index'))

    item = db.get_or_404(cfg['model'], id)
    item.ativo = True
    _log_tabela('reativacao', chave, item.id, f'Reativado: {item.descricao}')
    db.session.commit()
    flash(f'"{item.descricao}" reativado.', 'success')
    return redirect(url_for('tabelas.lista', chave=chave, filtro='inativos'))


# ── Remover ────────────────────────────────────────────────────────────────────
@tabelas_bp.route('/<chave>/<int:id>/remover', methods=['POST'])
@login_required
def remover(chave, id):
    bloqueio = _checar_acesso()
    if bloqueio:
        return bloqueio

    cfg = _get_cfg(chave)
    if cfg is None:
        flash('Tabela não encontrada.', 'danger')
        return redirect(url_for('tabelas.index'))

    item = db.get_or_404(cfg['model'], id)

    if getattr(item, 'protegido', False):
        flash(f'"{item.descricao}" é protegido e não pode ser removido.', 'danger')
        return redirect(url_for('tabelas.lista', chave=chave))

    uso = cfg['check_uso'](item.id)
    if uso:
        flash(
            f'Não é possível remover "{item.descricao}": está em uso em {uso} registro(s).',
            'danger'
        )
        return redirect(url_for('tabelas.lista', chave=chave))

    nome = item.descricao
    _log_tabela('exclusao', chave, item.id, f'Removido: {nome}')
    db.session.delete(item)
    db.session.commit()
    flash(f'"{nome}" removido com sucesso.', 'success')
    return redirect(url_for('tabelas.lista', chave=chave))
