Hook Plugin
===========

Internally, beets uses *events* to tell plugins when something happens. For
example, one event fires when the importer finishes processes a song, and
another triggers just before the ``beet`` command exits.
The ``hook`` plugin lets you run commands in response to these events.

.. _hook-configuration:

Configuration
-------------

To configure the plugin, make a ``hook`` section in your configuration
file. The available options are:

- **hooks**: A list of events and the commands to run
  (see :ref:`individual-hook-configuration`). Default: Empty.

.. _individual-hook-configuration:

Configuring Each Hook
'''''''''''''''''''''

Each element under ``hooks`` should have these keys:

- **event**: The name of the event that will trigger this hook.
  See the :ref:`plugin events <plugin_events>` documentation for a list
  of possible values.
- **command**: The command to run when this hook executes.

.. _command-substitution:

Command Substitution
''''''''''''''''''''

Commands can access the parameters of events using `Python string
formatting`_. Use ``{name}`` in your command and the plugin will substitute it
with the named value. The name can also refer to a field, as in
``{album.path}``.

.. _Python string formatting: https://www.python.org/dev/peps/pep-3101/

You can find a list of all available events and their arguments in the
:ref:`plugin events <plugin_events>` documentation.

Example Configuration
---------------------

.. code-block:: yaml

    hook:
      hooks:
        # Output on exit:
        #   beets just exited!
        #   have a nice day!
        - event: cli_exit
          command: echo "beets just exited!"
        - event: cli_exit
          command: echo "have a nice day!"

        # Output on item import:
        #   importing "<file_name_here>"
        # Where <file_name_here> is the item being imported
        - event: item_imported
          command: echo "importing \"{item.path}\""

        # Output on write:
        #   writing to "<file_name_here>"
        # Where <file_name_here> is the file being written to
        - event: write
          command: echo "writing to {path}"
