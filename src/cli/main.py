"""CLI entry point for the Autonomous Codebase Agent.

Provides the main Typer application and top-level commands.
"""

import sys
from pathlib import Path
from typing import Optional

# Reconfigure Windows console streams to UTF-8 when supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config.settings import get_settings

app = typer.Typer(
    name="codebase-agent",
    help="Autonomous Codebase Understanding & Refactor Agent",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit."
    ),
) -> None:
    """Autonomous Codebase Understanding & Refactor Agent."""
    settings = get_settings()

    if version or ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                f"[bold cyan]{settings.app_name}[/bold cyan]\n"
                f"Version: [green]{settings.app_version}[/green]",
                border_style="blue",
            )
        )
        if ctx.invoked_subcommand is None and not version:
            console.print(
                "\n[dim]Run [bold]codebase-agent --help[/bold] for available commands.[/dim]"
            )


# ---------------------------------------------------------------------------
# load command — Repository ingestion
# ---------------------------------------------------------------------------


@app.command()
def load(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    export_json: Optional[str] = typer.Option(
        None,
        "--export-json",
        "-e",
        help="Export the repository manifest to a JSON file.",
    ),
) -> None:
    """Load and index a local repository."""
    from ingestion.pipeline import IngestionPipeline
    from ingestion.validator import ValidationError

    try:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    stats = manifest.statistics

    # --- Header ---
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Repository:[/bold green] {manifest.name}\n"
            f"[bold green]Status:[/bold green] Successfully indexed",
            border_style="green",
        )
    )
    console.print()

    # --- Summary ---
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Label", style="bold")
    summary_table.add_column("Value", justify="right")
    summary_table.add_row("Files", f"{stats.total_files:,}")
    summary_table.add_row("Directories", f"{stats.total_directories:,}")
    summary_table.add_row("Lines", f"{stats.total_lines:,}")
    console.print(summary_table)
    console.print()

    # --- Languages ---
    if stats.files_by_language:
        lang_table = Table(title="Languages", show_header=True, header_style="bold cyan")
        lang_table.add_column("Language")
        lang_table.add_column("Files", justify="right")
        for lang, count in stats.files_by_language.items():
            lang_table.add_row(lang, str(count))
        console.print(lang_table)
        console.print()

    # --- Classifications ---
    class_table = Table(show_header=False, box=None, padding=(0, 2))
    class_table.add_column("Label", style="bold")
    class_table.add_column("Value", justify="right")
    class_table.add_row("Tests", str(len(stats.test_files)))
    class_table.add_row("Documentation", str(len(stats.documentation_files)))
    class_table.add_row("Configuration", str(len(stats.configuration_files)))
    console.print(class_table)
    console.print()

    # --- JSON export ---
    if export_json:
        try:
            pipeline.export_json(export_json)
            console.print(
                f"[bold green]Manifest exported to:[/bold green] {export_json}"
            )
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")
            raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Placeholder commands — will be implemented in later phases
# ---------------------------------------------------------------------------


@app.command()
def ask(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    question: str = typer.Argument(
        ..., help="Question about the codebase."
    ),
    top_k: int = typer.Option(
        5, "--top-k", "-k", help="Number of semantic chunks to retrieve."
    ),
    max_context: int = typer.Option(
        12000, "--max-context", help="Maximum context characters to send to LLM."
    ),
    no_semantic: bool = typer.Option(
        False, "--no-semantic", help="Disable semantic vector search."
    ),
    no_graph: bool = typer.Option(
        False, "--no-graph", help="Disable structural CodeGraph traversal."
    ),
    mock: bool = typer.Option(
        False, "--mock", help="Run in offline mock mode using FakeLLMProvider."
    ),
) -> None:
    """Ask a natural-language question about the repository with grounded citations."""
    from pathlib import Path
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.graph_builder import CodeGraphBuilder
    from citations.validator import CitationValidator
    from ingestion.pipeline import IngestionPipeline
    from ingestion.validator import ValidationError
    from llm.base import LLMConfigurationError, LLMError
    from llm.fake_provider import FakeLLMProvider
    from llm.openai_provider import OpenAIProvider
    from retrieval.chunker import SemanticChunker
    from retrieval.context_builder import ContextBuilder
    from retrieval.qa_engine import QAEngine
    from retrieval.retriever import HybridRetriever
    from retrieval.vector_store import LocalVectorStore, create_vector_store

    # 1. Validation and Ingestion
    try:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Ingestion error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 2. AST Code Indexing
    try:
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(source, manifest=manifest)
    except Exception as exc:
        console.print(f"[bold red]Analysis error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 3. CodeGraph Building
    try:
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(code_index)
    except Exception as exc:
        console.print(f"[bold red]Graph building error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 4. LLM Provider setup
    if mock:
        provider = FakeLLMProvider()
    else:
        try:
            provider = OpenAIProvider()
            # Test key presence early
            provider._get_client()
        except LLMConfigurationError as exc:
            console.print(f"[bold red]Configuration error:[/bold red] {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            console.print(f"[bold red]LLM provider error:[/bold red] {exc}")
            raise typer.Exit(code=1)

    # 5. Semantic Chunking & Vector Indexing
    try:
        root_path = Path(manifest.root_path)
        chunker = SemanticChunker(root_path=root_path)
        chunks = chunker.chunk_repository(manifest=manifest, code_index=code_index)

        vector_store = create_vector_store()
        if not no_semantic:
            vector_store.index(chunks, provider=provider)
    except Exception as exc:
        console.print(f"[bold red]Vector store indexing error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 6. Hybrid Retrieval and Question Answering
    try:
        citation_validator = CitationValidator(manifest=manifest, code_index=code_index)
        retriever = HybridRetriever(
            vector_store=vector_store,
            code_graph=code_graph,
            code_index=code_index,
        )
        context_builder = ContextBuilder(
            max_chunks=top_k,
            max_context_chars=max_context,
        )
        qa_engine = QAEngine(
            retriever=retriever,
            llm_provider=provider,
            citation_validator=citation_validator,
            context_builder=context_builder,
        )

        response = qa_engine.ask(
            question=question,
            top_k=top_k,
            max_context_chars=max_context,
            enable_semantic=not no_semantic,
            enable_graph=not no_graph,
        )
    except LLMError as exc:
        console.print(f"[bold red]Generation error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Unexpected error during Q&A:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 7. Display Results
    console.print()
    console.print(f"[bold cyan]Question:[/bold cyan]\n{response.question}\n")
    console.print(f"[bold green]Answer:[/bold green]\n\n{response.clean_answer_text()}\n")

    console.print("[bold cyan]Sources:[/bold cyan]")
    if response.citations:
        prefix = "📄"
        try:
            "📄".encode(sys.stdout.encoding or "utf-8")
        except Exception:
            prefix = "-"
        for c in response.citations:
            console.print(f"[dim]{prefix}[/dim] [yellow]{c.to_compact_str()}[/yellow]" + (f" ({c.entity})" if c.entity else ""))
    else:
        console.print("[dim]None[/dim]")
    console.print()


@app.command()
def analyze(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    export_json: Optional[str] = typer.Option(
        None,
        "--export-json",
        "-e",
        help="Export the repository analysis report and code index to a JSON file.",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        "-s",
        help="Filter findings by minimum severity: info, low, medium, high, critical.",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter findings by category: security, smell, pattern.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output findings report as JSON to stdout.",
    ),
    no_security: bool = typer.Option(
        False,
        "--no-security",
        help="Disable security analysis rules.",
    ),
    no_smells: bool = typer.Option(
        False,
        "--no-smells",
        help="Disable code smell analysis rules.",
    ),
    no_patterns: bool = typer.Option(
        False,
        "--no-patterns",
        help="Disable coding pattern analysis rules.",
    ),
) -> None:
    """Analyze Python source files, build a code index, and detect code smells and security risks."""
    import json
    from pathlib import Path
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.findings.engine import AnalysisEngine
    from analysis.findings.models import FindingCategory, Severity
    from analysis.graph_builder import CodeGraphBuilder
    from ingestion.validator import ValidationError

    try:
        analyzer = RepositoryAnalyzer()
        index = analyzer.analyze_repository(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    summary = index.summary
    manifest = index.manifest

    # Parse filter options
    parsed_sev: Optional[Severity] = None
    if severity:
        try:
            parsed_sev = Severity.from_str(severity)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1)

    parsed_cat: Optional[FindingCategory] = None
    if category:
        try:
            parsed_cat = FindingCategory.from_str(category)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1)

    # Build CodeGraph for graph-based smell detection
    try:
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(index)
    except Exception:
        code_graph = None

    # Run AnalysisEngine
    try:
        engine = AnalysisEngine()
        findings_report = engine.analyze(
            manifest=manifest,
            code_index=index,
            code_graph=code_graph,
            enable_security=not no_security,
            enable_smells=not no_smells,
            enable_patterns=not no_patterns,
            min_severity=parsed_sev,
            category=parsed_cat,
        )
    except Exception as exc:
        console.print(f"[bold red]Analysis engine error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if json_output:
        print(findings_report.to_json())
        return

    # Print AST Code Index Metrics
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Repository:[/bold green] {manifest.name}",
            border_style="green",
        )
    )
    console.print()

    metrics_table = Table(show_header=False, box=None, padding=(0, 2))
    metrics_table.add_column("Metric", style="bold")
    metrics_table.add_column("Value", justify="right")
    metrics_table.add_row("Python Files", str(summary.python_files_analyzed))
    metrics_table.add_row("Classes", str(summary.total_classes))
    metrics_table.add_row("Functions", str(summary.total_functions))
    metrics_table.add_row("Methods", str(summary.total_methods))
    metrics_table.add_row("Imports", str(summary.total_imports))
    metrics_table.add_row("Calls", str(summary.total_calls))
    console.print(metrics_table)
    console.print()

    classes = index.get_classes()
    if classes:
        console.print("[bold cyan]Classes:[/bold cyan]")
        for c in classes:
            console.print(f"- [green]{c.name}[/green]")
        console.print()

    functions = index.get_functions(include_methods=False)
    if functions:
        console.print("[bold cyan]Functions:[/bold cyan]")
        for f in functions:
            console.print(f"- [yellow]{f.name}()[/yellow]")
        console.print()

    # Print Findings Report
    console.print(findings_report.format_cli(min_severity=parsed_sev, category=parsed_cat))

    if export_json:
        try:
            combined_data = index.model_dump(mode="json")
            combined_data["findings_report"] = findings_report.model_dump(mode="json")
            combined_data["findings"] = [f.model_dump(mode="json") for f in findings_report.findings]
            out_p = Path(export_json)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(combined_data, indent=2), encoding="utf-8")
            console.print(
                f"[bold green]Analysis exported to:[/bold green] {export_json}"
            )
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")
            raise typer.Exit(code=1)


@app.command()
def graph(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    export_json: Optional[str] = typer.Option(
        None,
        "--export-json",
        "-e",
        help="Export the codebase graph to a JSON file.",
    ),
) -> None:
    """Analyze repository relationships, build CodeGraph, and detect dependency cycles."""
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.graph_builder import CodeGraphBuilder
    from ingestion.validator import ValidationError

    try:
        analyzer = RepositoryAnalyzer()
        index = analyzer.analyze_repository(source)
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(index)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    stats = code_graph.statistics
    manifest = index.manifest

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Repository:[/bold green] {manifest.name}",
            border_style="green",
        )
    )
    console.print()

    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")
    summary_table.add_row("Nodes", str(stats.total_nodes))
    summary_table.add_row("Edges", str(stats.total_edges))
    console.print(summary_table)
    console.print()

    if stats.relationships_by_type:
        console.print("[bold cyan]Relationships:[/bold cyan]")
        console.print()
        rel_table = Table(show_header=False, box=None, padding=(0, 2))
        rel_table.add_column("Type", style="bold")
        rel_table.add_column("Count", justify="right")
        for rel_name in ["IMPORTS", "DEFINES", "CALLS", "INHERITS", "CONTAINS", "TESTS", "DEPENDS_ON"]:
            if rel_name in stats.relationships_by_type:
                rel_table.add_row(rel_name, str(stats.relationships_by_type[rel_name]))
        for rel_name, count in stats.relationships_by_type.items():
            if rel_name not in ["IMPORTS", "DEFINES", "CALLS", "INHERITS", "CONTAINS", "TESTS", "DEPENDS_ON"]:
                rel_table.add_row(rel_name, str(count))
        console.print(rel_table)
        console.print()

    console.print("[bold cyan]Dependency hotspots:[/bold cyan]")
    console.print()
    if stats.most_depended_on_modules:
        for idx, (mod, count) in enumerate(stats.most_depended_on_modules[:5], 1):
            console.print(f"{idx}. [yellow]{mod}[/yellow]")
    else:
        console.print("[dim]None[/dim]")
    console.print()

    console.print("[bold cyan]Circular dependencies:[/bold cyan]")
    if stats.circular_dependencies:
        for idx, cycle in enumerate(stats.circular_dependencies, 1):
            console.print(f"[bold red]{idx}. {cycle.cycle_str}[/bold red]")
    else:
        console.print("[green]None[/green]")
    console.print()

    if export_json:
        try:
            code_graph.export_json(export_json)
            console.print(
                f"[bold green]Graph exported to:[/bold green] {export_json}"
            )
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")
            raise typer.Exit(code=1)


@app.command()
def plan(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    finding: Optional[str] = typer.Option(
        None,
        "--finding",
        "-f",
        help="Filter plan to a specific finding ID.",
    ),
    safe_only: bool = typer.Option(
        False,
        "--safe-only",
        help="Only include SAFE_AUTOMATIC_PROPOSAL actions.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Export the refactoring plan to a JSON file.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output plan as JSON to stdout.",
    ),
) -> None:
    """Generate a refactoring plan from analysis findings."""
    from pathlib import Path
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.findings.context import AnalysisContext
    from analysis.findings.engine import AnalysisEngine
    from analysis.graph_builder import CodeGraphBuilder
    from ingestion.pipeline import IngestionPipeline
    from ingestion.validator import ValidationError
    from refactoring.planner import RefactoringPlanner
    from refactoring.preview import format_plan_table

    # 1. Ingest
    try:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Ingestion error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 2. AST Analysis
    try:
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(source, manifest=manifest)
    except Exception as exc:
        console.print(f"[bold red]Analysis error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 3. CodeGraph
    try:
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(code_index)
    except Exception:
        code_graph = None

    # 4. Run AnalysisEngine
    try:
        engine = AnalysisEngine()
        report = engine.analyze(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
    except Exception as exc:
        console.print(f"[bold red]Analysis engine error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 5. Build context and generate plan
    try:
        context = AnalysisContext(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
        planner = RefactoringPlanner()
        ref_plan = planner.plan(
            report=report,
            context=context,
            finding_id=finding,
            safe_only=safe_only,
        )
    except Exception as exc:
        console.print(f"[bold red]Planning error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 6. Output
    if json_output:
        print(ref_plan.to_json())
        return

    if not ref_plan.actions:
        console.print("[yellow]No refactoring actions found for the given criteria.[/yellow]")
        return

    format_plan_table(ref_plan, console=console)

    if output:
        try:
            import json
            out_p = Path(output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(ref_plan.to_json(), encoding="utf-8")
            console.print(f"[bold green]Plan exported to:[/bold green] {output}")
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")
            raise typer.Exit(code=1)


@app.command()
def diff(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    finding: Optional[str] = typer.Option(
        None,
        "--finding",
        "-f",
        help="Generate diff for a specific finding ID only.",
    ),
    safe_only: bool = typer.Option(
        False,
        "--safe-only",
        help="Only generate diffs for SAFE_AUTOMATIC_PROPOSAL actions.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save unified diffs to a file.",
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate generated diffs against temporary copies.",
    ),
) -> None:
    """Generate unified diffs for proposed refactoring changes."""
    from pathlib import Path
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.findings.context import AnalysisContext
    from analysis.findings.engine import AnalysisEngine
    from analysis.graph_builder import CodeGraphBuilder
    from ingestion.pipeline import IngestionPipeline
    from ingestion.validator import ValidationError
    from refactoring.generator import DiffGenerator
    from refactoring.models import SafetyClassification
    from refactoring.planner import RefactoringPlanner
    from refactoring.preview import format_diff_output, format_validation_result
    from refactoring.validator import DiffValidator

    # 1. Ingest
    try:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Ingestion error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 2. AST Analysis
    try:
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(source, manifest=manifest)
    except Exception as exc:
        console.print(f"[bold red]Analysis error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 3. CodeGraph
    try:
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(code_index)
    except Exception:
        code_graph = None

    # 4. Run AnalysisEngine
    try:
        engine = AnalysisEngine()
        report = engine.analyze(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
    except Exception as exc:
        console.print(f"[bold red]Analysis engine error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 5. Build context and generate plan
    try:
        context = AnalysisContext(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
        planner = RefactoringPlanner()
        ref_plan = planner.plan(
            report=report,
            context=context,
            finding_id=finding,
            safe_only=safe_only,
        )
    except Exception as exc:
        console.print(f"[bold red]Planning error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 6. Generate diffs
    generator = DiffGenerator()
    validator = DiffValidator()
    all_diffs: list = []
    root_path = Path(manifest.root_path)

    actionable = [
        a for a in ref_plan.actions
        if a.proposal.file_changes
    ]

    if not actionable:
        console.print("[yellow]No actionable diffs to generate for the given criteria.[/yellow]")
        return

    for action in actionable:
        try:
            diff_results = generator.generate(action.proposal, context)
            if diff_results:
                all_diffs.extend(diff_results)

                # Validate if requested
                if validate:
                    validation = validator.validate(
                        action.proposal, diff_results, root_path
                    )
                    format_validation_result(validation, console=console)
        except Exception as exc:
            console.print(
                f"[bold red]Diff generation error for {action.finding.id}:[/bold red] {exc}"
            )

    # 7. Display diffs
    if all_diffs:
        format_diff_output(all_diffs, console=console)

    if output and all_diffs:
        try:
            out_p = Path(output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            diff_text = "\n".join(d.unified_diff for d in all_diffs)
            out_p.write_text(diff_text, encoding="utf-8")
            console.print(f"[bold green]Diffs exported to:[/bold green] {output}")
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")
            raise typer.Exit(code=1)


@app.command()
def apply(
    source: str = typer.Argument(
        ..., help="Local path to a repository."
    ),
    finding: str = typer.Option(
        ...,
        "--finding",
        "-f",
        help="Finding ID to apply and verify in sandbox.",
    ),
    approve: bool = typer.Option(
        False,
        "--approve",
        help="Explicit approval signal required to create sandbox and apply patch.",
    ),
    safe_only: bool = typer.Option(
        True,
        "--safe-only",
        help="Enforce that only SAFE_AUTOMATIC_PROPOSAL findings are eligible.",
    ),
    no_tests: bool = typer.Option(
        False,
        "--no-tests",
        help="Skip test execution inside the sandbox.",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Timeout in seconds for test execution inside sandbox.",
    ),
    keep_sandbox: bool = typer.Option(
        False,
        "--keep-sandbox",
        help="Retain the sandbox directory for manual inspection instead of deleting it.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output report as structured JSON.",
    ),
) -> None:
    """Safely apply a proposed refactoring patch inside an isolated sandbox copy and verify tests."""
    from pathlib import Path
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.findings.context import AnalysisContext
    from analysis.findings.engine import AnalysisEngine
    from analysis.graph_builder import CodeGraphBuilder
    from ingestion.pipeline import IngestionPipeline
    from ingestion.validator import ValidationError
    from refactoring.models import SafetyClassification
    from refactoring.planner import RefactoringPlanner
    from sandbox.manager import SandboxManager
    from sandbox.models import ApprovalStatus, SandboxReport, SandboxSession, SandboxStatus

    # 1. Approval Gate Check (Fail early before any disk operations)
    if not approve:
        error_msg = "Explicit approval is required before applying this proposal to a sandbox."
        if json_output:
            empty_session = SandboxSession(
                id="unapproved",
                source_repository=str(Path(source).resolve()),
                source_fingerprint_before="",
                source_fingerprint_after="",
                sandbox_path="",
                status=SandboxStatus.ERROR,
                approval_status=ApprovalStatus.REJECTED,
                created_at="",
                finding_id=finding,
                proposal_id=finding,
                cleaned_up=True,
                errors=[error_msg],
            )
            print(SandboxReport(session=empty_session).to_json())
        else:
            console.print(f"[bold red]Approval Error:[/bold red] {error_msg}")
            console.print("[dim]Re-run with [bold]--approve[/bold] to proceed with isolated sandbox verification.[/dim]")
        raise typer.Exit(code=1)

    # 2. Ingest
    try:
        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(source)
    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Ingestion error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 3. AST Analysis
    try:
        analyzer = RepositoryAnalyzer()
        code_index = analyzer.analyze_repository(source, manifest=manifest)
    except Exception as exc:
        console.print(f"[bold red]Analysis error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 4. CodeGraph
    try:
        builder = CodeGraphBuilder()
        code_graph = builder.build_graph(code_index)
    except Exception:
        code_graph = None

    # 5. Run AnalysisEngine
    try:
        engine = AnalysisEngine()
        report = engine.analyze(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
    except Exception as exc:
        console.print(f"[bold red]Analysis engine error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 6. Plan and locate targeted proposal
    try:
        context = AnalysisContext(
            manifest=manifest,
            code_index=code_index,
            code_graph=code_graph,
        )
        planner = RefactoringPlanner()
        ref_plan = planner.plan(
            report=report,
            context=context,
            finding_id=finding,
            safe_only=False,
        )
    except Exception as exc:
        console.print(f"[bold red]Planning error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if not ref_plan.actions:
        console.print(f"[bold red]Error:[/bold red] Finding '{finding}' was not found or has no refactoring strategy.")
        raise typer.Exit(code=1)

    action = ref_plan.actions[0]
    proposal = action.proposal

    # 7. Safety Classification Gate
    if safe_only and proposal.safety != SafetyClassification.SAFE_AUTOMATIC_PROPOSAL:
        error_msg = (
            f"Proposal '{finding}' has safety tier '{proposal.safety.value}'. "
            "Only 'SAFE_AUTOMATIC_PROPOSAL' can be applied to a sandbox."
        )
        if json_output:
            empty_session = SandboxSession(
                id="unsafe",
                source_repository=str(Path(source).resolve()),
                source_fingerprint_before="",
                source_fingerprint_after="",
                sandbox_path="",
                status=SandboxStatus.ERROR,
                approval_status=ApprovalStatus.APPROVED,
                created_at="",
                finding_id=finding,
                proposal_id=finding,
                safety_classification=proposal.safety.value,
                cleaned_up=True,
                errors=[error_msg],
            )
            print(SandboxReport(session=empty_session).to_json())
        else:
            console.print(f"[bold red]Safety Error:[/bold red] {error_msg}")
        raise typer.Exit(code=1)

    # 8. Execute Sandbox Session via SandboxManager
    try:
        manager = SandboxManager()
        sandbox_report = manager.execute_session(
            source_path=Path(manifest.root_path),
            proposal=proposal,
            approved=approve,
            run_tests=not no_tests,
            keep_sandbox=keep_sandbox,
            timeout_seconds=timeout,
            baseline_findings=report.findings,
            audit_verification=True,
        )
    except Exception as exc:
        console.print(f"[bold red]Sandbox manager error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 9. Output Report
    if json_output:
        print(sandbox_report.to_json())
    else:
        console.print()
        console.print(sandbox_report.format_cli())

    if sandbox_report.session.status not in (SandboxStatus.PASSED, SandboxStatus.CLEANED):
        raise typer.Exit(code=1)


@app.command()
def verify(
    source: str = typer.Argument(
        ..., help="Local path to a repository or sandbox copy to verify."
    ),
    finding: Optional[str] = typer.Option(
        None,
        "--finding",
        "-f",
        help="Optional target finding ID to audit for resolution.",
    ),
    policy: str = typer.Option(
        "strict",
        "--policy",
        "-p",
        help="Verification policy: 'strict' (default) or 'lenient'.",
    ),
    no_tests: bool = typer.Option(
        False,
        "--no-tests",
        help="Skip test execution.",
    ),
    no_lint: bool = typer.Option(
        False,
        "--no-lint",
        help="Skip lint and syntax checking.",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Test runner timeout in seconds.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to export verification report JSON.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output verification report as JSON to stdout.",
    ),
) -> None:
    """Verify code health, test suites, syntax/lint standards, and finding resolution without modifying the repository."""
    from pathlib import Path
    from verification.engine import VerificationEngine
    from verification.models import VerificationPolicy, VerificationVerdict
    from verification.reporter import format_verification_table

    repo_path = Path(source)
    if not repo_path.exists() or not repo_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Path does not exist or is not a directory: {source}")
        raise typer.Exit(code=1)

    policy_obj = (
        VerificationPolicy.strict()
        if policy.lower() == "strict"
        else VerificationPolicy.lenient()
    )

    try:
        engine = VerificationEngine()
        report = engine.verify_repository(
            repo_path=repo_path,
            target_finding_id=finding,
            policy=policy_obj,
            run_tests=not no_tests,
            run_lint=not no_lint,
            timeout_seconds=timeout,
        )
    except Exception as exc:
        console.print(f"[bold red]Verification error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if output:
        try:
            out_p = Path(output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(report.to_json(), encoding="utf-8")
            console.print(f"[bold green]Report exported to:[/bold green] {output}")
        except Exception as exc:
            console.print(f"[bold red]Export error:[/bold red] {exc}")

    if json_output:
        print(report.to_json())
    else:
        format_verification_table(report, console=console)

    if report.verdict == VerificationVerdict.FAILED:
        raise typer.Exit(code=1)


def cli_entry() -> None:
    """Entry point wrapper for console_scripts."""
    app()


if __name__ == "__main__":
    cli_entry()
