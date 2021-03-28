Lyrics Plugin
=============

The ``lyrics`` plugin fetches and stores song lyrics from databases on the Web.
Namely, the current version of the plugin uses `Musixmatch`_, `Genius.com`_,
`Tekstowo.pl`_, and, optionally, the Google custom search API.

.. _Musixmatch: https://www.musixmatch.com/
.. _Genius.com: https://genius.com/
.. _Tekstowo.pl: https://www.tekstowo.pl/


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

.. _requests: https://requests.readthedocs.io/en/master/


Configuration
-------------

To configure the plugin, make a ``lyrics:`` section in your
configuration file. The available options are:

- **auto**: Fetch lyrics automatically during import.
  Default: ``yes``.
- **bing_client_secret**: Your Bing Translation application password
  (to :ref:`lyrics-translation`)
- **bing_lang_from**: By default all lyrics with a language other than
  ``bing_lang_to`` are translated. Use a list of lang codes to restrict the set
  of source languages to translate.
  Default: ``[]``
- **bing_lang_to**: Language to translate lyrics into.
  Default: None.
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
  Default: ``google musixmatch genius tekstowo``, i.e., all the
  available sources. The ``google`` source will be automatically
  deactivated if no ``google_API_key`` is setup.
  The ``google``, ``genius``, and ``tekstowo`` sources will only be enabled if
  BeautifulSoup is installed.

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
already have lyrics. Inversely, the ``-l`` option restricts operations
to lyrics that are locally available, which show lyrics faster without using
the network at all.

Rendering Lyrics into Other Formats
-----------------------------------

The ``-r directory`` option renders all lyrics as `reStructuredText`_ (ReST)
documents in ``directory`` (by default, the current directory). That
directory, in turn, can be parsed by tools like `Sphinx`_ to generate HTML,
ePUB, or PDF documents.

A minimal ``conf.py`` and ``index.rst`` files are created the first time the
command is run. They are not overwritten on subsequent runs, so you can safely
modify these files to customize the output.

.. _Sphinx: https://www.sphinx-doc.org/
.. _reStructuredText: http://docutils.sourceforge.net/rst.html

Sphinx supports various `builders
<https://www.sphinx-doc.org/en/stable/builders.html>`_, but here are a
few suggestions.

 * Build an HTML version::

    sphinx-build -b html . _build/html

 * Build an ePUB3 formatted file, usable on ebook readers::

    sphinx-build -b epub3 . _build/epub

 * Build a PDF file, which incidentally also builds a LaTeX file::

    sphinx-build -b latex %s _build/latex && make -C _build/latex all-pdf

.. _activate-google-custom-search:

Activate Google Custom Search
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

.. _register for a Google API key: https://console.developers.google.com/

Optionally, you can `define a custom search engine`_. Get your search engine's
token and use it for your ``google_engine_ID`` configuration option. By
default, beets use a list of sources known to be scrapeable.

.. _define a custom search engine: https://www.google.com/cse/all

Note that the Google custom search API is limited to 100 queries per day.
After that, the lyrics plugin will fall back on other declared data sources.

.. _pip: https://pip.pypa.io
.. _BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

Activate Genius and Tekstowo.pl Lyrics
--------------------------------------

Using the Genius or Tekstowo.pl backends requires `BeautifulSoup`_, which
you can install using `pip`_ by typing::

    pip install beautifulsoup4

These backends are enabled by default.

.. _lyrics-translation:

Activate On-the-Fly Translation
-------------------------------

Using the Bing Translation API requires `langdetect`_, which you can install
using `pip`_ by typing::

    pip install langdetect

You also need to register for a Microsoft Azure Marketplace free account and
to the `Microsoft Translator API`_. Follow the four steps process, specifically
at step 3 enter ``beets`` as *Client ID* and copy/paste the generated
*Client secret* into your ``bing_client_secret`` configuration, alongside
``bing_lang_to`` target `language code`.

.. _langdetect: https://pypi.python.org/pypi/langdetect
.. _Microsoft Translator API: https://docs.microsoft.com/en-us/azure/cognitive-services/translator/translator-how-to-signup
