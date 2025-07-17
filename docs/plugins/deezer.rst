Deezer Plugin
=============

The ``deezer`` plugin provides metadata matches for the importer using the
Deezer_ Album_ and Track_ APIs.

.. _album: https://developers.deezer.com/api/album

.. _deezer: https://www.deezer.com

.. _track: https://developers.deezer.com/api/track

Basic Usage
-----------

First, enable the ``deezer`` plugin (see :ref:`using-plugins`).

You can enter the URL for an album or song on Deezer at the ``enter Id`` prompt
during import:

::

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://www.deezer.com/en/album/572261

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in
:ref:`metadata-source-plugin-configuration`.

The default options should work as-is, but there are some options you can put
in config.yaml under the ``deezer:`` section:

- **search_query_ascii**: If set to ``yes``, the search query will be converted to
  ASCII before being sent to Deezer. Converting searches to ASCII can
  enhance search results in some cases, but in general, it is not recommended. 
  For instance `artist:deadmau5 album:4×4` will be converted to 
  `artist:deadmau5 album:4x4` (notice `×!=x`).
  Default: ``no``.

The ``deezer`` plugin provides an additional command ``deezerupdate`` to update the ``rank`` information from Deezer. The ``rank`` (ranges from 0 to 1M) is a global indicator of a song's popularity on Deezer that is updated daily based on streams. The higher the ``rank``, the more popular the track is.
