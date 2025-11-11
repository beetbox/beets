MusicBrainz Plugin
==================

The ``musicbrainz`` plugin extends the autotagger's search capabilities to
include matches from the MusicBrainz_ database.

.. _musicbrainz: https://musicbrainz.org/

Installation
------------

To use the ``musicbrainz`` plugin, enable it in your configuration (see
:ref:`using-plugins`)

.. _musicbrainz-config:

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in
:ref:`metadata-source-plugin-configuration`.

Default
~~~~~~~

.. code-block:: yaml

    musicbrainz:
        host: musicbrainz.org
        https: no
        ratelimit: 1
        ratelimit_interval: 1.0
        extra_tags: []
        genres: no
        genres_tag: genre
        external_ids:
            discogs: no
            bandcamp: no
            spotify: no
            deezer: no
            beatport: no
            tidal: no
        data_source_mismatch_penalty: 0.5
        search_limit: 5

.. conf:: host
    :default: musicbrainz.org

    The Web server hostname (and port, optionally) that will be contacted by beets.
    You can use this to configure beets to use `your own MusicBrainz database
    <https://musicbrainz.org/doc/MusicBrainz_Server/Setup>`__ instead of the
    `main server`_.

    The server must have search indices enabled (see `Building search indexes`_).

    Example:

    .. code-block:: yaml

        musicbrainz:
            host: localhost:5000

.. conf:: https
    :default: no

    Makes the client use HTTPS instead of HTTP. This setting applies only to custom
    servers. The official MusicBrainz server always uses HTTPS.

.. conf:: ratelimit
    :default: 1

    Controls the number of Web service requests per second.

    **Do not change the rate limit setting** if you're using the main MusicBrainz
    server---on this public server, you're limited_ to one request per second.

.. conf:: ratelimit_interval
    :default: 1.0

    The time interval (in seconds) for the rate limit.

.. conf:: enabled
    :default: yes

    .. deprecated:: 2.4 Add ``musicbrainz`` to the ``plugins`` list instead.

.. conf:: extra_tags
    :default: []

    By default, beets will use only the artist, album, and track count to query
    MusicBrainz. Additional tags to be queried can be supplied with the
    ``extra_tags`` setting.

    This setting should improve the autotagger results if the metadata with the
    given tags match the metadata returned by MusicBrainz.

    Note that the only tags supported by this setting are: ``barcode``,
    ``catalognum``, ``country``, ``label``, ``media``, and ``year``.

    Example:

    .. code-block:: yaml

        musicbrainz:
            extra_tags: [barcode, catalognum, country, label, media, year]

.. conf:: genres
    :default: no

    Use MusicBrainz genre tags to populate (and replace if it's already set) the
    ``genre`` tag. This will make it a list of all the genres tagged for the release
    and the release-group on MusicBrainz, separated by "; " and sorted by the total
    number of votes.

.. conf:: external_ids

    **Default**

    .. code-block:: yaml

        musicbrainz:
            external_ids:
                discogs: no
                spotify: no
                bandcamp: no
                beatport: no
                deezer: no
                tidal: no

    Set any of the ``external_ids`` options to ``yes`` to enable the MusicBrainz
    importer to look for links to related metadata sources. If such a link is
    available the release ID will be extracted from the URL provided and imported to
    the beets library.

    The library fields of the corresponding :ref:`autotagger_extensions` are used to
    save the data as flexible attributes (``discogs_album_id``, ``bandcamp_album_id``, ``spotify_album_id``,
    ``beatport_album_id``, ``deezer_album_id``, ``tidal_album_id``). On re-imports
    existing data will be overwritten.

.. conf:: genres_tag
    :default: genre

    Either ``genre`` or ``tag``. Specify ``genre`` to use just musicbrainz genre and
    ``tag`` to use all user-supplied musicbrainz tags.

.. include:: ./shared_metadata_source_config.rst

.. _building search indexes: https://musicbrainz.org/doc/Development/Search_server_setup

.. _limited: https://musicbrainz.org/doc/XML_Web_Service/Rate_Limiting

.. _main server: https://musicbrainz.org/
