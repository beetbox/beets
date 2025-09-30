Getting Started
===============

Welcome to beets_! This guide will help get started with improving and
organizing your music collection.

.. _beets: https://beets.io/

Quick Installation
------------------

Beets is distributed via PyPI_ and can be installed by most users with a single
command:

.. include:: installation.rst
    :start-after: <!-- start-quick-install -->
    :end-before: <!-- end-quick-install -->

.. admonition:: Need more installation options?

    Having trouble with the commands above? Looking for package manager
    instructions? See the :doc:`complete installation guide
    </guides/installation>` for:

    - Operating system specific instructions
    - Package manager options
    - Troubleshooting help

.. _pypi: https://pypi.org/project/beets/

Basic Configuration
-------------------

Before using beets, you'll need a configuration file. This YAML_ file tells
beets where to store your music and how to organize it.

While beets is highly configurable, you only need a few basic settings to get
started.

1. **Open the config file:**
       .. code-block:: console

           beet config -e

       This creates the file (if needed) and opens it in your default editor.
       You can also find its location with ``beet config -p``.
2. **Add required settings:**
       In the config file, set the ``directory`` option to the path where you
       want beets to store your music files. Set the ``library`` option to the
       path where you want beets to store its database file.

       .. code-block:: yaml

           directory: ~/music
           library: ~/data/musiclibrary.db
3. **Choose your import style** (pick one):
       Beets offers flexible import strategies to match your workflow. Choose
       one of the following approaches and put one of the following in your
       config file:

       .. tab-set::

           .. tab-item:: Copy Files (Default)

               This is the default configuration and assumes you want to start a new organized music folder (inside ``directory`` above). During import we will *copy* cleaned-up music into that empty folder.

               .. code-block:: yaml

                   import:
                       copy: yes    # Copy files to new location


           .. tab-item:: Move Files

               Start with a new empty directory, but *move* new music in instead of copying it (saving disk space).

               .. code-block:: yaml

                   import:
                       move: yes    # Move files to new location

           .. tab-item:: Use Existing Structure

               Keep your current directory structure; importing should never move or copy files but instead just correct the tags on music. Make sure to point ``directory`` at the place where your music is currently stored.

               .. code-block:: yaml

                   import:
                       copy: no     # Use files in place

           .. tab-item:: Read-Only Mode

               Keep everything exactly as-is; only track metadata in database. (Corrected tags will still be stored in beets' database, and you can use them to do renaming or tag changes later.)

               .. code-block:: yaml

                   import:
                       copy: no     # Use files in place
                       write: no    # Don't modify tags
4. **Add customization via plugins (optional):**
       Beets comes with many plugins that extend its functionality. You can
       enable plugins by adding a `plugins` section to your config file.

       We recommend adding at least one :ref:`Autotagger Plugin
       <autotagger_extensions>` to help with fetching metadata during import.
       For getting started, :doc:`MusicBrainz </plugins/musicbrainz>` is a good
       choice.

       .. code-block:: yaml

           plugins:
             - musicbrainz  # Example plugin for fetching metadata
             - ... other plugins you want ...

       You can find a list of available plugins in the :doc:`plugins index
       </plugins/index>`.

.. _yaml: https://yaml.org/

To validate that you've set up your configuration and it is valid YAML, you can
type ``beet version`` to see a list of enabled plugins or ``beet config`` to get
a complete listing of your current configuration.

.. dropdown:: Full configuration file

    Here's a sample configuration file that includes the settings mentioned above:

    .. code-block:: yaml

        directory: ~/music
        library: ~/data/musiclibrary.db

        import:
            move: yes    # Move files to new location
            # copy: no   # Use files in place
            # write: no  # Don't modify tags

        plugins:
          - musicbrainz  # Example plugin for fetching metadata
          # - ... other plugins you want ...

    You can copy and paste this into your config file and modify it as needed.

.. admonition:: Ready for more?

    For a complete reference of all configuration options, see the
    :doc:`configuration reference </reference/config>`.

Importing Your Music
--------------------

Now you're ready to import your music into beets!

.. important::

    Importing can modify and move your music files. **Make sure you have a
    recent backup** before proceeding.

Choose Your Import Method
~~~~~~~~~~~~~~~~~~~~~~~~~

There are two good ways to bring your *existing* library into beets database.

.. tab-set::

    .. tab-item:: Autotag (Recommended)

        This method uses beets' autotagger to find canonical metadata for every album you import. It may take a while, especially for large libraries, and it's an interactive process. But it ensures all your songs' tags are exactly right from the get-go.

        .. code-block:: console

            beet import /a/chunk/of/my/library

        .. warning::

            The point about speed bears repeating: using the autotagger on a large library can take a
            very long time, and it's an interactive process. So set aside a good chunk of
            time if you're going to go that route.

            We also recommend importing smaller batches of music at a time (e.g., a few albums) to make the process more manageable. For more on the interactive tagging
            process, see :doc:`tagger`.


    .. tab-item:: Quick Import

        This method quickly brings all your files with all their current metadata into beets' database without any changes. It's really fast, but it doesn't clean up or correct any tags.

        To use this method, run:

        .. code-block:: console

            beet import -A /my/huge/mp3/library

        The ``-A`` flag skips autotagging and uses your files' current metadata.

.. admonition:: More Import Options

    The ``beet import`` command has many options to customize its behavior. For
    a full list, type ``beet help import`` or see the :ref:`import command
    reference <import-cmd>`.

Adding More Music Later
~~~~~~~~~~~~~~~~~~~~~~~

When you acquire new music, use the same ``beet import`` command to add it to
your library:

.. code-block:: console

    beet import ~/new_totally_not_ripped_album

This will apply the same autotagging process to your new additions. For
alternative import behaviors, consult the options mentioned above.

Seeing Your Music
-----------------

Once you've imported music into beets, you'll want to explore and query your
library. Beets provides several commands for searching, browsing, and getting
statistics about your collection.

Basic Searching
~~~~~~~~~~~~~~~

The ``beet list`` command (shortened to ``beet ls``) lets you search your music
library using :doc:`query string </reference/query>` similar to web searches:

.. code-block:: console

    $ beet ls the magnetic fields
    The Magnetic Fields - Distortion - Three-Way
    The Magnetic Fields - Dist
    The Magnetic Fields - Distortion - Old Fools

.. code-block:: console

    $ beet ls hissing gronlandic
    of Montreal - Hissing Fauna, Are You the Destroyer? - Gronlandic Edit

.. code-block:: console

    $ beet ls bird
    The Knife - The Knife - Bird
    The Mae Shi - Terrorbird - Revelation Six

By default, search terms match against :ref:`common attributes <keywordquery>`
of songs, and multiple terms are combined with AND logic (a track must match
*all* criteria).

Searching Specific Fields
~~~~~~~~~~~~~~~~~~~~~~~~~

To narrow a search term to a particular metadata field, prefix the term with the
field name followed by a colon. For example, ``album:bird`` searches for "bird"
only in the "album" field of your songs. For more details, see
:doc:`/reference/query/`.

.. code-block:: console

    $ beet ls album:bird
    The Mae Shi - Terrorbird - Revelation Six

This searches only the ``album`` field for the term ``bird``.

Searching for Albums
~~~~~~~~~~~~~~~~~~~~

The ``beet list`` command also has an ``-a`` option, which searches for albums
instead of songs:

.. code-block:: console

    $ beet ls -a forever
    Bon Iver - For Emma, Forever Ago
    Freezepop - Freezepop Forever

Custom Output Formatting
~~~~~~~~~~~~~~~~~~~~~~~~

There's also an ``-f`` option (for *format*) that lets you specify what gets
displayed in the results of a search:

.. code-block:: console

    $ beet ls -a forever -f "[$format] $album ($year) - $artist - $title"
    [MP3] For Emma, Forever Ago (2009) - Bon Iver - Flume
    [AAC] Freezepop Forever (2011) - Freezepop - Harebrained Scheme

In the format string, field references like ``$format``, ``$year``, ``$album``,
etc., are replaced with data from each result.

.. dropdown:: Available fields for formatting

    To see all available fields you can use in custom formats, run:

    .. code-block:: console

        beet fields

    This will display a comprehensive list of metadata fields available for your music.

Library Statistics
~~~~~~~~~~~~~~~~~~

Beets can also show you statistics about your music collection:

.. code-block:: console

    $ beet stats
    Tracks: 13019
    Total time: 4.9 weeks
    Total size: 71.1 GB
    Artists: 548
    Albums: 1094

.. admonition:: Ready for more advanced queries?

    The ``beet list`` command has many additional options for sorting, limiting
    results, and more complex queries. For a complete reference, run:

    .. code-block:: console

        beet help list

    Or see the :ref:`list command reference <list-cmd>`.

Keep Playing
------------

Congratulations! You've now mastered the basics of beets. But this is only the
beginning, beets has many more powerful features to explore.

Continue Your Learning Journey
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*I was there to push people beyond what's expected of them.*

.. grid:: 2
    :gutter: 3

    .. grid-item-card:: :octicon:`zap` Advanced Techniques
        :link: advanced
        :link-type: doc

        Explore sophisticated beets workflows including:

        - Advanced tagging strategies
        - Complex import scenarios
        - Custom metadata management
        - Workflow automation

    .. grid-item-card:: :octicon:`terminal` Command Reference
        :link: /reference/cli
        :link-type: doc

        Comprehensive guide to all beets commands:

        - Complete command syntax
        - All available options
        - Usage examples
        - **Important operations like deleting music**

    .. grid-item-card:: :octicon:`plug` Plugin Ecosystem
        :link: /plugins/index
        :link-type: doc

        Discover beets' true power through plugins:

        - Metadata fetching from multiple sources
        - Audio analysis and processing
        - Streaming service integration
        - Custom export formats

    .. grid-item-card:: :octicon:`question` Illustrated Walkthrough
        :link: https://beets.io/blog/walkthrough.html
        :link-type: url

        Visual, step-by-step guide covering:

        - Real-world import examples
        - Screenshots of interactive tagging
        - Common workflow patterns
        - Troubleshooting tips

.. admonition:: Need Help?

    Remember you can always use ``beet help`` to see all available commands, or
    ``beet help [command]`` for detailed help on specific commands.

Join the Community
~~~~~~~~~~~~~~~~~~

We'd love to hear about your experience with beets!

.. grid:: 2
    :gutter: 2

    .. grid-item-card:: :octicon:`comment-discussion` Discussion Board
        :link: https://github.com/beetbox/beets/discussions
        :link-type: url

        - Ask questions
        - Share tips and tricks
        - Discuss feature ideas
        - Get help from other users

    .. grid-item-card:: :octicon:`git-pull-request` Developer Resources
        :link: https://github.com/beetbox/beets
        :link-type: url

        - Contribute code
        - Report issues
        - Review pull requests
        - Join development discussions

.. admonition:: Found a Bug?

    If you encounter any issues, please report them on our `GitHub Issues page
    <https://github.com/beetbox/beets/issues>`_.
