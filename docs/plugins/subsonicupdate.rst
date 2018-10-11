SubsonicUpdate Plugin
=====================

``subsonicupdate`` is a very simple plugin for beets that lets you automatically
update `Subsonic`_'s index whenever you change your beets library.

.. _Subsonic: http://www.subsonic.org

To use ``subsonicupdate`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your Subsonic server.
You can do that using a ``subsonic:`` section in your ``config.yaml``,
which looks like this::

    subsonic:
        host: X.X.X.X
        port: 4040
        user: username
        pass: password
        contextpath: /subsonic

With that all in place, beets will send a Rest API to your Subsonic
server every time you import new music.
Due to a current limitation of the API, all libraries visible to that user will be scanned.

This plugin requires Subsonic v6.1 or higher and an active Premium license (or trial).

Configuration
-------------

The available options under the ``subsonic:`` section are:

- **host**: The Subsonic server name/IP. Default: ``localhost``
- **port**: The Subsonic server port. Default: ``4040``
- **user**: The Subsonic user. Default: ``admin``
- **pass**: The Subsonic user password. Default: ``admin``
- **contextpath**: The Subsonic context path. Default: ``/``
