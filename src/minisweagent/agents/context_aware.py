"""Context-aware agent with AContext integration.

This module provides ContextAwareAgent that extends DefaultAgent with:
- SOP learning capability
- Experience retrieval
- Message persistence to AContext
"""

from minisweagent.agents.default import DefaultAgent, TerminatingException
from minisweagent.acontext.manager import AContextManager
from minisweagent.utils.log import logger


class ContextAwareAgent(DefaultAgent):
    """DefaultAgent enhanced with AContext integration.

    This agent extends DefaultAgent with the following capabilities:
    - Searches for relevant SOPs before starting a task
    - Stores all messages to AContext for learning
    - Injects historical SOP into the system prompt

    All AContext operations fail gracefully without affecting the main agent flow.
    """

    def __init__(self, *args, acontext_config: dict | None = None, **kwargs):
        """Initialize ContextAwareAgent.

        Args:
            *args: Arguments passed to DefaultAgent.
            acontext_config: AContext configuration dictionary.
                If None or empty, AContext is disabled.
            **kwargs: Keyword arguments passed to DefaultAgent.
        """
        super().__init__(*args, **kwargs)
        self.acontext = AContextManager(acontext_config)
        self.sop_applied = False

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run step() until agent is finished.

        This method extends the parent run() method with:
        1. Initialize AContext at the start
        2. Search and apply relevant SOPs
        3. Store messages during execution
        4. Finalize AContext on completion

        Args:
            task: The task/problem statement.
            **kwargs: Additional keyword arguments.

        Returns:
            Tuple of (exit_status, result).
        """
        # Initialize AContext
        acontext_initialized = self.acontext.initialize()

        # Search and apply SOPs if AContext is available
        if acontext_initialized:
            self._search_and_apply_sop(task)

        try:
            # Run the parent agent loop
            exit_status, result = super().run(task, **kwargs)
        except Exception as e:
            exit_status, result = type(e).__name__, str(e)
            raise
        finally:
            # Finalize AContext
            self._finalize_acontext(exit_status if 'exit_status' in dir() else None)

        return exit_status, result

    def _search_and_apply_sop(self, task: str):
        """Search for relevant SOPs and apply them to the prompt.

        Args:
            task: The task description to search for.
        """
        try:
            sop_blocks = self.acontext.search_sop(task)
            if not sop_blocks:
                logger.debug("No relevant SOPs found for the task")
                return

            sop_text = self.acontext.format_sop_for_prompt(sop_blocks)
            if sop_text:
                self.extra_template_vars["historical_sop"] = sop_text
                self.sop_applied = True
                logger.info(f"Applied {len(sop_blocks)} SOP(s) from historical experience")

        except Exception as e:
            logger.debug(f"Failed to search/apply SOPs: {e}")

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message and sync to AContext.

        This extends the parent method to also store messages in AContext.

        Args:
            role: Message role (system, user, assistant).
            content: Message content.
            **kwargs: Additional message fields.
        """
        super().add_message(role, content, **kwargs)

        # Store to AContext (async, non-blocking)
        if self.acontext.enabled:
            self.acontext.store_message(role, content, **kwargs)

    def _finalize_acontext(self, exit_status: str | None = None):
        """Finalize AContext operations.

        Args:
            exit_status: The exit status of the agent.
        """
        if not self.acontext.enabled:
            return

        try:
            # Flush messages and get status
            self.acontext.flush_and_wait()
            status = self.acontext.get_task_status()
            logger.info(
                f"AContext session completed. "
                f"Space: '{status.get('space_name')}', "
                f"Tasks extracted: {status.get('total_tasks', 0)}, "
                f"Learning: {status.get('learning_status', 'unknown')}"
            )
        except Exception as e:
            logger.debug(f"Error finalizing AContext: {e}")
        finally:
            self.acontext.close()
