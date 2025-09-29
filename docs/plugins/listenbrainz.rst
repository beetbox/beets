.. _listenbrainz:

ListenBrainz Plugin
===================

The ListenBrainz plugin for beets allows you to interact with the ListenBrainz
service.

Installation
------------

To use the ``listenbrainz`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``listenbrainz`` extra

.. code-block:: bash

    pip install "beets[listenbrainz]"

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

.. _config.yaml: ../reference/config.rst

.. _here: https://listenbrainz.readthedocs.io/en/latest/users/api/index.html#get-the-user-token
