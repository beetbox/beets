ImportSource Plugin
===================

The ``importsource`` plugin adds a ``source_path`` field to every item imported
to the library which stores the original media files' paths. Using this plugin
makes most sense when the general importing workflow is using ``beet import
--copy``. Additionally the plugin interactively suggests deletion of original
source files whenever items are removed from the Beets library.

To enable it, add ``importsource`` to the list of plugins in your configuration
(see :ref:`using-plugins`).

Tracking Source Paths
---------------------

The primary use case for the plugin is tracking the original location of
imported files using the ``source_path`` field. Consider this scenario: you've
imported all directories in your current working directory using:

.. code-block:: bash

    beet import --flat --copy */

Later, for instance if the import didn't complete successfully, you'll need to
rerun the import but don't want Beets to re-process the already successfully
imported directories. You can view which files were successfully imported using:

.. code-block:: bash

    beet ls source_path:$PWD --format='$source_path'

To extract just the directory names, pipe the output to standard UNIX utilities:

.. code-block:: bash

    beet ls source_path:$PWD --format='$source_path' | awk -F / '{print $(NF-1)}' | sort -u

This might help to find out what's left to be imported.

Removal Suggestion
------------------

Another feature of the plugin is suggesting removal of original source files
when items are deleted from your library. Consider this scenario: you imported
an album using:

.. code-block:: bash

    beet import --copy --flat ~/Desktop/interesting-album-to-check/

After listening to that album and deciding it wasn't good, you want to delete it
from your library as well as from your ``~/Desktop``, so you run:

.. code-block:: bash

    beet remove --delete source_path:$HOME/Desktop/interesting-album-to-check

After approving the deletion, the plugin will prompt:

.. code-block:: text

    The item:
    <music-library>/Interesting Album/01 Interesting Song.flac
    is originated from:
    <HOME>/Desktop/interesting-album-to-check/01-interesting-song.flac
    What would you like to do?
    Delete the item's source, Recursively delete the source's directory,
    do Nothing,
    do nothing and Stop suggesting to delete items from this album?

Configuration
-------------

To configure the plugin, make an ``importsource:`` section in your configuration
file. There is one option available:

- **suggest_removal**: By default ``importsource`` suggests to remove the
  original directories / files from which the items were imported whenever
  library items (and files) are removed. To disable these prompts set this
  option to ``no``. Default: ``yes``.
