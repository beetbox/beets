Nonsense Plugin
=================

The ``nonsense`` plugin prints a random quote after every beets command
finishes. For example, after ``beet ls someTerm`` lists matching tracks, a
quote appears on the following line.

Installation
------------

This plugin depends on the `quotes-generator`_ package. Install it with beets'
optional extra:

.. code-block:: sh

    pip install "beets[nonsense]"

Configuration
-------------

To use the plugin, enable it in your configuration (see :ref:`using-plugins`):

.. code-block:: yaml

    plugins: nonsense

You can optionally pin the quote source to a specific category:

.. code-block:: yaml

    nonsense:
        source: motivational

When ``source`` is omitted, the plugin picks a random category on each run.
Available values are:

- ``motivational``
- ``albert_einstein``
- ``mahatma_gandhi``
- ``steve_jobs``
- ``bill_gates``
- ``elon_musk``
- ``mark_zuckerberg``

Example
-------

.. code-block:: sh

    $ beet ls artist:beatles
    /music/Beatles/Abbey Road/01 Come Together
    /music/Beatles/Abbey Road/02 Something
    And in the end, the love you take is equal to the love you make.

.. _quotes-generator: https://pypi.org/project/quotes-generator/
