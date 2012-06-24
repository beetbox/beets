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

Album Art Sources
-----------------

Currently, this plugin searches for art in the local filesystem, on Amazon.com,
and on AlbumArt.org (in that order).

When looking for local album art, beets looks for image files located in the
same folder as the music files you're importing. If you have an image file
called "cover," "front," "art," "album," for "folder" alongside your music,
beets will treat it as album art and skip searching any online databases.

Embedding Album Art
-------------------

This plugin fetches album art but does not embed images into files' tags. To do
that, use the :doc:`/plugins/embedart`. (You'll want to have both plugins
enabled.)
