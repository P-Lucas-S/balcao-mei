from functools import wraps
import io
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .. import db
from ..models import Usuario, PerfilAcesso, LogAcao

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

_PERFIS_PERMITIDOS = {'administrador'}


# Perfis que o sistema de fato reconhece — todo guard checa um destes três.
# Os demais em `perfil_acesso` são legado com 0 usuários; ficam no banco, mas
# não são oferecidos no formulário: escolher um por engano criaria alguém que
# falha em todos os guards e vira atendente de fato, sem ninguém ter decidido.
PERFIS_EM_USO = ('atendente', 'supervisor', 'administrador')


def _nome_perfil(id_perfil):
    """Nome do perfil por id — usado para o template decidir, no servidor, se
    o campo de supervisor aparece. Sem isso o esconder dependeria de JS."""
    p = db.session.get(PerfilAcesso, int(id_perfil)) if id_perfil else None
    return p.nome if p else ''


def _get_perfis(atual_id=None):
    """Perfis oferecidos no formulário.

    Os três em uso, MAIS o perfil atual do usuário editado — mesmo que seja
    legado. Sem esse "mais", editar um usuário de perfil antigo forçaria a
    troca de perfil como efeito colateral de salvar o nome.
    """
    cond = PerfilAcesso.nome.in_(PERFIS_EM_USO)
    if atual_id:
        cond = db.or_(cond, PerfilAcesso.id == atual_id)
    return PerfilAcesso.query.filter(cond).order_by(PerfilAcesso.nome).all()


def _get_supervisores(atual_id=None):
    """ADs que podem ser escolhidos como supervisor.

    Os ativos, MAIS o supervisor atualmente vinculado — ainda que inativo.

    Sem esse "mais", editar um bolsista cujo AD foi desativado desvinculava a
    equipe **em silêncio**: o `<select>` não encontrava o valor gravado, caía
    em "Nenhum", e salvar gravava `None`. Quem editasse o telefone de um
    bolsista desmontaria a equipe sem saber.
    """
    cond = Usuario.ativo == True
    if atual_id:
        cond = db.or_(cond, Usuario.id == atual_id)
    return (Usuario.query
            .join(Usuario.perfil)
            .filter(PerfilAcesso.nome == 'supervisor', cond)
            .order_by(Usuario.nome)
            .all())


def _cria_ciclo(usuario_id, supervisor_id):
    """Se pôr `supervisor_id` como chefe de `usuario_id` fecha um ciclo.

    Sobe a cadeia a partir do supervisor pretendido. Se reencontrar o próprio
    usuário, o vínculo se morderia. O limite de saltos é rede contra um ciclo
    que já exista no banco — sem ele, a subida não terminaria.
    """
    atual, saltos = supervisor_id, 0
    while atual and saltos < 20:
        if atual == usuario_id:
            return True
        chefe = db.session.get(Usuario, atual)
        atual = chefe.supervisor_id if chefe else None
        saltos += 1
    return False


def _resolver_supervisor(form, perfil_nome, usuario=None):
    """Decide o `supervisor_id` a gravar. Devolve `(valor, erros)`.

    `supervisor_id` só faz sentido para **atendente**: é o vínculo com o AD.
    Para supervisor e administrador é ignorado (vira `None`) em vez de virar
    erro — o campo fica escondido na tela, e um valor que chega aí é resíduo
    do formulário, não intenção de quem preencheu.
    """
    if perfil_nome != 'atendente':
        return None, []

    sup_id = form.get('supervisor_id', type=int) or None
    if sup_id is None:
        return None, []

    erros = []
    if usuario is not None and sup_id == usuario.id:
        erros.append('Um usuário não pode ser supervisor de si mesmo.')
        return None, erros

    chefe = db.session.get(Usuario, sup_id)
    if chefe is None or chefe.perfil.nome != 'supervisor':
        erros.append('O supervisor escolhido não existe ou não é um supervisor.')
        return None, erros

    if usuario is not None and _cria_ciclo(usuario.id, sup_id):
        erros.append('Esse vínculo criaria um ciclo de supervisão.')
        return None, erros

    return sup_id, erros


def _requer_admin_ou_secretario(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.perfil.nome not in _PERFIS_PERMITIDOS:
            flash('Acesso restrito a administradores e secretários.', 'danger')
            return redirect(url_for('pessoas.index'))
        return f(*args, **kwargs)
    return decorated


def _valida_form(form, criando=True):
    erros = []
    if not form.get('nome', '').strip():
        erros.append('Nome é obrigatório.')
    if not form.get('login', '').strip():
        erros.append('Login é obrigatório.')
    if not form.get('id_perfil'):
        erros.append('Selecione um perfil.')
    if criando and not form.get('senha', '').strip():
        erros.append('Senha é obrigatória no cadastro.')

    senha = form.get('senha', '').strip()
    confirmar = form.get('confirmar_senha', '').strip()
    if senha:
        if len(senha) < 6:
            erros.append('Senha deve ter pelo menos 6 caracteres.')
        if not any(c.isdigit() for c in senha):
            erros.append('Senha deve conter pelo menos 1 número.')
        if senha != confirmar:
            erros.append('As senhas não conferem.')

    return erros


# ── Lista ──────────────────────────────────────────────────────────────────────
@usuarios_bp.route('/')
@login_required
@_requer_admin_ou_secretario
def index():
    from datetime import date
    from sqlalchemy.orm import joinedload

    q = request.args.get('q', '').strip()
    f_equipe = request.args.get('equipe', '').strip()

    query = Usuario.query.join(Usuario.perfil)
    if q:
        query = query.filter(
            db.or_(
                Usuario.nome.ilike(f'%{q}%'),
                Usuario.login.ilike(f'%{q}%'),
            )
        )

    # Filtro por AD: a equipe é o supervisor + quem tem supervisor_id nele.
    # `sem` isola quem ficou fora de qualquer equipe — o caso que a gestão
    # precisa enxergar para agir.
    if f_equipe == 'sem':
        query = query.filter(Usuario.supervisor_id.is_(None),
                             PerfilAcesso.nome == 'atendente')
    elif f_equipe.isdigit():
        sup_id = int(f_equipe)
        query = query.filter(db.or_(Usuario.supervisor_id == sup_id,
                                    Usuario.id == sup_id))

    usuarios = (query.options(joinedload(Usuario.supervisor))
                .order_by(Usuario.ativo.desc(), Usuario.nome).all())
    return render_template('usuarios/lista.html', usuarios=usuarios,
                           hoje=date.today(), q=q, f_equipe=f_equipe,
                           supervisores=_get_supervisores())


# ── Novo ───────────────────────────────────────────────────────────────────────
@usuarios_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@_requer_admin_ou_secretario
def novo():
    perfis = _get_perfis()
    supervisores = _get_supervisores()

    if request.method == 'POST':
        erros = _valida_form(request.form, criando=True)

        login_existente = Usuario.query.filter_by(
            login=request.form.get('login', '').strip()
        ).first()
        if login_existente:
            erros.append(f'Login "{request.form["login"]}" já está em uso.')

        perfil_escolhido = db.session.get(
            PerfilAcesso, request.form.get('id_perfil', type=int) or 0)
        sup_id, erros_sup = _resolver_supervisor(
            request.form, perfil_escolhido.nome if perfil_escolhido else '')
        erros += erros_sup

        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('usuarios/form.html',
                                   titulo='Novo Usuário', acao='novo',
                                   perfis=perfis, supervisores=supervisores,
                                   perfil_atual=_nome_perfil(request.form.get('id_perfil')),
                                   form=request.form)

        u = Usuario(
            nome          = request.form['nome'].strip(),
            login         = request.form['login'].strip(),
            senha         = generate_password_hash(request.form['senha']),
            id_perfil     = int(request.form['id_perfil']),
            supervisor_id = sup_id,
            ativo         = True,
        )
        db.session.add(u)
        db.session.commit()
        flash(f'Usuário "{u.nome}" cadastrado com sucesso.', 'success')
        return redirect(url_for('usuarios.index'))

    return render_template('usuarios/form.html',
                           titulo='Novo Usuário', acao='novo',
                           perfis=perfis, supervisores=supervisores,
                                   perfil_atual='', form={})


# ── Editar ─────────────────────────────────────────────────────────────────────
@usuarios_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@_requer_admin_ou_secretario
def editar(id):
    u = db.get_or_404(Usuario, id)
    perfis = _get_perfis(u.id_perfil)
    # O supervisor atual entra na lista mesmo inativo — é o que impede a
    # desvinculação silenciosa ao editar qualquer outro campo.
    supervisores = _get_supervisores(u.supervisor_id)

    if request.method == 'POST':
        erros = _valida_form(request.form, criando=False)

        novo_login = request.form.get('login', '').strip()
        login_existente = Usuario.query.filter(
            Usuario.login == novo_login,
            Usuario.id != id
        ).first()
        if login_existente:
            erros.append(f'Login "{novo_login}" já está em uso por outro usuário.')

        if u.id == current_user.id:
            novo_perfil_id = int(request.form.get('id_perfil', 0) or 0)
            if novo_perfil_id and novo_perfil_id != current_user.id_perfil:
                erros.append('Você não pode alterar o próprio perfil de acesso.')

        perfil_escolhido = db.session.get(
            PerfilAcesso, request.form.get('id_perfil', type=int) or 0)
        sup_id, erros_sup = _resolver_supervisor(
            request.form, perfil_escolhido.nome if perfil_escolhido else '', u)
        erros += erros_sup

        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('usuarios/form.html',
                                   titulo='Editar Usuário', acao='editar',
                                   u=u, perfis=perfis, supervisores=supervisores,
                                   perfil_atual=_nome_perfil(request.form.get('id_perfil')),
                                   form=request.form)

        u.nome          = request.form['nome'].strip()
        u.login         = novo_login
        u.id_perfil     = int(request.form['id_perfil'])
        u.supervisor_id = sup_id

        nova_senha = request.form.get('senha', '').strip()
        if nova_senha:
            u.senha = generate_password_hash(nova_senha)

        db.session.commit()
        flash(f'Usuário "{u.nome}" atualizado com sucesso.', 'success')
        return redirect(url_for('usuarios.index'))

    form = {
        'nome':         u.nome,
        'login':        u.login,
        'id_perfil':    str(u.id_perfil),
        'supervisor_id': str(u.supervisor_id) if u.supervisor_id else '',
    }
    return render_template('usuarios/form.html',
                           titulo='Editar Usuário', acao='editar',
                           u=u, perfis=perfis, supervisores=supervisores,
                                   perfil_atual=u.perfil.nome, form=form)


# ── Ativar ─────────────────────────────────────────────────────────────────────
@usuarios_bp.route('/<int:id>/ativar', methods=['POST'])
@login_required
@_requer_admin_ou_secretario
def ativar(id):
    u = db.get_or_404(Usuario, id)
    u.ativo = True
    db.session.commit()
    flash(f'Usuário "{u.nome}" ativado.', 'success')
    return redirect(url_for('usuarios.index'))


# ── Desativar ──────────────────────────────────────────────────────────────────
@usuarios_bp.route('/<int:id>/desativar', methods=['POST'])
@login_required
@_requer_admin_ou_secretario
def desativar(id):
    u = db.get_or_404(Usuario, id)

    if u.id == current_user.id:
        flash('Você não pode desativar o seu próprio usuário.', 'danger')
        return redirect(url_for('usuarios.index'))

    u.ativo = False
    db.session.commit()
    flash(f'Usuário "{u.nome}" desativado.', 'warning')
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    erro = None
    sucesso = None

    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '')
        nova_senha  = request.form.get('nova_senha', '')
        confirmar   = request.form.get('confirmar_senha', '')

        if not check_password_hash(current_user.senha, senha_atual):
            erro = 'Senha atual incorreta.'
        elif len(nova_senha) < 6:
            erro = 'A nova senha deve ter pelo menos 6 caracteres.'
        elif not any(c.isdigit() for c in nova_senha):
            erro = 'A nova senha deve conter pelo menos 1 número.'
        elif nova_senha != confirmar:
            erro = 'As senhas não coincidem.'
        else:
            current_user.senha = generate_password_hash(nova_senha)
            db.session.commit()
            log = LogAcao(
                id_usuario  = current_user.id,
                acao        = 'alteracao_senha',
                entidade    = 'usuario',
                entidade_id = current_user.id,
                descricao   = f'Senha alterada pelo próprio usuário ({current_user.login})',
            )
            db.session.add(log)
            db.session.commit()
            sucesso = 'Senha alterada com sucesso.'

    return render_template('usuarios/perfil.html', erro=erro, sucesso=sucesso)


@usuarios_bp.route('/log')
@login_required
def log():
    if current_user.perfil.nome != 'administrador':
        flash('Acesso restrito ao administrador.', 'danger')
        return redirect(url_for('usuarios.index'))

    page = request.args.get('page', 1, type=int)
    acao_filtro     = request.args.get('acao',       '').strip()
    usuario_filtro  = request.args.get('usuario_id', '').strip()
    data_de_filtro  = request.args.get('data_de',    '').strip()
    data_ate_filtro = request.args.get('data_ate',   '').strip()

    query = LogAcao.query
    if acao_filtro:
        query = query.filter_by(acao=acao_filtro)
    if usuario_filtro:
        query = query.filter(LogAcao.id_usuario == int(usuario_filtro))
    if data_de_filtro:
        try:
            from datetime import date
            query = query.filter(LogAcao.created_at >= date.fromisoformat(data_de_filtro))
        except ValueError:
            pass
    if data_ate_filtro:
        try:
            from datetime import date, timedelta
            query = query.filter(LogAcao.created_at < date.fromisoformat(data_ate_filtro) + timedelta(days=1))
        except ValueError:
            pass

    usuarios_ativos = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()

    paginacao = (
        query
        .order_by(LogAcao.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template('usuarios/log.html',
                           logs=paginacao.items,
                           paginacao=paginacao,
                           acao_filtro=acao_filtro,
                           usuario_filtro=usuario_filtro,
                           data_de_filtro=data_de_filtro,
                           data_ate_filtro=data_ate_filtro,
                           usuarios_ativos=usuarios_ativos)


@usuarios_bp.route('/log/exportar')
@login_required
def exportar_log():
    if current_user.perfil.nome != 'administrador':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('usuarios.log'))

    from datetime import date, timedelta

    acao_filtro     = request.args.get('acao',       '').strip()
    usuario_filtro  = request.args.get('usuario_id', '').strip()
    data_de_filtro  = request.args.get('data_de',    '').strip()
    data_ate_filtro = request.args.get('data_ate',   '').strip()

    query = LogAcao.query
    if acao_filtro:
        query = query.filter_by(acao=acao_filtro)
    if usuario_filtro:
        query = query.filter(LogAcao.id_usuario == int(usuario_filtro))
    if data_de_filtro:
        try:
            query = query.filter(LogAcao.created_at >= date.fromisoformat(data_de_filtro))
        except ValueError:
            pass
    if data_ate_filtro:
        try:
            query = query.filter(
                LogAcao.created_at < date.fromisoformat(data_ate_filtro) + timedelta(days=1)
            )
        except ValueError:
            pass

    logs = query.order_by(LogAcao.created_at.desc()).limit(10000).all()

    usuario_nome_filtro = None
    if usuario_filtro:
        u = db.session.get(Usuario, int(usuario_filtro))
        if u:
            usuario_nome_filtro = u.nome

    filtros = {
        'data_de':      data_de_filtro or None,
        'data_ate':     data_ate_filtro or None,
        'usuario_nome': usuario_nome_filtro,
        'acao':         acao_filtro or None,
    }

    from .relatorios.exporters import gerar_xlsx_log
    conteudo = gerar_xlsx_log(logs, filtros)

    if data_de_filtro and data_ate_filtro:
        nome = f"log_auditoria_{data_de_filtro}_{data_ate_filtro}.xlsx"
    else:
        nome = f"log_auditoria_{date.today().isoformat()}.xlsx"

    return send_file(
        io.BytesIO(conteudo),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome,
    )


@usuarios_bp.route('/log/exportar/pdf')
@login_required
def exportar_log_pdf():
    if current_user.perfil.nome != 'administrador':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('usuarios.log'))

    from datetime import date, timedelta

    acao_filtro     = request.args.get('acao',       '').strip()
    usuario_filtro  = request.args.get('usuario_id', '').strip()
    data_de_filtro  = request.args.get('data_de',    '').strip()
    data_ate_filtro = request.args.get('data_ate',   '').strip()

    query = LogAcao.query
    if acao_filtro:
        query = query.filter_by(acao=acao_filtro)
    if usuario_filtro:
        query = query.filter(LogAcao.id_usuario == int(usuario_filtro))
    if data_de_filtro:
        try:
            query = query.filter(LogAcao.created_at >= date.fromisoformat(data_de_filtro))
        except ValueError:
            pass
    if data_ate_filtro:
        try:
            query = query.filter(
                LogAcao.created_at < date.fromisoformat(data_ate_filtro) + timedelta(days=1)
            )
        except ValueError:
            pass

    logs = query.order_by(LogAcao.created_at.desc()).limit(5000).all()

    filtros = {
        'data_de':  data_de_filtro or None,
        'data_ate': data_ate_filtro or None,
        'acao':     acao_filtro or None,
    }

    from .relatorios.exporters import gerar_pdf_log
    pdf_bytes = gerar_pdf_log(logs, filtros)

    nome = f"log_auditoria_{date.today().isoformat()}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nome,
    )
