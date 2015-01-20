FileFilter Plugin
=================

The ``regexfilefilter`` plugin allows you to skip files during import using
regular expressions.

To use the ``regexfilefilter`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make an ``regexfilefilter:`` section in your
configuration file. The available options are:

- **path**: A regular expression to filter files based on its path and name.
  Default: ``.*`` (everything)
- **album_path** and **singleton_path**: You may specify different regular
  expressions used for imports of albums and singletons. This way, you can
  automatically skip singletons when importing albums if the names (and paths)
  of the files are distinguishable via a regex. The regexes defined here
  take precedence over the global ``path`` option.

Here's an example::

    regexfilefilter:
        path: .*\d\d[^/]+$
              # will only import files which names start with two digits
        album_path: .*\d\d[^/]+$
        singleton_path: .*/(?!\d\d)[^/]+$
