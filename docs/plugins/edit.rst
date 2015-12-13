Edit Plugin
===========

The ``edit`` plugin lets you modify music metadata using your favorite text
editor.

Enable the ``edit`` plugin in your configuration (see :ref:`using-plugins`) and
then type::

     beet edit QUERY

Your text editor (i.e., the command in your ``$EDITOR`` environment variable)
will open with a list of tracks to edit. Make your changes and exit your text
editor to apply them to your music.

Command-Line Options
--------------------

The ``edit`` command has these command-line options:

- ``-a`` or ``--album``: Edit albums instead of individual items.
- ``-f FIELD`` or ``--field FIELD``: Specify an additional field to edit
  (in addition to the defaults set in the configuration).
- ``--all``: Edit *all* available fields.

Configuration
-------------

To configure the plugin, make an ``edit:`` section in your configuration
file. The available options are:

- **itemfields**: A space-separated list of item fields to include in the
  editor by default.
  Default: ``track title artist album``
- **albumfields**: The same when editing albums (with the ``-a`` option).
  Default: ``album albumartist``
