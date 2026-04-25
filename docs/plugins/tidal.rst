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

.. include:: ./shared_metadata_source_config.rst
