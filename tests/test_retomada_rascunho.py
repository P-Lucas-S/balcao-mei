"""
test_retomada_rascunho.py — Selo "Em aberto" e retomada do atendimento.

Um rascunho não some: ele aparece na lista de atendimentos com um selo
**neutro** ("Em aberto", não "incompleto"), e o selo é o caminho de volta.
Clicar nele reabre a tela guiada com o que já estava marcado.

A tela guiada sempre soube começar do zero; aqui ela aprende a continuar. Não
é um segundo caminho de criação: ao concluir, o mesmo `upsert_atendimento`
ATUALIZA aquele registro.

O escopo é o mesmo de sempre — `_no_escopo`, o que já governa a listagem e a
edição. Um atendente não retoma rascunho de outro.
"""
import re
from datetime import date

from app import db as _db
from app.models import (Atendimento, Servico, Solicitacao, Status,
                        TipoSolicitacao, ATENDIMENTO_CONCLUIDO,
                        ATENDIMENTO_RASCUNHO)
from tests.conftest import AtendimentoFactory, PessoaFactory, criar_usuario


def _servico(aplic="todos", excluir=None):
    q = Servico.query.filter_by(aplicabilidade=aplic)
    if excluir:
        q = q.filter(Servico.id != excluir)
    return q.first()


def _rascunho_de(usuario, pessoa, servicos=(), **kw):
    """Um rascunho já gravado, como o ícone de Solicitação deixaria."""
    from app.routes.atendimentos import upsert_atendimento

    atend = upsert_atendimento(
        id_pessoa=pessoa.id, id_usuario=usuario.id,
        servicos_ids=[s.id for s in servicos],
        status=ATENDIMENTO_RASCUNHO, **kw)
    _db.session.commit()
    return atend


# ── O selo na lista ───────────────────────────────────────────────────────────

class TestSeloNaLista:
    """Neutro, clicável, e só onde faz sentido."""

    def _lista(self, client):
        rv = client.get("/atendimentos/?data_de=&data_ate=&q_pessoa=&status=")
        assert rv.status_code == 200
        return rv.get_data(as_text=True)

    def test_selo_aparece_no_rascunho(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        r = _rascunho_de(u, p, [_servico()])

        html = self._lista(client)
        assert "selo-em-aberto" in html
        assert f"retomar={r.id}" in html

    def test_selo_nao_aparece_no_concluido(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        AtendimentoFactory.create(id_pessoa=p.id, id_usuario=u.id,
                                  status=ATENDIMENTO_CONCLUIDO)
        _db.session.commit()

        assert "selo-em-aberto" not in self._lista(client)

    def test_selo_leva_a_retomada(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        r = _rascunho_de(u, p, [_servico()])

        html = self._lista(client)
        href = re.search(r'class="selo-em-aberto"\s+href="([^"]+)"', html)
        assert href, "o selo tem de ser um link, não só um rótulo"
        assert href.group(1).endswith(f"/atendimentos/iniciar?retomar={r.id}")

    def test_selo_e_neutro_nao_erro(self, client, db, auth):
        """Trabalho em andamento não é defeito — nada de linguagem de erro."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        _rascunho_de(u, p, [_servico()])

        html = self._lista(client)
        selo = re.search(r'<a class="selo-em-aberto".*?</a>', html, re.S).group(0)
        assert "Em aberto" in selo
        for proibida in ("incompleto", "erro", "pendência", "danger", "perigo"):
            assert proibida not in selo.lower()

    def test_atendente_nao_ve_rascunho_de_outro(self, client, db, auth):
        """O selo herda o escopo da listagem — não cria visibilidade nova."""
        p = PessoaFactory.create()
        outro = criar_usuario("atendente", login="dono_do_rascunho_lista")
        alheio = _rascunho_de(outro, p, [_servico()])

        auth.login_como("atendente")
        html = self._lista(client)
        assert f"retomar={alheio.id}" not in html
        assert "selo-em-aberto" not in html

    def test_filtro_por_status_isola_os_rascunhos(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        r = _rascunho_de(u, p, [_servico()])
        concluido = AtendimentoFactory.create(id_pessoa=p.id, id_usuario=u.id,
                                              status=ATENDIMENTO_CONCLUIDO)
        _db.session.commit()

        html = client.get("/atendimentos/?status=rascunho").get_data(as_text=True)
        assert f"retomar={r.id}" in html
        assert f"/atendimentos/{concluido.id}/editar" not in html


# ── A retomada carrega o estado ───────────────────────────────────────────────

class TestRetomadaCarregaOEstado:
    """Continuar de onde parou: pessoa, serviços, canal e observação."""

    def test_reabre_com_a_pessoa_e_os_servicos_marcados(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s1 = _servico()
        s2 = _servico(excluir=s1.id)
        r = _rascunho_de(u, p, [s1, s2], observacao="continuar isto")

        html = client.get(f"/atendimentos/iniciar?retomar={r.id}").get_data(as_text=True)

        assert p.nome_razao_social in html
        assert f'value="{r.id}"' in html, "o hidden do rascunho tem de vir preenchido"
        assert "continuar isto" in html
        for s in (s1, s2):
            item = re.search(
                rf'<input[^>]*id="chk-{s.id}"[^>]*>', html).group(0)
            assert "checked" in item, f"o serviço {s.descricao} devia vir marcado"

    def test_servico_nao_marcado_continua_desmarcado(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s1 = _servico()
        s2 = _servico(excluir=s1.id)
        r = _rascunho_de(u, p, [s1])

        html = client.get(f"/atendimentos/iniciar?retomar={r.id}").get_data(as_text=True)
        item = re.search(rf'<input[^>]*id="chk-{s2.id}"[^>]*>', html).group(0)
        assert "checked" not in item

    def test_contexto_do_servico_volta_como_estava(self, client, db, auth):
        """Sem o `forcado`, a revalidação recusaria o serviço na conclusão."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s = _servico("mei")           # fora do perfil de uma pessoa nao_mei
        r = _rascunho_de(u, p, [s], contexto={s.id: {'tipo_efetivo': 'nao_mei',
                                                     'forcado': True}})

        html = client.get(f"/atendimentos/iniciar?retomar={r.id}").get_data(as_text=True)
        forcado = re.search(rf'<input[^>]*name="forcado_{s.id}"[^>]*>', html, re.S).group(0)
        snap = re.search(rf'<input[^>]*name="snap_{s.id}"[^>]*>', html, re.S).group(0)

        assert 'value="1"' in forcado
        assert 'value="nao_mei"' in snap

    def test_avisa_que_esta_retomando(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        r = _rascunho_de(u, p, [_servico()])

        html = client.get(f"/atendimentos/iniciar?retomar={r.id}").get_data(as_text=True)
        assert f"#{r.id}" in html
        assert "Concluir Atendimento" in html, (
            "o botão deve dizer que conclui, não que inicia")

    def test_iniciar_do_zero_segue_igual(self, client, db, auth):
        """A retomada é um modo a mais, não uma troca de comportamento."""
        auth.login_como("administrador")
        html = client.get("/atendimentos/iniciar").get_data(as_text=True)

        assert 'id="atendimento-rascunho"' in html
        assert 'value=""' in html
        assert "Finalizar Atendimento" in html
        assert "Retomando o atendimento" not in html
        assert 'checked' not in re.search(
            r'<div class="servicos-grid">.*?</div>\s*</div>', html, re.S).group(0)


# ── A conclusão atualiza, não duplica ─────────────────────────────────────────

class TestRetomadaConclui:
    """O upsert de novo: retomar e concluir dá UM atendimento."""

    def _concluir(self, client, pessoa, atend_id, servicos, **extra):
        dados = {
            "id_pessoa":      pessoa.id,
            "atendimento_id": atend_id,
            "servicos":       [str(s.id) for s in servicos],
            "tipo_efetivo":   "nao_mei",
        }
        dados.update(extra)
        return client.post("/atendimentos/iniciar", data=dados)

    def test_concluir_atualiza_o_mesmo_atendimento(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s = _servico()
        r = _rascunho_de(u, p, [s])
        assert Atendimento.query.count() == 1

        rv = self._concluir(client, p, r.id, [s])
        assert rv.status_code == 302

        assert Atendimento.query.count() == 1, "a retomada criou um segundo registro"
        assert _db.session.get(Atendimento, r.id).status == ATENDIMENTO_CONCLUIDO

    def test_concluir_grava_o_que_mudou_na_retomada(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s1 = _servico()
        s2 = _servico(excluir=s1.id)
        r = _rascunho_de(u, p, [s1], observacao="rascunho")

        self._concluir(client, p, r.id, [s1, s2], observacao="revisado")

        atend = _db.session.get(Atendimento, r.id)
        assert {a.id_servico for a in atend.servicos} == {s1.id, s2.id}
        assert atend.observacao == "revisado"
        assert Atendimento.query.count() == 1

    def test_solicitacao_vinculada_sobrevive_a_conclusao(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s = _servico()
        r = _rascunho_de(u, p, [s])
        client.post("/solicitacoes/nova", data={
            "atendimento_id":      r.id,
            "id_pessoa":           p.id,
            "id_tipo_solicitacao": TipoSolicitacao.query.first().id,
            "id_status":           Status.query.first().id,
            "id_usuario":          u.id,
            "data_solicitacao":    date.today().isoformat(),
        })

        self._concluir(client, p, r.id, [s])

        sol = Solicitacao.query.one()
        assert sol.atendimento_id == r.id
        assert _db.session.get(Atendimento, r.id).concluido is True

    def test_rascunho_concluido_passa_a_contar_na_metrica(self, client, db, auth):
        """O outro lado da moeda: concluído, ele entra no número oficial."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        s = _servico()
        r = _rascunho_de(u, p, [s])

        def _nums():
            html = client.get("/dashboard").get_data(as_text=True)
            html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
            html = re.sub(r'name="csrf_token"[^>]*', "", html)
            return re.findall(r"\d+", html)

        antes = _nums()
        self._concluir(client, p, r.id, [s])
        assert _nums() != antes, "concluído, o atendimento tem de contar"


# ── Escopo: rascunho alheio não é retomável ───────────────────────────────────

class TestEscopoDaRetomada:
    """Mesma proteção da edição — o id na URL não basta."""

    def test_atendente_nao_retoma_rascunho_de_outro(self, client, db, auth):
        p = PessoaFactory.create()
        outro = criar_usuario("atendente", login="dono_retomada")
        alheio = _rascunho_de(outro, p, [_servico()])

        auth.login_como("atendente")
        rv = client.get(f"/atendimentos/iniciar?retomar={alheio.id}")

        assert rv.status_code == 302
        assert rv.headers["Location"].endswith("/atendimentos/")

    def test_admin_retoma_qualquer_um(self, client, db, auth):
        p = PessoaFactory.create()
        outro = criar_usuario("atendente", login="dono_retomada_admin")
        alheio = _rascunho_de(outro, p, [_servico()])

        auth.login_como("administrador")
        assert client.get(
            f"/atendimentos/iniciar?retomar={alheio.id}").status_code == 200

    def test_concluido_nao_e_retomavel(self, client, db, auth):
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        a = AtendimentoFactory.create(id_pessoa=p.id, id_usuario=u.id,
                                      status=ATENDIMENTO_CONCLUIDO)
        _db.session.commit()

        rv = client.get(f"/atendimentos/iniciar?retomar={a.id}")
        assert rv.status_code == 302
        assert f"/atendimentos/{a.id}" in rv.headers["Location"]

    def test_id_inexistente_da_404(self, client, db, auth):
        auth.login_como("administrador")
        assert client.get("/atendimentos/iniciar?retomar=99999").status_code == 404

    def test_post_com_rascunho_alheio_nao_sobrescreve(self, client, db, auth):
        """A trava do POST é a mesma de antes — a retomada não a afrouxou."""
        p = PessoaFactory.create()
        outro = criar_usuario("atendente", login="dono_post_retomada")
        alheio = _rascunho_de(outro, p, [_servico()])

        auth.login_como("atendente")
        client.post("/atendimentos/iniciar", data={
            "id_pessoa":      p.id,
            "atendimento_id": alheio.id,
            "servicos":       [str(_servico().id)],
            "tipo_efetivo":   "nao_mei",
        })

        assert _db.session.get(Atendimento, alheio.id).status == ATENDIMENTO_RASCUNHO
        assert Atendimento.query.count() == 2
