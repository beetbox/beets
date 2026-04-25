.. _listenbrainz:

ListenBrainz Plugin
===================

The ListenBrainz plugin for beets allows you to interact with the ListenBrainz
service.

Configuration
-------------

To enable the ListenBrainz plugin, add the following to your beets configuration
file (config.yaml_):

.. code-block:: yaml

    plugins:
        - listenbrainz

You can then configure the plugin by providing your Listenbrainz token (see
intructions here_) and username:

::

    listenbrainz:
        token: TOKEN
        username: LISTENBRAINZ_USERNAME

Usage
-----

Once the plugin is enabled, you can import the listening history using the
``lbimport`` command in beets.

Matched tracks are populated with the ``listenbrainz_play_count`` field, which
you can use in queries and templates. For example:

::

    $ beet ls -f '$title: $listenbrainz_play_count' listenbrainz_play_count:1..

This field is separate from ``lastfm_play_count`` used by :doc:`lastimport` and
``play_count`` used by :doc:`mpdstats`, so importing play counts from one plugin
does not overwrite the others.

.. _config.yaml: ../reference/config.rst

.. _here: https://listenbrainz.readthedocs.io/en/latest/users/api/index.html#get-the-user-token
