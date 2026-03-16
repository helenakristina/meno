"""Tests for ExportService."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import DatabaseError, ValidationError
from app.models.export import ExportRequest, ExportResponse
from app.models.symptoms import SymptomFrequency, SymptomPair
from app.services.export import ExportService


START = date(2026, 1, 1)
END = date(2026, 1, 31)
USER_ID = "user-test-123"
SIGNED_URL = "https://storage.example.com/export.pdf"


def _make_request(start=START, end=END):
    return ExportRequest(date_range_start=start, date_range_end=end)


def _freq(name="Hot flashes", category="vasomotor", count=10):
    return SymptomFrequency(symptom_id="sym-1", symptom_name=name, category=category, count=count)


def _pair(s1="Hot flashes", s2="Night sweats", count=5, rate=0.5):
    return SymptomPair(
        symptom1_id="sym-1",
        symptom1_name=s1,
        symptom2_id="sym-2",
        symptom2_name=s2,
        cooccurrence_count=count,
        cooccurrence_rate=rate,
        total_occurrences_symptom1=count + 2,
    )


@pytest.fixture
def mock_symptoms_repo():
    mock = AsyncMock()
    row = {"logged_at": "2026-01-10T08:00:00Z", "symptoms": ["sym-1"], "free_text_entry": None}
    ref = {"sym-1": {"name": "Hot flashes", "category": "vasomotor"}}
    mock.get_logs_for_export.return_value = ([row], ref)
    return mock


@pytest.fixture
def mock_export_repo():
    mock = AsyncMock()
    mock.record_export.return_value = {"id": "exp-1"}
    mock.get_export_history.return_value = (
        [{"id": "exp-1", "export_type": "pdf"}],
        1,
    )
    return mock


@pytest.fixture
def mock_pdf_service():
    mock = MagicMock()
    mock.build_export_pdf.return_value = b"%PDF-mock"
    return mock


@pytest.fixture
def mock_storage_service():
    mock = AsyncMock()
    mock.upload_pdf.return_value = SIGNED_URL
    mock.upload_file.return_value = SIGNED_URL
    return mock


@pytest.fixture
def mock_llm_service():
    mock = AsyncMock()
    mock.generate_symptom_summary.return_value = "AI-generated summary of symptoms."
    mock.generate_provider_questions.return_value = ["Ask about HRT"]
    return mock


@pytest.fixture
def service(
    mock_symptoms_repo,
    mock_export_repo,
    mock_pdf_service,
    mock_storage_service,
    mock_llm_service,
):
    return ExportService(
        symptoms_repo=mock_symptoms_repo,
        export_repo=mock_export_repo,
        pdf_service=mock_pdf_service,
        storage_service=mock_storage_service,
        llm_service=mock_llm_service,
    )


# ---------------------------------------------------------------------------
# _validate_date_range
# ---------------------------------------------------------------------------


class TestValidateDateRange:
    def test_valid_range_does_not_raise(self, service):
        service._validate_date_range(START, END)  # no exception

    def test_start_after_end_raises(self, service):
        with pytest.raises(ValidationError, match="before"):
            service._validate_date_range(END, START)

    def test_future_end_raises(self, service):
        future = date(2099, 12, 31)
        with pytest.raises(ValidationError, match="future"):
            service._validate_date_range(START, future)

    def test_same_day_is_valid(self, service):
        service._validate_date_range(START, START)  # no exception


# ---------------------------------------------------------------------------
# _parse_log_date
# ---------------------------------------------------------------------------


class TestParseLogDate:
    def test_iso_datetime_returns_date(self, service):
        assert service._parse_log_date("2026-01-10T08:00:00Z") == "2026-01-10"

    def test_iso_with_offset_returns_date(self, service):
        assert service._parse_log_date("2026-01-10T08:00:00+00:00") == "2026-01-10"

    def test_invalid_falls_back_to_first_10_chars(self, service):
        assert service._parse_log_date("2026-01-10 bad") == "2026-01-10"


# ---------------------------------------------------------------------------
# export_as_pdf
# ---------------------------------------------------------------------------


class TestExportAsPdf:
    @pytest.mark.asyncio
    async def test_returns_export_response(self, service):
        result = await service.export_as_pdf(USER_ID, _make_request())

        assert isinstance(result, ExportResponse)
        assert result.export_type == "pdf"
        assert result.signed_url == SIGNED_URL
        assert ".pdf" in result.filename

    @pytest.mark.asyncio
    async def test_calls_llm_for_summary_and_questions(self, service, mock_llm_service):
        await service.export_as_pdf(USER_ID, _make_request())

        mock_llm_service.generate_symptom_summary.assert_called_once()
        mock_llm_service.generate_provider_questions.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_pdf_service(self, service, mock_pdf_service):
        await service.export_as_pdf(USER_ID, _make_request())

        mock_pdf_service.build_export_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_uploads_pdf_to_storage(self, service, mock_storage_service):
        await service.export_as_pdf(USER_ID, _make_request())

        mock_storage_service.upload_pdf.assert_called_once()
        call_kwargs = mock_storage_service.upload_pdf.call_args[1]
        assert call_kwargs["bucket"] == "exports"
        assert call_kwargs["content"] == b"%PDF-mock"

    @pytest.mark.asyncio
    async def test_records_export_non_critically(self, service, mock_export_repo):
        await service.export_as_pdf(USER_ID, _make_request())

        mock_export_repo.record_export.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_validation_error_on_invalid_range(self, service):
        with pytest.raises(ValidationError):
            await service.export_as_pdf(USER_ID, _make_request(start=END, end=START))

    @pytest.mark.asyncio
    async def test_raises_validation_error_when_no_logs(self, service, mock_symptoms_repo):
        mock_symptoms_repo.get_logs_for_export.return_value = ([], {})

        with pytest.raises(ValidationError, match="No symptom logs"):
            await service.export_as_pdf(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_fails(self, service, mock_llm_service):
        mock_llm_service.generate_symptom_summary.side_effect = Exception("LLM unavailable")

        with pytest.raises(DatabaseError, match="AI content"):
            await service.export_as_pdf(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_raises_database_error_when_pdf_build_fails(self, service, mock_pdf_service):
        mock_pdf_service.build_export_pdf.side_effect = Exception("ReportLab error")

        with pytest.raises(DatabaseError, match="generate PDF"):
            await service.export_as_pdf(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_raises_database_error_when_upload_fails(self, service, mock_storage_service):
        mock_storage_service.upload_pdf.side_effect = Exception("S3 unavailable")

        with pytest.raises(DatabaseError, match="upload PDF"):
            await service.export_as_pdf(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_record_failure_does_not_abort(self, service, mock_export_repo):
        """export_repo failure is non-critical — export still succeeds."""
        mock_export_repo.record_export.side_effect = Exception("DB write failed")

        result = await service.export_as_pdf(USER_ID, _make_request())

        assert isinstance(result, ExportResponse)


# ---------------------------------------------------------------------------
# export_as_csv
# ---------------------------------------------------------------------------


class TestExportAsCsv:
    @pytest.mark.asyncio
    async def test_returns_export_response(self, service):
        result = await service.export_as_csv(USER_ID, _make_request())

        assert isinstance(result, ExportResponse)
        assert result.export_type == "csv"
        assert result.signed_url == SIGNED_URL
        assert ".csv" in result.filename

    @pytest.mark.asyncio
    async def test_uploads_csv_to_storage(self, service, mock_storage_service):
        await service.export_as_csv(USER_ID, _make_request())

        mock_storage_service.upload_file.assert_called_once()
        call_kwargs = mock_storage_service.upload_file.call_args[1]
        assert call_kwargs["bucket"] == "exports"
        assert call_kwargs["content_type"] == "text/csv"

    @pytest.mark.asyncio
    async def test_csv_contains_headers(self, service, mock_storage_service):
        await service.export_as_csv(USER_ID, _make_request())

        uploaded_bytes = mock_storage_service.upload_file.call_args[1]["content"]
        csv_text = uploaded_bytes.decode()
        assert "date" in csv_text
        assert "symptoms" in csv_text
        assert "free_text_notes" in csv_text

    @pytest.mark.asyncio
    async def test_csv_contains_log_rows(self, service, mock_storage_service):
        await service.export_as_csv(USER_ID, _make_request())

        uploaded_bytes = mock_storage_service.upload_file.call_args[1]["content"]
        csv_text = uploaded_bytes.decode()
        assert "2026-01-10" in csv_text
        assert "Hot flashes" in csv_text

    @pytest.mark.asyncio
    async def test_raises_validation_error_when_no_logs(self, service, mock_symptoms_repo):
        mock_symptoms_repo.get_logs_for_export.return_value = ([], {})

        with pytest.raises(ValidationError, match="No symptom logs"):
            await service.export_as_csv(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_raises_database_error_when_upload_fails(self, service, mock_storage_service):
        mock_storage_service.upload_file.side_effect = Exception("S3 unavailable")

        with pytest.raises(DatabaseError, match="upload CSV"):
            await service.export_as_csv(USER_ID, _make_request())

    @pytest.mark.asyncio
    async def test_record_failure_does_not_abort(self, service, mock_export_repo):
        mock_export_repo.record_export.side_effect = Exception("DB write failed")

        result = await service.export_as_csv(USER_ID, _make_request())

        assert isinstance(result, ExportResponse)


# ---------------------------------------------------------------------------
# get_export_history
# ---------------------------------------------------------------------------


class TestGetExportHistory:
    @pytest.mark.asyncio
    async def test_returns_history_dict(self, service):
        result = await service.get_export_history(USER_ID)

        assert "exports" in result
        assert "total" in result
        assert "has_more" in result
        assert result["total"] == 1
        assert len(result["exports"]) == 1

    @pytest.mark.asyncio
    async def test_has_more_is_false_when_within_limit(self, service):
        result = await service.get_export_history(USER_ID, limit=50, offset=0)

        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_has_more_is_true_when_more_records_exist(self, service, mock_export_repo):
        mock_export_repo.get_export_history.return_value = (
            [{"id": "exp-1"}],
            100,
        )

        result = await service.get_export_history(USER_ID, limit=50, offset=0)

        assert result["has_more"] is True

    @pytest.mark.asyncio
    async def test_passes_limit_and_offset(self, service, mock_export_repo):
        await service.get_export_history(USER_ID, limit=10, offset=20)

        mock_export_repo.get_export_history.assert_called_once_with(USER_ID, 10, 20)
