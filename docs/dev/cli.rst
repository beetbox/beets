Providing a CLI
===============

The ``beets.ui`` module houses interactions with the user via a terminal, the
:doc:`/reference/cli`.
The main function is called when the user types beet on the command line.
The CLI functionality is organized into commands, some of which are built-in
and some of which are provided by plugins. The built-in commands are all
implemented in the ``beets.ui.commands`` submodule.
