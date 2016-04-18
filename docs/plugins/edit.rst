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

Interactive Usage
-----------------

The ``edit`` plugin can also be invoked during an import session. If enabled, it
adds two new options to the user prompt::

    [A]pply, More candidates, Skip, Use as-is, as Tracks, Group albums, Enter search, enter Id, aBort, eDit, edit Candidates?

- ``eDit``: use this option for using the original items' metadata as the
  starting point for your edits.
- ``edit Candidates``: use this option for using a candidate's metadata as the
  starting point for your edits.

Please note that currently the interactive usage of the plugin will only allow
you to change the item-level fields. In case you need to edit the album-level
fields, the recommended approach is to invoke the plugin via the command line
in album mode (``beet edit -a QUERY``) after the import.

Also, please be aware that the ``edit Candidates`` choice can only be used with
the matches found during the initial search (and currently not supporting the
candidates found via the ``Enter search`` or ``enter Id`` choices). You might
find the ``--search-id SEARCH_ID`` :ref:`import-cmd` option useful for those
cases where you already have a specific candidate ID that you want to edit.

Configuration
-------------

To configure the plugin, make an ``edit:`` section in your configuration
file. The available options are:

- **itemfields**: A space-separated list of item fields to include in the
  editor by default.
  Default: ``track title artist album``
- **albumfields**: The same when editing albums (with the ``-a`` option).
  Default: ``album albumartist``
