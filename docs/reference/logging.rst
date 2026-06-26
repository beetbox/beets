Logging
=======

Beets implements a flexible logging solution and ships multiple built-in modes.
You can select a mode from the command line for quick control, or define and
customize modes in the configuration file for more advanced setups.

Use the ``--logging <mode>`` option to select a logging mode for a single
invocation of any beets command. For example, to run the import command in debug
mode, you could do:

.. code-block:: console

    beets --logging debug import music/

.. note::

    The command-line option overrides any logging mode configured in the
    configuration file.

If you want to persist a logging mode across multiple invocations of beets, you
can define a mode in the configuration file. For example, to set the default
logging mode to ``debug``, you could add the following to your configuration
file:

.. code-block:: yaml
    :caption: config.yaml

    logging: debug

.. note::

    Invalid logging modes will be ignored, and beets will fall back to the
    default mode.

Build-in modes
--------------

Beets ships with several built-in logging modes. The following table summarizes
the available modes and their characteristics:

.. conf:: legacy

    The default mode for ``beets<v3.0.0``. Logs messages as plain text with a simple prefix indicating a plugin name.


    .. code-block:: console

        <plugin>: <message>
        TODO Add a real output

.. conf:: verbose

    The default logging mode for ``beets>=v3.0.0``.

    This mode explains what beets is doing in a more explicit way than
    ``legacy``, including key decisions such as matching, tagging, and
    file operations, without exposing full internal debug information.

    .. code-block:: console

        [<level:Info+>] <logger>: <message>
        TODO Add a real output


    This mode aims to be the recommended default for users on beets 3.0+ as it improves transparency while keeping output readable.

.. conf:: quiet

    Suppresses informational output and only displays warnings and errors.

    This mode is useful when running beets in scripts or when you want to minimize console output while still being notified of important issues.

    .. code-block:: console

        [<level:Warning+>] <logger>: <message>
        TODO Add a real output

.. conf:: debug

    Enables verbose diagnostic logging for both core functionality and plugins.

    This mode includes timestamps, log levels, and logger names, making it
    useful for debugging and development.

    .. code-block:: console

        <time> [<level:Debug+>] <logger>: <message> (<filename>:<line number>)
        TODO Add a real output

    Be warned, this mode may produce a large volume of output, especially when
    plugins with extensive logging are enabled.

Custom modes
------------

While the built-in modes should cover most use cases, having more control over
the logging configuration can be useful. Beets allows you to define custom
logging modes in the configuration file.

Custom modes are defined using Python’s standard logging configuration
dictionary schema. This gives you full access to handlers, formatters, filters,
and logger configuration options as described in the `Python logging
documentation
<https://docs.python.org/3/library/logging.config.html#logging-config-dictschema>`_.

.. code-block:: yaml
    :caption: config.yaml: Example custom logging mode

    loggging: my_mode

    logging_modes:
        my_mode:
            version: 1
            formatters:
                detailed:
                    format: "[%(levelname)s] %(name)s: %(message)s"

            handlers:
                console:
                    class: logging.StreamHandler
                    level: DEBUG
                    formatter: detailed
                    stream: ext://sys.stdout

            root:
                level: DEBUG
                handlers: [console]

What about the current ``print`` calls?
---------------------------------------

Will remove this section or rewrite it (just for discussion right now).

``print`` statements should only be used in the ``ui`` layer and are not part of
the logging system.

Unlike log messages, output from the UI layer is always shown regardless of the
active logging mode. This ensures that essential user-facing interaction is
never hidden or filtered by logging configuration.

The UI layer is intended for direct user communication, such as:

- prompts and confirmations
- interactive questions
- critical status messages that require immediate attention
- explicit user-facing feedback during command execution

In other words, the UI layer represents the *communication interface* of beets,
while the logging system represents *diagnostic and operational telemetry*.

What to do with the ``-v`` options?
-----------------------------------

Will remove this section or rewrite it (just for discussion right now).

We still have the ``-v`` option to enable verbosity but it is currently a bit
inconsistent. What I would propose is the follow

.. list-table::
    :header-rows: 1
    :widths: 15 85

    - - Flag
      - Effect
    - - (none)
      - Uses the default level defined by the active logging mode (e.g. ``INFO``
        in ``legacy``).
    - - ``-v``
      - Increases verbosity to ``INFO`` if the current level is lower. Has no
        effect if the mode is already more verbose.
    - - ``-vv``
      - Forces ``DEBUG`` level output across the application (``beets`` logger)
    - - ``-vvv``
      - Enables maximum verbosity, including extended diagnostic output from
        (all loggers).
