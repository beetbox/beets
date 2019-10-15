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

* ``--output`` or ``-o``: Path for an output file. If not informed, will print
  the data in the console.

* ``--append``: Appends the data to the file instead of writing.

* ``--format`` or ``-f``: Specifies the format the data will be exported as. If not informed, JSON will be used by default. The format options include csv, json and xml.

Configuration
-------------

To configure the plugin, make a ``export:`` section in your configuration
file. Under the ``json``, ``csv``, and ``xml`` keys, these options are available:

- **JSON Formatting**
    - **ensure_ascii**: Escape non-ASCII characters with ``\uXXXX`` entities.

    - **indent**: The number of spaces for indentation.

    - **separators**: A ``[item_separator, dict_separator]`` tuple.

    - **sort_keys**: Sorts the keys in JSON dictionaries.

- **CSV Formatting**
    - **delimiter**: Used as the separating character between fields. The default value is a comma (,).

    - **dialect**: A dialect, in the context of reading and writing CSVs, is a construct that allows you to create, store, and re-use various formatting parameters for your data.

- **XML Formatting**
    - **encoding**: Use encoding="unicode" to generate a Unicode string (otherwise, a bytestring is generated).

    - **xml_declaration**: Controls if an XML declaration should be added to the file. Use False for never, True for always, None for only if not US-ASCII or UTF-8 or Unicode (default is None).

    - **method**: Can be either "xml", "html" or "text" (default is "xml")

These options match the options from the `Python json module`_.

.. _Python json module: https://docs.python.org/2/library/json.html#basic-usage

The default options look like this::

    export:
        json:
            formatting:
                ensure_ascii: False
                indent: 4
                separators: [',' , ': ']
                sort_keys: True
        csv:
            formatting:
                delimiter: ','
                dialect: 'excel' 
        xml:
            formatting:
                encoding: 'unicode'
                xml_declaration: True
                method: 'xml'
