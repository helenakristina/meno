"""PdfService — all PDF rendering for Meno.

Consolidates PDF generation from appointment prep (markdown → PDF) and
health exports (clinical report with tables).

No external API calls — all methods are pure computation that return bytes.
"""

import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.appointment import CheatsheetResponse, ProviderSummaryResponse
from app.models.symptoms import SymptomFrequency, SymptomPair

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color palette — Meno design system
# ---------------------------------------------------------------------------

_NEUTRAL_DARK = colors.HexColor("#292524")   # neutral-800
_NEUTRAL_LIGHT = colors.HexColor("#78716c")  # neutral-500
_ACCENT = colors.HexColor("#0d9478")         # primary-600 (Meno teal)
_HEADER_BG = colors.HexColor("#f0fdf9")      # primary-50
_BORDER = colors.HexColor("#d6d3d1")         # neutral-300
_ALT_ROW = colors.HexColor("#f5f5f4")        # neutral-100


class PdfService:
    """PDF rendering service.

    Consolidates all PDF generation:
    - markdown_to_pdf(): appointment prep documents (markdown → formatted PDF)
    - build_export_pdf(): health summary export (clinical report with tables)

    All methods are pure — no external calls, no I/O. Return raw bytes.
    """

    def markdown_to_pdf(self, markdown_text: str, title: str = "") -> bytes:
        """Convert markdown text to PDF bytes using reportlab.

        Handles headings (h1–h4), bullet lists, numbered lists, paragraphs,
        and inline formatting (bold, italic, bold-italic, inline code).

        Args:
            markdown_text: Markdown-formatted text to render.
            title: Optional document title rendered centred at the top.

        Returns:
            PDF file content as bytes.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=HexColor("#1f2937"),
            spaceAfter=12,
            alignment=1,
        )
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=HexColor("#1f2937"),
            spaceBefore=10,
            spaceAfter=6,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=HexColor("#374151"),
            spaceBefore=8,
            spaceAfter=4,
        )
        h3_style = ParagraphStyle(
            "H3",
            parent=styles["Heading3"],
            fontSize=11,
            textColor=HexColor("#374151"),
            spaceBefore=6,
            spaceAfter=3,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            "Bullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            leftIndent=20,
            spaceAfter=2,
        )
        numbered_style = ParagraphStyle(
            "Numbered",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            leftIndent=20,
            spaceAfter=2,
        )

        story = []

        if title:
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 0.2 * inch))

        for line in markdown_text.split("\n"):
            stripped = line.strip()

            if not stripped:
                story.append(Spacer(1, 0.06 * inch))
            elif stripped.startswith("#### "):
                story.append(Paragraph(self._inline_md(stripped[5:]), h3_style))
            elif stripped.startswith("### "):
                story.append(Paragraph(self._inline_md(stripped[4:]), h3_style))
            elif stripped.startswith("## "):
                story.append(Paragraph(self._inline_md(stripped[3:]), h2_style))
            elif stripped.startswith("# "):
                story.append(Paragraph(self._inline_md(stripped[2:]), h1_style))
            elif stripped.startswith("- ") or stripped.startswith("* "):
                story.append(
                    Paragraph(f"• {self._inline_md(stripped[2:])}", bullet_style)
                )
            elif re.match(r"^\d+\. ", stripped):
                m = re.match(r"^(\d+)\. (.+)", stripped)
                if m:
                    story.append(
                        Paragraph(
                            f"{m.group(1)}. {self._inline_md(m.group(2))}",
                            numbered_style,
                        )
                    )
            elif stripped in ("---", "***", "___"):
                story.append(Spacer(1, 0.08 * inch))
            else:
                story.append(Paragraph(self._inline_md(stripped), body_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def build_export_pdf(
        self,
        date_range_start,
        date_range_end,
        ai_summary: str,
        frequency_stats: list[SymptomFrequency],
        cooccurrence_pairs: list[SymptomPair],
        provider_questions: list[str],
        current_medications: Optional[list] = None,
    ) -> bytes:
        """Assemble a clinical export PDF report and return raw bytes.

        Args:
            date_range_start: Start date of the report period.
            date_range_end: End date of the report period.
            ai_summary: LLM-generated symptom pattern summary text.
            frequency_stats: List of SymptomFrequency objects.
            cooccurrence_pairs: List of SymptomPair objects.
            provider_questions: List of question strings for provider.
            current_medications: Optional list of active MedicationResponse objects.

        Returns:
            PDF file content as bytes.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.9 * inch,
            leftMargin=0.9 * inch,
            topMargin=0.9 * inch,
            bottomMargin=1.0 * inch,
        )

        base = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "MenoTitle",
            parent=base["Title"],
            fontSize=20,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "MenoMeta",
            parent=base["Normal"],
            fontSize=9,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            spaceAfter=2,
        )
        heading_style = ParagraphStyle(
            "MenoHeading",
            parent=base["Heading2"],
            fontSize=12,
            textColor=_ACCENT,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "MenoBody",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica",
            leading=14,
            spaceAfter=6,
        )
        question_style = ParagraphStyle(
            "MenoQuestion",
            parent=body_style,
            leftIndent=14,
            spaceAfter=4,
        )
        disclaimer_style = ParagraphStyle(
            "MenoDisclaimer",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            leading=11,
        )

        story = []

        # --- Header ---
        story.append(Paragraph("Meno Health Summary", title_style))
        story.append(
            Paragraph(
                f"Period: {date_range_start.strftime('%B %d, %Y')} "
                f"– {date_range_end.strftime('%B %d, %Y')}",
                meta_style,
            )
        )
        story.append(
            Paragraph(
                f"Generated: {datetime.now(tz=timezone.utc).strftime('%B %d, %Y')}",
                meta_style,
            )
        )
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=8))

        # --- Section 1: AI Summary ---
        story.append(Paragraph("Symptom Pattern Summary", heading_style))
        for para in ai_summary.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para.replace("\n", " "), body_style))

        # --- Section 2: Symptom Frequency ---
        story.append(Paragraph("Symptom Frequency", heading_style))

        freq_data = [["Symptom", "Category", "Times Logged"]]
        for s in frequency_stats[:10]:
            freq_data.append(
                [s.symptom_name, s.category.replace("_", " ").title(), str(s.count)]
            )
        if len(freq_data) == 1:
            freq_data.append(["No symptom data for this period", "", ""])

        col_widths = [3.0 * inch, 2.2 * inch, 1.1 * inch]
        freq_table = Table(freq_data, colWidths=col_widths)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _NEUTRAL_DARK),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ]
        for i in range(1, len(freq_data)):
            ts.append(
                ("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 else _ALT_ROW)
            )
        freq_table.setStyle(TableStyle(ts))
        story.append(freq_table)

        # --- Section 3: Co-occurrence Highlights ---
        if cooccurrence_pairs:
            story.append(Paragraph("Co-occurring Symptoms", heading_style))
            story.append(
                Paragraph(
                    "The following symptom pairs appeared together most frequently in the logs:",
                    body_style,
                )
            )
            coocc_data = [["Symptom Pair", "Together", "Rate"]]
            for p in cooccurrence_pairs[:5]:
                pair = f"{p.symptom1_name} + {p.symptom2_name}"
                rate = f"{round(p.cooccurrence_rate * 100)}%"
                coocc_data.append([pair, str(p.cooccurrence_count), rate])

            coocc_col_widths = [3.5 * inch, 1.1 * inch, 1.7 * inch]
            coocc_table = Table(coocc_data, colWidths=coocc_col_widths)
            coocc_ts = [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), _NEUTRAL_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
            for i in range(1, len(coocc_data)):
                coocc_ts.append(
                    (
                        "BACKGROUND",
                        (0, i),
                        (-1, i),
                        colors.white if i % 2 else _ALT_ROW,
                    )
                )
            coocc_table.setStyle(TableStyle(coocc_ts))
            story.append(coocc_table)

        # --- Section 4: Provider Questions ---
        if provider_questions:
            story.append(Paragraph("Questions for Your Provider", heading_style))
            story.append(
                Paragraph(
                    "Based on the logged patterns, you might consider asking your provider:",
                    body_style,
                )
            )
            for i, q in enumerate(provider_questions, 1):
                story.append(Paragraph(f"{i}. {q}", question_style))

        # --- Section 5: Current Medications ---
        if current_medications:
            story.append(Paragraph("Current MHT Medications", heading_style))
            med_data = [["Medication", "Dose & Method", "Started"]]
            for m in current_medications:
                delivery = (m.delivery_method or "").replace("_", " ").title()
                started = str(m.start_date) if m.start_date else "—"
                med_data.append([m.medication_name, f"{m.dose} ({delivery})", started])

            med_col_widths = [2.5 * inch, 2.5 * inch, 1.3 * inch]
            med_table = Table(med_data, colWidths=med_col_widths)
            med_ts = [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), _NEUTRAL_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
            for i in range(1, len(med_data)):
                med_ts.append(
                    ("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 else _ALT_ROW)
                )
            med_table.setStyle(TableStyle(med_ts))
            story.append(med_table)

        story.append(Spacer(1, 14))

        # --- Disclaimer ---
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=6)
        )
        story.append(
            Paragraph(
                "<b>Disclaimer:</b> This report is generated from personal symptom logs "
                "and is not a medical document. The information presented reflects logged "
                "data only and does not constitute a medical diagnosis, clinical assessment, "
                "or treatment recommendation. Please discuss all health concerns with your "
                "qualified healthcare provider.",
                disclaimer_style,
            )
        )

        def _page_footer(canvas, doc):  # noqa: ANN001
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(_NEUTRAL_LIGHT)
            canvas.drawRightString(
                letter[0] - 0.9 * inch,
                0.45 * inch,
                f"Page {canvas.getPageNumber()}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
        return buffer.getvalue()

    def build_provider_summary_pdf(
        self,
        content: ProviderSummaryResponse,
        frequency_stats: list[SymptomFrequency],
        cooccurrence_stats: list[SymptomPair],
        concerns: list[str],
    ) -> bytes:
        """Build a clinical provider-facing appointment summary PDF.

        Args:
            content: Structured LLM response with opening, symptom_picture,
                     key_patterns, and closing prose sections.
            frequency_stats: Symptom frequency data to render as a table.
            cooccurrence_stats: Co-occurring symptom pairs to render as a table.
            concerns: Patient's prioritized concerns list.

        Returns:
            PDF file content as bytes.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.9 * inch,
            leftMargin=0.9 * inch,
            topMargin=0.9 * inch,
            bottomMargin=1.0 * inch,
        )

        base = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "PSTitle",
            parent=base["Title"],
            fontSize=20,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "PSMeta",
            parent=base["Normal"],
            fontSize=9,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            spaceAfter=2,
        )
        heading_style = ParagraphStyle(
            "PSHeading",
            parent=base["Heading2"],
            fontSize=12,
            textColor=_ACCENT,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "PSBody",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica",
            leading=14,
            spaceAfter=6,
        )
        concern_style = ParagraphStyle(
            "PSConcern",
            parent=body_style,
            leftIndent=14,
            spaceAfter=4,
        )
        disclaimer_style = ParagraphStyle(
            "PSDisclaimer",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            leading=11,
        )

        story = []

        # --- Header ---
        story.append(Paragraph("Appointment Summary", title_style))
        story.append(
            Paragraph(
                f"Generated: {datetime.now(tz=timezone.utc).strftime('%B %d, %Y')}",
                meta_style,
            )
        )
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=8))

        # --- Opening ---
        story.append(Paragraph("Overview", heading_style))
        story.append(Paragraph(content.opening, body_style))

        # --- Symptom Picture ---
        story.append(Paragraph("Symptom Picture", heading_style))
        story.append(Paragraph(content.symptom_picture, body_style))

        # --- Key Patterns (optional) ---
        if content.key_patterns:
            story.append(Paragraph("Key Patterns", heading_style))
            story.append(Paragraph(content.key_patterns, body_style))

        # --- Symptom Frequency Table ---
        if frequency_stats:
            story.append(Paragraph("Symptom Frequency", heading_style))
            freq_data = [["Symptom", "Category", "Times Logged"]]
            for s in frequency_stats[:10]:
                freq_data.append(
                    [s.symptom_name, s.category.replace("_", " ").title(), str(s.count)]
                )
            col_widths = [3.0 * inch, 2.2 * inch, 1.1 * inch]
            freq_table = Table(freq_data, colWidths=col_widths)
            ts = [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), _NEUTRAL_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ]
            for i in range(1, len(freq_data)):
                ts.append(
                    ("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 else _ALT_ROW)
                )
            freq_table.setStyle(TableStyle(ts))
            story.append(freq_table)

        # --- Co-occurrence Table ---
        if cooccurrence_stats:
            story.append(Paragraph("Co-occurring Symptoms", heading_style))
            coocc_data = [["Symptom Pair", "Together", "Rate"]]
            for p in cooccurrence_stats[:5]:
                pair = f"{p.symptom1_name} + {p.symptom2_name}"
                rate = f"{round(p.cooccurrence_rate * 100)}%"
                coocc_data.append([pair, str(p.cooccurrence_count), rate])
            coocc_col_widths = [3.5 * inch, 1.1 * inch, 1.7 * inch]
            coocc_table = Table(coocc_data, colWidths=coocc_col_widths)
            coocc_ts = [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), _NEUTRAL_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
            for i in range(1, len(coocc_data)):
                coocc_ts.append(
                    (
                        "BACKGROUND",
                        (0, i),
                        (-1, i),
                        colors.white if i % 2 else _ALT_ROW,
                    )
                )
            coocc_table.setStyle(TableStyle(coocc_ts))
            story.append(coocc_table)

        # --- Concerns ---
        if concerns:
            story.append(Paragraph("Patient's Prioritized Concerns", heading_style))
            for i, c in enumerate(concerns, 1):
                story.append(Paragraph(f"{i}. {c}", concern_style))

        # --- Closing ---
        story.append(Paragraph("Next Steps", heading_style))
        story.append(Paragraph(content.closing, body_style))

        story.append(Spacer(1, 14))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=6)
        )
        story.append(
            Paragraph(
                "<b>Disclaimer:</b> This document is generated from personal symptom logs "
                "and is not a medical document. It does not constitute a clinical assessment "
                "or treatment recommendation. Please discuss all health concerns with your "
                "qualified healthcare provider.",
                disclaimer_style,
            )
        )

        def _page_footer(canvas, doc):  # noqa: ANN001
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(_NEUTRAL_LIGHT)
            canvas.drawRightString(
                letter[0] - 0.9 * inch,
                0.45 * inch,
                f"Page {canvas.getPageNumber()}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
        return buffer.getvalue()

    def build_cheatsheet_pdf(
        self,
        content: CheatsheetResponse,
        concerns: list[str],
        scenarios: list[dict],
        frequency_stats: list[SymptomFrequency],
    ) -> bytes:
        """Build a patient-facing appointment cheat sheet PDF.

        Args:
            content: Structured LLM response with opening_statement and
                     question_groups (topic + questions per group).
            concerns: Patient's prioritized concerns list.
            scenarios: Scenario cards from Step 4 (each has 'title' and 'suggestion').
            frequency_stats: Symptom frequency data for the top symptoms section.

        Returns:
            PDF file content as bytes.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.9 * inch,
            leftMargin=0.9 * inch,
            topMargin=0.9 * inch,
            bottomMargin=1.0 * inch,
        )

        base = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CSTitle",
            parent=base["Title"],
            fontSize=20,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "CSMeta",
            parent=base["Normal"],
            fontSize=9,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            spaceAfter=2,
        )
        heading_style = ParagraphStyle(
            "CSHeading",
            parent=base["Heading2"],
            fontSize=12,
            textColor=_ACCENT,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=6,
        )
        subheading_style = ParagraphStyle(
            "CSSubheading",
            parent=base["Heading3"],
            fontSize=10,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "CSBody",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=_NEUTRAL_DARK,
            fontName="Helvetica",
            leading=14,
            spaceAfter=6,
        )
        item_style = ParagraphStyle(
            "CSItem",
            parent=body_style,
            leftIndent=14,
            spaceAfter=4,
        )
        disclaimer_style = ParagraphStyle(
            "CSDisclaimer",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=_NEUTRAL_LIGHT,
            fontName="Helvetica",
            leading=11,
        )

        story = []

        # --- Header ---
        story.append(Paragraph("My Appointment Cheat Sheet", title_style))
        story.append(
            Paragraph(
                f"Generated: {datetime.now(tz=timezone.utc).strftime('%B %d, %Y')}",
                meta_style,
            )
        )
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=8))

        # --- Opening Statement ---
        story.append(Paragraph("My Opening Statement", heading_style))
        story.append(Paragraph(content.opening_statement, body_style))

        # --- Top Symptoms ---
        if frequency_stats:
            story.append(Paragraph("My Most Frequent Symptoms", heading_style))
            for i, s in enumerate(frequency_stats[:5], 1):
                cat = s.category.replace("_", " ").title()
                story.append(
                    Paragraph(f"{i}. {s.symptom_name} ({cat}) — {s.count}x", item_style)
                )

        # --- Prioritized Concerns ---
        if concerns:
            story.append(Paragraph("What I Most Want to Address", heading_style))
            for i, c in enumerate(concerns, 1):
                story.append(Paragraph(f"{i}. {c}", item_style))

        # --- Questions by Topic Group ---
        if content.question_groups:
            story.append(Paragraph("Questions I Want to Ask", heading_style))
            for group in content.question_groups:
                story.append(Paragraph(group.topic, subheading_style))
                for q in group.questions:
                    story.append(Paragraph(f"• {q}", item_style))

        # --- If Things Go Sideways (scenarios) ---
        if scenarios:
            story.append(Paragraph("If Things Go Sideways", heading_style))
            story.append(
                Paragraph(
                    "If my provider dismisses my concerns, here's what I can say:",
                    body_style,
                )
            )
            for s in scenarios:
                title = s.get("title", "")
                suggestion = s.get("suggestion", "")
                if title:
                    story.append(Paragraph(title, subheading_style))
                if suggestion:
                    story.append(Paragraph(suggestion, item_style))

        # --- What to Bring (static) ---
        story.append(Paragraph("What to Bring", heading_style))
        for item in [
            "This cheat sheet",
            "A list of all current medications and supplements",
            "Any recent lab results or test reports",
            "A notebook or your phone to take notes",
        ]:
            story.append(Paragraph(f"• {item}", item_style))

        story.append(Spacer(1, 14))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=6)
        )
        story.append(
            Paragraph(
                "<b>Disclaimer:</b> This document is generated from personal symptom logs "
                "and is not a medical document. It does not constitute a clinical assessment "
                "or treatment recommendation. Please discuss all health concerns with your "
                "qualified healthcare provider.",
                disclaimer_style,
            )
        )

        def _page_footer(canvas, doc):  # noqa: ANN001
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(_NEUTRAL_LIGHT)
            canvas.drawRightString(
                letter[0] - 0.9 * inch,
                0.45 * inch,
                f"Page {canvas.getPageNumber()}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
        return buffer.getvalue()

    def _inline_md(self, text: str) -> str:
        """Convert inline markdown to reportlab XML tags.

        Handles bold-italic, bold, italic, and inline code.

        Args:
            text: Text with optional markdown formatting.

        Returns:
            Text with reportlab-compatible XML tags.
        """
        text = re.sub(r"\*{3}(.+?)\*{3}", r"<b><i>\1</i></b>", text)
        text = re.sub(r"_{3}(.+?)_{3}", r"<b><i>\1</i></b>", text)
        text = re.sub(r"\*{2}(.+?)\*{2}", r"<b>\1</b>", text)
        text = re.sub(r"_{2}(.+?)_{2}", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
        return text
