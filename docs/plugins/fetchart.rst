FetchArt Plugin
===============

The ``fetchart`` plugin retrieves album art images from various sources on the
Web and stores them as image files.


Fetching Album Art During Import
--------------------------------

To automatically get album art for every album you import, just enable the
plugin by putting ``fetchart`` on your config file's ``plugins`` line (see
:doc:`/plugins/index`).

By default, beets stores album art image files alongside the music files for an
album in a file called ``cover.jpg``. To customize the name of this file, use
the :ref:`art-filename` config option.

To disable automatic art downloading, just put this in your configuration
file::

    [fetchart]
    autofetch: no

Manually Fetching Album Art
---------------------------

Use the ``fetchart`` command to download album art after albums have already
been imported::

    $ beet fetchart [-f] [query]

By default, the command will only look for album art when the album doesn't
already have it; the ``-f`` or ``--force`` switch makes it search for art
regardless. If you specify a query, only matching albums will be processed;
otherwise, the command processes every album in your library.

Image Resizing
--------------

A maximum image width can be configured as ``maxwidth`` to downscale fetched
images if they are too big. The resize operation reduces image width to
``maxwidth`` pixels. The height is recomputed so that the aspect ratio is
preserved.

Beets can resize images using `PIL`_, `ImageMagick`_, or a server-side resizing
proxy. If either PIL or ImageMagick is installed, beets will use those;
otherwise, it falls back to the resizing proxy. Since server-side resizing can
be slow, consider installing one of the two backends for better performance.

.. _PIL: http://www.pythonware.com/products/pil/
.. _ImageMagick: http://www.imagemagick.org/

Album Art Sources
-----------------

Currently, this plugin searches for art in the local filesystem as well as on
the Cover Art Archive, Amazon, and AlbumArt.org (in that order).

When looking for local album art, beets checks for image files located in the
same folder as the music files you're importing. If you have an image file
called "cover," "front," "art," "album," for "folder" alongside your music,
beets will treat it as album art and skip searching any online databases.

When you choose to apply changes during an import, beets searches all sources
for album art. For "as-is" imports (and non-autotagged imports using the ``-A``
flag), beets only looks for art on the local filesystem.

Embedding Album Art
-------------------

This plugin fetches album art but does not embed images into files' tags. To do
that, use the :doc:`/plugins/embedart`. (You'll want to have both plugins
enabled.)
