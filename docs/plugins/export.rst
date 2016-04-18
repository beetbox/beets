Export Plugin
=============

The ``export`` plugin lets you get data from the items and export the content to
a ``json`` file.

Configuration
-------------
To configure the plugin, make a ``export:`` section in your configuration
file. The default options are::

  export:
    default_format: json
    json:
      formatting:
        ensure_ascii: False
        indent: 4
        separators: [',' , ': ']
        sort_keys: true

- **default_format**: Choose the format of the exported content.
  Supports json only for now.

Each format have their own options.

The ``json`` formatting uses the `json`_ standard library options.
Using custom options overwrites all options at the same level.
The default options used here are:

- **ensure_ascii**: All non-ASCII characters are escaped with `\uXXXX`, if true.

- **indent**: The number of spaces for indentation.

- **separators**: A ``(item_separator, dict_separator)`` tuple

- **sort_keys**: Sorts the keys of the json

.. _json: https://docs.python.org/2/library/json.html#basic-usage

Using
-----

Enable the ``export`` plugin (see :ref:`using-plugins` for help) and then add a
``export`` section to your :doc:`configuration file </reference/config>`

To use, you can enter a :doc:`query </reference/query>` to get the data from
your library::

    $ beet export beatles

If you just want to see specific properties you can use the
``--include-keys`` option to filter them. The argument is a
comma-separated list of simple glob patterns where ``*`` matches any
string. For example::

    $ beet export -i 'title,mb*' beatles

Will only show the ``title`` property and all properties starting with
``mb``. You can add the ``-i`` option multiple times to the command
line.

Additional command-line options include:

* ``--library`` or ``-l``: Show data from the library database instead of the
  files' tags.

* ``--output`` or ``-o``: Path for an output file. If not informed, will print
  the data in the console.

* ``--append``: Appends the data to the file instead of writing.
