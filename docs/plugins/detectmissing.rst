detectmissing plugin
====================

The ``detectmissing`` plugin lets you scan your library for missing files and
album art, and optionally delete them from your library database.

Installation
------------

To use ``detectmissing``, enable the plugin in your configuration (see
:ref:`using-plugins`); no additional configuration is necessary.

Usage
-----

Use ``beet detectmissing`` to scan your library for missing files and album art.
This does not modify your library.

::

    $ beet detectmissing
    /Users/example/Music/Music/Susumu Hirasawa/AURORA/cover.jpg
    /Users/example/Music/Music/Compilations/Enforcers_ The Beginning of the End/09 Distorted Tax.mp3
    /Users/example/Music/Music/Compilations/Distorted Reality (Future Drum & Bass)/03 The Killer.mp3
    /Users/example/Music/Music/Compilations/Distorted Reality (Future Drum & Bass)/07 The Killer (Radio Edit).mp3
    /Users/example/Music/Music/Compilations/Distorted Reality (Future Drum & Bass)/04 Toxic.mp3

``beet detectmissing --delete`` works the same way, but additionally deletes the
database entries from your library. Note that the files on disk are already
deleted, but if the files were contained in directories that are now empty,
those will be removed as well. The output format is the same as ``beet
detectmissing``:

::

    $ beet detectmissing --delete
    /Users/example/Music/Music/Susumu Hirasawa/AURORA/cover.jpg
    /Users/example/Music/Music/Compilations/Enforcers_ The Beginning of the End/09 Distorted Tax.mp3
