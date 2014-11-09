Freedesktop Plugin
==================

The ``freedesktop`` plugin creates .directory files in your album folders.
This lets Freedesktop.org compliant file managers such as Dolphin or Nautilus
to use an album's cover art as the folder's thumbnail.

To use the ``freedesktop`` plugin, enable it (see :doc:`/plugins/index`).

Configuration
-------------

To configure the plugin, make a ``freedesktop:`` section in your configuration
file. The only available option is:

- **auto**: Create .directory files automatically during import.
  Default: ``no``.

Creating .directory Files Manually
----------------------------------

The ``freedesktop`` command provided by this plugin creates .directory files
for albums that match a query (see :doc:`/reference/query`). For example, ``beet
freedesktop man the animal cannon`` will create the .directory file for the
folder containing the album Man the Animal Cannon.
