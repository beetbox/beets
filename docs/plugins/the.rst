The Plugin
==========

The ``the`` plugin allows you to move patterns in path formats. It's suitable,
for example, for moving articles from string start to the end. This is useful
for quick search on filesystems and generally looks good. Plugin DOES NOT
change tags. By default plugin supports English "the, a, an", but custom
regexp patterns can be added by user. How it works::

    The Something -> Something, The
    A Band -> Band, A
    An Orchestra -> Orchestra, An

Enable the ``the`` plugin (see :doc:`/plugins/index`) and then make use of a
template function called ``%the`` for use in path format expressions::

    paths:
        default: %the{$albumartist}/($year) $album/$track $title

The default configuration moves all English articles to the end of the string,
but you can override these defaults to make more complex changes.

Configuration
-------------

Available options:

- ``a``: handle "A/An" moves
  Default: ``yes``
- ``format``: format string with *{0}: part w/o article* and *{1} - article*.
  Spaces are already trimmed from ends of both parts.
  Default: ``u'{0}, {1}'``
- ``strip``:
  Default: ``no``
- ``patterns``: custom regexp patterns, space-separated. Custom patterns are
  case-insensitive regular expressions. Patterns can be matched anywhere in the
  string (not just the beginning), so use ``^`` if you intend to match leading
  words.
  Default: ``[]``
- ``the``: handle "The" moves
  Default: ``yes``

