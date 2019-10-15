Play Plugin
===========

The ``unimported`` plugin allows to list all files in the library folder which are not imported.

Command Line Usage
------------------

To use the ``unimported`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``beet unimported`` command.
The command will list all files in the library folder which are not imported. You can
exclude file extensions using the configuration file::

    unimported:
        ignore_extensions: [jpg,png] # default []



