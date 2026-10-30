"""
test_filtragem_servicos.py — Filtragem de serviços por tipo efetivo.

A tela guiada mostra só os serviços aplicáveis ao **tipo efetivo do
atendimento**:

    exibe se  aplicabilidade == tipo_efetivo  ou  aplicabilidade == 'todos'

O tipo efetivo é um estado DO ATENDIMENTO: nasce do cadastro da pessoa e pode
mudar durante o atendimento (conversão PF→MEI) sem tocar no cadastro.

O front guia escondendo; o back garante revalidando. Estes testes cobrem o
lado do servidor e o contrato que a tela entrega ao JavaScript.
"""
from app import db as _db
from app.models import Atendimento, Pessoa, Servico, tipo_efetivo_de
from tests.conftest import PessoaFactory

import re


def _servico(aplic):
    return Servico.query.filter_by(aplicabilidade=aplic).first()


def _pessoa(mei=False, cnpj=None):
    p = PessoaFactory.create()
    if mei:
        p.mei = True
    if cnpj:
        p.cnpj = cnpj
    _db.session.commit()
    return p


# ── Derivação do tipo efetivo a partir do cadastro ────────────────────────────

class TestTipoEfetivoInicial:

    def test_pessoa_sem_cnpj_nem_mei_e_nao_mei(self, client, db, auth):
        assert tipo_efetivo_de(_pessoa()) == "nao_mei"

    def test_pessoa_marcada_como_mei(self, client, db, auth):
        assert tipo_efetivo_de(_pessoa(mei=True)) == "mei"

    def test_pessoa_com_cnpj_e_mei(self, client, db, auth):
        assert tipo_efetivo_de(_pessoa(cnpj="11.222.333/0001-81")) == "mei"

    def test_sem_pessoa_assume_nao_mei(self, client, db, auth):
        assert tipo_efetivo_de(None) == "nao_mei"


# ── O que a tela entrega ao JavaScript ────────────────────────────────────────

class TestContratoDaTela:

    def _html(self, client, auth):
        auth.login_como("administrador")
        rv = client.get("/atendimentos/iniciar")
        assert rv.status_code == 200
        return rv.get_data(as_text=True)

    def test_aplicabilidade_de_cada_servico_vai_ao_dom(self, client, db, auth):
        """A filtragem é client-side a partir do `data-aplicabilidade` — sem
        nova ida ao servidor, e sem reintroduzir array de serviços no JS."""
        html = self._html(client, auth)
        aplics = re.findall(r'data-aplicabilidade="(\w+)"', html)

        assert len(aplics) == Servico.query.filter_by(ativo=True).count()
        assert {"nao_mei", "mei", "todos"} <= set(aplics)
        assert "const SERVICOS" not in html, "não reintroduzir o array no JS"

    def test_tipo_efetivo_vai_num_hidden(self, client, db, auth):
        html = self._html(client, auth)
        assert 'name="tipo_efetivo"' in html

    def test_cada_servico_tem_hidden_de_snapshot_e_forcado(self, client, db, auth):
        html = self._html(client, auth)
        total = Servico.query.filter_by(ativo=True).count()

        assert len(re.findall(r'name="snap_\d+"', html)) == total
        assert len(re.findall(r'name="forcado_\d+"', html)) == total

    def test_ancora_da_conversao_e_unica_e_derivada_da_descricao(self, client, db, auth):
        """`data-converte-mei` marca o serviço de Abertura de MEI, localizado
        por descrição — nunca por id hardcoded."""
        html = self._html(client, auth)
        # Conta apenas as divs de serviço — o seletor JS
        # `.servico-item[data-converte-mei="1"]` também contém essa string.
        divs = re.findall(r'<div class="servico-item".*?>', html, re.S)
        ancoras = [d for d in divs if 'data-converte-mei="1"' in d]
        assert len(ancoras) == 1, f"esperava 1 âncora, achou {len(ancoras)}"

    def test_valvula_de_escape_sempre_presente(self, client, db, auth):
        """O controle não pode estar escondido — é a saída para cadastro com
        tipo errado."""
        html = self._html(client, auth)
        assert 'id="mostrar-todos"' in html

    def test_checkbox_segue_sendo_a_fonte_de_verdade(self, client, db, auth):
        """A fusão anterior não pode ter sido desfeita."""
        html = self._html(client, auth)
        checks = re.findall(r'<input[^>]*type="checkbox"[^>]*name="servicos"', html)
        assert len(checks) == Servico.query.filter_by(ativo=True).count()


# ── O servidor valida ─────────────────────────────────────────────────────────

class TestServidorValida:

    def test_recusa_servico_nao_aplicavel(self, client, db, auth):
        """Pessoa nao_mei + serviço `mei` sem marca de forçado → recusado."""
        auth.login_como("administrador")
        p = _pessoa()
        serv_mei = _servico("mei")

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "nao_mei",
            "servicos": [str(serv_mei.id)],
        }, follow_redirects=False)

        assert rv.status_code == 200, "não redireciona — foi recusado"
        assert Atendimento.query.filter_by(id_pessoa=p.id).first() is None

    def test_aceita_forcado_e_marca_para_auditoria(self, client, db, auth):
        """Declarado como forçado (válvula de escape) → aceito com flag."""
        auth.login_como("administrador")
        p = _pessoa()
        serv_mei = _servico("mei")

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "nao_mei",
            "servicos": [str(serv_mei.id)],
            "forcado_%d" % serv_mei.id: "1",
        }, follow_redirects=False)

        assert rv.status_code == 302
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.servicos[0].forcado is True

    def test_servico_aplicavel_nunca_vira_forcado(self, client, db, auth):
        """Mesmo se o cliente mandar a flag — quem decide é o servidor."""
        auth.login_como("administrador")
        p = _pessoa()
        serv_todos = _servico("todos")

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "nao_mei",
            "servicos": [str(serv_todos.id)],
            "forcado_%d" % serv_todos.id: "1",
        }, follow_redirects=False)

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend.servicos[0].forcado is False

    def test_tipo_efetivo_adulterado_cai_no_cadastro(self, client, db, auth):
        """Valor inválido no POST não passa: o servidor recalcula do cadastro."""
        auth.login_como("administrador")
        p = _pessoa()                       # nao_mei
        serv_mei = _servico("mei")

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "qualquer_coisa",
            "servicos": [str(serv_mei.id)],
        }, follow_redirects=False)

        assert rv.status_code == 200
        assert Atendimento.query.filter_by(id_pessoa=p.id).first() is None

    def test_servico_todos_aceito_para_qualquer_tipo(self, client, db, auth):
        auth.login_como("administrador")
        serv = _servico("todos")

        for tipo in ("nao_mei", "mei"):
            p = _pessoa(mei=(tipo == "mei"))

            rv = client.post("/atendimentos/iniciar", data={
                "id_pessoa": p.id,
                "tipo_efetivo": tipo,
                "servicos": [str(serv.id)],
            }, follow_redirects=False)

            assert rv.status_code == 302, f"'todos' deve valer para {tipo}"


# ── Conversão PF→MEI dentro do atendimento ────────────────────────────────────

class TestConversaoNoAtendimento:

    def test_apos_converter_servico_mei_e_aceito(self, client, db, auth):
        """Pessoa nao_mei que abriu MEI no balcão: o tipo efetivo vai a 'mei' e
        os serviços de MEI passam a ser aceitos no mesmo atendimento."""
        auth.login_como("administrador")
        p = _pessoa()
        abertura = _servico("nao_mei")
        serv_mei = _servico("mei")

        rv = client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "mei",                       # convertido na tela
            "servicos": [str(abertura.id), str(serv_mei.id)],
            "snap_%d" % abertura.id: "nao_mei",
            "forcado_%d" % abertura.id: "1",             # revelado após converter
            "snap_%d" % serv_mei.id: "mei",
        }, follow_redirects=False)

        assert rv.status_code in (302,)
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert len(atend.servicos) == 2

    def test_conversao_nao_altera_o_cadastro(self, client, db, auth):
        """Fora de escopo desta fase: promover o cadastro é a próxima."""
        auth.login_como("administrador")
        p = _pessoa()
        pid = p.id
        serv_mei = _servico("mei")

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": pid,
            "tipo_efetivo": "mei",
            "servicos": [str(serv_mei.id)],
        }, follow_redirects=False)

        _db.session.expire_all()
        pessoa = _db.session.get(Pessoa, pid)
        assert not pessoa.mei, "o cadastro não vira MEI nesta fase"
        assert not pessoa.cnpj, "nenhum CNPJ é capturado nesta fase"


# ── Snapshot do tipo no momento do serviço ────────────────────────────────────

class TestSnapshotDoTipo:

    def test_servicos_do_mesmo_atendimento_com_tipos_diferentes(self, client, db, auth):
        """O histórico não muda retroativamente: Abertura de MEI fica como
        feita quando ainda era nao_mei; o serviço seguinte, como mei."""
        auth.login_como("administrador")
        p = _pessoa()
        abertura = _servico("nao_mei")
        serv_mei = _servico("mei")

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "mei",
            "servicos": [str(abertura.id), str(serv_mei.id)],
            "snap_%d" % abertura.id: "nao_mei",
            "forcado_%d" % abertura.id: "1",
            "snap_%d" % serv_mei.id: "mei",
        }, follow_redirects=False)

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        snaps = {v.id_servico: v.tipo_efetivo for v in atend.servicos}

        assert snaps[abertura.id] == "nao_mei"
        assert snaps[serv_mei.id] == "mei"

    def test_sem_snapshot_usa_o_tipo_do_atendimento(self, client, db, auth):
        """Ex.: JavaScript desligado — o registro ainda fica coerente."""
        auth.login_como("administrador")
        p = _pessoa()
        serv = _servico("todos")

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "nao_mei",
            "servicos": [str(serv.id)],
        }, follow_redirects=False)

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend.servicos[0].tipo_efetivo == "nao_mei"

    def test_snapshot_invalido_e_ignorado(self, client, db, auth):
        auth.login_como("administrador")
        p = _pessoa()
        serv = _servico("todos")

        client.post("/atendimentos/iniciar", data={
            "id_pessoa": p.id,
            "tipo_efetivo": "nao_mei",
            "servicos": [str(serv.id)],
            "snap_%d" % serv.id: "lixo",
        }, follow_redirects=False)

        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend.servicos[0].tipo_efetivo == "nao_mei"


# ── Os outros caminhos de atendimento não regridem ────────────────────────────

class TestOutrosCaminhos:

    def test_rapido_continua_gravando(self, client, db, auth):
        """`/atendimentos/rapido` não tem noção de tipo efetivo — grava NULL no
        snapshot, em vez de um valor inventado."""
        auth.login_como("administrador")
        p = _pessoa()
        serv = _servico("mei")

        rv = client.post("/atendimentos/rapido", data={
            "id_pessoa": p.id,
            "servicos": [str(serv.id)],
        }, follow_redirects=False)

        assert rv.status_code == 302
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.servicos[0].tipo_efetivo is None
        assert atend.servicos[0].forcado is False

    def test_completo_continua_gravando(self, client, db, auth):
        """`/atendimentos/novo` idem."""
        from tests.conftest import criar_usuario

        auth.login_como("administrador")
        p = _pessoa()
        resp = criar_usuario("atendente", login="dono_filtro")
        serv = _servico("mei")

        rv = client.post("/atendimentos/novo", data={
            "id_pessoa": p.id,
            "id_usuario": resp.id,
            "data_atendimento": "2026-08-16",
            "hora_atendimento": "10:00",
            "servicos": [str(serv.id)],
        }, follow_redirects=False)

        assert rv.status_code == 302
        atend = Atendimento.query.filter_by(id_pessoa=p.id).first()
        assert atend is not None
        assert atend.servicos[0].tipo_efetivo is None
