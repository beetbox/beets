Echo Nest Plugin
================

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

Finally, enable the ``echonest`` plugin in your configuration (see
:ref:`using-plugins`).

.. _pip: http://pip.openplans.org/
.. _FFmpeg: http://ffmpeg.org


Configuration
-------------

To configure the plugin, make an ``echonest:`` section in your configuration
file. The available options are:

- **apikey**: A custom EchoNest API key. You can `apply for your own`_ for
  free from the EchoNest.
  Default: beets' own Echo Nest API key.
- **auto**: Enable automatic metadata fetching during import.
  Default: ``yes``.
- **upload**: Send files to the Echo Nest server if they can not be identified
  by other means.
  Default: ``yes``.
- **convert**: Because the Echo Nest server only supports a limited range of
  file formats, the plugin automatically converts unsupported files to ``ogg``.
  Default: ``yes``.
- **truncate**: Automatically truncate large files to their first 5 minutes
  before uploading them to The Echo Nest server (as files with sizes greater
  than 50MB are rejected).
  Default: ``yes``.

.. _apply for your own: http://developer.echonest.com/account/register


Running Manually
----------------

In addition to running automatically on import, the plugin can also be run
manually from the command line. Use the command ``beet echonest [QUERY]`` to
fetch acoustic attributes for albums matching a certain query.
