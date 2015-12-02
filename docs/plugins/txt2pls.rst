txt2pls plugins
===============

The ``txt2pls`` takes a textfile with a list of albums - artists(albums or songs)
and searches your collection for them and saves a  playlist from them.
(think end of year lists ..)

Installation
============

To use it, enable the ``txt2pls`` plugin in your configuration
(see :ref:`using-plugins`).
Then configure your plugin like the following example::

    txt2pls:
        relative_to: ~/Music
        playlist_dir: ~/.mpd/playlists


- **relative_to**: Generate paths in the playlist files relative to a base
  directory. If you intend to use this plugin to generate playlists for MPD,
  point this to your MPD music directory.
  Default: Use absolute paths.
- **playlist_dir**: If set, placed to store your playlists.
  Default:``.``
- **use_folders**: Enable this option to store paths to folders.
  Default: ``no``.

Usage
=====

``beet txt2pls \path\to\list.txt``

where the list.txt is of the following structure:

- **first line**: contains the title of the playlist
- **second line**: expresses the format of the rest of the list. ex:

    - **x. album:  - albumartist: (x)** =>ex: 2. White - The Beatles (1967)
    - **albumartist: -- album: [x]**    =>ex:    The Beatles -- white [1967]
    - **artist: ; title:** =>ex: John Lennon ; imagine

        - where ``x.`` represents the linenumbering if the list has it.
        - ``[x]`` or ``(x)`` is anything in between brackets at the end of the line.
        - ``artist:``,``albumartist:``,``title:``,``album:`` ... obvious
- **all the other lines**: follow the format from the second line

If no playlist_dir in config, playlist will get saved in dir of ``.``
You will get a notice if your ``list.txt`` is not welformed.And remember: playlists
don't always use the names as you. 
