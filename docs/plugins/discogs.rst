Discogs Plugin
==============

The ``discogs`` plugin extends the autotagger's search capabilities to include
matches from the Discogs_ database.

Files can be imported as albums or as singletons. Since Discogs_ matches are
always based on Discogs_ releases, the album tag is written even to singletons.
This enhances the importers results when reimporting as (full or partial) albums
later on.

.. _discogs: https://discogs.com

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
        data_source_mismatch_penalty: 0.5
        search_limit: 5
        apikey: REDACTED
        apisecret: REDACTED
        tokenfile: discogs_token.json
        user_token: REDACTED
        index_tracks: no
        append_style_genre: no
        separator: ', '
        strip_disambiguation: yes

- **index_tracks**: Index tracks (see the `Discogs guidelines`_) along with
  headers, mark divisions between distinct works on the same release or within
  works. When enabled, beets will incorporate the names of the divisions
  containing each track into the imported track's title. Default: ``no``.

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

- **append_style_genre**: Appends the Discogs style (if found) to the genre tag.
  This can be useful if you want more granular genres to categorize your music.
  For example, a release in Discogs might have a genre of "Electronic" and a
  style of "Techno": enabling this setting would set the genre to be
  "Electronic, Techno" (assuming default separator of ``", "``) instead of just
  "Electronic". Default: ``False``
- **separator**: How to join multiple genre and style values from Discogs into a
  string. Default: ``", "``
- **strip_disambiguation**: Discogs uses strings like ``"(4)"`` to mark distinct
  artists and labels with the same name. If you'd like to use the discogs
  disambiguation in your tags, you can disable it. Default: ``True``
- **featured_string**: Configure the string used for noting featured artists.
  Useful if you prefer ``Featuring`` or ``ft.``. Default: ``Feat.``
- **anv**: These configuration option are dedicated to handling Artist Name
  Variations (ANVs). Sometimes a release credits artists differently compared to
  the majority of their work. For example, "Basement Jaxx" may be credited as
  "Tha Jaxx" or "The Basement Jaxx".You can select any combination of these
  config options to control where beets writes and stores the variation credit.
  The default, shown below, writes variations to the artist_credit field.

.. code-block:: yaml

    discogs:
        anv:
           artist_credit: True
           artist: False
           album_artist: False

.. _discogs guidelines: https://support.discogs.com/hc/en-us/articles/360005055373-Database-Guidelines-12-Tracklisting#Index_Tracks_And_Headings

.. _divisions album: https://www.discogs.com/Handel-Sutherland-Kirkby-Kwella-Nelson-Watkinson-Bowman-Rolfe-Johnson-Elliott-Partridge-Thomas-The-A/release/2026070

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
