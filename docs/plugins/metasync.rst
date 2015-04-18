MetaSync Plugin
===============

This plugin provides the ``metasync`` command, which lets you fetch certain
metadata from other local or remote sources, for example your favorite audio
player.

Currently we support the following list of metadata sources:
- **amarok**: This syncs rating, score, first played, last played, playcount and uid from amarok.


Installing Dependencies
-----------------------

Fetching metadata from amarok requires the dbus-python library.

There are packages for most major linux distributions, or you can download the
library from its _website.

   _website: http://dbus.freedesktop.org/releases/dbus-python/


Configuration
-------------

To configure the plugin, make a ``metasync:`` section in your configuration
file. The available options are:

- **source**: A list of sources to fetch metadata from.
  Default: empty


Usage
-----

Enable the ``metasync`` plugin in your configuration (see
:ref:`using-plugins`) then run ``beet metasync QUERY`` to fetch updated
metadata from the configured list of sources.

The command has a few command-line options:

* To preview the changes that would be made without applying them, use the
  ``-p`` (``--pretend``) flag.
* To specify a temporary source to fetch metadata from, use the ``-s``
  (``--source``) flag.
