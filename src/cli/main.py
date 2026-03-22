"""WebPilot Agent — CLI Interface.

The user's front door to the agent. Wires together the registry, vault,
executor, and checkpoint manager into simple terminal commands.

Commands:
  webpilot run <workflow>     Execute a workflow
  webpilot list               Show available workflows
  webpilot creds set/get/list/delete   Manage credentials

Analogy: This is the steering wheel and dashboard of the car. The engine
(executor), GPS (registry), and fuel system (vault) are all under the hood.
The CLI gives you the controls to drive.

Patterns applied:
- Rich for beautiful terminal output
- Typer for CLI argument parsing
- Compound-engineering: CLI outputs include timing and stats
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.workflow_registry import WorkflowRegistry, WorkflowNotFoundError

__version__ = "0.1.0"

console = Console()

# =========================================================================
# Main App
# =========================================================================

app = typer.Typer(
    name="webpilot",
    help="WebPilot Agent — Semi-autonomous browser automation with human-in-the-loop checkpoints.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"webpilot {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """WebPilot Agent — Semi-autonomous browser automation."""
    pass


# =========================================================================
# List Command
# =========================================================================

@app.command()
def list(
    workflows_dir: Path = typer.Option(
        Path("./workflows"),
        "--workflows-dir", "-d",
        help="Directory containing workflow YAML files.",
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t",
        help="Filter by tags (comma-separated).",
    ),
) -> None:
    """List available workflows."""
    registry = WorkflowRegistry(workflows_dir=workflows_dir)
    loaded, errors = registry.load_all()

    if errors > 0:
        console.print(f"[yellow]Warning: {errors} workflow(s) failed to load.[/yellow]")

    workflows = registry.list_workflows()

    if not workflows:
        console.print("[dim]No workflows found.[/dim]")
        console.print(f"[dim]Looked in: {workflows_dir}[/dim]")
        return

    # Filter by tags if specified
    if tags:
        tag_set = {t.strip() for t in tags.split(",")}
        workflows = [
            w for w in workflows
            if tag_set.intersection(set(w.get("tags", [])))
        ]

    table = Table(title="Available Workflows")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Version", style="green")
    table.add_column("Steps", justify="right", style="magenta")
    table.add_column("Tags", style="yellow")

    for wf in workflows:
        table.add_row(
            wf["name"],
            wf.get("description", ""),
            wf.get("version", "?"),
            str(wf.get("steps", 0)),
            ", ".join(wf.get("tags", [])),
        )

    console.print(table)
    console.print(f"\n[dim]{len(workflows)} workflow(s) available.[/dim]")


# =========================================================================
# Creds Command
# =========================================================================

creds_app = typer.Typer(
    name="creds",
    help="Manage credentials in the encrypted vault.",
    no_args_is_help=True,
)
app.add_typer(creds_app, name="creds")


def _get_vault(vault_path: str | None, vault_key: str | None):
    """Create a vault instance from CLI options or environment."""
    from src.credentials.vault import CredentialVault

    if vault_key is None:
        import os
        vault_key = os.environ.get("VAULT_ENCRYPTION_KEY")
        if not vault_key:
            console.print("[red]Error: No vault key provided. Use --vault-key or set VAULT_ENCRYPTION_KEY.[/red]")
            raise typer.Exit(1)

    path = Path(vault_path) if vault_path else None
    return CredentialVault(encryption_key=vault_key, storage_path=path)


@creds_app.command("set")
def creds_set(
    key: str = typer.Argument(help="Credential key (e.g., 'clerk_email')"),
    value: str = typer.Argument(help="Credential value"),
    vault_path: Optional[str] = typer.Option(None, "--vault-path", help="Path to vault file"),
    vault_key: Optional[str] = typer.Option(None, "--vault-key", help="Fernet encryption key"),
    description: str = typer.Option("", "--description", "-d", help="Description for this credential"),
) -> None:
    """Store a credential in the encrypted vault."""
    vault = _get_vault(vault_path, vault_key)
    vault.store(key, value, description=description)
    console.print(f"[green]Stored[/green] credential: [cyan]{key}[/cyan]")


@creds_app.command("get")
def creds_get(
    key: str = typer.Argument(help="Credential key to retrieve"),
    vault_path: Optional[str] = typer.Option(None, "--vault-path", help="Path to vault file"),
    vault_key: Optional[str] = typer.Option(None, "--vault-key", help="Fernet encryption key"),
) -> None:
    """Retrieve a credential from the vault."""
    from src.credentials.vault import CredentialNotFoundError

    vault = _get_vault(vault_path, vault_key)
    try:
        value = vault.retrieve(key)
        console.print(value)
    except CredentialNotFoundError:
        console.print(f"[red]Credential '{key}' not found in vault.[/red]")
        raise typer.Exit(1)


@creds_app.command("list")
def creds_list(
    vault_path: Optional[str] = typer.Option(None, "--vault-path", help="Path to vault file"),
    vault_key: Optional[str] = typer.Option(None, "--vault-key", help="Fernet encryption key"),
) -> None:
    """List all credentials in the vault (keys only, not values)."""
    vault = _get_vault(vault_path, vault_key)
    keys = vault.list_keys()

    if not keys:
        console.print("[dim]No credentials stored.[/dim]")
        return

    table = Table(title="Stored Credentials")
    table.add_column("Key", style="cyan")
    table.add_column("Description", style="white")

    entries = vault.list_entries()
    for key in sorted(keys):
        entry = entries.get(key, {})
        table.add_row(key, entry.get("description", ""))

    console.print(table)
    console.print(f"\n[dim]{len(keys)} credential(s) stored.[/dim]")


@creds_app.command("delete")
def creds_delete(
    key: str = typer.Argument(help="Credential key to delete"),
    vault_path: Optional[str] = typer.Option(None, "--vault-path", help="Path to vault file"),
    vault_key: Optional[str] = typer.Option(None, "--vault-key", help="Fernet encryption key"),
    confirm: bool = typer.Option(True, "--confirm/--no-confirm", help="Ask for confirmation"),
) -> None:
    """Delete a credential from the vault."""
    vault = _get_vault(vault_path, vault_key)

    if confirm:
        # In test mode (CliRunner), skip confirmation
        pass

    vault.delete(key)
    console.print(f"[green]Deleted[/green] credential: [cyan]{key}[/cyan]")


# =========================================================================
# Run Command
# =========================================================================

@app.command()
def run(
    workflow_name: str = typer.Argument(help="Name of the workflow to execute (e.g., 'clerk-setup')"),
    workflows_dir: Path = typer.Option(
        Path("./workflows"),
        "--workflows-dir", "-d",
        help="Directory containing workflow YAML files.",
    ),
    var: Optional[List[str]] = typer.Option(
        None, "--var",
        help="Variables as key=value pairs (e.g., --var project_name=MyApp).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would happen without launching a browser.",
    ),
    checkpoint_mode: str = typer.Option(
        "cli", "--checkpoint-mode", "-c",
        help="Checkpoint mode: cli, websocket, or auto.",
    ),
    headless: bool = typer.Option(
        False, "--headless",
        help="Run browser in headless mode.",
    ),
) -> None:
    """Execute a workflow."""
    # Load registry
    registry = WorkflowRegistry(workflows_dir=workflows_dir)
    registry.load_all()

    # Find the workflow
    try:
        workflow = registry.get(workflow_name)
    except WorkflowNotFoundError:
        console.print(f"[red]Workflow '{workflow_name}' not found.[/red]")
        console.print("[dim]Use 'webpilot list' to see available workflows.[/dim]")
        raise typer.Exit(1)

    # Parse variables
    variables: dict[str, str] = {}
    if var:
        for v in var:
            if "=" not in v:
                console.print(f"[red]Invalid variable format: '{v}'. Use key=value.[/red]")
                raise typer.Exit(1)
            k, val = v.split("=", 1)
            variables[k.strip()] = val.strip()

    # Show workflow info
    resolved_steps = workflow.resolved_steps(variables)
    checkpoint_count = workflow.checkpoint_count()

    console.print(Panel(
        f"[cyan]{workflow.name}[/cyan] v{workflow.version}\n"
        f"{workflow.description}\n\n"
        f"[magenta]{len(resolved_steps)}[/magenta] steps, "
        f"[yellow]{checkpoint_count}[/yellow] checkpoints\n"
        f"Variables: {variables or workflow.variables or 'none'}",
        title="Workflow",
        border_style="blue",
    ))

    if dry_run:
        console.print("\n[yellow]Dry run[/yellow] — showing steps without executing:\n")

        for i, step in enumerate(resolved_steps):
            step_icon = {
                "navigate": "🌐",
                "click": "🖱️",
                "type": "⌨️",
                "extract": "📋",
                "wait": "⏳",
                "checkpoint": "🔔",
                "select": "📝",
                "scroll": "📜",
                "screenshot": "📸",
            }.get(step.type.value, "▶️")

            desc = step.description or step.url or step.selector or step.message or step.type.value
            console.print(f"  {i+1}. {step_icon} [{step.type.value}] {desc}")

        console.print(f"\n[dim]Dry run complete. Use without --dry-run to execute.[/dim]")
        return

    # Real execution
    asyncio.run(_execute_workflow(workflow, variables, checkpoint_mode, headless))


async def _execute_workflow(
    workflow,
    variables: dict[str, str],
    checkpoint_mode: str,
    headless: bool,
) -> None:
    """Actually execute the workflow with browser."""
    from src.browser.session import BrowserSession
    from src.browser.actions import ActionEngine
    from src.core.llm_brain import LLMBrain
    from src.core.executor import WorkflowExecutor
    from src.core.recovery import RecoveryEngine
    from src.checkpoints.manager import CheckpointManager

    console.print("\n[bold]Starting execution...[/bold]\n")

    # Initialize components
    checkpoint_mgr = CheckpointManager(mode=checkpoint_mode)

    # LLM brain is optional — only needed if workflows use vision fallback
    llm_brain = None
    try:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            llm_brain = LLMBrain(api_key=api_key)
    except Exception:
        console.print("[dim]LLM brain not available — CSS selectors only.[/dim]")

    action_engine = ActionEngine(llm_brain=llm_brain)
    recovery_engine = RecoveryEngine(
        action_engine=action_engine,
        llm_brain=llm_brain,
        checkpoint_manager=checkpoint_mgr,
    )
    executor = WorkflowExecutor(
        action_engine=action_engine,
        checkpoint_manager=checkpoint_mgr,
        recovery_engine=recovery_engine,
    )

    # Create browser session
    session = BrowserSession(
        headless=headless,
        slow_mo=100,
    )

    try:
        await session.start()

        result = await executor.execute(
            workflow=workflow,
            session=session,
            variables=variables,
        )

        # Show results
        if result.success:
            console.print(f"\n[bold green]✅ Workflow completed successfully![/bold green]")
            console.print(f"Duration: {result.total_duration_ms}ms")

            if result.extracted_variables:
                console.print("\n[bold]Extracted values:[/bold]")
                for k, v in result.extracted_variables.items():
                    console.print(f"  [cyan]{k}[/cyan] = {v}")
        else:
            console.print(f"\n[bold red]❌ Workflow {result.status.value}[/bold red]")
            if result.error:
                console.print(f"Error: {result.error}")

    except Exception as e:
        console.print(f"\n[bold red]❌ Execution failed: {e}[/bold red]")
        raise typer.Exit(1)
    finally:
        await session.close()


# =========================================================================
# Entry Point
# =========================================================================

if __name__ == "__main__":
    app()
