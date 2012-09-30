Zero Plugin
===========

The ``zero`` plugin allows you to null fields before writing tags to files.
Fields can be nulled unconditionally or by pattern match. For example, it can
be used to strip useless comments like "ripped by" etc or any other stuff you
hate. Library is not modified.

To use plugin, enable it by including ``zero`` into ``plugins`` line of
your beets config::

    [beets]
    plugins = zero

To configure the plugin, use a ``[zero]`` section in your configuration file.
Set ``fields`` to the (whitespace-separated) list of fields to null. You can get
the list of available fields by running ``beet fields``. To conditionally filter
a field, use ``field=regexp regexp`` to specify regular expressions.

For example::

    [zero]
    fields=month day genre comments
    # Custom regexp patterns for each field, separated by spaces:
    comments=EAC LAME from.+collection ripped\sby
    genre=rnb power\smetal

If custom pattern is not defined, field will be nulled unconditionally. Note
that the plugin currently does not zero fields when importing "as-is".
