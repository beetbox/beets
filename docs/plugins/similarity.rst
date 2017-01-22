Similarity Plugin
=====================

The ``similarity`` plugin get similiarity information from last.fm 
and stores this relation as json-file for further processing.

Enable the ``similarity`` plugin in your configuration 
(see :ref:`using-plugins`) and run it by typing::

    $ beet similarity [-f] [-d DEPTH] [-j FILE] [QUERY]

By default, the command will look for similarity information provided
by last.fm when the artist is not processed before and stored in the 
JSON file ``-f`` or ``--force`` switch makes it re-download
data even when it already exists. If you specify a query, only 
matching artists will be processed, the ``-d`` or ``--depth`` marks 
the depth of resulting graph.

For all artists with a MusicBrainz artist ID, the plugin queries 
10 similar artists from last.fm. Depending on the ``-d`` or ``--depth`` 
argument it checks the similar artists for thier similar artists if
the artists is available in the beets library.

Without an option, the similarity-plugin checks every artists which 
is available in the beets library for 10 similar artists.


Configuration
-------------

To configure the plugin, make a ``similarity:`` section in your
configuration file. There is some options:

- **force**: Queries similarity data even for artists that already
processed before.
  Default: ``no``.

- **json**: Filename for json File which stores the relations between 
artists. Location is the default config-dir.

- **depth**: Depth of similarity graph which will be processed. If 
set to ``0`` it goes down until every owned artist is checked 
against similar artist and no more owned artist is found.
  Default: ``0``.
