StripFeat Plugin
================

The ``stripfeat`` plugin automatically removes the "featured artist" token from
the ``artist`` or ``albumartist`` field and replaces it with a delimiter of your
choice.

To use the ``stripfeat`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``stripfeat:`` section in your configuration
file. The available options are:

- **auto**: Enable metadata rewriting during import. Default: ``yes``.
- **delimiter**: Defines the delimiter you want to replace the "featured artist"
      token with. Default: ``;``.
- **strip_from_album_artist**: Also replace "featured artist" token in the
      ``albumartist`` field. Default: ``no``.

Running Manually
----------------

From the command line, type:

::

    $ beet stripfeat [QUERY]

The query is optional; if it's left off, the transformation will be applied to
your entire collection.

Use the ``-a`` flag to also apply to the ``albumartist`` field (equivalent of
the ``strip_from_album_artist`` config option).
