Rewrite Plugin
==============

The ``rewrite`` plugin lets you easily substitute values in your templates and
path formats. Specifically, it is intended to let you *canonicalize* names
such as artists: for example, perhaps you want albums from The Jimi Hendrix
Experience to be sorted into the same folder as solo Hendrix albums.

To use field rewriting, first enable the ``rewrite`` plugin
(see :ref:`using-plugins`).
Then, make a ``rewrite:`` section in your config file to contain your rewrite
rules. Each rule consists of a field name, a regular expression pattern, and a
replacement value. Rules are written ``fieldname regex: replacement``.
For example, this line implements the Jimi Hendrix example above::

    rewrite:
        artist The Jimi Hendrix Experience: Jimi Hendrix

This will make ``$artist`` in your templates expand to "Jimi Hendrix" where it
would otherwise be "The Jimi Hendrix Experience".

The pattern is a case-insensitive regular expression. This means you can use
ordinary regular expression syntax to match multiple artists. For example, you
might use::

    rewrite:
        artist .*jimi hendrix.*: Jimi Hendrix

As of v1.3.14 the replacement pattern may also consist of a regular expression
in order to back-reference matched substrings. For example, you might want to
replace certain characters in a tag. The following rewrite rule modifies the
title to replace a trailing year in parentheses with the trailing year in
brackets::

    rewrite:
        title (.*)\(([0-9]{4})\)$: '\1\[\2\]'

This example will transform Jimi Hendrix' ``$title`` "Hey Joe (1969)" to "Hey
Joe [1969]".

As a convenience, the plugin applies patterns for the ``artist`` field to the
``albumartist`` field as well. (Otherwise, you would probably want to duplicate
every rule for ``artist`` and ``albumartist``.)

Note that this plugin only applies to templating; it does not modify files'
metadata tags or the values tracked by beets' library database.
