MusicBrainz Plugin
==================

The ``musicbrainz`` plugin extends the autotagger's search capabilities to
include matches from the `MusicBrainz`_ database.

.. _MusicBrainz: https://musicbrainz.org/

Installation
------------

To use the ``musicbrainz`` plugin, enable it in your configuration (see
:ref:`using-plugins`)

.. _musicbrainz-config:

Configuration
-------------

Default
^^^^^^^

.. code-block:: yaml

    musicbrainz:
        host: musicbrainz.org
        https: no
        ratelimit: 1
        ratelimit_interval: 1.0
        searchlimit: 5
        extra_tags: []
        genres: no
        external_ids:
            discogs: no
            bandcamp: no
            spotify: no
            deezer: no
            beatport: no
            tidal: no


You can instruct beets to use `your own MusicBrainz database`_ instead of
the `main server`_. Use the ``host``, ``https`` and ``ratelimit`` options
under a ``musicbrainz:`` header, like so

.. code-block:: yaml

    musicbrainz:
        host: localhost:5000
        https: no
        ratelimit: 100

The ``host`` key, of course, controls the Web server hostname (and port,
optionally) that will be contacted by beets (default: musicbrainz.org). The
``https`` key makes the client use HTTPS instead of HTTP. This setting applies
only to custom servers. The official MusicBrainz server always uses HTTPS.
(Default: no.) The server must have search indices enabled (see `Building search
indexes`_).

The ``ratelimit`` option, an integer, controls the number of Web service
requests per second (default: 1). **Do not change the rate limit setting** if
you're using the main MusicBrainz server---on this public server, you're
`limited`_ to one request per second.

.. _your own MusicBrainz database: https://musicbrainz.org/doc/MusicBrainz_Server/Setup
.. _main server: https://musicbrainz.org/
.. _limited: https://musicbrainz.org/doc/XML_Web_Service/Rate_Limiting
.. _Building search indexes: https://musicbrainz.org/doc/Development/Search_server_setup

.. _musicbrainz.enabled:

enabled
~~~~~~~

.. deprecated:: 2.3
  Add ``musicbrainz`` to the ``plugins`` list instead.

This option allows you to disable using MusicBrainz as a metadata source. This
applies if you use plugins that fetch data from alternative sources and should
make the import process quicker.

Default: ``yes``.

.. _searchlimit:

searchlimit
~~~~~~~~~~~

The number of matches returned when sending search queries to the
MusicBrainz server.

Default: ``5``.

.. _extra_tags:

extra_tags
~~~~~~~~~~

By default, beets will use only the artist, album, and track count to query
MusicBrainz. Additional tags to be queried can be supplied with the
``extra_tags`` setting. For example

.. code-block:: yaml

    musicbrainz:
        extra_tags: [barcode, catalognum, country, label, media, year]

This setting should improve the autotagger results if the metadata with the
given tags match the metadata returned by MusicBrainz.

Note that the only tags supported by this setting are the ones listed in the
above example.

Default: ``[]``

.. _genres:

genres
~~~~~~

Use MusicBrainz genre tags to populate (and replace if it's already set) the
``genre`` tag.  This will make it a list of all the genres tagged for the
release and the release-group on MusicBrainz, separated by "; " and sorted by
the total number of votes.
Default: ``no``

.. _musicbrainz.external_ids:

external_ids
~~~~~~~~~~~~

Set any of the ``external_ids`` options to ``yes`` to enable the MusicBrainz
importer to look for links to related metadata sources. If such a link is
available the release ID will be extracted from the URL provided and imported
to the beets library

.. code-block:: yaml

    musicbrainz:
        external_ids:
            discogs: yes
            spotify: yes
            bandcamp: yes
            beatport: yes
            deezer: yes
            tidal: yes


The library fields of the corresponding :ref:`autotagger_extensions` are used
to save the data (``discogs_albumid``, ``bandcamp_album_id``,
``spotify_album_id``, ``beatport_album_id``, ``deezer_album_id``,
``tidal_album_id``). On re-imports existing data will be overwritten.

The default of all options is ``no``.
