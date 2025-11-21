"""Tests for the 'version' command."""

from platform import python_version
from unittest.mock import patch

import beets
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.version import show_version


class VersionTest(IOMixin, BeetsTestCase):
    """Tests for the version command."""

    def setUp(self):
        super().setUp()

    def test_show_version_basic(self):
        """Test that show_version displays beets and Python versions."""
        show_version()

        output = self.io.getoutput()
        assert f"beets version {beets.__version__}" in output
        assert f"Python version {python_version()}" in output

    def test_show_version_with_plugins(self):
        """Test that show_version displays loaded plugins."""
        # Mock plugins.find_plugins to return some test plugins
        with patch("beets.plugins.find_plugins") as mock_find:
            # Create mock plugin objects with name attribute
            class MockPlugin:
                def __init__(self, name):
                    self.name = name

            mock_find.return_value = [
                MockPlugin("plugin1"),
                MockPlugin("plugin2"),
                MockPlugin("plugin3"),
            ]

            show_version()

            output = self.io.getoutput()
            assert "plugins:" in output
            assert "plugin1" in output
            assert "plugin2" in output
            assert "plugin3" in output

    def test_show_version_no_plugins(self):
        """Test that show_version shows 'no plugins' when none are loaded."""
        # Mock plugins.find_plugins to return empty list
        with patch("beets.plugins.find_plugins") as mock_find:
            mock_find.return_value = []

            show_version()

            output = self.io.getoutput()
            assert "no plugins loaded" in output
            assert "plugins:" not in output

    def test_show_version_plugins_sorted(self):
        """Test that plugins are displayed in sorted order."""
        # Mock plugins.find_plugins to return unsorted plugins
        with patch("beets.plugins.find_plugins") as mock_find:
            # Create mock plugin objects with name attribute
            class MockPlugin:
                def __init__(self, name):
                    self.name = name

            # Return plugins in unsorted order
            mock_find.return_value = [
                MockPlugin("zebra"),
                MockPlugin("alpha"),
                MockPlugin("beta"),
            ]

            show_version()

            output = self.io.getoutput()
            # Check that plugins appear in sorted order
            assert "plugins: alpha, beta, zebra" in output

    def test_show_version_accepts_args(self):
        """Test that show_version accepts arbitrary arguments (for command interface)."""
        # The function signature is show_version(*args) to accept command args
        show_version("arg1", "arg2", "arg3")

        output = self.io.getoutput()
        # Should still display version info regardless of args
        assert f"beets version {beets.__version__}" in output
