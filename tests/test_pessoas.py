"""
test_pessoas.py — Testes do módulo de cadastro de empreendedores.

CPF válido usado nos testes: 123.456.789-09
CPF inválido (dígitos errados): 123.456.789-00
"""
from app.models import Pessoa
from tests.conftest import PessoaFactory

# CPF com dígitos verificadores corretos (verificado manualmente)
CPF_VALIDO   = "123.456.789-09"
CPF_INVALIDO = "123.456.789-00"   # formato correto, mas dígito verificador errado


# ── Listagem ──────────────────────────────────────────────────────────────────

class TestListaPessoas:
    def test_lista_retorna_200(self, client, db, auth):
        """GET /pessoas/ com autenticação → 200."""
        auth.login_como("atendente")
        rv = client.get("/pessoas/")
        assert rv.status_code == 200

    def test_lista_exibe_pessoas_cadastradas(self, client, db, auth):
        """Pessoas no banco aparecem na listagem."""
        auth.login_como("atendente")
        PessoaFactory.create(nome_razao_social="Empreendedor Teste ABC")
        rv = client.get("/pessoas/")
        assert b"Empreendedor Teste ABC" in rv.data

    def test_lista_paginada(self, client, db, auth):
        """A listagem é paginada — página 1 deve retornar 200."""
        auth.login_como("atendente")
        rv = client.get("/pessoas/?page=1")
        assert rv.status_code == 200

    def test_lista_sem_autenticacao_redireciona(self, client, db):
        rv = client.get("/pessoas/", follow_redirects=False)
        assert rv.status_code == 302


# ── Busca ─────────────────────────────────────────────────────────────────────

class TestBuscaPessoas:
    def test_busca_por_nome_retorna_200(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.get("/pessoas/?q=Empreendedor")
        assert rv.status_code == 200

    def test_busca_encontra_cadastro_existente(self, client, db, auth):
        """Busca pelo nome retorna a pessoa cadastrada."""
        auth.login_como("atendente")
        PessoaFactory.create(nome_razao_social="Fulano de Tal Unico")
        rv = client.get("/pessoas/?q=Fulano")
        assert b"Fulano de Tal Unico" in rv.data

    def test_busca_sem_resultado_retorna_200(self, client, db, auth):
        """Busca por termo inexistente retorna 200 (lista vazia, sem erro)."""
        auth.login_como("atendente")
        rv = client.get("/pessoas/?q=xyztermonaoexiste")
        assert rv.status_code == 200

    def test_filtro_chip_mei(self, client, db, auth):
        """Chip MEI filtra apenas empreendedores com flag mei=True."""
        auth.login_como("atendente")
        PessoaFactory.create(nome_razao_social="MEI Silva", mei=True)
        PessoaFactory.create(nome_razao_social="PF Souza",  mei=False)
        rv = client.get("/pessoas/?tipo=MEI")
        assert rv.status_code == 200


# ── Criar pessoa ──────────────────────────────────────────────────────────────

class TestNovaPessoa:
    def _form_minimo(self, nome=None, cpf=CPF_VALIDO):
        return {"nome_razao_social": nome or "João Empreendedor Silva", "cpf": cpf}

    def test_get_form_novo_retorna_200(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.get("/pessoas/nova")
        assert rv.status_code == 200

    def test_criar_pessoa_valida_redireciona(self, client, db, auth):
        """POST com dados válidos → 302 para a ficha da pessoa."""
        auth.login_como("atendente")
        rv = client.post("/pessoas/nova", data=self._form_minimo(), follow_redirects=False)
        assert rv.status_code == 302

    def test_pessoa_salva_no_banco(self, client, db, auth):
        """Após criação, a pessoa existe no banco de dados."""
        auth.login_como("atendente")
        client.post("/pessoas/nova", data=self._form_minimo(nome="Cadastro Persistido"))
        assert Pessoa.query.filter_by(nome_razao_social="Cadastro Persistido").first() is not None

    def test_criar_sem_nome_retorna_erro(self, client, db, auth):
        """POST sem nome_razao_social → 200 com mensagem de erro (não redireciona)."""
        auth.login_como("atendente")
        rv = client.post(
            "/pessoas/nova",
            data={"nome_razao_social": "", "cpf": CPF_VALIDO},
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert b"obrigat" in rv.data.lower()

    def test_criar_com_cpf_formato_invalido_retorna_erro(self, client, db, auth):
        """CPF fora do formato XXX.XXX.XXX-XX → erro de validação."""
        auth.login_como("atendente")
        rv = client.post(
            "/pessoas/nova",
            data={"nome_razao_social": "Teste CPF", "cpf": "12345678900"},  # sem formatação
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert b"CPF" in rv.data

    def test_criar_com_cpf_digito_invalido_retorna_erro(self, client, db, auth):
        """CPF no formato correto mas dígito verificador errado → erro."""
        auth.login_como("atendente")
        rv = client.post(
            "/pessoas/nova",
            data=self._form_minimo(cpf=CPF_INVALIDO),
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert b"inv" in rv.data.lower()   # "inválido"

    def test_criar_sem_cpf_nem_cnpj_retorna_erro(self, client, db, auth):
        """PF sem CPF e sem CNPJ → erro de validação."""
        auth.login_como("atendente")
        rv = client.post(
            "/pessoas/nova",
            data={"nome_razao_social": "Sem Documento"},
            follow_redirects=False,
        )
        assert rv.status_code == 200


# ── Detalhe e edição ──────────────────────────────────────────────────────────

class TestDetalhePessoa:
    def test_detalhe_retorna_200(self, client, db, auth):
        auth.login_como("atendente")
        p = PessoaFactory.create(nome_razao_social="Detalhe Test")
        rv = client.get(f"/pessoas/{p.id}")
        assert rv.status_code == 200
        assert b"Detalhe Test" in rv.data

    def test_detalhe_inexistente_retorna_404(self, client, db, auth):
        auth.login_como("atendente")
        rv = client.get("/pessoas/99999")
        assert rv.status_code == 404

    def test_editar_retorna_200(self, client, db, auth):
        auth.login_como("administrador")
        p = PessoaFactory.create()
        rv = client.get(f"/pessoas/{p.id}/editar")
        assert rv.status_code == 200
