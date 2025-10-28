Extending the Autotagger
========================

.. currentmodule:: beets.metadata_plugins

Beets supports **metadata source plugins**, which allow it to fetch and match
metadata from external services (such as Spotify, Discogs, or Deezer). This
guide explains how to build your own metadata source plugin by extending the
:py:class:`MetadataSourcePlugin`.

These plugins integrate directly with the autotagger, providing candidate
metadata during lookups. To implement one, you must subclass
:py:class:`MetadataSourcePlugin` and implement its abstract methods.

Overview
--------

Creating a metadata source plugin is very similar to writing a standard plugin
(see :ref:`basic-plugin-setup`). The main difference is that your plugin must:

1. Subclass :py:class:`MetadataSourcePlugin`.
2. Implement all required abstract methods.

Here`s a minimal example:

.. code-block:: python

    # beetsplug/myawesomeplugin.py
    from typing import Sequence
    from beets.autotag.hooks import Item
    from beets.metadata_plugin import MetadataSourcePlugin


    class MyAwesomePlugin(MetadataSourcePlugin):

        def candidates(
            self,
            items: Sequence[Item],
            artist: str,
            album: str,
            va_likely: bool,
        ): ...

        def item_candidates(self, item: Item, artist: str, title: str): ...

        def track_for_id(self, track_id: str): ...

        def album_for_id(self, album_id: str): ...

Each metadata source plugin automatically gets a unique identifier. You can
access this identifier using the :py:meth:`~MetadataSourcePlugin.data_source`
class property to tell plugins apart.

Metadata lookup
---------------

When beets runs the autotagger, it queries **all enabled metadata source
plugins** for potential matches:

- For **albums**, it calls :py:meth:`~MetadataSourcePlugin.candidates`.
- For **singletons**, it calls :py:meth:`~MetadataSourcePlugin.item_candidates`.

The results are combined and scored. By default, candidate ranking is handled
automatically by the beets core, but you can customize weighting by overriding:

- :py:meth:`~MetadataSourcePlugin.album_distance`
- :py:meth:`~MetadataSourcePlugin.track_distance`

This is optional, if not overridden, both methods return a constant distance of
`0.5`.

ID-based lookups
----------------

Your plugin must also define:

- :py:meth:`~MetadataSourcePlugin.album_for_id` — fetch album metadata by ID.
- :py:meth:`~MetadataSourcePlugin.track_for_id` — fetch track metadata by ID.

IDs are expected to be strings. If your source uses specific formats, consider
contributing an extractor regex to the core module:
:py:mod:`beets.util.id_extractors`.

Best practices
--------------

Beets already ships with several metadata source plugins. Studying these
implementations can help you follow conventions and avoid pitfalls. Good
starting points include:

- ``spotify``
- ``deezer``
- ``discogs``

Migration guidance
------------------

Older metadata plugins that extend |BeetsPlugin| should be migrated to
:py:class:`MetadataSourcePlugin`. Legacy support will be removed in **beets
v3.0.0**.

.. seealso::

    - :py:mod:`beets.autotag`
    - :py:mod:`beets.metadata_plugins`
    - :ref:`autotagger_extensions`
    - :ref:`using-the-auto-tagger`
