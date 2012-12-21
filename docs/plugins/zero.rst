Zero Plugin
===========

The ``zero`` plugin allows you to null fields in files' metadata tags. Fields
can be nulled unconditionally or conditioned on a pattern match. For example,
the plugin can strip useless comments like "ripped by MyGreatRipper." This
plugin only affects files' tags; the beets database is unchanged.

To use plugin, enable it by including ``zero`` into ``plugins`` line of your
configuration file. To configure the plugin, use a ``zero:`` section in your
configuration file. Set ``fields`` to the (whitespace-separated) list of fields
to change. You can get the list of available fields by running ``beet fields``.
To conditionally filter a field, use ``field: [regexp, regexp]`` to specify
regular expressions.

For example::

    zero:
        fields: month day genre comments
        comments: [EAC, LAME, from.+collection, 'ripped by']
        genre: [rnb, 'power metal']

If custom pattern is not defined for a given field, the field will be nulled
unconditionally.

Note that the plugin currently does not zero fields when importing "as-is".
