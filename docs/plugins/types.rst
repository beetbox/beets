Types Plugin
============

The ``types`` plugin lets you declare types for attributes you use in your
library. For example, you can declare that a ``rating`` field is numeric so
that you can query it with ranges---which isn't possible when the field is
considered a string (the default).

Enable the ``types`` plugin as described in :doc:`/plugins/index` and then add
a ``types`` section to your :doc:`configuration file </reference/config>`. The
configuration section should map field name to one of ``int``, ``float``,
``bool``, or ``date``.

Here's an example::

    types:
        rating: int

Now you can assign numeric ratings to tracks and albums and use :ref:`range
queries <numericquery>` to filter them.::

    beet modify "My favorite track" rating=5
    beet ls rating:4..5

    beet modify --album "My favorite album" rating=5
    beet ls --album rating:4..5
