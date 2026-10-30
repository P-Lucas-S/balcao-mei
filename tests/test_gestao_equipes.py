"""
test_gestao_equipes.py — Gestão de equipes pela interface.

O vínculo `supervisor_id` já existia e funcionava; o que faltava era
acabamento para a tela poder ser operada por um admin não técnico, com
segurança. Este arquivo cobre os quatro defeitos fechados em 2026-09-01 e as
duas validações que só existiam no JavaScript.

O mais grave era a **desvinculação silenciosa**: o dropdown listava apenas
ADs ativos, então editar o nome de um bolsista cujo AD fora desativado
gravava `supervisor_id = None` e desmontava a equipe sem aviso.
"""
import re

from app import db as _db
from app.models import PerfilAcesso, Usuario
from tests.conftest import criar_usuario


def _entrar(client, usuario):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(usuario.id)
        sess["_fresh"] = True


def _admin(client, login="adm_equipes"):
    adm = criar_usuario("administrador", login=login)
    _entrar(client, adm)
    return adm


def _perfil_id(nome):
    return PerfilAcesso.query.filter_by(nome=nome).first().id


def _perfil_legado(nome="OPERADOR"):
    """Cria um perfil legado. O seed de teste só tem os três em uso, então
    ele não existe — mas no banco real existem seis assim."""
    p = PerfilAcesso.query.filter_by(nome=nome).first()
    if p is None:
        p = PerfilAcesso(nome=nome, descricao="Legado")
        _db.session.add(p)
        _db.session.commit()
    return p


def _equipe(sup_login="ad_um", at_login="bolsista_um", ad_ativo=True):
    """Um AD com um bolsista vinculado."""
    sup = criar_usuario("supervisor", login=sup_login, ativo=ad_ativo)
    at = criar_usuario("atendente", login=at_login)
    at.supervisor_id = sup.id
    _db.session.commit()
    return sup, at


def _form_renderizado(client, usuario_id):
    """Os campos como o navegador os enviaria ao salvar sem tocar em nada.

    É a simulação honesta de "o admin corrigiu o nome e clicou em salvar":
    o POST leva o que o formulário renderizou, não o que o teste inventou.
    """
    html = client.get(f"/usuarios/{usuario_id}/editar").get_data(as_text=True)

    def _selecionado(select_id):
        bloco = re.search(rf'<select id="{select_id}".*?</select>', html, re.S)
        if not bloco:
            return ""
        m = re.search(r'<option value="([^"]*)"[^>]*\bselected\b', bloco.group(0))
        return m.group(1) if m else ""

    return {
        "nome":          re.search(r'id="nome"[^>]*value="([^"]*)"', html).group(1),
        "login":         re.search(r'id="login"[^>]*value="([^"]*)"', html).group(1),
        "id_perfil":     _selecionado("id_perfil"),
        "supervisor_id": _selecionado("supervisor_id"),
    }


# ── O defeito grave: desvinculação silenciosa ─────────────────────────────────

class TestNaoDesvinculaEmSilencio:
    """Editar um bolsista jamais pode desmontar a equipe por efeito colateral."""

    def test_ad_inativo_continua_no_dropdown(self, client, db, auth):
        """Antes, o AD desativado sumia da lista e o select caía em 'Nenhum'."""
        _admin(client)
        sup, at = _equipe(ad_ativo=False)

        html = client.get(f"/usuarios/{at.id}/editar").get_data(as_text=True)
        bloco = re.search(r'<select id="supervisor_id".*?</select>', html, re.S).group(0)

        assert f'value="{sup.id}"' in bloco, (
            "o AD inativo sumiu do dropdown — é assim que o vínculo se perdia")
        assert "selected" in bloco, "o vínculo atual tem de vir selecionado"
        assert "(inativo)" in bloco, "o admin precisa ver que aquele AD está inativo"

    def test_salvar_sem_mexer_preserva_o_vinculo_com_ad_inativo(self, client, db, auth):
        """O teste que prova a correção: round-trip completo do formulário."""
        _admin(client)
        sup, at = _equipe(ad_ativo=False)
        at_id, sup_id = at.id, sup.id

        dados = _form_renderizado(client, at_id)
        assert dados["supervisor_id"] == str(sup_id), (
            "o formulário já veio sem o vínculo — o POST nem chegaria a errar")

        rv = client.post(f"/usuarios/{at_id}/editar", data=dados)
        assert rv.status_code == 302

        assert _db.session.get(Usuario, at_id).supervisor_id == sup_id, (
            "salvar sem tocar no supervisor desvinculou a equipe")

    def test_editar_o_nome_nao_mexe_no_vinculo(self, client, db, auth):
        _admin(client)
        sup, at = _equipe(sup_login="ad_nome", at_login="bolsista_nome")
        at_id, sup_id = at.id, sup.id

        dados = _form_renderizado(client, at_id)
        dados["nome"] = "Nome Corrigido"
        client.post(f"/usuarios/{at_id}/editar", data=dados)

        atualizado = _db.session.get(Usuario, at_id)
        assert atualizado.nome == "Nome Corrigido"
        assert atualizado.supervisor_id == sup_id

    def test_desvincular_de_propósito_continua_possível(self, client, db, auth):
        """Preservar não pode virar impossibilidade de tirar da equipe."""
        _admin(client)
        sup, at = _equipe(sup_login="ad_solta", at_login="bolsista_solta")
        at_id = at.id

        dados = _form_renderizado(client, at_id)
        dados["supervisor_id"] = ""
        client.post(f"/usuarios/{at_id}/editar", data=dados)

        assert _db.session.get(Usuario, at_id).supervisor_id is None

    def test_remanejar_entre_ads(self, client, db, auth):
        """O caso real: a Nil sai de um AD e vai para outro."""
        _admin(client)
        sup_a, at = _equipe(sup_login="ad_origem", at_login="nil")
        sup_b = criar_usuario("supervisor", login="ad_destino")
        _db.session.commit()
        at_id, destino = at.id, sup_b.id

        dados = _form_renderizado(client, at_id)
        dados["supervisor_id"] = str(destino)
        client.post(f"/usuarios/{at_id}/editar", data=dados)

        assert _db.session.get(Usuario, at_id).supervisor_id == destino


# ── Validação no backend, não só no JavaScript ───────────────────────────────

class TestIntegridadeNoBackend:
    """O JS esconde o campo; o servidor é quem garante."""

    def test_supervisor_id_ignorado_para_supervisor(self, client, db, auth):
        """"AD sob AD" não existe — o campo é o vínculo do bolsista com o AD."""
        _admin(client)
        chefe = criar_usuario("supervisor", login="ad_chefe")
        _db.session.commit()

        rv = client.post("/usuarios/novo", data={
            "nome": "Outro AD", "login": "ad_sob_ad",
            "id_perfil": _perfil_id("supervisor"),
            "supervisor_id": str(chefe.id),
            "senha": "senha123", "confirmar_senha": "senha123",
        })
        assert rv.status_code == 302

        criado = Usuario.query.filter_by(login="ad_sob_ad").one()
        assert criado.supervisor_id is None

    def test_supervisor_id_ignorado_para_administrador(self, client, db, auth):
        _admin(client)
        chefe = criar_usuario("supervisor", login="ad_chefe_adm")
        _db.session.commit()

        client.post("/usuarios/novo", data={
            "nome": "Admin", "login": "adm_com_sup",
            "id_perfil": _perfil_id("administrador"),
            "supervisor_id": str(chefe.id),
            "senha": "senha123", "confirmar_senha": "senha123",
        })
        assert Usuario.query.filter_by(login="adm_com_sup").one().supervisor_id is None

    def test_auto_supervisao_recusada(self, client, db, auth):
        _admin(client)
        at = criar_usuario("atendente", login="ele_mesmo")
        _db.session.commit()
        at_id = at.id

        dados = _form_renderizado(client, at_id)
        dados["supervisor_id"] = str(at_id)
        rv = client.post(f"/usuarios/{at_id}/editar", data=dados)

        assert rv.status_code == 200, "deve recusar e reexibir o formulário"
        assert "supervisor de si mesmo" in rv.get_data(as_text=True)
        assert _db.session.get(Usuario, at_id).supervisor_id is None

    def test_cria_ciclo_detecta_a_volta(self, client, db, auth):
        """Teste de unidade, porque pelo FORMULÁRIO o ciclo é inalcançável.

        `supervisor_id` só vale para atendente, e o escolhido tem de ter
        perfil supervisor — então um supervisor nunca ganha um chefe por essa
        via, e a volta não se fecha. `_cria_ciclo` é defesa em profundidade
        para dado que chegue por outro caminho (banco direto, ou uma futura
        hierarquia de ADs).

        A primeira versão deste teste passava com a checagem REMOVIDA: ele
        procurava a palavra "ciclo" na página, e ela vinha do login do usuário
        de teste, não da mensagem de erro. A mutação denunciou.
        """
        from app.routes.usuarios import _cria_ciclo

        a = criar_usuario("supervisor", login="volta_a")
        b = criar_usuario("supervisor", login="volta_b")
        b.supervisor_id = a.id
        _db.session.commit()

        # Pôr `a` sob `b` fecharia a volta: a -> b -> a
        assert _cria_ciclo(a.id, b.id) is True
        # Um vínculo qualquer que não volta
        c = criar_usuario("atendente", login="volta_c")
        _db.session.commit()
        assert _cria_ciclo(c.id, a.id) is False

    def test_cria_ciclo_pega_auto_referencia(self, client, db, auth):
        from app.routes.usuarios import _cria_ciclo

        u = criar_usuario("atendente", login="volta_eu")
        _db.session.commit()
        assert _cria_ciclo(u.id, u.id) is True

    def test_cria_ciclo_termina_com_ciclo_ja_no_banco(self, client, db, auth):
        """Se o banco já vier corrompido, a subida não pode rodar para sempre."""
        from app.routes.usuarios import _cria_ciclo

        a = criar_usuario("supervisor", login="preso_a")
        b = criar_usuario("supervisor", login="preso_b")
        a.supervisor_id = b.id
        b.supervisor_id = a.id      # ciclo já existente
        _db.session.commit()

        c = criar_usuario("atendente", login="preso_c")
        _db.session.commit()
        assert _cria_ciclo(c.id, a.id) is False   # termina, não trava


    def test_supervisor_inexistente_recusado(self, client, db, auth):
        _admin(client)
        at = criar_usuario("atendente", login="sup_fantasma")
        _db.session.commit()
        at_id = at.id

        rv = client.post(f"/usuarios/{at_id}/editar", data={
            "nome": "Fulano", "login": "sup_fantasma",
            "id_perfil": _perfil_id("atendente"),
            "supervisor_id": "99999",
        })
        assert rv.status_code == 200
        assert _db.session.get(Usuario, at_id).supervisor_id is None

    def test_atendente_nao_vira_supervisor_de_ninguem(self, client, db, auth):
        """Só quem tem perfil supervisor pode ser escolhido como AD."""
        _admin(client)
        outro = criar_usuario("atendente", login="nao_e_ad")
        at = criar_usuario("atendente", login="quer_chefe_errado")
        _db.session.commit()
        at_id = at.id

        rv = client.post(f"/usuarios/{at_id}/editar", data={
            "nome": "Fulano", "login": "quer_chefe_errado",
            "id_perfil": _perfil_id("atendente"),
            "supervisor_id": str(outro.id),
        })
        assert rv.status_code == 200
        assert _db.session.get(Usuario, at_id).supervisor_id is None


# ── O formulário como o admin o vê ───────────────────────────────────────────

class TestFormulario:

    def test_so_os_perfis_em_uso_sao_oferecidos(self, client, db, auth):
        """6 perfis legado com 0 usuários eram armadilha de configuração."""
        _admin(client)
        html = client.get("/usuarios/novo").get_data(as_text=True)
        bloco = re.search(r'<select id="id_perfil".*?</select>', html, re.S).group(0)
        oferecidos = re.findall(r'<option[^>]*>\s*(.*?)\s*</option>', bloco)

        assert set(oferecidos) == {"Selecione…", "atendente",
                                   "supervisor", "administrador"}
        for legado in ("ADMIN", "APOIO", "DESENVOLVEDOR", "INTERMEDIARIO",
                       "OPERADOR", "SECRETARIO"):
            assert legado not in oferecidos

    def test_perfil_legado_nao_e_oferecido_mas_permanece(self, client, db, auth):
        """Não oferecer é diferente de apagar — quem já o tem não quebra."""
        _admin(client)
        legado = _perfil_legado()

        html = client.get("/usuarios/novo").get_data(as_text=True)
        bloco = re.search(r'<select id="id_perfil".*?</select>', html, re.S).group(0)

        assert "OPERADOR" not in bloco, "perfil legado voltou ao formulário"
        assert _db.session.get(PerfilAcesso, legado.id) is not None

    def test_perfil_legado_do_usuario_editado_e_preservado(self, client, db, auth):
        """Editar quem tem perfil antigo não força troca de perfil."""
        _admin(client)
        u = criar_usuario("atendente", login="tem_perfil_antigo")
        u.id_perfil = _perfil_legado().id
        _db.session.commit()

        html = client.get(f"/usuarios/{u.id}/editar").get_data(as_text=True)
        bloco = re.search(r'<select id="id_perfil".*?</select>', html, re.S).group(0)
        assert "OPERADOR" in bloco

    def test_campo_supervisor_escondido_sem_js_para_nao_atendente(self, client, db, auth):
        """Um único `style`, decidido no servidor — antes eram dois, e o
        segundo era descartado pelo HTML."""
        _admin(client)
        sup = criar_usuario("supervisor", login="ad_form")
        _db.session.commit()

        html = client.get(f"/usuarios/{sup.id}/editar").get_data(as_text=True)
        div = re.search(r'<div class="form-row" id="campo-supervisor".*?>',
                        html, re.S).group(0)

        assert div.count("style=") == 1, "dois atributos style: o HTML descarta o 2º"
        assert "display:none" in div

    def test_campo_supervisor_visivel_para_atendente(self, client, db, auth):
        _admin(client)
        _, at = _equipe(sup_login="ad_vis", at_login="bolsista_vis")

        html = client.get(f"/usuarios/{at.id}/editar").get_data(as_text=True)
        div = re.search(r'<div class="form-row" id="campo-supervisor".*?>',
                        html, re.S).group(0)
        assert "display:none" not in div


# ── A listagem ───────────────────────────────────────────────────────────────

class TestListagem:

    def test_coluna_equipe_mostra_o_ad(self, client, db, auth):
        _admin(client)
        sup, at = _equipe(sup_login="ad_lista", at_login="bolsista_lista")
        sup.nome = "AD Da Lista"
        _db.session.commit()

        html = client.get("/usuarios/").get_data(as_text=True)
        assert "<th>Equipe</th>" in html
        assert "AD Da Lista" in html

    def test_atendente_sem_ad_e_sinalizado(self, client, db, auth):
        _admin(client)
        criar_usuario("atendente", login="orfao")
        _db.session.commit()

        assert "selo-sem-equipe" in client.get("/usuarios/").get_data(as_text=True)

    def test_filtro_por_ad(self, client, db, auth):
        _admin(client)
        sup_a, at_a = _equipe(sup_login="ad_f1", at_login="bolsista_f1")
        sup_b, at_b = _equipe(sup_login="ad_f2", at_login="bolsista_f2")
        at_a.nome, at_b.nome = "Bolsista Da Equipe A", "Bolsista Da Equipe B"
        _db.session.commit()

        html = client.get(f"/usuarios/?equipe={sup_a.id}").get_data(as_text=True)
        assert "Bolsista Da Equipe A" in html
        assert "Bolsista Da Equipe B" not in html

    def test_filtro_sem_equipe_isola_os_orfaos(self, client, db, auth):
        _admin(client)
        _, at_com = _equipe(sup_login="ad_f3", at_login="bolsista_com")
        at_sem = criar_usuario("atendente", login="bolsista_sem")
        # Nomes disjuntos de propósito: "Nao Tem Equipe" conteria "Tem Equipe"
        # como substring, e a asserção passaria por acidente.
        at_com.nome, at_sem.nome = "Vinculado Zeta", "Orfao Zeta"
        _db.session.commit()

        html = client.get("/usuarios/?equipe=sem").get_data(as_text=True)
        assert "Orfao Zeta" in html
        assert "Vinculado Zeta" not in html

    def test_filtro_invalido_nao_quebra(self, client, db, auth):
        _admin(client)
        assert client.get("/usuarios/?equipe=abc").status_code == 200

    def test_ad_inativo_sinalizado_na_coluna(self, client, db, auth):
        _admin(client)
        sup, at = _equipe(sup_login="ad_off", at_login="bolsista_off", ad_ativo=False)
        _db.session.commit()

        html = client.get("/usuarios/").get_data(as_text=True)
        assert "AD inativo" in html

    def test_guard_continua_admin_only(self, client, db, auth):
        """O acabamento não afrouxou o acesso à tela."""
        _entrar(client, criar_usuario("supervisor", login="sup_curioso"))
        rv = client.get("/usuarios/")
        assert rv.status_code == 302
