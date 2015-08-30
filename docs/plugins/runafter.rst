Run After Plugin
================

The ``runafter`` plugin adds the option to run arbitrary shell scripts upon
certain events. Currently this is only possible for the import-finished event.
Support for other events might follow in the future.

Configuration
-------------

First, enable the ``runafter`` plugin (see :ref:`using-plugins`). After that you
can add the ``runafter`` section to your config file::

    runafter:
        import: '/path/to/script'

Make sure to have the correct permissions set in order to execute the script.
