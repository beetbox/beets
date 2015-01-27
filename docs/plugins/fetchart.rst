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
- **google_search**: Gather images from Google Image Search.
  Default: ``no``.
- **maxwidth**: A maximum image width to downscale fetched images if they are
  too big. The resize operation reduces image width to at most ``maxwidth``
  pixels. The height is recomputed so that the aspect ratio is preserved.
- **remote_priority**: Query remote sources every time and use local image only
  as fallback.
  Default: ``no``; remote (Web) art sources are only queried if no local art is
  found in the filesystem.
- **sources**: List of sources to search for images. An asterisk `*` expands
  to all available sources.
  Default: ``coverart itunes albumart amazon google wikipedia``, i.e.,
  all sources.

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

Beets can resize images using `PIL`_, `ImageMagick`_, or a server-side resizing
proxy. If either PIL or ImageMagick is installed, beets will use those;
otherwise, it falls back to the resizing proxy. If the resizing proxy is used,
no resizing is performed for album art found on the filesystem---only downloaded
art is resized. Server-side resizing can also be slower than local resizing, so
consider installing one of the two backends for better performance.

When using ImageMagic, beets looks for the ``convert`` executable in your path.
On some versions of Windows, the program can be shadowed by a system-provided
``convert.exe``. On these systems, you may need to modify your ``%PATH%``
environment variable so that ImageMagick comes first or use PIL instead.

.. _PIL: http://www.pythonware.com/products/pil/
.. _ImageMagick: http://www.imagemagick.org/

Album Art Sources
-----------------

By default, this plugin searches for art in the local filesystem as well as on
the Cover Art Archive, the iTunes Store, Amazon, AlbumArt.org,
and Google Image Search, and Wikipedia, in that order. You can reorder the sources or remove
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

    $ pip install python-itunes

Once the library is installed, the plugin will use it to search automatically.

.. _python-itunes: https://github.com/ocelma/python-itunes
.. _pip: http://pip.openplans.org/

Google Image Search
'''''''''''''''''''

You can optionally search for cover art on `Google Images`_. This option uses
the first hit for a search query consisting of the artist and album name. It
is therefore approximate: "incorrect" image matches are possible (although
unlikely).

.. _Google Images: http://images.google.com/


Embedding Album Art
-------------------

This plugin fetches album art but does not embed images into files' tags. To do
that, use the :doc:`/plugins/embedart`. (You'll want to have both plugins
enabled.)
