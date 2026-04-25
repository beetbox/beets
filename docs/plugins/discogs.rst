Discogs Plugin
==============

The ``discogs`` plugin extends the autotagger's search capabilities to include
matches from the Discogs_ database.

Files can be imported as albums or as singletons. Since Discogs_ matches are
always based on Discogs_ releases, the album tag is written even to singletons.
This enhances the importers results when reimporting as (full or partial) albums
later on.

.. _discogs: https://discogs.com

Genre Mapping
-------------

Discogs uses ``styles`` for the more specific classifications and ``genres`` for
the broader ones. The plugin therefore uses Discogs ``styles`` as the primary
source for the beets ``genres`` field, because beets treats ``genres`` as the
main multi-valued genre field.

The broader Discogs ``genres`` values are written to the beets ``style`` field.
If :conf:`plugins.discogs:append_style_genre` is enabled, those broader Discogs
``genres`` values are also appended to beets ``genres``.

For example, a Discogs release with ``styles`` set to ``["Techno"]`` and
``genres`` set to ``["Electronic"]`` becomes beets ``genres`` = ``["Techno"]``
and ``style`` = ``"Electronic"`` by default. With ``append_style_genre``
enabled, beets ``genres`` becomes ``["Techno", "Electronic"]``.

Installation
------------

To use the ``discogs`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``discogs`` extra

.. code-block:: bash

    pip install "beets[discogs]"

You will also need to register for a Discogs_ account, and provide
authentication credentials via a personal access token or an OAuth2
authorization.

Matches from Discogs will now show up during import alongside matches from
MusicBrainz. The search terms sent to the Discogs API are based on the artist
and album tags of your tracks. If those are empty no query will be issued.

If you have a Discogs ID for an album you want to tag, you can also enter it at
the "enter Id" prompt in the importer.

OAuth Authorization
~~~~~~~~~~~~~~~~~~~

The first time you run the :ref:`import-cmd` command after enabling the plugin,
it will ask you to authorize with Discogs by visiting the site in a browser.
Subsequent runs will not require re-authorization.

Authentication via Personal Access Token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As an alternative to OAuth, you can get a token from Discogs and add it to your
configuration. To get a personal access token (called a "user token" in the
python3-discogs-client_ documentation):

1. login to Discogs_;
2. visit the `Developer settings page
   <https://www.discogs.com/settings/developers>`_;
3. press the *Generate new token* button;
4. copy the generated token;
5. place it in your configuration in the ``discogs`` section as the
   ``user_token`` option:

   .. code-block:: yaml

       discogs:
           user_token: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in
:ref:`metadata-source-plugin-configuration`.

Default
~~~~~~~

.. code-block:: yaml

    discogs:
        apikey: REDACTED
        apisecret: REDACTED
        tokenfile: discogs_token.json
        user_token:
        index_tracks: no
        append_style_genre: no
        separator: ', '
        strip_disambiguation: yes
        featured_string: Feat.
        extra_tags: []
        anv:
            artist_credit: yes
            artist: no
            album_artist: no
        data_source_mismatch_penalty: 0.5
        search_limit: 5

.. conf:: index_tracks
    :default: no

    Index tracks (see the `Discogs guidelines`_) along with headers, mark divisions
    between distinct works on the same release or within works. When enabled,
    beets will incorporate the names of the divisions containing each track into the
    imported track's title.

    For example, importing `divisions album`_ would result in track names like:

    .. code-block:: text

     Messiah, Part I: No.1: Sinfony
     Messiah, Part II: No.22: Chorus- Behold The Lamb Of God
     Athalia, Act I, Scene I: Sinfonia

    whereas with ``index_tracks`` disabled you'd get:

    .. code-block:: text

     No.1: Sinfony
     No.22: Chorus- Behold The Lamb Of God
     Sinfonia

    This option is useful when importing classical music.

.. conf:: append_style_genre
    :default: no

    Appends the broader Discogs ``genres`` values to beets ``genres`` after
    the specific Discogs ``styles`` values already stored there. See the
    Genre Mapping section above for the default field mapping and an example.

.. conf:: separator
    :default: ", "

    How to join multiple Discogs ``genres`` values when writing the beets
    ``style`` field.

    .. versionchanged:: 2.7.0

       This option now only applies to the ``style`` field as beets now only
       handles lists of ``genres``.

.. conf:: strip_disambiguation
    :default: yes

    Discogs uses strings like ``"(4)"`` to mark distinct artists and labels with
    the same name. If you'd like to use the Discogs disambiguation in your tags,
    you can disable this option.

.. conf:: featured_string
    :default: Feat.

    Configure the string used for noting featured artists. Useful if you prefer ``Featuring`` or ``ft.``.

.. conf:: extra_tags
    :default: []

    By default, beets will use only the artist and album to query Discogs.
    Additional tags to be queried can be supplied with the
    ``extra_tags`` setting.

    This setting should improve the autotagger results if the metadata with the
    given tags match the metadata returned by Discogs.

    Tags supported by this setting:

    * ``barcode``
    * ``catalognum``
    * ``country``
    * ``label``
    * ``media``
    * ``year``

    Example:

    .. code-block:: yaml

        discogs:
            extra_tags: [barcode, catalognum, country, label, media, year]

.. conf:: anv

    This configuration option is dedicated to handling Artist Name
    Variations (ANVs). Sometimes a release credits artists differently compared to
    the majority of their work. For example, "Basement Jaxx" may be credited as
    "Tha Jaxx" or "The Basement Jaxx". You can select any combination of these
    config options to control where beets writes and stores the variation credit.
    The default, shown below, writes variations to the artist_credit field.

    .. code-block:: yaml

        discogs:
            anv:
               artist_credit: yes
               artist: no
               album_artist: no

Contributor credits
~~~~~~~~~~~~~~~~~~~

When Discogs provides artist roles on a track, beets uses them to separate main
artists from other credited contributors. Main artist fields such as ``artist``,
``artists``, ``artist_credit``, ``artists_credit``, ``artist_id``, and
``artists_ids`` keep the primary artist credits, while featured artists from
track roles are appended using :conf:`plugins.discogs:featured_string`.

Discogs contributor roles are also imported into beets' multi-value performer
fields when available. This includes remixer, lyricist, composer, and arranger
credits, which populate ``remixers``, ``lyricists``, ``composers``, and
``arrangers`` respectively.

.. include:: ./shared_metadata_source_config.rst

.. _discogs guidelines: https://support.discogs.com/hc/en-us/articles/360005055373-Database-Guidelines-12-Tracklisting#Index_Tracks_And_Headings

.. _divisions album: https://www.discogs.com/release/2026070-Handel-Sutherland-Kirkby-Kwella-Nelson-Watkinson-Bowman-Rolfe-Johnson-Elliott-Partridge-Thomas-The-A

Troubleshooting
---------------

Several issues have been encountered with the Discogs API. If you have one,
please start by searching for `a similar issue on the repo
<https://github.com/beetbox/beets/issues?utf8=%E2%9C%93&q=is%3Aissue+discogs>`_.

Here are two things you can try:

- Try deleting the token file (``~/.config/beets/discogs_token.json`` by
  default) to force re-authorization.
- Make sure that your system clock is accurate. The Discogs servers can reject
  your request if your clock is too out of sync.

Matching tracks by Discogs ID is not yet supported. The ``--group-albums``
option in album import mode provides an alternative to singleton mode for
autotagging tracks that are not in album-related folders.

.. _python3-discogs-client: https://github.com/joalla/discogs_client
