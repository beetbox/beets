Lyrics Plugin
=============

The ``lyrics`` plugin fetches and stores song lyrics from databases on the Web.
Namely, the current version of the plugin uses `Lyric Wiki`_, `Lyrics.com`_,
and, optionally, the Google custom search API.

.. _Lyric Wiki: http://lyrics.wikia.com/
.. _Lyrics.com: http://www.lyrics.com/


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

The ``-f`` option to the ``lyrics`` command forces it to fetch previously
downloaded lyrics.


Configuring
-----------

To disable automatic lyric fetching during import, set the ``auto`` option to
false, like so::

    lyrics:
        auto: no

By default, if no lyrics are found, the file will be left unchanged. To
specify a placeholder for the lyrics tag when none are found, use the
``fallback`` configuration option::

    lyrics:
        fallback: 'No lyrics found'

.. _activate-google-custom-search:


Activate Google custom search
------------------------------

Using the Google backend requires `BeautifulSoup`_, which you can install
using `pip`_ by typing::

    pip install beautifulsoup4

You also need to `register for a Google API key`_. Set the ``google_API_key``
configuration option to your key. This enables the Google backend.

.. _register for a Google API key: https://code.google.com/apis/console.

Optionally, you can `define a custom search engine`_. Get your search engine's
token and use it for your ``google_engine_ID`` configuration option. By
default, beets use a list of sources known to be scrapeable.

.. _define a custom search engine: http://www.google.com/cse/all

Here's an example of ``config.yaml``::

    lyrics:
      google_API_key: AZERTYUIOPQSDFGHJKLMWXCVBN1234567890_ab
      google_engine_ID: 009217259823014548361:lndtuqkycfu

Note that the Google custom search API is limited to 100 queries per day.
After that, the lyrics plugin will fall back on its other data sources.

.. _pip: http://www.pip-installer.org/
.. _BeautifulSoup: http://www.crummy.com/software/BeautifulSoup/bs4/doc/
