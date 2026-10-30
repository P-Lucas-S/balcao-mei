"""
test_seguranca.py — Testes de segurança e controle de acesso por perfil.
"""
from app.models import (Atendimento, DocumentoPessoa, Pessoa,
                        SolicitacaoExclusao, Solicitacao, Status)
from tests.conftest import (AtendimentoFactory, PessoaFactory,
                            SolicitacaoFactory, criar_usuario)


# ── Headers HTTP ──────────────────────────────────────────────────────────────

class TestHeadersSeguranca:
    """Todos os headers de segurança devem estar presentes em qualquer resposta."""

    def _get_headers(self, client):
        """Retorna headers de uma resposta pública (/login)."""
        return client.get("/login").headers

    def test_x_frame_options(self, client, db):
        assert self._get_headers(client).get("X-Frame-Options") == "SAMEORIGIN"

    def test_x_content_type_options(self, client, db):
        assert self._get_headers(client).get("X-Content-Type-Options") == "nosniff"

    def test_x_xss_protection(self, client, db):
        assert self._get_headers(client).get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self, client, db):
        assert self._get_headers(client).get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client, db):
        assert "geolocation=()" in self._get_headers(client).get("Permissions-Policy", "")

    def test_headers_em_pagina_autenticada(self, client, db, auth):
        """Headers também devem estar presentes em páginas autenticadas."""
        auth.login_como("atendente")
        headers = client.get("/pessoas/").headers
        assert headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert headers.get("X-Content-Type-Options") == "nosniff"

    def test_headers_em_resposta_de_redirecionamento(self, client, db):
        """Headers devem estar presentes inclusive em respostas 302."""
        rv = client.get("/dashboard", follow_redirects=False)
        assert rv.status_code == 302
        assert rv.headers.get("X-Frame-Options") == "SAMEORIGIN"


# ── Controle de acesso por perfil ─────────────────────────────────────────────

class TestControleAcessoAtendente:
    """Atendente não deve acessar rotas administrativas."""

    def test_atendente_nao_acessa_usuarios(self, client, db, auth):
        """GET /usuarios/ como atendente → redireciona (não 200)."""
        auth.login_como("atendente")
        rv = client.get("/usuarios/", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_atendente_nao_acessa_pendencias(self, client, db, auth):
        """GET /pendencias/ como atendente → redireciona (não 200)."""
        auth.login_como("atendente")
        rv = client.get("/pendencias/", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_atendente_nao_acessa_analise(self, client, db, auth):
        """GET /analise/ como atendente → redireciona (não 200)."""
        auth.login_como("atendente")
        rv = client.get("/analise/", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_atendente_nao_acessa_tabelas(self, client, db, auth):
        """GET /tabelas/ como atendente → redireciona."""
        auth.login_como("atendente")
        rv = client.get("/tabelas/", follow_redirects=False)
        assert rv.status_code in (302, 403)


class TestControleAcessoSupervisor:
    """Supervisor acessa páginas de equipe mas não configurações de admin."""

    def test_supervisor_nao_acessa_usuarios(self, client, db, auth):
        auth.login_como("supervisor")
        rv = client.get("/usuarios/", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_supervisor_acessa_analise(self, client, db, auth):
        """Supervisor tem acesso ao módulo de análise."""
        auth.login_como("supervisor")
        rv = client.get("/analise/", follow_redirects=False)
        # Supervisor pode ver /analise/
        assert rv.status_code == 200

    def test_supervisor_acessa_relatorios(self, client, db, auth):
        auth.login_como("supervisor")
        rv = client.get("/relatorios/", follow_redirects=False)
        assert rv.status_code == 200


class TestControleAcessoAdmin:
    """Administrador tem acesso a todas as rotas."""

    def test_admin_acessa_usuarios(self, client, db, auth):
        auth.login_como("administrador")
        rv = client.get("/usuarios/", follow_redirects=False)
        assert rv.status_code == 200

    def test_admin_acessa_pendencias(self, client, db, auth):
        auth.login_como("administrador")
        rv = client.get("/pendencias/", follow_redirects=False)
        assert rv.status_code == 200

    def test_admin_acessa_analise(self, client, db, auth):
        auth.login_como("administrador")
        rv = client.get("/analise/", follow_redirects=False)
        assert rv.status_code == 200


# ── Autorização em operações específicas ──────────────────────────────────────

class TestAutorizacaoStatusSolicitacao:
    """Atendente não pode Aprovar nem Recusar — apenas Pendente e Em Análise."""

    def _criar_solicitacao_para(self, usuario):
        """Cria solicitação vinculada ao usuário dado."""
        p = PessoaFactory.create()
        tipo = __import__('app.models', fromlist=['TipoSolicitacao']).TipoSolicitacao.query.first()
        status_pend = Status.query.filter_by(descricao="Pendente").first()
        from app.models import Solicitacao
        from datetime import date
        from app import db as _db
        sol = Solicitacao(
            data_solicitacao=date.today(),
            id_usuario=usuario.id,
            id_pessoa=p.id,
            id_tipo_solicitacao=tipo.id,
            id_status=status_pend.id,
            exclusao_pendente=False,
        )
        _db.session.add(sol)
        _db.session.commit()
        return sol

    def test_atendente_nao_pode_aprovar(self, client, db, auth):
        """POST /{id}/status com Aprovado como atendente → 403."""
        u = auth.login_como("atendente")
        sol = self._criar_solicitacao_para(u)
        status_aprov = Status.query.filter_by(descricao="Aprovado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_aprov.id},
        )
        assert rv.status_code == 403
        data = rv.get_json()
        assert data["ok"] is False

    def test_atendente_nao_pode_recusar(self, client, db, auth):
        """POST /{id}/status com Recusado como atendente → 403."""
        u = auth.login_como("atendente")
        sol = self._criar_solicitacao_para(u)
        status_recus = Status.query.filter_by(descricao="Recusado").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_recus.id},
        )
        assert rv.status_code == 403

    def test_atendente_pode_mudar_para_em_analise(self, client, db, auth):
        """Atendente SÍ pode mover para Em Análise."""
        u = auth.login_como("atendente")
        sol = self._criar_solicitacao_para(u)
        status_analise = Status.query.filter_by(descricao="Em Análise").first()

        rv = client.post(
            f"/solicitacoes/{sol.id}/status",
            data={"id_status": status_analise.id},
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["ok"] is True


class TestAutorizacaoExclusaoAtendimento:
    """Excluir atendimento é exclusivo do administrador.

    Os demais perfis devem usar o fluxo de pendências. A proteção é imposta no
    backend, não só escondendo o botão na interface.
    """

    def test_admin_pode_excluir(self, client, db, auth):
        """POST /atendimentos/<id>/remover como admin → registro é removido."""
        auth.login_como("administrador")
        atend = AtendimentoFactory.create()
        atend_id = atend.id

        rv = client.post(f"/atendimentos/{atend_id}/remover",
                         follow_redirects=False)

        assert rv.status_code == 302
        assert db.session.get(Atendimento, atend_id) is None

    def test_supervisor_nao_pode_excluir(self, client, db, auth):
        """Supervisor é bloqueado e o atendimento permanece no banco."""
        auth.login_como("supervisor")
        atend = AtendimentoFactory.create()
        atend_id = atend.id

        rv = client.post(f"/atendimentos/{atend_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Atendimento, atend_id) is not None

    def test_atendente_nao_pode_excluir(self, client, db, auth):
        """Atendente é bloqueado e o atendimento permanece no banco."""
        auth.login_como("atendente")
        atend = AtendimentoFactory.create()
        atend_id = atend.id

        rv = client.post(f"/atendimentos/{atend_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Atendimento, atend_id) is not None

    def test_atendente_nao_exclui_nem_o_proprio(self, client, db, auth):
        """Nem sobre o próprio atendimento o atendente tem permissão de exclusão."""
        u = auth.login_como("atendente")
        atend = AtendimentoFactory.create(id_usuario=u.id)
        atend_id = atend.id

        rv = client.post(f"/atendimentos/{atend_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Atendimento, atend_id) is not None


class TestAutorizacaoExclusaoSolicitacao:
    """Excluir solicitação é exclusivo do administrador."""

    def test_admin_pode_excluir(self, client, db, auth):
        """POST /solicitacoes/<id>/remover como admin → registro é removido."""
        auth.login_como("administrador")
        sol = SolicitacaoFactory.create()
        sol_id = sol.id

        rv = client.post(f"/solicitacoes/{sol_id}/remover",
                         follow_redirects=False)

        assert rv.status_code == 302
        assert db.session.get(Solicitacao, sol_id) is None

    def test_supervisor_nao_pode_excluir(self, client, db, auth):
        """Supervisor é bloqueado e a solicitação permanece no banco."""
        auth.login_como("supervisor")
        sol = SolicitacaoFactory.create()
        sol_id = sol.id

        rv = client.post(f"/solicitacoes/{sol_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Solicitacao, sol_id) is not None

    def test_atendente_nao_pode_excluir(self, client, db, auth):
        """Atendente é bloqueado e a solicitação permanece no banco."""
        auth.login_como("atendente")
        sol = SolicitacaoFactory.create()
        sol_id = sol.id

        rv = client.post(f"/solicitacoes/{sol_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Solicitacao, sol_id) is not None

    def test_atendente_nao_exclui_nem_a_propria(self, client, db, auth):
        """Nem sobre a própria solicitação o atendente tem permissão de exclusão."""
        u = auth.login_como("atendente")
        sol = SolicitacaoFactory.create(id_usuario=u.id)
        sol_id = sol.id

        rv = client.post(f"/solicitacoes/{sol_id}/remover",
                         follow_redirects=False)

        assert rv.status_code in (302, 403)
        assert db.session.get(Solicitacao, sol_id) is not None


class TestAcessoIndiceRelatorios:
    """/relatorios/ é função de gestão — administrador e supervisor apenas."""

    def test_admin_acessa(self, client, db, auth):
        auth.login_como("administrador")
        rv = client.get("/relatorios/", follow_redirects=False)
        assert rv.status_code == 200

    def test_supervisor_acessa(self, client, db, auth):
        auth.login_como("supervisor")
        rv = client.get("/relatorios/", follow_redirects=False)
        assert rv.status_code == 200

    def test_atendente_nao_acessa(self, client, db, auth):
        """Atendente é redirecionado para o próprio desempenho."""
        u = auth.login_como("atendente")
        rv = client.get("/relatorios/", follow_redirects=False)
        assert rv.status_code == 302
        assert f"/relatorios/desempenho/{u.id}" in rv.headers["Location"]


# ── Autorização horizontal (propriedade do registro) ──────────────────────────

class TestEscopoEdicaoAtendimento:
    """Editar atendimento segue o mesmo escopo da listagem.

    O usuário só edita o que já poderia ver — o id na URL não basta.
    """

    def test_admin_edita_de_qualquer_um(self, client, db, auth):
        """Administrador não é restringido por propriedade."""
        auth.login_como("administrador")
        outro = criar_usuario("atendente", login="dono_atend_1")
        atend = AtendimentoFactory.create(id_usuario=outro.id)

        rv = client.get(f"/atendimentos/{atend.id}/editar", follow_redirects=False)
        assert rv.status_code == 200

    def test_atendente_edita_o_proprio(self, client, db, auth):
        """Atendente acessa a edição do atendimento que ele criou."""
        u = auth.login_como("atendente")
        atend = AtendimentoFactory.create(id_usuario=u.id)

        rv = client.get(f"/atendimentos/{atend.id}/editar", follow_redirects=False)
        assert rv.status_code == 200

    def test_atendente_nao_edita_de_outro(self, client, db, auth):
        """GET da edição de atendimento alheio → bloqueado."""
        auth.login_como("atendente")
        outro = criar_usuario("atendente", login="dono_atend_2")
        atend = AtendimentoFactory.create(id_usuario=outro.id)

        rv = client.get(f"/atendimentos/{atend.id}/editar", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_post_de_outro_nao_altera_o_registro(self, client, db, auth):
        """POST bloqueado não pode alterar o atendimento-alvo."""
        auth.login_como("atendente")
        outro = criar_usuario("atendente", login="dono_atend_3")
        atend = AtendimentoFactory.create(id_usuario=outro.id)
        atend_id, obs_antes = atend.id, atend.observacao

        rv = client.post(
            f"/atendimentos/{atend_id}/editar",
            data={"observacao": "INVADIDO"},
            follow_redirects=False,
        )

        assert rv.status_code in (302, 403)
        db.session.expire_all()
        assert db.session.get(Atendimento, atend_id).observacao == obs_antes


class TestEscopoEdicaoSolicitacao:
    """Editar solicitação segue o mesmo escopo da listagem."""

    def test_admin_edita_de_qualquer_um(self, client, db, auth):
        auth.login_como("administrador")
        outro = criar_usuario("atendente", login="dono_sol_1")
        sol = SolicitacaoFactory.create(id_usuario=outro.id)

        rv = client.get(f"/solicitacoes/{sol.id}/editar", follow_redirects=False)
        assert rv.status_code == 200

    def test_atendente_edita_a_propria(self, client, db, auth):
        u = auth.login_como("atendente")
        sol = SolicitacaoFactory.create(id_usuario=u.id)

        rv = client.get(f"/solicitacoes/{sol.id}/editar", follow_redirects=False)
        assert rv.status_code == 200

    def test_atendente_nao_edita_de_outro(self, client, db, auth):
        auth.login_como("atendente")
        outro = criar_usuario("atendente", login="dono_sol_2")
        sol = SolicitacaoFactory.create(id_usuario=outro.id)

        rv = client.get(f"/solicitacoes/{sol.id}/editar", follow_redirects=False)
        assert rv.status_code in (302, 403)

    def test_post_de_outro_nao_altera_o_registro(self, client, db, auth):
        """POST bloqueado não pode alterar a solicitação-alvo."""
        auth.login_como("atendente")
        outro = criar_usuario("atendente", login="dono_sol_3")
        sol = SolicitacaoFactory.create(id_usuario=outro.id)
        sol_id, obs_antes = sol.id, sol.observacao

        rv = client.post(
            f"/solicitacoes/{sol_id}/editar",
            data={"observacao": "INVADIDO"},
            follow_redirects=False,
        )

        assert rv.status_code in (302, 403)
        db.session.expire_all()
        assert db.session.get(Solicitacao, sol_id).observacao == obs_antes


# ── Remoção de documento: perfil + exclusão lógica ────────────────────────────

class TestRemocaoDocumento:
    """Remover documento é exclusivo do administrador e é exclusão lógica."""

    def _criar_documento(self):
        """Cria um documento ativo e não removido."""
        from app import db as _db
        p = PessoaFactory.create()
        doc = DocumentoPessoa(
            id_pessoa=p.id,
            tipo="rg_cnh",
            arquivo="rg_cnh_teste.pdf",
            ativo=True,
        )
        _db.session.add(doc)
        _db.session.commit()
        return doc

    def test_admin_remove_logicamente(self, client, db, auth):
        """Admin remove: a linha PERMANECE no banco, com removido_em marcado."""
        u = auth.login_como("administrador")
        doc = self._criar_documento()
        doc_id = doc.id

        rv = client.post(f"/documentos/remover/{doc_id}", follow_redirects=False)

        assert rv.status_code == 302
        db.session.expire_all()
        persistido = db.session.get(DocumentoPessoa, doc_id)
        assert persistido is not None, "soft-delete não deve apagar a linha"
        assert persistido.removido_em is not None
        assert persistido.removido_por == u.id

    def test_atendente_nao_remove(self, client, db, auth):
        auth.login_como("atendente")
        doc = self._criar_documento()
        doc_id = doc.id

        rv = client.post(f"/documentos/remover/{doc_id}", follow_redirects=False)

        assert rv.status_code in (302, 403)
        db.session.expire_all()
        assert db.session.get(DocumentoPessoa, doc_id).removido_em is None

    def test_supervisor_nao_remove(self, client, db, auth):
        auth.login_como("supervisor")
        doc = self._criar_documento()
        doc_id = doc.id

        rv = client.post(f"/documentos/remover/{doc_id}", follow_redirects=False)

        assert rv.status_code in (302, 403)
        db.session.expire_all()
        assert db.session.get(DocumentoPessoa, doc_id).removido_em is None

    def test_removido_some_de_documentos_visiveis(self, client, db, auth):
        """Após a remoção, o documento não aparece na coleção de exibição."""
        auth.login_como("administrador")
        doc = self._criar_documento()
        doc_id, pessoa = doc.id, doc.pessoa

        assert doc_id in [d.id for d in pessoa.documentos_visiveis]

        client.post(f"/documentos/remover/{doc_id}", follow_redirects=False)

        db.session.expire_all()
        pessoa = db.session.get(type(pessoa), pessoa.id)
        assert doc_id not in [d.id for d in pessoa.documentos_visiveis]
        assert doc_id in [d.id for d in pessoa.documentos], \
            "a linha continua existindo — só não é exibida"

    def test_removido_retorna_404_em_ver_e_baixar(self, client, db, auth):
        """Documento removido não pode mais ser aberto nem baixado."""
        auth.login_como("administrador")
        doc = self._criar_documento()
        doc_id = doc.id

        client.post(f"/documentos/remover/{doc_id}", follow_redirects=False)

        assert client.get(f"/documentos/ver/{doc_id}").status_code == 404
        assert client.get(f"/documentos/baixar/{doc_id}").status_code == 404


# ── Exclusão lógica de cadastro ───────────────────────────────────────────────

class TestSoftDeleteCadastro:
    """Exclusão de cadastro é lógica, e os dois caminhos convergem.

    O histórico vinculado permanece intacto e continua contando nos
    relatórios — o trabalho da Sala não é apagado quando o empreendedor
    exerce direito de exclusão.
    """

    def _pessoa_com_historico(self, nome=None):
        """Pessoa com 1 atendimento e 1 solicitação vinculados.

        `nome` sem dígitos permite testar a busca global no SQLite: com
        dígitos, a busca entra no ramo que usa `regexp_replace`, função
        que só existe no PostgreSQL.
        """
        from app import db as _db
        p = PessoaFactory.create()
        if nome:
            p.nome_razao_social = nome
        atend = AtendimentoFactory.create(id_pessoa=p.id)
        sol = SolicitacaoFactory.create(id_pessoa=p.id)
        _db.session.commit()
        return p, atend, sol

    def _flush_flash(self, client):
        """Consome a mensagem de flash pendente.

        Sem isso, o nome da pessoa aparece na página seguinte pela própria
        mensagem de sucesso ("Pessoa X removida"), e não pelo conteúdo que
        se quer testar.
        """
        client.get("/dashboard")

    def _pendencia_para(self, pessoa, solicitante):
        from app import db as _db
        pend = SolicitacaoExclusao(
            entidade="cadastro",
            entidade_id=pessoa.id,
            entidade_desc=pessoa.nome_razao_social,
            id_usuario_solicitante=solicitante.id,
            status="pendente",
        )
        _db.session.add(pend)
        _db.session.commit()
        return pend

    # ── O caso que antes quebrava com IntegrityError ──────────────────────

    def test_aprovar_pendencia_de_cadastro_com_historico(self, client, db, auth):
        """Aprovar exclusão de cadastro COM histórico não quebra e é lógica.

        Antes do ciclo 11 esta rota levantava IntegrityError
        (NotNullViolation em atendimento.id_pessoa).
        """
        admin = auth.login_como("administrador")
        pessoa, atend, sol = self._pessoa_com_historico()
        pid, aid, sid = pessoa.id, atend.id, sol.id
        pend = self._pendencia_para(pessoa, admin)

        rv = client.post(f"/pendencias/{pend.id}/aprovar", follow_redirects=False)

        assert rv.status_code == 302
        db.session.expire_all()

        persistida = db.session.get(Pessoa, pid)
        assert persistida is not None, "soft-delete não apaga a linha"
        assert persistida.removido_em is not None
        assert persistida.removido_por == admin.id

        # O histórico permanece intacto
        assert db.session.get(Atendimento, aid) is not None
        assert db.session.get(Solicitacao, sid) is not None

    def test_exclusao_direta_de_cadastro_com_historico(self, client, db, auth):
        """pessoas.remover converge para o mesmo comportamento.

        Antes do ciclo 11 esta rota BLOQUEAVA quando havia histórico.
        """
        admin = auth.login_como("administrador")
        pessoa, atend, sol = self._pessoa_com_historico()
        pid, aid, sid = pessoa.id, atend.id, sol.id

        rv = client.post(f"/pessoas/{pid}/remover", follow_redirects=False)

        assert rv.status_code == 302
        db.session.expire_all()

        persistida = db.session.get(Pessoa, pid)
        assert persistida is not None
        assert persistida.removido_em is not None
        assert persistida.removido_por == admin.id
        assert db.session.get(Atendimento, aid) is not None
        assert db.session.get(Solicitacao, sid) is not None

    # ── Some do operacional ───────────────────────────────────────────────

    def test_removido_nao_aparece_na_lista(self, client, db, auth):
        auth.login_como("administrador")
        pessoa, _, _ = self._pessoa_com_historico(nome="Zetta Comercio Ltda")
        nome, pid = pessoa.nome_razao_social, pessoa.id

        assert nome in client.get("/pessoas/").get_data(as_text=True)

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        self._flush_flash(client)

        assert nome not in client.get("/pessoas/").get_data(as_text=True)

    def test_removido_nao_aparece_na_busca_global(self, client, db, auth):
        """Confere o LINK do resultado, não o nome — a busca ecoa o termo
        digitado no campo do topbar, o que daria falso positivo."""
        auth.login_como("administrador")
        pessoa, _, _ = self._pessoa_com_historico(nome="Zetta Comercio Ltda")
        nome, pid = pessoa.nome_razao_social, pessoa.id
        link = f'/pessoas/{pid}"'

        assert link in client.get(f"/busca?q={nome}").get_data(as_text=True)

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        self._flush_flash(client)

        assert link not in client.get(f"/busca?q={nome}").get_data(as_text=True)

    def test_removido_nao_aparece_na_selecao_de_novo_atendimento(self, client, db, auth):
        """A pessoa some do dropdown de seleção ao criar atendimento."""
        auth.login_como("administrador")
        pessoa, _, _ = self._pessoa_com_historico(nome="Zetta Comercio Ltda")
        nome, pid = pessoa.nome_razao_social, pessoa.id

        assert nome in client.get("/atendimentos/novo").get_data(as_text=True)

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        self._flush_flash(client)

        assert nome not in client.get("/atendimentos/novo").get_data(as_text=True)

    def test_ficha_do_removido_nao_abre(self, client, db, auth):
        auth.login_como("administrador")
        pessoa, _, _ = self._pessoa_com_historico()
        pid = pessoa.id

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)

        rv = client.get(f"/pessoas/{pid}", follow_redirects=False)
        assert rv.status_code == 302

    # ── PERMANECE nas agregações ──────────────────────────────────────────

    def test_atendimento_de_removido_ainda_conta_em_relatorio(self, client, db, auth):
        """O trabalho realizado permanece contado após a exclusão do cadastro."""
        from app.routes.relatorios.queries import atendimentos_por_periodo
        from datetime import date, timedelta

        auth.login_como("administrador")
        pessoa, atend, _ = self._pessoa_com_historico()
        pid = pessoa.id
        ini, fim = date.today() - timedelta(days=1), date.today() + timedelta(days=1)

        antes = atendimentos_por_periodo(ini, fim)
        total_antes = len(antes) if isinstance(antes, list) else antes

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        db.session.expire_all()

        depois = atendimentos_por_periodo(ini, fim)
        total_depois = len(depois) if isinstance(depois, list) else depois

        assert total_depois == total_antes, \
            "atendimento de cadastro removido deve continuar contando"

    def test_atendimento_de_removido_permanece_vinculado(self, client, db, auth):
        """A FK continua apontando para a pessoa — nada é desvinculado."""
        auth.login_como("administrador")
        pessoa, atend, _ = self._pessoa_com_historico()
        pid, aid = pessoa.id, atend.id

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        db.session.expire_all()

        assert db.session.get(Atendimento, aid).id_pessoa == pid

    # ── Idempotência e permissão ──────────────────────────────────────────

    def test_remover_duas_vezes_nao_regrava_a_data(self, client, db, auth):
        auth.login_como("administrador")
        pessoa, _, _ = self._pessoa_com_historico()
        pid = pessoa.id

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        db.session.expire_all()
        primeira = db.session.get(Pessoa, pid).removido_em

        client.post(f"/pessoas/{pid}/remover", follow_redirects=False)
        db.session.expire_all()
        assert db.session.get(Pessoa, pid).removido_em == primeira

    def test_atendente_nao_remove_cadastro(self, client, db, auth):
        """Continua admin-only — não regrediu."""
        auth.login_como("atendente")
        pessoa, _, _ = self._pessoa_com_historico()
        pid = pessoa.id

        rv = client.post(f"/pessoas/{pid}/remover", follow_redirects=False)

        assert rv.status_code in (302, 403)
        db.session.expire_all()
        assert db.session.get(Pessoa, pid).removido_em is None


# ── CSRF ──────────────────────────────────────────────────────────────────────

class TestCSRF:
    """CSRF está desabilitado em testes (WTF_CSRF_ENABLED=False).
       Verificamos que a config de teste foi aplicada corretamente."""

    def test_csrf_desabilitado_em_testes(self, app):
        """WTF_CSRF_ENABLED deve ser False na config de testes."""
        assert app.config["WTF_CSRF_ENABLED"] is False

    def test_post_sem_token_aceito_em_testes(self, client, db):
        """Em testes, POST sem csrf_token não é bloqueado."""
        rv = client.post("/login", data={"login": "x", "senha": "x"})
        # Não deve retornar 400 por CSRF (pode retornar 200 por credencial errada)
        assert rv.status_code != 400

    def test_meta_csrf_token_presente_em_paginas_autenticadas(self, client, db, auth):
        """Meta tag csrf-token deve estar no HTML de páginas autenticadas."""
        auth.login_como("atendente")
        rv = client.get("/pessoas/")
        assert b'name="csrf-token"' in rv.data
