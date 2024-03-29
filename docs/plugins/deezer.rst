Deezer Plugin
==============

The ``deezer`` plugin provides metadata matches for the importer using the
`Deezer`_ `Album`_ and `Track`_ APIs.

.. _Deezer: https://www.deezer.com
.. _Album: https://developers.deezer.com/api/album
.. _Track: https://developers.deezer.com/api/track

Basic Usage
-----------

First, enable the ``deezer`` plugin (see :ref:`using-plugins`).

You can enter the URL for an album or song on Deezer at the ``enter Id``
prompt during import::

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://www.deezer.com/en/album/572261

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in :ref:`metadata-source-plugin-configuration`.

The ``deezer`` plugin provides an additional command ``deezerupdate`` to update the ``rank`` information from Deezer. The ``rank`` (ranges from 0 to 1M) is a global indicator of a song's popularity on Deezer that is updated daily based on streams. The higher the ``rank``, the more popular the track is.
