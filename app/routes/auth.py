from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timezone
from ..models import Usuario, LogAcao
from .. import db, limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        senha_val = request.form.get('senha', '')

        usuario = Usuario.query.filter_by(login=login_val).first()

        if usuario and usuario.ativo and check_password_hash(usuario.senha, senha_val):
            login_user(usuario)
            session.permanent = True

            from .pessoas import _registrar_log
            _registrar_log(
                acao='login',
                entidade='usuario',
                entidade_id=usuario.id,
                descricao=f'Login: {usuario.nome} ({usuario.login}) — IP: {request.remote_addr}'
            )
            usuario.ultimo_login = datetime.now(timezone.utc)
            db.session.commit()

            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        log_falha = LogAcao(
            id_usuario=None,
            acao='login_falha',
            entidade='usuario',
            entidade_id=None,
            descricao=f'Tentativa falha: login="{login_val}" — IP: {request.remote_addr}'
        )
        db.session.add(log_falha)
        db.session.commit()
        flash('⚠️ Login ou senha incorretos. Verifique se o Caps Lock está ativado.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_logout = LogAcao(
        id_usuario=current_user.id,
        acao='logout',
        entidade='usuario',
        entidade_id=current_user.id,
        descricao=f'Logout: {current_user.nome} ({current_user.login}) — IP: {request.remote_addr}'
    )
    db.session.add(log_logout)
    db.session.commit()
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))
