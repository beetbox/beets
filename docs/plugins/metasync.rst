MetaSync Plugin
===============

This plugin provides the ``metasync`` command, which lets you fetch certain
metadata from other sources: for example, your favorite audio player.

Currently, the plugin supports synchronizing with the `Amarok`_ music player.
It can fetch the rating, score, first-played date, last-played date, play
count, and track uid from Amarok.

.. _Amarok: https://amarok.kde.org/


Installation
------------

Enable the ``metasync`` plugin in your configuration (see
:ref:`using-plugins`).

To synchronize with Amarok, you'll need the `dbus-python`_ library. There are
packages for most major Linux distributions.

.. _dbus-python: http://dbus.freedesktop.org/releases/dbus-python/


Configuration
-------------

To configure the plugin, make a ``metasync:`` section in your configuration
file. The available options are:

- **source**: A list of sources to fetch metadata from. Set this to "amarok"
  to enable synchronization with that player.
  Default: empty


Usage
-----

Run ``beet metasync QUERY`` to fetch metadata from the configured list of
sources.

The command has a few command-line options:

* To preview the changes that would be made without applying them, use the
  ``-p`` (``--pretend``) flag.
* To specify a temporary source to fetch metadata from, use the ``-s``
  (``--source``) flag.
