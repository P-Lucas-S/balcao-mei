"""
conftest.py — Fixtures globais para o suite de testes do Balcão MEI.

Usa SQLite em memória para isolamento total; cada teste recebe um banco zerado.
CSRF e rate limiting são desabilitados na config de teste.
"""
import pytest
from datetime import date, time
from werkzeug.security import generate_password_hash
import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.pool import StaticPool

from app import create_app, db as _db
from app.models import (
    PerfilAcesso, Usuario, Pessoa, Atendimento,
    Status, TipoSolicitacao, CanalAtendimento, Servico, Solicitacao,
)

# ── Configuração de teste ─────────────────────────────────────────────────────
#
# StaticPool garante que todas as conexões (fixture + requisições HTTP) usem
# a mesma instância do banco SQLite em memória. Sem isso, cada request do
# test_client abre uma nova conexão e vê um banco vazio.

TEST_CONFIG = {
    "TESTING": True,
    "WTF_CSRF_ENABLED": False,
    "SQLALCHEMY_DATABASE_URI": "sqlite://",
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    },
    "RATELIMIT_ENABLED": False,
    "SECRET_KEY": "test-secret-key-demo",
    "SERVER_NAME": None,
}

# ── Fixtures de app / banco / cliente ─────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Cria a aplicação Flask com configurações de teste (uma vez por sessão).

    Passa TEST_CONFIG para create_app() para que o engine SQLite seja criado
    ANTES de db.init_app(app) — Flask-SQLAlchemy 3.1+ cria engines eagerly.
    """
    application = create_app(TEST_CONFIG)
    # Garante que logs não poluam a saída dos testes
    application.logger.handlers.clear()
    return application


@pytest.fixture(scope="function")
def db(app):
    """
    Cria todas as tabelas antes de cada teste e as destrói depois.
    Também semeia os dados base necessários (perfis, status, tipo de solicitação).
    """
    with app.app_context():
        _db.create_all()
        _seed_base()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):
    """Cliente HTTP de teste com contexto de aplicação ativo."""
    with app.test_client() as c:
        yield c


# ── Semeadura de dados base ───────────────────────────────────────────────────

def _seed_base():
    """Insere registros mínimos que as rotas esperam encontrar no banco."""
    # Perfis de acesso
    for nome in ("administrador", "supervisor", "atendente"):
        if not PerfilAcesso.query.filter_by(nome=nome).first():
            _db.session.add(PerfilAcesso(nome=nome, descricao=nome.capitalize()))

    # Status de solicitação
    for descricao in ("Pendente", "Em Análise", "Aprovado", "Recusado"):
        if not Status.query.filter_by(descricao=descricao).first():
            _db.session.add(Status(descricao=descricao))

    # Tipo de solicitação padrão
    if not TipoSolicitacao.query.first():
        _db.session.add(TipoSolicitacao(descricao="Orientação Geral", ativo=True))

    # Canais — COMO o empreendedor chegou (um por atendimento)
    for descricao in ("Presencial", "Telefone"):
        if not CanalAtendimento.query.filter_by(descricao=descricao).first():
            _db.session.add(CanalAtendimento(descricao=descricao, ativo=True))

    # Serviços — O QUE foi feito (vários por atendimento). Sem eles nenhuma
    # rota de criação de atendimento passa na validação.
    # Um COM link_portal e um SEM: a tela guiada só desenha o ícone de portal
    # nos que têm link, e há teste para essa distinção.
    # Mistura representativa das três aplicabilidades — a filtragem por tipo
    # efetivo depende disso para ser testável, e "Abertura de MEI" é a âncora
    # da conversão PF→MEI na tela guiada.
    for descricao, aplic, link in (
        ("Abertura de MEI", "nao_mei",
         "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/quero-ser-mei"),
        ("Boleto DAS", "mei",
         "https://www8.receita.fazenda.gov.br/simplesnacional/aplicacoes/"
         "atspo/pgmei.app/identificacao"),
        ("Orientação ao Empreendedor", "todos", None),
        ("Cadastro de Box/Quiosque", "todos", None),
        # Sem link_portal de propósito: o ícone dele abre o formulário
        # interno de solicitação, não um portal externo.
        ("Solicitação", "todos", None),
    ):
        if not Servico.query.filter_by(descricao=descricao).first():
            _db.session.add(Servico(descricao=descricao, ativo=True,
                                    aplicabilidade=aplic, link_portal=link))

    _db.session.commit()


# ── Helper de usuário ─────────────────────────────────────────────────────────

def criar_usuario(perfil_nome, login=None, senha="senha123", ativo=True):
    """Cria e persiste um Usuario com o perfil indicado."""
    perfil = PerfilAcesso.query.filter_by(nome=perfil_nome).first()
    login = login or f"teste_{perfil_nome}"
    u = Usuario(
        nome=f"Teste {perfil_nome.capitalize()}",
        login=login,
        senha=generate_password_hash(senha),
        ativo=ativo,
        id_perfil=perfil.id,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


# ── Fixture auth ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def auth(client):
    """
    Helper para autenticar o cliente de teste.

    login_como(): injeta a sessão Flask-Login diretamente via session_transaction(),
    sem passar pelo HTTP login. Isso evita problemas com múltiplos app contexts
    e torna os testes de funcionalidade agnósticos à implementação do login.

    login_via_http(): usa a rota POST /login, útil nos testes de autenticação.
    """
    class AuthHelper:
        def login_como(self, perfil="atendente", senha="senha123"):
            """
            Cria usuário do perfil e injeta o ID na sessão diretamente.
            Retorna o objeto Usuario criado.
            """
            u = criar_usuario(perfil, senha=senha)
            with client.session_transaction() as sess:
                sess["_user_id"] = str(u.id)
                sess["_fresh"] = True
            return u

        def login_via_http(self, login, senha="senha123", follow=False):
            """Faz login através da rota POST /login (para testes de auth)."""
            return client.post(
                "/login",
                data={"login": login, "senha": senha},
                follow_redirects=follow,
            )

        def logout(self):
            return client.get("/logout", follow_redirects=True)

    return AuthHelper()


# ── Factories (factory-boy) ───────────────────────────────────────────────────

class _Base(SQLAlchemyModelFactory):
    """Configuração base compartilhada por todas as factories."""
    class Meta:
        abstract = True
        sqlalchemy_session = _db.session
        sqlalchemy_session_persistence = "commit"


class PerfilFactory(_Base):
    class Meta:
        model = PerfilAcesso
    nome = factory.Sequence(lambda n: f"perfil_{n}")
    descricao = factory.LazyAttribute(lambda o: o.nome.capitalize())


class UsuarioFactory(_Base):
    class Meta:
        model = Usuario

    nome  = factory.Sequence(lambda n: f"Usuário {n}")
    login = factory.Sequence(lambda n: f"user_{n}")
    senha = factory.LazyFunction(lambda: generate_password_hash("senha123"))
    ativo = True

    @factory.lazy_attribute
    def id_perfil(self):
        return PerfilAcesso.query.filter_by(nome="atendente").first().id


class PessoaFactory(_Base):
    class Meta:
        model = Pessoa

    nome_razao_social = factory.Sequence(lambda n: f"Empreendedor {n}")
    cpf               = factory.Sequence(lambda n: f"000.000.{n:03d}-00")
    origem            = "operacional"
    exclusao_pendente = False


class AtendimentoFactory(_Base):
    class Meta:
        model = Atendimento

    data_atendimento  = factory.LazyFunction(date.today)
    hora_atendimento  = time(9, 0)
    exclusao_pendente = False
    origem            = "operacional"

    @factory.lazy_attribute
    def id_usuario(self):
        return UsuarioFactory.create().id

    @factory.lazy_attribute
    def id_pessoa(self):
        return PessoaFactory.create().id

    @factory.lazy_attribute
    def id_canal(self):
        return CanalAtendimento.query.order_by(CanalAtendimento.id).first().id


class SolicitacaoFactory(_Base):
    class Meta:
        model = Solicitacao

    data_solicitacao  = factory.LazyFunction(date.today)
    exclusao_pendente = False

    @factory.lazy_attribute
    def id_usuario(self):
        return UsuarioFactory.create().id

    @factory.lazy_attribute
    def id_pessoa(self):
        return PessoaFactory.create().id

    @factory.lazy_attribute
    def id_tipo_solicitacao(self):
        return TipoSolicitacao.query.first().id

    @factory.lazy_attribute
    def id_status(self):
        return Status.query.filter_by(descricao="Pendente").first().id
