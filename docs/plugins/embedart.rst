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

This behavior can be disabled with the ``auto`` config option (see below).

.. _image-similarity-check:

Checking image similarity before embedding
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

When importing a lot of files with the ``auto`` option, one may be reluctant to
overwrite existing embedded art for all of them.

It's possible to tell beets to embed fetched art only if it corresponds to a
similar image than already embedded art. This works by computing the perceptual
hashes (`PHASH`_) of the two images and checking that the difference between
the two does not exceed a given threshold.
The threshold used is given by the ``compare_threshold`` option:

* use '0' to always embed image (disable similarity check)

* use any positive integer to define a similarity threshold. The smaller the
  value, the more similar the images must be. A value in the range [10,100] is
  recommended.

Requires `ImageMagick`_

Manually Embedding and Extracting Art
-------------------------------------

The ``embedart`` plugin provides a couple of commands for manually managing
embedded album art:

* ``beet embedart [-f IMAGE] QUERY``: embed images into the every track on the
  albums matching the query. If the ``-f`` (``--file``) option is given, then
  use a specific image file from the filesystem; otherwise, each album embeds
  its own currently associated album art.

* ``beet extractart [-o FILE] QUERY``: extracts the image from an item matching
  the query and stores it in a file. You can specify the destination file using
  the ``-o`` option, but leave off the extension: it will be chosen
  automatically. The destination filename defaults to ``cover`` if it's not
  specified.

* ``beet clearart QUERY``: removes all embedded images from all items matching
  the query. (Use with caution!)

Configuring
-----------

The ``auto`` option  lets you disable automatic album art embedding.
To do so, add this to your ``config.yaml``::

    embedart:
        auto: no

A maximum image width can be configured as ``maxwidth`` to downscale images
before embedding them (the original image file is not altered). The resize
operation reduces image width to ``maxwidth`` pixels. The height is recomputed
so that the aspect ratio is preserved.
Requires `ImageMagick`_ or `PIL`_, see :ref:`image-resizing` for further
caveats about image resizing.

The ``compare_threshold`` option defines how similar must candidate art be
regarding to embedded art to be written to the file, see
:ref:`image-similarity-check` for more infos.
By default the option is set to '0' (candidate art is always written to file).
Requires `ImageMagick`_


.. _PIL: http://www.pythonware.com/products/pil/
.. _ImageMagick: http://www.imagemagick.org/
.. _PHASH: http://www.fmwconcepts.com/misc_tests/perceptual_hash_test_results_510/
