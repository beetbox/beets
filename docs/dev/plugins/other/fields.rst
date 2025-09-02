Flexible Field Types
====================

If your plugin uses flexible fields to store numbers or other non-string values,
you can specify the types of those fields. A rating plugin, for example, might
want to declare that the ``rating`` field should have an integer type:

.. code-block:: python

    from beets.plugins import BeetsPlugin
    from beets.dbcore import types


    class RatingPlugin(BeetsPlugin):
        item_types = {"rating": types.INTEGER}

        @property
        def album_types(self):
            return {"rating": types.INTEGER}

A plugin may define two attributes: ``item_types`` and ``album_types``. Each of
those attributes is a dictionary mapping a flexible field name to a type
instance. You can find the built-in types in the ``beets.dbcore.types`` and
``beets.library`` modules or implement your own type by inheriting from the
``Type`` class.

Specifying types has several advantages:

- Code that accesses the field like ``item['my_field']`` gets the right type
  (instead of just a string).
- You can use advanced queries (like :ref:`ranges <numericquery>`) from the
  command line.
- User input for flexible fields may be validated and converted.
- Items missing the given field can use an appropriate null value for querying
  and sorting purposes.
