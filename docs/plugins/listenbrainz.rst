.. _listenbrainz:

ListenBrainz Plugin
===================

The ListenBrainz plugin for beets allows you to interact with the ListenBrainz
service.

Installation
------------

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

Other ``musicbrainz`` options may be set to modify the connection to MusicBrainz
(see :ref:`musicbrainz-shared-options`).

Usage
-----

Once the plugin is enabled, you can import the listening history using the
``lbimport`` command in beets.

.. _config.yaml: ../reference/config.rst

.. _here: https://listenbrainz.readthedocs.io/en/latest/users/api/index.html#get-the-user-token
