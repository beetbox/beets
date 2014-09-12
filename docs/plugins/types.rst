Types Plugin
============

The ``types`` plugin lets you declare types for attributes you use in your
library. For example, you can declare that a ``rating`` field is numeric so
that you can query it with ranges---which isn't possible when the field is
considered a string, which is the default.

Enable the plugin as described in :doc:`/plugins/index` and then add a
``types`` section to your :doc:`configuration file </reference/config>`. The
configuration section should map field name to one of ``int``, ``float``,
``bool``, or ``date``.

Here's an example:

    types:
        rating: int
