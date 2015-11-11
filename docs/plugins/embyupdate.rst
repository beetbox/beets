EmbyUpdate Plugin
=================

``embyupdate`` is a plugin that lets you automatically update `Emby`_'s library whenever you change your beets library.

To use ``embyupdate`` plugin, enable it in your configuration (see :ref:`using-plugins`). Then, you'll probably want to configure the specifics of your Emby server. You can do that using an ``emby:`` section in your ``config.yaml``, which looks like this::

    emby:
        host: localhost
        port: 8096
        username: user
        password: password

To use the ``embyupdate`` plugin you need to install the `requests`_ library with::

    pip install requests

With that all in place, you'll see beets send the "update" command to your Emby server every time you change your beets library.

.. _Emby: http://emby.media/
.. _requests: http://docs.python-requests.org/en/latest/

Configuration
-------------

The available options under the ``emby:`` section are:

- **host**: The Emby server name.
  Default: ``localhost``
- **port**: The Emby server port.
  Default: 8096
- **username**: A username of a Emby user that is allowed to refresh the library.
- **password**: That user's password.
