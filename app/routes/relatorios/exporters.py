"""
relatorios/exporters.py
Exportação para PDF (ReportLab) e Excel (openpyxl).
Sem dependência de WeasyPrint — ReportLab é mais estável no Windows.
"""
from app import marca
import io
import os
from datetime import datetime
from flask import current_app

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# ── openpyxl ───────────────────────────────────────────────────────────────
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import MergedCell
from openpyxl.drawing.spreadsheet_drawing import AbsoluteAnchor
from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------
COR_ESCURA   = colors.HexColor("#0f4c5c")
AZUL_MEDIO   = colors.HexColor("#2563EB")
AZUL_CLARO   = colors.HexColor("#DBEAFE")
CINZA_LINHA  = colors.HexColor("#F1F5F9")
VERDE        = colors.HexColor("#16A34A")
VERMELHO     = colors.HexColor("#DC2626")
AMARELO      = colors.HexColor("#D97706")
BRANCO       = colors.white

# ---------------------------------------------------------------------------
# Helpers compartilhados
# ---------------------------------------------------------------------------

def _fmt_data(valor):
    if valor is None:
        return "—"
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _fmt_hora(valor):
    if valor is None:
        return "—"
    if hasattr(valor, "strftime"):
        return valor.strftime("%H:%M")
    return str(valor)


def _status_color(status: str):
    mapa = {
        "Concluído":    VERDE,
        "Pendente":     AMARELO,
        "Em Andamento": AZUL_MEDIO,
        "Cancelado":    VERMELHO,
    }
    return mapa.get(status, colors.black)


def _cabecalho_pdf(elements, titulo, subtitulo, styles):
    """Bloco de cabeçalho padrão com logo."""
    from reportlab.platypus import Image
    from reportlab.lib.utils import ImageReader

    logo_path = os.path.join(
        current_app.root_path, 'static', 'img', 'logo.png'
    )
    if os.path.exists(logo_path):
        img_reader = ImageReader(logo_path)
        iw, ih = img_reader.getSize()
        ratio = ih / iw
        logo_w = 10 * cm
        logo = Image(logo_path, width=logo_w, height=logo_w * ratio)
        logo.hAlign = 'CENTER'
        elements.append(logo)
        elements.append(Spacer(1, 4))
    else:
        elements.append(
            Paragraph(
                f"{marca.APP_NOME_UP}",
                ParagraphStyle("inst", parent=styles["Normal"],
                               fontSize=8, textColor=COR_ESCURA,
                               spaceAfter=1, alignment=1)
            )
        )
        elements.append(
            Paragraph(
                f"{marca.ORG_NOME}",
                ParagraphStyle("setor", parent=styles["Normal"],
                               fontSize=9, textColor=COR_ESCURA,
                               spaceAfter=2, alignment=1,
                               fontName="Helvetica-Bold")
            )
        )

    elements.append(
        Paragraph(
            titulo,
            ParagraphStyle("titulo", parent=styles["Normal"],
                           fontSize=14, textColor=COR_ESCURA,
                           spaceBefore=4, spaceAfter=2,
                           alignment=1, fontName="Helvetica-Bold")
        )
    )
    elements.append(
        Paragraph(
            subtitulo,
            ParagraphStyle("sub", parent=styles["Normal"],
                           fontSize=9, textColor=colors.HexColor("#64748B"),
                           spaceAfter=4, alignment=1)
        )
    )
    elements.append(
        HRFlowable(width="100%", thickness=1.5,
                   color=AZUL_MEDIO, spaceAfter=8)
    )


def _rodape_pdf(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(1.5 * cm, 0.8 * cm,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}  –  {marca.APP_NOME} / {marca.CIDADE_UF}")
    canvas.drawRightString(
        doc.pagesize[0] - 1.5 * cm, 0.8 * cm,
        f"Página {doc.page}"
    )
    canvas.restoreState()


# ===========================================================================
# PDF – Atendimentos por período
# ===========================================================================

def gerar_pdf_atendimentos(dados: list, filtros: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm,    bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    periodo = (
        f"{_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"
    )
    atendente = filtros.get("usuario_nome") or "Todos os atendentes"
    _cabecalho_pdf(
        elements,
        "Relatório de Atendimentos por Período",
        f"Período: {periodo}   |   Atendente: {atendente}   |   Total: {len(dados)} registro(s)",
        styles,
    )

    cabecalhos = ["Nº", "Data", "Hora", "Cidadão", "CPF", "Atendente", "Observação"]
    linhas = [cabecalhos]

    for r in dados:
        linha = [
            str(r["id"]),
            _fmt_data(r["data_atendimento"]),
            _fmt_hora(r["hora_atendimento"]),
            r["pessoa_nome"] or "—",
            r["pessoa_cpf"] or "—",
            r["usuario_nome"] or "—",
            (r["observacoes"] or "—")[:60],
        ]
        linhas.append(linha)

    col_widths = [1.2*cm, 2.2*cm, 1.5*cm, 5*cm, 3.2*cm, 4*cm, 8*cm]

    tabela = Table(linhas, colWidths=col_widths, repeatRows=1)

    estilo_base = [
        ("BACKGROUND",  (0, 0), (-1, 0), COR_ESCURA),
        ("TEXTCOLOR",   (0, 0), (-1, 0), BRANCO),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("FONTSIZE",    (0, 1), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRANCO, CINZA_LINHA]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]

    tabela.setStyle(TableStyle(estilo_base))
    elements.append(tabela)

    if not dados:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(
            Paragraph(
                "Nenhum atendimento encontrado para os filtros selecionados.",
                ParagraphStyle("vazio", parent=styles["Normal"],
                               fontSize=10, textColor=colors.HexColor("#94A3B8"),
                               alignment=1)
            )
        )

    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=COR_ESCURA))
    elements.append(
        Paragraph(
            f"Período: {periodo}   |   Atendente: {atendente}   |   "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — {marca.ORG_COMPLETO_UP}",
            ParagraphStyle("rodape_hist", parent=styles["Normal"],
                           fontSize=7, textColor=colors.HexColor("#9ca3af"),
                           alignment=1, spaceBefore=4)
        )
    )

    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buffer.getvalue()


# ===========================================================================
# PDF – Desempenho por usuário/atendente
# ===========================================================================

def gerar_pdf_desempenho(dados: list, detalhes: dict, filtros: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm,    bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    periodo = (
        f"{_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"
    )
    _cabecalho_pdf(
        elements,
        "Relatório de Desempenho por Atendente",
        f"Período: {periodo}",
        styles,
    )

    cab = ["Atendente", "Total de Atendimentos"]
    linhas = [cab]
    for r in dados:
        linhas.append([
            r["usuario_nome"],
            str(r["total"]),
        ])

    larguras = [10*cm, 5*cm]
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), COR_ESCURA),
        ("TEXTCOLOR",   (0, 0), (-1, 0), BRANCO),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
        ("ALIGN",       (0, 0), (0, -1), "LEFT"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRANCO, CINZA_LINHA]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(tabela)
    elements.append(Spacer(1, 0.5 * cm))

    for r in dados:
        uid = r["usuario_id"]
        lista = detalhes.get(uid, [])
        if not lista:
            continue

        elements.append(
            Paragraph(
                f"Detalhamento – {r['usuario_nome']}",
                ParagraphStyle("det", parent=styles["Normal"],
                               fontSize=10, textColor=COR_ESCURA,
                               fontName="Helvetica-Bold",
                               spaceBefore=10, spaceAfter=4)
            )
        )

        cab2 = ["Nº", "Data", "Hora", "Cidadão", "Observação"]
        linhas2 = [cab2]
        for d in lista:
            linhas2.append([
                str(d["id"]),
                _fmt_data(d["data_atendimento"]),
                _fmt_hora(d["hora_atendimento"]),
                d["pessoa_nome"] or "—",
                (d["observacoes"] or "—")[:50],
            ])

        t2 = Table(linhas2, colWidths=[1.2*cm, 2.2*cm, 1.5*cm, 5*cm, 7*cm], repeatRows=1)
        estilo2 = [
            ("BACKGROUND",  (0, 0), (-1, 0), AZUL_MEDIO),
            ("TEXTCOLOR",   (0, 0), (-1, 0), BRANCO),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRANCO, CINZA_LINHA]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        t2.setStyle(TableStyle(estilo2))
        elements.append(t2)
        elements.append(Spacer(1, 0.3 * cm))

    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=COR_ESCURA))
    elements.append(
        Paragraph(
            f"Período: {periodo}   |   "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — {marca.ORG_COMPLETO_UP}",
            ParagraphStyle("rodape_hist_d", parent=styles["Normal"],
                           fontSize=7, textColor=colors.HexColor("#9ca3af"),
                           alignment=1, spaceBefore=4)
        )
    )

    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buffer.getvalue()


# ===========================================================================
# Excel – Atendimentos por período
# ===========================================================================

def _inserir_logo_excel(ws, logo_path: str, col: str = "A", row: int = 1,
                        width: int = 180, height: int = 60):
    """Insere a logo da instituição no Excel ancorada a um intervalo fixo."""
    if not os.path.exists(logo_path):
        return
    try:
        from openpyxl.drawing.image import Image as XlImage
        img = XlImage(logo_path)
        img.width  = 110   # px — largura fixa para não distorcer
        img.height = 55    # px — mantém proporção da logo
        img.anchor = f"{col}{row}"
        ws.add_image(img)
        ws.row_dimensions[row].height = height * 0.75
        ws.column_dimensions[col].width = max(ws.column_dimensions[col].width or 0, 15)
    except Exception:
        pass


def _estilo_excel_cabecalho(ws, titulo: str, subtitulo: str,
                             num_cols: int = 7,
                             logo_path: str = None,
                             col_widths: list = None):
    """Cabeçalho padrão — logo centralizada + texto em 7 linhas.

    L1-3: logo via AbsoluteAnchor (proporcional, centrada horizontalmente)
    L4:   título bold
    L5:   subtítulo
    L6:   gerado em (itálico cinza)
    L7:   separador vazio
    → cabeçalho na cor primária em L8; dados a partir de L9
    """
    img_w, img_h = 320, 160  # defaults sem Pillow
    if logo_path and os.path.exists(logo_path):
        # Dimensões proporcionais via Pillow
        try:
            from PIL import Image as PILImage
            with PILImage.open(logo_path) as pil_img:
                orig_w, orig_h = pil_img.size
            img_w = 320
            img_h = int(orig_h * img_w / orig_w)
        except Exception:
            pass
        # Inserir logo centralizada
        try:
            from openpyxl.drawing.image import Image as XlImage
            img = XlImage(logo_path)
            total_px = sum(w * 7 for w in col_widths) if col_widths else num_cols * 12 * 7
            x_off = max(0, (total_px - img_w) // 2)
            p2d  = XDRPoint2D(pixels_to_EMU(x_off), pixels_to_EMU(8))
            size = XDRPositiveSize2D(pixels_to_EMU(img_w), pixels_to_EMU(img_h))
            img.anchor = AbsoluteAnchor(pos=p2d, ext=size)
            ws.add_image(img)
        except Exception:
            pass
        pts = img_h / 0.75
        ws.row_dimensions[1].height = round(pts * 0.55)
        ws.row_dimensions[2].height = round(pts * 0.35)
        ws.row_dimensions[3].height = round(pts * 0.10)
    else:
        ws.row_dimensions[1].height = 4
        ws.row_dimensions[2].height = 4
        ws.row_dimensions[3].height = 4

    # L4 — título
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=num_cols)
    c4 = ws.cell(row=4, column=1, value=titulo)
    c4.font      = Font(bold=True, size=13, color='0F2A30')
    c4.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[4].height = 22

    # L5 — subtítulo
    ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=num_cols)
    c5 = ws.cell(row=5, column=1, value=subtitulo)
    c5.font      = Font(size=10, color='0f4c5c')
    c5.alignment = Alignment(horizontal='center')
    ws.row_dimensions[5].height = 16

    # L6 — gerado em
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=num_cols)
    c6 = ws.cell(row=6, column=1,
                 value=(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                        f" — {marca.ORG_COMPLETO}"))
    c6.font      = Font(size=9, italic=True, color='6b7280')
    c6.alignment = Alignment(horizontal='center')
    ws.row_dimensions[6].height = 14

    # L7 — separador
    ws.row_dimensions[7].height = 8


def _aplicar_linha_cabecalho(ws, row: int, colunas: list):
    fill_cab = PatternFill("solid", fgColor="0f4c5c")
    borda = Border(
        left=Side(style="medium", color="0f4c5c"),
        right=Side(style="medium", color="0f4c5c"),
        top=Side(style="medium", color="0f4c5c"),
        bottom=Side(style="medium", color="0f4c5c"),
    )
    for col_idx, nome in enumerate(colunas, start=1):
        c = ws.cell(row=row, column=col_idx, value=nome)
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = fill_cab
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = borda
    ws.row_dimensions[row].height = 18


def _aplicar_linha_total(ws, row: int, valores: list):
    """Linha de total roxa com borda."""
    fill_total = PatternFill("solid", fgColor="0f4c5c")
    borda = Border(
        left=Side(style="medium", color="0f4c5c"),
        right=Side(style="medium", color="0f4c5c"),
        top=Side(style="medium", color="0f4c5c"),
        bottom=Side(style="medium", color="0f4c5c"),
    )
    for col_idx, val in enumerate(valores, start=1):
        c = ws.cell(row=row, column=col_idx, value=val)
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = fill_total
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = borda
    ws.row_dimensions[row].height = 18


def _aplicar_linha_dado(ws, row: int, valores: list):
    fill_par  = PatternFill("solid", fgColor="F1F5F9")
    fill_impar = PatternFill("solid", fgColor="FFFFFF")
    borda = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    fill = fill_par if row % 2 == 0 else fill_impar
    for col_idx, val in enumerate(valores, start=1):
        c = ws.cell(row=row, column=col_idx, value=val)
        c.fill = fill
        c.border = borda
        c.font = Font(size=9)
        c.alignment = Alignment(vertical="center")


def gerar_excel_atendimentos(dados: list, totais_dia: list, filtros: dict, mostrar_horarios: bool = False) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    ws1 = wb.active
    ws1.title = "Atendimentos"
    ws1.sheet_view.showGridLines = False

    periodo = (
        f"Período: {_fmt_data(filtros.get('data_inicio'))} a "
        f"{_fmt_data(filtros.get('data_fim'))}"
        f"   |   Atendente: {filtros.get('usuario_nome') or 'Todos'}"
        f"   |   Total: {len(dados)} registro(s)"
    )
    _estilo_excel_cabecalho(ws1,
                            f"{marca.ORG_COMPLETO} — Relatório de Atendimentos",
                            periodo, num_cols=7, logo_path=logo_path)

    if mostrar_horarios:
        colunas = ["Nº", "Data", "Hora Atend.", "Cadastrado em", "Cidadão", "CPF", "Atendente", "Observação"]
        larguras_1 = [6, 12, 10, 18, 30, 16, 24, 40]
    else:
        colunas = ["Nº", "Data", "Hora", "Cidadão", "CPF", "Atendente", "Observação"]
        larguras_1 = [6, 12, 8, 30, 16, 24, 40]
    _aplicar_linha_cabecalho(ws1, 8, colunas)

    for i, r in enumerate(dados, start=9):
        valores = [
            r["id"],
            _fmt_data(r["data_atendimento"]),
            _fmt_hora(r["hora_atendimento"]),
        ]
        if mostrar_horarios:
            valores.append(
                r["created_at"].strftime("%d/%m/%Y %H:%M") if r.get("created_at") else "—"
            )
        valores += [
            r["pessoa_nome"] or "—",
            r["pessoa_cpf"] or "—",
            r["usuario_nome"] or "—",
            r["observacoes"] or "—",
        ]
        _aplicar_linha_dado(ws1, i, valores)

    for col_idx, larg in enumerate(larguras_1, start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg
    ws1.freeze_panes = "A9"

    ws2 = wb.create_sheet("Resumo por Dia")
    ws2.sheet_view.showGridLines = False

    _estilo_excel_cabecalho(ws2,
                            f"{marca.ORG_COMPLETO} — Atendimentos por Dia",
                            periodo, num_cols=2, logo_path=logo_path)

    _aplicar_linha_cabecalho(ws2, 8, ["Data", "Total"])

    for i, r in enumerate(totais_dia, start=9):
        _aplicar_linha_dado(ws2, i, [
            _fmt_data(r["data"]),
            r["total"],
        ])

    total_row = len(totais_dia) + 9
    _aplicar_linha_total(ws2, total_row, ["TOTAL", sum(r["total"] for r in totais_dia)])

    for col_idx, larg in enumerate([14, 10], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg
    ws2.freeze_panes = "A9"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ===========================================================================
# Excel – Desempenho por usuário
# ===========================================================================

def gerar_excel_desempenho(dados: list, detalhes: dict, filtros: dict) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    periodo = (
        f"Período: {_fmt_data(filtros.get('data_inicio'))} "
        f"a {_fmt_data(filtros.get('data_fim'))}"
    )

    ws1 = wb.active
    ws1.title = "Resumo por Atendente"
    ws1.sheet_view.showGridLines = False

    _estilo_excel_cabecalho(ws1,
                            f"{marca.ORG_COMPLETO} — Desempenho por Atendente",
                            periodo, num_cols=2, logo_path=logo_path)

    colunas = ["Atendente", "Total de Atendimentos"]
    _aplicar_linha_cabecalho(ws1, 8, colunas)

    for i, r in enumerate(dados, start=9):
        _aplicar_linha_dado(ws1, i, [
            r["usuario_nome"],
            r["total"],
        ])

    larguras_r = [30, 20]
    for col_idx, larg in enumerate(larguras_r, start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg
    ws1.freeze_panes = "A9"

    for r in dados:
        uid = r["usuario_id"]
        lista = detalhes.get(uid, [])
        nome_aba = r["usuario_nome"][:28]
        ws = wb.create_sheet(nome_aba)
        ws.sheet_view.showGridLines = False

        _estilo_excel_cabecalho(ws,
                                f"Detalhamento – {r['usuario_nome']}",
                                periodo, num_cols=5, logo_path=logo_path)

        cab = ["Nº", "Data", "Hora", "Cidadão", "Observação"]
        _aplicar_linha_cabecalho(ws, 8, cab)

        for i, d in enumerate(lista, start=9):
            _aplicar_linha_dado(ws, i, [
                d["id"],
                _fmt_data(d["data_atendimento"]),
                _fmt_hora(d["hora_atendimento"]),
                d["pessoa_nome"] or "—",
                d["observacoes"] or "—",
            ])

        for col_idx, larg in enumerate([6, 12, 8, 30, 40], start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = larg
        ws.freeze_panes = "A9"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ===========================================================================
# PDF – Relatório Executivo
# ===========================================================================

def gerar_pdf_executivo(filtros, total_atend, total_atend_ant, variacao,
                        por_tipo, por_tipo_ant, por_atendente,
                        solic_status, solic_tipo):
    """Gera o PDF do Relatório Executivo."""
    from reportlab.lib.enums import TA_CENTER
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    COR_PRIMARIA = colors.HexColor('#0f4c5c')
    COR_CINZA    = colors.HexColor('#f4f7f7')
    COR_TEXTO    = colors.HexColor('#0f2a30')

    s_secao  = ParagraphStyle('exec_secao', fontSize=12, textColor=COR_PRIMARIA,
                               spaceBefore=16, spaceAfter=6, fontName='Helvetica-Bold')
    s_normal = ParagraphStyle('exec_normal', fontSize=9, textColor=COR_TEXTO, spaceAfter=4)
    s_rodape = ParagraphStyle('exec_rodape', fontSize=7, textColor=colors.HexColor('#9ca3af'),
                               alignment=TA_CENTER, spaceBefore=6)

    story = []
    styles = getSampleStyleSheet()

    periodo = (f"{filtros['data_inicio'].strftime('%d/%m/%Y')} a "
               f"{filtros['data_fim'].strftime('%d/%m/%Y')}")

    # Cabeçalho com logo
    _cabecalho_pdf(
        story,
        'Relatório Executivo',
        f'Período: {periodo}',
        styles,
    )

    # 1. Resumo geral
    story.append(Paragraph('1. Resumo Geral', s_secao))
    var_texto = f'{variacao:+.1f}%' if variacao is not None else '—'
    dados_resumo = [
        ['Indicador', 'Período Atual', 'Período Anterior', 'Variação'],
        ['Total de Atendimentos', str(total_atend), str(total_atend_ant), var_texto],
    ]
    t = Table(dados_resumo, colWidths=[7*cm, 3.5*cm, 3.5*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COR_CINZA]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dbe7e9')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)

    # 2. Atendimentos por tipo
    story.append(Paragraph('2. Atendimentos por Tipo', s_secao))
    if por_tipo:
        total_tipos = sum(r['total'] for r in por_tipo)
        dados_tipo = [['Tipo de Atendimento', 'Total', '% do Período', 'Período Anterior']]
        for r in por_tipo:
            pct = f"{r['total']/total_tipos*100:.1f}%" if total_tipos > 0 else '—'
            ant = str(por_tipo_ant.get(r['tipo'], 0))
            dados_tipo.append([r['tipo'], str(r['total']), pct, ant])
        t2 = Table(dados_tipo, colWidths=[8*cm, 2.5*cm, 3*cm, 3.5*cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COR_CINZA]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dbe7e9')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t2)
    else:
        story.append(Paragraph('Nenhum atendimento no período.', s_normal))

    # 3. Atendimentos por atendente
    story.append(Paragraph('3. Atendimentos por Atendente', s_secao))
    if por_atendente:
        total_geral = sum(r['total'] for r in por_atendente)
        dados_atend = [['Atendente', 'Total', '% do Total']]
        for r in por_atendente:
            pct = f"{r['total']/total_geral*100:.1f}%" if total_geral > 0 else '—'
            dados_atend.append([r['usuario_nome'], str(r['total']), pct])
        dados_atend.append(['TOTAL GERAL', str(total_geral), '100%'])
        t3 = Table(dados_atend, colWidths=[9*cm, 3*cm, 5*cm])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), COR_PRIMARIA),
            ('TEXTCOLOR',  (0,-1), (-1,-1), colors.white),
            ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, COR_CINZA]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dbe7e9')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t3)

    # 4. Solicitações por status
    story.append(Paragraph('4. Solicitações por Status', s_secao))
    if solic_status:
        total_solic = sum(r['total'] for r in solic_status)
        dados_ss = [['Status', 'Total', '% do Total']]
        for r in solic_status:
            pct = f"{r['total']/total_solic*100:.1f}%" if total_solic > 0 else '—'
            dados_ss.append([r['status'], str(r['total']), pct])
        t4 = Table(dados_ss, colWidths=[9*cm, 3*cm, 5*cm])
        t4.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COR_CINZA]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dbe7e9')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t4)

    # 5. Solicitações por tipo
    story.append(Paragraph('5. Solicitações por Tipo', s_secao))
    if solic_tipo:
        total_st = sum(r['total'] for r in solic_tipo)
        dados_st = [['Tipo de Solicitação', 'Total', '% do Total']]
        for r in solic_tipo:
            pct = f"{r['total']/total_st*100:.1f}%" if total_st > 0 else '—'
            dados_st.append([r['tipo'], str(r['total']), pct])
        t5 = Table(dados_st, colWidths=[9*cm, 3*cm, 5*cm])
        t5.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COR_CINZA]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dbe7e9')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t5)

    # Rodapé
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=COR_PRIMARIA))
    story.append(Paragraph(
        f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")} — {marca.ORG_COMPLETO_UP}',
        s_rodape
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ===========================================================================
# Excel – Relatório Executivo
# ===========================================================================

def gerar_excel_executivo(filtros, total_atend, total_atend_ant, variacao,
                          por_tipo, por_tipo_ant, por_atendente,
                          solic_status, solic_tipo) -> bytes:
    """Gera o Excel do Relatório Executivo com 4 abas."""
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    periodo = (f"Período: {_fmt_data(filtros['data_inicio'])} "
               f"a {_fmt_data(filtros['data_fim'])}")
    var_texto = f'{variacao:+.1f}%' if variacao is not None else '—'

    # ── Aba 1: Resumo Geral ──────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Resumo Geral"
    ws1.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws1,
                            f"{marca.ORG_COMPLETO} — Relatório Executivo",
                            periodo, num_cols=4, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws1, 8, ['Indicador', 'Período Atual', 'Período Anterior', 'Variação'])
    _aplicar_linha_dado(ws1, 9, ['Total de Atendimentos', total_atend, total_atend_ant, var_texto])
    for col_idx, larg in enumerate([30, 18, 18, 12], start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg

    # ── Aba 2: Atendimentos por Tipo ─────────────────────────────────────
    ws2 = wb.create_sheet("Por Tipo de Atendimento")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2,
                            f"{marca.ORG_COMPLETO} — Atendimentos por Tipo",
                            periodo, num_cols=4, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ['Tipo de Atendimento', 'Total', '% do Período', 'Período Anterior'])
    total_tipos = sum(r['total'] for r in por_tipo) if por_tipo else 0
    for i, r in enumerate(por_tipo, start=9):
        pct = f"{r['total']/total_tipos*100:.1f}%" if total_tipos > 0 else '—'
        ant = por_tipo_ant.get(r['tipo'], 0)
        _aplicar_linha_dado(ws2, i, [r['tipo'], r['total'], pct, ant])
    total_row = len(por_tipo) + 9
    ant_total = sum(por_tipo_ant.values()) if por_tipo_ant else 0
    _aplicar_linha_total(ws2, total_row, ['TOTAL', total_tipos, '100%', ant_total])
    for col_idx, larg in enumerate([36, 10, 14, 16], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg
    ws2.freeze_panes = "A9"

    # ── Aba 3: Atendimentos por Atendente ────────────────────────────────
    ws3 = wb.create_sheet("Por Atendente")
    ws3.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws3,
                            f"{marca.ORG_COMPLETO} — Atendimentos por Atendente",
                            periodo, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws3, 8, ['Atendente', 'Total', '% do Total'])
    total_geral = sum(r['total'] for r in por_atendente) if por_atendente else 0
    for i, r in enumerate(por_atendente, start=9):
        pct = f"{r['total']/total_geral*100:.1f}%" if total_geral > 0 else '—'
        _aplicar_linha_dado(ws3, i, [r['usuario_nome'], r['total'], pct])
    total_row3 = len(por_atendente) + 9
    _aplicar_linha_total(ws3, total_row3, ['TOTAL GERAL', total_geral, '100%'])
    for col_idx, larg in enumerate([30, 10, 14], start=1):
        ws3.column_dimensions[get_column_letter(col_idx)].width = larg
    ws3.freeze_panes = "A9"

    # ── Aba 4: Solicitações ──────────────────────────────────────────────
    ws4 = wb.create_sheet("Solicitações")
    ws4.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws4,
                            f"{marca.ORG_COMPLETO} — Solicitações",
                            periodo, num_cols=3, logo_path=logo_path)

    ws4.cell(row=8, column=1, value="POR STATUS").font = Font(bold=True, size=10, color="0f4c5c")
    _aplicar_linha_cabecalho(ws4, 9, ['Status', 'Total', '% do Total'])
    total_solic = sum(r['total'] for r in solic_status) if solic_status else 0
    linha_atual = 10
    for r in solic_status:
        pct = f"{r['total']/total_solic*100:.1f}%" if total_solic > 0 else '—'
        _aplicar_linha_dado(ws4, linha_atual, [r['status'], r['total'], pct])
        linha_atual += 1

    linha_atual += 1
    ws4.cell(row=linha_atual, column=1, value="POR TIPO DE SOLICITAÇÃO").font = Font(bold=True, size=10, color="0f4c5c")
    linha_atual += 1
    _aplicar_linha_cabecalho(ws4, linha_atual, ['Tipo de Solicitação', 'Total', '% do Total'])
    linha_atual += 1
    total_st = sum(r['total'] for r in solic_tipo) if solic_tipo else 0
    for r in solic_tipo:
        pct = f"{r['total']/total_st*100:.1f}%" if total_st > 0 else '—'
        _aplicar_linha_dado(ws4, linha_atual, [r['tipo'], r['total'], pct])
        linha_atual += 1

    for col_idx, larg in enumerate([36, 10, 14], start=1):
        ws4.column_dimensions[get_column_letter(col_idx)].width = larg

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ===========================================================================
# Análise — Excel (uma função por aba)
# ===========================================================================

def _v(variacao):
    """Formata variação percentual ou '—'."""
    if variacao is None:
        return "—"
    return f"{variacao:+}%"


def gerar_xlsx_analise_executivo(kpis: dict, variacoes: dict, evolucao: list,
                                  top_tipos: list, filtros: dict) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    periodo = f"Período: {_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"

    ws1 = wb.active
    ws1.title = "KPIs"
    ws1.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws1,
                            f"{marca.ORG_NOME} — Análise: Painel Executivo",
                            periodo, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws1, 8, ["Indicador", "Valor", "Variação vs Anterior"])
    for i, row in enumerate([
        ("Empreendedores Únicos",   kpis["unicos"],      _v(variacoes.get("unicos"))),
        ("Novos MEIs Formalizados", kpis["novos_meis"],  _v(variacoes.get("novos_meis"))),
        ("Total de Atendimentos",   kpis["total_atend"], _v(variacoes.get("total_atend"))),
        ("Taxa de Retorno",         f"{kpis['taxa_retorno']}%", "—"),
        ("Cobertura sobre MEIs",    f"{kpis['cobertura']}%" if kpis['cobertura'] is not None else "—", "—"),
        ("Progresso da Meta Anual", f"{kpis['progresso_meta']}%" if kpis['progresso_meta'] is not None else "—", "—"),
    ], start=9):
        _aplicar_linha_dado(ws1, i, list(row))
    for col_idx, larg in enumerate([30, 16, 22], start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg

    ws2 = wb.create_sheet("Evolução Mensal")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2, f"{marca.ORG_NOME} — Evolução Mensal",
                            periodo, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ["Mês", "Únicos", "Total Atendimentos"])
    for i, r in enumerate(evolucao, start=9):
        _aplicar_linha_dado(ws2, i, [r["label"], r["unicos"], r["total"]])
    for col_idx, larg in enumerate([12, 10, 18], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg
    ws2.freeze_panes = "A9"

    ws3 = wb.create_sheet("Top Serviços")
    ws3.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws3, f"{marca.ORG_NOME} — Top Serviços Demandados",
                            periodo, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws3, 8, ["Tipo de Atendimento", "Total"])
    for i, r in enumerate(top_tipos, start=9):
        _aplicar_linha_dado(ws3, i, [r["tipo"], r["total"]])
    for col_idx, larg in enumerate([40, 10], start=1):
        ws3.column_dimensions[get_column_letter(col_idx)].width = larg
    ws3.freeze_panes = "A9"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gerar_xlsx_analise_jornada(funil: list, top10: list,
                                uma_visita: dict, tempo_medio) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    sub = "Dados acumulados de todo o histórico disponível"

    ws1 = wb.active
    ws1.title = "Funil da Jornada"
    ws1.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws1, f"{marca.ORG_NOME} — Análise: Jornada",
                            sub, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws1, 8, ["Etapa", "Quantidade", "%"])
    for i, r in enumerate(funil, start=9):
        _aplicar_linha_dado(ws1, i, [r["label"], r["valor"], f"{r['pct']}%"])
    linha_kpi = len(funil) + 11
    ws1.cell(row=linha_kpi, column=1, value="INDICADORES ADICIONAIS").font = Font(bold=True, size=10, color="0f4c5c")
    _aplicar_linha_cabecalho(ws1, linha_kpi + 1, ["Indicador", "Valor"])
    _aplicar_linha_dado(ws1, linha_kpi + 2, ["Só Vieram Uma Vez", f"{uma_visita['total']} ({uma_visita['pct']}%)"])
    _aplicar_linha_dado(ws1, linha_kpi + 3, ["Tempo Médio até Retorno (dias)", tempo_medio if tempo_medio else "—"])
    for col_idx, larg in enumerate([30, 16, 10], start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg

    ws2 = wb.create_sheet("Top 10 Mais Atendidos")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2, f"{marca.ORG_NOME} — Top 10 Mais Atendidos",
                            sub, num_cols=4, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ["Posição", "Empreendedor", "Total Atendimentos", "Último Atendimento"])
    for i, r in enumerate(top10, start=9):
        _aplicar_linha_dado(ws2, i, [i - 8, r["nome"], r["total"], r["ultimo"]])
    for col_idx, larg in enumerate([10, 36, 18, 18], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg
    ws2.freeze_panes = "A9"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gerar_xlsx_analise_demanda(heatmap: dict, dias_semana: list,
                                hora_pico: list, bairros: dict,
                                filtros: dict) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    periodo = f"Período: {_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"

    ws1 = wb.active
    ws1.title = "Heatmap Meses × Tipos"
    ws1.sheet_view.showGridLines = False
    n_tipos = max(len(heatmap["tipos"]), 1)
    _estilo_excel_cabecalho(ws1, f"{marca.ORG_NOME} — Heatmap de Demanda",
                            periodo, num_cols=n_tipos + 1, logo_path=logo_path)
    if heatmap["tipos"]:
        _aplicar_linha_cabecalho(ws1, 8, ["Mês"] + heatmap["tipos"])
        for i, (mes, linha) in enumerate(zip(heatmap["meses"], heatmap["matriz"]), start=9):
            _aplicar_linha_dado(ws1, i, [mes] + linha)
    ws1.column_dimensions["A"].width = 8
    for col_idx in range(2, n_tipos + 2):
        ws1.column_dimensions[get_column_letter(col_idx)].width = 16
    ws1.freeze_panes = "B9"

    ws2 = wb.create_sheet("Dias da Semana")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2, f"{marca.ORG_NOME} — Atendimentos por Dia",
                            periodo, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ["Dia", "Total"])
    for i, r in enumerate(dias_semana, start=9):
        _aplicar_linha_dado(ws2, i, [r["dia"], r["total"]])
    for col_idx, larg in enumerate([12, 10], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg

    ws3 = wb.create_sheet("Hora de Pico")
    ws3.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws3, f"{marca.ORG_NOME} — Atendimentos por Hora",
                            periodo, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws3, 8, ["Hora", "Total"])
    for i, r in enumerate(hora_pico, start=9):
        _aplicar_linha_dado(ws3, i, [r["hora"], r["total"]])
    for col_idx, larg in enumerate([8, 10], start=1):
        ws3.column_dimensions[get_column_letter(col_idx)].width = larg

    ws4 = wb.create_sheet("Bairros")
    ws4.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws4, f"{marca.ORG_NOME} — Atendimentos por Bairro",
                            periodo, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws4, 8, ["Bairro", "Empreendedores Únicos"])
    for i, r in enumerate(bairros["bairros"], start=9):
        _aplicar_linha_dado(ws4, i, [r["bairro"], r["unicos"]])
    _aplicar_linha_dado(ws4, len(bairros["bairros"]) + 10, ["Sem bairro preenchido", bairros["sem_bairro"]])
    for col_idx, larg in enumerate([30, 22], start=1):
        ws4.column_dimensions[get_column_letter(col_idx)].width = larg
    ws4.freeze_panes = "A9"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gerar_xlsx_analise_perfil(dist_tipo: list, top_cnaes: list,
                               situacao: dict, dist_porte: list,
                               dist_sexo: dict) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    sub = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    ws1 = wb.active
    ws1.title = "Distribuição por Tipo"
    ws1.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws1, f"{marca.ORG_NOME} — Perfil dos Empreendedores",
                            sub, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws1, 8, ["Tipo", "Total", "%"])
    for i, r in enumerate(dist_tipo, start=9):
        _aplicar_linha_dado(ws1, i, [r["tipo"], r["total"], f"{r['pct']}%"])
    for col_idx, larg in enumerate([22, 10, 8], start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg

    ws2 = wb.create_sheet("Situação Cadastral")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2,
                            f"{marca.ORG_NOME} — Situação Cadastral (Receita Federal)",
                            sub, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ["Situação", "Total"])
    for i, r in enumerate(situacao["dados"], start=9):
        _aplicar_linha_dado(ws2, i, [r["situacao"], r["total"]])
    _aplicar_linha_dado(ws2, len(situacao["dados"]) + 10, ["Sem informação", situacao["sem_info"]])
    for col_idx, larg in enumerate([30, 10], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg

    ws3 = wb.create_sheet("Top CNAEs")
    ws3.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws3, f"{marca.ORG_NOME} — Top CNAEs Mais Frequentes",
                            sub, num_cols=2, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws3, 8, ["CNAE", "Total"])
    for i, r in enumerate(top_cnaes, start=9):
        _aplicar_linha_dado(ws3, i, [r["cnae"], r["total"]])
    for col_idx, larg in enumerate([52, 10], start=1):
        ws3.column_dimensions[get_column_letter(col_idx)].width = larg
    ws3.freeze_panes = "A9"

    ws4 = wb.create_sheet("Porte e Sexo")
    ws4.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws4, f"{marca.ORG_NOME} — Porte e Sexo",
                            sub, num_cols=3, logo_path=logo_path)
    ws4.cell(row=8, column=1, value="POR PORTE").font = Font(bold=True, size=10, color="0f4c5c")
    _aplicar_linha_cabecalho(ws4, 9, ["Porte", "Total"])
    linha = 10
    for r in dist_porte:
        _aplicar_linha_dado(ws4, linha, [r["porte"], r["total"]])
        linha += 1
    linha += 1
    ws4.cell(row=linha, column=1, value="POR SEXO").font = Font(bold=True, size=10, color="0f4c5c")
    linha += 1
    _aplicar_linha_cabecalho(ws4, linha, ["Sexo", "Total", "%"])
    linha += 1
    for r in dist_sexo["dados"]:
        _aplicar_linha_dado(ws4, linha, [r["sexo"], r["total"], f"{r['pct']}%"])
        linha += 1
    _aplicar_linha_dado(ws4, linha, ["Sem informação", dist_sexo["sem_info"], "—"])
    for col_idx, larg in enumerate([22, 10, 8], start=1):
        ws4.column_dimensions[get_column_letter(col_idx)].width = larg

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gerar_xlsx_analise_potencial(campeoes: list, inativos: list,
                                  nunca_solic: list, em_risco: list) -> bytes:
    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    sub = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    ws1 = wb.active
    ws1.title = "Campeões"
    ws1.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws1, f"{marca.ORG_NOME} — Campeões (Alta Recorrência)",
                            "5+ atendimentos nos últimos 6 meses",
                            num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws1, 8, ["Empreendedor", "Total Atendimentos", "Último Atendimento"])
    for i, r in enumerate(campeoes, start=9):
        _aplicar_linha_dado(ws1, i, [r["nome"], r["total"], r["ultimo"]])
    for col_idx, larg in enumerate([36, 18, 18], start=1):
        ws1.column_dimensions[get_column_letter(col_idx)].width = larg
    ws1.freeze_panes = "A9"

    ws2 = wb.create_sheet("Em Risco")
    ws2.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws2, f"{marca.ORG_NOME} — Em Risco (Solicitação Parada)",
                            "Solicitação pendente ou em análise há mais de 30 dias",
                            num_cols=5, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws2, 8, ["Empreendedor", "Tipo Solicitação", "Data Solic.", "Dias Parada", "Último Atend."])
    for i, r in enumerate(em_risco, start=9):
        _aplicar_linha_dado(ws2, i, [r["nome"], r["solic_tipo"], r["solic_data"],
                                      r["dias_parada"], r["ultimo_atend"]])
    for col_idx, larg in enumerate([36, 24, 12, 12, 14], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = larg
    ws2.freeze_panes = "A9"

    ws3 = wb.create_sheet("Inativos")
    ws3.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws3, f"{marca.ORG_NOME} — Inativos (Sem Atendimento há +12 Meses)",
                            sub, num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws3, 8, ["Empreendedor", "Dias Sem Visita", "Último Atendimento"])
    for i, r in enumerate(inativos, start=9):
        _aplicar_linha_dado(ws3, i, [r["nome"], r["dias"], r["ultimo"]])
    for col_idx, larg in enumerate([36, 16, 18], start=1):
        ws3.column_dimensions[get_column_letter(col_idx)].width = larg
    ws3.freeze_panes = "A9"

    ws4 = wb.create_sheet("Nunca Solicitaram")
    ws4.sheet_view.showGridLines = False
    _estilo_excel_cabecalho(ws4, f"{marca.ORG_NOME} — Nunca Solicitaram",
                            "Empreendedores atendidos sem nenhuma solicitação formal",
                            num_cols=3, logo_path=logo_path)
    _aplicar_linha_cabecalho(ws4, 8, ["Empreendedor", "Total Atendimentos", "Último Atendimento"])
    for i, r in enumerate(nunca_solic, start=9):
        _aplicar_linha_dado(ws4, i, [r["nome"], r["total_atend"], r["ultimo"]])
    for col_idx, larg in enumerate([36, 18, 18], start=1):
        ws4.column_dimensions[get_column_letter(col_idx)].width = larg
    ws4.freeze_panes = "A9"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ===========================================================================
# Análise — PDF (uma função por aba)
# ===========================================================================

def _pdf_secao(elements, titulo, cabecalhos, linhas_dados, col_widths, styles):
    """Título de seção + tabela ReportLab padronizada."""
    COR_P = colors.HexColor('#0f4c5c')
    COR_C = colors.HexColor('#f4f7f7')
    elements.append(
        Paragraph(titulo,
                  ParagraphStyle('sec', parent=styles['Normal'], fontSize=10,
                                 textColor=COR_P, fontName='Helvetica-Bold',
                                 spaceBefore=12, spaceAfter=6))
    )
    if not linhas_dados:
        elements.append(
            Paragraph("Sem dados disponíveis.",
                      ParagraphStyle('vazio', parent=styles['Normal'],
                                     fontSize=9, textColor=colors.HexColor('#94A3B8')))
        )
        return
    t = Table([cabecalhos] + linhas_dados, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  COR_P),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  8),
        ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  5),
        ('TOPPADDING',    (0, 0), (-1, 0),  5),
        ('FONTSIZE',      (0, 1), (-1, -1), 7.5),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, COR_C]),
        ('GRID',          (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
    ]))
    elements.append(t)


def _pdf_rodape_linha(elements, styles, texto):
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0f4c5c')))
    elements.append(
        Paragraph(texto,
                  ParagraphStyle('rod', parent=styles['Normal'], fontSize=7,
                                 textColor=colors.HexColor('#9ca3af'),
                                 alignment=1, spaceBefore=4))
    )


def gerar_pdf_analise_executivo(kpis: dict, variacoes: dict, evolucao: list,
                                 top_tipos: list, filtros: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    periodo = f"{_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"
    _cabecalho_pdf(elements, "Análise — Painel Executivo", f"Período: {periodo}", styles)

    _pdf_secao(elements, "1. KPIs do Período",
               ["Indicador", "Valor", "Variação"],
               [
                   ["Empreendedores Únicos",   str(kpis["unicos"]),      _v(variacoes.get("unicos"))],
                   ["Novos MEIs Formalizados", str(kpis["novos_meis"]),  _v(variacoes.get("novos_meis"))],
                   ["Total de Atendimentos",   str(kpis["total_atend"]), _v(variacoes.get("total_atend"))],
                   ["Taxa de Retorno",         f"{kpis['taxa_retorno']}%", "—"],
                   ["Cobertura sobre MEIs",    f"{kpis['cobertura']}%" if kpis['cobertura'] is not None else "—", "—"],
                   ["Progresso da Meta Anual", f"{kpis['progresso_meta']}%" if kpis['progresso_meta'] is not None else "—", "—"],
               ],
               [9*cm, 3*cm, 3*cm], styles)

    _pdf_secao(elements, "2. Evolução Mensal",
               ["Mês", "Únicos", "Total Atendimentos"],
               [[r["label"], str(r["unicos"]), str(r["total"])] for r in evolucao],
               [5*cm, 3.5*cm, 6.5*cm], styles)

    _pdf_secao(elements, "3. Top Serviços Mais Demandados",
               ["Tipo de Atendimento", "Total"],
               [[r["tipo"], str(r["total"])] for r in top_tipos],
               [11*cm, 4*cm], styles)

    _pdf_rodape_linha(elements, styles,
                      f"Período: {periodo} | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                      f" — {marca.ORG_COMPLETO_UP}")
    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buf.getvalue()


def gerar_pdf_analise_jornada(funil: list, top10: list,
                               uma_visita: dict, tempo_medio) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    _cabecalho_pdf(elements, "Análise — Jornada do Empreendedor",
                   "Dados acumulados de todo o histórico disponível", styles)

    _pdf_secao(elements, "1. KPIs de Jornada",
               ["Indicador", "Valor"],
               [
                   ["Só Vieram Uma Vez", f"{uma_visita['total']} ({uma_visita['pct']}%)"],
                   ["Tempo Médio até Retorno (dias)", str(tempo_medio) if tempo_medio else "—"],
               ],
               [10*cm, 5*cm], styles)

    _pdf_secao(elements, "2. Funil da Jornada",
               ["Etapa", "Quantidade", "%"],
               [[r["label"], str(r["valor"]), f"{r['pct']}%"] for r in funil],
               [7*cm, 4*cm, 4*cm], styles)

    _pdf_secao(elements, "3. Top 10 Empreendedores Mais Atendidos",
               ["Pos.", "Empreendedor", "Total", "Último"],
               [[str(i + 1), r["nome"], str(r["total"]), r["ultimo"]] for i, r in enumerate(top10)],
               [1.5*cm, 8*cm, 2.5*cm, 3*cm], styles)

    _pdf_rodape_linha(elements, styles,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                      f" — {marca.ORG_COMPLETO_UP}")
    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buf.getvalue()


def gerar_pdf_analise_demanda(heatmap: dict, dias_semana: list,
                               hora_pico: list, bairros: dict,
                               filtros: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    periodo = f"{_fmt_data(filtros.get('data_inicio'))} a {_fmt_data(filtros.get('data_fim'))}"
    _cabecalho_pdf(elements, "Análise — Demanda", f"Período: {periodo}", styles)

    if heatmap["tipos"]:
        n = len(heatmap["tipos"])
        tipo_w = min(3.5 * cm, 22 * cm / (n + 1))
        _pdf_secao(elements, "1. Heatmap — Meses × Tipos de Atendimento",
                   ["Mês"] + heatmap["tipos"],
                   [[mes] + [str(v) if v > 0 else "—" for v in linha]
                    for mes, linha in zip(heatmap["meses"], heatmap["matriz"])],
                   [2 * cm] + [tipo_w] * n, styles)

    _pdf_secao(elements, "2. Atendimentos por Dia da Semana",
               ["Dia", "Total"],
               [[r["dia"], str(r["total"])] for r in dias_semana],
               [7*cm, 3*cm], styles)

    _pdf_secao(elements, "3. Atendimentos por Hora do Dia",
               ["Hora", "Total"],
               [[r["hora"], str(r["total"])] for r in hora_pico],
               [5*cm, 3*cm], styles)

    _pdf_secao(elements, "4. Atendimentos por Bairro (Top 15)",
               ["Bairro", "Empreendedores Únicos"],
               [[r["bairro"], str(r["unicos"])] for r in bairros["bairros"]],
               [14*cm, 6*cm], styles)

    _pdf_rodape_linha(elements, styles,
                      f"Período: {periodo} | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                      f" — {marca.ORG_COMPLETO_UP}")
    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buf.getvalue()


def gerar_pdf_analise_perfil(dist_tipo: list, top_cnaes: list,
                              situacao: dict, dist_porte: list,
                              dist_sexo: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    _cabecalho_pdf(elements, "Análise — Perfil dos Empreendedores",
                   f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles)

    _pdf_secao(elements, "1. Distribuição por Tipo",
               ["Tipo", "Total", "%"],
               [[r["tipo"], str(r["total"]), f"{r['pct']}%"] for r in dist_tipo],
               [8*cm, 3*cm, 4*cm], styles)

    _pdf_secao(elements, "2. Distribuição por Porte",
               ["Porte", "Total"],
               [[r["porte"], str(r["total"])] for r in dist_porte],
               [9*cm, 6*cm], styles)

    sit_linhas = [[r["situacao"], str(r["total"])] for r in situacao["dados"]]
    if situacao["sem_info"]:
        sit_linhas.append(["Sem informação", str(situacao["sem_info"])])
    _pdf_secao(elements, "3. Situação Cadastral (Receita Federal)",
               ["Situação", "Total"], sit_linhas, [10*cm, 5*cm], styles)

    _pdf_secao(elements, "4. Top 10 CNAEs Mais Frequentes",
               ["CNAE", "Total"],
               [[r["cnae"], str(r["total"])] for r in top_cnaes],
               [11*cm, 4*cm], styles)

    sexo_linhas = [[r["sexo"], str(r["total"]), f"{r['pct']}%"] for r in dist_sexo["dados"]]
    if dist_sexo["sem_info"]:
        sexo_linhas.append(["Sem informação", str(dist_sexo["sem_info"]), "—"])
    _pdf_secao(elements, "5. Distribuição por Sexo",
               ["Sexo", "Total", "%"], sexo_linhas, [8*cm, 3*cm, 4*cm], styles)

    _pdf_rodape_linha(elements, styles,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                      f" — {marca.ORG_COMPLETO_UP}")
    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buf.getvalue()


def gerar_pdf_analise_potencial(campeoes: list, inativos: list,
                                 nunca_solic: list, em_risco: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    _cabecalho_pdf(elements, "Análise — Potencial e Alertas",
                   f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles)

    _pdf_secao(elements, "1. Campeões — Alta Recorrência (5+ atend. em 6 meses)",
               ["Empreendedor", "Total", "Último Atend."],
               [[r["nome"], str(r["total"]), r["ultimo"]] for r in campeoes],
               [9*cm, 2.5*cm, 3.5*cm], styles)

    _pdf_secao(elements, "2. Em Risco — Solicitação Parada (+30 dias)",
               ["Empreendedor", "Tipo", "Dias Parada", "Último Atend."],
               [[r["nome"], r["solic_tipo"], str(r["dias_parada"]), r["ultimo_atend"]] for r in em_risco],
               [6*cm, 4*cm, 2.5*cm, 2.5*cm], styles)

    _pdf_secao(elements, "3. Inativos — Sem Atendimento há +12 Meses",
               ["Empreendedor", "Dias Sem Visita", "Último Atend."],
               [[r["nome"], str(r["dias"]), r["ultimo"]] for r in inativos],
               [9*cm, 3*cm, 3*cm], styles)

    _pdf_secao(elements, "4. Nunca Solicitaram Nada",
               ["Empreendedor", "Total Atend.", "Último Atend."],
               [[r["nome"], str(r["total_atend"]), r["ultimo"]] for r in nunca_solic],
               [9*cm, 2.5*cm, 3.5*cm], styles)

    _pdf_rodape_linha(elements, styles,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                      f" — {marca.ORG_COMPLETO_UP}")
    doc.build(elements, onFirstPage=_rodape_pdf, onLaterPages=_rodape_pdf)
    return buf.getvalue()


# ===========================================================================
# PDF — Log de Auditoria
# ===========================================================================

def gerar_pdf_log(logs: list, filtros: dict) -> bytes:
    """Exporta o log de auditoria (LogAcao) para PDF — orientação paisagem."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, Image)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from datetime import datetime as _dt

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm,  bottomMargin=1.5 * cm,
        title=f'Log de Auditoria — {marca.APP_NOME}',
    )

    styles     = getSampleStyleSheet()
    COR_PRIM   = colors.HexColor('#0f4c5c')
    COR_LISTRA = colors.HexColor('#f8fbfb')

    titulo_st = ParagraphStyle(
        'titulo', parent=styles['Heading1'],
        textColor=COR_PRIM, fontSize=14, spaceAfter=4,
    )
    sub_st = ParagraphStyle(
        'sub', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#6b7280'), spaceAfter=6,
    )
    aviso_st = ParagraphStyle(
        'aviso', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#92400e'),
        backColor=colors.HexColor('#fef3c7'), spaceAfter=4,
    )
    rodape_st = ParagraphStyle(
        'rodape', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#9ca3af'),
    )

    elementos = []

    # Logo
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=3.5 * cm, height=1.75 * cm)
        logo.hAlign = 'LEFT'
        elementos.append(logo)
        elementos.append(Spacer(1, 0.2 * cm))

    elementos.append(Paragraph('Log de Auditoria', titulo_st))

    partes = []
    if filtros.get('data_de'):
        partes.append(f"De: {filtros['data_de']}")
    if filtros.get('data_ate'):
        partes.append(f"Até: {filtros['data_ate']}")
    if filtros.get('acao'):
        partes.append(f"Ação: {filtros['acao']}")
    sub_txt = (' · '.join(partes) if partes else 'Todos os registros')
    sub_txt += f' · {len(logs)} registro(s)'
    elementos.append(Paragraph(sub_txt, sub_st))

    if len(logs) >= 5000:
        elementos.append(Paragraph(
            '⚠ Exibindo os primeiros 5.000 registros.', aviso_st,
        ))

    elementos.append(Spacer(1, 0.3 * cm))

    cabecalho = [['Data/Hora', 'Usuário', 'Ação', 'Entidade', 'Descrição']]
    linhas = []
    for log in logs:
        linhas.append([
            log.created_at.strftime('%d/%m/%Y %H:%M') if log.created_at else '—',
            log.usuario.nome if log.usuario else '—',
            log.acao or '—',
            f"{log.entidade} #{log.entidade_id}" if log.entidade else '—',
            (log.descricao or '—')[:80],
        ])

    tabela = Table(
        cabecalho + linhas,
        colWidths=[3.5 * cm, 3.5 * cm, 3 * cm, 3.5 * cm, None],
        repeatRows=1,
    )
    tabela.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  COR_PRIM),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  8),
        ('FONTSIZE',      (0, 1), (-1, -1), 7.5),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, COR_LISTRA]),
        ('GRID',          (0, 0), (-1, -1), 0.25, colors.HexColor('#dbe7e9')),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(tabela)

    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(Paragraph(
        f"Gerado em {_dt.now().strftime('%d/%m/%Y às %H:%M')}"
        f" — {marca.APP_NOME} / {marca.ORG_COMPLETO}",
        rodape_st,
    ))

    doc.build(elementos)
    return buf.getvalue()


# ===========================================================================
# Excel — Log de Auditoria
# ===========================================================================

def gerar_xlsx_log(logs: list, filtros: dict) -> bytes:
    """Exporta o log de auditoria (LogAcao) para Excel com aba de resumo."""
    from collections import Counter

    wb = openpyxl.Workbook()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    # ── Aba principal ──────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Log de Auditoria"
    ws.sheet_view.showGridLines = False

    partes = [f"Total: {len(logs)} registro(s)"]
    if filtros.get('data_de') or filtros.get('data_ate'):
        partes.append(
            f"Período: {filtros.get('data_de') or 'início'}"
            f" a {filtros.get('data_ate') or 'hoje'}"
        )
    if filtros.get('usuario_nome'):
        partes.append(f"Usuário: {filtros['usuario_nome']}")
    if filtros.get('acao'):
        partes.append(f"Tipo: {filtros['acao']}")
    subtitulo = "   |   ".join(partes)

    # ── Cabeçalho dedicado: logo centralizada + título/subtítulo/gerado_em ──

    # Logo centralizada nas linhas 1-3 via AbsoluteAnchor
    _COL_WIDTHS = [6, 18, 16, 12, 12, 6, 55]  # larguras das colunas A-G
    if os.path.exists(logo_path):
        try:
            from openpyxl.drawing.image import Image as XlImage
            from PIL import Image as PILImage
            with PILImage.open(logo_path) as pil_img:
                orig_w, orig_h = pil_img.size
            img_w = 320
            img_h = int(orig_h * img_w / orig_w)
        except Exception:
            img_w, img_h = 320, 160
        try:
            from openpyxl.drawing.image import Image as XlImage
            img = XlImage(logo_path)
            total_px = sum(w * 7 for w in _COL_WIDTHS)
            x_off = max(0, (total_px - img_w) // 2)
            p2d  = XDRPoint2D(pixels_to_EMU(x_off), pixels_to_EMU(8))
            size = XDRPositiveSize2D(pixels_to_EMU(img_w), pixels_to_EMU(img_h))
            img.anchor = AbsoluteAnchor(pos=p2d, ext=size)
            ws.add_image(img)
        except Exception:
            pass
    pts_por_px = 0.75
    total_pts  = img_h / pts_por_px
    ws.row_dimensions[1].height = round(total_pts * 0.55)
    ws.row_dimensions[2].height = round(total_pts * 0.35)
    ws.row_dimensions[3].height = round(total_pts * 0.10)

    # Linha 4 — título
    ws.merge_cells('A4:G4')
    c4 = ws['A4']
    c4.value     = f'{marca.ORG_COMPLETO} — Log de Auditoria'
    c4.font      = Font(bold=True, size=13, color='0F2A30')
    c4.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[4].height = 22

    # Linha 5 — subtítulo
    ws.merge_cells('A5:G5')
    c5 = ws['A5']
    c5.value     = subtitulo
    c5.font      = Font(size=10, color='0f4c5c')
    c5.alignment = Alignment(horizontal='center')
    ws.row_dimensions[5].height = 16

    # Linha 6 — gerado em
    ws.merge_cells('A6:G6')
    c6 = ws['A6']
    c6.value     = (f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    f" — {marca.ORG_COMPLETO}")
    c6.font      = Font(size=9, italic=True, color='6b7280')
    c6.alignment = Alignment(horizontal='center')
    ws.row_dimensions[6].height = 14

    # Linha 7 — separador
    ws.row_dimensions[7].height = 8

    # Linha 8 — cabeçalho na cor primária
    colunas = ["#", "Data/Hora", "Usuário", "Ação", "Entidade", "ID", "Descrição"]
    _aplicar_linha_cabecalho(ws, 8, colunas)

    # Linhas 9+ — dados
    for i, log in enumerate(logs, start=9):
        usuario_nome = log.usuario.nome if log.usuario else "Sistema"
        dt_str = log.created_at.strftime("%d/%m/%Y %H:%M") if log.created_at else "—"
        _aplicar_linha_dado(ws, i, [
            log.id,
            dt_str,
            usuario_nome,
            log.acao or "—",
            log.entidade or "—",
            log.entidade_id if log.entidade_id is not None else "—",
            log.descricao or "—",
        ])
        ws.cell(row=i, column=7).alignment = Alignment(wrap_text=True, vertical='top')

    # Larguras de coluna: auto-ajuste (pula cabeçalho) + mínimos fixos
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        if col_letter == 'G':
            continue
        max_len = 0
        for cell in ws[col_letter]:
            if cell.row <= 7 or isinstance(cell, MergedCell):
                continue
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 4, 60)
    _mins = {'A': 6, 'B': 18, 'C': 16, 'D': 12, 'E': 12, 'F': 6, 'G': 55}
    for letra, minimo in _mins.items():
        ws.column_dimensions[letra].width = max(
            ws.column_dimensions[letra].width or 0, minimo
        )

    ws.freeze_panes = "A9"
    ws.auto_filter.ref = f"A8:{get_column_letter(len(colunas))}8"

    # ── Aba Resumo ─────────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Resumo")
    ws2.sheet_view.showGridLines = False

    _estilo_excel_cabecalho(
        ws2,
        "Log de Auditoria — Resumo",
        subtitulo,
        num_cols=2,
        logo_path=logo_path,
    )

    contagem_acao    = Counter(log.acao or "—" for log in logs)
    contagem_usuario = Counter(
        (log.usuario.nome if log.usuario else "Sistema") for log in logs
    )

    # Distribuição por tipo de ação
    row = 8
    _aplicar_linha_cabecalho(ws2, row, ["Tipo de Ação", "Total"])
    for r_idx, (acao, total) in enumerate(
        sorted(contagem_acao.items(), key=lambda x: -x[1]), start=row + 1
    ):
        _aplicar_linha_dado(ws2, r_idx, [acao, total])

    total_row = row + len(contagem_acao) + 1
    _aplicar_linha_total(ws2, total_row, ["TOTAL", len(logs)])

    # Distribuição por usuário
    row2 = total_row + 2
    _aplicar_linha_cabecalho(ws2, row2, ["Usuário", "Total"])
    for r_idx, (nome, total) in enumerate(
        sorted(contagem_usuario.items(), key=lambda x: -x[1]), start=row2 + 1
    ):
        _aplicar_linha_dado(ws2, r_idx, [nome, total])

    for col_idx in range(1, ws2.max_column + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for cell in ws2[col_letter]:
            if cell.row <= 4:          # pula cabeçalho (linhas 1-4)
                continue
            if isinstance(cell, MergedCell):
                continue
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws2.column_dimensions[col_letter].width = min(max_len + 4, 60)
    ws2.freeze_panes = "A6"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
