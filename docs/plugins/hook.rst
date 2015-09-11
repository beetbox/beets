Hook Plugin
===============

Internally, beets sends events to plugins when an action finishes. These can
range from importing a song (``import``) to beets exiting (``cli_exit``), and
provide a very flexible way to perform actions based on the events. This plugin
allows you to run commands when an event is emitted by beets, such as syncing
your library with another drive when the library is updated.

Hooks are currently run in the order defined in the configuration, however this
is dependent on beets itself (may change in the future) and cannot be controlled
by this plugin.

.. _hook-configuration:

Configuration
-------------

To configure the plugin, make a ``hook:`` section in your configuration
file. The available options are:

- **hooks**: A list of events and the commands to run (see :ref:`individual-hook-configuration`)
  Default: Empty.
- **substitute_event**: The string to replace in each command with the name of
  the event executing it. This can be used to allow one script to act
  differently depending on the event it was called by. Can be individually
  overridden (see :ref:`individual-hook-configuration`).
  Default: ``%EVENT%``
- **shell**: Run each command in a shell. Can be individually overridden (see
  :ref:`individual-hook-configuration`).
  Default: ``yes``

.. _individual-hook-configuration:

Individual Hook Configuration
-----------------------------

Each element of the ``hooks`` configuration option can be configured separately.
The available options are:

- **event** (required): The name of the event that should cause this hook to execute. See
  :ref:`Plugin Events <plugin_events>` for a list of possible values.
- **command** (required): The command to run when this hook executes.
- **substitute_event**: Hook-level override for ``substitute_event`` option in
  :ref:`hook-configuration`.
  Default: Value of top level ``substitute_event`` option (see :ref:`hook-configuration`)
- **shell**: Hook-level override for ``shell`` option in :ref:`hook-configuration`.
  Default: Value of top level ``shell`` option (see :ref:`hook-configuration`).
- **substitute_args**: A key/value set where the key is the name of the an
  argument passed to the event (see :ref:`Plugin Events <plugin_events>` for
  a list of arguments for each event) and the value is the string to replace
  in the command with the value of the argument. Note that any arguments that
  are not strings will be converted to strings (e.g. Python objects).
  Default: Empty.

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

        # Output on write
        #   writing to "<file_name_here>"
        # Where <file_name_here> is the file being written to
        - event: write
          command echo "writing to \"%FILE_NAME%\""
          substitute_args:
            path: %FILE_NAME%
