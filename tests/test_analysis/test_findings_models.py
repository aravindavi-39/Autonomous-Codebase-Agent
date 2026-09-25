"""Tests for findings data models."""

from analysis.findings.models import (
    Confidence,
    Finding,
    FindingCategory,
    Severity,
    AnalysisReport,
)


def test_severity_levels():
    assert Severity.INFO.value == "INFO"
    assert Severity.LOW.value == "LOW"
    assert Severity.MEDIUM.value == "MEDIUM"
    assert Severity.HIGH.value == "HIGH"
    assert Severity.CRITICAL.value == "CRITICAL"
    assert Severity.CRITICAL.level > Severity.HIGH.level > Severity.LOW.level
    assert Severity.from_str("high") == Severity.HIGH


def test_confidence_levels():
    assert Confidence.LOW.value == "LOW"
    assert Confidence.MEDIUM.value == "MEDIUM"
    assert Confidence.HIGH.value == "HIGH"
    assert Confidence.HIGH.level > Confidence.LOW.level
    assert Confidence.from_str("medium") == Confidence.MEDIUM


def test_finding_category():
    assert FindingCategory.CODE_SMELL.value == "CODE_SMELL"
    assert FindingCategory.SECURITY.value == "SECURITY"
    assert FindingCategory.PATTERN.value == "PATTERN"
    assert FindingCategory.from_str("security") == FindingCategory.SECURITY
    assert FindingCategory.from_str("code_smell") == FindingCategory.CODE_SMELL
    assert FindingCategory.from_str("pattern") == FindingCategory.PATTERN


def test_finding_creation_and_citation():
    finding = Finding(
        id="SEC-001-abc12345",
        type="SEC-001",
        category=FindingCategory.SECURITY,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        title="Hardcoded API key detected",
        description="A hardcoded secret was found.",
        rationale="Exposing secrets risks credential compromise.",
        file="src/config.py",
        start_line=10,
        end_line=10,
        evidence="api_key = '[REDACTED]'",
        recommendation="Use environment variables or a secret vault.",
        entity="api_key",
    )

    d = finding.model_dump()
    assert d["id"] == "SEC-001-abc12345"
    assert d["type"] == "SEC-001"
    assert d["category"] == "SECURITY"
    assert d["severity"] == "HIGH"
    assert d["confidence"] == "HIGH"
    assert d["file"] == "src/config.py"
    assert d["start_line"] == 10
    assert d["evidence"] == "api_key = '[REDACTED]'"
    assert finding.to_citation_str() == "📄 src/config.py:10 (api_key)"


def test_analysis_report_metrics_and_summary():
    f1 = Finding(
        id="SEC-001-1",
        type="SEC-001",
        category=FindingCategory.SECURITY,
        severity=Severity.CRITICAL,
        confidence=Confidence.HIGH,
        title="Secret",
        description="Hardcoded secret",
        rationale="Security risk",
        file="src/a.py",
        start_line=1,
        end_line=1,
        evidence="token = 'xyz'",
        recommendation="Remove",
    )
    f2 = Finding(
        id="SMELL-001-1",
        type="SMELL-001",
        category=FindingCategory.CODE_SMELL,
        severity=Severity.MEDIUM,
        confidence=Confidence.MEDIUM,
        title="Long function",
        description="Function is too long",
        rationale="Hard to maintain",
        file="src/b.py",
        start_line=5,
        end_line=80,
        evidence="def big():",
        recommendation="Split",
    )
    f3 = Finding(
        id="PAT-001-1",
        type="PAT-001",
        category=FindingCategory.PATTERN,
        severity=Severity.LOW,
        confidence=Confidence.HIGH,
        title="Broad except",
        description="Catches everything",
        rationale="Masks bugs",
        file="src/c.py",
        start_line=10,
        end_line=12,
        evidence="except:",
        recommendation="Catch specific exception",
    )

    summary = {
        "total": 3,
        "critical": 1,
        "high": 0,
        "medium": 1,
        "low": 1,
        "info": 0,
        "security": 1,
        "code_smell": 1,
        "pattern": 1,
    }

    report = AnalysisReport(
        repository="/repo",
        files_analyzed=10,
        total_findings=3,
        findings=[f1, f2, f3],
        summary=summary,
    )

    assert report.total_findings == 3
    assert report.summary["critical"] == 1
    assert report.summary["medium"] == 1
    assert report.summary["low"] == 1
    assert report.summary["high"] == 0
    assert report.summary["security"] == 1


def test_analysis_report_filtering():
    f_crit = Finding(
        id="1", type="SEC-1", category=FindingCategory.SECURITY, severity=Severity.CRITICAL,
        confidence=Confidence.HIGH, title="t1", file="src/sec.py", start_line=1, end_line=1,
        evidence="s", description="d", rationale="r", recommendation="rec"
    )
    f_med = Finding(
        id="2", type="SMELL-1", category=FindingCategory.CODE_SMELL, severity=Severity.MEDIUM,
        confidence=Confidence.HIGH, title="t2", file="src/smell.py", start_line=1, end_line=1,
        evidence="s", description="d", rationale="r", recommendation="rec"
    )
    f_low = Finding(
        id="3", type="PAT-1", category=FindingCategory.PATTERN, severity=Severity.LOW,
        confidence=Confidence.LOW, title="t3", file="src/pat.py", start_line=1, end_line=1,
        evidence="s", description="d", rationale="r", recommendation="rec"
    )

    report = AnalysisReport(
        repository="/repo",
        files_analyzed=3,
        total_findings=3,
        findings=[f_crit, f_med, f_low],
        summary={},
    )

    # Min severity MEDIUM
    med_plus = report.filter_findings(min_severity=Severity.MEDIUM)
    assert len(med_plus) == 2
    assert f_low not in med_plus

    # Filter by category
    sec_only = report.filter_findings(category=FindingCategory.SECURITY)
    assert len(sec_only) == 1
    assert sec_only[0].type == "SEC-1"

    # Format CLI output
    cli_out = report.format_cli()
    assert "Codebase Analysis Report" in cli_out
    assert "Security Findings" in cli_out
    assert "Code Smells" in cli_out
    assert "Coding Patterns" in cli_out


def test_analysis_report_json():
    f = Finding(
        id="1", type="SEC-1", category=FindingCategory.SECURITY, severity=Severity.HIGH,
        confidence=Confidence.HIGH, title="Title", file="a.py", start_line=1, end_line=2,
        evidence="code", description="desc", rationale="rat", recommendation="rec"
    )
    report = AnalysisReport(
        repository="/test",
        files_analyzed=1,
        total_findings=1,
        findings=[f],
        summary={"total": 1},
    )
    json_str = report.to_json()
    assert "/test" in json_str
    assert "SEC-1" in json_str
