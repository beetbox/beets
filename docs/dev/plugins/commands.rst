.. _add_subcommands:

Add Commands to the CLI
~~~~~~~~~~~~~~~~~~~~~~~

Plugins can add new subcommands to the ``beet`` command-line interface. Define
the plugin class' ``commands()`` method to return a list of ``Subcommand``
objects. (The ``Subcommand`` class is defined in the ``beets.ui`` module.)
Here's an example plugin that adds a simple command:

::

    from beets.plugins import BeetsPlugin
    from beets.ui import Subcommand

    my_super_command = Subcommand('super', help='do something super')
    def say_hi(lib, opts, args):
        print("Hello everybody! I'm a plugin!")
    my_super_command.func = say_hi

    class SuperPlug(BeetsPlugin):
        def commands(self):
            return [my_super_command]

To make a subcommand, invoke the constructor like so: ``Subcommand(name, parser,
help, aliases)``. The ``name`` parameter is the only required one and should
just be the name of your command. ``parser`` can be an `OptionParser instance`_,
but it defaults to an empty parser (you can extend it later). ``help`` is a
description of your command, and ``aliases`` is a list of shorthand versions of
your command name.

.. _optionparser instance: https://docs.python.org/library/optparse.html

You'll need to add a function to your command by saying ``mycommand.func =
myfunction``. This function should take the following parameters: ``lib`` (a
beets ``Library`` object) and ``opts`` and ``args`` (command-line options and
arguments as returned by OptionParser.parse_args_).

.. _optionparser.parse_args: https://docs.python.org/library/optparse.html#parsing-arguments

The function should use any of the utility functions defined in ``beets.ui``.
Try running ``pydoc beets.ui`` to see what's available.

You can add command-line options to your new command using the ``parser`` member
of the ``Subcommand`` class, which is a ``CommonOptionsParser`` instance. Just
use it like you would a normal ``OptionParser`` in an independent script. Note
that it offers several methods to add common options: ``--album``, ``--path``
and ``--format``. This feature is versatile and extensively documented, try
``pydoc beets.ui.CommonOptionsParser`` for more information.

