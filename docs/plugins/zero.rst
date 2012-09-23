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

You need to configure plugin before use, so add following section into config
file and adjust it to your needs::

    [zero]
    # list of fields to null, you can get full list by running 'beet fields'
    fields=month day genre comments
    # custom regexp patterns for each field, separated by space
    # if custom pattern is not defined, field will be nulled unconditionally
    comments=EAC LAME from.+collection ripped\sby
    genre=rnb power\smetal

  Note: for now plugin will not zero fields in 'as-is' mode.
  