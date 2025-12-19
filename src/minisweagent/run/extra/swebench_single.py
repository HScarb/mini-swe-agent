"""Run on a single SWE-Bench instance."""

import traceback
from pathlib import Path

import typer
import yaml
from datasets import load_dataset

from minisweagent import global_config_dir
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.config import builtin_config_dir, get_config_path
from minisweagent.models import get_model
from minisweagent.run.extra.swebench import (
    DATASET_MAPPING,
    get_sb_environment,
)
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

app = typer.Typer(add_completion=False)

DEFAULT_OUTPUT = global_config_dir / "last_swebench_single_run.traj.json"
DEFAULT_ACONTEXT_CONFIG = builtin_config_dir / "acontext.yaml"


def _load_acontext_config(
    acontext_enabled: bool,
    acontext_config_path: Path | None,
    acontext_space_name: str | None,
    acontext_space_id: str | None,
    acontext_session_id: str | None,
    instance_id: str | None = None,
) -> dict | None:
    """Load and prepare AContext configuration for single instance processing.

    Args:
        acontext_enabled: Whether AContext is enabled.
        acontext_config_path: Path to AContext config file.
        acontext_space_name: Space name override.
        acontext_space_id: Space ID override.
        acontext_session_id: Session ID to resume.
        instance_id: SWE-bench instance ID (for session metadata).

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

    # Add instance metadata to session config
    if instance_id:
        acontext_config.setdefault("session", {}).setdefault("configs", {})["instance_id"] = instance_id
        acontext_config["session"]["configs"]["agent"] = "mini-swe-agent-swebench-single"

    return acontext_config


# fmt: off
@app.command()
def main(
    subset: str = typer.Option("lite", "--subset", help="SWEBench subset to use or path to a dataset", rich_help_panel="Data selection"),
    split: str = typer.Option("dev", "--split", help="Dataset split", rich_help_panel="Data selection"),
    instance_spec: str = typer.Option(0, "-i", "--instance", help="SWE-Bench instance ID or index", rich_help_panel="Data selection"),
    model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use", rich_help_panel="Basic"),
    model_class: str | None = typer.Option(None, "--model-class", help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')", rich_help_panel="Advanced"),
    config_path: Path = typer.Option( builtin_config_dir / "extra" / "swebench.yaml", "-c", "--config", help="Path to a config file", rich_help_panel="Basic"),
    environment_class: str | None = typer.Option(None, "--environment-class", rich_help_panel="Advanced"),
    exit_immediately: bool = typer.Option( False, "--exit-immediately", help="Exit immediately when the agent wants to finish instead of prompting.", rich_help_panel="Basic"),
    output: Path = typer.Option(DEFAULT_OUTPUT, "-o", "--output", help="Output trajectory file", rich_help_panel="Basic"),
    # AContext options
    acontext_enabled: bool = typer.Option(False, "--acontext/--no-acontext", help="Enable AContext for SOP learning and experience retrieval", rich_help_panel="AContext"),
    acontext_config: Path | None = typer.Option(None, "--acontext-config", help="Path to AContext config file", rich_help_panel="AContext"),
    acontext_space_name: str | None = typer.Option(None, "--acontext-space-name", help="AContext space name", rich_help_panel="AContext"),
    acontext_space_id: str | None = typer.Option(None, "--acontext-space-id", help="AContext space ID (takes precedence over name)", rich_help_panel="AContext"),
    acontext_session_id: str | None = typer.Option(None, "--acontext-session-id", help="AContext session ID to resume", rich_help_panel="AContext"),
) -> None:
    # fmt: on
    """Run on a single SWE-Bench instance."""
    dataset_path = DATASET_MAPPING.get(subset, subset)
    logger.info(f"Loading dataset from {dataset_path}, split {split}...")
    instances = {
        inst["instance_id"]: inst  # type: ignore
        for inst in load_dataset(dataset_path, split=split)
    }
    if instance_spec.isnumeric():
        instance_spec = sorted(instances.keys())[int(instance_spec)]
    instance: dict = instances[instance_spec]  # type: ignore

    config_path = get_config_path(config_path)
    logger.info(f"Loading agent config from '{config_path}'")
    config = yaml.safe_load(config_path.read_text())
    if environment_class is not None:
        config.setdefault("environment", {})["environment_class"] = environment_class
    if model_class is not None:
        config.setdefault("model", {})["model_class"] = model_class
    if exit_immediately:
        config.setdefault("agent", {})["confirm_exit"] = False
    env = get_sb_environment(config, instance)

    # Load AContext configuration
    acontext_cfg = _load_acontext_config(
        acontext_enabled=acontext_enabled,
        acontext_config_path=acontext_config,
        acontext_space_name=acontext_space_name,
        acontext_space_id=acontext_space_id,
        acontext_session_id=acontext_session_id,
        instance_id=instance_spec,
    )

    # Create agent based on AContext configuration
    if acontext_cfg:
        from minisweagent.agents.interactive_context_aware import InteractiveContextAwareAgent
        agent = InteractiveContextAwareAgent(
            get_model(model_name, config.get("model", {})),
            env,
            acontext_config=acontext_cfg,
            **({"mode": "yolo"} | config.get("agent", {})),
        )
    else:
        agent = InteractiveAgent(
            get_model(model_name, config.get("model", {})),
            env,
            **({"mode": "yolo"} | config.get("agent", {})),
        )

    exit_status, result, extra_info = None, None, None
    try:
        exit_status, result = agent.run(instance["problem_statement"])  # type: ignore[arg-type]
    except Exception as e:
        logger.error(f"Error processing instance {instance_spec}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}
    finally:
        save_traj(agent, output, exit_status=exit_status, result=result, extra_info=extra_info)  # type: ignore[arg-type]


if __name__ == "__main__":
    app()
