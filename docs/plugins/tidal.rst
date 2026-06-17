Tidal Plugin
============

The ``tidal`` plugin provides metadata matches for the autotagger using the
Tidal_ Web APIs.

.. _tidal: https://tidal.com

Why Use the Tidal Plugin?
-------------------------

The Tidal plugin allows you to:

- Fetch metadata for albums and tracks from Tidal's catalog
- Look up tracks by ISRC code (useful if your music files already contain ISRC
  tags)
- Look up albums by barcode ID (useful if your CDs have UPC barcodes)
- Get matches during import without needing to manually search

This is especially useful if your music already has ISRC or barcode metadata
embedded, as it allows for quick and accurate matching to Tidal's catalog.

Requirements
------------

- A Tidal account (free or premium)
- Python environment with network access to Tidal's API

Before using the plugin, you need to authorize your beets installation to access
your Tidal account.

Installation
------------

To use the ``tidal`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``tidal`` extra

.. code-block:: bash

    pip install "beets[tidal]"

Authentication
--------------

To authenticate with Tidal, run:

.. code-block:: bash

    beet tidal --auth

This will open a browser window where you can log in to your Tidal account.
After successful authentication, your token will be saved to the configured
token file and you won't need to re-authenticate on subsequent runs.

Basic Usage
-----------

Enable the ``tidal`` plugin (see :ref:`using-plugins`). Once enabled, you will
receive Tidal matches when importing new items.

During import, you can also manually enter a Tidal URL at the ``enter Id``
prompt:

.. code-block:: bash

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://tidal.com/album/226495055

You can enter both album and track URLs. For example:

.. code-block:: bash

    https://tidal.com/track/490839595
    https://tidal.com/album/234493117

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in
:ref:`metadata-source-plugin-configuration`.

Default
~~~~~~~

.. code-block:: yaml

    tidal:
        client_id: mcjmpl1bPATJXcBT
        tokenfile: tidal_token.json
        data_source_mismatch_penalty: 0.5
        search_limit: 5

.. conf:: client_id
    :default: mcjmpl1bPATJXcBT

    The Tidal API client ID. The default value is the public demo client ID.
    You can register your own application at Tidal's developer portal for
    production use.

.. conf:: tokenfile
    :default: tidal_token.json

    The path to the file where the Tidal authentication token is stored.

Flexible Attributes
-------------------

The plugin stores the following flexible attributes on your items during import.
You can use them in queries and path formats.

.. list-table::
    :header-rows: 1

    - - Attribute
      - Type
      - Description
    - - ``tidal_track_id``
      - STRING
      - Tidal track ID
    - - ``tidal_album_id``
      - STRING
      - Tidal album ID
    - - ``tidal_artist_id``
      - STRING
      - Tidal artist ID
    - - ``tidal_track_popularity``
      - INTEGER
      - Track popularity score (0-100)
    - - ``tidal_album_popularity``
      - INTEGER
      - Album popularity score (0-100)
    - - ``tidal_updated``
      - DATE
      - Unix timestamp of last popularity sync

For example, to list your most popular tracks:

::

    beet ls tidal_track_popularity:80..

To find tracks that have not been synced yet:

::

    beet ls tidal_track_popularity:0

Commands
--------

The ``tidal`` plugin provides the following commands:

``beet tidal --auth``
    Authenticate and log in to Tidal.

``beet tidalsync``
    Refresh popularity data for imported items.

    By default, ``tidalsync`` skips items that already have popularity data. Use
    ``--force`` (``-f``) to re-fetch all items:

    ::

        beet tidalsync -f

    Use ``--album`` (``-a``) to sync albums instead of items:

    ::

        beet tidalsync -a

    Use ``--write`` (``-w``) to also write the updated metadata to the media
    files:

    ::

        beet tidalsync -w

    You can also filter which items to sync by passing a query:

    ::

        beet tidalsync artist:"My Artist"

.. include:: ./shared_metadata_source_config.rst
