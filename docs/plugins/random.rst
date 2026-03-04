Random Plugin
=============

The ``random`` plugin provides a command that randomly selects tracks or albums
from your library. This can be helpful if you need some help deciding what to
listen to.

First, enable the plugin named ``random`` (see :ref:`using-plugins`). You'll
then be able to use the ``beet random`` command:

.. code-block:: shell

    beet random
    >> Aesop Rock - None Shall Pass - The Harbor Is Yours

Usage
-----

The basic command selects and displays a single random track. Several options
allow you to customize the selection:

.. code-block:: shell

    Usage: beet random [options]

    Options:
      -h, --help            show this help message and exit
      -n NUMBER, --number=NUMBER
                            number of objects to choose
      -e, --equal-chance    each field has the same chance
      -t TIME, --time=TIME  total length in minutes of objects to choose
      --field=FIELD         field to use for equal chance sampling (default:
                            albumartist)
      -a, --album           match albums instead of tracks
      -p PATH, --path=PATH  print paths for matched items or albums
      -f FORMAT, --format=FORMAT
                            print with custom format

Detailed Options
----------------

``-n, --number=NUMBER``
    Select multiple items at once. The default is 1.

``-e, --equal-chance``
    Give each distinct value of a field an equal chance of being selected. This
    prevents artists with many albums/tracks from dominating the selection.

    **Implementation note:** When this option is used, the plugin:

    1. Groups items by the specified field
    2. Shuffles items within each group
    3. Randomly selects groups, then items from those groups
    4. Continues until all groups are exhausted

    Items without the specified field (``--field``) value are excluded from the
    selection.

``--field=FIELD``
    Specify which field to use for equal chance sampling. Default is
    ``albumartist``.

``-t, --time=TIME``
    Select items whose total duration (in minutes) is approximately equal to
    TIME. The plugin will continue adding items until the total exceeds the
    requested time.

``-a, --album``
    Operate on albums instead of tracks.

``-p, --path``
    Output filesystem paths instead of formatted metadata.

``-f, --format=FORMAT``
    Use a custom format string for output. See :doc:`/reference/query` for
    format syntax.

Examples
--------

Select multiple items:

.. code-block:: shell

    # Select 5 random tracks
    beet random -n 5

    # Select 3 random albums
    beet random -a -n 3

Control selection fairness:

.. code-block:: shell

    # Ensure equal chance per artist (default field: albumartist)
    beet random -e

    # Ensure equal chance per genre
    beet random -e --field genre

Select by total playtime:

.. code-block:: shell

    # Select tracks totaling 60 minutes (1 hour)
    beet random -t 60

    # Select albums totaling 120 minutes (2 hours)
    beet random -a -t 120

Custom output formats:

.. code-block:: shell

    # Print only artist and title
    beet random -f '$artist - $title'

    # Print file paths
    beet random -p

    # Print album paths
    beet random -a -p
