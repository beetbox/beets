IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. You specify queries (see
:doc:`/reference/query`) and the plugin skips (or warns about) albums or items
that match any query.

To use the plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-----------

Available options ::

- ``skip``: never import matches. Default: ``[]`
- ``warn``: print a warning message for matches. Default: ``[]``


Here's an example ::

    ihate:
        warn:
            - artist:rnb
            - genre: soul
            # Only warn about tribute albums in rock genre.
            - genre:rock album:tribute
        skip:
            - genre::russian\srock
            - genre:polka
            - artist:manowar
            - album:christmas

The plugin trusts your decision in "as-is" imports.
