Spotify Plugin
==============

The ``spotify`` plugin generates `Spotify`_ playlists from tracks in your library. Using the `Spotify Web API`_, any tracks that can be matched with a Spotify ID are returned, and the results can be either pasted in to a playlist or opened directly in the Spotify app.

.. _Spotify: https://www.spotify.com/
.. _Spotify Web API: https://developer.spotify.com/web-api/search-item/

Why Use This Plugin?
--------------------

* You're a Beets user and Spotify user already.
* You have playlists or albums you'd like to make available in Spotify from Beets without having to search for each artist/album/track.
* You want to check which tracks in your library are available on Spotify.

Basic Usage
-----------

First, enable the plugin (see :ref:`using-plugins`). Then, use the ``spotify``
command with a beets query::

    beet spotify [OPTIONS...] QUERY

Here's an example::

    $ beet spotify "In The Lonely Hour"
    Processing 14 tracks...
    http://open.spotify.com/track/19w0OHr8SiZzRhjpnjctJ4
    http://open.spotify.com/track/3PRLM4FzhplXfySa4B7bxS
    [...]

Command-line options include:

* ``-m MODE`` or ``--mode=MODE`` where ``MODE`` is either "list" or "open"
  controls whether to print out the playlist (for copying and pasting) or
  open it in the Spotify app. (See below.)
* ``--show-failures`` or ``-f``: List the tracks that did not match a Spotify
  ID.

Configuring
-----------

The default options should work as-is, but there are some options you can put in config.yaml:

* ``mode``: See the section below on modes.
* ``region_filter``: Use the 2-character country abbreviation to limit results
  to that market.
* ``show_failures``: Show the artist/album/track for each lookup that does not
  return a Spotify ID (and therefore cannot be added to a playlist).
* ``tiebreak``: How to choose the track if there is more than one identical
  result.  For example, there might be multiple releases of the same album.
  Currently, this defaults to "popularity", "first" simply chooses the first
  in the list returned by Spotify.
* ``regex``: An array of regex transformations to perform on the
  track/album/artist fields before sending them to Spotify.  Can be useful for
  changing certain abbreviations, like ft. -> feat.  See the examples below.
* ``artist_field`` / ``album_field`` / ``track_field``: These allow the user
  to choose a different field to send to Spotify when looking up the track,
  album and artist.  Most users will not want to change this.

Example Configuration
---------------------

::

    spotify:
        # Default is list, shows the plugin output. Open attempts to open
        # directly in Spotify (only tested on Mac).
        mode: "open"

        # Filter tracks by only that market (2-letter code)
        region_filter: "US"

        # Display the tracks that did not match a Spotify ID.
        show_faiulres: on

        # Need to break ties when then are multiple tracks.  Default is
        popularity.
        tiebreak: "first"

        # Which beets fields to use for lookups.
        artist_field: "albumartist"
        album_field: "album"
        track_field: "title"

        regex: [
            {
                field: "albumartist", # Field in the item object to regex.
                search: "Something", # String to look for.
                replace: "Replaced" # Replacement value.
            },
            {
                field: "title",
                search: "Something Else",
                replace: "AlsoReplaced"
            }
        ]

Spotify Plugin Modes
---------------------

* ``list``: The default mode is to print out the playlist as a list of links.
  This list can then be pasted in to a new or existing Spotify playlist.
* ``open``: This mode actually sends a link to your default browser with
  instructions to open Spotify with the playlist you created.  Until this has
  been tested on all platforms, it will remain optional.

