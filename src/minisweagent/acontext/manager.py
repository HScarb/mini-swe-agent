"""AContext Manager for mini-swe-agent.

This module provides the AContextManager class that encapsulates all AContext operations.
"""

import os
from typing import Any

from minisweagent.utils.log import logger

# Lazy import to avoid dependency issues when AContext is not installed
AcontextClient = None


def _get_acontext_client():
    """Lazy import of AcontextClient to avoid dependency issues."""
    global AcontextClient
    if AcontextClient is None:
        try:
            from acontext import AcontextClient as _AcontextClient
            AcontextClient = _AcontextClient
        except ImportError:
            logger.warning("AContext SDK not installed. AContext features will be disabled.")
            return None
    return AcontextClient


class AContextManager:
    """Manager class for AContext operations.

    This class encapsulates all AContext operations including:
    - Space management (create/find)
    - Session management (create/resume)
    - Message storage
    - SOP search and formatting

    All operations are designed to fail gracefully without affecting the main agent flow.
    """

    def __init__(self, config: dict | None = None):
        """Initialize AContextManager.

        Args:
            config: AContext configuration dictionary. If None, AContext is disabled.
                Expected keys:
                - enabled: bool (default: True)
                - api_key: str (default: from ACONTEXT_API_KEY env var)
                - base_url: str (default: from ACONTEXT_BASE_URL env var)
                - timeout: float (default: 60.0)
                - space: dict with space_name, space_id
                - session: dict with session_id, resume_last, configs
                - sop_search: dict with enabled, mode, limit, semantic_threshold
                - message: dict with store_realtime
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self._client = None
        self._space = None
        self._session = None
        self._initialized = False
        self.space_name = None
        self.space_id = None
        self.session_id = None

    def initialize(self) -> bool:
        """Initialize AContext client, space, and session.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        if not self.enabled:
            logger.debug("AContext is disabled")
            return False

        if self._initialized:
            return True

        try:
            # Get client class
            ClientClass = _get_acontext_client()
            if ClientClass is None:
                self.enabled = False
                return False

            # Create client
            api_key = self.config.get("api_key") or os.getenv("ACONTEXT_API_KEY")
            base_url = self.config.get("base_url") or os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1")
            timeout = self.config.get("timeout", 60.0)

            if not api_key:
                logger.warning("AContext API key not configured. AContext features will be disabled.")
                self.enabled = False
                return False

            self._client = ClientClass(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )

            # Test connection
            try:
                self._client.ping()
            except Exception as e:
                logger.warning(f"Failed to connect to AContext server: {e}")
                self.enabled = False
                return False

            # Initialize space
            if not self._init_space():
                self.enabled = False
                return False

            # Initialize session
            if not self._init_session():
                self.enabled = False
                return False

            self._initialized = True
            logger.info(
                f"AContext initialized successfully. Space: '{self.space_name}' ({self.space_id}), "
                f"Session: {self.session_id}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to initialize AContext: {e}")
            self.enabled = False
            return False

    def _init_space(self) -> bool:
        """Initialize or find the space.

        Returns:
            True if space initialization succeeded, False otherwise.
        """
        space_config = self.config.get("space", {})
        space_id = space_config.get("space_id")
        space_name = space_config.get("space_name", "mini-swe-agent-default")

        try:
            if space_id:
                # Use specified space ID
                self._space = self._client.spaces.get_configs(space_id)
                self.space_id = space_id
                self.space_name = self._space.configs.get("name", space_name)
                logger.info(f"Using existing space: '{self.space_name}' (ID: {self.space_id})")
            else:
                # Find or create space by name
                self._space = self._find_or_create_space(space_name)
                if self._space is None:
                    return False
                self.space_id = self._space.id
                self.space_name = self._space.configs.get("name", space_name)

            return True
        except Exception as e:
            logger.warning(f"Failed to initialize space: {e}")
            return False

    def _find_or_create_space(self, space_name: str):
        """Find a space by name or create a new one.

        Args:
            space_name: Name of the space to find or create.

        Returns:
            Space object or None if failed.
        """
        try:
            # List all spaces and find by name
            result = self._client.spaces.list(limit=100)
            for space in result.items:
                if space.configs.get("name") == space_name:
                    logger.info(f"Found existing space: '{space_name}' (ID: {space.id})")
                    return space

            # Create new space if not found
            new_space = self._client.spaces.create(configs={"name": space_name})
            logger.info(f"Created new space: '{space_name}' (ID: {new_space.id})")
            return new_space

        except Exception as e:
            logger.warning(f"Failed to find or create space '{space_name}': {e}")
            return None

    def _init_session(self) -> bool:
        """Initialize or resume the session.

        Returns:
            True if session initialization succeeded, False otherwise.
        """
        session_config = self.config.get("session", {})
        session_id = session_config.get("session_id")
        session_configs = session_config.get("configs", {})

        try:
            if session_id:
                # Resume existing session
                self._session = self._client.sessions.get_configs(session_id)
                self.session_id = session_id
                logger.info(f"Resumed existing session: {self.session_id}")
            else:
                # Create new session
                self._session = self._client.sessions.create(
                    space_id=self.space_id,
                    configs={"agent": "mini-swe-agent", **session_configs},
                )
                self.session_id = self._session.id
                logger.info(f"Created new session: {self.session_id}")

            return True
        except Exception as e:
            logger.warning(f"Failed to initialize session: {e}")
            return False

    def store_message(self, role: str, content: str, **kwargs) -> bool:
        """Store a message to AContext.

        Args:
            role: Message role (system, user, assistant).
            content: Message content.
            **kwargs: Additional message fields.

        Returns:
            True if storage succeeded, False otherwise.
        """
        if not self.enabled or not self._initialized:
            return False

        message_config = self.config.get("message", {})
        if not message_config.get("store_realtime", True):
            return False

        try:
            message = {"role": role, "content": content, **kwargs}
            self._client.sessions.store_message(
                session_id=self.session_id,
                blob=message,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to store message to AContext: {e}")
            return False

    def search_sop(self, query: str) -> list[dict]:
        """Search for relevant SOPs based on the query.

        Args:
            query: Search query (typically the task description).

        Returns:
            List of SOP blocks, or empty list if search failed or disabled.
        """
        if not self.enabled or not self._initialized:
            return []

        sop_config = self.config.get("sop_search", {})
        if not sop_config.get("enabled", True):
            return []

        try:
            mode = sop_config.get("mode", "fast")
            limit = sop_config.get("limit", 5)
            semantic_threshold = sop_config.get("semantic_threshold", 0.8)

            result = self._client.spaces.experience_search(
                space_id=self.space_id,
                query=query,
                mode=mode,
                limit=limit,
            )

            # Filter results by distance threshold
            sop_blocks = []
            for block in result.cited_blocks:
                # Lower distance means more similar (0 = identical, 2 = opposite)
                if block.distance is not None and block.distance > (2 - semantic_threshold * 2):
                    continue
                sop_blocks.append({
                    "block_id": block.block_id,
                    "title": block.title,
                    "type": block.type,
                    "props": block.props,
                    "distance": block.distance,
                })

            logger.info(f"Found {len(sop_blocks)} relevant SOP blocks for query")
            return sop_blocks

        except Exception as e:
            logger.debug(f"Failed to search SOPs: {e}")
            return []

    def format_sop_for_prompt(self, sop_blocks: list[dict]) -> str:
        """Format SOP blocks as text for injection into the prompt.

        Args:
            sop_blocks: List of SOP blocks from search_sop().

        Returns:
            Formatted SOP text ready for prompt injection.
        """
        if not sop_blocks:
            return ""

        lines = [
            "\n## Historical Experience (SOP)",
            "The following are relevant standard operating procedures (SOPs) learned from previous successful tasks.",
            "Consider using these approaches if applicable to the current task.\n"
        ]

        for i, block in enumerate(sop_blocks, 1):
            props = block.get("props", {})
            relevance = 1 - (block.get("distance", 1.0) / 2)  # Convert distance to similarity score

            lines.append(f"### SOP {i}: {block.get('title', 'Untitled')}")
            lines.append(f"**Relevance Score**: {relevance:.2f}")

            if use_when := props.get("use_when"):
                lines.append(f"**When to use**: {use_when}")

            if preferences := props.get("preferences"):
                if isinstance(preferences, list):
                    lines.append("**Preferences**:")
                    for pref in preferences:
                        lines.append(f"  - {pref}")
                else:
                    lines.append(f"**Preferences**: {preferences}")

            if tool_sops := props.get("tool_sops"):
                if isinstance(tool_sops, list):
                    lines.append("**Recommended steps**:")
                    for step in tool_sops:
                        if isinstance(step, dict):
                            tool_name = step.get("tool_name", "Unknown")
                            description = step.get("description", "")
                            lines.append(f"  - [{tool_name}] {description}")
                        else:
                            lines.append(f"  - {step}")

            lines.append("")  # Empty line between SOPs

        return "\n".join(lines)

    def flush_and_wait(self, timeout: float = 30.0) -> bool:
        """Flush the session buffer and wait for task extraction.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if flush succeeded, False otherwise.
        """
        if not self.enabled or not self._initialized:
            return False

        try:
            self._client.sessions.flush(self.session_id)
            return True
        except Exception as e:
            logger.debug(f"Failed to flush session: {e}")
            return False

    def get_task_status(self) -> dict[str, Any]:
        """Get the current task status from AContext.

        Returns:
            Dictionary with task status information.
        """
        if not self.enabled or not self._initialized:
            return {
                "enabled": False,
                "session_id": None,
                "space_id": None,
                "space_name": None,
                "total_tasks": 0,
                "learning_status": "disabled",
            }

        try:
            tasks_response = self._client.sessions.get_tasks(self.session_id)
            learning_status = self._client.sessions.get_learning_status(self.session_id)

            return {
                "enabled": True,
                "session_id": self.session_id,
                "space_id": self.space_id,
                "space_name": self.space_name,
                "total_tasks": len(tasks_response.items),
                "learning_status": "completed" if learning_status.not_space_digested_count == 0 else "in_progress",
                "not_digested_count": learning_status.not_space_digested_count,
            }
        except Exception as e:
            logger.debug(f"Failed to get task status: {e}")
            return {
                "enabled": True,
                "session_id": self.session_id,
                "space_id": self.space_id,
                "space_name": self.space_name,
                "total_tasks": 0,
                "learning_status": "unknown",
                "error": str(e),
            }

    def close(self):
        """Close the AContext client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                logger.debug(f"Error closing AContext client: {e}")
            finally:
                self._client = None
                self._initialized = False
