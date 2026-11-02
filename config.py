import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir (desenvolvimento local)
load_dotenv()

APP_ENV = os.environ.get('APP_ENV', 'development')


def _secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    if APP_ENV == 'production':
        raise RuntimeError('SECRET_KEY não definida: obrigatória com APP_ENV=production.')
    return 'dev-secret-key-somente-local'


def _database_uri():
    # DATABASE_URL tem prioridade (ex.: sqlite:///demo.db na demo publicada).
    url = os.environ.get('DATABASE_URL')
    if url:
        return url.replace('postgres://', 'postgresql://', 1)
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    name = os.environ.get('DB_NAME', 'sistema_solicitacoes')
    user = os.environ.get('DB_USER', 'postgres')
    pwd = os.environ.get('DB_PASSWORD', '')
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}?client_encoding=utf8"


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Demonstração pública: mostra os logins de teste na tela de entrada
    DEMO_MODE = os.environ.get('DEMO_MODE', '0') == '1'

    # CSRF
    WTF_CSRF_ENABLED    = True
    WTF_CSRF_TIME_LIMIT = 7200  # 2 horas
