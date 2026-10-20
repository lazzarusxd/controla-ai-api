from io import BytesIO
from decimal import Decimal
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.application.interfaces import IExportSerializer
from app.application.dto import ExportPackageDTO, ExportSectionDTO, SerializedExportDTO


_FONT_SIZE = 6.5
_CELL_PADDING = 3
_MIN_COLUMN_WIDTH = 14 * mm
_MAX_COLUMN_WIDTH = 60 * mm
_EMPTY_CELL = "-"
_DISPLAY_TIMEZONE = ZoneInfo("America/Sao_Paulo")

_HEADER_LABELS: Dict[str, str] = {
    "transaction_id": "ID do lançamento",
    "receipt_id": "ID do comprovante",
    "asset_id": "ID do bem",
    "goal_id": "ID da meta",
    "subscription_id": "ID da recorrência",
    "type": "Tipo",
    "amount": "Valor",
    "category": "Categoria",
    "description": "Descrição",
    "transaction_date": "Data",
    "due_date": "Vencimento",
    "status": "Situação",
    "pending_review": "Em revisão",
    "confidence_score": "Confiança",
    "file_path": "Arquivo",
    "file_type": "Tipo de arquivo",
    "file_size_bytes": "Tamanho (bytes)",
    "processed_at": "Processado em",
    "created_at": "Criado em",
    "updated_at": "Atualizado em"
}


class PdfExportSerializer(IExportSerializer):
    """Relatório legível do dossiê (LGPD art. 18, II e V): resumo humano, não o conjunto íntegro."""

    def __init__(self, max_rows_per_section: int, title: str = "Controla AI") -> None:
        self._title = title
        self._cell_max_chars = 42
        self._max_rows_per_section = max_rows_per_section

    def serialize(self, export_package: ExportPackageDTO) -> SerializedExportDTO:
        buffer = BytesIO()
        styles = getSampleStyleSheet()

        heading = ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], spaceAfter=4)
        footnote = ParagraphStyle(name="Footnote", parent=styles["Normal"], fontSize=7, textColor=colors.grey)

        cell_style = ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=_FONT_SIZE,
            leading=_FONT_SIZE + 1.5,
            wordWrap="CJK"
        )
        header_style = ParagraphStyle(name="HeaderCell", parent=cell_style, fontName="Helvetica-Bold")

        document = SimpleDocTemplate(
            buffer,
            topMargin=14 * mm,
            author=self._title,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            bottomMargin=14 * mm,
            pagesize=landscape(A4),
            title=f"{self._title}: Exportação de dados"
        )

        scope = export_package.scope
        end = self._format_date(scope.end_date) if scope.end_date is not None else "lançamento mais recente"
        start = self._format_date(scope.start_date) if scope.start_date is not None else "início do histórico"

        story: List[Any] = [
            Paragraph(f"{escape(self._title)}: Exportação de dados", styles["Title"]),
            Paragraph(f"Titular: {export_package.user_id}", styles["Normal"]),
            Paragraph(f"Gerado em: {self._format_datetime(export_package.generated_at)}", styles["Normal"]),
            Paragraph(f"Período apurado: {start} a {end}", styles["Normal"]),
            Paragraph(f"Total de registros: {export_package.total_records}", styles["Normal"]),
            Spacer(1, 8 * mm)
        ]

        truncated = False

        for section in export_package.sections:
            visible = section.rows[:self._max_rows_per_section]
            section_truncated = len(section.rows) > len(visible)
            truncated = truncated or section_truncated

            story.append(Paragraph(f"{escape(section.title)} ({section.total})", heading))

            if not visible:
                story.append(Paragraph("Nenhum registro no escopo solicitado.", footnote))
            else:
                story.append(
                    self._to_table(
                        rows=visible,
                        section=section,
                        cell_style=cell_style,
                        header_style=header_style,
                        available_width=document.width
                    )
                )

            if section_truncated:
                story.append(
                    Paragraph(
                        f"Exibidos {len(visible)} de {section.total} registros. O relatório em PDF é "
                        f"resumo legível; para o conjunto íntegro, solicite a exportação em JSON ou CSV.",
                        footnote
                    )
                )

            story.append(Spacer(1, 6 * mm))

        document.build(story)

        return SerializedExportDTO(
            truncated=truncated,
            file_extension="pdf",
            content=buffer.getvalue(),
            media_type="application/pdf"
        )

    def _to_table(
            self,
            rows: List[Any],
            available_width: float,
            section: ExportSectionDTO,
            cell_style: ParagraphStyle,
            header_style: ParagraphStyle
    ) -> Table:
        headers = [self._to_header(column=column) for column in section.columns]
        body = [[self._to_cell(value=row.get(column)) for column in section.columns] for row in rows]

        widths = self._column_widths(headers=headers, body=body, available_width=available_width)

        data: List[List[Paragraph]] = [[Paragraph(escape(text), header_style) for text in headers]]
        data.extend([Paragraph(escape(text), cell_style) for text in line] for line in body)

        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B9C4CF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), _CELL_PADDING),
                    ("RIGHTPADDING", (0, 0), (-1, -1), _CELL_PADDING),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2)
                ]
            )
        )

        return table

    @staticmethod
    def _column_widths(headers: List[str], body: List[List[str]], available_width: float) -> List[float]:
        """
        Larguras proporcionais ao conteúdo, limitadas e encaixadas na largura útil da página.

        Sem colWidths, o ReportLab mede cada coluna pelo texto sem quebra e a tabela vaza da margem.
        """
        natural: List[float] = []

        for index, header in enumerate(headers):
            widest = stringWidth(header, "Helvetica-Bold", _FONT_SIZE)

            for line in body:
                widest = max(widest, stringWidth(line[index], "Helvetica", _FONT_SIZE))

            natural.append(min(max(widest + 2 * _CELL_PADDING + 1, _MIN_COLUMN_WIDTH), _MAX_COLUMN_WIDTH))

        total = sum(natural)

        if total <= available_width:
            return natural

        # Encolhe só o que excede o piso, preservando colunas curtas (status, tipo) legíveis.
        floor_total = _MIN_COLUMN_WIDTH * len(natural)
        if floor_total >= available_width:
            return [available_width / len(natural)] * len(natural)

        ratio = (available_width - floor_total) / (total - floor_total)

        return [_MIN_COLUMN_WIDTH + (width - _MIN_COLUMN_WIDTH) * ratio for width in natural]

    @staticmethod
    def _to_header(column: str) -> str:
        return _HEADER_LABELS.get(column, column.replace("_", " ").strip().capitalize())

    def _to_cell(self, value: object) -> str:
        if value is None:
            return _EMPTY_CELL

        if isinstance(value, bool):
            return "sim" if value else "não"

        if isinstance(value, datetime):
            text = self._format_datetime(value)
        elif isinstance(value, date):
            text = self._format_date(value)
        elif isinstance(value, (Decimal, float)):
            text = f"{value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        else:
            text = self._parse_iso(str(value))

        if len(text) > self._cell_max_chars:
            return f"{text[: self._cell_max_chars - 1]}…"

        return text

    def _parse_iso(self, text: str) -> str:
        """Datas que chegam serializadas como texto ISO 8601 também são exibidas no padrão brasileiro."""
        if len(text) < 10 or text[4:5] != "-" or text[7:8] != "-":
            return text

        parsed: Optional[datetime] = None

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return text

        if len(text) == 10:
            return self._format_date(parsed.date())

        return self._format_datetime(parsed)

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        localized = value.astimezone(_DISPLAY_TIMEZONE) if value.tzinfo is not None else value
        return localized.strftime("%d/%m/%Y %H:%M:%S")
