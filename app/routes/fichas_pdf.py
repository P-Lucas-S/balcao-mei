"""
fichas_pdf.py — v4
Gera o requerimento do empreendedor em PDF.
v4: quebra de linha automática nos campos de texto longo (credenciamento e solicitação).
"""
from app import marca
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


def _limpar_none(valor):
    if not valor or str(valor).strip().lower() == 'none':
        return ''
    return str(valor)


def _fit_text(c, text, font, size, max_w):
    """Trunca texto com reticências se não couber na largura."""
    if not text:
        return ''
    if c.stringWidth(text, font, size) <= max_w:
        return text
    while text and c.stringWidth(text + '\u2026', font, size) > max_w:
        text = text[:-1]
    return (text + '\u2026') if text else ''



def gerar_requerimento(dados, logo_path):
    buf = BytesIO()
    W, H = A4
    ML   = 45
    MR   = 45
    TW   = W - ML - MR
    ROW_H   = 22
    LINE_GAP = 22

    c = canvas.Canvas(buf, pagesize=A4)

    y = H - 35

    # ── Logo ─────────────────────────────────────────────────────────────────
    if os.path.exists(logo_path):
        logo_w, logo_h = 200, 100
        c.drawImage(logo_path, (W - logo_w) / 2, y - logo_h,
                    width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    y -= 112

    # ── Título ────────────────────────────────────────────────────────────────
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(W / 2, y, 'REQUERIMENTO')
    y -= 16

    protocolo = dados.get('protocolo', '')
    atendente = dados.get('atendente', '')
    if protocolo:
        c.setFont('Helvetica', 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(W / 2, y - 2,
            f'Protocolo: {protocolo}')
        y -= 12
        if atendente:
            from datetime import datetime as _dt
            agora = _dt.now().strftime('%d/%m/%Y às %H:%M')
            c.drawCentredString(W / 2, y,
                f'Gerado por {atendente} em {agora} — {marca.APP_NOME}')
            y -= 8
        c.setFillColorRGB(0, 0, 0)

    # ── Tabela DADOS DO EMPREENDEDOR ──────────────────────────────────────────
    HDR_H = 16
    c.setFillColorRGB(0.82, 0.82, 0.82)
    c.rect(ML, y - HDR_H, TW, HDR_H, stroke=1, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(W / 2, y - HDR_H + 5, 'DADOS DO EMPREENDEDOR')
    y -= HDR_H

    def _row(y_bot, label, value, x=ML, w=TW):
        c.rect(x, y_bot, w, ROW_H, stroke=1, fill=0)
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(x + 4, y_bot + 7, label)
        lw = c.stringWidth(label, 'Helvetica-Bold', 8)
        val = _limpar_none(value)
        if val:
            val = _fit_text(c, val, 'Helvetica', 9, w - lw - 10)
            c.setFont('Helvetica', 9)
            c.drawString(x + 4 + lw + 3, y_bot + 7, val)

    y -= ROW_H
    _row(y, 'NOME:', dados.get('nome', ''))
    y -= ROW_H
    half = TW / 2
    _row(y, 'CPF:',  dados.get('cpf', ''),  x=ML,        w=half)
    _row(y, 'CNPJ:', dados.get('cnpj', ''), x=ML + half, w=half)
    y -= ROW_H
    _row(y, 'ENDEREÇO:', dados.get('endereco', ''))
    y -= ROW_H
    _row(y, 'CONTATO WHATSAPP:', dados.get('whatsapp', ''))

    y -= 14

    # ── Parágrafo introdutório ────────────────────────────────────────────────
    c.setFont('Helvetica', 9)
    c.drawString(ML, y,
        f'O Empreendedor acima identificado vem requerer junto \u00e0')
    y -= 13
    c.drawString(ML, y, f'{marca.ORG_COMPLETO_UP} o abaixo exposto:')
    y -= 20

    def _linha_vazia(y_linha):
        c.setStrokeColorRGB(0, 0, 0)
        c.line(ML, y_linha, ML + TW, y_linha)

    def _bloco_com_texto(y_inicio, label, valor, n_linhas_total=3):
        """
        Desenha exatamente n_linhas_total linhas guia.
        O texto é distribuído sobre essas linhas — se sobrar texto, trunca com reticências.
        Linhas sem texto ficam vazias para escrita manual.
        """
        lw = c.stringWidth(label, 'Helvetica-Bold', 9)

        val = _limpar_none(valor)

        # Primeira linha: espaço disponível descontando o label
        espaco_primeira = TW - lw - 8
        # Demais linhas: largura total
        espaco_restante = TW - 4

        # Quebra o texto considerando larguras diferentes para primeira e demais linhas
        linhas_texto = []
        if val:
            palavras = val.split()
            linha_atual = ''
            primeira = True

            for palavra in palavras:
                max_w = espaco_primeira if primeira else espaco_restante

                # Palavra maior que a largura — quebra por caractere
                if c.stringWidth(palavra, 'Helvetica', 9) > max_w:
                    if linha_atual:
                        linhas_texto.append(linha_atual)
                        linha_atual = ''
                        primeira = False
                    while c.stringWidth(palavra, 'Helvetica', 9) > max_w:
                        i = len(palavra)
                        while i > 1 and c.stringWidth(palavra[:i], 'Helvetica', 9) > max_w:
                            i -= 1
                        linhas_texto.append(palavra[:i])
                        palavra = palavra[i:]
                        primeira = False
                    linha_atual = palavra
                    continue

                teste = (linha_atual + ' ' + palavra).strip()
                max_w_teste = espaco_primeira if primeira else espaco_restante
                if c.stringWidth(teste, 'Helvetica', 9) <= max_w_teste:
                    linha_atual = teste
                else:
                    linhas_texto.append(linha_atual)
                    linha_atual = palavra
                    primeira = False

            if linha_atual:
                linhas_texto.append(linha_atual)

        # Trunca ao número de linhas disponíveis
        if len(linhas_texto) > n_linhas_total:
            linhas_texto = linhas_texto[:n_linhas_total]
            ultima = linhas_texto[-1]
            # Última linha: se for a primeira, desconta o label; senão usa largura total
            idx_ultima = n_linhas_total - 1
            max_w = espaco_primeira if idx_ultima == 0 else espaco_restante
            while ultima and c.stringWidth(ultima + '\u2026', 'Helvetica', 9) > max_w:
                ultima = ultima[:-1]
            linhas_texto[-1] = ultima + '\u2026'

        y_atual = y_inicio

        for i in range(n_linhas_total):
            _linha_vazia(y_atual)
            if i < len(linhas_texto) and linhas_texto[i]:
                ty = y_atual + 4
                if i == 0:
                    # Primeira linha: label + texto
                    c.setFont('Helvetica-Bold', 9)
                    c.drawString(ML, ty, label)
                    c.setFont('Helvetica', 9)
                    c.drawString(ML + lw + 4, ty, linhas_texto[i])
                else:
                    # Demais linhas: só texto, começando em ML
                    c.setFont('Helvetica', 9)
                    c.drawString(ML + 4, ty, linhas_texto[i])
            elif i == 0:
                # Primeira linha sem texto: só label
                c.setFont('Helvetica-Bold', 9)
                c.drawString(ML, y_atual + 4, label)

            if i < n_linhas_total - 1:
                y_atual -= LINE_GAP

        return y_atual

    # ── CREDENCIAMENTO / EVENTO ───────────────────────────────────────────────
    y = _bloco_com_texto(y, 'CREDENCIAMENTO / EVENTO:',
                         dados.get('credenciamento_evento', ''),
                         n_linhas_total=3)
    y -= 18

    # ── SOLICITAÇÃO ───────────────────────────────────────────────────────────
    y = _bloco_com_texto(y, 'SOLICITAÇÃO:',
                         dados.get('solicitacao', ''),
                         n_linhas_total=10)
    y -= 30

    # ── Data de protocolo ─────────────────────────────────────────────────────
    c.setFont('Helvetica', 9)
    c.drawCentredString(W / 2, y,
        f'{marca.MUNICIPIO}, _______ de _________________________ de _________')
    y -= 14

    # Termo de veracidade
    c.setFont('Helvetica', 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(W / 2, y,
        'Declaro sob as penas da lei que as informações prestadas são verdadeiras.')
    c.setFillColorRGB(0, 0, 0)
    y -= 38

    # Assinaturas
    sig_len = 190
    sig1_x  = ML + 20
    sig2_x  = W - MR - 20 - sig_len
    c.setStrokeColorRGB(0, 0, 0)
    c.line(sig1_x, y, sig1_x + sig_len, y)
    c.line(sig2_x, y, sig2_x + sig_len, y)
    c.setFont('Helvetica', 8)
    c.drawCentredString(sig1_x + sig_len / 2, y - 12,
        'Assinatura do Empreendedor')
    c.drawCentredString(sig2_x + sig_len / 2, y - 12,
        'Agente de Desenvolvimento - AD')
    y -= 32

    # Campo de data de recebimento
    c.setFont('Helvetica', 8)
    c.drawCentredString(sig2_x + sig_len / 2, y,
        'Data de recebimento: ___/___/______')

    # ── Rodapé ────────────────────────────────────────────────────────────────
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(W / 2, 20, f'{marca.ORG_COMPLETO_UP}')

    c.save()
    buf.seek(0)
    return buf


def gerar_requerimento_assistido(dados, logo_path):
    """Modo assistido: dados preenchidos, campo de justificativa em branco para preenchimento manual."""
    buf = BytesIO()
    W, H = A4
    ML   = 45
    MR   = 45
    TW   = W - ML - MR
    ROW_H   = 22
    LINE_GAP = 22

    c = canvas.Canvas(buf, pagesize=A4)
    y = H - 35

    # Logo
    if os.path.exists(logo_path):
        logo_w, logo_h = 200, 100
        c.drawImage(logo_path, (W - logo_w) / 2, y - logo_h,
                    width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    y -= 112

    # Título
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(W / 2, y, 'REQUERIMENTO')
    y -= 16

    protocolo = dados.get('protocolo', '')
    atendente = dados.get('atendente', '')
    if protocolo:
        c.setFont('Helvetica', 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(W / 2, y - 2, f'Protocolo: {protocolo}')
        y -= 12
        if atendente:
            from datetime import datetime as _dt
            agora = _dt.now().strftime('%d/%m/%Y às %H:%M')
            c.drawCentredString(W / 2, y,
                f'Gerado por {atendente} em {agora} — Modo Assistido')
            y -= 8
        c.setFillColorRGB(0, 0, 0)

    # Tabela DADOS DO EMPREENDEDOR
    HDR_H = 16
    c.setFillColorRGB(0.82, 0.82, 0.82)
    c.rect(ML, y - HDR_H, TW, HDR_H, stroke=1, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(W / 2, y - HDR_H + 5, 'DADOS DO EMPREENDEDOR')
    y -= HDR_H

    def _row(y_bot, label, value, x=ML, w=TW):
        c.rect(x, y_bot, w, ROW_H, stroke=1, fill=0)
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(x + 4, y_bot + 7, label)
        lw = c.stringWidth(label, 'Helvetica-Bold', 8)
        val = _limpar_none(value)
        if val:
            val = _fit_text(c, val, 'Helvetica', 9, w - lw - 10)
            c.setFont('Helvetica', 9)
            c.drawString(x + 4 + lw + 3, y_bot + 7, val)

    y -= ROW_H
    _row(y, 'NOME:', dados.get('nome', ''))
    y -= ROW_H
    half = TW / 2
    _row(y, 'CPF:',  dados.get('cpf', ''),  x=ML,        w=half)
    _row(y, 'CNPJ:', dados.get('cnpj', ''), x=ML + half, w=half)
    y -= ROW_H
    _row(y, 'ENDEREÇO:', dados.get('endereco', ''))
    y -= ROW_H
    _row(y, 'CONTATO WHATSAPP:', dados.get('whatsapp', ''))
    y -= ROW_H
    _row(y, 'TIPO DE SOLICITAÇÃO:', dados.get('tipo_solicitacao', ''))

    y -= 14

    # Parágrafo introdutório
    c.setFont('Helvetica', 9)
    c.drawString(ML, y,
        f'O Empreendedor acima identificado vem requerer junto à')
    y -= 13
    c.drawString(ML, y, f'{marca.ORG_COMPLETO_UP} o abaixo exposto:')
    y -= 20

    def _linha_vazia(y_linha):
        c.setStrokeColorRGB(0, 0, 0)
        c.line(ML, y_linha, ML + TW, y_linha)

    # CREDENCIAMENTO / EVENTO — preenchido se houver
    cred = dados.get('credenciamento_evento', '')
    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML, y + 4, 'CREDENCIAMENTO / EVENTO:')
    lw = c.stringWidth('CREDENCIAMENTO / EVENTO:', 'Helvetica-Bold', 9)
    if cred:
        c.setFont('Helvetica', 9)
        val = _fit_text(c, cred, 'Helvetica', 9, TW - lw - 8)
        c.drawString(ML + lw + 4, y + 4, val)
    _linha_vazia(y)
    y -= LINE_GAP
    _linha_vazia(y)
    y -= LINE_GAP
    _linha_vazia(y)
    y -= 18

    # SOLICITAÇÃO — linhas em branco para o empreendedor preencher
    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML, y + 4, 'SOLICITAÇÃO:')
    _linha_vazia(y)
    for _ in range(9):
        y -= LINE_GAP
        _linha_vazia(y)
    y -= 25

    # Data
    c.setFont('Helvetica', 9)
    c.drawCentredString(W / 2, y,
        f'{marca.MUNICIPIO}, _______ de _________________________ de _________')
    y -= 14

    # Termo de veracidade
    c.setFont('Helvetica', 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(W / 2, y,
        'Declaro sob as penas da lei que as informações prestadas são verdadeiras.')
    c.setFillColorRGB(0, 0, 0)
    y -= 38

    # Assinaturas
    sig_len = 190
    sig1_x  = ML + 20
    sig2_x  = W - MR - 20 - sig_len
    c.setStrokeColorRGB(0, 0, 0)
    c.line(sig1_x, y, sig1_x + sig_len, y)
    c.line(sig2_x, y, sig2_x + sig_len, y)
    c.setFont('Helvetica', 8)
    c.drawCentredString(sig1_x + sig_len / 2, y - 12, 'Assinatura do Empreendedor')
    c.drawCentredString(sig2_x + sig_len / 2, y - 12, 'Agente de Desenvolvimento - AD')
    y -= 32

    c.setFont('Helvetica', 8)
    c.drawCentredString(sig2_x + sig_len / 2, y,
        'Data de recebimento: ___/___/______')

    # Rodapé
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(W / 2, 20, f'{marca.ORG_COMPLETO_UP}')

    c.save()
    buf.seek(0)
    return buf