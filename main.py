"""
Recruiting Agents CLI — Livo Health AI Talent Pipeline

Usage:
  python main.py                          # Interactive mode
  python main.py --role engineer          # Source AI Engineers
  python main.py --role pm --n 5          # Source 5 AI PMs
  python main.py --desc "We need a..."    # Free-form job description
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box

from models.candidate import RoleType
from pipeline import run_pipeline, run_interview_analysis, PipelineResult

console = Console()

ROLE_CHOICES = {
    "pm": RoleType.AI_PM,
    "designer": RoleType.AI_DESIGNER,
    "engineer": RoleType.AI_ENGINEER,
    "ds": RoleType.DATA_SCIENTIST,
    "data_scientist": RoleType.DATA_SCIENTIST,
}

DEFAULT_DESCRIPTIONS = {
    RoleType.AI_PM: "Senior AI Product Manager to lead our intelligent scheduling product at Livo Health. "
                    "Must have experience shipping AI-powered features and working with engineering teams "
                    "building LLM-based systems in healthcare or regulated industries.",
    RoleType.AI_DESIGNER: "AI/UX Designer to craft human-AI interaction experiences for Livo Health's "
                           "staffing platform. Must have experience designing AI-assisted workflows, "
                           "familiarity with LLM product patterns, and a portfolio showing AI product work.",
    RoleType.AI_ENGINEER: "Senior AI Engineer to build and deploy production AI systems at Livo Health. "
                           "Must have deep experience with LLMs, RAG, fine-tuning, and production ML. "
                           "Python expert, experience with LangChain or similar frameworks, MLOps a plus.",
    RoleType.DATA_SCIENTIST: "Senior Data Scientist to build predictive models for healthcare staffing "
                              "at Livo Health. Must have strong ML fundamentals, experience with time-series "
                              "forecasting, and ideally prior work in healthcare data or operations research.",
}


def _print_header():
    console.print(
        Panel.fit(
            "[bold blue]Livo Health[/bold blue] [white]— AI Recruiting Pipeline[/white]\n"
            "[dim]Powered by Claude Opus 4.7[/dim]",
            border_style="blue",
        )
    )
    console.print()


def _print_stats(result: PipelineResult):
    stats = result.stats
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("", style="dim")
    table.add_column("", style="bold white")

    table.add_row("Role", f"{result.job_spec.title}")
    table.add_row("Sourced", f"{stats['sourced']} candidates")
    table.add_row("Enriched", f"{stats['enriched']} profiles")
    table.add_row("Scored", f"{stats['scored']} evaluated")
    table.add_row("Recommended", f"[green]{stats['recommended']} ✓[/green]")
    table.add_row("Outreach ready", f"[cyan]{stats['outreached']} messages[/cyan]")

    console.print(Panel(table, title="[bold]Pipeline Summary[/bold]", border_style="green"))
    console.print()


def _print_top_candidates(result: PipelineResult):
    if not result.outreached:
        console.print("[yellow]No recommended candidates found.[/yellow]")
        return

    console.print("[bold]Top Candidates — Recommended for Outreach[/bold]\n")

    for i, candidate in enumerate(result.outreached, 1):
        score_color = "green" if candidate.fit_score >= 7 else "yellow" if candidate.fit_score >= 5 else "red"

        header = Text()
        header.append(f"{i}. {candidate.name}", style="bold white")
        header.append(f"  [{score_color}]{candidate.fit_score:.1f}/10[/{score_color}]")
        header.append(f"  · {candidate.source.value}", style="dim")
        header.append(f"  · {candidate.outreach_channel or 'N/A'}", style="dim cyan")
        console.print(header)

        if candidate.headline:
            console.print(f"   [dim]{candidate.headline}[/dim]")

        if candidate.scoring_rationale:
            rationale = candidate.scoring_rationale[:200].replace("\n", " ")
            console.print(f"   [italic]{rationale}...[/italic]" if len(candidate.scoring_rationale) > 200 else f"   [italic]{candidate.scoring_rationale}[/italic]")

        if candidate.outreach_message:
            msg_preview = candidate.outreach_message[:300].replace("\n", " ")
            console.print(
                Panel(
                    f"[dim italic]{msg_preview}{'...' if len(candidate.outreach_message) > 300 else ''}[/dim italic]",
                    title=f"[cyan]{candidate.outreach_subject or 'Outreach Message'}[/cyan]",
                    border_style="dim cyan",
                    padding=(0, 1),
                )
            )

        console.print()


def _save_results(result: PipelineResult, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    role_slug = result.job_spec.role_type.value.lower().replace(" ", "_")
    filename = output_dir / f"{role_slug}_{timestamp}.json"

    data = {
        "job_spec": result.job_spec.model_dump(),
        "stats": result.stats,
        "candidates": [c.model_dump() for c in result.outreached],
        "all_scored": [c.model_dump() for c in result.scored],
        "interview_insights": [i.model_dump() for i in result.interview_insights],
        "generated_at": datetime.now().isoformat(),
    }

    filename.write_text(json.dumps(data, indent=2, default=str))
    console.print(f"[dim]Results saved to [cyan]{filename}[/cyan][/dim]")
    return filename


def _interactive_mode() -> tuple[RoleType, str]:
    console.print("[bold]Select a role to source:[/bold]")
    console.print("  [cyan]1[/cyan] — AI Product Manager")
    console.print("  [cyan]2[/cyan] — AI Designer")
    console.print("  [cyan]3[/cyan] — AI Engineer")
    console.print("  [cyan]4[/cyan] — Data Scientist")
    console.print()

    choice = console.input("[bold cyan]Choice (1-4):[/bold cyan] ").strip()
    role_map = {
        "1": RoleType.AI_PM,
        "2": RoleType.AI_DESIGNER,
        "3": RoleType.AI_ENGINEER,
        "4": RoleType.DATA_SCIENTIST,
    }
    role = role_map.get(choice, RoleType.AI_ENGINEER)

    console.print()
    console.print(f"[dim]Default description: {DEFAULT_DESCRIPTIONS[role][:100]}...[/dim]")
    custom = console.input("[bold cyan]Custom description (Enter to use default):[/bold cyan] ").strip()
    description = custom if custom else DEFAULT_DESCRIPTIONS[role]

    return role, description


def main():
    parser = argparse.ArgumentParser(description="Livo Health AI Recruiting Pipeline")
    parser.add_argument("--role", choices=list(ROLE_CHOICES.keys()), help="Role type to source")
    parser.add_argument("--desc", type=str, help="Job description (free-form)")
    parser.add_argument("--n", type=int, default=10, help="Number of candidates to source (default: 10)")
    parser.add_argument("--enrich-n", type=int, default=10, help="How many to enrich (default: 10)")
    parser.add_argument("--output", type=str, default="output", help="Output directory for results")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to disk")
    args = parser.parse_args()

    _print_header()

    # Determine role and description
    if args.role:
        role = ROLE_CHOICES[args.role]
        description = args.desc or DEFAULT_DESCRIPTIONS[role]
    elif args.desc:
        role = None
        description = args.desc
    else:
        role, description = _interactive_mode()

    console.print()
    console.print(f"[bold]Starting pipeline for:[/bold] [cyan]{description[:80]}...[/cyan]" if len(description) > 80 else f"[bold]Starting pipeline for:[/bold] [cyan]{description}[/cyan]")
    console.print()

    # Track current stage for progress display
    current_stage = {"name": "", "msg": ""}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        def on_progress(stage: str, msg: str):
            current_stage["name"] = stage
            current_stage["msg"] = msg
            progress.update(task, description=f"[cyan]{stage.upper()}[/cyan]  {msg}")

        result = run_pipeline(
            raw_description=description,
            role_type=role,
            num_candidates=args.n,
            enrich_top_n=args.enrich_n,
            on_progress=on_progress,
        )

    _print_stats(result)
    _print_top_candidates(result)

    if not args.no_save and result.outreached:
        _save_results(result, Path(args.output))

    return result


if __name__ == "__main__":
    main()
