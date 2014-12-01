Zero Plugin
===========

The ``zero`` plugin allows you to null fields in files' metadata tags. Fields
can be nulled unconditionally or conditioned on a pattern match. For example,
the plugin can strip useless comments like "ripped by MyGreatRipper." This
plugin only affects files' tags ; the beets database is left unchanged.

To use the ``zero`` plugin, enable the plugin in your configuration
(see :ref:`using-plugins`).

Configuration
-------------

Make a ``zero:`` section in your configuration file. You can specify the
fields to nullify and the conditions for nullifying them:

* Set ``fields`` to a whitespace-separated list of fields to change. You can
  get the list of all available fields by running ``beet fields``. In
  addition, the ``images`` field allows you to remove any images
  embedded in the media file.
* To conditionally filter a field, use ``field: [regexp, regexp]`` to specify
  regular expressions.

For example::

    zero:
        fields: month day genre comments
        comments: [EAC, LAME, from.+collection, 'ripped by']
        genre: [rnb, 'power metal']

If a custom pattern is not defined for a given field, the field will be nulled
unconditionally.

Note that the plugin currently does not zero fields when importing "as-is".
