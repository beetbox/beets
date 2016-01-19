IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. You specify queries (see
:doc:`/reference/query`) and the plugin skips (or warns about) albums or items
that match any query.

To use the ``ihate`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make an ``ihate:`` section in your configuration
file. The available options are:

- **skip**: Never import items and albums that match a query in this list.
  Default: ``[]`` (empty list).
- **warn**: Print a warning message for matches in this list of queries.
  Default: ``[]``.

Here's an example::

    ihate:
        warn:
            - artist:rnb
            - genre:soul
            # Only warn about tribute albums in rock genre.
            - genre:rock album:tribute
        skip:
            - genre::russian\srock
            - genre:polka
            - artist:manowar
            - album:christmas

The plugin trusts your decision in "as-is" imports.
