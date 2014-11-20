Permissions Plugin
==================

The ``permissions`` plugin allows you to set file permissions after they got written.

To use the ``permissions`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make an ``permissions:`` section in your configuration
file. You need to use **octal modes** to configure permissions. 

Here's an example::

    permissions:
        file: 644
