import re
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .. import db
from ..escopo import filtrar_por_escopo, no_escopo
from ..models import (Atendimento, AtendimentoServico, Servico,
                      CanalAtendimento, Pessoa, Usuario, Solicitacao,
                      ATENDIMENTO_CONCLUIDO, ATENDIMENTO_RASCUNHO,
                      ATENDIMENTO_STATUS,
                      APLIC_MEI, APLIC_TODOS, TIPOS_EFETIVOS, tipo_efetivo_de)

atendimentos_bp = Blueprint('atendimentos', __name__, url_prefix='/atendimentos')

POR_PAGINA = 20


def servico_abertura_mei():
    """O serviço que dispara a conversão PF→MEI durante o atendimento.

    Localizado por descrição, o mesmo critério que `analise.py` já usa para o
    KPI de novos MEIs — não por id hardcoded.
    """
    return Servico.query.filter(
        Servico.descricao.ilike('%abertura%mei%')).first()


def servico_solicitacao():
    """O serviço cujo ícone abre o formulário de solicitação, não um portal.

    Mesmo critério de `servico_abertura_mei()`: localizado por descrição, não
    por id. Ele não tem `link_portal` porque o destino dele é interno.
    """
    return Servico.query.filter(
        Servico.descricao.ilike('solicita%')).first()


def resolver_servicos(servicos_sel, tipo_efetivo, form):
    """Valida os serviços submetidos contra o tipo efetivo do atendimento.

    O front guia, o back garante: a tela esconde os serviços não aplicáveis,
    mas quem decide o que entra no banco é aqui.

    Regra de exibição/validação:
        aplicável  ⇔  aplicabilidade == tipo_efetivo  ou  == 'todos'

    Um serviço NÃO aplicável só é aceito se veio marcado como **forçado**
    (revelado pela válvula de escape "Mostrar todos"). Nesse caso é gravado
    com `forcado=True`, para auditoria. Não aplicável e não forçado é estado
    inconsistente — é recusado, em vez de virar registro silencioso.

    Cada serviço carrega o SNAPSHOT do tipo vigente quando foi marcado
    (`snap_<id>`), para o histórico não mudar retroativamente. Sem snapshot
    válido, cai no tipo efetivo do atendimento.

    Retorna `(vinculos, erros)`, onde vinculos é lista de dicts prontos para
    virar AtendimentoServico. Não toca no banco.
    """
    vinculos, erros = [], []

    for sid in servicos_sel:
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            erros.append(f'Serviço inválido: {sid!r}.')
            continue

        servico = db.session.get(Servico, sid_int)
        if servico is None:
            erros.append(f'Serviço {sid_int} não existe.')
            continue

        aplicavel = servico.aplicabilidade in (tipo_efetivo, APLIC_TODOS)
        forcado   = form.get(f'forcado_{sid_int}') == '1'

        if not aplicavel and not forcado:
            erros.append(
                f'"{servico.descricao}" não se aplica a este atendimento. '
                f'Use "Mostrar todos os serviços" para registrá-lo mesmo assim.'
            )
            continue

        snap = form.get(f'snap_{sid_int}')
        if snap not in TIPOS_EFETIVOS:
            snap = tipo_efetivo

        vinculos.append({
            'id_servico':   sid_int,
            'tipo_efetivo': snap,
            # Um serviço aplicável nunca é forçado, mesmo que o front diga
            'forcado':      (not aplicavel),
        })

    return vinculos, erros


def canal_padrao_id():
    """Id do canal Presencial — o padrão quando nenhum é informado."""
    c = CanalAtendimento.query.filter_by(descricao='Presencial').first()
    if c is None:                      # fallback: primeiro canal ativo
        c = CanalAtendimento.query.filter_by(ativo=True).order_by(
            CanalAtendimento.id).first()
    return c.id if c else None


def rascunho_do_usuario(atendimento_id):
    """O rascunho indicado, se ele existe e é do usuário logado.

    Devolve None em qualquer outro caso — id inexistente, atendimento de outra
    pessoa, ou já concluído. Quem chama trata None como "crie um novo": a
    finalização nunca é bloqueada por um id ruim, e um id de outro usuário
    nunca sobrescreve o registro dele.
    """
    if not atendimento_id:
        return None
    atend = db.session.get(Atendimento, atendimento_id)
    if atend is None or atend.id_usuario != current_user.id:
        return None
    return atend if atend.rascunho else None


def upsert_atendimento(*, id_pessoa, id_usuario, servicos_ids,
                       id_canal=None, status=ATENDIMENTO_CONCLUIDO,
                       observacao=None, atendimento_id=None, contexto=None):
    """Caminho único de persistência de atendimento — cria ou atualiza.

    Sem `atendimento_id`, cria. Com `atendimento_id`, carrega e atualiza o
    registro existente. Substitui o conjunto de serviços por `servicos_ids`.

    `id_canal` é COMO o empreendedor chegou (um só). Omitido, usa Presencial.
    `servicos_ids` é O QUE foi feito (vários).

    Fundação da Fase 1. **Ligada à interface em 2026-08-23:** é usada tanto
    pelo clique no ícone de "Solicitação" (que grava um rascunho) quanto pelo
    "Finalizar Atendimento" (que atualiza o mesmo registro e o conclui). É por
    isso que rascunho + finalizar dá UM atendimento, não dois.

    `contexto` é opcional: `{id_servico: {'tipo_efetivo':…, 'forcado':…}}`,
    normalmente o que `resolver_servicos()` devolve. Aplicado tanto aos
    vínculos novos quanto aos que já existiam — um serviço marcado no rascunho
    e mantido na finalização tem o contexto atualizado, não congelado.

    Idempotente: chamar duas vezes com o mesmo `atendimento_id` e os mesmos
    dados não duplica nem o atendimento nem os vínculos de tipo.

    `data_atendimento` e `hora_atendimento` são gravados na criação e
    **preservados** nas atualizações seguintes — ou seja, marcam o início do
    atendimento, não a conclusão. Se a Fase 2 ou 3 precisar do instante da
    conclusão, isso é decisão daquelas fases.

    Não faz commit: quem chama decide o momento.
    Levanta ValueError se o status não for válido.
    Retorna o Atendimento.
    """
    if status not in ATENDIMENTO_STATUS:
        raise ValueError(
            f'Status inválido: {status!r}. Use um de {ATENDIMENTO_STATUS}.'
        )

    atend = db.session.get(Atendimento, atendimento_id) if atendimento_id else None
    canal = id_canal or canal_padrao_id()

    if atend is None:
        agora = datetime.now()
        atend = Atendimento(
            data_atendimento=agora.date(),
            hora_atendimento=agora.time(),
            id_pessoa=id_pessoa,
            id_usuario=id_usuario,
            id_canal=canal,
        )
        db.session.add(atend)

    atend.id_pessoa  = id_pessoa
    atend.id_usuario = id_usuario
    atend.id_canal   = canal
    atend.observacao = observacao
    atend.status     = status

    db.session.flush()          # garante atend.id nas criações

    # Substitui o conjunto de serviços por diferença, não por recriação: a PK
    # de AtendimentoServico é composta, então re-adicionar um vínculo
    # existente violaria a chave primária.
    desejados = {int(t) for t in servicos_ids}
    atuais    = {at.id_servico for at in atend.servicos}
    ctx       = contexto or {}

    for at in list(atend.servicos):
        if at.id_servico not in desejados:
            db.session.delete(at)
        elif at.id_servico in ctx:
            at.tipo_efetivo = ctx[at.id_servico].get('tipo_efetivo')
            at.forcado      = bool(ctx[at.id_servico].get('forcado'))

    for tid in desejados - atuais:
        c = ctx.get(tid, {})
        db.session.add(AtendimentoServico(
            id_atendimento=atend.id,
            id_servico=tid,
            tipo_efetivo=c.get('tipo_efetivo'),
            forcado=bool(c.get('forcado')),
        ))

    return atend


def _get_form_data():
    """Carrega listas necessárias para o formulário."""
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.descricao).all()
    pessoas  = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    canais   = CanalAtendimento.query.filter_by(ativo=True).order_by(
        CanalAtendimento.id).all()
    return servicos, pessoas, usuarios, canais


def _salva_atendimento(atend, form):
    """Aplica dados do form no objeto Atendimento e atualiza os serviços."""
    atend.data_atendimento = date.fromisoformat(form['data_atendimento'])
    atend.hora_atendimento = datetime.strptime(form['hora_atendimento'], '%H:%M').time()
    atend.observacao       = form.get('observacao', '').strip() or None
    atend.id_pessoa        = int(form['id_pessoa'])
    atend.id_usuario       = int(form['id_usuario'])
    atend.id_canal         = int(form.get('id_canal') or 0) or canal_padrao_id()

    # Serviços só são gerenciados aqui em edição (id já existe).
    # Em criação, são adicionados em novo() após o flush().
    if atend.id:
        AtendimentoServico.query.filter_by(id_atendimento=atend.id).delete()
        for sid in request.form.getlist('servicos'):
            db.session.add(AtendimentoServico(
                id_atendimento=atend.id,
                id_servico=int(sid)
            ))


def _valida_form(form):
    erros = []
    if not form.get('data_atendimento'):
        erros.append('Data é obrigatória.')
    if not form.get('hora_atendimento'):
        erros.append('Hora é obrigatória.')
    if not form.get('id_pessoa'):
        erros.append('Selecione uma pessoa.')
    if not form.get('id_usuario'):
        erros.append('Selecione o usuário responsável.')
    if not request.form.getlist('servicos'):
        erros.append('Selecione pelo menos um serviço.')
    return erros


# ── Lista ──────────────────────────────────────────────────────────────────────
@atendimentos_bp.route('/')
@login_required
def index():
    data_de   = request.args.get('data_de',    '').strip()
    data_ate  = request.args.get('data_ate',   '').strip()
    q_pessoa  = request.args.get('q_pessoa',   '').strip()
    f_usuario = request.args.get('usuario_id', '').strip()
    f_tipo    = request.args.get('tipo_id',    '').strip()
    f_status  = request.args.get('status',     '').strip()

    filtros_ativos = any([data_de, data_ate, q_pessoa, f_usuario, f_tipo, f_status])
    if not filtros_ativos:
        hoje_str = date.today().isoformat()
        data_de  = hoje_str
        data_ate = hoje_str

    query = (
        Atendimento.query
        .join(Atendimento.pessoa)
        .join(Atendimento.usuario)
    )

    # Rascunhos aparecem na lista (é onde eles são retomados), mas o filtro
    # permite ir direto neles — é o destino do indicador da análise.
    if f_status in ATENDIMENTO_STATUS:
        query = query.filter(Atendimento.status == f_status)

    if data_de:
        try:
            query = query.filter(Atendimento.data_atendimento >= date.fromisoformat(data_de))
        except ValueError:
            pass
    if data_ate:
        try:
            query = query.filter(Atendimento.data_atendimento <= date.fromisoformat(data_ate))
        except ValueError:
            pass
    if q_pessoa:
        q_limpo = re.sub(r'\D', '', q_pessoa)
        like_original = f'%{q_pessoa}%'

        if q_limpo and q_limpo != q_pessoa:
            like_limpo = f'%{q_limpo}%'
            query = query.filter(
                db.or_(
                    Pessoa.nome_razao_social.ilike(like_original),
                    Pessoa.cpf.ilike(like_original),
                    Pessoa.cnpj.ilike(like_original),
                    db.func.regexp_replace(Pessoa.cpf,  r'\D', '', 'g').ilike(like_limpo),
                    db.func.regexp_replace(Pessoa.cnpj, r'\D', '', 'g').ilike(like_limpo),
                )
            )
        else:
            query = query.filter(
                db.or_(
                    Pessoa.nome_razao_social.ilike(like_original),
                    Pessoa.cpf.ilike(like_original),
                    Pessoa.cnpj.ilike(like_original),
                )
            )

    if f_usuario:
        try:
            query = query.filter(Atendimento.id_usuario == int(f_usuario))
        except ValueError:
            pass

    if f_tipo:
        try:
            query = query.join(AtendimentoServico,
                               AtendimentoServico.id_atendimento == Atendimento.id
                               ).filter(
                AtendimentoServico.id_servico == int(f_tipo)
            )
        except ValueError:
            pass

    # Escopo por perfil — regra única em app/escopo.py
    query = filtrar_por_escopo(query, Atendimento.id_usuario)

    if current_user.perfil.nome != 'administrador':
        query = query.filter(Atendimento.exclusao_pendente == False)

    from sqlalchemy.orm import joinedload, selectinload
    query = query.options(
        joinedload(Atendimento.pessoa),
        joinedload(Atendimento.usuario),
        selectinload(Atendimento.servicos).joinedload(AtendimentoServico.servico),
    )

    page = request.args.get('page', 1, type=int)
    paginacao = (
        query
        .order_by(Atendimento.data_atendimento.desc(), Atendimento.hora_atendimento.desc())
        .paginate(page=page, per_page=POR_PAGINA, error_out=False)
    )

    # Solicitações vinculadas — uma query para toda a página (evita N+1)
    atend_ids_pagina = [a.id for a in paginacao.items]
    solic_por_atend = {}
    if atend_ids_pagina:
        rows = (db.session
                .query(Solicitacao.id, Solicitacao.atendimento_id)
                .filter(Solicitacao.atendimento_id.in_(atend_ids_pagina))
                .all())
        for r in rows:
            solic_por_atend.setdefault(r.atendimento_id, []).append(r.id)

    if current_user.perfil.nome == 'administrador':
        usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    elif current_user.perfil.nome == 'supervisor':
        atendentes_ids = [a.id for a in current_user.atendentes]
        if atendentes_ids:
            usuarios = Usuario.query.filter(
                Usuario.id.in_(atendentes_ids + [current_user.id]),
                Usuario.ativo == True,
            ).order_by(Usuario.nome).all()
        else:
            usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    else:
        usuarios = []

    servicos_filtro = Servico.query.filter_by(ativo=True).order_by(
        Servico.descricao).all()

    # Agrupar por data preservando a ordem DESC da query
    from itertools import groupby as _groupby
    grupos_data = [
        (k, list(v))
        for k, v in _groupby(paginacao.items, key=lambda a: a.data_atendimento)
    ]

    _DIAS_PT = ['Segunda-feira', 'Terça-feira', 'Quarta-feira',
                'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']

    return render_template('atendimentos/lista.html',
                           atendimentos=paginacao.items, paginacao=paginacao,
                           grupos_data=grupos_data,
                           dias_pt=_DIAS_PT,
                           usuarios=usuarios,
                           data_de=data_de, data_ate=data_ate,
                           q_pessoa=q_pessoa, f_usuario=f_usuario,
                           f_tipo=f_tipo, f_status=f_status,
                           servicos_filtro=servicos_filtro,
                           filtros_ativos=filtros_ativos,
                           solic_por_atend=solic_por_atend,
                           hoje=date.today(), timedelta=timedelta)


# ── Atendimento rápido ────────────────────────────────────────────────────────
@atendimentos_bp.route('/rapido', methods=['GET', 'POST'])
@login_required
def rapido():
    from datetime import datetime as dt
    # Antes do ciclo canal×serviço isto filtrava ids hardcoded [1,2,9,10,12],
    # que após a troca do conteúdo da tabela devolviam "Presencial" e
    # "Telefone". Agora lista os serviços ativos de verdade.
    servicos_rapidos = Servico.query.filter_by(ativo=True).order_by(
        Servico.descricao).all()

    pessoas = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()

    if request.method == 'POST':
        id_pessoa = request.form.get('id_pessoa', type=int)
        servicos_sel = request.form.getlist('servicos')

        if not id_pessoa:
            flash('Selecione uma pessoa.', 'danger')
        elif not servicos_sel:
            flash('Selecione pelo menos um serviço.', 'danger')
        else:
            now = dt.now()
            atend = Atendimento(
                data_atendimento=now.date(),
                hora_atendimento=now.time(),
                observacao=request.form.get('observacao', '').strip() or None,
                id_pessoa=id_pessoa,
                id_usuario=current_user.id,
                id_canal=request.form.get('id_canal', type=int) or canal_padrao_id(),
            )
            db.session.add(atend)
            db.session.flush()
            for tid in servicos_sel:
                db.session.add(AtendimentoServico(
                    id_atendimento=atend.id,
                    id_servico=int(tid),
                ))
            db.session.commit()
            proximo = request.form.get('proximo')
            if proximo:
                flash('Atendimento registrado!', 'success')
                return redirect(url_for('atendimentos.rapido'))
            return redirect(url_for('atendimentos.sucesso', id=atend.id))

    return render_template('atendimentos/rapido.html',
                           servicos_rapidos=servicos_rapidos,
                           canais=CanalAtendimento.query.filter_by(ativo=True)
                                  .order_by(CanalAtendimento.id).all(),
                           canal_padrao=canal_padrao_id(),
                           pessoas=pessoas)


# ── Iniciar Atendimento ───────────────────────────────────────────────────────
@atendimentos_bp.route('/iniciar', methods=['GET', 'POST'])
@login_required
def iniciar():
    """Atendimento integrado com portais MEI."""
    todos_servicos = Servico.query.filter_by(ativo=True).order_by(
        Servico.descricao).all()
    pessoas = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()

    pessoa_pre = None
    pessoa_id_pre = request.args.get('pessoa_id', type=int)
    if pessoa_id_pre:
        pessoa_pre = db.session.get(Pessoa, pessoa_id_pre)

    # ── Modo retomada ────────────────────────────────────────────────────
    # A tela sempre soube começar do zero. Aqui ela aprende a continuar: o
    # selo "Em aberto" da lista traz o id do rascunho, e a tela reabre com
    # o que já estava marcado. Ao concluir, o mesmo upsert ATUALIZA aquele
    # registro — não é um segundo caminho de criação.
    retomar = None
    contexto_retomado = {}
    retomar_id = request.args.get('retomar', type=int)
    if retomar_id:
        candidato = db.get_or_404(Atendimento, retomar_id)
        # Mesmo escopo da edição: o id na URL não basta.
        if not _no_escopo(candidato):
            flash('Você não tem permissão para retomar este atendimento.', 'danger')
            return redirect(url_for('atendimentos.index'))
        if not candidato.rascunho:
            flash('Este atendimento já foi concluído.', 'warning')
            return redirect(url_for('atendimentos.detalhe', id=candidato.id))
        retomar    = candidato
        pessoa_pre = candidato.pessoa
        # O contexto gravado por serviço volta como estava: sem o `forcado`,
        # um serviço fora do perfil seria recusado na revalidação.
        contexto_retomado = {
            av.id_servico: {'snap': av.tipo_efetivo or '',
                            'forcado': '1' if av.forcado else ''}
            for av in candidato.servicos
        }

    if request.method == 'POST':
        id_pessoa = request.form.get('id_pessoa', type=int)
        servicos_sel = request.form.getlist('servicos')

        # Tipo efetivo DO ATENDIMENTO. Vem da tela (pode ter mudado durante o
        # atendimento, ex.: a pessoa abriu MEI no balcão). Sem valor válido,
        # deriva do cadastro — que é como ele nasce.
        tipo_efetivo = request.form.get('tipo_efetivo')
        if tipo_efetivo not in TIPOS_EFETIVOS:
            tipo_efetivo = tipo_efetivo_de(db.session.get(Pessoa, id_pessoa)
                                           if id_pessoa else None)

        vinculos, erros_serv = resolver_servicos(
            servicos_sel, tipo_efetivo, request.form)

        if not id_pessoa:
            flash('Selecione uma pessoa.', 'danger')
        elif not servicos_sel:
            flash('Selecione pelo menos um serviço.', 'danger')
        elif erros_serv:
            for e in erros_serv:
                flash(e, 'danger')
        else:
            # Se o atendente clicou no ícone de "Solicitação", já existe um
            # rascunho — finalizar ATUALIZA aquele registro em vez de criar
            # outro. É o upsert que garante que rascunho + finalizar = UM
            # atendimento.
            rascunho = rascunho_do_usuario(
                request.form.get('atendimento_id', type=int))
            atend = upsert_atendimento(
                id_pessoa=id_pessoa,
                id_usuario=current_user.id,
                servicos_ids=[v['id_servico'] for v in vinculos],
                id_canal=request.form.get('id_canal', type=int),
                status=ATENDIMENTO_CONCLUIDO,
                observacao=request.form.get('observacao', '').strip() or None,
                atendimento_id=rascunho.id if rascunho else None,
                contexto={v['id_servico']: v for v in vinculos},
            )
            db.session.commit()
            flash('Atendimento registrado com sucesso!', 'success')
            # Se incluiu Abertura de MEI e a pessoa ainda não tem CNPJ,
            # leva para a ficha com o prompt de atualização.
            # Antes: `if '9' in tipos_sel` — id hardcoded que deixara de existir
            # na tabela, o que tornava este ramo código morto.
            serv_abertura = servico_abertura_mei()
            if serv_abertura and str(serv_abertura.id) in servicos_sel:
                pessoa_atend = db.session.get(Pessoa, id_pessoa)
                if pessoa_atend and not pessoa_atend.cnpj:
                    return redirect(url_for('pessoas.detalhe',
                                            id=id_pessoa, mei_aberto=1))
            return redirect(url_for('atendimentos.sucesso', id=atend.id))

    serv_abertura = servico_abertura_mei()
    serv_solic    = servico_solicitacao()

    # Numa retomada o tipo efetivo é reconstruído do snapshot gravado: se
    # algum serviço foi registrado como 'mei', a conversão aconteceu naquele
    # atendimento e continua valendo. Fora disso, nasce do cadastro.
    if retomar and any(c['snap'] == APLIC_MEI for c in contexto_retomado.values()):
        tipo_inicial = APLIC_MEI
    else:
        tipo_inicial = tipo_efetivo_de(pessoa_pre)

    return render_template('atendimentos/iniciar.html',
                           todos_servicos=todos_servicos,
                           canais=CanalAtendimento.query.filter_by(ativo=True)
                                  .order_by(CanalAtendimento.id).all(),
                           canal_padrao=canal_padrao_id(),
                           pessoas=pessoas,
                           pessoa_pre=pessoa_pre,
                           # Ancora da conversão PF→MEI na tela
                           id_servico_abertura=serv_abertura.id if serv_abertura else None,
                           # Serviço cujo ícone abre o formulário interno
                           id_servico_solicitacao=serv_solic.id if serv_solic else None,
                           retomar=retomar,
                           contexto_retomado=contexto_retomado,
                           tipo_efetivo_inicial=tipo_inicial)


# ── Cadastro rápido (AJAX) ────────────────────────────────────────────────────
@atendimentos_bp.route('/rascunho', methods=['POST'])
@login_required
def rascunho():
    """Salva o atendimento em andamento como rascunho e devolve o id.

    Chamado pelo ícone do serviço "Solicitação" na tela guiada, antes de abrir
    o formulário em nova aba: a solicitação precisa de um atendimento que já
    exista para se vincular a ele.

    Reutiliza `upsert_atendimento` — chamar duas vezes com o mesmo
    `atendimento_id` atualiza o mesmo registro. É o mesmo caminho de
    persistência que "Finalizar Atendimento" usa depois, com outro status.

    Serviços não aplicáveis ao tipo efetivo são **descartados**, não recusados:
    um rascunho não deve travar o atendente. A validação que vale é a da
    finalização, onde o formulário reenvia tudo e `resolver_servicos()` decide.
    """
    from flask import jsonify

    dados     = request.get_json(silent=True) or {}
    id_pessoa = dados.get('id_pessoa')
    if not id_pessoa:
        return jsonify({'erro': 'Selecione uma pessoa antes.'}), 400

    tipo_efetivo = dados.get('tipo_efetivo')
    if tipo_efetivo not in TIPOS_EFETIVOS:
        tipo_efetivo = tipo_efetivo_de(db.session.get(Pessoa, id_pessoa))

    # `resolver_servicos` lê o contexto de um form; aqui ele vem do JSON.
    contexto_form = {}
    for item in (dados.get('servicos') or []):
        sid = item.get('id')
        contexto_form[f'snap_{sid}']    = item.get('snap') or ''
        contexto_form[f'forcado_{sid}'] = item.get('forcado') or ''
    ids = [item.get('id') for item in (dados.get('servicos') or [])]

    vinculos, _ = resolver_servicos(ids, tipo_efetivo, contexto_form)

    existente = rascunho_do_usuario(dados.get('atendimento_id'))
    atend = upsert_atendimento(
        id_pessoa=id_pessoa,
        id_usuario=current_user.id,
        servicos_ids=[v['id_servico'] for v in vinculos],
        id_canal=dados.get('id_canal'),
        status=ATENDIMENTO_RASCUNHO,
        observacao=(dados.get('observacao') or '').strip() or None,
        atendimento_id=existente.id if existente else None,
        contexto={v['id_servico']: v for v in vinculos},
    )
    db.session.commit()

    return jsonify({
        'atendimento_id': atend.id,
        'url_solicitacao': url_for('solicitacoes.nova', atendimento_id=atend.id),
    })


@atendimentos_bp.route('/<int:id>/tem-solicitacao')
@login_required
def tem_solicitacao(id):
    """Se já existe alguma solicitação vinculada a este atendimento.

    É o que sustenta o aviso anti-fantasma da finalização. A pergunta é feita
    ao banco, e não a uma variável da aba: o formulário é preenchido em OUTRA
    aba, que pode ter sido fechada, recarregada ou aberta duas vezes.
    """
    from flask import jsonify

    atend = db.session.get(Atendimento, id)
    if atend is None or atend.id_usuario != current_user.id:
        return jsonify({'tem': False})
    return jsonify({
        'tem': Solicitacao.query.filter_by(atendimento_id=id).count() > 0
    })


@atendimentos_bp.route('/cadastro-rapido', methods=['POST'])
@login_required
def cadastro_rapido():
    """Cadastra uma pessoa rapidamente durante o atendimento."""
    from flask import jsonify
    from ..models import Pessoa

    nome  = request.json.get('nome', '').strip()
    cpf   = request.json.get('cpf', '').strip()
    cnpj  = request.json.get('cnpj', '').strip()
    tel   = request.json.get('telefone', '').strip() or None
    end   = request.json.get('endereco', '').strip() or None

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório.'}), 400

    if cpf and cnpj:
        return jsonify({'erro': 'Preencha CPF ou CNPJ, não os dois.'}), 400

    if cpf:
        existe = Pessoa.visiveis().filter_by(cpf=cpf).first()
        if existe:
            return jsonify({
                'erro': f'CPF já cadastrado: {existe.nome_razao_social}',
                'pessoa': {'id': existe.id, 'nome': existe.nome_razao_social,
                           'doc': existe.cpf or '', 'cnpj': existe.cnpj or ''}
            }), 409

    if cnpj:
        existe = Pessoa.visiveis().filter_by(cnpj=cnpj).first()
        if existe:
            return jsonify({
                'erro': f'CNPJ já cadastrado: {existe.nome_razao_social}',
                'pessoa': {'id': existe.id, 'nome': existe.nome_razao_social,
                           'doc': existe.cnpj or '', 'cnpj': existe.cnpj or ''}
            }), 409

    p = Pessoa(
        nome_razao_social=nome,
        cpf=cpf or None,
        cnpj=cnpj or None,
        telefone=tel,
        endereco=end,
    )
    db.session.add(p)
    db.session.commit()

    return jsonify({
        'pessoa': {
            'id':   p.id,
            'nome': p.nome_razao_social,
            'doc':  p.cpf or p.cnpj or '',
            'cnpj': p.cnpj or '',
        }
    }), 201


# ── Novo ───────────────────────────────────────────────────────────────────────
@atendimentos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    servicos, pessoas, usuarios, canais = _get_form_data()

    if request.method == 'POST':
        erros = _valida_form(request.form)
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('atendimentos/form.html',
                                   titulo='Novo Atendimento', acao='novo',
                                   servicos=servicos, canais=canais, pessoas=pessoas, usuarios=usuarios,
                                   form=request.form,
                                   servicos_sel=request.form.getlist('servicos'))

        atend = Atendimento()
        _salva_atendimento(atend, request.form)
        db.session.add(atend)
        db.session.flush()  # gera o id antes de salvar os tipos
        for tid in request.form.getlist('servicos'):
            db.session.add(AtendimentoServico(
                id_atendimento=atend.id,
                id_servico=int(tid)
            ))
        db.session.commit()
        flash('Atendimento registrado com sucesso.', 'success')
        return redirect(url_for('atendimentos.detalhe', id=atend.id))

    now = datetime.now()
    form_default = {
        'data_atendimento': now.strftime('%Y-%m-%d'),
        'hora_atendimento': now.strftime('%H:%M'),
        'id_usuario':       str(current_user.id),
        'id_canal':         str(canal_padrao_id() or ''),
    }
    return render_template('atendimentos/form.html',
                           titulo='Novo Atendimento', acao='novo',
                           servicos=servicos, canais=canais, pessoas=pessoas, usuarios=usuarios,
                           form=form_default, servicos_sel=[])


# ── Detalhe ────────────────────────────────────────────────────────────────────
@atendimentos_bp.route('/<int:id>')
@login_required
def detalhe(id):
    atend = db.get_or_404(Atendimento, id)
    # Ler respeita o mesmo escopo que editar. O id na URL não basta: o
    # trabalho de um atendente não fica exposto a outro. Decisão de
    # 2026-08-29, registrada em 02_REGRAS_DE_NEGOCIO.md.
    if not _no_escopo(atend):
        flash('Você não tem permissão para ver este atendimento.', 'danger')
        return redirect(url_for('atendimentos.index'))
    return render_template('atendimentos/detalhe.html', atend=atend)


# ── Editar ─────────────────────────────────────────────────────────────────────
def _no_escopo(atend):
    """Escopo registro a registro — a mesma regra da listagem.

    Desde 2026-08-29 vale para LER também, não só editar: `detalhe` e
    `sucesso` passaram a usá-la. Ver `app/escopo.py`.
    """
    return no_escopo(atend)


@atendimentos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    atend = db.get_or_404(Atendimento, id)

    if not _no_escopo(atend):
        flash('Você não tem permissão para editar este atendimento.', 'danger')
        return redirect(url_for('atendimentos.index'))

    servicos, pessoas, usuarios, canais = _get_form_data()

    if request.method == 'POST':
        erros = _valida_form(request.form)
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('atendimentos/form.html',
                                   titulo='Editar Atendimento', acao='editar',
                                   atend=atend, servicos=servicos, canais=canais, pessoas=pessoas,
                                   usuarios=usuarios, form=request.form,
                                   servicos_sel=request.form.getlist('servicos'))

        _salva_atendimento(atend, request.form)
        db.session.commit()
        flash('Atendimento atualizado com sucesso.', 'success')
        return redirect(url_for('atendimentos.detalhe', id=atend.id))

    servicos_sel = [str(at.id_servico) for at in atend.servicos]
    form = {
        'data_atendimento': atend.data_atendimento.isoformat(),
        'hora_atendimento': atend.hora_atendimento.strftime('%H:%M'),
        'observacao':       atend.observacao or '',
        'id_pessoa':        str(atend.id_pessoa),
        'id_usuario':       str(atend.id_usuario),
        'id_canal':         str(atend.id_canal),
    }
    return render_template('atendimentos/form.html',
                           titulo='Editar Atendimento', acao='editar',
                           atend=atend, servicos=servicos, canais=canais, pessoas=pessoas,
                           usuarios=usuarios, form=form, servicos_sel=servicos_sel)


# ── Remover ────────────────────────────────────────────────────────────────────
_PERFIS_REMOVER = {'administrador'}


@atendimentos_bp.route('/<int:id>/remover', methods=['POST'])
@login_required
def remover(id):
    if current_user.perfil.nome not in _PERFIS_REMOVER:
        flash('Você não tem permissão para excluir atendimentos. '
              'Solicite a exclusão para análise da administração.', 'danger')
        return redirect(url_for('atendimentos.index'))

    atend = db.get_or_404(Atendimento, id)
    nome_pessoa = atend.pessoa.nome_razao_social
    data_fmt    = atend.data_atendimento.strftime('%d/%m/%Y')
    from .pessoas import _registrar_log
    _registrar_log(
        acao='exclusao',
        entidade='atendimento',
        entidade_id=id,
        descricao=f'Atendimento removido: {nome_pessoa} em {data_fmt} (id={id})',
    )
    db.session.delete(atend)
    db.session.commit()
    flash(f'Atendimento de {nome_pessoa} em {data_fmt} removido.', 'success')
    return redirect(url_for('atendimentos.index'))


# ── Registrar MEI (carrinho) ───────────────────────────────────────────────────
@atendimentos_bp.route('/registrar-mei', methods=['POST'])
@login_required
def registrar_mei():
    from flask import jsonify
    from datetime import datetime as dt
    data = request.get_json()

    pessoa_id = data.get('pessoa_id')
    tipos     = data.get('tipos', [])

    if not pessoa_id or not tipos:
        return jsonify({'ok': False, 'erro': 'Dados incompletos.'}), 400

    pessoa = db.session.get(Pessoa, pessoa_id)
    if not pessoa:
        return jsonify({'ok': False, 'erro': 'Pessoa não encontrada.'}), 404

    now   = dt.now()
    atend = Atendimento(
        data_atendimento=now.date(),
        hora_atendimento=now.time(),
        id_pessoa=pessoa_id,
        id_usuario=current_user.id,
        id_canal=canal_padrao_id(),
        observacao='Registrado automaticamente via serviços MEI',
    )
    db.session.add(atend)
    db.session.flush()

    for tid in tipos:
        tipo = db.session.get(Servico, tid)
        if tipo:
            db.session.add(AtendimentoServico(
                id_atendimento=atend.id,
                id_servico=tid,
            ))

    db.session.commit()
    return jsonify({'ok': True, 'atendimento_id': atend.id})


# ── Sucesso ────────────────────────────────────────────────────────────────────
@atendimentos_bp.route('/<int:id>/sucesso')
@login_required
def sucesso(id):
    atend = db.get_or_404(Atendimento, id)
    if not _no_escopo(atend):
        flash('Você não tem permissão para ver este atendimento.', 'danger')
        return redirect(url_for('atendimentos.index'))
    return render_template('atendimentos/sucesso.html', atend=atend)
