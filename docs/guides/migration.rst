Upgrading from 1.0
==================

Prior to version 1.1, beets used a completely different system for
configuration. The config file was in "INI" syntax instead of `YAML`_ and the
various files used by beets were (messily) stored in ``$HOME`` instead of a
centralized beets directory. If you're upgrading from version 1.0 or earlier,
your configuration syntax (and paths) need to be updated to work with the
latest version.

Fortunately, this should require very little effort on your part. When you
first run beets 1.1, it will look for an old-style ``.beetsconfig`` to
migrate. If it finds one (and there is no new-style
``config.yaml`` yet), beets will warn you and then
transparently convert one to the other. At this point, you'll likely want to:

* Look at your new configuration file (find out where in
  :doc:`/reference/config`) to make sure everything was migrated correctly.
* Remove your old configuration file (``~/.beetsconfig`` on Unix;
  ``%APPDATA%\beetsconfig.ini`` on Windows) to avoid confusion in the future.

You might be interested in the :doc:`/changelog` to see which configuration
option names have changed.

What's Migrated
---------------

Automatic migration is most important for the configuration file, since its
syntax is completely different, but two other files are also moved. This is to
consolidate everything beets needs in a single directory instead of leaving it
messily strewn about in your home directory.

First, the library database file was at ``~/.beetsmusic.blb`` on Unix and
``%APPDATA%\beetsmusic.blb`` on Windows. This file will be copied to
``library.db`` in the same directory as your new configuration file. Finally,
the runtime state file, which keeps track of interrupted and incremental
imports, was previously known as ``~/.beetsstate``; it is copied to a file
called ``state.pickle``.

Feel free to remove the old files once they've been copied to their new homes.

Manual Migration
----------------

If you find you need to re-run the migration process, just type ``beet
migrate`` in your shell. This will migrate the configuration file, the
database, and the runtime state file all over again. Unlike automatic
migration, no step is suppressed if the file already exists. If you already
have a ``config.yaml``, for example, it will be renamed to make room for the
newly migrated configuration.

.. _YAML: http://en.wikipedia.org/wiki/YAML
