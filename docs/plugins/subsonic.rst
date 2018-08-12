Subsonic Plugin
================

``Subsonic`` is a very simple plugin for beets that lets you automatically
update `Subsonic`_'s index whenever you change your beets library.

.. _Subsonic: http://www.subsonic.org

To use ``Subsonic`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll probably want to configure the specifics of your Subsonic server.
You can do that using an ``subsonic:`` section in your ``config.yaml``,
which looks like this::

    subsonic: 
        host: 192.168.x.x
        port: 4040
        user: username
        pass: password

With that all in place, beets will send a Rest API to your Subsonic
server every time you change your beets library.

This plugin requires the Premium version of Subsonic (or a Trial Premium version).
This plugin requires Subsonic version 6.1 or higher. 

Configuration
-------------

The available options under the ``subsonic:`` section are:

- **host**: The Subsonic server name/IP.
- **port**: The Subsonic server port.
- **user**: The Subsonic user.
- **pass**: The Subsonic user password.

This plugin does not set default values for the above values.
