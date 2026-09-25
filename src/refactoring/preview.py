"""Rich terminal preview for refactoring plans and unified diffs."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from refactoring.models import (
    DiffResult,
    RefactoringAction,
    RefactoringPlan,
    SafetyClassification,
    ValidationResult,
)


# Safety classification colors
_SAFETY_COLORS = {
    SafetyClassification.SAFE_AUTOMATIC_PROPOSAL: "green",
    SafetyClassification.REVIEW_REQUIRED: "yellow",
    SafetyClassification.UNSUPPORTED: "red",
}

_SAFETY_ICONS = {
    SafetyClassification.SAFE_AUTOMATIC_PROPOSAL: "✅",
    SafetyClassification.REVIEW_REQUIRED: "⚠️",
    SafetyClassification.UNSUPPORTED: "❌",
}


def format_plan_table(plan: RefactoringPlan, console: Optional[Console] = None) -> str:
    """Format a RefactoringPlan as a Rich table and return as string.

    Also prints to the console if provided.
    """
    table = Table(
        title=f"Refactoring Plan: {plan.repository}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", width=4)
    table.add_column("Safety", width=12)
    table.add_column("Finding", width=14)
    table.add_column("File", width=30)
    table.add_column("Lines", width=10, justify="right")
    table.add_column("Strategy", width=25)
    table.add_column("Description", width=50)

    for idx, action in enumerate(plan.actions, 1):
        safety = action.proposal.safety
        color = _SAFETY_COLORS.get(safety, "white")
        icon = _SAFETY_ICONS.get(safety, "")

        table.add_row(
            str(idx),
            f"[{color}]{icon} {safety.value}[/{color}]",
            action.finding.id,
            action.finding.file,
            f"{action.finding.start_line}-{action.finding.end_line}",
            action.proposal.strategy,
            action.proposal.description[:80],
        )

    if console:
        console.print()
        console.print(table)
        console.print()

        # Print summary
        summary = plan.summary
        console.print(f"[bold]Total actions:[/bold] {summary.get('total_actions', 0)}")
        console.print(f"[green]Safe automatic:[/green] {summary.get('safe_automatic', 0)}")
        console.print(f"[yellow]Review required:[/yellow] {summary.get('review_required', 0)}")
        console.print(f"[red]Unsupported:[/red] {summary.get('unsupported', 0)}")
        console.print()

    # Return a plain-text version
    lines = [
        f"Refactoring Plan: {plan.repository}",
        "=" * 60,
        "",
    ]
    for idx, action in enumerate(plan.actions, 1):
        safety = action.proposal.safety.value
        lines.append(f"{idx}. [{safety}] {action.finding.id}")
        lines.append(f"   File: {action.finding.file}:{action.finding.start_line}-{action.finding.end_line}")
        lines.append(f"   Strategy: {action.proposal.strategy}")
        lines.append(f"   {action.proposal.description}")
        if action.risk_notes:
            lines.append(f"   Risk: {action.risk_notes}")
        lines.append("")

    lines.append(f"Total: {plan.summary.get('total_actions', 0)} actions")
    lines.append(f"Safe: {plan.summary.get('safe_automatic', 0)} | "
                 f"Review: {plan.summary.get('review_required', 0)} | "
                 f"Unsupported: {plan.summary.get('unsupported', 0)}")

    return "\n".join(lines)


def format_diff_output(
    diff_results: list[DiffResult],
    console: Optional[Console] = None,
) -> str:
    """Format unified diffs for terminal display.

    Returns the diff text and optionally prints colorized output.
    """
    parts: list[str] = []

    for diff_result in diff_results:
        parts.append(diff_result.unified_diff)

        if console:
            console.print(
                Panel.fit(
                    f"[bold]{diff_result.file_path}[/bold]",
                    border_style="cyan",
                )
            )
            # Print colorized diff
            for line in diff_result.unified_diff.splitlines():
                if line.startswith("+++"):
                    console.print(f"[bold green]{line}[/bold green]")
                elif line.startswith("---"):
                    console.print(f"[bold red]{line}[/bold red]")
                elif line.startswith("+"):
                    console.print(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    console.print(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    console.print(f"[cyan]{line}[/cyan]")
                else:
                    console.print(line)
            console.print()

    return "\n".join(parts)


def format_validation_result(
    result: ValidationResult,
    console: Optional[Console] = None,
) -> str:
    """Format a ValidationResult for terminal display."""
    lines: list[str] = []

    if result.valid:
        lines.append("✅ Validation PASSED")
    else:
        lines.append("❌ Validation FAILED")

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for err in result.errors:
            lines.append(f"  ✗ {err}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warn in result.warnings:
            lines.append(f"  ⚠ {warn}")

    text = "\n".join(lines)

    if console:
        color = "green" if result.valid else "red"
        console.print(Panel.fit(text, border_style=color, title="Diff Validation"))

    return text
