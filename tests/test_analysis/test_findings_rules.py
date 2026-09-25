"""Tests for individual smell, security, and pattern rules."""

from pathlib import Path
import pytest

from ingestion.pipeline import IngestionPipeline
from analysis.analyzer import RepositoryAnalyzer
from analysis.graph_builder import CodeGraphBuilder
from analysis.findings.context import AnalysisContext

from analysis.findings.smell_rules.function_smells import (
    LongFunctionRule,
    HighParameterCountRule,
    DeepNestingRule,
    TooManyBranchesRule,
    MissingDocstringRule,
)
from analysis.findings.smell_rules.class_smells import LargeClassRule
from analysis.findings.smell_rules.graph_smells import (
    DeadFunctionRule,
    CircularDependencyRule,
    ExcessiveDependenciesRule,
)
from analysis.findings.smell_rules.duplication_smells import DuplicateLogicRule

from analysis.findings.security_rules.secrets_rule import HardcodedSecretRule
from analysis.findings.security_rules.execution_rule import DangerousExecutionRule
from analysis.findings.security_rules.injection_rule import (
    UnsafeSubprocessRule,
    SqlInjectionRule,
    CommandInjectionRule,
    PathTraversalRule,
)
from analysis.findings.security_rules.deserialization_rule import UnsafeDeserializationRule
from analysis.findings.security_rules.crypto_rule import WeakCryptoRule
from analysis.findings.security_rules.config_rule import InsecureTlsRule, DebugSettingsRule

from analysis.findings.pattern_rules.exception_rules import BroadExceptRule
from analysis.findings.pattern_rules.import_rules import WildcardImportRule, UnusedImportRule
from analysis.findings.pattern_rules.syntax_rules import (
    MutableDefaultRule,
    ShadowingBuiltinRule,
    UnreachableCodeRule,
)


@pytest.fixture(scope="module")
def vulnerable_context():
    repo_path = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(repo_path))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(repo_path))
    builder = CodeGraphBuilder()
    graph = builder.build_graph(code_index)
    return AnalysisContext(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
    )


# ---------------------------------------------------------
# SMELL RULES TESTS
# ---------------------------------------------------------

def test_long_function_rule(vulnerable_context):
    rule = LongFunctionRule(max_lines=30)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-001"]
    assert any("long_and_complex_function" in (f.entity or "") for f in rule_findings)
    assert not any("clean.py" in f.file for f in rule_findings)


def test_high_parameter_count_rule(vulnerable_context):
    rule = HighParameterCountRule(max_params=5)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-002"]
    assert any("long_and_complex_function" in (f.entity or "") for f in rule_findings)
    assert not any("clean.py" in f.file for f in rule_findings)


def test_deep_nesting_rule(vulnerable_context):
    rule = DeepNestingRule(max_depth=3)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-003"]
    assert any("long_and_complex_function" in (f.entity or "") for f in rule_findings)
    assert not any("clean.py" in f.file for f in rule_findings)


def test_too_many_branches_rule(vulnerable_context):
    rule = TooManyBranchesRule(max_branches=3)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-004"]
    assert any("long_and_complex_function" in (f.entity or "") for f in rule_findings)
    assert not any("clean.py" in f.file for f in rule_findings)


def test_large_class_rule(vulnerable_context):
    rule = LargeClassRule(max_methods=8, max_lines=40)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-005"]
    assert any("GodClass" in (f.entity or "") for f in rule_findings)
    assert not any("clean.py" in f.file for f in rule_findings)


def test_dead_function_rule(vulnerable_context):
    rule = DeadFunctionRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-006"]
    assert any("unused_dead_function" in (f.entity or "") for f in rule_findings)
    assert any(f.confidence.value == "LOW" for f in rule_findings)


def test_missing_docstring_rule(vulnerable_context):
    rule = MissingDocstringRule(min_lines=2)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-009"]
    assert len(rule_findings) > 0


def test_duplicate_logic_rule(vulnerable_context):
    rule = DuplicateLogicRule(min_statements=3)
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SMELL-010"]
    assert len(rule_findings) >= 1
    assert any("duplicate_task" in (f.entity or "") for f in rule_findings)


# ---------------------------------------------------------
# SECURITY RULES TESTS
# ---------------------------------------------------------

def test_hardcoded_secret_rule(vulnerable_context):
    rule = HardcodedSecretRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-001"]
    assert len(rule_findings) >= 1
    # Ensure evidence is redacted
    for f in rule_findings:
        evidence = f.evidence or ""
        assert "[REDACTED" in evidence or "[REDACTED" in f.description
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB" not in evidence
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB" not in f.description


def test_dangerous_execution_rule(vulnerable_context):
    rule = DangerousExecutionRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-002"]
    assert any("eval" in (f.evidence or "") for f in rule_findings)
    assert any("exec" in (f.evidence or "") for f in rule_findings)


def test_unsafe_subprocess_rule(vulnerable_context):
    rule = UnsafeSubprocessRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-003"]
    assert any("shell=True" in (f.evidence or "") for f in rule_findings)


def test_unsafe_deserialization_rule(vulnerable_context):
    rule = UnsafeDeserializationRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-004"]
    assert any("pickle.loads" in (f.evidence or "") for f in rule_findings)


def test_sql_injection_rule(vulnerable_context):
    rule = SqlInjectionRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-005"]
    assert len(rule_findings) >= 1
    assert any("execute" in (f.entity or "") or "SELECT" in (f.evidence or "") for f in rule_findings)


def test_command_injection_rule(vulnerable_context):
    rule = CommandInjectionRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-006"]
    assert any("os.system" in (f.evidence or "") for f in rule_findings)


def test_path_traversal_rule(vulnerable_context):
    rule = PathTraversalRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-007"]
    assert any("open" in (f.evidence or "") for f in rule_findings)


def test_weak_crypto_rule(vulnerable_context):
    rule = WeakCryptoRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-008"]
    assert any("hashlib.md5" in (f.evidence or "") for f in rule_findings)
    assert any("hashlib.sha1" in (f.evidence or "") for f in rule_findings)


def test_insecure_tls_rule(vulnerable_context):
    rule = InsecureTlsRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-009"]
    assert any("verify=False" in (f.evidence or "") for f in rule_findings)


def test_debug_settings_rule(vulnerable_context):
    rule = DebugSettingsRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "SEC-010"]
    assert any("DEBUG" in (f.evidence or "") or "debug" in (f.evidence or "") for f in rule_findings)


# ---------------------------------------------------------
# PATTERN RULES TESTS
# ---------------------------------------------------------

def test_broad_except_rule(vulnerable_context):
    rule = BroadExceptRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-001"]
    assert len(rule_findings) >= 2  # bare except and except Exception: pass
    assert any("bare 'except:'" in f.title or "bare 'except:'" in f.description for f in rule_findings)


def test_wildcard_import_rule(vulnerable_context):
    rule = WildcardImportRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-002"]
    assert any("import *" in (f.evidence or "") for f in rule_findings)


def test_mutable_default_rule(vulnerable_context):
    rule = MutableDefaultRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-003"]
    assert any("items: list = []" in (f.evidence or "") or "items=[]" in (f.evidence or "") for f in rule_findings)


def test_shadowing_builtin_rule(vulnerable_context):
    rule = ShadowingBuiltinRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-004"]
    assert any("id" in (f.evidence or "") or "type" in (f.evidence or "") for f in rule_findings)


def test_unused_import_rule(vulnerable_context):
    rule = UnusedImportRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-005"]
    assert any("sys" in (f.evidence or "") or "sys" in (f.entity or "") for f in rule_findings)


def test_unreachable_code_rule(vulnerable_context):
    rule = UnreachableCodeRule()
    findings = rule.check(vulnerable_context)
    rule_findings = [f for f in findings if f.type == "PAT-006"]
    assert any("after return" in (f.evidence or "") or "unreachable" in f.title.lower() for f in rule_findings)


# ---------------------------------------------------------
# CLEAN REPO CONTROLS
# ---------------------------------------------------------

def test_clean_file_produces_no_critical_or_high_findings(vulnerable_context):
    """Verify that clean.py does not trigger critical or high security/smell findings."""
    rules = [
        DangerousExecutionRule(),
        UnsafeSubprocessRule(),
        UnsafeDeserializationRule(),
        SqlInjectionRule(),
        CommandInjectionRule(),
        InsecureTlsRule(),
        DebugSettingsRule(),
        MutableDefaultRule(),
        WildcardImportRule(),
        UnreachableCodeRule(),
    ]
    for rule in rules:
        findings = rule.check(vulnerable_context)
        clean_findings = [f for f in findings if "clean.py" in f.file]
        assert len(clean_findings) == 0, f"Rule {rule.rule_id} triggered unexpectedly on clean.py: {clean_findings}"
