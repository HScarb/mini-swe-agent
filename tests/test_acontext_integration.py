"""Unit tests for AContext integration.

These tests verify the AContext integration functionality.
Tests that require a live AContext server are marked with @pytest.mark.slow.
"""

import os
import pytest
from unittest.mock import MagicMock, patch


class TestAContextManager:
    """Tests for AContextManager class."""

    def test_manager_disabled_by_default(self):
        """Test that manager is disabled when no config is provided."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        assert not manager.enabled
        assert not manager.initialize()

    def test_manager_disabled_with_empty_config(self):
        """Test that manager is disabled with empty config."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager({})
        assert not manager.enabled
        assert not manager.initialize()

    def test_manager_disabled_explicitly(self):
        """Test that manager is disabled when enabled=False."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager({"enabled": False})
        assert not manager.enabled
        assert not manager.initialize()

    def test_manager_stores_message_when_disabled(self):
        """Test that store_message returns False when disabled."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        result = manager.store_message("user", "test message")
        assert result is False

    def test_manager_search_sop_when_disabled(self):
        """Test that search_sop returns empty list when disabled."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        result = manager.search_sop("test query")
        assert result == []

    def test_manager_get_task_status_when_disabled(self):
        """Test that get_task_status returns disabled status when disabled."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        status = manager.get_task_status()
        assert status["enabled"] is False
        assert status["session_id"] is None

    def test_format_sop_for_prompt_empty(self):
        """Test that format_sop_for_prompt returns empty string for empty list."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        result = manager.format_sop_for_prompt([])
        assert result == ""

    def test_format_sop_for_prompt_with_blocks(self):
        """Test that format_sop_for_prompt formats blocks correctly."""
        from minisweagent.acontext import AContextManager

        manager = AContextManager(None)
        sop_blocks = [
            {
                "block_id": "block1",
                "title": "Fix Bug SOP",
                "type": "sop",
                "props": {
                    "use_when": "When fixing a bug",
                    "preferences": ["Use logging", "Add tests"],
                },
                "distance": 0.5,
            }
        ]

        result = manager.format_sop_for_prompt(sop_blocks)

        assert "Historical Experience" in result
        assert "Fix Bug SOP" in result
        assert "When fixing a bug" in result
        assert "Use logging" in result
        assert "Add tests" in result


class TestContextAwareAgent:
    """Tests for ContextAwareAgent class."""

    def test_agent_without_acontext_config(self):
        """Test that agent works without AContext config."""
        from minisweagent.agents.context_aware import ContextAwareAgent
        from minisweagent.agents.default import AgentConfig

        # Create mock model and environment
        mock_model = MagicMock()
        mock_model.cost = 0.0
        mock_model.n_calls = 0
        mock_model.get_template_vars.return_value = {}

        mock_env = MagicMock()
        mock_env.get_template_vars.return_value = {}

        # Create agent without AContext
        agent = ContextAwareAgent(
            mock_model,
            mock_env,
            acontext_config=None,
            system_template="System",
            instance_template="Instance: {{task}}",
            timeout_template="Timeout",
            format_error_template="Format error",
            action_observation_template="Observation: {{output}}",
        )

        assert agent.acontext is not None
        assert not agent.acontext.enabled
        assert not agent.sop_applied

    def test_agent_with_disabled_acontext(self):
        """Test that agent works with disabled AContext config."""
        from minisweagent.agents.context_aware import ContextAwareAgent

        mock_model = MagicMock()
        mock_model.cost = 0.0
        mock_model.n_calls = 0
        mock_model.get_template_vars.return_value = {}

        mock_env = MagicMock()
        mock_env.get_template_vars.return_value = {}

        agent = ContextAwareAgent(
            mock_model,
            mock_env,
            acontext_config={"enabled": False},
            system_template="System",
            instance_template="Instance: {{task}}",
            timeout_template="Timeout",
            format_error_template="Format error",
            action_observation_template="Observation: {{output}}",
        )

        assert agent.acontext is not None
        assert not agent.acontext.enabled


class TestInteractiveContextAwareAgent:
    """Tests for InteractiveContextAwareAgent class."""

    def test_agent_without_acontext_config(self):
        """Test that interactive agent works without AContext config."""
        from minisweagent.agents.interactive_context_aware import InteractiveContextAwareAgent

        mock_model = MagicMock()
        mock_model.cost = 0.0
        mock_model.n_calls = 0
        mock_model.get_template_vars.return_value = {}

        mock_env = MagicMock()
        mock_env.get_template_vars.return_value = {}

        agent = InteractiveContextAwareAgent(
            mock_model,
            mock_env,
            acontext_config=None,
            system_template="System",
            instance_template="Instance: {{task}}",
            timeout_template="Timeout",
            format_error_template="Format error",
            action_observation_template="Observation: {{output}}",
        )

        assert agent.acontext is not None
        assert not agent.acontext.enabled
        assert not agent.sop_applied


class TestSaveTrajectory:
    """Tests for save_traj function with AContext info."""

    def test_save_traj_without_acontext(self, tmp_path):
        """Test that save_traj works without AContext info."""
        from minisweagent.run.utils.save import save_traj

        mock_agent = MagicMock()
        mock_agent.model.cost = 1.5
        mock_agent.model.n_calls = 10
        mock_agent.messages = [{"role": "user", "content": "test"}]
        mock_agent.config.model_dump.return_value = {}
        mock_agent.model.config.model_dump.return_value = {}
        mock_agent.env.config.model_dump.return_value = {}

        # Agent without acontext attribute
        del mock_agent.acontext

        output_path = tmp_path / "test.traj.json"
        save_traj(mock_agent, output_path, exit_status="Submitted", result="Test result")

        import json
        data = json.loads(output_path.read_text())

        assert "acontext" not in data["info"]
        assert data["info"]["exit_status"] == "Submitted"
        assert data["info"]["submission"] == "Test result"

    def test_save_traj_with_disabled_acontext(self, tmp_path):
        """Test that save_traj works with disabled AContext."""
        from minisweagent.run.utils.save import save_traj

        mock_agent = MagicMock()
        mock_agent.model.cost = 1.5
        mock_agent.model.n_calls = 10
        mock_agent.messages = [{"role": "user", "content": "test"}]
        mock_agent.config.model_dump.return_value = {}
        mock_agent.model.config.model_dump.return_value = {}
        mock_agent.env.config.model_dump.return_value = {}
        mock_agent.acontext.enabled = False

        output_path = tmp_path / "test.traj.json"
        save_traj(mock_agent, output_path, exit_status="Submitted", result="Test result")

        import json
        data = json.loads(output_path.read_text())

        assert "acontext" not in data["info"]


@pytest.mark.slow
class TestAContextIntegration:
    """Integration tests that require a live AContext server.

    These tests are skipped unless ACONTEXT_API_KEY is set.
    """

    @pytest.fixture(autouse=True)
    def check_acontext_available(self):
        """Skip tests if AContext is not configured."""
        if not os.getenv("ACONTEXT_API_KEY"):
            pytest.skip("ACONTEXT_API_KEY not set")

    def test_manager_initialization(self):
        """Test AContextManager initialization with live server."""
        from minisweagent.acontext import AContextManager

        config = {
            "enabled": True,
            "space": {
                "space_name": "test-mini-swe-agent-pytest",
            },
        }

        manager = AContextManager(config)

        try:
            result = manager.initialize()
            assert result is True
            assert manager.space_id is not None
            assert manager.session_id is not None
        finally:
            manager.close()

    def test_message_storage(self):
        """Test message storage with live server."""
        from minisweagent.acontext import AContextManager

        config = {
            "enabled": True,
            "space": {
                "space_name": "test-mini-swe-agent-pytest",
            },
        }

        manager = AContextManager(config)

        try:
            manager.initialize()
            result = manager.store_message("user", "Test message from pytest")
            assert result is True
        finally:
            manager.close()

    def test_sop_search(self):
        """Test SOP search with live server."""
        from minisweagent.acontext import AContextManager

        config = {
            "enabled": True,
            "space": {
                "space_name": "test-mini-swe-agent-pytest",
            },
            "sop_search": {
                "enabled": True,
                "mode": "fast",
                "limit": 5,
            },
        }

        manager = AContextManager(config)

        try:
            manager.initialize()
            results = manager.search_sop("fix a bug in Python code")
            # May return empty list if no SOPs exist yet
            assert isinstance(results, list)
        finally:
            manager.close()
