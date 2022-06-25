Spotify Plugin
==============

The ``spotify`` plugin generates `Spotify`_ playlists from tracks in your
library with the ``beet spotify`` command using the `Spotify Search API`_.

Also, the plugin can use the Spotify `Album`_ and `Track`_ APIs to provide
metadata matches for the importer.

.. _Spotify: https://www.spotify.com/
.. _Spotify Search API: https://developer.spotify.com/documentation/web-api/reference/#/operations/search
.. _Album: https://developer.spotify.com/documentation/web-api/reference/#/operations/get-an-album
.. _Track: https://developer.spotify.com/documentation/web-api/reference/#/operations/get-track

Why Use This Plugin?
--------------------

* You're a Beets user and Spotify user already.
* You have playlists or albums you'd like to make available in Spotify from Beets without having to search for each artist/album/track.
* You want to check which tracks in your library are available on Spotify.
* You want to autotag music with metadata from the Spotify API.
* You want to obtain track popularity and audio features (e.g., danceability)

Basic Usage
-----------
First, enable the ``spotify`` plugin (see :ref:`using-plugins`).
Then, use the ``spotify`` command with a beets query::

    beet spotify [OPTIONS...] QUERY

Here's an example::

    $ beet spotify "In The Lonely Hour"
    Processing 14 tracks...
    https://open.spotify.com/track/19w0OHr8SiZzRhjpnjctJ4
    https://open.spotify.com/track/3PRLM4FzhplXfySa4B7bxS
    [...]

Command-line options include:

* ``-m MODE`` or ``--mode=MODE`` where ``MODE`` is either "list" or "open"
  controls whether to print out the playlist (for copying and pasting) or
  open it in the Spotify app. (See below.)
* ``--show-failures`` or ``-f``: List the tracks that did not match a Spotify
  ID.

You can enter the URL for an album or song on Spotify at the ``enter Id``
prompt during import::

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://open.spotify.com/album/2rFYTHFBLQN3AYlrymBPPA

Configuration
-------------

This plugin can be configured like other metadata source plugins as described in :ref:`metadata-source-plugin-configuration`. In addition, the following
configuration options are provided.

The default options should work as-is, but there are some options you can put
in config.yaml under the ``spotify:`` section:

- **mode**: One of the following:

   - ``list``: Print out the playlist as a list of links. This list can then
     be pasted in to a new or existing Spotify playlist.
   - ``open``: This mode actually sends a link to your default browser with
     instructions to open Spotify with the playlist you created.  Until this
     has been tested on all platforms, it will remain optional.

  Default: ``list``.
- **region_filter**: A two-character country abbreviation, to limit results
  to that market.
  Default: None.
- **show_failures**: List each lookup that does not return a Spotify ID (and
  therefore cannot be added to a playlist).
  Default: ``no``.
- **tiebreak**: How to choose the track if there is more than one identical
  result. For example, there might be multiple releases of the same album.
  The options are ``popularity`` and ``first`` (to just choose the first match
  returned).
  Default: ``popularity``.
- **regex**: An array of regex transformations to perform on the
  track/album/artist fields before sending them to Spotify.  Can be useful for
  changing certain abbreviations, like ft. -> feat.  See the examples below.
  Default: None.

Here's an example::

    spotify:
        source_weight: 0.7
        mode: open
        region_filter: US
        show_failures: on
        tiebreak: first

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

Obtaining Track Popularity and Audio Features from Spotify
----------------------------------------------------------

Spotify provides information on track `popularity`_ and audio `features`_ that
can be used for music discovery.

.. _popularity: https://developer.spotify.com/documentation/web-api/reference/#/operations/get-track

.. _features: https://developer.spotify.com/documentation/web-api/reference/#/operations/get-audio-features

The ``spotify`` plugin provides an additional command ``spotifysync`` to obtain
these track attributes from Spotify:

* ``beet spotifysync [-f]``: obtain popularity and audio features information
  for every track in the library. By default, ``spotifysync`` will skip tracks
  that already have this information populated. Using the ``-f`` or ``-force``
  option will download the data even for tracks that already have it. Please
  note that ``spotifysync`` works on tracks that have the Spotify track
  identifiers. So run ``spotifysync`` only after importing your music, during
  which Spotify identifiers will be added for tracks where Spotify is chosen as
  the tag source.

  In addition to ``popularity``, the command currently sets these audio features
  for all tracks with a Spotify track ID:

  * ``acousticness``
  * ``danceability``
  * ``energy``
  * ``instrumentalness``
  * ``key``
  * ``liveness``
  * ``loudness``
  * ``mode``
  * ``speechiness``
  * ``tempo``
  * ``time_signature``
  * ``valence``
