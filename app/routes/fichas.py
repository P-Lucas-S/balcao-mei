import re
import os
from datetime import datetime as dt
from flask import (Blueprint, render_template, request, send_file,
                   current_app, redirect, url_for, flash)
from flask_login import login_required, current_user
from ..models import Pessoa, Evento, RequerimentoGerado, Solicitacao, ParametroMunicipio
from .. import db

_MODELOS_PADRAO = [
    ('modelo_requerimento_1', 'Modelo: Participar de Evento',
     'Venho por meio deste solicitar autorização para participar como '
     'expositor/vendedor no evento a ser realizado nesta municipalidade, '
     'comprometendo-me a cumprir todas as normas e regulamentos '
     'estabelecidos pela organização.'),
    ('modelo_requerimento_2', 'Modelo: Espaço Público',
     'Venho respeitosamente solicitar a concessão de uso de espaço público '
     'para exercício de atividade comercial, declarando estar em '
     'conformidade com as exigências legais e comprometendo-me a zelar '
     'pela conservação do espaço concedido.'),
    ('modelo_requerimento_3', 'Modelo: Box/Mercado',
     'Venho por meio deste requerer a concessão de box/espaço no mercado '
     'público municipal para exercício de atividade comercial, '
     'comprometendo-me a cumprir o regulamento interno e manter o espaço '
     'em perfeitas condições de higiene e conservação.'),
    ('modelo_requerimento_4', 'Modelo: Feira/Exposição',
     'Solicito autorização para participar como expositor na feira/'
     'exposição municipal, comprometendo-me a obedecer às normas '
     'estabelecidas pela organização do evento e a manter meu espaço '
     'organizado durante todo o período de realização.'),
    ('modelo_requerimento_5', 'Modelo: Quiosque/Trailer',
     'Venho solicitar autorização para instalação e operação de quiosque/'
     'trailer em área pública desta municipalidade, declarando estar em '
     'regularidade com todas as exigências fiscais e sanitárias '
     'pertinentes à atividade.'),
    ('modelo_requerimento_6', 'Modelo: Regularização',
     'Venho por este meio solicitar orientações e apoio para regularização '
     'da minha atividade econômica junto aos órgãos competentes, buscando '
     'formalizar meu negócio e obter os benefícios da regularidade '
     'fiscal e previdenciária.'),
]

def _garantir_modelos_padrao():
    alterou = False
    for chave, descricao, valor in _MODELOS_PADRAO:
        if not ParametroMunicipio.query.filter_by(chave=chave).first():
            db.session.add(ParametroMunicipio(chave=chave, valor=valor, descricao=descricao))
            alterou = True
    if alterou:
        db.session.commit()


def _carregar_modelos():
    return (ParametroMunicipio.query
            .filter(ParametroMunicipio.chave.like('modelo_requerimento_%'))
            .order_by(ParametroMunicipio.chave)
            .all())


def _gerar_protocolo():
    ano = dt.now().year
    ultimo = (RequerimentoGerado.query
              .filter(RequerimentoGerado.protocolo.like(f'REQ-{ano}-%'))
              .order_by(RequerimentoGerado.id.desc())
              .first())
    n = int(ultimo.protocolo.split('-')[-1]) + 1 if ultimo else 1
    return f'REQ-{ano}-{n:04d}'


def _nome_pdf(nome, protocolo):
    nome_limpo = re.sub(r'[^\w\s-]', '', nome).strip().replace(' ', '_')[:30]
    return f'Requerimento_{protocolo}_{nome_limpo}_{dt.now().strftime("%d-%m-%Y")}.pdf'


fichas_bp = Blueprint('fichas', __name__, url_prefix='/fichas')


# ── Rota legada (mantida para não quebrar bookmarks antigos) ──────────────────
@fichas_bp.route('/')
@login_required
def index():
    return redirect(url_for('fichas.form', pessoa_id=0))


@fichas_bp.route('/<int:pessoa_id>/form')
@login_required
def form(pessoa_id):
    _garantir_modelos_padrao()
    pessoa  = None if pessoa_id == 0 else db.get_or_404(Pessoa, pessoa_id)
    pessoas = Pessoa.visiveis().order_by(Pessoa.nome_razao_social).all()
    eventos = Evento.query.order_by(Evento.descricao).all()
    modelos = _carregar_modelos()
    return render_template('fichas/form.html', pessoa=pessoa,
                           pessoas=pessoas, eventos=eventos,
                           modelos=modelos,
                           sol_id=None, sol_tipo=None, sol_descricao='')


@fichas_bp.route('/de-solicitacao/<int:sol_id>')
@login_required
def de_solicitacao(sol_id):
    return redirect(url_for('fichas.emitir', sol_id=sol_id))


@fichas_bp.route('/gerar', methods=['POST'])
@login_required
def gerar():
    from .fichas_pdf import gerar_requerimento

    dados = {k: request.form.get(k, '').strip()
             for k in ('nome', 'cpf', 'cnpj', 'endereco', 'whatsapp',
                       'credenciamento_evento', 'solicitacao')}

    if not dados.get('nome'):
        flash('Nome é obrigatório para gerar o requerimento.', 'danger')
        return redirect(url_for('fichas.index'))

    protocolo = _gerar_protocolo()
    pessoa_id = request.form.get('pessoa_id', type=int)
    sol_id    = request.form.get('sol_id', type=int)

    req = RequerimentoGerado(
        protocolo=protocolo,
        id_usuario=current_user.id,
        id_pessoa=pessoa_id or None,
        nome_manual=dados['nome'] if not pessoa_id else None,
        cpf_manual=dados['cpf']   if not pessoa_id else None,
        cnpj_manual=dados['cnpj'] if not pessoa_id else None,
        credenciamento_evento=dados.get('credenciamento_evento') or None,
        solicitacao=dados.get('solicitacao') or None,
        id_solicitacao=sol_id or None,
        modo_emissao='digital',
        status_requerimento='gerado',
    )
    db.session.add(req)
    db.session.commit()

    dados['protocolo'] = protocolo
    dados['atendente'] = current_user.nome
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    pdf_buf   = gerar_requerimento(dados, logo_path)
    return send_file(pdf_buf, mimetype='application/pdf',
                     as_attachment=False,
                     download_name=_nome_pdf(dados.get('nome', 'empreendedor'), protocolo))


# ── NOVA TELA DE EMISSÃO ──────────────────────────────────────────────────────

@fichas_bp.route('/emitir/<int:sol_id>')
@login_required
def emitir(sol_id):
    _garantir_modelos_padrao()
    sol     = db.get_or_404(Solicitacao, sol_id)
    modelos = _carregar_modelos()
    historico = (RequerimentoGerado.query
                 .filter_by(id_solicitacao=sol_id)
                 .order_by(RequerimentoGerado.id.desc())
                 .all())
    return render_template('fichas/emitir.html',
                           sol=sol,
                           modelos=modelos,
                           historico=historico)


@fichas_bp.route('/emitir/<int:sol_id>/digital', methods=['POST'])
@login_required
def emitir_digital(sol_id):
    from .fichas_pdf import gerar_requerimento
    sol = db.get_or_404(Solicitacao, sol_id)
    p   = sol.pessoa

    justificativa = request.form.get('justificativa', '').strip()
    protocolo     = _gerar_protocolo()

    dados = {
        'nome':                 p.nome_razao_social,
        'cpf':                  p.cpf or '',
        'cnpj':                 p.cnpj or '',
        'endereco':             p.endereco or '',
        'whatsapp':             p.telefone or '',
        'credenciamento_evento': sol.evento.descricao if sol.evento else '',
        'solicitacao':          justificativa,
        'protocolo':            protocolo,
        'atendente':            current_user.nome,
    }

    req = RequerimentoGerado(
        protocolo=protocolo,
        id_usuario=current_user.id,
        id_pessoa=p.id,
        id_solicitacao=sol_id,
        modo_emissao='digital',
        status_requerimento='gerado',
    )
    db.session.add(req)
    db.session.commit()

    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    pdf_buf   = gerar_requerimento(dados, logo_path)
    return send_file(pdf_buf, mimetype='application/pdf',
                     as_attachment=False,
                     download_name=_nome_pdf(p.nome_razao_social, protocolo))


@fichas_bp.route('/emitir/<int:sol_id>/assistido', methods=['POST'])
@login_required
def emitir_assistido(sol_id):
    from .fichas_pdf import gerar_requerimento_assistido
    sol = db.get_or_404(Solicitacao, sol_id)
    p   = sol.pessoa

    protocolo = _gerar_protocolo()

    dados = {
        'nome':                  p.nome_razao_social,
        'cpf':                   p.cpf or '',
        'cnpj':                  p.cnpj or '',
        'endereco':              p.endereco or '',
        'whatsapp':              p.telefone or '',
        'tipo_solicitacao':      sol.tipo_solicitacao.descricao,
        'credenciamento_evento': sol.evento.descricao if sol.evento else '',
        'protocolo':             protocolo,
        'atendente':             current_user.nome,
    }

    req = RequerimentoGerado(
        protocolo=protocolo,
        id_usuario=current_user.id,
        id_pessoa=p.id,
        id_solicitacao=sol_id,
        modo_emissao='assistido',
        status_requerimento='gerado',
    )
    db.session.add(req)
    db.session.commit()

    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    pdf_buf   = gerar_requerimento_assistido(dados, logo_path)
    return send_file(pdf_buf, mimetype='application/pdf',
                     as_attachment=False,
                     download_name=_nome_pdf(p.nome_razao_social, protocolo))


@fichas_bp.route('/emitir/<int:sol_id>/manual', methods=['POST'])
@login_required
def emitir_manual(sol_id):
    sol = db.get_or_404(Solicitacao, sol_id)
    obs = request.form.get('observacao', '').strip()

    protocolo = _gerar_protocolo()
    req = RequerimentoGerado(
        protocolo=protocolo,
        id_usuario=current_user.id,
        id_pessoa=sol.pessoa.id,
        id_solicitacao=sol_id,
        modo_emissao='manual',
        status_requerimento='entregue',
        observacao_manual=obs or None,
    )
    db.session.add(req)
    db.session.commit()

    flash(f'Emissão manual registrada — protocolo {protocolo}.', 'success')
    return redirect(url_for('fichas.emitir', sol_id=sol_id))


# ── Re-download de PDF ────────────────────────────────────────────────────────

@fichas_bp.route('/requerimento/<int:req_id>/pdf')
@login_required
def baixar_pdf(req_id):
    from .fichas_pdf import gerar_requerimento, gerar_requerimento_assistido
    req = db.session.get(RequerimentoGerado, req_id)
    if not req or req.modo_emissao == 'manual':
        flash('PDF não disponível para este registro.', 'danger')
        if req and req.id_solicitacao:
            return redirect(url_for('fichas.emitir', sol_id=req.id_solicitacao))
        return redirect(url_for('fichas.index'))

    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    p = req.pessoa or None

    if req.modo_emissao == 'assistido':
        sol = req.solicitacao_ref
        dados = {
            'nome':                  p.nome_razao_social if p else (req.nome_manual or ''),
            'cpf':                   (p.cpf if p else req.cpf_manual) or '',
            'cnpj':                  (p.cnpj if p else req.cnpj_manual) or '',
            'endereco':              p.endereco if p else '',
            'whatsapp':              p.telefone if p else '',
            'tipo_solicitacao':      sol.tipo_solicitacao.descricao if sol else '',
            'credenciamento_evento': sol.evento.descricao if sol and sol.evento else '',
            'protocolo':             req.protocolo,
            'atendente':             req.usuario.nome if req.usuario else '',
        }
        pdf_buf = gerar_requerimento_assistido(dados, logo_path)
    else:
        sol = req.solicitacao_ref
        dados = {
            'nome':                  p.nome_razao_social if p else (req.nome_manual or ''),
            'cpf':                   (p.cpf if p else req.cpf_manual) or '',
            'cnpj':                  (p.cnpj if p else req.cnpj_manual) or '',
            'endereco':              p.endereco if p else '',
            'whatsapp':              p.telefone if p else '',
            'credenciamento_evento': (sol.evento.descricao if sol and sol.evento else '') or (req.credenciamento_evento or ''),
            'solicitacao':           req.solicitacao or '',
            'protocolo':             req.protocolo,
            'atendente':             req.usuario.nome if req.usuario else '',
        }
        pdf_buf = gerar_requerimento(dados, logo_path)

    nome = p.nome_razao_social if p else (req.nome_manual or 'empreendedor')
    return send_file(pdf_buf, mimetype='application/pdf',
                     as_attachment=False,
                     download_name=_nome_pdf(nome, req.protocolo))

