.. _plugin-logging:

Logging
=======

Each plugin object has a ``_log`` attribute, which is a ``Logger`` from the
`standard Python logging module`_. The logger is set up to `PEP 3101`_,
str.format-style string formatting. So you can write logging calls like this:

.. code-block:: python

    self._log.debug("Processing {0.title} by {0.artist}", item)

.. _pep 3101: https://www.python.org/dev/peps/pep-3101/

.. _standard python logging module: https://docs.python.org/3/library/logging.html

When beets is in verbose mode, plugin messages are prefixed with the plugin name
to make them easier to see.

Which messages will be logged depends on the logging level and the action
performed:

- Inside import stages and event handlers, the default is ``WARNING`` messages
  and above.
- Everywhere else, the default is ``INFO`` or above.

The verbosity can be increased with ``--verbose`` (``-v``) flags: each flags
lowers the level by a notch. That means that, with a single ``-v`` flag, event
handlers won't have their ``DEBUG`` messages displayed, but command functions
(for example) will. With ``-vv`` on the command line, ``DEBUG`` messages will be
displayed everywhere.

This addresses a common pattern where plugins need to use the same code for a
command and an import stage, but the command needs to print more messages than
the import stage. (For example, you'll want to log "found lyrics for this song"
when you're run explicitly as a command, but you don't want to noisily interrupt
the importer interface when running automatically.)
