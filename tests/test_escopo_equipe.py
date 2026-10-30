"""
test_escopo_equipe.py — O escopo de EQUIPE, que nunca teve teste.

Até 2026-08-29 a suíte testava só o **guard de perfil** (entra / não entra).
O `supervisor_id` — o vínculo que define a equipe — não aparecia em teste
nenhum, apesar de governar cinco telas. E a feature do Foco vai se apoiar
exatamente nele para distribuir atendimentos entre os ADs.

Aqui se testa a regra em si, em `app/escopo.py`:

    administrador  ->  tudo
    supervisor     ->  a própria equipe (supervisor_id) + ele mesmo
    atendente      ->  só ele mesmo

Dois ramos são cobertos de propósito, porque são os que mais erram:
**supervisor COM equipe** e **supervisor SEM equipe** (o fallback legado,
que dava o sistema inteiro a quem ainda não configurou a equipe, foi
removido neste ciclo).
"""
from datetime import date

from app import db as _db
from app.escopo import ids_da_equipe, no_escopo
from app.models import (Solicitacao, Status, TipoSolicitacao,
                        ATENDIMENTO_CONCLUIDO)
from tests.conftest import (AtendimentoFactory, PessoaFactory, criar_usuario)


# ── Montagem: duas equipes distintas + um avulso ──────────────────────────────

class Equipes:
    """Duas equipes completas, para provar que uma não enxerga a outra."""

    def __init__(self):
        self.sup_a = criar_usuario("supervisor", login="sup_a")
        self.sup_b = criar_usuario("supervisor", login="sup_b")
        self.sup_vazio = criar_usuario("supervisor", login="sup_sem_equipe")

        self.at_a1 = criar_usuario("atendente", login="at_a1")
        self.at_a2 = criar_usuario("atendente", login="at_a2")
        self.at_b1 = criar_usuario("atendente", login="at_b1")
        self.avulso = criar_usuario("atendente", login="at_avulso")

        for at in (self.at_a1, self.at_a2):
            at.supervisor_id = self.sup_a.id
        self.at_b1.supervisor_id = self.sup_b.id
        # `avulso` fica sem supervisor de propósito

        # `criar_usuario` dá o MESMO nome a todos do mesmo perfil
        # ("Teste Atendente"), então nome não distingue ninguém. Os testes de
        # relatório procuram o nome na página — precisam de nomes únicos.
        for u in (self.sup_a, self.sup_b, self.sup_vazio,
                  self.at_a1, self.at_a2, self.at_b1, self.avulso):
            u.nome = f"Fulano {u.login}"
        _db.session.commit()

        self.pessoa = PessoaFactory.create()
        _db.session.commit()

        # Um atendimento e uma solicitação para cada usuário
        self.atend = {}
        self.solic = {}
        for u in (self.sup_a, self.sup_b, self.sup_vazio,
                  self.at_a1, self.at_a2, self.at_b1, self.avulso):
            self.atend[u.login] = self._atendimento(u)
            self.solic[u.login] = self._solicitacao(u)
        _db.session.commit()

    def _atendimento(self, usuario):
        return AtendimentoFactory.create(
            id_pessoa=self.pessoa.id, id_usuario=usuario.id,
            status=ATENDIMENTO_CONCLUIDO)

    def _solicitacao(self, usuario):
        s = Solicitacao(
            data_solicitacao=date.today(),
            id_usuario=usuario.id,
            id_pessoa=self.pessoa.id,
            id_tipo_solicitacao=TipoSolicitacao.query.first().id,
            id_status=Status.query.first().id,
            exclusao_pendente=False,
        )
        _db.session.add(s)
        return s


def _entrar(client, usuario):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(usuario.id)
        sess["_fresh"] = True


def _lista_atendimentos(client):
    rv = client.get("/atendimentos/?data_de=&data_ate=&q_pessoa=")
    assert rv.status_code == 200
    return rv.get_data(as_text=True)


def _lista_solicitacoes(client):
    rv = client.get("/solicitacoes/")
    assert rv.status_code == 200
    return rv.get_data(as_text=True)


# ── A regra, isolada ──────────────────────────────────────────────────────────

class TestRegraDeEquipe:
    """`ids_da_equipe` é a única definição de equipe no sistema."""

    def test_admin_nao_tem_filtro(self, client, db, auth):
        Equipes()
        adm = criar_usuario("administrador", login="adm_escopo")
        assert ids_da_equipe(adm) is None, (
            "None significa SEM FILTRO — não pode virar lista vazia")

    def test_supervisor_com_equipe(self, client, db, auth):
        eq = Equipes()
        ids = ids_da_equipe(eq.sup_a)
        assert set(ids) == {eq.sup_a.id, eq.at_a1.id, eq.at_a2.id}
        assert eq.at_b1.id not in ids, "a equipe do outro supervisor vazou"
        assert eq.avulso.id not in ids, (
            "atendente sem supervisor_id não pertence a equipe nenhuma — "
            "era isto que a regra antiga fazia errado")

    def test_supervisor_sem_equipe_ve_so_a_si(self, client, db, auth):
        """O fallback legado dava o sistema inteiro a quem não tem equipe."""
        eq = Equipes()
        assert ids_da_equipe(eq.sup_vazio) == [eq.sup_vazio.id]

    def test_atendente_ve_so_a_si(self, client, db, auth):
        eq = Equipes()
        assert ids_da_equipe(eq.at_a1) == [eq.at_a1.id]

    def test_no_escopo_espelha_a_lista(self, client, db, auth):
        """Registro a registro tem de dar a mesma resposta que a query."""
        eq = Equipes()
        assert no_escopo(eq.atend["at_a1"], eq.sup_a) is True
        assert no_escopo(eq.atend["at_b1"], eq.sup_a) is False
        assert no_escopo(eq.atend["sup_a"], eq.sup_a) is True
        assert no_escopo(eq.atend["at_a1"], eq.at_a2) is False

    def test_exclusao_pendente_sai_para_nao_admin(self, client, db, auth):
        eq = Equipes()
        alvo = eq.atend["at_a1"]
        alvo.exclusao_pendente = True
        _db.session.commit()

        assert no_escopo(alvo, eq.sup_a) is False
        adm = criar_usuario("administrador", login="adm_pendente")
        assert no_escopo(alvo, adm) is True


# ── A listagem de atendimentos ────────────────────────────────────────────────

class TestListaDeAtendimentos:

    def test_supervisor_ve_a_propria_equipe_e_nao_a_outra(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        html = _lista_atendimentos(client)

        for login in ("at_a1", "at_a2", "sup_a"):
            assert f"/atendimentos/{eq.atend[login].id}" in html, (
                f"o supervisor devia ver o atendimento de {login}")
        for login in ("at_b1", "sup_b", "at_avulso"):
            assert f"/atendimentos/{eq.atend[login].id}" not in html, (
                f"o atendimento de {login} vazou para outro supervisor")

    def test_supervisor_sem_equipe_nao_ve_os_outros(self, client, db, auth):
        """Antes do fallback ser removido, este supervisor via TUDO."""
        eq = Equipes()
        _entrar(client, eq.sup_vazio)
        html = _lista_atendimentos(client)

        for login in ("at_a1", "at_b1", "sup_a", "sup_b", "at_avulso"):
            assert f"/atendimentos/{eq.atend[login].id}" not in html, (
                "o fallback legado voltou: supervisor sem equipe vendo o "
                f"atendimento de {login}")

    def test_atendente_ve_so_os_proprios(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        html = _lista_atendimentos(client)

        assert f"/atendimentos/{eq.atend['at_a1'].id}" in html
        for login in ("at_a2", "sup_a", "at_b1"):
            assert f"/atendimentos/{eq.atend[login].id}" not in html, (
                f"o atendente viu o atendimento de {login} — nem o do colega "
                "de equipe é dele")

    def test_admin_ve_todos(self, client, db, auth):
        eq = Equipes()
        _entrar(client, criar_usuario("administrador", login="adm_lista"))
        html = _lista_atendimentos(client)

        for login in eq.atend:
            assert f"/atendimentos/{eq.atend[login].id}" in html


# ── A listagem de solicitações ────────────────────────────────────────────────

class TestListaDeSolicitacoes:

    def test_supervisor_ve_a_propria_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        html = _lista_solicitacoes(client)

        for login in ("at_a1", "at_a2", "sup_a"):
            assert f"/solicitacoes/{eq.solic[login].id}" in html
        for login in ("at_b1", "sup_b"):
            assert f"/solicitacoes/{eq.solic[login].id}" not in html

    def test_supervisor_sem_equipe_ve_so_as_proprias(self, client, db, auth):
        """Ele não fica cego para o próprio trabalho — só para o dos outros."""
        eq = Equipes()
        _entrar(client, eq.sup_vazio)
        html = _lista_solicitacoes(client)

        assert f"/solicitacoes/{eq.solic['sup_sem_equipe'].id}" in html
        for login in ("at_a1", "at_b1", "sup_a"):
            assert f"/solicitacoes/{eq.solic[login].id}" not in html

    def test_atendente_ve_so_as_proprias(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        html = _lista_solicitacoes(client)

        assert f"/solicitacoes/{eq.solic['at_a1'].id}" in html
        assert f"/solicitacoes/{eq.solic['at_a2'].id}" not in html


# ── Leitura por id na URL — o buraco fechado neste ciclo ──────────────────────

class TestLeituraRespeitaEscopo:
    """Antes de 2026-08-29, `detalhe` e `sucesso` não checavam nada.

    Um atendente digitava o id na URL e lia o atendimento de qualquer
    colega, observação inclusive. A lista escondia; a URL entregava.
    """

    def test_atendente_nao_le_atendimento_de_colega(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        rv = client.get(f"/atendimentos/{eq.atend['at_a2'].id}")

        assert rv.status_code == 302, "ler por id tem de respeitar o escopo"
        assert "/atendimentos/" in rv.headers["Location"]

    def test_atendente_le_o_proprio(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        assert client.get(
            f"/atendimentos/{eq.atend['at_a1'].id}").status_code == 200

    def test_supervisor_le_o_da_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        assert client.get(
            f"/atendimentos/{eq.atend['at_a1'].id}").status_code == 200

    def test_supervisor_nao_le_o_de_outra_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        assert client.get(
            f"/atendimentos/{eq.atend['at_b1'].id}").status_code == 302

    def test_tela_de_sucesso_tambem_escopada(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        assert client.get(
            f"/atendimentos/{eq.atend['at_a2'].id}/sucesso").status_code == 302
        assert client.get(
            f"/atendimentos/{eq.atend['at_a1'].id}/sucesso").status_code == 200

    def test_solicitacao_de_colega_barrada(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.at_a1)
        assert client.get(
            f"/solicitacoes/{eq.solic['at_a2'].id}").status_code == 302
        assert client.get(
            f"/solicitacoes/{eq.solic['at_a1'].id}").status_code == 200

    def test_admin_le_qualquer_um(self, client, db, auth):
        eq = Equipes()
        _entrar(client, criar_usuario("administrador", login="adm_leitura"))
        assert client.get(
            f"/atendimentos/{eq.atend['at_b1'].id}").status_code == 200
        assert client.get(
            f"/solicitacoes/{eq.solic['at_b1'].id}").status_code == 200

    def test_edicao_continua_direta_para_o_dono(self, client, db, auth):
        """Escopar a leitura não transformou edição em pedido de aprovação."""
        eq = Equipes()
        _entrar(client, eq.at_a1)
        assert client.get(
            f"/atendimentos/{eq.atend['at_a1'].id}/editar").status_code == 200


# ── A regra unificada em relatórios e dashboard ───────────────────────────────

class TestRegraUnicaEmRelatoriosEDashboard:
    """Antes deste ciclo, relatórios e dashboard usavam OUTRA definição de
    equipe: todos os usuários de perfil atendente, vinculados ou não. Um
    supervisor via no relatório gente que não via na lista de atendimentos.
    """

    def test_dashboard_conta_so_a_propria_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        html = client.get("/dashboard").get_data(as_text=True)

        # A equipe A tem 3 atendimentos (sup_a, at_a1, at_a2) — os demais,
        # de outra equipe e do avulso, não podem entrar na conta.
        assert f"/atendimentos/{eq.atend['at_a1'].id}" in html
        assert f"/atendimentos/{eq.atend['at_b1'].id}" not in html
        assert f"/atendimentos/{eq.atend['at_avulso'].id}" not in html

    def test_relatorio_de_desempenho_lista_so_a_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)
        html = client.get("/relatorios/atendimentos").get_data(as_text=True)

        assert eq.at_a1.nome in html
        assert eq.at_b1.nome not in html, (
            "o relatório mostrou atendente de outra equipe — a regra "
            "divergente voltou")
        assert eq.avulso.nome not in html

    def test_desempenho_individual_barra_fora_da_equipe(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_a)

        assert client.get(
            f"/relatorios/desempenho/{eq.at_a1.id}").status_code == 200
        rv = client.get(f"/relatorios/desempenho/{eq.at_b1.id}")
        assert rv.status_code == 302, (
            "supervisor abriu o desempenho de quem não é da equipe dele")

    def test_supervisor_sem_equipe_nao_ve_atendente_algum(self, client, db, auth):
        eq = Equipes()
        _entrar(client, eq.sup_vazio)
        html = client.get("/relatorios/atendimentos").get_data(as_text=True)

        for u in (eq.at_a1, eq.at_b1, eq.avulso):
            assert u.nome not in html

    def test_atendente_nao_entra_no_relatorio(self, client, db, auth):
        """O guard de perfil continua valendo — escopo não o substitui."""
        eq = Equipes()
        _entrar(client, eq.at_a1)
        assert client.get("/relatorios/atendimentos").status_code == 302


# ── A mesma regra nas duas pontas ─────────────────────────────────────────────

class TestListaEDetalheNaoDivergem:
    """O que a lista esconde, o detalhe recusa. É a invariante que o buraco
    de leitura violava: dois lugares, duas respostas para a mesma pergunta.
    """

    def test_o_que_some_da_lista_da_302_no_detalhe(self, client, db, auth):
        eq = Equipes()
        for usuario in (eq.at_a1, eq.sup_a, eq.sup_vazio):
            _entrar(client, usuario)
            html = _lista_atendimentos(client)

            for login, atend in eq.atend.items():
                visivel_na_lista = f"/atendimentos/{atend.id}" in html
                status = client.get(f"/atendimentos/{atend.id}").status_code
                assert visivel_na_lista == (status == 200), (
                    f"{usuario.login} x atendimento de {login}: lista diz "
                    f"{visivel_na_lista}, detalhe responde {status}")
