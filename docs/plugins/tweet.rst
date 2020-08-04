Tweet Plugin
===================

The ``tweet`` plugin allows you to tweet the results of a beets album query to a connected twitter account.


Installation
-------------

The plugin requires `twitter`_. You can install it using ``pip``::

    pip install twitter

Then, enable the ``tweet`` plugin in your configuration (see :ref:`using-plugins`), and configure authorisation (detailed below).


Configuration
-------------

As a bare minimum, this plugin requires configuration for `OAuth authorisation`_ to access your Twitter account::

    tweet:
          api_key: YOUR_TWITTER_API_KEY
          api_secret_key: YOUR_TWITTER_API_SECRET_KEY
          access_token: YOUR_TWITTER_ACCESS_TOKEN
          access_token_secret: YOUR_TWITTER_ACCESS_TOKEN_SECRET

Additionally, you can configure the plugin's behaviour:

- **template**: The template used for each tweet, accepting any of the
  beets library identifiers. Default: ``"$albumartist - $album ($year)"``.
- **upload_album_art**: Whether the album art of the query should be
  uploaded to Twitter and attached to the tweet. Default: ``yes``.
- **cautious**: Ask for confirmation before tweeting. Default: ``yes``.

Usage
-------------

To tweet information about an album use::
  
  $ beet tweet [query]

For example::

  $ beet tweet yves tumor
  tweet: About to Tweet: Yves Tumor - Safe in the Hands of Love (2018)
  tweet: Does this look correct?
  [Y]es, No? y

If multiple albums match your query, they will be displayed in turn,
with a confirmation if the ``cautious`` flag is set (as default).

.. _twitter: https://pypi.org/project/twitter/
.. _OAuth authorisation: https://developer.twitter.com/en/docs/basics/authentication/oauth-2-0/bearer-tokens
