Play Plugin
============

The ``play`` plugin allows you to pass the results of a query to a music player in the form of a m3u playlist.

To use the plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, add an ``play:`` section to your configuration
file::

    play:
        # Command(optional) override the system default for m3u files.
        # You can define a command to be executed by the shell which the m3u path will be appended to.
        command: command: /Applications/VLC.app/Contents/MacOS/VLC
        # Debug(optional) displays output from player for aiding in setting up command correctly.
        debug: True

How it works
============
The plugin works by turning your query results into a temporary m3u file. Then the command you have configured it executed by the shell and the playlist is passed as the last parameter.
