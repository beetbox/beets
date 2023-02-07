Substitute Plugin
==============

The ``substitute`` plugin lets you easily substitute values in your templates and
path formats. Specifically, it is intended to let you *canonicalize* names
such as artists: for example, perhaps you want albums from The Jimi Hendrix
Experience to be sorted into the same folder as solo Hendrix albums.

To use field substituting, first enable the ``substitute`` plugin
(see :ref:`using-plugins`).
Then, make a ``substitute:`` section in your config file to contain your rules.
Each rule consists of a a regular expression pattern, and a
replacement value. Rules are written ``regex: replacement``.
For example, this line implements the Jimi Hendrix example above::

    rewrite:
        The Jimi Hendrix Experience: Jimi Hendrix

The pattern is a case-insensitive regular expression. This means you can use
ordinary regular expression syntax to match multiple artists. For example, you
might use::

    rewrite:
        .*jimi hendrix.*: Jimi Hendrix

This plugin is intented as a replacement for the ``rewrite`` plugin. Indeed, while
the ``rewrite`` plugin modifies the metadata, this plugin does not.
