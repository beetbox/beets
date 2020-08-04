# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2020, David Swarbrick
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tweet the Album, Artist and Coverart of an album in the library.

Relies on:
twitter : https://pypi.org/project/twitter/
fetchart : [Beets Plugin] for the .artpath field

Configuration:
    tweet:
            # Login details for your Twitter account
            api_key: YOUR_TWITTER_API_KEY
            api_secret_key: YOUR_TWITTER_API_SECRET_KEY
            access_token: YOUR_TWITTER_ACCESS_TOKEN
            access_token_secret: YOUR_TWITTER_ACCESS_TOKEN_SECRET

            # Default behaviours

            # The template for each tweet
            template: $albumartist - $album ($year)

            # Whether to upload album art
            upload_album_art: True

            # Ask for confirmation before tweeting?
            cautious: True

"""
from __future__ import division, absolute_import, print_function
from beets.plugins import BeetsPlugin
from beets import ui
from beets.util.artresizer import ArtResizer
from twitter import OAuth, Twitter
import os


class BeetTweet(BeetsPlugin):
    """A Plugin to post info from the library to a Twitter account."""

    def __init__(self):
        super(BeetTweet, self).__init__()
        # Set all API keys to redacted
        self.config["api_key"].redact = True
        self.config["api_secret_key"].redact = True
        self.config["access_token"].redact = True
        self.config["access_token_secret"].redact = True
        # OAuth object for authentication when posting to twitter
        self.auth = OAuth(
            self.config["access_token"].get(),
            self.config["access_token_secret"].get(),
            self.config["api_key"].get(),
            self.config["api_secret_key"].get(),
        )
        # Template for tweets using beets names (if unspecified in config file)
        self.config.add({"template": "$albumartist - $album ($year)"})
        self.config.add({"upload_album_art": True})
        self.config.add({"cautious": True})
        self.t = Twitter(auth=self.auth)
        self.t_upload = Twitter(domain="upload.twitter.com", auth=self.auth)

    def commands(self):
        cmd = ui.Subcommand(
            "tweet",
            help=u"Tweet the artist, album and coverart from the library.",
        )

        def func(lib, opts, args):
            self.tweet(lib, lib.albums(ui.decargs(args)))

        cmd.func = func
        return [cmd]

    def _get_album_art_data(self, album):
        """Upload album art to Twitter if available, resizing if needed."""
        if album.artpath:
            self._log.debug(u"Getting album art for {0}", album)
            imgdata = None
            if os.stat(album.artpath).st_size > 5e6:
                self._log.debug(
                    u"Album Art too large for upload (5MB) - Resizing"
                )
                orig_dim = ArtResizer.shared.get_size(album.artpath)
                art_path = ArtResizer.shared.resize(
                    orig_dim[0], album.artpath, max_filesize=5e6
                )
            else:
                art_path = album.artpath

            with open(art_path, "rb") as imgfile:
                imgdata = imgfile.read()

            return imgdata

        else:
            self._log.info(u"Album Art Not Found")
            return None

    def _twitter_upload(self, filled_template, imagedata=None):
        """Upload album art (if given) and final tweet to Twitter."""
        if imagedata:
            img_id = self.t_upload.media.upload(media=imagedata)[
                "media_id_string"
            ]
            self.t.statuses.update(status=filled_template, media_ids=img_id)
        else:
            self.t.statuses.update(status=filled_template)

    def _send_tweet(self, album):
        """Command to construct and send a tweet for a single album."""
        status = album.evaluate_template(self.config["template"].get(), False)
        imagedata = None
        if self.config["upload_album_art"].get():
            imagedata = self._get_album_art_data(album)
            if not imagedata:
                self._log.info(u"Error with Album Art Upload")
                return

        self._log.info(u"About to Tweet: {0}", status)
        # If "cautious" flag set in config, ask before tweeting
        if self.config["cautious"].get():
            self._log.info(u"Does this look correct?")
            sel = ui.input_options((u"yes", u"no"))
            if sel == u"y":
                self._twitter_upload(status, imagedata)
                return
            else:
                return
        else:
            self._twitter_upload(status, imagedata)
            return

    def tweet(self, lib, albums):
        """Tweet information about the specified album."""
        for album in albums:
            self._send_tweet(album)

        return
