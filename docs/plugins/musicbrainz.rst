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
        pseudo_releases:
            scripts: []
            custom_tags_only: no
            multiple_allowed: no
            album_custom_tags:
                album_transl: album
                album_artist_transl: artist
            track_custom_tags:
                title_transl: title
                artist_transl: artist

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

    Controls the number of Web service requests per second. This setting applies only
    to custom servers. The official MusicBrainz server enforces a rate limit of 1
    request per second.

.. conf:: ratelimit_interval
    :default: 1.0

    The time interval (in seconds) for the rate limit. Only applies to custom servers.

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

    Tags supported by this setting:

    * ``alias`` (also search for release aliases matching the query)
    * ``barcode``
    * ``catalognum``
    * ``country``
    * ``label``
    * ``media``
    * ``tracks`` (number of tracks on the release)
    * ``year``

    Example:

    .. code-block:: yaml

        musicbrainz:
            extra_tags: [alias, barcode, catalognum, country, label, media, tracks, year]

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

Pseudo-Releases
---------------

This plugin can also search for MusicBrainz pseudo-releases_ during the import
process, which are added to the normal candidates from the MusicBrainz search.

.. _pseudo-releases: https://musicbrainz.org/doc/Style/Specific_types_of_releases/Pseudo-Releases

This is useful for releases whose title and track titles are written with a
script_ that can be translated or transliterated into a different one.

.. _script: https://en.wikipedia.org/wiki/ISO_15924

The configuration expects an array of scripts that are desired for the
pseudo-releases. For ``artist`` in particular, keep in mind that even
pseudo-releases might specify it with the original script, so you should also
configure import :ref:`languages` to give artist aliases more priority.
Therefore, the minimum configuration to enable this functionality looks like
this:

.. code-block:: yaml

    import:
        languages: en

    musicbrainz:
        # other config not shown
        pseudo_releases:
            scripts:
            - Latn

Pseudo-releases will only be included if the initial search in MusicBrainz
returns releases whose script is *not* desired and whose relationships include
pseudo-releases with desired scripts.

A release may have multiple pseudo-releases, for example when there is both a
transliteration and a translation available. By default, only 1 pseudo-release
per original release is emitted as a candidate, using the languages from the
configuration to decide which one has most priority. If you're importing in
timid mode and you would like to receive all valid pseudo-releases as additional
candidates, you can add the following to the configuration:

.. code-block:: yaml

    musicbrainz:
        pseudo_releases:
            # other config not shown
            multiple_allowed: yes

.. note::

    A limitation of reimporting in particular is that it will *not* give you a
    pseudo-release proposal if multiple candidates exist and are allowed, so you
    should disallow multiple in that scenario.

By default, the data from the pseudo-release will be used to create a proposal
that is independent from the original release and sets all properties in its
metadata. It's possible to change the configuration so that some information
from the pseudo-release is instead added as custom tags, keeping the metadata
from the original release:

.. code-block:: yaml

    musicbrainz:
        pseudo_releases:
            # other config not shown
            custom_tags_only: yes

The default custom tags with this configuration are specified as mappings where
the keys define the tag names and the values define the pseudo-release property
that will be used to set the tag's value:

.. code-block:: yaml

    musicbrainz:
        pseudo_releases:
            # other config not shown
            album_custom_tags:
                album_transl: album
                album_artist_transl: artist
            track_custom_tags:
                title_transl: title
                artist_transl: artist

Note that the information for each set of custom tags corresponds to different
metadata levels (album or track level), which is why ``artist`` appears twice
even though it effectively references album artist and track artist
respectively.

If you want to modify any mapping under ``album_custom_tags`` or
``track_custom_tags``, you must specify *everything* for that set of tags in
your configuration file because any customization replaces the whole dictionary
of mappings for that level.

.. note::

    These custom tags are also added to the music files, not only to the
    database.
