Echonest Plugin
===========================

Acoustic fingerprinting is a technique for identifying songs from the
way they "sound" rather from their existing metadata. That means that
beets' autotagger can theoretically use fingerprinting to tag files
that don't have any ID3 information at all (or have completely
incorrect data). This plugin uses an open-source fingerprinting
technology called `echoprint <http://echoprint.me/>`_ (or
alternatively the closed-source `ENMFP
<http://blog.echonest.com/post/545323349/the-echo-nest-musical-fingerprint-enmfp>`_ and its associated
Web service, called Echonest `song/identify
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

To get fingerprinting working, you'll need to install three things:
the `echoprint <http://github.com/echonest/echoprint-codegen>`_ or
`ENMFP <http://static.echonest.com/ENMFP_codegen.zip>`_ 
codegen command-line tools, and the `pyechonest <http://github.com/echonest/pyechonest>`_ 
Python library.

First, you will need to install ``echoprint`` or ``ENMFP``, as a
command-line tool (``echoprint-codegen`` or ``codegen.OS-ARCH``).
Dynamic libraries can also be built for both, but currently the
``Echonest`` plugin requires the command-line tools. 

The ``ENMFP`` codegen binary distribution has executables for all
major OSs and architectures. The ``echoprint`` codegen must be built
from source, and requires the `Boost <http://www.boost.org/>`_ libraries.

Then, install pyechonest itself. You can do this using `pip <http://pip.openplans.org/>`_,
like so::

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

Finally, if the ``echoprint`` or ``ENMFP`` binary is not in your path,
you'll need to add an additional key called ``codegen`` under the
``echonest`` section like so::

    echonest:
        apikey: YOURKEY
        codegen: PATH/TO/YOUR/CODEGEN/BINARY

With that, beets will use fingerprinting the next time you run ``beet
import``.

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

Since most of these fields represent real numbers between 0 and 1, the
plugin also adds a new type of query for searching for ranges. You can
query inequalities using the range operator ``...`` like so::

    beet ls danceability:0.25...0.75
    beet ls liveness:...0.1
    beet ls speechiness:0.9...

The above will return all tracks will danceability values in the range
[0.25, 0.75], liveness values less than 0.1, or speechiness values
greater than 0.9.
