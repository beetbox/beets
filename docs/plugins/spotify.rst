Spotify Plugin
==============

The ``spotify`` plugin generates `Spotify`_ playlists from tracks in your
library with the ``beet spotify`` command. Using the `Spotify Search API`_,
any tracks that can be matched with a Spotify ID are returned, and the
results can be either pasted in to a playlist or opened directly in the
Spotify app.

Spotify URLs and IDs may also be provided in the ``Enter release ID:`` prompt
during ``beet import`` to autotag music with data from the Spotify
`Album`_ and `Track`_ APIs.

.. _Spotify: https://www.spotify.com/
.. _Spotify Search API: https://developer.spotify.com/documentation/web-api/reference/search/search/
.. _Album: https://developer.spotify.com/documentation/web-api/reference/albums/get-album/
.. _Track: https://developer.spotify.com/documentation/web-api/reference/tracks/get-track/

Why Use This Plugin?
--------------------

* You're a Beets user and Spotify user already.
* You have playlists or albums you'd like to make available in Spotify from Beets without having to search for each artist/album/track.
* You want to check which tracks in your library are available on Spotify.
* You want to autotag music with Spotify metadata

Basic Usage
-----------

First, register a `Spotify application`_ to use with beets and add your Client ID
and Client Secret to your :doc:`configuration file </reference/config>` under a
``spotify`` section::

    spotify:
        client_id: N3dliiOOTBEEFqCH5NDDUmF5Eo8bl7AN
        client_secret: 6DRS7k66h4643yQEbepPxOuxeVW0yZpk

.. _Spotify application: https://developer.spotify.com/documentation/general/guides/app-settings/

Then, enable the ``spotify`` plugin (see :ref:`using-plugins`) and use the ``spotify``
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

A Spotify ID or URL may also be provided to the ``Enter release ID``
prompt during import::

    Enter search, enter Id, aBort, eDit, edit Candidates, plaY? i
    Enter release ID: https://open.spotify.com/album/2rFYTHFBLQN3AYlrymBPPA
    Tagging:
        Bear Hands - Blue Lips / Ignoring the Truth / Back Seat Driver (Spirit Guide) / 2AM
    URL:
        https://open.spotify.com/album/2rFYTHFBLQN3AYlrymBPPA
    (Similarity: 88.2%) (source, tracks) (Spotify, 2019, Spensive Sounds)
     * Blue Lips (feat. Ursula Rose)   -> Blue Lips (feat. Ursula Rose) (source)
     * Ignoring the Truth              -> Ignoring the Truth (source)
     * Back Seat Driver (Spirit Guide) -> Back Seat Driver (Spirit Guide) (source)
     * 2AM                             -> 2AM (source)
    [A]pply, More candidates, Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort, eDit, edit Candidates, plaY?


Configuration
-------------

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
- **tokenfile**: Filename of the JSON file stored in the beets configuration
  directory to use for caching the OAuth access token.
  access token.
  Default: ``spotify_token.json``.
- **source_weight**: Penalty applied to Spotify matches during import. Set to
  0.0 to disable.
  Default: ``0.5``.

.. _beets configuration directory: https://beets.readthedocs.io/en/stable/reference/config.html#default-location

Here's an example::

    spotify:
        client_id: N3dliiOOTBEEFqCH5NDDUmF5Eo8bl7AN
        client_secret: 6DRS7k66h4643yQEbepPxOuxeVW0yZpk
        source_weight: 0.7
        tokenfile: my_spotify_token.json
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

