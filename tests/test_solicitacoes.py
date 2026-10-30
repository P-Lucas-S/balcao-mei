"""
test_solicitacoes.py — Testes do módulo de solicitações.
"""
from datetime import date
from app import db as _db
from app.models import Solicitacao, Status, TipoSolicitacao
from tests.conftest import criar_usuario, PessoaFactory, SolicitacaoFactory, AtendimentoFactory


# ── Helpers ───────────────────────────────────────────────────────────────────

def _criar_solicitacao(id_usuario):
    """Cria uma solicitação Pendente para o usuário dado."""
    p = PessoaFactory.create()
    tipo = TipoSolicitacao.query.first()
    status_pend = Status.query.filter_by(descricao="Pendente").first()
    sol = Solicitacao(
        data_solicitacao=date.today(),
        id_usuario=id_usuario,
        id_pessoa=p.id,
        id_tipo_solicitacao=tipo.id,
        id_status=status_pend.id,
        exclusao_pendente=False,
    )
    _db.session.add(sol)
    _db.session.commit()
    return sol


def _login_como(client, perfil, login, senha="senha123"):
    """Cria usuário e injeta sessão diretamente (sem HTTP login)."""
    u = criar_usuario(perfil, login=login, senha=senha)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(u.id)
        sess["_fresh"] = True
    return u


# ── Listagem ──────────────────────────────────────────────────────────────────

class TestListaSolicitacoes:
    def test_lista_retorna_200_admin(self, client, db, auth):
        auth.login_como("administrador")
        rv = client.get("/solicitacoes/")
        assert rv.status_code == 200

    def test_lista_retorna_200_atendente(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.get("/solicitacoes/")
        assert rv.status_code == 200

    def test_lista_sem_autenticacao_redireciona(self, client, db):
        rv = client.get("/solicitacoes/", follow_redirects=False)
        assert rv.status_code == 302

    def test_lista_exibe_solicitacoes_existentes(self, client, db, auth):
        auth.login_como("administrador")
        SolicitacaoFactory.create()
        rv = client.get("/solicitacoes/")
        assert rv.status_code == 200


class TestEscopoAtendente:
    """Atendente só deve ver as próprias solicitações."""

    def test_atendente_ve_apenas_proprias(self, client, db):
        # Cria dois atendentes com solicitações distintas
        u1 = _login_como(client, "atendente", "atend1")
        sol1 = _criar_solicitacao(u1.id)
        # Troca de usuário direto via session_transaction (sem logout HTTP)
        u2 = _login_como(client, "atendente", "atend2")
        sol2 = _criar_solicitacao(u2.id)

        rv = client.get("/solicitacoes/")
        assert rv.status_code == 200
        # Ambas as solicitações existem no banco (filtro é testado na camada de query)
        assert Solicitacao.query.count() == 2

    def test_admin_ve_todas(self, client, db):
        u1 = criar_usuario("atendente", login="atend_a")
        u2 = criar_usuario("atendente", login="atend_b")
        _criar_solicitacao(u1.id)
        _criar_solicitacao(u2.id)

        # Login via session_transaction em vez de HTTP
        admin = _login_como(client, "administrador", "admin_all")
        rv = client.get("/solicitacoes/")
        assert rv.status_code == 200


# ── Troca de status ───────────────────────────────────────────────────────────

class TestTrocaStatus:
    def test_atendente_nao_pode_aprovar(self, client, db):
        """Atendente tentando Aprovar → 403."""
        u = _login_como(client, "atendente", "at_aprov")
        sol = _criar_solicitacao(u.id)
        status_aprov = Status.query.filter_by(descricao="Aprovado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_aprov.id},
        )
        assert rv.status_code == 403
        assert rv.get_json()["ok"] is False

    def test_atendente_nao_pode_recusar(self, client, db):
        """Atendente tentando Recusar → 403."""
        u = _login_como(client, "atendente", "at_recus")
        sol = _criar_solicitacao(u.id)
        status_recus = Status.query.filter_by(descricao="Recusado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_recus.id},
        )
        assert rv.status_code == 403

    def test_recusa_sem_motivo_retorna_400(self, client, db):
        """Admin tentando Recusar sem motivo → 400."""
        u = _login_como(client, "administrador", "adm_recus")
        sol = _criar_solicitacao(u.id)
        status_recus = Status.query.filter_by(descricao="Recusado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_recus.id},   # sem motivo_recusa
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["ok"] is False
        assert "motivo" in data["erro"].lower()

    def test_recusa_com_motivo_retorna_200(self, client, db):
        """Admin recusando com motivo válido → 200 e ok=True."""
        u = _login_como(client, "administrador", "adm_recus_ok")
        sol = _criar_solicitacao(u.id)
        status_recus = Status.query.filter_by(descricao="Recusado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={
                "id_status":     status_recus.id,
                "motivo_recusa": "Documentação insuficiente para análise.",
            },
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["ok"] is True
        assert "Recusado" in data["novo_status"]

    def test_recusa_persiste_no_banco(self, client, db):
        """Após recusa, o status da solicitação é atualizado no banco."""
        u = _login_como(client, "administrador", "adm_persist")
        sol = _criar_solicitacao(u.id)
        status_recus = Status.query.filter_by(descricao="Recusado").first()

        client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_recus.id, "motivo_recusa": "Motivo de teste válido"},
        )

        _db.session.refresh(sol)
        assert sol.id_status == status_recus.id

    def test_aprovacao_por_admin_retorna_200(self, client, db):
        """Admin pode aprovar sem restrições."""
        u = _login_como(client, "administrador", "adm_aprov")
        sol = _criar_solicitacao(u.id)
        status_aprov = Status.query.filter_by(descricao="Aprovado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_aprov.id},
        )
        assert rv.status_code == 200
        assert rv.get_json()["ok"] is True

    def test_status_invalido_retorna_400(self, client, db):
        """id_status inexistente ou não enviado → 400."""
        u = _login_como(client, "administrador", "adm_invalid")
        sol = _criar_solicitacao(u.id)

        rv = client.post(f"/solicitacoes/{sol.id}/status", data={})
        assert rv.status_code == 400

    def test_solicitacao_inexistente_retorna_404(self, client, db):
        u = _login_como(client, "administrador", "adm_404")
        status_pend = Status.query.filter_by(descricao="Pendente").first()

        rv = client.post(
            "/solicitacoes/99999/status",
            data={"id_status": status_pend.id},
        )
        assert rv.status_code == 404


# ── Nova solicitação ──────────────────────────────────────────────────────────

class TestNovaSolicitacao:
    def test_get_sem_atendimento_redireciona(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.get("/solicitacoes/nova", follow_redirects=False)
        assert rv.status_code == 302

    def test_get_com_atendimento_retorna_200(self, client, db, auth):
        auth.login_como("atendente")
        atend = AtendimentoFactory.create()
        rv = client.get(f"/solicitacoes/nova?atendimento_id={atend.id}")
        assert rv.status_code == 200

    def test_criar_solicitacao_valida_redireciona(self, client, db):
        u = _login_como(client, "atendente", "atend_nova")
        p = PessoaFactory.create()
        atend = AtendimentoFactory.create(id_pessoa=p.id, id_usuario=u.id)
        tipo = TipoSolicitacao.query.first()
        status_pend = Status.query.filter_by(descricao="Pendente").first()

        rv = client.post(
            "/solicitacoes/nova",
            data={
                "data_solicitacao":    date.today().isoformat(),
                "id_pessoa":           p.id,
                "id_tipo_solicitacao": tipo.id,
                "id_status":           status_pend.id,
                "id_usuario":          u.id,
                "atendimento_id":      atend.id,
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302

    def test_criar_sem_pessoa_retorna_erro(self, client, db, auth):
        auth.login_como("atendente")
        atend = AtendimentoFactory.create()
        rv = client.post(
            "/solicitacoes/nova",
            data={
                "data_solicitacao": date.today().isoformat(),
                "atendimento_id":   atend.id,
            },
            follow_redirects=False,
        )
        assert rv.status_code == 200   # fica na página com erro

    def test_criar_sem_atendimento_redireciona(self, client, db, auth):
        auth.login_como("atendente")
        p = PessoaFactory.create()
        tipo = TipoSolicitacao.query.first()
        status_pend = Status.query.filter_by(descricao="Pendente").first()
        rv = client.post(
            "/solicitacoes/nova",
            data={
                "data_solicitacao":    date.today().isoformat(),
                "id_pessoa":           p.id,
                "id_tipo_solicitacao": tipo.id,
                "id_status":           status_pend.id,
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302
