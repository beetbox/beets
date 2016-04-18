Hook Plugin
===============

Internally, beets sends events to plugins when an action finishes. These can
range from importing a song (``import``) to beets exiting (``cli_exit``), and
provide a very flexible way to perform actions based on the events. This plugin
allows you to run commands when an event is emitted by beets, such as syncing
your library with another drive when the library is updated.

Hooks are currently run in the order defined in the configuration, however this
is dependent on beets itself and it's consistency should not be depended upon.

.. _hook-configuration:

Configuration
-------------

To configure the plugin, make a ``hook`` section in your configuration
file. The available options are:

- **hooks**: A list of events and the commands to run
  (see :ref:`individual-hook-configuration`). Default: Empty.

.. _individual-hook-configuration:

Individual Hook Configuration
-----------------------------

Each element of the ``hooks`` configuration option can be configured separately.
The available options are:

- **event**: The name of the event that should cause this hook to
  execute. See the :ref:`plugin events <plugin_events>` documentation for a list
  of possible values.
- **command**: The command to run when this hook executes.

.. _command-substitution:

Command Substitution
--------------------

Certain key words can be replaced in commands, allowing access to event
information such as the path of an album or the name of a song. This information
is accessed using the syntax ``{property_name}``, where ``property_name`` is the
name of an argument passed to the event. ``property_name`` can also be a key on
an argument passed to the event, such as ``{album.path}``.

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
