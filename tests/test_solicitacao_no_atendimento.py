"""
test_solicitacao_no_atendimento.py — Solicitação criada de dentro do atendimento.

O serviço "Solicitação" segue o padrão do botão unificado, com um destino
diferente no ícone: em vez de abrir um portal externo, ele

    1. salva o atendimento como RASCUNHO (`POST /atendimentos/rascunho`), e
    2. abre `/solicitacoes/nova?atendimento_id=<id>` em nova aba.

Os dois passos usam a fundação que já existia: `upsert_atendimento` (Fase 1) e
o formulário de solicitação, que sempre exigiu `atendimento_id`. É por isso que
rascunho + finalizar dá UM atendimento — o mesmo registro, atualizado.

O aviso anti-fantasma cobre o caso de o atendente marcar "Solicitação" e não
preencher nenhuma. Ele avisa e **nunca bloqueia**: as duas saídas concluem o
atendimento.
"""
import re
from datetime import date

from app import db as _db
from app.models import (Atendimento, Servico, Solicitacao, Status,
                        TipoSolicitacao, ATENDIMENTO_RASCUNHO,
                        ATENDIMENTO_CONCLUIDO)
from tests.conftest import AtendimentoFactory, PessoaFactory, criar_usuario


def _servico_solicitacao():
    return Servico.query.filter(Servico.descricao.ilike("solicita%")).first()


def _outro_servico():
    """Um serviço 'todos' que não é o de Solicitação."""
    return (Servico.query
            .filter(Servico.aplicabilidade == "todos",
                    ~Servico.descricao.ilike("solicita%"))
            .first())


def _rascunho(client, pessoa, servicos, atendimento_id=None):
    """Simula o clique no ícone de Solicitação."""
    return client.post("/atendimentos/rascunho", json={
        "atendimento_id": atendimento_id,
        "id_pessoa":      pessoa.id,
        "tipo_efetivo":   "nao_mei",
        "observacao":     "",
        "servicos":       [{"id": s, "snap": "nao_mei", "forcado": ""}
                           for s in servicos],
    })


def _atendimento_alheio(pessoa, login, status=ATENDIMENTO_RASCUNHO):
    """Atendimento de OUTRO usuário — alvo dos testes de propriedade."""
    dono = criar_usuario("atendente", login=login)
    atend = AtendimentoFactory.create(id_pessoa=pessoa.id, id_usuario=dono.id,
                                      status=status)
    _db.session.commit()
    return dono, atend


def _html_iniciar(client, auth):
    auth.login_como("administrador")
    rv = client.get("/atendimentos/iniciar")
    assert rv.status_code == 200
    return rv.get_data(as_text=True)


# ── O ícone salva o rascunho ──────────────────────────────────────────────────

class TestRascunhoNoClique:
    """Clicar no ícone persiste o atendimento antes de abrir o formulário.

    A solicitação precisa de um atendimento que já exista para se vincular a
    ele — daí o rascunho nascer no clique, e não na finalização.
    """

    def test_cria_atendimento_com_status_rascunho(self, client, db, auth):
        auth.login_como("atendente")
        p = PessoaFactory.create()
        sol = _servico_solicitacao()

        rv = _rascunho(client, p, [sol.id])
        assert rv.status_code == 200

        atend = _db.session.get(Atendimento, rv.get_json()["atendimento_id"])
        assert atend is not None
        assert atend.status == ATENDIMENTO_RASCUNHO
        assert atend.rascunho is True
        assert atend.id_pessoa == p.id

    def test_resposta_traz_a_url_do_formulario_com_o_id(self, client, db, auth):
        """O front não monta a URL: ela vem pronta do servidor (url_for)."""
        auth.login_como("atendente")
        p = PessoaFactory.create()

        dados = _rascunho(client, p, [_servico_solicitacao().id]).get_json()
        assert dados["url_solicitacao"] == (
            f"/solicitacoes/nova?atendimento_id={dados['atendimento_id']}")

    def test_formulario_abre_com_o_atendimento_e_a_pessoa(self, client, db, auth):
        """O formulário recebe o atendimento_id e pré-preenche a pessoa."""
        auth.login_como("atendente")
        p = PessoaFactory.create()

        dados = _rascunho(client, p, [_servico_solicitacao().id]).get_json()
        rv = client.get(dados["url_solicitacao"])

        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert f'value="{dados["atendimento_id"]}"' in html
        assert p.nome_razao_social in html

    def test_grava_os_servicos_ja_marcados(self, client, db, auth):
        """O rascunho leva o estado do momento, não só a Solicitação."""
        auth.login_como("atendente")
        p = PessoaFactory.create()
        sol, outro = _servico_solicitacao(), _outro_servico()

        dados = _rascunho(client, p, [sol.id, outro.id]).get_json()
        atend = _db.session.get(Atendimento, dados["atendimento_id"])

        assert {a.id_servico for a in atend.servicos} == {sol.id, outro.id}

    def test_sem_pessoa_recusa(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.post("/atendimentos/rascunho", json={"servicos": []})
        assert rv.status_code == 400
        assert Atendimento.query.count() == 0

    def test_clicar_duas_vezes_nao_duplica(self, client, db, auth):
        """Reabrir o formulário reaproveita o mesmo rascunho."""
        auth.login_como("atendente")
        p = PessoaFactory.create()
        sol = _servico_solicitacao()

        primeiro = _rascunho(client, p, [sol.id]).get_json()["atendimento_id"]
        segundo = _rascunho(client, p, [sol.id],
                            atendimento_id=primeiro).get_json()["atendimento_id"]

        assert primeiro == segundo
        assert Atendimento.query.count() == 1

    def test_rascunho_de_outro_usuario_nao_e_sobrescrito(self, client, db, auth):
        """Id alheio não vira alvo: cria um novo em vez de invadir o dele."""
        p = PessoaFactory.create()
        outro, alheio = _atendimento_alheio(p, "dono_do_rascunho")
        alheio_id = alheio.id

        auth.login_como("atendente")
        novo = _rascunho(client, p, [_servico_solicitacao().id],
                         atendimento_id=alheio_id).get_json()["atendimento_id"]

        assert novo != alheio_id
        assert _db.session.get(Atendimento, alheio_id).id_usuario == outro.id


# ── O vínculo da solicitação ──────────────────────────────────────────────────

class TestVinculoDaSolicitacao:
    """A solicitação nasce presa ao atendimento — o formulário já fazia isso."""

    def _criar_pelo_formulario(self, client, usuario, pessoa, atendimento_id):
        return client.post("/solicitacoes/nova", data={
            "atendimento_id":      atendimento_id,
            "id_pessoa":           pessoa.id,
            "id_tipo_solicitacao": TipoSolicitacao.query.first().id,
            "id_status":           Status.query.first().id,
            "id_usuario":          usuario.id,
            "data_solicitacao":    date.today().isoformat(),
        }, follow_redirects=False)

    def test_solicitacao_fica_no_atendimento_correto(self, client, db, auth):
        u = auth.login_como("atendente")
        p = PessoaFactory.create()
        atend_id = _rascunho(client, p,
                             [_servico_solicitacao().id]).get_json()["atendimento_id"]

        rv = self._criar_pelo_formulario(client, u, p, atend_id)
        assert rv.status_code == 302

        sol = Solicitacao.query.one()
        assert sol.atendimento_id == atend_id
        assert sol.id_pessoa == p.id

    def test_finalizar_depois_mantem_o_vinculo(self, client, db, auth):
        """Concluir o atendimento não solta a solicitação já criada."""
        u = auth.login_como("atendente")
        p = PessoaFactory.create()
        serv = _servico_solicitacao()
        atend_id = _rascunho(client, p, [serv.id]).get_json()["atendimento_id"]
        self._criar_pelo_formulario(client, u, p, atend_id)

        client.post("/atendimentos/iniciar", data={
            "id_pessoa":      p.id,
            "atendimento_id": atend_id,
            "servicos":       [str(serv.id)],
            "tipo_efetivo":   "nao_mei",
        })

        sol = Solicitacao.query.one()
        assert sol.atendimento_id == atend_id
        assert _db.session.get(Atendimento, atend_id).concluido is True


# ── Rascunho + finalizar = UM atendimento ─────────────────────────────────────

class TestSemDuplicacao:
    """A garantia central: o upsert atualiza o rascunho em vez de criar outro."""

    def test_rascunho_e_finalizacao_dao_um_atendimento(self, client, db, auth):
        auth.login_como("atendente")
        p = PessoaFactory.create()
        serv = _servico_solicitacao()

        atend_id = _rascunho(client, p, [serv.id]).get_json()["atendimento_id"]
        assert Atendimento.query.count() == 1

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa":      p.id,
            "atendimento_id": atend_id,
            "servicos":       [str(serv.id)],
            "tipo_efetivo":   "nao_mei",
        })
        assert rv.status_code == 302

        assert Atendimento.query.count() == 1, "o rascunho virou um segundo atendimento"
        atend = _db.session.get(Atendimento, atend_id)
        assert atend.status == ATENDIMENTO_CONCLUIDO

    def test_finalizacao_atualiza_os_servicos_do_rascunho(self, client, db, auth):
        """O que vale é o que está marcado no fim, não o que foi ao rascunho."""
        auth.login_como("atendente")
        p = PessoaFactory.create()
        sol, outro = _servico_solicitacao(), _outro_servico()

        atend_id = _rascunho(client, p, [sol.id, outro.id]).get_json()["atendimento_id"]

        client.post("/atendimentos/iniciar", data={
            "id_pessoa":      p.id,
            "atendimento_id": atend_id,
            "servicos":       [str(outro.id)],       # desmarcou a Solicitação
            "tipo_efetivo":   "nao_mei",
        })

        atend = _db.session.get(Atendimento, atend_id)
        assert {a.id_servico for a in atend.servicos} == {outro.id}
        assert Atendimento.query.count() == 1

    def test_sem_rascunho_finalizar_cria_normalmente(self, client, db, auth):
        """O caminho de quem nunca clicou no ícone segue igual."""
        auth.login_como("atendente")
        p = PessoaFactory.create()

        client.post("/atendimentos/iniciar", data={
            "id_pessoa":    p.id,
            "servicos":     [str(_outro_servico().id)],
            "tipo_efetivo": "nao_mei",
        })

        assert Atendimento.query.count() == 1
        assert Atendimento.query.one().status == ATENDIMENTO_CONCLUIDO

    def test_id_alheio_no_form_nao_sobrescreve(self, client, db, auth):
        """Finalizar com id de outro usuário cria o seu, não invade o dele."""
        p = PessoaFactory.create()
        _, alheio = _atendimento_alheio(p, "dono_do_atendimento")
        alheio_id = alheio.id

        auth.login_como("atendente")
        client.post("/atendimentos/iniciar", data={
            "id_pessoa":      p.id,
            "atendimento_id": alheio_id,
            "servicos":       [str(_outro_servico().id)],
            "tipo_efetivo":   "nao_mei",
        })

        assert _db.session.get(Atendimento, alheio_id).status == ATENDIMENTO_RASCUNHO
        assert Atendimento.query.count() == 2


# ── Aviso anti-fantasma ───────────────────────────────────────────────────────

class TestAvisoAntiFantasma:
    """Solicitação marcada e nenhuma preenchida: avisa, nunca bloqueia."""

    def test_endpoint_diz_que_nao_ha_solicitacao(self, client, db, auth):
        auth.login_como("atendente")
        p = PessoaFactory.create()
        atend_id = _rascunho(client, p,
                             [_servico_solicitacao().id]).get_json()["atendimento_id"]

        rv = client.get(f"/atendimentos/{atend_id}/tem-solicitacao")
        assert rv.get_json() == {"tem": False}

    def test_endpoint_diz_que_ha_solicitacao(self, client, db, auth):
        u = auth.login_como("atendente")
        p = PessoaFactory.create()
        atend_id = _rascunho(client, p,
                             [_servico_solicitacao().id]).get_json()["atendimento_id"]
        client.post("/solicitacoes/nova", data={
            "atendimento_id":      atend_id,
            "id_pessoa":           p.id,
            "id_tipo_solicitacao": TipoSolicitacao.query.first().id,
            "id_status":           Status.query.first().id,
            "id_usuario":          u.id,
            "data_solicitacao":    date.today().isoformat(),
        })

        rv = client.get(f"/atendimentos/{atend_id}/tem-solicitacao")
        assert rv.get_json() == {"tem": True}

    def test_atendimento_de_outro_usuario_nao_vaza(self, client, db, auth):
        p = PessoaFactory.create()
        _, alheio = _atendimento_alheio(p, "dono_tem_solic",
                                        status=ATENDIMENTO_CONCLUIDO)

        auth.login_como("atendente")
        rv = client.get(f"/atendimentos/{alheio.id}/tem-solicitacao")
        assert rv.get_json() == {"tem": False}

    def test_modal_oferece_as_duas_saidas(self, client, db, auth):
        html = _html_iniciar(client, auth)
        assert 'id="modal-fantasma"' in html
        assert "Preencher agora" in html
        assert "Desmarcar e finalizar" in html

    def test_preencher_agora_reusa_a_acao_do_icone(self, client, db, auth):
        """Não há dois caminhos para abrir o formulário — é o mesmo."""
        html = _html_iniciar(client, auth)
        bloco = re.search(
            r"getElementById\('fantasma-preencher'\)\.addEventListener.*?\}\);",
            html, re.S).group(0)
        assert "abrirSolicitacao()" in bloco

    def test_desmarcar_e_finalizar_submete(self, client, db, auth):
        """A saída pela negativa conclui o atendimento, não trava nele."""
        html = _html_iniciar(client, auth)
        bloco = re.search(
            r"getElementById\('fantasma-desmarcar'\)\.addEventListener.*?\n\}\);",
            html, re.S).group(0)
        assert "chk.checked = false" in bloco
        assert "submeterFinalizacao()" in bloco

    def test_falha_na_checagem_nao_impede_finalizar(self, client, db, auth):
        """Se a consulta falhar, o aviso se cala — finalizar vem primeiro."""
        html = _html_iniciar(client, auth)
        bloco = re.search(r"function temSolicitacaoCriada\(\).*?\n\}", html, re.S).group(0)
        assert ".catch(() => true)" in bloco, (
            "no erro deve responder 'tem', para não abrir o modal e travar")

    def test_servidor_nao_bloqueia_solicitacao_fantasma(self, client, db, auth):
        """O aviso é da tela. O servidor grava o atendimento do mesmo jeito."""
        auth.login_como("atendente")
        p = PessoaFactory.create()

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa":    p.id,
            "servicos":     [str(_servico_solicitacao().id)],
            "tipo_efetivo": "nao_mei",
        })

        assert rv.status_code == 302
        assert Atendimento.query.one().status == ATENDIMENTO_CONCLUIDO
        assert Solicitacao.query.count() == 0


# ── O contrato da tela ────────────────────────────────────────────────────────

class TestContratoDaTela:
    """O que o HTML precisa entregar para o JS — e o que não pode quebrar."""

    def test_icone_da_solicitacao_e_uma_zona_separada(self, client, db, auth):
        html = _html_iniciar(client, auth)
        botoes = re.findall(
            r'<button[^>]*class="servico-solicitacao".*?</button>', html, re.S)

        assert len(botoes) == 1, "esperava exatamente um ícone de solicitação"
        b = botoes[0]
        assert 'type="button"' in b, "não pode submeter o formulário"
        assert "abrirSolicitacao()" in b
        assert "name=" not in b, "o ícone não vai no POST"
        assert "aria-label=" in b

    def test_solicitacao_nao_abre_portal_externo(self, client, db, auth):
        """O ícone dela tem destino interno — nada de data-url."""
        html = _html_iniciar(client, auth)
        botao = re.search(
            r'<button[^>]*class="servico-solicitacao".*?</button>', html, re.S).group(0)

        assert "data-url=" not in botao
        assert "abrirPortal" not in botao

    def test_portais_externos_seguem_intactos(self, client, db, auth):
        """Serviço com link_portal continua abrindo o portal pelo ícone."""
        html = _html_iniciar(client, auth)
        com_link = Servico.query.filter(
            Servico.ativo.is_(True), Servico.link_portal.isnot(None)).count()

        botoes = re.findall(
            r'<button[^>]*class="servico-portal".*?</button>', html, re.S)
        assert len(botoes) == com_link
        for b in botoes:
            assert "abrirPortal(this)" in b
            assert "data-url=" in b

    def test_ancora_da_solicitacao_no_dom(self, client, db, auth):
        """Um único item marcado — o JS o encontra por data-solicitacao."""
        html = _html_iniciar(client, auth)
        itens = re.findall(r'<div class="servico-item"[^>]*data-solicitacao="1"', html)
        assert len(itens) == 1

    def test_hidden_do_rascunho_vai_no_post(self, client, db, auth):
        """O id do rascunho é campo do formulário, não variável de JS."""
        html = _html_iniciar(client, auth)
        campo = re.search(r'<input[^>]*id="atendimento-rascunho"[^>]*>', html).group(0)

        assert 'name="atendimento_id"' in campo
        assert 'type="hidden"' in campo

    def test_seletores_do_js_existem_no_html(self, client, db, auth):
        """Os ids que o JS busca precisam estar na página.

        Mesma família do bug que quebrou a finalização em 2026-08-16: um
        seletor desatualizado não dá erro, só deixa de achar.
        """
        html = _html_iniciar(client, auth)
        for ident in ("atendimento-rascunho", "modal-fantasma",
                      "fantasma-preencher", "fantasma-desmarcar",
                      "tipo-efetivo", "id_canal"):
            assert f'id="{ident}"' in html, f"o JS busca #{ident}, que sumiu do HTML"

    def test_checkbox_continua_sendo_a_fonte_do_post(self, client, db, auth):
        """O ícone não substitui o checkbox — ele só abre o formulário."""
        html = _html_iniciar(client, auth)
        checks = re.findall(r'<input[^>]*name="servicos"[^>]*>', html)
        assert len(checks) == Servico.query.filter_by(ativo=True).count()
