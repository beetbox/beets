EmbyUpdate Plugin
=================

``embyupdate`` is a plugin that lets you automatically update `Emby`_'s library whenever you change your beets library.

To use ``embyupdate`` plugin, enable it in your configuration (see :ref:`using-plugins`). Then, you'll want to configure the specifics of your Emby server. You can do that using an ``emby:`` section in your ``config.yaml``, which looks like this::

    emby:
        host: localhost
        port: 8096
        username: user
        apikey: apikey

To use the ``embyupdate`` plugin you need to install the `requests`_ library with::

    pip install requests

With that all in place, you'll see beets send the "update" command to your Emby server every time you change your beets library.

.. _Emby: https://emby.media/
.. _requests: https://requests.readthedocs.io/en/master/

Configuration
-------------

The available options under the ``emby:`` section are:

- **host**: The Emby server host. You also can include ``http://`` or ``https://``.
  Default: ``localhost``
- **port**: The Emby server port.
  Default: 8096
- **username**: A username of a Emby user that is allowed to refresh the library.
- **apikey**: An Emby API key for the user.
- **password**: The password for the user. (This is only necessary if no API
  key is provided.)

You can choose to authenticate either with ``apikey`` or ``password``, but only
one of those two is required.
