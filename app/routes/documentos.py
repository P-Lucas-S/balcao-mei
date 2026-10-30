import os
import uuid
from datetime import datetime, timezone
from flask import (Blueprint, request, redirect, url_for,
                   flash, send_file, abort, current_app)
from flask_login import login_required, current_user
from .. import db
from ..models import DocumentoPessoa, Pessoa

documentos_bp = Blueprint('documentos', __name__, url_prefix='/documentos')

TIPOS_DOC = {
    'rg_cnh':               'RG / CNH',
    'comprovante_endereco': 'Comprovante de Endereço',
    'cnpj_mei':             'Comprovante CNPJ / MEI',
    'outro':                'Outro',
}
EXTENSOES = {'jpg', 'jpeg', 'png', 'pdf'}


def _ext_ok(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES


def _pasta(pessoa_id):
    p = os.path.join(current_app.config['UPLOAD_DOCUMENTOS'], str(pessoa_id))
    os.makedirs(p, exist_ok=True)
    return p


def _log(acao, entidade_id, descricao):
    from .pessoas import _registrar_log
    _registrar_log(acao=acao, entidade='documento',
                   entidade_id=entidade_id, descricao=descricao)


@documentos_bp.route('/upload/<int:pessoa_id>', methods=['POST'])
@login_required
def upload(pessoa_id):
    pessoa  = db.get_or_404(Pessoa, pessoa_id)
    arquivo = request.files.get('arquivo')
    tipo    = request.form.get('tipo', '').strip()

    if not arquivo or arquivo.filename == '':
        flash('Selecione um arquivo.', 'danger')
        return redirect(url_for('pessoas.detalhe', id=pessoa_id))

    if not _ext_ok(arquivo.filename):
        flash('Formato não permitido. Use JPG, PNG ou PDF.', 'danger')
        return redirect(url_for('pessoas.detalhe', id=pessoa_id))

    if tipo not in TIPOS_DOC:
        flash('Tipo de documento inválido.', 'danger')
        return redirect(url_for('pessoas.detalhe', id=pessoa_id))

    # Desativa versão anterior do mesmo tipo (ignora as já removidas)
    DocumentoPessoa.query.filter_by(
        id_pessoa=pessoa_id, tipo=tipo, ativo=True
    ).filter(
        DocumentoPessoa.removido_em.is_(None)
    ).update({'ativo': False})

    # Salva arquivo
    ext      = arquivo.filename.rsplit('.', 1)[1].lower()
    nome_arq = f"{tipo}_{uuid.uuid4().hex[:8]}.{ext}"
    arquivo.save(os.path.join(_pasta(pessoa_id), nome_arq))

    doc = DocumentoPessoa(
        id_pessoa  = pessoa_id,
        tipo       = tipo,
        descricao  = request.form.get('descricao', '').strip() or None,
        arquivo    = os.path.join(str(pessoa_id), nome_arq),
        id_usuario = current_user.id,
    )
    db.session.add(doc)
    db.session.flush()
    _log('upload', doc.id,
         f'Upload de {TIPOS_DOC[tipo]} para {pessoa.nome_razao_social} (id={pessoa_id})')
    db.session.commit()

    flash(f'"{TIPOS_DOC[tipo]}" enviado com sucesso.', 'success')
    return redirect(url_for('pessoas.detalhe', id=pessoa_id))


@documentos_bp.route('/ver/<int:doc_id>')
@login_required
def ver(doc_id):
    doc  = db.get_or_404(DocumentoPessoa, doc_id)
    if doc.removido_em is not None:
        abort(404)
    path = os.path.join(current_app.config['UPLOAD_DOCUMENTOS'], doc.arquivo)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False)


@documentos_bp.route('/baixar/<int:doc_id>')
@login_required
def baixar(doc_id):
    doc  = db.get_or_404(DocumentoPessoa, doc_id)
    if doc.removido_em is not None:
        abort(404)
    path = os.path.join(current_app.config['UPLOAD_DOCUMENTOS'], doc.arquivo)
    if not os.path.exists(path):
        abort(404)
    ext  = doc.arquivo.rsplit('.', 1)[1]
    nome = f"{TIPOS_DOC.get(doc.tipo, doc.tipo)}_{doc.pessoa.nome_razao_social[:30]}.{ext}"
    return send_file(path, as_attachment=True, download_name=nome)


_PERFIS_REMOVER = {'administrador'}


@documentos_bp.route('/remover/<int:doc_id>', methods=['POST'])
@login_required
def remover(doc_id):
    doc       = db.get_or_404(DocumentoPessoa, doc_id)
    pessoa_id = doc.id_pessoa

    if current_user.perfil.nome not in _PERFIS_REMOVER:
        flash('Você não tem permissão para remover documentos. '
              'Solicite a remoção para análise da administração.', 'danger')
        return redirect(url_for('pessoas.detalhe', id=pessoa_id, aba='documentos'))

    if doc.removido_em is not None:
        flash('Este documento já foi removido.', 'warning')
        return redirect(url_for('pessoas.detalhe', id=pessoa_id, aba='documentos'))

    # Exclusão lógica — o arquivo em disco é preservado
    doc.removido_em  = datetime.now(timezone.utc)
    doc.removido_por = current_user.id

    _log('exclusao', doc.id,
         f'Remoção de {TIPOS_DOC.get(doc.tipo)} de pessoa id={pessoa_id} '
         f'(exclusão lógica — arquivo preservado)')

    db.session.commit()
    flash('Documento removido.', 'success')
    return redirect(url_for('pessoas.detalhe', id=pessoa_id, aba='documentos'))
