SubsonicUpdate Plugin
=====================

``subsonicupdate`` is a very simple plugin for beets that lets you automatically
update Subsonic_'s index whenever you change your beets library.

.. _subsonic: https://www.subsonic.org/pages/index.jsp

To use ``subsonicupdate`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then, you'll probably want to configure the specifics of
your Subsonic server. You can do that using a ``subsonic:`` section in your
``config.yaml``, which looks like this:

::

    subsonic:
        url: https://example.com:443/subsonic
        user: username
        pass: password
        auth: token

With that all in place, this plugin will send a REST API call to your Subsonic
server every time you change your beets library. Due to a current limitation of
the API, all libraries visible to that user will be scanned.

If the :doc:`/plugins/smartplaylist` is used, creating or changing any playlist
will trigger a Subsonic update as well.

You can also request the update manually, which is useful when the Subsonic
library lives on another machine and is not in sync with the beets library:

::

    beet subsonicupdate

This works regardless of the ``auto`` setting.

This plugin requires Subsonic with an active Premium license (or active trial)
or any other `Subsonic API compatible`_ server implementing the ``startScan``
endpoint.

.. _subsonic api compatible: https://www.subsonic.org/pages/api.jsp

Marking Favourites
------------------

The plugin also lets you mark beets query results as favourites (starred songs)
for the configured user, using the same ``subsonic:`` connection details:

.. code-block:: sh

    beet subsonic-set-favorite QUERY

This works with any `Subsonic API compatible`_ server implementing the
``search3``, ``getStarred2`` and ``star`` endpoints, such as Navidrome_. Tracks
that are already favourites are left alone, and only newly marked tracks are
counted in the summary. Without a query, the command asks for confirmation
before marking your whole library.

Subsonic servers use their own song IDs, which are different from beets item
IDs. The plugin first looks for a ``subsonic_id`` field on each selected item
and uses that value directly when present. You can populate this as a flexible
attribute and query it like any other field.

When ``subsonic_id`` is missing, the plugin searches the server using the item's
artist, album, and title. If that returns no usable match, the plugin tries
narrower artist/title, title-only and artist-only searches, followed by
accent-folded variants for metadata containing accents or characters such as
``Ø`` and ``Æ``. Missing or ambiguous matches are skipped to avoid favouriting
the wrong track. A unique match is stored in ``subsonic_id``, so later runs skip
the search for that item. If the server does not star a stored ID, for example
because the track was retagged and got a new ID, the plugin searches for it
again.

.. _navidrome: https://www.navidrome.org/

Configuration
-------------

The available options under the ``subsonic:`` section are:

- **url**: The Subsonic server resource. Default: ``http://localhost:4040``
- **user**: The Subsonic user. Default: ``admin``
- **pass**: The Subsonic user password. (This may either be a clear-text
  password or hex-encoded with the prefix ``enc:``.) Default: ``admin``
- **auth**: The authentication method. Possible choices are ``token`` or
  ``password``. ``token`` authentication is preferred to avoid sending cleartext
  password.
- **auto**: Whether to request an update automatically whenever the beets
  library or a smart playlist changes. Set to ``no`` to only update when you run
  ``beet subsonicupdate`` yourself. Default: ``yes``
