Thumbnails Plugin
==================

The ``thumbnails`` plugin creates thumbnails for your album folders with the
album cover. This works on freedesktop.org-compliant file managers such as
Nautilus or Thunar, and is therefore POSIX-only.

To use the ``thumbnails`` plugin, enable it (see :doc:`/plugins/index`) as well
as the :doc:`/plugins/fetchart`.  You'll need 2 additional python packages:
:pypi:`pyxdg` and :pypi:`pathlib`.

``thumbnails`` needs to resize the covers, and therefore requires either
`ImageMagick`_ or `Pillow`_.

.. _Pillow: https://github.com/python-pillow/Pillow
.. _ImageMagick: http://www.imagemagick.org/

Configuration
-------------

To configure the plugin, make a ``thumbnails`` section in your configuration
file. The available options are

- **auto**: Whether the thumbnail should be automatically set on import.
  Default: ``yes``.
- **force**: Generate the thumbnail even when there's one that seems fine (more
  recent than the cover art).
  Default: ``no``.
- **dolphin**: Generate dolphin-compatible thumbnails. Dolphin (KDE file
  explorer) does not respect freedesktop.org's standard on thumbnails. This
  functionality replaces the :doc:`/plugins/freedesktop`
  Default: ``no``

Usage
-----

The ``thumbnails`` command provided by this plugin creates a thumbnail for
albums that match a query (see :doc:`/reference/query`).
