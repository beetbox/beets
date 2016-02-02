Lyrics Plugin
=============

The ``lyrics`` plugin fetches and stores song lyrics from databases on the Web.
Namely, the current version of the plugin uses `Lyric Wiki`_, `Lyrics.com`_,
`Musixmatch`_, `Genius.com`_, and, optionally, the Google custom search API.

.. _Lyric Wiki: http://lyrics.wikia.com/
.. _Lyrics.com: http://www.lyrics.com/
.. _Musixmatch: https://www.musixmatch.com/
.. _Genius.com: http://genius.com/


Fetch Lyrics During Import
--------------------------

To automatically fetch lyrics for songs you import, enable the ``lyrics``
plugin in your configuration (see :ref:`using-plugins`).
Then, install the `requests`_ library by typing::

    pip install requests

The plugin uses `requests`_ to download lyrics.

When importing new files, beets will now fetch lyrics for files that don't
already have them. The lyrics will be stored in the beets database. If the
``import.write`` config option is on, then the lyrics will also be written to
the files' tags.

.. _requests: http://docs.python-requests.org/en/latest/


Configuration
-------------

To configure the plugin, make a ``lyrics:`` section in your
configuration file. The available options are:

- **auto**: Fetch lyrics automatically during import.
  Default: ``yes``.
- **fallback**: By default, the file will be left unchanged when no lyrics are
  found. Use the empty string ``''`` to reset the lyrics in such a case.
  Default: None.
- **force**: By default, beets won't fetch lyrics if the files already have
  ones. To instead always fetch lyrics, set the ``force`` option to ``yes``.
  Default: ``no``.
- **google_API_key**: Your Google API key (to enable the Google Custom Search
  backend).
  Default: None.
- **google_engine_ID**: The custom search engine to use.
  Default: The `beets custom search engine`_, which gathers an updated list of
  sources known to be scrapeable.
- **sources**: List of sources to search for lyrics. An asterisk ``*`` expands
  to all available sources.
  Default: ``google lyricwiki lyrics.com musixmatch``, i.e., all the
  sources except for `genius`. The `google` source will be automatically
  deactivated if no ``google_API_key`` is setup.

Here's an example of ``config.yaml``::

    lyrics:
      fallback: ''
      google_API_key: AZERTYUIOPQSDFGHJKLMWXCVBN1234567890_ab
      google_engine_ID: 009217259823014548361:lndtuqkycfu

.. _beets custom search engine: https://www.google.com:443/cse/publicurl?cx=009217259823014548361:lndtuqkycfu

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

The ``-f`` option forces the command to fetch lyrics, even for tracks that
already have lyrics.

.. _activate-google-custom-search:

Activate Google custom search
------------------------------

Using the Google backend requires `BeautifulSoup`_, which you can install
using `pip`_ by typing::

    pip install beautifulsoup4

You also need to `register for a Google API key`_. Set the ``google_API_key``
configuration option to your key.
Then add ``google`` to the list of sources in your configuration (or use
default list, which includes it as long as you have an API key).
If you use default ``google_engine_ID``, we recommend limiting the sources to
``musixmatch google`` as the other sources are already included in the Google
results.

.. _register for a Google API key: https://code.google.com/apis/console.

Optionally, you can `define a custom search engine`_. Get your search engine's
token and use it for your ``google_engine_ID`` configuration option. By
default, beets use a list of sources known to be scrapeable.

.. _define a custom search engine: http://www.google.com/cse/all

Note that the Google custom search API is limited to 100 queries per day.
After that, the lyrics plugin will fall back on other declared data sources.

.. _pip: http://www.pip-installer.org/
.. _BeautifulSoup: http://www.crummy.com/software/BeautifulSoup/bs4/doc/
