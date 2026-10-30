"""
test_atendimento_status.py — Fundação da mudança no fluxo de atendimento.

Fase 1: o campo `status` (rascunho/concluido) e o caminho único de
persistência `upsert_atendimento`. Nada aqui exercita a interface — o upsert
ainda não está ligado a ela de propósito.
"""
from app import db as _db
from app.models import (Atendimento, AtendimentoServico, Servico,
                        ATENDIMENTO_CONCLUIDO, ATENDIMENTO_RASCUNHO)
from app.routes.atendimentos import upsert_atendimento
from tests.conftest import AtendimentoFactory, PessoaFactory, criar_usuario

import pytest


def _tipos(n=2):
    """Ids de n serviços aplicáveis a QUALQUER pessoa (aplicabilidade 'todos').

    Desde a filtragem por tipo efetivo, o servidor recusa serviço fora da
    aplicabilidade. Estes testes exercitam a finalização, não a filtragem —
    então usam serviços que valem para qualquer tipo de pessoa.
    """
    todos = (Servico.query.filter_by(aplicabilidade='todos')
             .order_by(Servico.id).limit(n).all())
    return [t.id for t in todos]


def _servico_por_aplicabilidade(aplic):
    return Servico.query.filter_by(aplicabilidade=aplic).first()


# ── O campo status ────────────────────────────────────────────────────────────

class TestCampoStatus:

    def test_default_e_concluido(self, client, db, auth):
        """Atendimento criado sem status explícito nasce 'concluido'."""
        atend = AtendimentoFactory.create()
        _db.session.commit()
        assert atend.status == ATENDIMENTO_CONCLUIDO

    def test_propriedades_de_conveniencia(self, client, db, auth):
        atend = AtendimentoFactory.create()
        _db.session.commit()
        assert atend.concluido is True
        assert atend.rascunho is False

        atend.status = ATENDIMENTO_RASCUNHO
        _db.session.commit()
        assert atend.rascunho is True
        assert atend.concluido is False

    def test_fluxo_atual_da_tela_produz_concluido(self, client, db, auth):
        """O POST de /atendimentos/iniciar continua criando atendimento
        finalizado — comportamento idêntico ao de antes da Fase 1."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        tipos = _tipos(1)
        _db.session.commit()

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "servicos": [str(tipos[0])],
            "observacao": "via tela",
        }, follow_redirects=False)

        assert rv.status_code == 302
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.status == ATENDIMENTO_CONCLUIDO
        assert atend.id_usuario == u.id

    def test_fluxo_novo_tambem_produz_concluido(self, client, db, auth):
        """O formulário completo (/atendimentos/novo) idem."""
        auth.login_como("administrador")
        p = PessoaFactory.create()
        responsavel = criar_usuario("atendente", login="dono_novo")
        tipos = _tipos(1)
        _db.session.commit()

        rv = client.post("/atendimentos/novo", data={
            "id_pessoa": p.id,
            "id_usuario": responsavel.id,
            "data_atendimento": "2026-08-05",
            "hora_atendimento": "09:00",
            "servicos": [str(tipos[0])],
        }, follow_redirects=False)

        assert rv.status_code == 302, "form deve passar na validação"
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.status == ATENDIMENTO_CONCLUIDO


# ── upsert_atendimento ────────────────────────────────────────────────────────

class TestUpsertAtendimento:

    def _contexto(self):
        p = PessoaFactory.create()
        u = criar_usuario("atendente", login=f"upsert_{PessoaFactory._meta.model.query.count()}")
        _db.session.commit()
        return p, u

    def test_cria_quando_nao_ha_id(self, client, db, auth):
        p, u = self._contexto()
        tipos = _tipos(2)

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=tipos,
        )
        _db.session.commit()

        assert atend.id is not None
        assert atend.id_pessoa == p.id
        assert atend.id_usuario == u.id
        assert atend.status == ATENDIMENTO_CONCLUIDO
        assert {t.id_servico for t in atend.servicos} == set(tipos)

    def test_cria_como_rascunho_quando_pedido(self, client, db, auth):
        p, u = self._contexto()

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=_tipos(1),
            status=ATENDIMENTO_RASCUNHO,
        )
        _db.session.commit()

        assert atend.status == ATENDIMENTO_RASCUNHO
        assert atend.rascunho is True

    def test_atualiza_quando_ha_id(self, client, db, auth):
        """Com id, altera o registro existente em vez de criar outro."""
        p, u = self._contexto()
        tipos = _tipos(2)

        criado = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=[tipos[0]],
            status=ATENDIMENTO_RASCUNHO, observacao="primeiro",
        )
        _db.session.commit()
        atend_id = criado.id
        total_antes = Atendimento.query.count()

        atualizado = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=tipos,
            status=ATENDIMENTO_CONCLUIDO, observacao="segundo",
            atendimento_id=atend_id,
        )
        _db.session.commit()

        assert atualizado.id == atend_id, "deve ser o mesmo registro"
        assert Atendimento.query.count() == total_antes, "não pode criar outro"
        assert atualizado.status == ATENDIMENTO_CONCLUIDO
        assert atualizado.observacao == "segundo"
        assert {t.id_servico for t in atualizado.servicos} == set(tipos)

    def test_idempotente_com_mesmos_dados(self, client, db, auth):
        """Duas chamadas com o mesmo id e mesmos dados não duplicam nada."""
        p, u = self._contexto()
        tipos = _tipos(2)

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=tipos,
        )
        _db.session.commit()
        atend_id = atend.id
        total_atend = Atendimento.query.count()
        total_vinc = AtendimentoServico.query.filter_by(id_atendimento=atend_id).count()

        for _ in range(2):
            upsert_atendimento(
                id_pessoa=p.id, id_usuario=u.id, servicos_ids=tipos,
                atendimento_id=atend_id,
            )
            _db.session.commit()

        assert Atendimento.query.count() == total_atend
        assert AtendimentoServico.query.filter_by(id_atendimento=atend_id).count() == total_vinc
        assert total_vinc == len(tipos)

    def test_remove_tipo_desmarcado(self, client, db, auth):
        """Tipos fora da nova lista são removidos do vínculo."""
        p, u = self._contexto()
        tipos = _tipos(2)

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=tipos,
        )
        _db.session.commit()
        atend_id = atend.id

        upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=[tipos[0]],
            atendimento_id=atend_id,
        )
        _db.session.commit()

        restantes = {t.id_servico for t in
                     _db.session.get(Atendimento, atend_id).servicos}
        assert restantes == {tipos[0]}

    def test_preserva_data_e_hora_na_atualizacao(self, client, db, auth):
        """A data/hora marca o início e não é reescrita a cada update."""
        p, u = self._contexto()

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=_tipos(1),
            status=ATENDIMENTO_RASCUNHO,
        )
        _db.session.commit()
        atend_id, data0, hora0 = atend.id, atend.data_atendimento, atend.hora_atendimento

        upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=_tipos(1),
            status=ATENDIMENTO_CONCLUIDO, atendimento_id=atend_id,
        )
        _db.session.commit()

        atualizado = _db.session.get(Atendimento, atend_id)
        assert atualizado.data_atendimento == data0
        assert atualizado.hora_atendimento == hora0

    def test_status_invalido_levanta_erro(self, client, db, auth):
        p, u = self._contexto()
        with pytest.raises(ValueError):
            upsert_atendimento(
                id_pessoa=p.id, id_usuario=u.id, servicos_ids=_tipos(1),
                status="finalizado",
            )

    def test_id_inexistente_cria_novo(self, client, db, auth):
        """Id que não existe no banco não quebra — cai no caminho de criação."""
        p, u = self._contexto()

        atend = upsert_atendimento(
            id_pessoa=p.id, id_usuario=u.id, servicos_ids=_tipos(1),
            atendimento_id=999999,
        )
        _db.session.commit()

        assert atend.id is not None
        assert atend.id != 999999


# ── Tela guiada: contrato entre o JS e o HTML ─────────────────────────────────

class TestTelaGuiadaFinaliza:
    """Protege contra a regressão do ciclo de 2026-08-16.

    A Etapa 2 (separação canal × serviço) renomeou os checkboxes de
    `name="tipos"` para `name="servicos"`, mas três `querySelectorAll` do
    JavaScript continuaram procurando `name="tipos"`. Casavam com zero
    elementos, e a validação de submit passou a contar sempre 0 serviços —
    a tela deixou de finalizar qualquer atendimento.

    Os testes de POST não pegaram isso porque o test client não executa
    JavaScript: o backend sempre esteve correto. Por isso o teste abaixo
    verifica o CONTRATO entre os seletores do JS e os inputs renderizados,
    e não só o comportamento do servidor.
    """

    def _html_da_tela(self, client, auth):
        auth.login_como("administrador")
        rv = client.get("/atendimentos/iniciar")
        assert rv.status_code == 200
        return rv.get_data(as_text=True)

    def test_seletores_do_js_casam_com_inputs_reais(self, client, db, auth):
        """Todo input[name=X] procurado pelo JS existe de fato no HTML."""
        import re

        html = self._html_da_tela(client, auth)

        procurados = set(re.findall(r'querySelectorAll\(\s*[\'"]input\[name="(\w+)"\]', html))
        existentes = set(re.findall(r'<input[^>]*name="(\w+)"', html))

        assert procurados, "esperava encontrar seletores de input no JS da tela"

        orfaos = procurados - existentes
        assert not orfaos, (
            f"o JS procura input[name=...] que não existe no HTML: {sorted(orfaos)}. "
            f"Nomes realmente renderizados: {sorted(existentes)}"
        )

    def test_checkboxes_de_servico_usam_name_servicos(self, client, db, auth):
        """O campo que alimenta o POST é `servicos` — é o contrato com a rota."""
        import re

        html = self._html_da_tela(client, auth)
        checkboxes = re.findall(r'<input[^>]*type="checkbox"[^>]*name="(\w+)"', html)

        assert checkboxes, "a tela deve renderizar checkboxes de serviço"
        assert set(checkboxes) == {"servicos"}, (
            f"checkbox com name inesperado: {set(checkboxes)}"
        )

    def test_finaliza_atendimento_com_um_servico(self, client, db, auth):
        """Ponta a ponta: submeter com um serviço grava o atendimento."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        servico_id = _tipos(1)[0]
        _db.session.commit()

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "servicos": [str(servico_id)],
        }, follow_redirects=False)

        assert rv.status_code == 302, "deve redirecionar após finalizar"

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None, "o atendimento deve ter sido gravado"
        assert atend.id_usuario == u.id
        assert {s.id_servico for s in atend.servicos} == {servico_id}

    def test_finaliza_com_varios_servicos(self, client, db, auth):
        """Vários serviços no mesmo atendimento — a relação é N:N."""
        auth.login_como("administrador")
        p = PessoaFactory.create()
        ids = _tipos(2)
        _db.session.commit()

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "servicos": [str(i) for i in ids],
        }, follow_redirects=False)

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert {s.id_servico for s in atend.servicos} == set(ids)

    def test_sem_servico_nao_grava(self, client, db, auth):
        """A validação do backend segue barrando submissão sem serviço."""
        auth.login_como("administrador")
        p = PessoaFactory.create()
        _db.session.commit()

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
        }, follow_redirects=False)

        assert Atendimento.query.filter_by(id_pessoa=p.id).first() is None


# ── Tela guiada: bloco único de serviço (duas zonas) ──────────────────────────

class TestBotaoServicoUnificado:
    """O bloco de serviços foi unificado em 2026-08-16.

    Antes havia dois blocos redundantes: botões que abriam portal e marcavam
    (mas não submetiam) e checkboxes que eram a única coisa no POST. Agora é
    um item só, com duas zonas independentes:

        .servico-corpo  → <label> do checkbox: marca/desmarca, nunca abre
        .servico-portal → botão irmão, FORA do label: abre, nunca marca

    O checkbox continua sendo a fonte de verdade e submete nativamente.
    """

    def _html(self, client, auth):
        auth.login_como("administrador")
        rv = client.get("/atendimentos/iniciar")
        assert rv.status_code == 200
        return rv.get_data(as_text=True)

    def test_um_item_por_servico_sem_bloco_duplicado(self, client, db, auth):
        """Cada serviço aparece uma única vez — o bloco 3 não existe mais."""
        import re

        html = self._html(client, auth)
        total_servicos = Servico.query.filter_by(ativo=True).count()

        itens  = re.findall(r'class="servico-item"', html)
        corpos = re.findall(r'class="servico-corpo"', html)
        checks = re.findall(r'<input[^>]*name="servicos"[^>]*>', html)

        assert len(itens) == total_servicos
        assert len(corpos) == total_servicos
        assert len(checks) == total_servicos, (
            "deve haver exatamente um checkbox por serviço — mais que isso "
            "indica que o bloco duplicado voltou"
        )

    def test_marcar_nao_abre_portal(self, client, db, auth):
        """A zona de marcação não dispara window.open.

        O <label> só aponta para o checkbox via `for`; abrir portal é
        responsabilidade exclusiva do botão irmão.
        """
        import re

        html = self._html(client, auth)

        for label in re.findall(r'<label[^>]*class="servico-corpo".*?</label>', html, re.S):
            assert "window.open" not in label
            assert "onclick" not in label
            assert "abrirPortal" not in label

    def test_icone_de_portal_so_em_servico_com_link(self, client, db, auth):
        """Serviço sem link_portal não exibe o ícone."""
        import re

        html = self._html(client, auth)
        com_link = Servico.query.filter(
            Servico.ativo.is_(True), Servico.link_portal.isnot(None)
        ).count()

        icones = re.findall(r'class="servico-portal"', html)
        assert len(icones) == com_link
        assert icones, "esperava ao menos um serviço com portal"

    def test_icone_abre_portal_e_nao_marca(self, client, db, auth):
        """O botão de portal chama abrirPortal e fica fora do label."""
        import re

        html = self._html(client, auth)
        botoes = re.findall(r'<button[^>]*class="servico-portal".*?</button>', html, re.S)

        assert botoes
        for b in botoes:
            assert 'type="button"' in b, "não pode submeter o formulário"
            assert "abrirPortal(this)" in b
            assert "data-url=" in b
            assert 'name=' not in b, "o botão de portal não vai no POST"

    def test_aplicabilidade_exposta_no_dom(self, client, db, auth):
        """`data-aplicabilidade` fica pronto para a filtragem futura."""
        import re

        html = self._html(client, auth)
        valores = re.findall(r'data-aplicabilidade="(\w+)"', html)

        assert len(valores) == Servico.query.filter_by(ativo=True).count()
        assert set(valores) <= {"nao_mei", "mei", "todos"}

    def test_finaliza_com_servicos_marcados_pelos_botoes(self, client, db, auth):
        """O POST continua chegando com name="servicos" — a fusão preservou
        a fonte de verdade."""
        u = auth.login_como("administrador")
        p = PessoaFactory.create()
        ids = _tipos(2)
        _db.session.commit()

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "servicos": [str(i) for i in ids],
        }, follow_redirects=False)

        assert rv.status_code == 302
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.id_usuario == u.id
        assert {s.id_servico for s in atend.servicos} == set(ids)
