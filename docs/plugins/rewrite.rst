Rewrite Plugin
==============

The ``rewrite`` plugin lets you easily substitute values in your path formats.
Specifically, it is intended to let you *canonicalize* names such as artists:
for example, perhaps you want albums from The Jimi Hendrix Experience to be
sorted into the same folder as solo Hendrix albums.

To use field rewriting, first enable the plugin by putting ``rewrite``
on your ``plugins`` line::

    [beets]
    plugins: rewrite

Then, make a ``[rewrite]`` section in your config file to contain your rewrite
rules. Each rule consists of a field name, a regular expression pattern, and a
replacement value. Rules are written ``fieldname regex: replacement``. For
example, this line implements the Jimi Hendrix example above::

    [rewrite]
    artist The Jimi Hendrix Experience: Jimi Hendrix

This will make ``$artist`` in your path formats expand to "Jimi Henrix" where it
would otherwise be "The Jimi Hendrix Experience".

The pattern is a case-insensitive regular expression. This means you can use
ordinary regular expression syntax to match multiple artists. For example, you
might use::

    [rewrite]
    artist .*jimi hendrix.*: Jimi Hendrix

As a convenience, the plugin applies patterns for the ``artist`` field to the
``albumartist`` field as well. (Otherwise, you would probably want to duplicate
every rule for ``artist`` and ``albumartist``.)

Note that this plugin only applies to path templating; it does not modify files'
metadata tags or the values tracked by beets' library database.
