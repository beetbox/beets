LastID Plugin
=============

Acoustic fingerprinting is a technique for identifying songs from the way they
"sound" rather from their existing metadata. That means that beets' autotagger
can theoretically use fingerprinting to tag files that don't have any ID3
information at all (or have completely incorrect data). The MusicBrainz project
currently uses a fingerprinting technology called PUIDs, but beets uses a
different fingerprinting algorithm provided by `Last.fm`_.

.. _Last.fm: http://last.fm/

Turning on fingerprinting can increase the accuracy of the
autotagger---especially on files with very poor metadata---but it comes at a
cost. First, it can be trickier to set up than beets itself (you need to compile
the fingerprinting code, whereas all of the beets core is written in Python).
Also, fingerprinting takes significantly more CPU and memory than ordinary
tagging---which means that imports will go substantially slower.

If you're willing to pay the performance cost for fingerprinting, read on!

Installing Dependencies
-----------------------

To use lastid, you'll need to install the `pylastfp`_ fingerprinting library,
which has a few dependencies: `fftw`_, `libsamplerate`_, and `Gstreamer for
Python`_.  How you install these will depend on your operating system. Here's a
few examples:

.. _pylastfp: http://github.com/sampsyo/pylastfp
.. _fftw: http://www.fftw.org/
.. _libsamplerate: http://www.mega-nerd.com/SRC/
.. _Gstreamer for Python:
    http://gstreamer.freedesktop.org/modules/gst-python.html

* On Ubuntu, just run ``apt-get install libfftw3-dev libsamplerate0-dev
  python-gst0.10-dev``.

* On Arch Linux, you want
  ``pacman -S fftw libsamplerate gstreamer0.10-python``. 

Let me know if you have a good source for installing the packages on Windows.

To decode audio formats (MP3, FLAC, etc.), you'll need the standard set of
Gstreamer plugins. For example, on Ubuntu, install the packages
``gstreamer0.10-plugins-good``, ``gstreamer0.10-plugins-bad``, and
``gstreamer0.10-plugins-ugly``.

Then, install pylastfp itself. You can do this using `pip`_, like so::

    $ pip install pylastfp

.. _pip: http://pip.openplans.org/

Using
-----

Once you have all the dependencies sorted out, you can enable fingerprinting by
editing your :doc:`/reference/config`. Put ``lastid`` on your ``plugins:``
line. Your config file should contain something like this::

    [beets]
    plugins: lastid

With that, beets will use fingerprinting the next time you run ``beet import``.
