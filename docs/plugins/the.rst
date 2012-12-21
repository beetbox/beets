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

To use plugin, enable it by including ``the`` into ``plugins`` line of your
beets config. The plugin provides a template function called ``%the`` for use
in path format expressions::

    paths:
        default: %the{$albumartist}/($year) $album/$track $title

The default configuration moves all English articles to the end of the string,
but you can override these defaults to make more complex changes::

    the:
        # handle The, default is on
        the=yes
        # handle A/An, default is on
        a=yes
        # format string, {0} - part w/o article, {1} - article
        # spaces already trimmed from ends of both parts
        # default is '{0}, {1}'
        format={0}, {1}
        # strip instead of moving to the end, default is off
        strip=no
        # custom regexp patterns, separated by space
        patterns=

Custom patterns are case-insensitive regular expressions. Patterns can be
matched anywhere in the string (not just the beginning), so use ``^`` if you
intend to match leading words.
