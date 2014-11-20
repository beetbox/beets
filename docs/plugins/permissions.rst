Permissions Plugin
==================

The ``permissions`` plugin allows you to set file permissions for imported
music files.

To use the ``permissions`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Permissions will be adjusted automatically on import.

Configuration
-------------

To configure the plugin, make an ``permissions:`` section in your configuration
file. The ``file`` config value therein uses **octal modes** to specify the
desired permissions. The default flags are octal 644.

Here's an example::

    permissions:
        file: 644
