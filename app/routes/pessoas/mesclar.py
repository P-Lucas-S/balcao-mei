from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ... import db
from ...models import Pessoa, Atendimento, Solicitacao
from .crud import pessoas_bp, _registrar_log

_PERFIS_MESCLAR = {'administrador'}


@pessoas_bp.route('/mesclar')
@login_required
def mesclar_busca():
    if current_user.perfil.nome not in _PERFIS_MESCLAR:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('pessoas.index'))

    q = request.args.get('q', '').strip()
    pessoas = []
    if q and len(q) >= 2:
        like = f'%{q}%'
        pessoas = Pessoa.visiveis().filter(
            db.or_(
                Pessoa.nome_razao_social.ilike(like),
                Pessoa.cpf.ilike(like),
                Pessoa.cnpj.ilike(like),
            )
        ).order_by(Pessoa.nome_razao_social).limit(20).all()

    return render_template('pessoas/mesclar_busca.html', q=q, pessoas=pessoas)


@pessoas_bp.route('/mesclar/confirmar')
@login_required
def mesclar_confirmar():
    if current_user.perfil.nome not in _PERFIS_MESCLAR:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('pessoas.index'))

    id_principal = request.args.get('principal', type=int)
    id_duplicada = request.args.get('duplicada', type=int)

    if not id_principal or not id_duplicada:
        flash('Selecione as duas pessoas.', 'danger')
        return redirect(url_for('pessoas.mesclar_busca'))

    if id_principal == id_duplicada:
        flash('Selecione pessoas diferentes.', 'danger')
        return redirect(url_for('pessoas.mesclar_busca'))

    principal = db.get_or_404(Pessoa, id_principal)
    duplicada  = db.get_or_404(Pessoa, id_duplicada)

    qtd_atend_dup = Atendimento.query.filter_by(id_pessoa=id_duplicada).count()
    qtd_solic_dup = Solicitacao.query.filter_by(id_pessoa=id_duplicada).count()

    return render_template('pessoas/mesclar_confirmar.html',
                           principal=principal,
                           duplicada=duplicada,
                           qtd_atend_dup=qtd_atend_dup,
                           qtd_solic_dup=qtd_solic_dup)


@pessoas_bp.route('/mesclar/executar', methods=['POST'])
@login_required
def mesclar_executar():
    if current_user.perfil.nome not in _PERFIS_MESCLAR:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('pessoas.index'))

    id_principal = request.form.get('principal', type=int)
    id_duplicada = request.form.get('duplicada', type=int)

    if not id_principal or not id_duplicada or id_principal == id_duplicada:
        flash('Dados inválidos.', 'danger')
        return redirect(url_for('pessoas.mesclar_busca'))

    principal = db.get_or_404(Pessoa, id_principal)
    duplicada  = db.get_or_404(Pessoa, id_duplicada)

    qtd_atend = Atendimento.query.filter_by(id_pessoa=id_duplicada).update(
        {'id_pessoa': id_principal}
    )
    qtd_solic = Solicitacao.query.filter_by(id_pessoa=id_duplicada).update(
        {'id_pessoa': id_principal}
    )

    if not principal.cpf             and duplicada.cpf:
        principal.cpf             = duplicada.cpf
    if not principal.cnpj            and duplicada.cnpj:
        principal.cnpj            = duplicada.cnpj
    if not principal.telefone        and duplicada.telefone:
        principal.telefone        = duplicada.telefone
    if not principal.email           and duplicada.email:
        principal.email           = duplicada.email
    if not principal.endereco        and duplicada.endereco:
        principal.endereco        = duplicada.endereco
    if not principal.data_nascimento and duplicada.data_nascimento:
        principal.data_nascimento = duplicada.data_nascimento

    nome_dup = duplicada.nome_razao_social
    _registrar_log(
        acao='mesclagem',
        entidade='pessoa',
        entidade_id=id_principal,
        descricao=(
            f'Mesclagem: "{nome_dup}" (id={id_duplicada}) '
            f'→ "{principal.nome_razao_social}" (id={id_principal}). '
            f'{qtd_atend} atendimento(s) e {qtd_solic} solicitação(ões) transferidos.'
        ),
    )
    db.session.delete(duplicada)
    db.session.commit()

    flash(
        f'Mesclagem concluída! {qtd_atend} atendimento(s) e {qtd_solic} '
        f'solicitação(ões) transferidos de "{nome_dup}" para '
        f'"{principal.nome_razao_social}".',
        'success'
    )
    return redirect(url_for('pessoas.detalhe', id=id_principal))
