"""
Unit tests for pure functions in app.py (validation + RAG scoring).
These do NOT require a running database — app.py needs DATABASE_URL set
just to import, so we set a dummy one before import and never open a
real connection in these tests.
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

from app import validate_string, validate_email, validate_token, AdvancedRAG  # noqa: E402


class TestValidateString:
    def test_accepts_normal_string(self):
        assert validate_string("Physics", "subject") == "Physics"

    def test_strips_whitespace(self):
        assert validate_string("  Physics  ", "subject") == "Physics"

    def test_rejects_too_short(self):
        with pytest.raises(ValueError):
            validate_string("", "subject", min_len=1)

    def test_rejects_too_long(self):
        with pytest.raises(ValueError):
            validate_string("x" * 300, "subject", max_len=255)

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            validate_string(123, "subject")

    @pytest.mark.parametrize("bad_char", ["<", ">", '"', "'"])
    def test_rejects_html_special_chars(self, bad_char):
        with pytest.raises(ValueError):
            validate_string(f"exam{bad_char}name", "exam_name")


class TestValidateEmail:
    def test_accepts_valid_email(self):
        assert validate_email("Student@Example.com") == "student@example.com"

    def test_rejects_missing_at(self):
        with pytest.raises(ValueError):
            validate_email("not-an-email")

    def test_rejects_missing_domain(self):
        with pytest.raises(ValueError):
            validate_email("user@")


class TestValidateToken:
    def test_accepts_well_formed_token(self):
        token = "a" * 32
        assert validate_token(token) == token

    def test_rejects_short_token(self):
        with pytest.raises(ValueError):
            validate_token("short")

    def test_rejects_token_with_bad_chars(self):
        with pytest.raises(ValueError):
            validate_token("a" * 20 + "!!!")

    def test_rejects_empty_token(self):
        with pytest.raises(ValueError):
            validate_token("")


class TestAdvancedRAG:
    def setup_method(self):
        self.rag = AdvancedRAG()

    def test_hybrid_search_empty_chunks_returns_empty(self):
        assert self.rag.hybrid_search("what is gravity", []) == []

    def test_hybrid_search_ranks_relevant_chunk_higher(self):
        chunks = [
            "Photosynthesis converts light energy into chemical energy in plants.",
            "The mitochondria is the powerhouse of the cell.",
            "Gravity is a force that attracts two bodies toward each other.",
        ]
        results = self.rag.hybrid_search("What causes gravity?", chunks, top_k=1)
        assert len(results) == 1
        assert "gravity" in results[0]["text"].lower()

    def test_hybrid_search_respects_top_k(self):
        chunks = [f"chunk {i} about topic {i}" for i in range(10)]
        results = self.rag.hybrid_search("topic 5", chunks, top_k=3)
        assert len(results) == 3

    def test_bm25_score_length_matches_chunks(self):
        chunks = ["alpha beta", "beta gamma", "gamma delta"]
        scores = self.rag.bm25_score("beta", chunks)
        assert len(scores) == len(chunks)
