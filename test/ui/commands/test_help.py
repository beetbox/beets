"""Tests for the 'help' command."""

from unittest.mock import Mock

import pytest

from beets import ui
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.help import HelpCommand


class HelpCommandTest(IOMixin, BeetsTestCase):
    """Tests for the help command."""

    def setUp(self):
        super().setUp()
        self.help_cmd = HelpCommand()

    def test_help_command_init(self):
        """Test that HelpCommand initializes with correct name and alias."""
        assert self.help_cmd.name == "help"
        assert "?" in self.help_cmd.aliases
        assert "help" in self.help_cmd.help

    def test_help_no_args_prints_root_help(self):
        """Test that help with no arguments prints root parser help."""
        # Mock root_parser
        mock_root_parser = Mock()
        self.help_cmd.root_parser = mock_root_parser

        # Call func with no args
        self.help_cmd.func(self.lib, Mock(), [])

        # Verify print_help was called on root parser
        mock_root_parser.print_help.assert_called_once()

    def test_help_with_valid_command(self):
        """Test that help with a valid command prints that command's help."""
        # Create a mock subcommand
        mock_subcommand = Mock()
        mock_subcommand.print_help = Mock()

        # Mock root_parser to return the subcommand
        mock_root_parser = Mock()
        mock_root_parser._subcommand_for_name = Mock(
            return_value=mock_subcommand
        )
        self.help_cmd.root_parser = mock_root_parser

        # Call func with command name
        self.help_cmd.func(self.lib, Mock(), ["import"])

        # Verify _subcommand_for_name was called with correct arg
        mock_root_parser._subcommand_for_name.assert_called_once_with("import")
        # Verify print_help was called on the subcommand
        mock_subcommand.print_help.assert_called_once()

    def test_help_with_invalid_command_raises_error(self):
        """Test that help with an invalid command raises UserError."""
        # Mock root_parser to return None (command not found)
        mock_root_parser = Mock()
        mock_root_parser._subcommand_for_name = Mock(return_value=None)
        self.help_cmd.root_parser = mock_root_parser

        # Call func with invalid command name and expect UserError
        with pytest.raises(ui.UserError, match="unknown command.*nonexistent"):
            self.help_cmd.func(self.lib, Mock(), ["nonexistent"])

        # Verify _subcommand_for_name was called
        mock_root_parser._subcommand_for_name.assert_called_once_with(
            "nonexistent"
        )

    def test_help_alias_question_mark(self):
        """Test that '?' is a valid alias for help command."""
        assert "?" in self.help_cmd.aliases
