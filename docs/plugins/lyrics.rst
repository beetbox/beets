Lyrics Plugin
=============

The ``lyrics`` plugin fetches and stores song lyrics from databases on the Web.
Namely, the current version of the plugin uses `Lyric Wiki`_ and `Lyrics.com`_.

.. _Lyric Wiki: http://lyrics.wikia.com/
.. _Lyrics.com: http://www.lyrics.com/

:ref:`_activate-google-custom-search` to expand the plugin firepower, by using google search to harvest lyrics from your own websites list.

By default if no lyrics are found, the file will be left unchanged. To specify a placeholder for the lyrics tags when none are found, use the ``fallback`` configuration option.

    lyrics:
        fallback: 'No lyrics found'

Fetch Lyrics During Import
--------------------------

To automatically fetch lyrics for songs you import, just enable the plugin by
putting ``lyrics`` on your config file's ``plugins`` line (see
:doc:`/plugins/index`).  When importing new files, beets will now fetch lyrics
for files that don't already have them. The lyrics will be stored in the beets
database. If the ``import.write`` config option is on, then the lyrics will also
be written to the files' tags.

This behavior can be disabled with the ``auto`` config option (see below).

Fetching Lyrics Manually
------------------------

The ``lyrics`` command provided by this plugin fetches lyrics for items that
match a query (see :doc:`/reference/query`). For example, ``beet lyrics magnetic
fields absolutely cuckoo`` will get the lyrics for the appropriate Magnetic
Fields song, ``beet lyrics magnetic fields`` will get lyrics for all my tracks
by that band, and ``beet lyrics`` will get lyrics for my entire library. The
lyrics will be added to the beets database and, if ``import.write`` is on,
embedded into files' metadata.

The ``-p`` option to the ``lyrics`` command makes it print lyrics out to the
console so you can view the fetched (or previously-stored) lyrics.

Configuring
-----------

The plugin has one configuration option, ``auto``, which lets you disable
automatic lyrics fetching during import. To do so, add this to your
``config.yaml``::

    lyrics:
        auto: no

.. _activate-google-custom-search:

Activate Google custom search
------------------------------

Using Google backend requires `beautifulsoup`_, which you can install using `pip`_ by typing::

    pip install beautifulsoup4

To activate google search you must first register an API key on https://code.google.com/apis/console. Then click *API Access* and use that key for the `google_API_key` plugin option.

Optionally, you can define a custom search engine on http://www.google.com/cse/all. Click the *Search engine ID* button to display the token to copy into the `google_engine_ID` option.
By default, beets use a list of sources known to be scrapable.
 

Example of ``config.yaml``::

    lyrics:
      google_API_key: AZERTYUIOPQSDFGHJKLMWXCVBN1234567890_ab
      google_engine_ID: 009217259823014548361:lndtuqkycfu

.. _pip: http://www.pip-installer.org/
.. _beautifulsoup: http://www.crummy.com/software/BeautifulSoup/bs4/doc/