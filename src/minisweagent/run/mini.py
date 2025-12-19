#!/usr/bin/env python3

"""Run mini-SWE-agent in your local environment. This is the default executable `mini`."""
# Read this first: https://mini-swe-agent.com/latest/usage/mini/  (usage)

import os
import traceback
from pathlib import Path
from typing import Any

import typer
import yaml
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession
from rich.console import Console

from minisweagent import global_config_dir
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.agents.interactive_textual import TextualAgent
from minisweagent.config import builtin_config_dir, get_config_path
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.extra.config import configure_if_first_time
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

DEFAULT_CONFIG = Path(os.getenv("MSWEA_MINI_CONFIG_PATH", builtin_config_dir / "mini.yaml"))
DEFAULT_ACONTEXT_CONFIG = builtin_config_dir / "acontext.yaml"
DEFAULT_OUTPUT = global_config_dir / "last_mini_run.traj.json"
console = Console(highlight=False)
app = typer.Typer(rich_markup_mode="rich")
prompt_session = PromptSession(history=FileHistory(global_config_dir / "mini_task_history.txt"))
_HELP_TEXT = """Run mini-SWE-agent in your local environment.

[not dim]
There are two different user interfaces:

[bold green]mini[/bold green] Simple REPL-style interface
[bold green]mini -v[/bold green] Pager-style interface (Textual)

More information about the usage: [bold green]https://mini-swe-agent.com/latest/usage/mini/[/bold green]
[/not dim]
"""


def _load_acontext_config(
    acontext_enabled: bool,
    acontext_config_path: Path | None,
    acontext_space_name: str | None,
    acontext_space_id: str | None,
    acontext_session_id: str | None,
) -> dict | None:
    """Load and prepare AContext configuration.

    Args:
        acontext_enabled: Whether AContext is enabled.
        acontext_config_path: Path to AContext config file.
        acontext_space_name: Space name override.
        acontext_space_id: Space ID override.
        acontext_session_id: Session ID to resume.

    Returns:
        AContext configuration dictionary, or None if disabled.
    """
    if not acontext_enabled:
        return None

    # Load base config
    config_path = acontext_config_path or DEFAULT_ACONTEXT_CONFIG
    acontext_config = {}
    if config_path.exists():
        try:
            full_config = yaml.safe_load(config_path.read_text())
            acontext_config = full_config.get("acontext", {})
        except Exception as e:
            logger.warning(f"Failed to load AContext config from {config_path}: {e}")

    # Enable AContext
    acontext_config["enabled"] = True

    # Apply CLI overrides
    if acontext_space_name:
        acontext_config.setdefault("space", {})["space_name"] = acontext_space_name
    if acontext_space_id:
        acontext_config.setdefault("space", {})["space_id"] = acontext_space_id
    if acontext_session_id:
        acontext_config.setdefault("session", {})["session_id"] = acontext_session_id

    return acontext_config


# fmt: off
@app.command(help=_HELP_TEXT)
def main(
    visual: bool = typer.Option(False, "-v", "--visual", help="Toggle (pager-style) UI (Textual) depending on the MSWEA_VISUAL_MODE_DEFAULT environment setting",),
    model_name: str | None = typer.Option( None, "-m", "--model", help="Model to use",),
    model_class: str | None = typer.Option(None, "--model-class", help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')", rich_help_panel="Advanced"),
    task: str | None = typer.Option(None, "-t", "--task", help="Task/problem statement", show_default=False),
    yolo: bool = typer.Option(False, "-y", "--yolo", help="Run without confirmation"),
    cost_limit: float | None = typer.Option(None, "-l", "--cost-limit", help="Cost limit. Set to 0 to disable."),
    config_spec: Path = typer.Option(DEFAULT_CONFIG, "-c", "--config", help="Path to config file"),
    output: Path | None = typer.Option(DEFAULT_OUTPUT, "-o", "--output", help="Output trajectory file"),
    exit_immediately: bool = typer.Option( False, "--exit-immediately", help="Exit immediately when the agent wants to finish instead of prompting.", rich_help_panel="Advanced"),
    # AContext options
    acontext_enabled: bool = typer.Option(False, "--acontext/--no-acontext", help="Enable AContext for SOP learning and experience retrieval", rich_help_panel="AContext"),
    acontext_config: Path | None = typer.Option(None, "--acontext-config", help="Path to AContext config file", rich_help_panel="AContext"),
    acontext_space_name: str | None = typer.Option(None, "--acontext-space-name", help="AContext space name", rich_help_panel="AContext"),
    acontext_space_id: str | None = typer.Option(None, "--acontext-space-id", help="AContext space ID (takes precedence over name)", rich_help_panel="AContext"),
    acontext_session_id: str | None = typer.Option(None, "--acontext-session-id", help="AContext session ID to resume", rich_help_panel="AContext"),
) -> Any:
    # fmt: on
    configure_if_first_time()
    config_path = get_config_path(config_spec)
    console.print(f"Loading agent config from [bold green]'{config_path}'[/bold green]")
    config = yaml.safe_load(config_path.read_text())

    if not task:
        console.print("[bold yellow]What do you want to do?")
        task = prompt_session.prompt(
            "",
            multiline=True,
            bottom_toolbar=HTML(
                "Submit task: <b fg='yellow' bg='black'>Esc+Enter</b> | "
                "Navigate history: <b fg='yellow' bg='black'>Arrow Up/Down</b> | "
                "Search history: <b fg='yellow' bg='black'>Ctrl+R</b>"
            ),
        )
        console.print("[bold green]Got that, thanks![/bold green]")

    if yolo:
        config.setdefault("agent", {})["mode"] = "yolo"
    if cost_limit is not None:
        config.setdefault("agent", {})["cost_limit"] = cost_limit
    if exit_immediately:
        config.setdefault("agent", {})["confirm_exit"] = False
    if model_class is not None:
        config.setdefault("model", {})["model_class"] = model_class
    model = get_model(model_name, config.get("model", {}))
    env = LocalEnvironment(**config.get("env", {}))

    # Load AContext configuration
    acontext_cfg = _load_acontext_config(
        acontext_enabled=acontext_enabled,
        acontext_config_path=acontext_config,
        acontext_space_name=acontext_space_name,
        acontext_space_id=acontext_space_id,
        acontext_session_id=acontext_session_id,
    )

    # Determine agent class based on visual mode and AContext
    # Both visual flag and the MSWEA_VISUAL_MODE_DEFAULT flip the mode, so it's essentially a XOR
    use_textual = visual != (os.getenv("MSWEA_VISUAL_MODE_DEFAULT", "false") == "false")

    if use_textual:
        # TextualAgent doesn't support AContext yet
        if acontext_cfg:
            console.print("[yellow]Warning: AContext is not yet supported with TextualAgent (visual mode). Disabling AContext.[/yellow]")
            acontext_cfg = None
        agent_class = TextualAgent
        agent = agent_class(model, env, **config.get("agent", {}))
    else:
        if acontext_cfg:
            from minisweagent.agents.interactive_context_aware import InteractiveContextAwareAgent
            agent = InteractiveContextAwareAgent(model, env, acontext_config=acontext_cfg, **config.get("agent", {}))
        else:
            agent = InteractiveAgent(model, env, **config.get("agent", {}))

    exit_status, result, extra_info = None, None, None
    try:
        exit_status, result = agent.run(task)  # type: ignore[arg-type]
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}
    finally:
        save_traj(agent, output, exit_status=exit_status, result=result, extra_info=extra_info)  # type: ignore[arg-type]
    return agent


if __name__ == "__main__":
    app()
