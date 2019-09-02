Deezer Plugin
==============

The ``deezer`` plugin provides metadata matches for the importer using the
`Deezer_` `Album`_ and `Track`_ APIs.

.. _Deezer: https://www.deezer.com
.. _Album: https://developers.deezer.com/api/album
.. _Track: https://developers.deezer.com/api/track

Why Use This Plugin?
--------------------

* You're a Beets user.
* You want to autotag music with metadata from the Deezer API.

Basic Usage
-----------
First, enable the ``deezer`` plugin (see :ref:`using-plugins`).

You can enter the URL for an album or song on Deezer at the ``enter Id``
prompt during import::

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://www.deezer.com/en/album/572261

Configuration
-------------
Put these options in config.yaml under the ``deezer:`` section:

- **source_weight**: Penalty applied to Spotify matches during import. Set to
  0.0 to disable.
  Default: ``0.5``.

Here's an example::

    deezer:
        source_weight: 0.7
