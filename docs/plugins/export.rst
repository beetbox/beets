Export Plugin
=============

The ``export`` plugin lets you get data from the items and export the content
as `JSON`_, `CSV`_, or `XML`_.

.. _JSON: https://www.json.org
.. _CSV: https://fileinfo.com/extension/csv
.. _XML: https://fileinfo.com/extension/xml

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

* ``--album`` or ``-a``: Show data from albums instead of tracks (implies
  ``--library``).

* ``--output`` or ``-o``: Path for an output file. If not informed, will print
  the data in the console.

* ``--append``: Appends the data to the file instead of writing.

* ``--format`` or ``-f``: Specifies the format the data will be exported as. If not informed, JSON will be used by default. The format options include csv, json, `jsonlines <https://jsonlines.org/>`_ and xml.

Configuration
-------------

To configure the plugin, make a ``export:`` section in your configuration
file.
For JSON export, these options are available under the ``json`` and
``jsonlines`` keys:

- **ensure_ascii**: Escape non-ASCII characters with ``\uXXXX`` entities.
- **indent**: The number of spaces for indentation.
- **separators**: A ``[item_separator, dict_separator]`` tuple.
- **sort_keys**: Sorts the keys in JSON dictionaries.

Those options match the options from the `Python json module`_.
Similarly, these options are available for the CSV format under the ``csv``
key:

- **delimiter**: Used as the separating character between fields. The default value is a comma (,).
- **dialect**: The kind of CSV file to produce. The default is `excel`.

These options match the options from the `Python csv module`_.

.. _Python json module: https://docs.python.org/2/library/json.html#basic-usage
.. _Python csv module: https://docs.python.org/3/library/csv.html#csv-fmt-params

The default options look like this::

    export:
        json:
            formatting:
                ensure_ascii: false
                indent: 4
                separators: [',' , ': ']
                sort_keys: true
        csv:
            formatting:
                delimiter: ','
                dialect: excel
