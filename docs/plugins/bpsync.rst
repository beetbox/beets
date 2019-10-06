BPSync Plugin
=============

This plugin provides the ``bpsync`` command, which lets you fetch metadata
from Beatport for albums and tracks that already have Beatport IDs.
This plugin works similarly to :doc:`/plugins/mbsync`.

If you have downloaded music from Beatport, this can speed
up the initial import if you just import "as-is" and then use ``bpsync`` to
get up-to-date tags that are written to the files according to your beets
configuration.


Usage
-----

Enable the ``bpsync`` plugin in your configuration (see :ref:`using-plugins`)
and then run ``beet bpsync QUERY`` to fetch updated metadata for a part of your
collection (or omit the query to run over your whole library).

This plugin treats albums and singletons (non-album tracks) separately. It
first processes all matching singletons and then proceeds on to full albums.
The same query is used to search for both kinds of entities.

The command has a few command-line options:

* To preview the changes that would be made without applying them, use the
  ``-p`` (``--pretend``) flag.
* By default, files will be moved (renamed) according to their metadata if
  they are inside your beets library directory. To disable this, use the
  ``-M`` (``--nomove``) command-line option.
* If you have the ``import.write`` configuration option enabled, then this
  plugin will write new metadata to files' tags. To disable this, use the
  ``-W`` (``--nowrite``) option.
