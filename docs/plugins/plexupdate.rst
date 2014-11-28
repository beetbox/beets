PlexUpdate Plugin
=================

``plexupdate`` is a very simple plugin for beets that lets you automatically
update `Plex`_'s music library whenever you change your beets library.

To use ``plexupdate`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your Plex server.
You can do that using an ``plex:`` section in your ``config.yaml``,
which looks like this::

    plex:
        host: localhost
        port: 32400

To use the ``plexupdate`` plugin you need to install the `requests`_ library with:

    pip install requests

With that all in place, you'll see beets send the "update" command to your Plex 
server every time you change your beets library.

.. _Plex: http://plex.tv/
.. _requests: http://docs.python-requests.org/en/latest/

Configuration
-------------

The available options under the ``plex:`` section are:

- **host**: The Plex server name.
  Default: ``localhost``.
- **port**: The Plex server port.
  Default: 32400.
