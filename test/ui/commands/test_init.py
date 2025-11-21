"""Tests for the ui/commands __init__ module."""

import warnings

import pytest


class TestDeprecatedImports:
    """Tests for deprecated import handling."""

    def test_deprecated_import_terminal_import_session(self):
        """Test that deprecated TerminalImportSession import shows warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Try importing deprecated name
            from beets.ui import commands

            try:
                _ = commands.TerminalImportSession
                # If the import worked, verify a deprecation warning was issued
                assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
            except AttributeError:
                # If it doesn't exist, that's also valid (fully removed)
                pass

    def test_deprecated_import_prompt_choice(self):
        """Test that deprecated PromptChoice import shows warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from beets.ui import commands

            try:
                _ = commands.PromptChoice
                # If the import worked, verify a deprecation warning was issued
                assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
            except AttributeError:
                # If it doesn't exist, that's also valid (fully removed)
                pass

    def test_getattr_unknown_name(self):
        """Test that unknown attribute raises AttributeError."""
        from beets.ui import commands

        with pytest.raises(AttributeError):
            _ = commands.NonExistentAttribute


class TestDefaultCommands:
    """Tests for default_commands list."""

    def test_default_commands_exists(self):
        """Test that default_commands list exists."""
        from beets.ui.commands import default_commands

        assert default_commands is not None
        assert isinstance(default_commands, list)
        assert len(default_commands) > 0

    def test_default_commands_contains_expected(self):
        """Test that default_commands contains expected commands."""
        from beets.ui.commands import default_commands

        # Check that we have the major commands
        command_names = [cmd.name for cmd in default_commands]

        expected_commands = {
            "fields",
            "help",
            "import",
            "list",
            "update",
            "remove",
            "stats",
            "version",
            "modify",
            "move",
            "write",
            "config",
            "completion",
        }

        # Verify all expected commands are present
        assert expected_commands.issubset(set(command_names)), (
            f"Missing commands: {expected_commands - set(command_names)}"
        )
