The Plugin
==========

The ``the`` plugin allows you to move patterns in path formats. It's suitable,
for example, for moving articles from string start to the end. This is useful
for quick search on filesystems and generally looks good. Plugin does not
change tags. By default plugin supports English "the, a, an", but custom
regexp patterns can be added by user. How it works::

    The Something -> Something, The
    A Band -> Band, A
    An Orchestra -> Orchestra, An

To use the ``the`` plugin, enable it (see :doc:`/plugins/index`) and then use
a template function called ``%the`` in path format expressions::

    paths:
        default: %the{$albumartist}/($year) $album/$track $title

The default configuration moves all English articles to the end of the string,
but you can override these defaults to make more complex changes.

Configuration
-------------

To configure the plugin, make a ``the:`` section in your
configuration file. The available options are:

- **a**: Handle "A/An" moves.
  Default: ``yes``.
- **the**: handle "The" moves.
  Default: ``yes``.
- **patterns**: Custom regexp patterns, space-separated. Custom patterns are
  case-insensitive regular expressions. Patterns can be matched anywhere in the
  string (not just the beginning), so use ``^`` if you intend to match leading
  words.
  Default: ``[]``.
- **strip**: Remove the article altogether instead of moving it to the end.
  Default: ``no``.
- **format**: A Python format string for the output. Use ``{0}`` to indicate
  the part without the article and ``{1}`` for the article.
  Spaces are already trimmed from ends of both parts.
  Default: ``'{0}, {1}'``.
