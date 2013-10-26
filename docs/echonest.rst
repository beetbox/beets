Echonest Plugin
===========================

Acoustic fingerprinting is a technique for identifying songs from the
way they "sound" rather from their existing metadata. That means that
beets' autotagger can theoretically use fingerprinting to tag files
that don't have any ID3 information at all (or have completely
incorrect data). This plugin uses a fingerprinting technology called
`ENMFP <http://blog.echonest.com/post/545323349/the-echo-nest-musical-fingerprint-enmfp>`_
and its associated Web service, called Echonest `song/identify
<http://developer.echonest.com/docs/v4/song.html#identify>`_.

Turning on fingerprinting can increase the accuracy of the
autotagger---especially on files with very poor metadata---but it
comes at a cost. First, it can be trickier to set up than beets itself
(you need to set up the native fingerprinting library, whereas all of
the beets core is written in pure Python). Also, fingerprinting takes
significantly more CPU and memory than ordinary tagging---which means
that imports will go substantially slower.

If you're willing to pay the performance cost for fingerprinting, read
on!

Installing Dependencies
-----------------------

To get fingerprinting working, you'll need to install two things:
the `ENMFP <http://static.echonest.com/ENMFP_codegen.zip>`_ codegen
command-line tool, and the `pyechonest
<http://github.com/echonest/pyechonest>`_ Python library.

First, you will need to install ``ENMFP``, as a command-line tool.
The ``ENMFP`` codegen binary distribution has executables for all
major OSs and architectures.

Then, install pyechonest itself. You can do this using `pip
<http://pip.openplans.org/>`_, like so::

    $ pip install pyechonest

Configuring
-----------

Once you have all the dependencies sorted out, you can enable
fingerprinting by editing your :doc:`configuration file
</reference/config>`. Put ``echonest`` on your ``plugins:`` line.
You'll also need an `API key from Echonest <http://developer.echonest.com/account/register>`_.
Then, add the key to your ``config.yaml`` as the value ``apikey`` in a
section called ``echonest`` like so::

    echonest:
        apikey: YOURKEY

If the ``ENMFP`` binary is not in your path, you'll need to add an
additional key called ``codegen`` under the ``echonest`` section like
so::

    echonest:
        apikey: YOURKEY
        codegen: PATH/TO/YOUR/CODEGEN/BINARY

With that, beets will use fingerprinting the next time you run ``beet
import``.

If you'd prefer not to run the Echonest plugin importer automatically
when importing, you can shut it off::

    echonest:
        apikey: YOURKEY
        codegen: PATH/TO/YOUR/CODEGEN/BINARY
	auto: no

Using
'''''

The Echonest plugin will automatically fetch and store in the database
(but *not* in the audio file itself) the following audio descriptors:

- danceability
- duration
- energy
- key
- liveness
- loudness
- mode
- speechiness
- tempo
- time_signature


Since most of these fields represent real numbers between 0 and 1, you
will also be able to query inequalities using the range operator
``..``, once it supports doing so in flexattrs, like so::

    beet ls danceability:0.25...0.75
    beet ls liveness:...0.1
    beet ls speechiness:0.9...

The above would return all tracks will danceability values in the
range [0.25, 0.75], liveness values less than 0.1, or speechiness
values greater than 0.9. For now, you can sort of get around this
limitation by using regexp queries::

    beet ls energy::0\.[89]


Additionally, the plugin adds a new command, named ``fingerprint``,
which is analogous to the same command provided by ``chroma``.

TODO
''''
Provide a command for performing tagging outside of an import stage.
