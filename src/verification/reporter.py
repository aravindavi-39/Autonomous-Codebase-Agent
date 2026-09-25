"""Rich formatting and presentation utilities for VerificationReport."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from verification.models import VerificationReport, VerificationVerdict


def format_verification_table(report: VerificationReport, console: Optional[Console] = None) -> None:
    """Format and display a Rich presentation table for a VerificationReport."""
    if not console:
        return

    verdict_colors = {
        VerificationVerdict.PASSED: "bold green",
        VerificationVerdict.FAILED: "bold red",
        VerificationVerdict.WARNING: "bold yellow",
        VerificationVerdict.SKIPPED: "cyan",
        VerificationVerdict.ERROR: "bold red",
    }
    color = verdict_colors.get(report.verdict, "white")

    console.print()
    console.print(
        Panel.fit(
            f"[{color}]VERDICT: {report.verdict.value}[/{color}] (Policy: {report.policy.mode.value})",
            title=f"Verification Report — {report.repository}",
            border_style=color,
        )
    )

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Verification Check", width=25)
    table.add_column("Status", width=20)
    table.add_column("Details", width=50)

    # 1. Target Finding Resolution
    if report.target_finding_id:
        if report.finding_delta and report.finding_delta.target_resolved:
            table.add_row(
                "Target Finding",
                "[green]RESOLVED[/green]",
                f"Finding '{report.target_finding_id}' successfully eliminated",
            )
        elif report.finding_delta and not report.finding_delta.target_resolved:
            table.add_row(
                "Target Finding",
                "[red]UNRESOLVED[/red]",
                f"Finding '{report.target_finding_id}' still present after refactoring",
            )
        else:
            table.add_row("Target Finding", "[yellow]NOT_EVALUATED[/yellow]", f"Target: {report.target_finding_id}")

    # 2. Findings Delta (New Findings)
    if report.finding_delta:
        fd = report.finding_delta
        if not fd.new_findings:
            table.add_row(
                "New Code Smells/Flaws",
                "[green]ZERO NEW[/green]",
                f"Clean: 0 new issues introduced ({len(fd.resolved_findings)} resolved, {len(fd.remaining_findings)} remaining)",
            )
        else:
            table.add_row(
                "New Code Smells/Flaws",
                f"[red]{len(fd.new_findings)} INTRODUCED[/red]",
                f"Regression: {len(fd.new_findings)} new issue(s) detected",
            )

    # 3. Unit Tests
    if report.test_skipped:
        table.add_row("Unit Tests", "[dim]SKIPPED[/dim]", "Test verification bypassed (--no-tests)")
    elif report.test_comparison:
        tc = report.test_comparison
        status_color = "green" if tc.regression_status.value == "PASS" else "red"
        table.add_row(
            "Unit Tests",
            f"[{status_color}]{tc.regression_status.value}[/{status_color}]",
            tc.summary,
        )
    elif report.test_run:
        status_color = "green" if report.test_run.status == "PASSED" else "yellow" if report.test_run.status == "NO_TESTS" else "red"
        table.add_row(
            "Unit Tests",
            f"[{status_color}]{report.test_run.status}[/{status_color}]",
            report.test_run.summary,
        )

    # 4. Lint and Syntax
    if report.lint_skipped:
        table.add_row("Lint & Syntax", "[dim]SKIPPED[/dim]", "Linting bypassed (--no-lint)")
    elif report.lint_run:
        lr = report.lint_run
        status_color = "green" if lr.status == "PASSED" else "yellow" if lr.status == "WARNING" else "red"
        table.add_row(
            "Lint & Syntax",
            f"[{status_color}]{lr.status}[/{status_color}]",
            lr.summary,
        )

    # 5. Original Repo Immutability
    imm_color = "green" if report.source_intact else "red"
    imm_text = "Verified SHA-256 match (byte-for-byte untouched)" if report.source_intact else "MODIFIED_ERROR"
    table.add_row("Repo Immutability", f"[{imm_color}]UNCHANGED[/{imm_color}]", imm_text)

    console.print(table)
    console.print()

    if report.messages:
        console.print("[bold]Observations:[/bold]")
        for msg in report.messages:
            console.print(f"  • {msg}")
        console.print()

    if report.errors:
        console.print("[bold red]Violations & Failures:[/bold red]")
        for err in report.errors:
            console.print(f"  [red][x][/red] {err}")
        console.print()

    if report.warnings:
        console.print("[bold yellow]Notices & Warnings:[/bold yellow]")
        for warn in report.warnings:
            console.print(f"  [yellow][!][/yellow] {warn}")
        console.print()
