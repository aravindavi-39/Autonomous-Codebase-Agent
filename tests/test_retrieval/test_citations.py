"""Tests for Citation models and CitationValidator (Check 3 compliance)."""

from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from citations.models import Citation
from citations.validator import CitationValidator
from ingestion.pipeline import IngestionPipeline


@pytest.fixture
def sample_validator() -> CitationValidator:
    sample_repo_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(sample_repo_path))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(sample_repo_path), manifest=manifest)
    return CitationValidator(manifest=manifest, code_index=code_index)


class TestCitations:
    """Verify citation formatting and validation rules."""

    def test_citation_formatting(self) -> None:
        c1 = Citation(file="src/models.py", start_line=8, end_line=13, entity="User")
        assert c1.format_citation() == "📄 src/models.py:8-13 (User)"
        assert c1.to_compact_str() == "src/models.py:8-13"

        c2 = Citation(file="src/app.py", start_line=10, end_line=10)
        assert c2.format_citation() == "📄 src/app.py:10"
        assert c2.to_compact_str() == "src/app.py:10"

    def test_validate_valid_citation(self, sample_validator: CitationValidator) -> None:
        c = Citation(file="src/models.py", start_line=8, end_line=13, entity="User")
        res = sample_validator.validate_citation(c)
        assert res.valid is True
        assert res.reason is None

    def test_validate_nonexistent_file(self, sample_validator: CitationValidator) -> None:
        c = Citation(file="src/nonexistent.py", start_line=1, end_line=10)
        res = sample_validator.validate_citation(c)
        assert res.valid is False
        assert "does not exist" in res.reason

    def test_validate_invalid_lines(self, sample_validator: CitationValidator) -> None:
        # start_line < 1
        c1 = Citation(file="src/models.py", start_line=0, end_line=5)
        assert sample_validator.validate_citation(c1).valid is False

        # end_line < start_line
        c2 = Citation(file="src/models.py", start_line=15, end_line=10)
        assert sample_validator.validate_citation(c2).valid is False

        # start_line > total file lines (src/models.py has 24 lines)
        c3 = Citation(file="src/models.py", start_line=1000, end_line=1010)
        assert sample_validator.validate_citation(c3).valid is False

    def test_validate_nonexistent_entity(self, sample_validator: CitationValidator) -> None:
        # File exists and lines are valid, but entity NonExistentClass does not exist
        c = Citation(
            file="src/models.py",
            start_line=8,
            end_line=13,
            entity="NonExistentClass",
        )
        res = sample_validator.validate_citation(c)
        assert res.valid is False
        assert "not found" in res.reason.lower()

    def test_validate_file_exists_but_not_retrieved(self, sample_validator: CitationValidator) -> None:
        # File tests/test_app.py exists in manifest, but was NOT in retrieved allowed_sources
        c = Citation(file="tests/test_app.py", start_line=1, end_line=5)
        allowed = [Citation(file="src/models.py", start_line=8, end_line=13)]

        res = sample_validator.validate_citation(c, allowed_sources=allowed)
        assert res.valid is False
        assert "not retrieved in context" in res.reason.lower()

    def test_extract_citations_from_text(self, sample_validator: CitationValidator) -> None:
        text = """
The application starts in `src/app.py:6-14` where `create_app` is defined.
It also uses models from src/models.py:8-13 (AppConfig).
"""
        extracted = sample_validator.extract_citations_from_text(text)
        assert len(extracted) == 2
        assert extracted[0].file == "src/app.py"
        assert extracted[0].start_line == 6
        assert extracted[0].end_line == 14

        assert extracted[1].file == "src/models.py"
        assert extracted[1].start_line == 8
        assert extracted[1].end_line == 13

    def test_extract_malformed_citation(self, sample_validator: CitationValidator) -> None:
        text = "This text mentions file.py without line numbers or invalid ::: format."
        extracted = sample_validator.extract_citations_from_text(text)
        assert extracted == []

    def test_answer_with_no_citation(self, sample_validator: CitationValidator) -> None:
        text = "This answer contains purely generic text without any sources cited."
        extracted = sample_validator.extract_citations_from_text(text)
        assert extracted == []

        # Without fallback, validation result has empty valid citations
        result = sample_validator.validate_citations(extracted, fallback_citations=None)
        assert len(result.valid_citations) == 0
        assert result.fallback_used is False

    def test_hallucinated_citation_rejected(self, sample_validator: CitationValidator) -> None:
        hallucinated = [
            Citation(file="src/hallucinated_auth.py", start_line=1, end_line=50),
            Citation(file="src/models.py", start_line=8, end_line=13),
        ]
        result = sample_validator.validate_citations(hallucinated)
        assert len(result.valid_citations) == 1
        assert result.valid_citations[0].file == "src/models.py"
        assert len(result.invalid_citations) == 1
        assert result.invalid_citations[0].file == "src/hallucinated_auth.py"

    def test_system_does_not_silently_create_unretrieved_citations(
        self, sample_validator: CitationValidator
    ) -> None:
        # If an unretrieved file citation is provided, it is marked invalid and not accepted
        cites = [Citation(file="data/schema.sql", start_line=1, end_line=5)]
        allowed = [Citation(file="src/models.py", start_line=8, end_line=13)]

        result = sample_validator.validate_citations(cites, allowed_sources=allowed)
        assert len(result.valid_citations) == 0
        assert len(result.invalid_citations) == 1
        assert "not retrieved" in result.invalid_citations[0].reason.lower()

    def test_fallback_citations_injected_when_empty(self, sample_validator: CitationValidator) -> None:
        fallback = [Citation(file="src/utils.py", start_line=7, end_line=13, entity="hash_file")]
        # Empty list of LLM citations -> fallback used
        result = sample_validator.validate_citations([], fallback_citations=fallback)
        assert len(result.valid_citations) == 1
        assert result.fallback_used is True
        assert result.valid_citations[0].file == "src/utils.py"

    def test_fallback_not_used_when_valid_citations_present(self, sample_validator: CitationValidator) -> None:
        llm_cites = [Citation(file="src/models.py", start_line=8, end_line=13)]
        fallback = [Citation(file="src/utils.py", start_line=7, end_line=13)]
        result = sample_validator.validate_citations(llm_cites, fallback_citations=fallback)
        assert len(result.valid_citations) == 1
        assert result.fallback_used is False
        assert result.valid_citations[0].file == "src/models.py"
