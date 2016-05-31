Export Plugin
=============

The ``export`` plugin lets you get data from the items and export the content
as `JSON`_.

.. _JSON: http://www.json.org

Enable the ``export`` plugin (see :ref:`using-plugins` for help). Then, type ``beet export`` followed by a :doc:`query </reference/query>` to get the data from
your library. For example, run this::

    $ beet export beatles

to print a JSON file containing information about your Beatles tracks.

Command-Line Options
--------------------

The ``export`` command has these command-line options:

* ``--include-keys`` or ``-i``: Choose the properties to include in the output
  data. The argument is a comma-separated list of simple glob patterns where
  ``*`` matches any string. For example::

      $ beet export -i 'title,mb*' beatles

  will include the ``title`` property and all properties starting with
  ``mb``. You can add the ``-i`` option multiple times to the command
  line.

* ``--library`` or ``-l``: Show data from the library database instead of the
  files' tags.

* ``--output`` or ``-o``: Path for an output file. If not informed, will print
  the data in the console.

* ``--append``: Appends the data to the file instead of writing.

Configuration
-------------

To configure the plugin, make a ``export:`` section in your configuration
file. Under the ``json`` key, these options are available:

- **ensure_ascii**: Escape non-ASCII characters with `\uXXXX` entities.

- **indent**: The number of spaces for indentation.

- **separators**: A ``[item_separator, dict_separator]`` tuple.

- **sort_keys**: Sorts the keys in JSON dictionaries.

These options match the options from the `Python json module`_.

.. _Python json module: https://docs.python.org/2/library/json.html#basic-usage

The default options look like this::

    export:
        json:
            formatting:
                ensure_ascii: False
                indent: 4
                separators: [',' , ': ']
                sort_keys: true
