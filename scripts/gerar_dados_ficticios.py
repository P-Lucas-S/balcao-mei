"""
gerar_dados_ficticios.py  —  v2.0
Gera dados fictícios de demonstração para o Balcão MEI:
  400 pessoas, ~800 atendimentos, 250 solicitações,
  220+ logs, 60 requerimentos, 2 parâmetros municipais.

Distribuídos de jan/2025 a mai/2026 com sazonalidade realista.
Idempotente: limpa dados fictícios antes de cada execução.

Uso:
    python -X utf8 scripts/gerar_dados_ficticios.py
"""

import sys
import os
import random
from datetime import date, timedelta, datetime, time as dt_time, timezone
from sqlalchemy import text, func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db, marca
from app.models import (
    Pessoa, Atendimento, AtendimentoServico,
    Solicitacao, Status, LogAcao,
    RequerimentoGerado, ParametroMunicipio,
    Servico, CanalAtendimento, TipoSolicitacao, Evento, Atividade, Usuario,
    TagInteresse,
)

# ── Configuração ───────────────────────────────────────────────────────────────
SEED              = 42
DATA_INICIO       = date(2025, 1, 2)
DATA_FIM          = date(2026, 5, 9)
LOTE              = 50
META_PESSOAS      = 400
META_ATENDIMENTOS = 800
META_SOLICITACOES = 250
META_LOGS         = 220
META_REQUERIMENTOS = 60

# ── Listas de nomes e dados geográficos ───────────────────────────────────────
NOMES_MASCULINOS = [
    'João', 'José', 'Francisco', 'Carlos', 'Antônio', 'Paulo', 'Pedro',
    'Lucas', 'Luiz', 'Marcos', 'Gabriel', 'Rafael', 'Daniel', 'Marcelo',
    'Bruno', 'Eduardo', 'Felipe', 'Raimundo', 'Manoel', 'Geraldo',
    'Cícero', 'Aldenir', 'Robson', 'Welton', 'Edilson', 'Gilberto',
    'Ronaldo', 'Vanderlei', 'Adriano', 'Reinaldo', 'Sandro', 'Fábio',
    'Leandro', 'Diego', 'Thiago', 'Anderson', 'Rodrigo', 'Cleiton',
]
NOMES_FEMININOS = [
    'Maria', 'Ana', 'Francisca', 'Antônia', 'Adriana', 'Juliana',
    'Márcia', 'Fernanda', 'Patrícia', 'Aline', 'Sandra', 'Camila',
    'Amanda', 'Bruna', 'Jessica', 'Letícia', 'Vanessa', 'Simone',
    'Rosana', 'Luciana', 'Edilene', 'Cláudia', 'Sueli', 'Débora',
    'Renata', 'Tatiana', 'Viviane', 'Cristiane', 'Eliane', 'Soraia',
    'Gleice', 'Valdirene', 'Neuza', 'Solange', 'Célia', 'Fátima',
]
SOBRENOMES = [
    'Silva', 'Santos', 'Oliveira', 'Souza', 'Lima', 'Pereira', 'Costa',
    'Ferreira', 'Rodrigues', 'Almeida', 'Nascimento', 'Carvalho', 'Gomes',
    'Martins', 'Araújo', 'Melo', 'Barbosa', 'Ribeiro', 'Moura', 'Cavalcante',
    'Lopes', 'Freitas', 'Nunes', 'Moreira', 'Dias', 'Castro', 'Rocha',
    'Monteiro', 'Cardoso', 'Vieira', 'Mendes', 'Pinheiro', 'Vasconcelos',
    'Macedo', 'Bezerra', 'Nogueira', 'Farias', 'Batista', 'Medeiros',
    'Cunha', 'Teixeira', 'Andrade', 'Queiroz', 'Xavier', 'Pinto',
]

BAIRROS = list(marca.BAIRROS)
# bairros do início da lista concentram mais cadastros
PESOS_BAIRROS = [len(BAIRROS) - i for i in range(len(BAIRROS))]

LOGRADOUROS = ['Rua', 'Rua', 'Rua', 'Avenida', 'Travessa', 'Alameda', 'Estrada']

CNAE_MEI = [
    '4712-1/00', '5611-2/01', '5612-1/00', '4781-4/00',
    '4782-2/01', '7410-2/01', '8623-2/06', '4771-7/01',
    '5620-1/01', '9602-5/01', '9601-7/01', '4330-4/05',
    '6201-5/01', '7711-0/00', '4399-1/03',
]

NIVEL_ESCOLAR_OPTS = [
    ('Fundamental incompleto', 0.15),
    ('Fundamental completo',   0.20),
    ('Médio incompleto',       0.15),
    ('Médio completo',         0.30),
    ('Superior incompleto',    0.10),
    ('Superior completo',      0.08),
    ('Pós-graduação',          0.02),
]
RENDA_FAMILIAR_OPTS = [
    ('Até 1 salário mínimo',        0.25),
    ('1 a 2 salários mínimos',      0.35),
    ('2 a 3 salários mínimos',      0.25),
    ('3 a 5 salários mínimos',      0.10),
    ('Acima de 5 salários mínimos', 0.05),
]
SITUACAO_CADASTRAL_OPTS = [
    ('ATIVA',   0.80),
    ('BAIXADA', 0.15),
    ('INAPTA',  0.05),
]

MOTIVOS_RECUSA = [
    'Documentação incompleta.',
    'Requisitos não atendidos para o tipo de solicitação.',
    'Solicitação duplicada — já existe processo aberto.',
    'Local solicitado indisponível na data informada.',
    'Solicitante não está em conformidade com a legislação vigente.',
    'Inconsistência nas informações cadastrais.',
    'Capacidade de atendimento esgotada para este período.',
    'Prazo para solicitação encerrado.',
]
DESCRICOES_SOLIC = [
    'Solicito análise e aprovação conforme documentação em anexo.',
    'Requerimento para regularização junto aos órgãos competentes.',
    'Solicitação de informações sobre processo de credenciamento.',
    'Pedido de agendamento para orientação sobre abertura de negócio.',
    'Solicitação de apoio para participação em evento municipal.',
    'Solicito orientação para emissão de documentos necessários.',
    'Pedido de apoio para formalização de atividade econômica.',
]


# ── Geradores ─────────────────────────────────────────────────────────────────

def _gerar_cpf():
    """CPF válido com dígitos verificadores corretos."""
    n = [random.randint(0, 9) for _ in range(9)]
    s1 = sum((10 - i) * n[i] for i in range(9))
    r1 = s1 % 11
    d1 = 0 if r1 < 2 else 11 - r1
    n.append(d1)
    s2 = sum((11 - i) * n[i] for i in range(10))
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    n.append(d2)
    return (f"{''.join(map(str, n[:3]))}."
            f"{''.join(map(str, n[3:6]))}."
            f"{''.join(map(str, n[6:9]))}-"
            f"{n[9]}{n[10]}")


def _gerar_cnpj():
    """CNPJ válido no formato MEI (filial 0001)."""
    n = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(n[i] * p1[i] for i in range(12))
    r1 = s1 % 11
    d1 = 0 if r1 < 2 else 11 - r1
    n.append(d1)
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(n[i] * p2[i] for i in range(13))
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    n.append(d2)
    return (f"{''.join(map(str, n[:2]))}."
            f"{''.join(map(str, n[2:5]))}."
            f"{''.join(map(str, n[5:8]))}/"
            f"{''.join(map(str, n[8:12]))}-"
            f"{''.join(map(str, n[12:]))}")


def _wpick(opts):
    """Escolhe aleatoriamente de lista de (item, peso)."""
    itens, pesos = zip(*opts)
    return random.choices(itens, weights=pesos, k=1)[0]


def _peso_mensal(d):
    """Peso sazonal de atendimentos por mês."""
    return {
        1: 0.75, 2: 0.95, 3: 1.15, 4: 0.90,
        5: 1.10, 6: 1.45, 7: 1.20, 8: 0.85,
        9: 1.05, 10: 0.90, 11: 1.05, 12: 1.30,
    }.get(d.month, 1.0)


def _data_aleatoria(inicio=None, fim=None, peso=True):
    inicio = inicio or DATA_INICIO
    fim    = fim    or DATA_FIM
    delta  = (fim - inicio).days
    for _ in range(2000):
        d = inicio + timedelta(days=random.randint(0, delta))
        if d.weekday() < 5:
            if not peso or random.random() < _peso_mensal(d):
                return d
    return inicio + timedelta(days=random.randint(0, delta))


def _hora():
    return dt_time(random.randint(8, 16), random.choice([0, 15, 30, 45]))


def _dt(d):
    """Date → datetime UTC com hora aleatória de expediente."""
    return datetime(d.year, d.month, d.day,
                    random.randint(7, 18), random.randint(0, 59),
                    tzinfo=timezone.utc)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    random.seed(SEED)
    app = create_app()

    with app.app_context():
        print('=== Balcão MEI — Gerador de Dados Fictícios v2.0 ===')
        print()

        # ── 1. Carregar referências do banco ──────────────────────────────────
        print('[1/10] Carregando referências do banco...')

        tipos_atend  = Servico.query.filter_by(ativo=True).all()
        canais       = CanalAtendimento.query.filter_by(ativo=True).all()
        tipos_solic  = TipoSolicitacao.query.filter_by(ativo=True).all()
        todos_status = Status.query.all()
        eventos      = Evento.query.all()
        atividades   = Atividade.query.all()

        if not tipos_atend:
            sys.exit('ERRO: tipo_atendimento vazio.')
        if not tipos_solic:
            sys.exit('ERRO: tipo_solicitacao vazio.')

        t_atend_ids = [t.id for t in tipos_atend]
        canal_ids   = [c.id for c in canais]
        if not canal_ids:
            sys.exit('ERRO: canal_atendimento vazio.')
        # Serviços separados por aplicabilidade — quem não é MEI não recebe
        # 'Boleto DAS'; quem é MEI não recebe 'Abertura de MEI'.
        serv_mei     = [s.id for s in tipos_atend if s.aplicabilidade in ('mei', 'todos')]
        serv_nao_mei = [s.id for s in tipos_atend if s.aplicabilidade in ('nao_mei', 'todos')]
        t_solic_ids = [t.id for t in tipos_solic]
        evento_ids  = [e.id for e in eventos]
        atv_ids     = [a.id for a in atividades]

        # Mapear status para solicitações
        status_map = {}
        for s in todos_status:
            dl = s.descricao.lower().replace('á', 'a').replace('é', 'e')
            if 'pendente' in dl:
                status_map['pendente'] = s.id
            elif 'analise' in dl or 'análise' in dl:
                status_map['analise'] = s.id
            elif 'aprovado' in dl:
                status_map['aprovado'] = s.id
            elif 'recusado' in dl:
                status_map['recusado'] = s.id

        id_pendente = status_map.get('pendente')
        id_analise  = status_map.get('analise')
        id_aprovado = status_map.get('aprovado')
        id_recusado = status_map.get('recusado')

        if not all([id_pendente, id_analise, id_aprovado, id_recusado]):
            sys.exit(f'ERRO: status incompletos para solicitações: {status_map}')

        # Usuários operacionais (excluir usuários de teste)
        usuarios = (Usuario.query
                    .filter(Usuario.ativo == True,
                            ~Usuario.nome.like('Teste%'))
                    .all())
        atendentes  = [u for u in usuarios if u.perfil.nome == 'atendente']
        supervisores = [u for u in usuarios if u.perfil.nome == 'supervisor']

        if not atendentes:
            sys.exit('ERRO: nenhum atendente ativo encontrado.')

        atend_ids = [u.id for u in atendentes]
        sup_ids   = [u.id for u in supervisores]
        op_ids    = atend_ids + sup_ids  # Todos que podem criar registros

        print(f'  servico ({len(tipos_atend)}): '
              f'{[(t.id, t.descricao, t.aplicabilidade) for t in tipos_atend]}')
        print(f'  canal_atendimento ({len(canais)}): '
              f'{[(c.id, c.descricao) for c in canais]}')
        print(f'  tipo_solicitacao ({len(tipos_solic)}): '
              f'{[(t.id, t.descricao) for t in tipos_solic]}')
        print(f'  status: {status_map}')
        print(f'  eventos ({len(eventos)}): {[(e.id, e.descricao) for e in eventos]}')
        print(f'  atividades ({len(atividades)}): {[(a.id, a.descricao) for a in atividades]}')
        print(f'  atendentes: {[(u.id, u.login) for u in atendentes]}')
        print(f'  supervisores: {[(u.id, u.login) for u in supervisores]}')

        # ── 2. Limpeza idempotente ────────────────────────────────────────────
        print()
        print('[2/10] Limpando dados fictícios anteriores...')
        db.session.execute(text(
            "DELETE FROM requerimento_gerado WHERE id_pessoa IN "
            "(SELECT id FROM pessoa WHERE origem = 'dados_ficticios')"
        ))
        db.session.execute(text(
            "DELETE FROM atendimento_servico WHERE id_atendimento IN "
            "(SELECT id FROM atendimento WHERE origem = 'dados_ficticios')"
        ))
        db.session.execute(text(
            "DELETE FROM atendimento WHERE origem = 'dados_ficticios'"
        ))
        db.session.execute(text(
            "DELETE FROM solicitacao WHERE id_pessoa IN "
            "(SELECT id FROM pessoa WHERE origem = 'dados_ficticios')"
        ))
        db.session.execute(text(
            "DELETE FROM pessoa WHERE origem = 'dados_ficticios'"
        ))
        db.session.commit()
        print('  Limpeza concluída.')

        # ── 3. Pessoas (400) ──────────────────────────────────────────────────
        print()
        print('[3/10] Gerando pessoas...')

        cpfs_usados  = set()
        cnpjs_usados = set()
        pessoas_ids  = []
        lote         = []

        for i in range(META_PESSOAS):
            if random.random() < 0.50:
                primeiro, sexo = random.choice(NOMES_FEMININOS), 'F'
            else:
                primeiro, sexo = random.choice(NOMES_MASCULINOS), 'M'
            nome = f"{primeiro} {random.choice(SOBRENOMES)} {random.choice(SOBRENOMES)}"

            for _ in range(1000):
                cpf = _gerar_cpf()
                if cpf not in cpfs_usados:
                    cpfs_usados.add(cpf)
                    break

            tipo_r = random.random()
            cnpj = mei = cnae = simples = nome_fantasia = None

            if tipo_r < 0.60:          # MEI
                for _ in range(1000):
                    c = _gerar_cnpj()
                    if c not in cnpjs_usados:
                        cnpjs_usados.add(c)
                        cnpj = c
                        break
                mei           = True
                cnae          = random.choice(CNAE_MEI)
                simples       = True
                nome_fantasia = f"{random.choice(SOBRENOMES)} Comercial"
            elif tipo_r < 0.85:        # PF sem CNPJ
                mei = False
            else:                      # PJ
                for _ in range(1000):
                    c = _gerar_cnpj()
                    if c not in cnpjs_usados:
                        cnpjs_usados.add(c)
                        cnpj = c
                        break
                mei     = False
                cnae    = random.choice(CNAE_MEI)
                simples = random.random() < 0.60

            bairro = random.choices(BAIRROS, weights=PESOS_BAIRROS, k=1)[0]
            logr   = random.choice(LOGRADOUROS)
            num    = random.randint(1, 999)
            cep_n  = random.randint(80000000, 82999999)
            cep    = f"{cep_n // 1000:05d}-{cep_n % 1000:03d}"
            end    = f"{logr} {random.randint(1,99)}, Nº {num}, {bairro}, {marca.CIDADE_UF}"
            tel    = f"(41) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}"

            p = Pessoa(
                nome_razao_social   = nome,
                cpf                 = cpf,
                cnpj                = cnpj,
                sexo                = sexo,
                telefone            = tel,
                endereco            = end,
                cep                 = cep,
                bairro              = bairro,
                logradouro          = f"{logr} {random.randint(1,99)}",
                numero              = str(num),
                mei                 = mei,
                simples_nacional    = simples,
                cnae_principal      = cnae,
                nome_fantasia       = nome_fantasia,
                situacao_cadastral  = _wpick(SITUACAO_CADASTRAL_OPTS),
                nivel_escolar       = _wpick(NIVEL_ESCOLAR_OPTS),
                num_membros_familia = random.randint(1, 6),
                renda_familiar      = _wpick(RENDA_FAMILIAR_OPTS),
                origem              = 'dados_ficticios',
                id_usuario_criador  = random.choice(atend_ids),
                exclusao_pendente   = False,
            )
            lote.append(p)

            if len(lote) >= LOTE:
                db.session.add_all(lote)
                db.session.flush()
                pessoas_ids.extend(obj.id for obj in lote)
                db.session.commit()
                print(f'  {len(pessoas_ids)}/{META_PESSOAS} pessoas...')
                lote.clear()

        if lote:
            db.session.add_all(lote)
            db.session.flush()
            pessoas_ids.extend(obj.id for obj in lote)
            db.session.commit()

        print(f'  OK: {len(pessoas_ids)} pessoas criadas.')

        # ── 4. Atendimentos (~800) ────────────────────────────────────────────
        print()
        print('[4/10] Gerando atendimentos...')

        # 80% das pessoas recebem atendimento
        pessoas_com_atend = random.sample(pessoas_ids, k=int(0.80 * len(pessoas_ids)))

        total_atend = 0
        lote_atend  = []

        # Quem é MEI define quais serviços fazem sentido
        meis = {r[0] for r in db.session.query(Pessoa.id).filter(Pessoa.mei.is_(True)).all()}

        for pid in pessoas_com_atend:
            pool_serv = serv_mei if pid in meis else serv_nao_mei
            # Distribuição de frequência: retorno realista
            n_a = random.choices(
                [1, 2, 3, 4, 5, 6, 8],
                weights=[0.28, 0.28, 0.20, 0.12, 0.07, 0.03, 0.02]
            )[0]

            datas = sorted(_data_aleatoria() for _ in range(n_a))
            for d in datas:
                uid = random.choice(atend_ids)  # Apenas atendentes registram atend.

                n_tipos   = random.choices([1, 2, 3], weights=[0.60, 0.35, 0.05])[0]
                tipos_sel = random.sample(pool_serv, k=min(n_tipos, len(pool_serv)))

                a = Atendimento(
                    data_atendimento  = d,
                    hora_atendimento  = _hora(),
                    id_pessoa         = pid,
                    id_usuario        = uid,
                    id_canal          = random.choices(
                        canal_ids, weights=[6, 2, 1, 3][:len(canal_ids)])[0],
                    origem            = 'dados_ficticios',
                    exclusao_pendente = False,
                )
                lote_atend.append((a, tipos_sel))

            if len(lote_atend) >= LOTE:
                for atend, _ in lote_atend:
                    db.session.add(atend)
                db.session.flush()
                for atend, tipos in lote_atend:
                    for tid in tipos:
                        db.session.add(AtendimentoServico(
                            id_atendimento      = atend.id,
                            id_servico = tid,
                        ))
                db.session.commit()
                total_atend += len(lote_atend)
                if total_atend % 200 == 0:
                    print(f'  {total_atend} atendimentos...')
                lote_atend.clear()

        if lote_atend:
            for atend, _ in lote_atend:
                db.session.add(atend)
            db.session.flush()
            for atend, tipos in lote_atend:
                for tid in tipos:
                    db.session.add(AtendimentoServico(
                        id_atendimento      = atend.id,
                        id_servico = tid,
                    ))
            db.session.commit()
            total_atend += len(lote_atend)

        print(f'  OK: {total_atend} atendimentos criados.')

        # Mapa pessoa_id → [atendimento_ids] para vincular solicitações
        atend_por_pessoa = {}
        for row in (db.session
                    .query(Atendimento.id, Atendimento.id_pessoa)
                    .filter(Atendimento.id_pessoa.in_(pessoas_com_atend),
                            Atendimento.origem == 'dados_ficticios')
                    .all()):
            atend_por_pessoa.setdefault(row.id_pessoa, []).append(row.id)

        # ── 5. Solicitações (250) ─────────────────────────────────────────────
        print()
        print('[5/10] Gerando solicitações...')

        # ~62% das pessoas com atendimento têm solicitação (funil realista)
        pool_solic = random.sample(pessoas_com_atend,
                                   k=min(int(0.62 * len(pessoas_com_atend)),
                                         len(pessoas_com_atend)))

        status_pesos = [
            (id_pendente, 0.30),
            (id_analise,  0.20),
            (id_aprovado, 0.35),
            (id_recusado, 0.15),
        ]

        total_solic = 0
        lote_solic  = []

        for pid in pool_solic:
            if total_solic >= META_SOLICITACOES:
                break

            n_s = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.10])[0]
            for _ in range(n_s):
                if total_solic >= META_SOLICITACOES:
                    break

                d         = _data_aleatoria()
                tipo_id   = random.choice(t_solic_ids)
                status_id = _wpick(status_pesos)

                # Atendentes e supervisor criam solicitações
                uid = random.choices(
                    op_ids,
                    weights=[3 if uid in atend_ids else 1 for uid in op_ids]
                )[0]

                evento_id    = random.choice(evento_ids) if evento_ids and random.random() < 0.20 else None
                atividade_id = random.choice(atv_ids)    if atv_ids else None

                obs = None
                if status_id == id_recusado:
                    obs = random.choice(MOTIVOS_RECUSA)
                elif random.random() < 0.35:
                    obs = random.choice(DESCRICOES_SOLIC)

                atend_ids_pessoa = atend_por_pessoa.get(pid, [])
                atend_id_sol = random.choice(atend_ids_pessoa) if atend_ids_pessoa else None

                lote_solic.append(Solicitacao(
                    data_solicitacao    = d,
                    id_pessoa           = pid,
                    id_usuario          = uid,
                    id_tipo_solicitacao = tipo_id,
                    id_status           = status_id,
                    id_evento           = evento_id,
                    id_atividade        = atividade_id,
                    observacao          = obs,
                    exclusao_pendente   = False,
                    atendimento_id      = atend_id_sol,
                ))
                total_solic += 1

            if len(lote_solic) >= LOTE:
                db.session.add_all(lote_solic)
                db.session.commit()
                print(f'  {total_solic} solicitações...')
                lote_solic.clear()

        if lote_solic:
            db.session.add_all(lote_solic)
            db.session.commit()

        print(f'  OK: {total_solic} solicitações criadas.')

        # ── 6. Log de ações (220+) ────────────────────────────────────────────
        print()
        print('[6/10] Gerando log de ações...')

        todos_u = [u for u in usuarios if u.perfil.nome in ('atendente', 'supervisor', 'administrador')]
        todos_u_ids = [u.id for u in todos_u]
        u_by_id = {u.id: u for u in todos_u}

        logs = []

        # Logins distribuídos ao longo do período (120 eventos)
        for _ in range(120):
            d   = _data_aleatoria()
            uid = random.choice(todos_u_ids)
            u   = u_by_id[uid]
            logs.append(LogAcao(
                created_at  = _dt(d),
                id_usuario  = uid,
                acao        = 'login',
                entidade    = 'usuario',
                entidade_id = uid,
                descricao   = f'Login: {u.nome} ({u.login})',
            ))

        # Criações de cadastros (60 eventos)
        for pid in random.sample(pessoas_ids, k=min(60, len(pessoas_ids))):
            d   = _data_aleatoria()
            uid = random.choice(atend_ids)
            logs.append(LogAcao(
                created_at  = _dt(d),
                id_usuario  = uid,
                acao        = 'criacao',
                entidade    = 'pessoa',
                entidade_id = pid,
                descricao   = f'Cadastro criado — empreendedor id={pid}',
            ))

        # Alterações de status de solicitação (50 eventos)
        solic_amostra = (Solicitacao.query
                         .filter(Solicitacao.id_pessoa.in_(pessoas_ids))
                         .order_by(Solicitacao.id)
                         .limit(300)
                         .all())
        if solic_amostra:
            for s in random.sample(solic_amostra, k=min(50, len(solic_amostra))):
                d   = _data_aleatoria()
                uid = random.choice(todos_u_ids)
                logs.append(LogAcao(
                    created_at  = _dt(d),
                    id_usuario  = uid,
                    acao        = 'status',
                    entidade    = 'solicitacao',
                    entidade_id = s.id,
                    descricao   = f'Status atualizado — solicitação #{s.id}',
                ))

        # Commit em lotes
        for i in range(0, len(logs), LOTE):
            db.session.add_all(logs[i:i + LOTE])
            db.session.commit()

        print(f'  OK: {len(logs)} entradas de log criadas.')

        # ── 7. Requerimentos (60) ─────────────────────────────────────────────
        print()
        print('[7/10] Gerando requerimentos...')

        # Protocolos existentes para evitar colisão
        existentes = {r.protocolo for r in RequerimentoGerado.query.all()}

        pessoas_req = random.sample(pessoas_ids, k=min(META_REQUERIMENTOS, len(pessoas_ids)))
        reqs        = []
        seq         = 1

        for pid in pessoas_req:
            d   = _data_aleatoria()
            uid = random.choice(op_ids)

            # Protocolo único: REQ-YYYYMMDD-F####  (F = ficticio)
            for tentativa in range(1000):
                proto = f"REQ-{d.strftime('%Y%m%d')}-F{seq + tentativa:04d}"
                if proto not in existentes:
                    existentes.add(proto)
                    seq += tentativa + 1
                    break

            # Vincular a solicitação existente (40% de chance)
            id_sol = None
            if solic_amostra:
                candidatos = [s for s in solic_amostra if s.id_pessoa == pid]
                if candidatos and random.random() < 0.40:
                    id_sol = random.choice(candidatos).id

            reqs.append(RequerimentoGerado(
                protocolo             = proto,
                created_at            = _dt(d),
                id_usuario            = uid,
                id_pessoa             = pid,
                credenciamento_evento = f"Evento Municipal {d.year}" if random.random() < 0.5 else None,
                solicitacao           = random.choice(DESCRICOES_SOLIC),
                id_solicitacao        = id_sol,
            ))

        for i in range(0, len(reqs), LOTE):
            db.session.add_all(reqs[i:i + LOTE])
            db.session.commit()

        print(f'  OK: {len(reqs)} requerimentos criados.')

        # ── 8. Parâmetros municipais ──────────────────────────────────────────
        print()
        print('[8/10] Inserindo parâmetros municipais...')

        params = [
            ('total_meis_municipio',    '8500',
             'Total de MEIs registrados no município (valor fictício)'),
            ('meta_anual_atendimentos', '3000',
             'Meta anual de atendimentos'),
        ]
        now = datetime.now(timezone.utc)
        for chave, valor, descricao in params:
            p = ParametroMunicipio.query.filter_by(chave=chave).first()
            if p:
                p.valor      = valor
                p.descricao  = descricao
                p.updated_at = now
            else:
                db.session.add(ParametroMunicipio(
                    chave=chave, valor=valor, descricao=descricao, updated_at=now
                ))
        db.session.commit()
        print('  OK: 2 parâmetros inseridos/atualizados.')

        # ── 9. Tags de Interesse ──────────────────────────────────────────────
        print()
        print('[9/10] Associando tags de interesse...')

        tags_ativas = TagInteresse.query.filter_by(ativo=True).all()

        total_assoc      = 0
        pessoas_com_tag  = set()
        contagem_por_tag = {}

        if not tags_ativas:
            print('  Nenhuma tag ativa encontrada — etapa ignorada.')
        else:
            for t in tags_ativas:
                contagem_por_tag[t.id] = 0

            tags_por_nome = {t.descricao: t for t in tags_ativas}

            # Pesos relativos por perfil (descricao → peso; ausentes → 1.0)
            _PESOS_MEI = {
                'MEI':                    5.0,
                'Orientação Fiscal':      4.0,
                'Crédito/Financiamento':  2.0,
                'Box/Mercado':            1.5,
                'Feira/Evento':           1.5,
                'Espaço Público':         1.0,
                'Outros':                 1.0,
            }
            _PESOS_PJ = {
                'Box/Mercado':            5.0,
                'Crédito/Financiamento':  4.0,
                'Orientação Fiscal':      2.0,
                'Feira/Evento':           1.5,
                'Espaço Público':         1.0,
                'MEI':                    0.5,
                'Outros':                 1.5,
            }
            _PESOS_PF = {
                'Feira/Evento':           5.0,
                'Espaço Público':         4.0,
                'Crédito/Financiamento':  2.0,
                'Orientação Fiscal':      2.0,
                'Box/Mercado':            1.5,
                'MEI':                    1.0,
                'Outros':                 1.5,
            }

            def _pool(mapa_pesos):
                """(ids, pesos) para as tags existentes no banco, na ordem das ativas."""
                ids_out, pw_out = [], []
                for t in tags_ativas:
                    ids_out.append(t.id)
                    pw_out.append(mapa_pesos.get(t.descricao, 1.0))
                return ids_out, pw_out

            pool_mei = _pool(_PESOS_MEI)
            pool_pj  = _pool(_PESOS_PJ)
            pool_pf  = _pool(_PESOS_PF)

            # Distribuição do número de tags por pessoa
            dist_n = [(0, 0.30), (1, 0.40), (2, 0.20), (3, 0.07), (4, 0.03)]

            pessoas_ficticias = (
                Pessoa.query
                .filter_by(origem='dados_ficticios')
                .with_entities(Pessoa.id, Pessoa.mei, Pessoa.cnpj)
                .all()
            )

            for pid, p_mei, p_cnpj in pessoas_ficticias:
                n = _wpick(dist_n)
                if n == 0:
                    continue

                ids_pool, pw = (pool_mei if p_mei else
                                pool_pj  if p_cnpj else
                                pool_pf)

                # Sorteio sem reposição
                selecionados = []
                pool_ids_mut = list(ids_pool)
                pool_pw_mut  = list(pw)
                for _ in range(min(n, len(pool_ids_mut))):
                    [escolha] = random.choices(pool_ids_mut, weights=pool_pw_mut, k=1)
                    idx = pool_ids_mut.index(escolha)
                    selecionados.append(escolha)
                    pool_ids_mut.pop(idx)
                    pool_pw_mut.pop(idx)

                for tid in selecionados:
                    db.session.execute(
                        text('INSERT INTO pessoa_tag (id_pessoa, id_tag) '
                             'VALUES (:p, :t) ON CONFLICT DO NOTHING'),
                        {'p': pid, 't': tid},
                    )
                    contagem_por_tag[tid] += 1
                    total_assoc += 1

                if selecionados:
                    pessoas_com_tag.add(pid)

            db.session.commit()

        pct_com = (100 * len(pessoas_com_tag) / len(pessoas_ids)) if pessoas_ids else 0
        print(f'  OK: {total_assoc} associações criadas '
              f'({len(pessoas_com_tag)}/{len(pessoas_ids)} pessoas com tags, {pct_com:.0f}%)')
        if contagem_por_tag and tags_ativas:
            print('  Distribuição por tag:')
            for t in sorted(tags_ativas, key=lambda x: -contagem_por_tag.get(x.id, 0)):
                c = contagem_por_tag.get(t.id, 0)
                print(f'    {t.descricao:<30} {c:>4}')

        # ── 10. Resumo ────────────────────────────────────────────────────────
        print()
        print('=' * 60)
        print('CONCLUÍDO — RESUMO DOS DADOS GERADOS')
        print('=' * 60)

        cnt_p  = Pessoa.query.filter_by(origem='dados_ficticios').count()
        cnt_a  = Atendimento.query.filter_by(origem='dados_ficticios').count()
        cnt_s  = (Solicitacao.query
                  .filter(Solicitacao.id_pessoa.in_(pessoas_ids))
                  .count())
        cnt_l  = LogAcao.query.count()
        cnt_r  = RequerimentoGerado.query.count()

        cnt_tags = total_assoc

        print(f'  Pessoas fictícias:   {cnt_p}')
        print(f'  Com tags:            {len(pessoas_com_tag)} ({pct_com:.0f}%)')
        print(f'  Atendimentos:        {cnt_a}')
        print(f'  Solicitações:        {cnt_s}')
        print(f'  Tags associadas:     {cnt_tags}')
        print(f'  Log de ações total:  {cnt_l}')
        print(f'  Requerimentos total: {cnt_r}')

        print()
        print('  Distribuição por status (solicitações):')
        for s in Status.query.all():
            c = (Solicitacao.query
                 .filter_by(id_status=s.id)
                 .filter(Solicitacao.id_pessoa.in_(pessoas_ids))
                 .count())
            if c:
                print(f'    {s.descricao:<20} {c:>4}')

        print()
        print('  Top 5 bairros (pessoas fictícias):')
        top_b = (db.session.query(Pessoa.bairro, func.count(Pessoa.id).label('total'))
                 .filter(Pessoa.origem == 'dados_ficticios',
                         Pessoa.bairro.isnot(None), Pessoa.bairro != '')
                 .group_by(Pessoa.bairro)
                 .order_by(func.count(Pessoa.id).desc())
                 .limit(5).all())
        for b in top_b:
            print(f'    {b.bairro:<25} {b.total:>4}')

        print()
        print('  Atendimentos por atendente:')
        for u in atendentes:
            c = Atendimento.query.filter_by(id_usuario=u.id, origem='dados_ficticios').count()
            print(f'    {u.nome:<20} {c:>4}')

        print('=' * 60)


if __name__ == '__main__':
    main()
