"""
test_auth.py — Testes de autenticação.
"""
from tests.conftest import criar_usuario


# ── Helpers ───────────────────────────────────────────────────────────────────

def _post_login(client, login, senha, follow=False):
    return client.post(
        "/login",
        data={"login": login, "senha": senha},
        follow_redirects=follow,
    )


# ── Testes ────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_correto_redireciona_para_dashboard(self, client, db, auth):
        """Login com credenciais válidas → 302 para /dashboard."""
        u = criar_usuario("atendente", login="joao", senha="senha123")
        rv = auth.login_via_http("joao", "senha123")
        assert rv.status_code == 302
        assert "/dashboard" in rv.headers["Location"]

    def test_login_senha_errada_permanece_na_pagina(self, client, db, auth):
        """Login com senha incorreta → 200 (permanece no login)."""
        criar_usuario("atendente", login="maria", senha="correta")
        rv = auth.login_via_http("maria", "errada", follow=True)
        assert rv.status_code == 200
        assert b"Login ou senha incorretos" in rv.data or b"login" in rv.data.lower()

    def test_login_usuario_inexistente(self, client, db, auth):
        """Login com usuário que não existe → 200 (sem revelar qual campo errou)."""
        rv = auth.login_via_http("nao_existe", "qualquer", follow=True)
        assert rv.status_code == 200

    def test_login_usuario_inativo_bloqueado(self, client, db, auth):
        """Usuário inativo não consegue logar."""
        criar_usuario("atendente", login="inativo", senha="senha123", ativo=False)
        rv = auth.login_via_http("inativo", "senha123", follow=True)
        assert rv.status_code == 200
        assert b"/dashboard" not in rv.data

    def test_pagina_login_acessivel_sem_autenticacao(self, client, db):
        """GET /login é público — deve retornar 200."""
        rv = client.get("/login")
        assert rv.status_code == 200

    def test_formulario_login_tem_csrf_token(self, client, db):
        """O formulário de login deve conter o campo csrf_token."""
        rv = client.get("/login")
        assert b"csrf_token" in rv.data


class TestLogout:
    def test_logout_encerra_sessao(self, client, db, auth):
        """Após logout, acesso a área autenticada redireciona para login."""
        auth.login_como("atendente")
        rv = client.get("/dashboard", follow_redirects=False)
        assert rv.status_code == 200

        auth.logout()

        rv = client.get("/dashboard", follow_redirects=False)
        assert rv.status_code == 302
        assert "/login" in rv.headers["Location"]

    def test_logout_redireciona_para_login(self, client, db, auth):
        auth.login_como("atendente")
        rv = auth.logout()
        assert rv.status_code == 200  # follow_redirects=True no helper


class TestProtecaoRotas:
    def test_dashboard_sem_auth_redireciona(self, client, db):
        rv = client.get("/dashboard", follow_redirects=False)
        assert rv.status_code == 302
        assert "/login" in rv.headers["Location"]

    def test_pessoas_sem_auth_redireciona(self, client, db):
        rv = client.get("/pessoas/", follow_redirects=False)
        assert rv.status_code == 302

    def test_solicitacoes_sem_auth_redireciona(self, client, db):
        rv = client.get("/solicitacoes/", follow_redirects=False)
        assert rv.status_code == 302

    def test_atendimentos_sem_auth_redireciona(self, client, db):
        rv = client.get("/atendimentos/", follow_redirects=False)
        assert rv.status_code == 302

    def test_rota_autenticada_com_login_valido(self, client, db, auth):
        """Com login via session_transaction, rota autenticada retorna 200."""
        auth.login_como("atendente")
        rv = client.get("/pessoas/", follow_redirects=False)
        assert rv.status_code == 200
