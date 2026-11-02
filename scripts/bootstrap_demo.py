"""
bootstrap_demo.py
Prepara um banco vazio para a demonstração pública: cria as tabelas, insere
as tabelas de apoio (serviços, canais, status…), os usuários de demonstração
e gera os dados fictícios. Idempotente: se já houver usuários, não faz nada.

Uso:
    DATABASE_URL=sqlite:///demo.db python scripts/bootstrap_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    PerfilAcesso, Usuario, Status, TipoSolicitacao, CanalAtendimento, Servico,
    Evento, Atividade, TagInteresse,
)

SENHA_DEMO = os.environ.get('DEMO_PASSWORD', 'demo1234')

SERVICOS = [
    ('Abertura de MEI', 'nao_mei', 'https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/quero-ser-mei'),
    ('Boleto DAS', 'mei', 'https://www8.receita.fazenda.gov.br/simplesnacional/aplicacoes/atspo/pgmei.app/identificacao'),
    ('Parcelamento DAS', 'mei', 'https://www8.receita.fazenda.gov.br/SimplesNacional/Servicos/Grupo.aspx?grp=19'),
    ('Baixa de MEI', 'mei', 'https://mei.receita.economia.gov.br/baixa/login'),
    ('Emissão de Documento', 'mei', 'https://mei.receita.economia.gov.br/certificado/login'),
    ('Consulta Cadastral', 'mei', 'https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj='),
    ('Declaração Anual (DASN-SIMEI)', 'mei', 'https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/dasnsimei.app/Identificacao'),
    ('Alterar Dados do MEI', 'mei', 'https://mei.receita.economia.gov.br/alteracao/acesso'),
    ('Regularizar Débitos', 'mei', 'https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/verificar-debitos-do-mei'),
    ('Orientação ao Empreendedor', 'todos', None),
    ('Cadastro de Box/Quiosque', 'todos', None),
    ('Solicitação', 'todos', None),
]
CANAIS = ['Presencial', 'Telefone', 'E-mail', 'WhatsApp']
STATUS = ['Pendente', 'Em Análise', 'Aprovado', 'Recusado']
TIPOS_SOLIC = ['Credenciamento em Feira', 'Cadastro de Box/Quiosque', 'Requerimento Geral', 'Orientação Geral']
EVENTOS = ['Feira do Empreendedor', 'Feira de Artesanato', 'Festival Gastronômico', 'Feira de Natal']
ATIVIDADES = ['Alimentação', 'Artesanato', 'Vestuário e acessórios', 'Beleza e estética',
              'Comércio varejista', 'Serviços gerais']
TAGS = ['Feira/Evento', 'Box/Mercado', 'Espaço Público', 'MEI', 'Crédito/Financiamento',
        'Orientação Fiscal', 'Outros']

# login, nome, perfil (todos fictícios)
USUARIOS = [
    ('admin', 'Ana Lima', 'administrador'),
    ('supervisor', 'Carla Mendes', 'supervisor'),
    ('atendente', 'Bruno Costa', 'atendente'),
    ('juliana', 'Juliana Alves', 'atendente'),
    ('rafael', 'Rafael Souza', 'atendente'),
    ('marina', 'Marina Rocha', 'atendente'),
]


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        if Usuario.query.first():
            print('Banco já preparado — nada a fazer.')
            return

        perfis = {}
        for nome in ('administrador', 'supervisor', 'atendente'):
            perfis[nome] = PerfilAcesso(nome=nome, descricao=nome.capitalize())
            db.session.add(perfis[nome])
        for d in STATUS:
            db.session.add(Status(descricao=d))
        for d in TIPOS_SOLIC:
            db.session.add(TipoSolicitacao(descricao=d, ativo=True, protegido=True))
        for d in CANAIS:
            db.session.add(CanalAtendimento(descricao=d, ativo=True, protegido=True))
        for d, aplic, link in SERVICOS:
            db.session.add(Servico(descricao=d, aplicabilidade=aplic, link_portal=link,
                                   ativo=True, protegido=True))
        for d in EVENTOS:
            db.session.add(Evento(descricao=d))
        for d in ATIVIDADES:
            db.session.add(Atividade(descricao=d))
        for d in TAGS:
            db.session.add(TagInteresse(descricao=d, ativo=True, protegido=True))
        db.session.flush()

        hash_demo = generate_password_hash(SENHA_DEMO)
        criados = {}
        for login, nome, perfil in USUARIOS:
            u = Usuario(login=login, nome=nome, senha=hash_demo, ativo=True, id_perfil=perfis[perfil].id)
            db.session.add(u)
            criados[login] = u
        db.session.flush()
        for login, _, perfil in USUARIOS:
            if perfil == 'atendente':
                criados[login].supervisor_id = criados['supervisor'].id
        db.session.commit()
        print('Tabelas de apoio e usuários de demonstração criados.')

    import gerar_dados_ficticios
    gerar_dados_ficticios.main()


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
