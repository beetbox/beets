.. _listenbrainz:

ListenBrainz Plugin
===================

The ListenBrainz plugin for beets allows you to interact with the ListenBrainz service.

Installation
------------

To enable the ListenBrainz plugin, add the following to your beets configuration file (`config.yaml`):

.. code-block:: yaml

   plugins:
       - listenbrainz

You can then configure the plugin by providing your Listenbrainz token (see intructions `here`_`)and username::

    listenbrainz:
        token: TOKEN
        username: LISTENBRAINZ_USERNAME


Usage
-----

Once the plugin is enabled, you can import the listening history using the `lbimport` command in beets.


.. _here: https://listenbrainz.readthedocs.io/en/latest/users/api/index.html#get-the-user-token