Add Path Format Functions and Fields
------------------------------------

Beets supports *function calls* in its path format syntax (see
:doc:`/reference/pathformat`). Beets includes a few built-in functions, but
plugins can register new functions by adding them to the ``template_funcs``
dictionary.

Here's an example:

.. code-block:: python

    class MyPlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.template_funcs["initial"] = _tmpl_initial


    def _tmpl_initial(text: str) -> str:
        if text:
            return text[0].upper()
        else:
            return ""

This plugin provides a function ``%initial`` to path templates where
``%initial{$artist}`` expands to the artist's initial (its capitalized first
character).

Plugins can also add template *fields*, which are computed values referenced as
``$name`` in templates. To add a new field, add a function that takes an
``Item`` object to the ``template_fields`` dictionary on the plugin object.
Here's an example that adds a ``$disc_and_track`` field:

.. code-block:: python

    class MyPlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.template_fields["disc_and_track"] = _tmpl_disc_and_track


    def _tmpl_disc_and_track(item: Item) -> str:
        """Expand to the disc number and track number if this is a
        multi-disc release. Otherwise, just expands to the track
        number.
        """
        if item.disctotal > 1:
            return "%02i.%02i" % (item.disc, item.track)
        else:
            return "%02i" % (item.track)

With this plugin enabled, templates can reference ``$disc_and_track`` as they
can any standard metadata field.

This field works for *item* templates. Similarly, you can register *album*
template fields by adding a function accepting an ``Album`` argument to the
``album_template_fields`` dict.
