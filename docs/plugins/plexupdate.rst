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
        token: token

The ``token`` key is optional: you'll need to use it when in a Plex Home (see Plex's own `documentation about tokens`_).

To use the ``plexupdate`` plugin you need to install the `requests`_ library with:

    pip install requests

With that all in place, you'll see beets send the "update" command to your Plex
server every time you change your beets library.

.. _Plex: https://plex.tv/
.. _requests: https://requests.readthedocs.io/en/master/
.. _documentation about tokens: https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token

Configuration
-------------

The available options under the ``plex:`` section are:

- **host**: The Plex server name.
  Default: ``localhost``.
- **port**: The Plex server port.
  Default: 32400.
- **token**: The Plex Home token.
  Default: Empty.
- **library_name**: The name of the Plex library to update.
  Default: ``Music``
- **secure**: Use secure connections to the Plex server.
  Default: ``False``
- **ignore_cert_errors**: Ignore TLS certificate errors when using secure connections.
  Default: ``False``
