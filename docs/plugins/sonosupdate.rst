SonosUpdate Plugin
==================

The ``sonosupdate`` plugin lets you automatically update `Sonos`_'s music
library whenever you change your beets library.

To use ``sonosupdate`` plugin, enable it in your configuration
(see :ref:`using-plugins`).

To use the ``sonosupdate`` plugin you need to install the `soco`_ library with::

    pip install soco

With that all in place, you'll see beets send the "update" command to your Sonos
controller every time you change your beets library.

.. _Sonos: https://sonos.com/
.. _soco: http://python-soco.com
