PlexUpdate Plugin
=================

The ``plexupdate`` plugin automatically refreshes the music library on your
Plex_ Media Server whenever your beets library changes.

Why Use the PlexUpdate Plugin?
------------------------------

The PlexUpdate plugin allows you to:

- Keep the music library on your Plex Media Server in sync with beets
- Avoid having to trigger a library scan in Plex manually
- Refresh Plex automatically after imports, edits, moves, and other commands
  that modify your library

Once configured, the refresh happens automatically whenever a beets command
changes your library, so you don't need to think about it.

Requirements
------------

- A running Plex Media Server instance that beets can reach over the network

Installation
------------

To use the ``plexupdate`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with the ``plexupdate`` extra:

.. code-block:: bash

    pip install "beets[plexupdate]"

Authentication
--------------

Plex requires an authentication token for API requests. The easiest way to
obtain one is the interactive login:

.. code-block:: bash

    beet plexupdate --auth

This opens a browser window where you can log in to your Plex account and
authorize beets. After a successful login, the access token is stored in the
token file (see the ``tokenfile`` option below), and beets uses it to update
your library on subsequent runs.

.. dropdown:: Alternative Authentication

    Alternatively, the ``token`` configuration option provides a legacy way to
    authenticate: it accepts a token from your Plex account directly (see Plex's
    `documentation about tokens`_). It should not be used for new setups, though --
    run ``beet plexupdate --auth`` instead, which stores the token in the token
    file and keeps it out of your configuration.

Basic Usage
-----------

Enable the ``plexupdate`` plugin (see :ref:`using-plugins`) and, optionally,
configure your Plex server as described below. Whenever a beets command modifies
your library (for example ``beet import``, ``beet modify``, or ``beet move``)
the plugin tells Plex to refresh its music library when the command finishes.

You can verify the refresh in the Plex web interface: the activity view of your
music library shows the scan started by beets.

Configuration
-------------

The plugin is configured under the ``plex:`` section!

Default
~~~~~~~

.. code-block:: yaml

    plex:
        host: localhost
        port: 32400
        library_name: Music
        secure: no
        ignore_cert_errors: no
        tokenfile: plex_token.json

.. conf:: host
    :default: localhost

    The hostname or IP address of the Plex Media Server.

.. conf:: port
    :default: 32400

    The port on which the Plex Media Server listens.

.. conf:: library_name
    :default: Music

    The name of the Plex library to refresh.

.. conf:: secure
    :default: no

    Use HTTPS instead of HTTP when connecting to the Plex Media Server.
    Enable this when your server is only reachable over a secure connection,
    for example through a reverse proxy.

.. conf:: ignore_cert_errors
    :default: no

    Ignore TLS certificate errors when ``secure`` is enabled. Useful when
    the server uses a self-signed certificate.

.. conf:: tokenfile
    :default: plex_token.json

    The file where the token obtained via ``beet plexupdate --auth`` is
    stored together with the client identifier used for the login. The file
    is created in the beets configuration directory.

.. conf:: token
    :default: ""

    .. deprecated:: 2.14 Use ``beet plexupdate --auth`` instead.

    A Plex token that overrides the token stored by ``beet plexupdate
    --auth``. Kept for legacy configurations that cannot use the interactive
    login, for example Plex Home accounts. This value is never written to the
    token file and is redacted in beets' configuration listings.

.. _documentation about tokens: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

.. _plex: https://www.plex.tv/
