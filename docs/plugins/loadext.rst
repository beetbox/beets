Load Extension Plugin
=====================

Beets uses an SQLite database to store and query library information, which
has support for extensions to extend its functionality. The ``loadext`` plugin
lets you enable these SQLite extensions within beets.

One of the primary uses of this within beets is with the `"ICU" extension`_,
which adds support for case insensitive querying of non-ASCII characters.

.. _"ICU" extension: https://www.sqlite.org/src/dir?ci=7461d2e120f21493&name=ext/icu

Configuration
-------------

To configure the plugin, make a ``loadext`` section in your configuration
file. The section must consist of a list of paths to extensions to load, which
looks like this:

.. code-block:: yaml

    loadext:
      - libicu

If a relative path is specified, it is resolved relative to the beets
configuration directory.

If no file extension is specified, the default dynamic library extension for
the current platform will be used.

Building the ICU extension
--------------------------
This section is for **advanced** users only, and is not an in-depth guide on
building the extension.

To compile the ICU extension, you will need a few dependencies:

 - gcc
 - icu-devtools
 - libicu
 - libicu-dev
 - libsqlite3-dev

Here's roughly how to download, build and install the extension (although the
specifics may vary from system to system):

.. code-block:: shell

    $ wget https://sqlite.org/2019/sqlite-src-3280000.zip
    $ unzip sqlite-src-3280000.zip
    $ cd sqlite-src-3280000/ext/icu
    $ gcc -shared -fPIC icu.c `icu-config --ldflags` -o libicu.so
    $ cp libicu.so ~/.config/beets
