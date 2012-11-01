EmbedArt Plugin
===============

Typically, beets stores album art in a "file on the side": along with each
album, there is a file (named "cover.jpg" by default) that stores the album art.
You might want to embed the album art directly into each file's metadata. While
this will take more space than the external-file approach, it is necessary for
displaying album art in some media players (iPods, for example).

This plugin was added in beets 1.0b8.

Embedding Art Automatically
---------------------------

To automatically embed discovered album art into imported files, just enable the
plugin (see :doc:`/plugins/index`). You'll also want to enable the
:doc:`/plugins/fetchart` to obtain the images to be embedded. Art will be
embedded after each album is added to the library.

This behavior can be disabled with the ``autoembed`` config option (see below).

Manually Embedding and Extracting Art
-------------------------------------

The ``embedart`` plugin provides a couple of commands for manually managing
embedded album art:

* ``beet embedart IMAGE QUERY``: given an image file and a query matching an
  album, embed the image into the metadata of every track on the album.

* ``beet extractart [-o FILE] QUERY``: extracts the image from an item matching
  the query and stores it in a file. You can specify the destination file using
  the ``-o`` option, but leave off the extension: it will be chosen
  automatically. The destination filename defaults to ``cover`` if it's not
  specified.

* ``beet clearart QUERY``: removes all embedded images from all items matching
  the query. (Use with caution!)

Configuring
-----------

``autoembed`` option  lets you disable automatic album art embedding. 
To do so, add this to your ``~/.beetsconfig``::

    [embedart]
    autoembed: no

A maximum image width can be configured as ``maxwidth`` to downscale images
before embedding them (the original image file is not altered). The resize
operation reduces image width to ``maxwidth`` pixels. The height is recomputed
so that the aspect ratio is preserved. `PIL`_ or `ImageMagick`_ is required to
use the ``maxwidth`` config option.

.. _PIL: http://www.pythonware.com/products/pil/
.. _ImageMagick: http://www.imagemagick.org/
