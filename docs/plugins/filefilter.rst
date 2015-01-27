FileFilter Plugin
=================

The ``filefilter`` plugin allows you to skip files during import using
regular expressions.

To use the ``filefilter`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``filefilter:`` section in your
configuration file. The available options are:

- **path**: A regular expression to filter files based on their path and name.
  Default: ``.*`` (import everything)
- **album_path** and **singleton_path**: You may specify different regular
  expressions used for imports of albums and singletons. This way, you can
  automatically skip singletons when importing albums if the names (and paths)
  of the files are distinguishable via a regex. The regexes defined here
  take precedence over the global ``path`` option.

Here's an example::

    filefilter:
        path: .*\d\d[^/]+$
              # will only import files which names start with two digits
        album_path: .*\d\d[^/]+$
        singleton_path: .*/(?!\d\d)[^/]+$
