"""Tests for RAG retrieval module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.retrieval import retrieve_relevant_chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supabase_mock(data: list[dict]) -> MagicMock:
    """Return a Supabase client mock whose rpc().execute() returns data."""
    mock_supabase = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute = AsyncMock(return_value=MagicMock(data=data))
    mock_supabase.rpc.return_value = mock_rpc
    return mock_supabase


def _make_openai_mock() -> AsyncMock:
    """Return an OpenAI client mock that returns a dummy embedding."""
    mock_openai = AsyncMock()
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
    )
    return mock_openai


# ---------------------------------------------------------------------------
# Sample data: RPC returns similarity (not embedding)
# ---------------------------------------------------------------------------

SAMPLE_DOCS = [
    {
        "id": "doc-1",
        "content": "Estrogen therapy helps hot flashes and night sweats during menopause",
        "title": "Hormone Therapy Overview",
        "source_url": "http://example.com/ht",
        "source_type": "wiki",
        "section_name": "Treatment",
        "similarity": 0.85,
    },
    {
        "id": "doc-2",
        "content": "Progesterone plays an important role in the menstrual cycle and bone health",
        "title": "Progesterone Guide",
        "source_url": "http://example.com/prog",
        "source_type": "research",
        "section_name": "Hormones",
        "similarity": 0.72,
    },
    {
        "id": "doc-3",
        "content": "Estradiol patches and pills are common hormone therapy options",
        "title": "Estradiol Delivery",
        "source_url": "http://example.com/estradiol",
        "source_type": "wiki",
        "section_name": "Medication",
        "similarity": 0.68,
    },
]


# ============================================================================
# TestRetrieveRelevantChunks
# ============================================================================


class TestRetrieveRelevantChunks:
    @pytest.mark.asyncio
    async def test_when_rpc_returns_docs_then_returns_them(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock(SAMPLE_DOCS)

                results = await retrieve_relevant_chunks("hot flashes")

                assert len(results) == 3

    @pytest.mark.asyncio
    async def test_when_rpc_returns_no_docs_then_returns_empty_list(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock([])

                results = await retrieve_relevant_chunks("test query")

                assert results == []

    @pytest.mark.asyncio
    async def test_when_all_docs_below_min_similarity_then_returns_empty_list(self):
        low_similarity_docs = [{**doc, "similarity": 0.10} for doc in SAMPLE_DOCS]
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock(low_similarity_docs)

                results = await retrieve_relevant_chunks("test query")

                assert results == []

    @pytest.mark.asyncio
    async def test_when_mixed_similarity_then_only_above_threshold_returned(self):
        mixed_docs = [
            {**SAMPLE_DOCS[0], "similarity": 0.80},  # above threshold
            {**SAMPLE_DOCS[1], "similarity": 0.20},  # below threshold (0.25)
            {**SAMPLE_DOCS[2], "similarity": 0.40},  # above threshold
        ]
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock(mixed_docs)

                results = await retrieve_relevant_chunks("test query")

                assert len(results) == 2
                result_ids = {doc["id"] for doc in results}
                assert "doc-1" in result_ids
                assert "doc-3" in result_ids
                assert "doc-2" not in result_ids

    @pytest.mark.asyncio
    async def test_when_top_k_specified_then_rpc_called_with_match_count(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_supabase = _make_supabase_mock(SAMPLE_DOCS[:2])
                mock_get_client.return_value = mock_supabase

                await retrieve_relevant_chunks("hot flashes", top_k=2)

                mock_supabase.rpc.assert_called_once_with(
                    "match_rag_documents",
                    {"query_embedding": "[0.1, 0.2, 0.3]", "match_count": 2},
                )

    @pytest.mark.asyncio
    async def test_when_docs_returned_then_response_structure_complete(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock(SAMPLE_DOCS[:1])

                results = await retrieve_relevant_chunks("test query")

                assert len(results) == 1
                doc = results[0]
                assert "id" in doc
                assert "content" in doc
                assert "title" in doc
                assert "source_url" in doc
                assert "source_type" in doc
                assert "section_name" in doc
                assert "similarity" in doc

    @pytest.mark.asyncio
    async def test_when_openai_fails_then_raises(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai
            mock_openai.embeddings.create.side_effect = Exception("OpenAI API error")

            with pytest.raises(Exception, match="OpenAI API error"):
                await retrieve_relevant_chunks("test query")

    @pytest.mark.asyncio
    async def test_when_supabase_rpc_fails_then_raises(self):
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()

                mock_supabase = MagicMock()
                mock_rpc = MagicMock()
                mock_rpc.execute = AsyncMock(
                    side_effect=Exception("Supabase RPC error")
                )
                mock_supabase.rpc.return_value = mock_rpc
                mock_get_client.return_value = mock_supabase

                with pytest.raises(Exception, match="Supabase RPC error"):
                    await retrieve_relevant_chunks("test query")

    @pytest.mark.asyncio
    async def test_when_custom_min_similarity_then_threshold_applied(self):
        docs = [
            {**SAMPLE_DOCS[0], "similarity": 0.60},
            {**SAMPLE_DOCS[1], "similarity": 0.45},
        ]
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch(
                "app.rag.retrieval.get_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_openai_class.return_value = _make_openai_mock()
                mock_get_client.return_value = _make_supabase_mock(docs)

                # With a high threshold, only doc-1 (0.60) should pass
                results = await retrieve_relevant_chunks(
                    "test query", min_similarity=0.55
                )

                assert len(results) == 1
                assert results[0]["id"] == "doc-1"
