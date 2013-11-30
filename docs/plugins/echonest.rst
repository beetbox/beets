Echonest Plugin
===============

The ``echonest`` plugin fetches `acoustic attributes`_ from `the Echo Nest`_.
It automatically fills in the following attributes:

- danceability
- energy
- liveness
- loudness
- speechiness
- bpm

All attributes except ``bpm`` are stored in flexible attributes (i.e., not
in files' metadata).
See the Echo Nest's page on `acoustic attributes`_ for a detailed description.
(Their name for ``bpm`` is ``tempo``.)

.. _the Echo Nest: http://the.echonest.com/
.. _acoustic attributes: http://developer.echonest.com/acoustic-attributes.html


Installing Dependencies
-----------------------

This plugin requires the pyechonest library in order to talk to the Echo Nest
API.  At least version 8.0.1 is required.

There are packages for most major linux distributions, you can download the
library from the Echo Nest, or you can install the library from `pip`_,
like so::

    $ pip install pyechonest

To transcode music for server-side analysis (optional, of course), install
the `ffmpeg`_ command-line tool.

To get fingerprinting working, you'll need to install the command-line
codegen tool for `ENMFP`_ or `Echoprint`_, the two fingerprinting
algorithms supported by the Echo Nest. Please note that fingerprinting is not
required if ``upload`` and ``convert`` is enabled, which is the default (but
it can be faster than uploading).

.. _pip: http://pip.openplans.org/
.. _FFmpeg: http://ffmpeg.org
.. _ENMFP: http://static.echonest.com/ENMFP_codegen.zip
.. _Echoprint: http://echoprint.me


Configuring
-----------

Beets includes its own Echo Nest API key, but you can `apply for your own`_ for
free from the Echo Nest.  To specify your own API key, add the key to your
:doc:`configuration file </reference/config>` as the value for ``apikey`` under
the key ``echonest_tempo`` like so::

    echonest:
        apikey: YOUR_API_KEY

In addition, the ``auto`` config option lets you disable automatic metadata
fetching during import. To do so, add this to your ``config.yaml``::

    echonest:
        auto: no

The ``echonest`` plugin tries to upload files to the Echo Nest server if it
can not be identified by other means.  If you don't want that, disable the
``upload`` config option like so::

    echonest:
        upload: no

The Echo Nest server only supports a limited range of file formats.  The
``plugin`` automatically converts unsupported files to ``ogg``.  If you don't
want that, disable the ``convert`` config option like so::

    echonest:
        convert: no

To enable fingerprinting, you'll need to tell the plugin where to find the
Echoprint or ENMFP codegen binary. Use the ``codegen`` key under the
``echonest`` section like so::

    echonest:
        codegen: /usr/bin/echoprint-codegen

.. _apply for your own: http://developer.echonest.com/account/register