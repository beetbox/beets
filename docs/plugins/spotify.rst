Spotify Plugin
=====================

The ``spotify`` plugin generates Spotify playlists from tracks within the Beets library. Using the `Spotify Web API`_, any tracks that can be matched with a Spotify ID are returned, and the results can be either pasted in to a playlist, or opened directly in Spotify.

.. _Spotify Web API: https://developer.spotify.com/web-api/search-item/

Why Use This Plugin?
--------------------

* You're a Beets user and Spotify user already
* You have playlists or albums you'd like to make available in Spotify from Beets without having to search for each artist/album/track
* You want to check which tracks in your library are available on Spotify

Basic Usage
-----------
First, enable the plugin in your beets configuration::

    plugins: <other plugins> spotify

Then, you can search for tracks as usual with the ``spotify`` command::

    beet spotify <options if needed> <search args>


An example command, and it's output::

    beet spotify "In The Lonely Hour"

    Processing 14 tracks...

    http://open.spotify.com/track/19w0OHr8SiZzRhjpnjctJ4
    http://open.spotify.com/track/3PRLM4FzhplXfySa4B7bxS
    http://open.spotify.com/track/0ci6bxPw8muHTmSRs1MOjD
    http://open.spotify.com/track/7IHOIqZUUInxjVkko181PB
    http://open.spotify.com/track/0fySyVgczjbjbxMwNrdwkp
    http://open.spotify.com/track/1VbhR6D6zUoSTBzvnRonXO
    http://open.spotify.com/track/4TBFEe4n95WPxeUYt9jrMe
    http://open.spotify.com/track/2DnBQKrh8aodN4dBSdXAUh
    http://open.spotify.com/track/4DlYkz7xtje3iV2dDBu3OK
    http://open.spotify.com/track/7C6cA8girfd6ZvbkmZmx9V
    http://open.spotify.com/track/6uZ2x1Z6DSpOGAlVlvuhif
    http://open.spotify.com/track/3aoAkxvRjwhXDajp5aSZS6
    http://open.spotify.com/track/7cG68oOj0pZYoSVuP1Jzot
    http://open.spotify.com/track/4qPtIDBT2iVQv13tjpXMDt

Options for the command::

    Usage: beet spotify [options]

    Options:
      -h, --help            show this help message and exit
      -m MODE, --mode=MODE  "open" to open spotify with playlist, "list" to
                            print (default)
      -f, --show_failures   Print out list of any tracks that did not match a
                            Sptoify ID
      -v, --verbose         show extra output

Configuring
-----------

The default options should work as-is, but there are some options you can put in config.yaml:

* ``mode``: See the section below on modes
* ``region_filter``: Use the 2-character country abbreviation to limit results to that market
* ``show_failures``: Show the artist/album/track for each lookup that does not return a Spotify ID (and therefore cannot be added to a playlist)
* ``tiebreak``: How to choose the track if there is more than one identical result.  For example, there might be multiple releases of the same album.  Currently, this defaults to "popularity", "first" simply chooses the first in the list returned by Spotify.
* ``regex``: An array of regex transformations to perform on the track/album/artist fields before sending them to Spotify.  Can be useful for changing certain abbreviations, like ft. -> feat.  See the examples below.
* ``artist_field`` / ``album_field`` / ``track_field``: These allow the user to choose a different field to send to Spotify when looking up the track, album and artist.  Most users will not want to change this.

Example config.yaml
-------------------

Examples of the configuration options::

    spotify:
        mode: "open" # Default is list, shows the plugin output.  open attempts to open directly in Spotify (only tested on Mac)
        region_filter: "US" # Filters tracks by only that market (2-letter code)
        show_faiulres: on # Displays the tracks that did not match a Spotify ID
        tiebreak: "first" # Need to break ties when then are multiple tracks.  Default is popularity.
        artist_field: "albumartist" # Which beets field to use for the artist lookup
        album_field: "album" # Which beets field to use for the album lookup
        track_field: "title" # Which beets field to use for the track lookup
        regex: [
            {
                field: "albumartist", # Field in the item object to regex
                search: "Something", # String to look for
                replace: "Replaced" # Replacement value
            },
            {
                field: "title",
                search: "Something Else",
                replace: "AlsoReplaced"
            }
        ]

Spotify Plugin Modes
---------------------

* ``list``: The default mode for the spotify plugin is to print out the playlist as a list of links.  This list can then be pasted in to a new or existing spotify playlist.
* ``open``: This mode actually sends a link to your default webbrowser with instructions to open spotify with the playlist you created.  Until this has been tested on all platforms, it will remain optional.

