"""Export endpoints: PDF provider summary and CSV raw data download.

POST /api/export/pdf  — Authenticated. Generates a clinical PDF with AI-written
                        symptom summary and suggested provider questions.
POST /api/export/csv  — Authenticated. Returns raw symptom logs as a CSV file.
"""
import csv
import itertools
import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from reportlab.lib import colors
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
from supabase import AsyncClient

from app.api.dependencies import CurrentUser
from app.core.supabase import get_client
from app.models.export import ExportRequest
from app.models.symptoms import SymptomFrequency, SymptomPair
from app.services.llm import generate_provider_questions, generate_symptom_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])

# ---------------------------------------------------------------------------
# PDF styling constants — clinical, professional, neutral palette
# ---------------------------------------------------------------------------

_NEUTRAL_DARK = colors.HexColor("#2D3748")
_NEUTRAL_LIGHT = colors.HexColor("#718096")
_ACCENT = colors.HexColor("#2B6CB0")
_HEADER_BG = colors.HexColor("#F7FAFC")
_BORDER = colors.HexColor("#CBD5E0")
_ALT_ROW = colors.HexColor("#EDF2F7")


SupabaseClient = Annotated[AsyncClient, Depends(get_client)]


# ---------------------------------------------------------------------------
# Shared data-fetching helpers
# ---------------------------------------------------------------------------


async def _fetch_logs(
    user_id: str,
    start: date,
    end: date,
    client: AsyncClient,
) -> list[dict]:
    """Fetch symptom logs for the user in the given date range."""
    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)
    response = (
        await client.table("symptom_logs")
        .select("logged_at, symptoms, free_text_entry")
        .eq("user_id", user_id)
        .gte("logged_at", start_dt.isoformat())
        .lte("logged_at", end_dt.isoformat())
        .order("logged_at", desc=False)
        .execute()
    )
    return response.data or []


async def _fetch_symptom_names(
    symptom_ids: list[str], client: AsyncClient
) -> dict[str, dict]:
    """Return a map of symptom_id → {name, category} for the given IDs."""
    if not symptom_ids:
        return {}
    response = (
        await client.table("symptoms_reference")
        .select("id, name, category")
        .in_("id", symptom_ids)
        .execute()
    )
    return {row["id"]: row for row in (response.data or [])}


def _compute_frequency_stats(
    rows: list[dict], ref_lookup: dict[str, dict]
) -> list[SymptomFrequency]:
    """Calculate per-symptom occurrence counts, resolved to SymptomFrequency objects."""
    counts: Counter[str] = Counter(
        sid for row in rows for sid in (row.get("symptoms") or [])
    )
    stats: list[SymptomFrequency] = []
    for symptom_id, count in counts.most_common():
        ref = ref_lookup.get(symptom_id)
        if ref:
            stats.append(
                SymptomFrequency(
                    symptom_id=symptom_id,
                    symptom_name=ref["name"],
                    category=ref["category"],
                    count=count,
                )
            )
    return stats


def _compute_cooccurrence_stats(
    rows: list[dict],
    ref_lookup: dict[str, dict],
    min_threshold: int = 2,
) -> list[SymptomPair]:
    """Calculate symptom pair co-occurrence rates above a minimum threshold."""
    symptom_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()

    for row in rows:
        symptoms = list(dict.fromkeys(row.get("symptoms") or []))
        for sid in symptoms:
            symptom_counts[sid] += 1
        if len(symptoms) >= 2:
            for a, b in itertools.combinations(sorted(symptoms), 2):
                pair_counts[(a, b)] += 1

    pairs: list[SymptomPair] = []
    for (id_a, id_b), co_count in pair_counts.items():
        if co_count < min_threshold:
            continue
        ref_a = ref_lookup.get(id_a)
        ref_b = ref_lookup.get(id_b)
        if not ref_a or not ref_b:
            continue
        total_a = symptom_counts[id_a]
        rate = co_count / total_a if total_a else 0.0
        pairs.append(
            SymptomPair(
                symptom1_id=id_a,
                symptom1_name=ref_a["name"],
                symptom2_id=id_b,
                symptom2_name=ref_b["name"],
                cooccurrence_count=co_count,
                cooccurrence_rate=round(rate, 4),
                total_occurrences_symptom1=total_a,
            )
        )

    pairs.sort(key=lambda p: p.cooccurrence_rate, reverse=True)
    return pairs[:10]


def _log_date(logged_at: str) -> str:
    """Extract YYYY-MM-DD from an ISO 8601 datetime string."""
    try:
        dt = datetime.fromisoformat(logged_at.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return logged_at[:10]


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------


def _build_pdf(
    date_range_start: date,
    date_range_end: date,
    ai_summary: str,
    frequency_stats: list[SymptomFrequency],
    cooccurrence_pairs: list[SymptomPair],
    provider_questions: list[str],
) -> bytes:
    """Assemble a clinical PDF report using reportlab and return raw bytes."""
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
        ts.append(("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 else _ALT_ROW))
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
                ("BACKGROUND", (0, i), (-1, i), colors.white if i % 2 else _ALT_ROW)
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

    story.append(Spacer(1, 14))

    # --- Disclaimer ---
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=6))
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


# ---------------------------------------------------------------------------
# POST /api/export/pdf
# ---------------------------------------------------------------------------


@router.post(
    "/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export symptom summary as PDF",
    description=(
        "Generate a clinical PDF report for a healthcare provider visit. "
        "Includes an AI-written symptom pattern summary, frequency table, "
        "co-occurrence highlights, and suggested questions to discuss."
    ),
)
async def export_pdf(
    payload: ExportRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> Response:
    """Generate and return a PDF provider summary for the authenticated user.

    Raises:
        HTTPException: 400 if date range is invalid or no logs exist.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 500 if OpenAI or PDF generation fails.
    """
    today = date.today()

    if payload.date_range_start > payload.date_range_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_range_start must be on or before date_range_end",
        )
    if payload.date_range_end > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_range_end cannot be in the future",
        )

    # --- Fetch logs ---
    try:
        rows = await _fetch_logs(
            user_id, payload.date_range_start, payload.date_range_end, client
        )
    except Exception as exc:
        logger.error("DB error fetching logs for PDF export (user %s): %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom logs",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No symptom logs found for the selected date range",
        )

    # --- Resolve symptom names ---
    all_ids = list({sid for row in rows for sid in (row.get("symptoms") or [])})
    try:
        ref_lookup = await _fetch_symptom_names(all_ids, client)
    except Exception as exc:
        logger.error("DB error fetching symptom names for PDF (user %s): %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom data",
        )

    # --- Calculate stats ---
    freq_stats = _compute_frequency_stats(rows, ref_lookup)
    coocc_pairs = _compute_cooccurrence_stats(rows, ref_lookup, min_threshold=2)

    logger.info(
        "PDF export stats: user=%s range=%s–%s logs=%d freq=%d pairs=%d",
        user_id,
        payload.date_range_start,
        payload.date_range_end,
        len(rows),
        len(freq_stats),
        len(coocc_pairs),
    )

    # --- LLM generation ---
    try:
        ai_summary = await generate_symptom_summary(
            freq_stats,
            coocc_pairs,
            (payload.date_range_start, payload.date_range_end),
        )
        questions = await generate_provider_questions(freq_stats, coocc_pairs)
    except Exception as exc:
        logger.error("OpenAI call failed for PDF export (user %s): %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI content for the report",
        )

    # --- Build PDF ---
    try:
        pdf_bytes = _build_pdf(
            date_range_start=payload.date_range_start,
            date_range_end=payload.date_range_end,
            ai_summary=ai_summary,
            frequency_stats=freq_stats,
            cooccurrence_pairs=coocc_pairs,
            provider_questions=questions,
        )
    except Exception as exc:
        logger.error("PDF generation failed for user %s: %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF",
        )

    # --- Record export (non-critical) ---
    try:
        await client.table("exports").insert({
            "user_id": user_id,
            "export_type": "pdf",
            "date_range_start": payload.date_range_start.isoformat(),
            "date_range_end": payload.date_range_end.isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("Failed to record PDF export for user %s: %s", user_id, exc)

    filename = (
        f"meno-summary-{payload.date_range_start}-{payload.date_range_end}.pdf"
    )
    logger.info("PDF export complete: user=%s size=%d bytes", user_id, len(pdf_bytes))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# POST /api/export/csv
# ---------------------------------------------------------------------------


@router.post(
    "/csv",
    status_code=status.HTTP_200_OK,
    summary="Export symptom logs as CSV",
    description=(
        "Download raw symptom logs as a CSV file with columns: "
        "date, symptoms (comma-separated), free_text_notes. "
        "Compatible with Excel and Google Sheets."
    ),
)
async def export_csv(
    payload: ExportRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> Response:
    """Return raw symptom logs as a downloadable CSV file.

    Raises:
        HTTPException: 400 if date range is invalid or no logs exist.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 500 if data fetching fails.
    """
    today = date.today()

    if payload.date_range_start > payload.date_range_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_range_start must be on or before date_range_end",
        )
    if payload.date_range_end > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_range_end cannot be in the future",
        )

    # --- Fetch logs ---
    try:
        rows = await _fetch_logs(
            user_id, payload.date_range_start, payload.date_range_end, client
        )
    except Exception as exc:
        logger.error("DB error fetching logs for CSV export (user %s): %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom logs",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No symptom logs found for the selected date range",
        )

    # --- Resolve symptom names ---
    all_ids = list({sid for row in rows for sid in (row.get("symptoms") or [])})
    try:
        ref_lookup = await _fetch_symptom_names(all_ids, client)
    except Exception as exc:
        logger.error("DB error fetching symptom names for CSV (user %s): %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom data",
        )

    # --- Build CSV ---
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "symptoms", "free_text_notes"])

    for row in rows:
        log_date = _log_date(row.get("logged_at", ""))
        symptom_ids = row.get("symptoms") or []
        symptom_names = ", ".join(
            ref_lookup[sid]["name"] for sid in symptom_ids if sid in ref_lookup
        )
        free_text = row.get("free_text_entry") or ""
        writer.writerow([log_date, symptom_names, free_text])

    csv_content = output.getvalue()

    # --- Record export (non-critical) ---
    try:
        await client.table("exports").insert({
            "user_id": user_id,
            "export_type": "csv",
            "date_range_start": payload.date_range_start.isoformat(),
            "date_range_end": payload.date_range_end.isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("Failed to record CSV export for user %s: %s", user_id, exc)

    filename = (
        f"meno-logs-{payload.date_range_start}-{payload.date_range_end}.csv"
    )
    logger.info(
        "CSV export complete: user=%s logs=%d size=%d bytes",
        user_id,
        len(rows),
        len(csv_content),
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(csv_content.encode())),
        },
    )
