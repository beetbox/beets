FetchArt Plugin
===============

The ``fetchart`` plugin retrieves album art images from various sources on the
Web and stores them as image files.

To use the ``fetchart`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install the `requests`_ library by typing::

    pip install requests

The plugin uses `requests`_ to fetch album art from the Web.

.. _requests: http://docs.python-requests.org/en/latest/

Fetching Album Art During Import
--------------------------------

When the plugin is enabled, it automatically gets album art for every album
you import.

By default, beets stores album art image files alongside the music files for an
album in a file called ``cover.jpg``. To customize the name of this file, use
the :ref:`art-filename` config option.

Configuration
-------------

To configure the plugin, make a ``fetchart:`` section in your configuration
file. The available options are:

- **auto**: Enable automatic album art fetching during import.
  Default: ``yes``.
- **cautious**: Pick only trusted album art by ignoring filenames that do not
  contain one of the keywords in ``cover_names``.
  Default: ``no``.
- **cover_names**: Prioritize images containing words in this list.
  Default: ``cover front art album folder``.
- **minwidth**: Only images with a width bigger or equal to ``minwidth`` are
  considered as valid album art candidates. Default: 0.
- **maxwidth**: A maximum image width to downscale fetched images if they are
  too big. The resize operation reduces image width to at most ``maxwidth``
  pixels. The height is recomputed so that the aspect ratio is preserved.
- **enforce_ratio**: Only images with a width:height ratio of 1:1 are
  considered as valid album art candidates. Default: ``no``.
- **remote_priority**: Query remote sources every time and use local image only
  as fallback.
  Default: ``no``; remote (Web) art sources are only queried if no local art is
  found in the filesystem.
- **sources**: List of sources to search for images. An asterisk `*` expands
  to all available sources.
  Default: ``coverart itunes amazon albumart``, i.e., everything but
  ``wikipedia`` and ``google``. Enable those two sources for more matches at
  the cost of some speed.
- **google_key**: Your Google API key (to enable the Google Custom Search
  backend).
  Default: None.
- **google_engine**: The custom search engine to use.
  Default: The `beets custom search engine`_, which searches the entire web.

Note: ``minwidth`` and ``enforce_ratio`` options require either `ImageMagick`_
or `Pillow`_.

.. _beets custom search engine: https://cse.google.com.au:443/cse/publicurl?cx=001442825323518660753:hrh5ch1gjzm
.. _Pillow: https://github.com/python-pillow/Pillow
.. _ImageMagick: http://www.imagemagick.org/

Here's an example that makes plugin select only images that contain *front* or
*back* keywords in their filenames and prioritizes the iTunes source over
others::

    fetchart:
        cautious: true
        cover_names: front back
        sources: itunes *


Manually Fetching Album Art
---------------------------

Use the ``fetchart`` command to download album art after albums have already
been imported::

    $ beet fetchart [-f] [query]

By default, the command will only look for album art when the album doesn't
already have it; the ``-f`` or ``--force`` switch makes it search for art
in Web databases regardless. If you specify a query, only matching albums will
be processed; otherwise, the command processes every album in your library.

.. _image-resizing:

Image Resizing
--------------

Beets can resize images using `Pillow`_, `ImageMagick`_, or a server-side resizing
proxy. If either Pillow or ImageMagick is installed, beets will use those;
otherwise, it falls back to the resizing proxy. If the resizing proxy is used,
no resizing is performed for album art found on the filesystem---only downloaded
art is resized. Server-side resizing can also be slower than local resizing, so
consider installing one of the two backends for better performance.

When using ImageMagick, beets looks for the ``convert`` executable in your path.
On some versions of Windows, the program can be shadowed by a system-provided
``convert.exe``. On these systems, you may need to modify your ``%PATH%``
environment variable so that ImageMagick comes first or use Pillow instead.

.. _Pillow: https://github.com/python-pillow/Pillow
.. _ImageMagick: http://www.imagemagick.org/

Album Art Sources
-----------------

By default, this plugin searches for art in the local filesystem as well as on
the Cover Art Archive, the iTunes Store, Amazon, and AlbumArt.org, in that
order.
You can reorder the sources or remove
some to speed up the process using the ``sources`` configuration option.

When looking for local album art, beets checks for image files located in the
same folder as the music files you're importing. Beets prefers to use an image
file whose name contains "cover", "front", "art", "album" or "folder", but in
the absence of well-known names, it will use any image file in the same folder
as your music files.

When you choose to apply changes during an import, beets will search for art as
described above.  For "as-is" imports (and non-autotagged imports using the
``-A`` flag), beets only looks for art on the local filesystem.

iTunes Store
''''''''''''

To use the iTunes Store as an art source, install the `python-itunes`_
library. You can do this using `pip`_, like so::

    $ pip install https://github.com/ocelma/python-itunes/archive/master.zip

(There's currently `a problem`_ that prevents a plain ``pip install
python-itunes`` from working.)
Once the library is installed, the plugin will use it to search automatically.

.. _a problem: https://github.com/ocelma/python-itunes/issues/9
.. _python-itunes: https://github.com/ocelma/python-itunes
.. _pip: http://pip.openplans.org/

Google custom search
''''''''''''''''''''

To use the google image search backend you need to
`register for a Google API key`_. Set the ``google_key`` configuration
option to your key, then add ``google`` to the list of sources in your
configuration.

.. _register for a Google API key: https://code.google.com/apis/console.

Optionally, you can `define a custom search engine`_. Get your search engine's
token and use it for your ``google_engine`` configuration option. The
default engine searches the entire web for cover art.

.. _define a custom search engine: http://www.google.com/cse/all

Note that the Google custom search API is limited to 100 queries per day.
After that, the fetchart plugin will fall back on other declared data sources.

Embedding Album Art
-------------------

This plugin fetches album art but does not embed images into files' tags. To do
that, use the :doc:`/plugins/embedart`. (You'll want to have both plugins
enabled.)
