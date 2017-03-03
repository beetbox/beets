KodiUpdate Plugin
=================

``kodiupdate`` is a very simple plugin for beets that lets you automatically
update `Kodi`_'s music library whenever you change your beets library.

To use ``kodiupdate`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your Kodi host.
You can do that using a ``kodi:`` section in your ``config.yaml``,
which looks like this::

    kodi:
        host: localhost
        port: 8080
        user: kodi
        pwd: kodi

To use the ``kodiupdate`` plugin you need to install the `requests`_ library with:

    pip install requests

You'll also need to enable jsonrpc in Kodi in order the use the plugin.
(System/Settings/Network/Services > Allow control of Kodi via HTTP)

With that all in place, you'll see beets send the "update" command to your Kodi
host every time you change your beets library.

.. _Kodi: http://kodi.tv/
.. _requests: http://docs.python-requests.org/en/latest/

Configuration
-------------

The available options under the ``kodi:`` section are:

- **host**: The Kodi host name.
  Default: ``localhost``
- **port**: The Kodi host port.
  Default: 8080
- **user**: The Kodi host user.
  Default: ``kodi``
- **pwd**: The Kodi host password.
  Default: ``kodi``
