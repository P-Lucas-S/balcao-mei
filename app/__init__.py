import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

db            = SQLAlchemy()
login_manager = LoginManager()
csrf          = CSRFProtect()
limiter       = Limiter(get_remote_address, default_limits=["200 per day", "50 per hour"])
cache         = Cache()


def create_app(test_config=None):
    app = Flask(__name__)

    from config import Config
    app.config.from_object(Config)

    # Sobrescreve com configurações de teste antes de qualquer init_app.
    # Flask-SQLAlchemy 3.1+ cria engines eagerly em init_app, portanto
    # o test_config deve ser aplicado ANTES de db.init_app(app).
    if test_config is not None:
        app.config.update(test_config)

    # Performance e pool de conexões (setdefault não sobrescreve se test_config já definiu)
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
        'pool_size':    5,
        'max_overflow': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    })

    import os
    _upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'documentos')
    os.makedirs(_upload_dir, exist_ok=True)
    app.config['UPLOAD_DOCUMENTOS']  = _upload_dir
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

    from datetime import timedelta
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)

    app.config.from_mapping({
        'CACHE_TYPE': 'NullCache' if test_config is not None else 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300,
    })
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    from .models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    from .routes.main         import main_bp
    from .routes.auth         import auth_bp
    from .routes.pessoas      import pessoas_bp
    from .routes.atendimentos import atendimentos_bp
    from .routes.solicitacoes import solicitacoes_bp
    from .routes.usuarios     import usuarios_bp
    from .routes.relatorios   import bp as relatorios_bp
    from .routes.tabelas      import tabelas_bp
    from .routes.fichas       import fichas_bp
    from .routes.documentos   import documentos_bp
    from .routes.pendencias   import pendencias_bp
    from .routes.analise      import analise_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(pessoas_bp)
    app.register_blueprint(atendimentos_bp)
    app.register_blueprint(solicitacoes_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(tabelas_bp)
    app.register_blueprint(fichas_bp)
    app.register_blueprint(documentos_bp)
    app.register_blueprint(pendencias_bp)
    app.register_blueprint(analise_bp)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        n_pendencias = 0
        if current_user.is_authenticated:
            if current_user.perfil.nome == 'administrador':
                from .models import SolicitacaoExclusao
                n_pendencias = SolicitacaoExclusao.query.filter_by(status='pendente').count()
        from . import marca
        return dict(n_pendencias=n_pendencias, marca=marca)

    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def erro_interno(e):
        return render_template('500.html'), 500

    # ── Headers de segurança ──────────────────────────────────────────────
    @app.after_request
    def _seguranca(response):
        response.headers['X-Frame-Options']        = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection']       = '1; mode=block'
        response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy']     = 'geolocation=(), microphone=(), camera=()'
        response.headers['Cache-Control']          = 'no-store, no-cache, must-revalidate'
        return response

    # ── Logs em arquivo ───────────────────────────────────────────────────
    _logs_dir = os.path.normpath(os.path.join(app.root_path, '..', 'logs'))
    os.makedirs(_logs_dir, exist_ok=True)
    _handler = RotatingFileHandler(
        os.path.join(_logs_dir, 'app.log'),
        maxBytes=1 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    _handler.setLevel(logging.WARNING)
    _handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s %(module)s: %(message)s'
    ))
    app.logger.setLevel(logging.WARNING)
    app.logger.addHandler(_handler)

    return app
