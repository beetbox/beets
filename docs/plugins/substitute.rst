Substitute Plugin
=================

The ``substitute`` plugin lets you easily substitute values in your templates and
path formats. Specifically, it is intended to let you *canonicalize* names
such as artists: For example, perhaps you want albums from The Jimi Hendrix
Experience to be sorted into the same folder as solo Hendrix albums.

This plugin is intended as a replacement for the ``rewrite`` plugin. While
the ``rewrite`` plugin modifies the metadata, this plugin does not.

Enable the ``substitute`` plugin (see :ref:`using-plugins`), then make a ``substitute:`` section in your config file to contain your rules.
Each rule consists of a case-insensitive regular expression pattern, and a
replacement value. For example, you might use:

    substitute:
        .*jimi hendrix.*: Jimi Hendrix


To apply the substitution, you have to call the function ``%substitute{}`` in the paths section. For example:
    
    paths:
        default: %substitute{$albumartist}/$year - $album%aunique{}/$track - $title