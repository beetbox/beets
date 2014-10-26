MPDUpdate Plugin
================

``mpdupdate`` is a very simple plugin for beets that lets you automatically
update `MPD`_'s index whenever you change your beets library.

.. _MPD: http://www.musicpd.org/

To use it, enable it in your configuration (see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your MPD server.
You can do that using an ``mpd:`` section in your ``config.yaml``,
which looks like this::

    mpd:
        host: localhost
        port: 6600
        password: seekrit

With that all in place, you'll see beets send the "update" command to your MPD server every time you change your beets library.

If you want to communicate with MPD over a Unix domain socket instead over
TCP, just give the path to the socket in the filesystem for the ``host``
setting. (Any ``host`` value starting with a slash or a tilde is interpreted as a domain
socket.)

Configuration
-------------

Available options :

- ``host``: mpd server name.
  Default: ``localhost``.
- ``password``: mpd server password.
  Default: ``u''``
- ``port``: mpd server port.
  Default: ``6600``.
