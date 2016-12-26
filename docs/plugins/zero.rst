Zero Plugin
===========

The ``zero`` plugin allows you to null fields in files' metadata tags. Fields
can be nulled unconditionally or conditioned on a pattern match. For example,
the plugin can strip useless comments like "ripped by MyGreatRipper."

The plugin can work in one of two modes. The first mode, the default, is a
blacklist, where you choose the tags you want to remove. The second mode is a
whitelist, where you instead specify the tags you want to keep.

To use the ``zero`` plugin, enable the plugin in your configuration
(see :ref:`using-plugins`).

Configuration
-------------

Make a ``zero:`` section in your configuration file. You can specify the
fields to nullify and the conditions for nullifying them:

* Set ``auto`` to ``yes`` to null fields automatically on import.
  Default: ``yes``.
* Set ``fields`` to a whitespace-separated list of fields to change. You can
  get the list of all available fields by running ``beet fields``. In
  addition, the ``images`` field allows you to remove any images
  embedded in the media file.
* Set ``keep_fields`` to *invert* the logic of the plugin. Only these fields
  will be kept; other fields will be removed. Remember to set only
  ``fields`` or ``keep_fields``---not both!
* To conditionally filter a field, use ``field: [regexp, regexp]`` to specify
  regular expressions.
* By default this plugin only affects files' tags ; the beets database is left
  unchanged. To update the tags in the database, set the ``update_database`` option.

For example::

    zero:
        fields: month day genre comments
        comments: [EAC, LAME, from.+collection, 'ripped by']
        genre: [rnb, 'power metal']
        update_database: true

If a custom pattern is not defined for a given field, the field will be nulled
unconditionally.

Note that the plugin currently does not zero fields when importing "as-is".

Manually Triggering Zero
------------------------

You can also type ``beet zero [QUERY]`` to manually invoke the plugin on music
in your library.
