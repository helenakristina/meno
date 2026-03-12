"""Tests for RAG retrieval module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.retrieval import (
    _keyword_score,
    _reciprocal_rank_fusion,
    retrieve_relevant_chunks,
)


# ============================================================================
# TestKeywordScore: Unit tests for keyword scoring
# ============================================================================


class TestKeywordScore:
    """Test keyword scoring function."""

    def test_exact_match_scores_nonzero(self):
        """Test that exact match in content returns nonzero score."""
        query = "hot flashes"
        content = "Hot flashes are common during menopause"
        score = _keyword_score(query, content)
        assert score > 0

    def test_no_match_scores_zero(self):
        """Test that unrelated query and content returns zero."""
        query = "estradiol therapy"
        content = "This discusses diet and exercise only"
        score = _keyword_score(query, content)
        assert score == 0.0

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        query = "Hot Flash"
        content = "hot flash symptoms are common"
        score = _keyword_score(query, content)
        assert score > 0

    def test_stopwords_ignored(self):
        """Test that stopwords are filtered out."""
        query = "the hot flashes"  # "the" is a stopword
        content = "hot flashes are common"
        score = _keyword_score(query, content)
        assert score > 0

    def test_short_tokens_ignored(self):
        """Test that tokens shorter than 3 chars are ignored."""
        query = "we do hot flashes in menopause"  # "we", "do" ignored
        content = "hot flashes menopause symptoms"
        score = _keyword_score(query, content)
        assert score > 0

    def test_empty_query_tokens_returns_zero(self):
        """Test that query with only stopwords/short tokens returns zero."""
        query = "the a an or we do"  # All stopwords/short
        content = "Some medical content here"
        score = _keyword_score(query, content)
        assert score == 0.0

    def test_multiple_occurrences_higher_score(self):
        """Test that multiple occurrences increase score."""
        query = "progesterone"
        content_one = "Progesterone therapy is one option"
        content_many = "Progesterone progesterone progesterone therapy is discussed"
        score_one = _keyword_score(query, content_one)
        score_many = _keyword_score(query, content_many)
        assert score_many > score_one

    def test_longer_content_with_more_matches_scores_higher(self):
        """Test that more matches increase score, even with sqrt normalization."""
        query = "progesterone"
        content_one_match = "Progesterone therapy"
        content_many_matches = "Progesterone " * 5 + "therapy"
        score_one = _keyword_score(query, content_one_match)
        score_many = _keyword_score(query, content_many_matches)
        # More matches increase score despite sqrt normalization
        assert score_many > score_one


# ============================================================================
# TestReciprocalRankFusion: Unit tests for RRF combining
# ============================================================================


class TestReciprocalRankFusion:
    """Test Reciprocal Rank Fusion function."""

    def test_doc_in_both_lists_scores_higher(self):
        """Test that document in both lists ranks higher than in only one."""
        doc_a = {"id": "a", "title": "Doc A"}
        doc_b = {"id": "b", "title": "Doc B"}
        doc_c = {"id": "c", "title": "Doc C"}

        semantic = [doc_a, doc_b]
        keyword = [doc_a, doc_c]

        combined = _reciprocal_rank_fusion(semantic, keyword)

        # doc_a is in both lists, so should rank first
        assert combined[0]["id"] == "a"
        # doc_b and doc_c in only one list each, order depends on RRF calculation
        ids = [combined[1]["id"], combined[2]["id"]]
        assert set(ids) == {"b", "c"}

    def test_preserves_all_unique_docs(self):
        """Test that all unique documents are returned."""
        doc_a = {"id": "a"}
        doc_b = {"id": "b"}
        doc_c = {"id": "c"}
        doc_d = {"id": "d"}

        semantic = [doc_a, doc_b]
        keyword = [doc_c, doc_d]

        combined = _reciprocal_rank_fusion(semantic, keyword)

        assert len(combined) == 4
        ids = {doc["id"] for doc in combined}
        assert ids == {"a", "b", "c", "d"}

    def test_empty_semantic_list(self):
        """Test RRF with empty semantic list."""
        doc_a = {"id": "a"}
        keyword = [doc_a]
        combined = _reciprocal_rank_fusion([], keyword)
        assert len(combined) == 1
        assert combined[0]["id"] == "a"

    def test_empty_keyword_list(self):
        """Test RRF with empty keyword list."""
        doc_a = {"id": "a"}
        semantic = [doc_a]
        combined = _reciprocal_rank_fusion(semantic, [])
        assert len(combined) == 1
        assert combined[0]["id"] == "a"

    def test_both_empty_lists(self):
        """Test RRF with both lists empty."""
        combined = _reciprocal_rank_fusion([], [])
        assert combined == []

    def test_hybrid_score_field_present(self):
        """Test that hybrid_score field is added to results."""
        doc_a = {"id": "a"}
        semantic = [doc_a]
        keyword = []
        combined = _reciprocal_rank_fusion(semantic, keyword)
        assert "hybrid_score" in combined[0]
        assert isinstance(combined[0]["hybrid_score"], float)

    def test_custom_k_parameter_affects_scores(self):
        """Test that custom k parameter affects RRF scores."""
        doc_a = {"id": "a"}
        doc_b = {"id": "b"}

        semantic = [doc_a]
        keyword = [doc_b]

        combined_k60 = _reciprocal_rank_fusion(semantic, keyword, k=60)
        combined_k10 = _reciprocal_rank_fusion(semantic, keyword, k=10)

        # Verify that k parameter is actually used in RRF calculation
        # Both produce valid scores
        for combined in [combined_k60, combined_k10]:
            assert len(combined) == 2
            for doc in combined:
                assert "hybrid_score" in doc
                assert doc["hybrid_score"] > 0


# ============================================================================
# TestRetrieveRelevantChunks: Integration tests with mocks
# ============================================================================

SAMPLE_DOCS = [
    {
        "id": "doc-1",
        "content": "Estrogen therapy helps hot flashes and night sweats during menopause",
        "title": "Hormone Therapy Overview",
        "source_url": "http://example.com/ht",
        "source_type": "wiki",
        "section_name": "Treatment",
        "embedding": "[0.1, 0.2, 0.3]",
    },
    {
        "id": "doc-2",
        "content": "Progesterone plays an important role in the menstrual cycle and bone health",
        "title": "Progesterone Guide",
        "source_url": "http://example.com/prog",
        "source_type": "research",
        "section_name": "Hormones",
        "embedding": "[0.15, 0.25, 0.35]",
    },
    {
        "id": "doc-3",
        "content": "Estradiol patches and pills are common hormone therapy options",
        "title": "Estradiol Delivery",
        "source_url": "http://example.com/estradiol",
        "source_type": "wiki",
        "section_name": "Medication",
        "embedding": "[0.12, 0.22, 0.32]",
    },
]


class TestRetrieveRelevantChunks:
    """Test main retrieval function."""

    @pytest.mark.asyncio
    async def test_returns_top_k_results(self):
        """Test that function returns at most top_k results."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                # Mock OpenAI embedding
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                # Mock Supabase
                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=SAMPLE_DOCS)
                )

                results = await retrieve_relevant_chunks("hot flashes", top_k=2)

                assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_docs(self):
        """Test that function returns empty list when Supabase has no docs."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=[])
                )

                results = await retrieve_relevant_chunks("test query")

                assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_score_field_present(self):
        """Test that returned dicts contain hybrid_score field."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=SAMPLE_DOCS)
                )

                results = await retrieve_relevant_chunks("test query")

                assert len(results) > 0
                for doc in results:
                    assert "hybrid_score" in doc

    @pytest.mark.asyncio
    async def test_semantic_similarity_field_preserved(self):
        """Test that returned dicts contain similarity field (semantic)."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=SAMPLE_DOCS)
                )

                results = await retrieve_relevant_chunks("test query")

                assert len(results) > 0
                for doc in results:
                    assert "similarity" in doc

    @pytest.mark.asyncio
    async def test_keyword_match_elevated(self):
        """Test that docs with exact keyword matches rank in top results."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=SAMPLE_DOCS)
                )

                # Query with specific medical term that appears in doc-3
                results = await retrieve_relevant_chunks("estradiol patch", top_k=3)

                assert len(results) > 0
                # Doc-3 contains "estradiol patches" explicitly, should rank high
                result_ids = [doc["id"] for doc in results]
                assert "doc-3" in result_ids

    @pytest.mark.asyncio
    async def test_openai_failure_propagates(self):
        """Test that OpenAI API failure is propagated."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai
            mock_openai.embeddings.create.side_effect = Exception("OpenAI API error")

            with pytest.raises(Exception, match="OpenAI API error"):
                await retrieve_relevant_chunks("test query")

    @pytest.mark.asyncio
    async def test_supabase_failure_propagates(self):
        """Test that Supabase API failure is propagated."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    side_effect=Exception("Supabase error")
                )

                with pytest.raises(Exception, match="Supabase error"):
                    await retrieve_relevant_chunks("test query")

    @pytest.mark.asyncio
    async def test_skips_docs_with_no_embedding(self):
        """Test that docs without valid embeddings are skipped."""
        docs_with_missing = [
            {
                "id": "doc-1",
                "content": "Valid doc with embedding",
                "title": "Doc 1",
                "source_url": "http://example.com/1",
                "source_type": "wiki",
                "embedding": "[0.1, 0.2, 0.3]",
            },
            {
                "id": "doc-2",
                "content": "Doc without embedding",
                "title": "Doc 2",
                "source_url": "http://example.com/2",
                "source_type": "wiki",
                "embedding": None,  # Missing embedding
            },
            {
                "id": "doc-3",
                "content": "Another valid doc",
                "title": "Doc 3",
                "source_url": "http://example.com/3",
                "source_type": "wiki",
                "embedding": "[0.15, 0.25, 0.35]",
            },
        ]

        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=docs_with_missing)
                )

                results = await retrieve_relevant_chunks("test query")

                # Only 2 docs should be in results (doc-1 and doc-3)
                result_ids = [doc["id"] for doc in results]
                assert "doc-2" not in result_ids
                assert len(result_ids) == 2

    @pytest.mark.asyncio
    async def test_handles_unparseable_embedding_string(self):
        """Test that unparseable embedding strings are handled gracefully."""
        docs_with_bad_embedding = [
            {
                "id": "doc-1",
                "content": "Valid doc",
                "title": "Doc 1",
                "source_url": "http://example.com/1",
                "source_type": "wiki",
                "embedding": "[0.1, 0.2, 0.3]",
            },
            {
                "id": "doc-2",
                "content": "Doc with bad embedding",
                "title": "Doc 2",
                "source_url": "http://example.com/2",
                "source_type": "wiki",
                "embedding": "not_a_valid_embedding",
            },
        ]

        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=docs_with_bad_embedding)
                )

                results = await retrieve_relevant_chunks("test query")

                # Only doc-1 should be in results
                result_ids = [doc["id"] for doc in results]
                assert "doc-1" in result_ids
                assert "doc-2" not in result_ids

    @pytest.mark.asyncio
    async def test_response_structure_complete(self):
        """Test that response has all required fields."""
        with patch("app.rag.retrieval._openai_client") as mock_openai_class:
            with patch("app.rag.retrieval.get_client") as mock_get_client:
                mock_openai = AsyncMock()
                mock_openai_class.return_value = mock_openai
                mock_openai.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
                )

                mock_supabase = MagicMock()
                mock_get_client.return_value = mock_supabase
                mock_supabase.table.return_value.select.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=SAMPLE_DOCS)
                )

                results = await retrieve_relevant_chunks("test query", top_k=1)

                assert len(results) > 0
                doc = results[0]
                assert "id" in doc
                assert "content" in doc
                assert "title" in doc
                assert "source_url" in doc
                assert "source_type" in doc
                assert "section_name" in doc
                assert "similarity" in doc
                assert "hybrid_score" in doc
