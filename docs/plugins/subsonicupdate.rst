SubsonicUpdate Plugin
=====================

``subsonicupdate`` is a very simple plugin for beets that lets you automatically
update `Subsonic`_'s index whenever you change your beets library.

.. _Subsonic: https://www.subsonic.org

To use ``subsonicupdate`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your Subsonic server.
You can do that using a ``subsonic:`` section in your ``config.yaml``,
which looks like this::

    subsonic:
        url: https://example.com:443/subsonic
        user: username
        pass: password

\* NOTE: The pass config option can either be clear text or hex-encoded with a "enc:" prefix.

With that all in place, beets will send a Rest API to your Subsonic
server every time you import new music.
Due to a current limitation of the API, all libraries visible to that user will be scanned.

This plugin requires Subsonic v6.1 or higher and an active Premium license (or trial).

Configuration
-------------

The available options under the ``subsonic:`` section are:

- **url**: The Subsonic server resource. Default: ``http://localhost:4040``