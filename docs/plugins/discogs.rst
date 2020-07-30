Discogs Plugin
==============

The ``discogs`` plugin extends the autotagger's search capabilities to
include matches from the `Discogs`_ database.

.. _Discogs: https://discogs.com

Installation
------------

To use the ``discogs`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install the `discogs-client`_ library by typing::

    pip install discogs-client

You will also need to register for a `Discogs`_ account, and provide
authentication credentials via a personal access token or an OAuth2
authorization.

Matches from Discogs will now show up during import alongside matches from
MusicBrainz.

If you have a Discogs ID for an album you want to tag, you can also enter it
at the "enter Id" prompt in the importer.

OAuth Authorization
```````````````````

The first time you run the :ref:`import-cmd` command after enabling the plugin,
it will ask you to authorize with Discogs by visiting the site in a browser.
Subsequent runs will not require re-authorization.

Authentication via Personal Access Token
````````````````````````````````````````

As an alternative to OAuth, you can get a token from Discogs and add it to
your configuration.
To get a personal access token (called a "user token" in the `discogs-client`_
documentation), login to `Discogs`_, and visit the
`Developer settings page
<https://www.discogs.com/settings/developers>`_. Press the ``Generate new
token`` button, and place the generated token in your configuration, as the
``user_token`` config option in the ``discogs`` section.

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in :ref:`metadata-source-plugin-configuration`.

There is one additional option in the ``discogs:`` section, ``index_tracks``.
Index tracks (see the `Discogs guidelines
<https://support.discogs.com/hc/en-us/articles/360005055373-Database-Guidelines-12-Tracklisting#12.13>`_),
along with headers, mark divisions between distinct works on the same release
or within works. When ``index_tracks`` is enabled::

    discogs:
        index_tracks: yes

beets will incorporate the names of the divisions containing each track into
the imported track's title. For example, importing
`this album
<https://www.discogs.com/Handel-Sutherland-Kirkby-Kwella-Nelson-Watkinson-Bowman-Rolfe-Johnson-Elliott-Partridge-Thomas-The-A/release/2026070>`_
would result in track names like::

    Messiah, Part I: No.1: Sinfony
    Messiah, Part II: No.22: Chorus- Behold The Lamb Of God
    Athalia, Act I, Scene I: Sinfonia

whereas with ``index_tracks`` disabled you'd get::

    No.1: Sinfony
    No.22: Chorus- Behold The Lamb Of God
    Sinfonia

This option is useful when importing classical music.

Troubleshooting
---------------

Several issues have been encountered with the Discogs API. If you have one,
please start by searching for `a similar issue on the repo
<https://github.com/beetbox/beets/issues?utf8=%E2%9C%93&q=is%3Aissue+discogs>`_.

Here are two things you can try:

* Try deleting the token file (``~/.config/beets/discogs_token.json`` by
  default) to force re-authorization.
* Make sure that your system clock is accurate. The Discogs servers can reject
  your request if your clock is too out of sync.

.. _discogs-client: https://github.com/discogs/discogs_client
