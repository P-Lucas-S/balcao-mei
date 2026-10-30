import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir (desenvolvimento local)
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-mude-em-producao')

    DB_HOST     = os.environ.get('DB_HOST',     'localhost')
    DB_PORT     = os.environ.get('DB_PORT',     '5432')
    DB_NAME     = os.environ.get('DB_NAME',     'sistema_solicitacoes')
    DB_USER     = os.environ.get('DB_USER',     'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '123')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?client_encoding=utf8"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CSRF
    WTF_CSRF_ENABLED    = True
    WTF_CSRF_TIME_LIMIT = 7200  # 2 horas
