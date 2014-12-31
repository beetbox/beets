IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. You specify queries (see
:doc:`/reference/query`) and the plugin skips (or warns about) albums or items
that match any query. You can also specify regular expressions to filter files
to import regarding of their path and name.

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
- **path**: A regular expression to filter files based on its path and name.
  Default: ``.*`` (everything)
- **album_path** and **singleton_path**: You may specify different regular
  expressions used for imports of albums and singletons. This way, you can
  automatically skip singletons when importing albums if the names (and paths)
  of the files are distinguishable via a regex. The path regex defined here
  take precedence over the global ``path`` option.

Here's an example::

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
        path: .*\d\d[^/]+$
              # will only import files which names start with two digits
        album_path: .*\d\d[^/]+$
        singleton_path: .*/(?!\d\d)[^/]+$

The plugin trusts your decision in "as-is" imports.

