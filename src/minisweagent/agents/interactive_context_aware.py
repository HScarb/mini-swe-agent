"""Interactive context-aware agent with AContext integration.

This module provides InteractiveContextAwareAgent that extends InteractiveAgent with:
- SOP learning capability
- Experience retrieval
- Message persistence to AContext
- Visual feedback in interactive mode
"""

from rich.console import Console
from rich.panel import Panel

from minisweagent.agents.interactive import InteractiveAgent, InteractiveAgentConfig
from minisweagent.acontext.manager import AContextManager
from minisweagent.utils.log import logger

console = Console(highlight=False)


class InteractiveContextAwareAgent(InteractiveAgent):
    """InteractiveAgent enhanced with AContext integration.

    This agent extends InteractiveAgent with the following capabilities:
    - Searches for relevant SOPs before starting a task
    - Stores all messages to AContext for learning
    - Injects historical SOP into the system prompt
    - Displays SOP information in interactive mode

    All AContext operations fail gracefully without affecting the main agent flow.
    """

    def __init__(self, *args, acontext_config: dict | None = None, **kwargs):
        """Initialize InteractiveContextAwareAgent.

        Args:
            *args: Arguments passed to InteractiveAgent.
            acontext_config: AContext configuration dictionary.
                If None or empty, AContext is disabled.
            **kwargs: Keyword arguments passed to InteractiveAgent.
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

        if acontext_initialized:
            # Display AContext status
            self._display_acontext_status()
            # Search and apply SOPs
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

    def _display_acontext_status(self):
        """Display AContext initialization status."""
        console.print(
            Panel(
                f"[bold green]AContext Enabled[/bold green]\n"
                f"Space: [cyan]{self.acontext.space_name}[/cyan]\n"
                f"Session: [dim]{self.acontext.session_id}[/dim]",
                title="[bold]AContext[/bold]",
                border_style="green",
            )
        )

    def _search_and_apply_sop(self, task: str):
        """Search for relevant SOPs and apply them to the prompt.

        Args:
            task: The task description to search for.
        """
        try:
            with console.status("[bold blue]Searching for relevant SOPs..."):
                sop_blocks = self.acontext.search_sop(task)

            if not sop_blocks:
                console.print("[dim]No relevant SOPs found for this task.[/dim]")
                return

            # Display found SOPs
            self._display_sop_blocks(sop_blocks)

            # Apply SOPs to prompt
            sop_text = self.acontext.format_sop_for_prompt(sop_blocks)
            if sop_text:
                self.extra_template_vars["historical_sop"] = sop_text
                self.sop_applied = True

        except Exception as e:
            logger.debug(f"Failed to search/apply SOPs: {e}")
            console.print(f"[yellow]Warning: Could not search for SOPs: {e}[/yellow]")

    def _display_sop_blocks(self, sop_blocks: list[dict]):
        """Display found SOP blocks in a formatted way.

        Args:
            sop_blocks: List of SOP blocks to display.
        """
        sop_lines = []
        for i, block in enumerate(sop_blocks, 1):
            props = block.get("props", {})
            relevance = 1 - (block.get("distance", 1.0) / 2)
            title = block.get("title", "Untitled")

            sop_lines.append(f"[bold]{i}. {title}[/bold] (relevance: {relevance:.1%})")

            if use_when := props.get("use_when"):
                sop_lines.append(f"   [dim]When: {use_when[:80]}...[/dim]" if len(use_when) > 80 else f"   [dim]When: {use_when}[/dim]")

        console.print(
            Panel(
                "\n".join(sop_lines),
                title=f"[bold]Found {len(sop_blocks)} Relevant SOP(s)[/bold]",
                border_style="blue",
            )
        )

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
        """Finalize AContext operations and display summary.

        Args:
            exit_status: The exit status of the agent.
        """
        if not self.acontext.enabled:
            return

        try:
            # Flush messages
            self.acontext.flush_and_wait()

            # Get and display status
            status = self.acontext.get_task_status()

            console.print(
                Panel(
                    f"[bold]Session Summary[/bold]\n"
                    f"Space: [cyan]{status.get('space_name', 'N/A')}[/cyan]\n"
                    f"Tasks Extracted: [green]{status.get('total_tasks', 0)}[/green]\n"
                    f"Learning Status: [yellow]{status.get('learning_status', 'unknown')}[/yellow]\n"
                    f"SOPs Applied: [{'green' if self.sop_applied else 'dim'}]{'Yes' if self.sop_applied else 'No'}[/{'green' if self.sop_applied else 'dim'}]",
                    title="[bold]AContext[/bold]",
                    border_style="green",
                )
            )

        except Exception as e:
            logger.debug(f"Error finalizing AContext: {e}")
        finally:
            self.acontext.close()
