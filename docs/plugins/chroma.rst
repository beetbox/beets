Chromaprint/Acoustid Plugin
===========================

Acoustic fingerprinting is a technique for identifying songs from the way they
"sound" rather from their existing metadata. That means that beets' autotagger
can theoretically use fingerprinting to tag files that don't have any ID3
information at all (or have completely incorrect data).  This plugin uses an
open-source fingerprinting technology called `Chromaprint`_ and its associated
Web service, called `Acoustid`_.

.. _Chromaprint: http://acoustid.org/chromaprint
.. _acoustid: http://acoustid.org/

Turning on fingerprinting can increase the accuracy of the
autotagger---especially on files with very poor metadata---but it comes at a
cost. First, it can be trickier to set up than beets itself (you need to set up
the native fingerprinting library, whereas all of the beets core is written in
pure Python).  Also, fingerprinting takes significantly more CPU and memory than
ordinary tagging---which means that imports will go substantially slower.

If you're willing to pay the performance cost for fingerprinting, read on!

Installing Dependencies
-----------------------

To get fingerprinting working, you'll need to install three things: the
`Chromaprint`_ library or command-line tool, an audio decoder, and the
`pyacoustid`_ Python library (version 0.6 or later).

First, you will need to install `Chromaprint`_, either as a dynamic library or
in the form of a command-line tool (``fpcalc``). The Chromaprint site has links
to packages for major Linux distributions. On Mac OS X and Windows, download the
appropriate binary package and place the ``fpcalc`` (or ``fpcalc.exe``) on your
shell search path (e.g., in ``/usr/local/bin`` on Mac OS X or ``C:\\Program
Files`` on Windows).

Next, you will need a mechanism for decoding audio files supported by the
`audioread`_ library. Mac OS X has a number of decoders already built into Core
Audio; on Linux, you can install `GStreamer for Python`_, `FFmpeg`_, or `MAD`_
and `pymad`_. (Let me know if you have a good source for installing a decoder on
Windows.) How you install these will depend on your distribution. For example:

.. _audioread: https://github.com/sampsyo/audioread
.. _pyacoustid: http://github.com/sampsyo/pyacoustid
.. _GStreamer for Python:
    http://gstreamer.freedesktop.org/modules/gst-python.html
.. _FFmpeg: http://ffmpeg.org/
.. _MAD: http://spacepants.org/src/pymad/
.. _pymad: http://www.underbit.com/products/mad/
.. _Core Audio: http://developer.apple.com/technologies/mac/audio-and-video.html

* On Ubuntu, run ``apt-get install python-gst0.10-dev``.

* On Arch Linux, you want ``pacman -S gstreamer0.10-python``. 

To decode audio formats (MP3, FLAC, etc.) with GStreamer, you'll need the
standard set of Gstreamer plugins. For example, on Ubuntu, install the packages
``gstreamer0.10-plugins-good``, ``gstreamer0.10-plugins-bad``, and
``gstreamer0.10-plugins-ugly``.

Then, install pyacoustid itself. You can do this using `pip`_, like so::

    $ pip install pyacoustid

.. _pip: http://pip.openplans.org/

Using
-----

Once you have all the dependencies sorted out, you can enable fingerprinting by
editing your :doc:`/reference/config`. Put ``chroma`` on your ``plugins:``
line. Your config file should contain something like this::

    [beets]
    plugins: chroma

With that, beets will use fingerprinting the next time you run ``beet import``.


.. _submitfp:

Submitting Fingerprints
'''''''''''''''''''''''

You can help expand the `Acoustid`_ database by submitting fingerprints for the
music in your collection. To do this, first `get an API key`_ from the Acoustid
service. Just use an OpenID or MusicBrainz account to log in and you'll get a
short token string. Then, add the key to your :doc:`/reference/config` as the
value ``apikey`` in a section called ``acoustid`` like so::

    [acoustid]
    apikey=AbCd1234

Then, run ``beet submit``. (You can also provide a query to submit a subset of
your library.) The command will use stored fingerprints if they're available;
otherwise it will fingerprint each file before submitting it.

.. _get an API key: http://acoustid.org/api-key
