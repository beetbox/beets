Unimported Plugin
=================

The ``unimported`` plugin allows one to list all files in the library folder
which are not listed in the beets library database, including art files.

Command Line Usage
------------------

To use the ``unimported`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``beet unimported`` command.
The command will list all files in the library folder which are not imported.
You can exclude file extensions or entire subdirectories using the configuration
file:

::

    unimported:
        ignore_extensions: jpg png
        ignore_subdirectories: NonMusic data temp
        ignore_as_globs: false

The default configuration lists all unimported files, ignoring no extensions.

When true, the ``ignore_as_globs`` parameter uses the same way of parsing files
as beets, using the ``ignore_subdirectories`` as globs whatever the depth,
instead of excluding them if they are the direct child of the library root.
