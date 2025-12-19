import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from minisweagent import Agent, __version__
from minisweagent.utils.log import logger


def _get_class_name_with_module(obj: Any) -> str:
    """Get the full class name with module path."""
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"


def _get_acontext_info(agent: Agent) -> dict | None:
    """Get AContext information from agent if available.

    Args:
        agent: The agent to get AContext info from.

    Returns:
        Dictionary with AContext information, or None if not available.
    """
    if not hasattr(agent, "acontext"):
        return None

    acontext = agent.acontext
    if not acontext.enabled:
        return None

    try:
        task_status = acontext.get_task_status()
        sop_applied = getattr(agent, "sop_applied", False)

        return {
            "session_id": task_status.get("session_id"),
            "space_id": task_status.get("space_id"),
            "space_name": task_status.get("space_name"),
            "total_tasks": task_status.get("total_tasks", 0),
            "learning_status": task_status.get("learning_status", "unknown"),
            "sop_applied": sop_applied,
        }
    except Exception as e:
        logger.debug(f"Failed to get AContext info: {e}")
        return {
            "error": str(e),
            "sop_applied": getattr(agent, "sop_applied", False),
        }


def save_traj(
    agent: Agent | None,
    path: Path | None,
    *,
    print_path: bool = True,
    exit_status: str | None = None,
    result: str | None = None,
    extra_info: dict | None = None,
    print_fct: Callable = print,
    **kwargs,
):
    """Save the trajectory of the agent to a file.

    Args:
        agent: The agent to save the trajectory of.
        path: The path to save the trajectory to.
        print_path: Whether to print confirmation of path to the terminal.
        exit_status: The exit status of the agent.
        result: The result/submission of the agent.
        extra_info: Extra information to save (will be merged into the info dict).
        **kwargs: Additional information to save (will be merged into top level)

    """
    if path is None:
        return
    data = {
        "info": {
            "exit_status": exit_status,
            "submission": result,
            "model_stats": {
                "instance_cost": 0.0,
                "api_calls": 0,
            },
            "mini_version": __version__,
        },
        "messages": [],
        "trajectory_format": "mini-swe-agent-1",
    } | kwargs
    if agent is not None:
        data["info"]["model_stats"]["instance_cost"] = agent.model.cost
        data["info"]["model_stats"]["api_calls"] = agent.model.n_calls
        data["messages"] = agent.messages
        data["info"]["config"] = {
            "agent": agent.config.model_dump(),
            "model": agent.model.config.model_dump(),
            "environment": agent.env.config.model_dump(),
            "agent_type": _get_class_name_with_module(agent),
            "model_type": _get_class_name_with_module(agent.model),
            "environment_type": _get_class_name_with_module(agent.env),
        }

        # Add AContext information if available
        acontext_info = _get_acontext_info(agent)
        if acontext_info:
            data["info"]["acontext"] = acontext_info

    if extra_info:
        data["info"].update(extra_info)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    if print_path:
        print_fct(f"Saved trajectory to '{path}'")
