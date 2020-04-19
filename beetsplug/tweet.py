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

"""Tweet the Album, Artist and Coverart of an album in the library."""
from beets.plugins import BeetsPlugin
from beets import ui

# from beets.util.functemplate import template
from twitter import OAuth, Twitter
import os


class BeetTweet(BeetsPlugin):
    """A Plugin to post info from the library to a Twitter account"""

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
        self.t = Twitter(auth=self.auth)
        self.t_upload = Twitter(domain="upload.twitter.com", auth=self.auth)

    def commands(self):
        cmd = ui.Subcommand(
            "tweet", help=u"Tweet the artist, album and coverart from the library."
        )
        # ToDo implement custom template on commandline
        # cmd.parser.add_option(
        #     u'-t', u'--template', dest='template',
        #     # action='store_true', default=False,
        #     help=u'define custom template for tweet'
        # )

        # ToDo implement pretend on commandline
        cmd.parser.add_option(
            u"-p",
            u"--pretend",
            dest="pretend",
            action="store_true",
            default=False,
            help=u"pretend to tweet",
        )

        def func(lib, opts, args):
            self.tweet(lib, lib.albums(ui.decargs(args)), opts.pretend)

        cmd.func = func
        return [cmd]

    def _upload_album_art(self, album, pretend):
        if album.artpath:
            self._log.info(u"Uploading album art for {0}", album)
            if not pretend:
                with open(album.artpath, "rb") as imgfile:
                    imgdata = imgfile.read()
                img = self.t_upload.media.upload(media=imgdata)
                # ToDo check uploaded correctly
                return img["media_id_string"]
            else:
                return None
        else:
            message = ui.colorize("text_error", u"No art found")
            self._log.info(u"{0} for {1}", message, album)
            return None

    def _send_tweet(self, album, pretend):
        """Command to construct and send a tweet for a single album."""
        status = album.evaluate_template(self.config["template"].get(), True)
        img_id = self._upload_album_art(album, pretend)

        self._log.info(u"Tweeting: {0}", status)
        if not pretend:
            self.t.statuses.update(status=status, media_ids=img_id)

    def tweet(self, lib, albums, pretend):
        """Tweet information about the specified album."""
        for album in albums:
            self._send_tweet(album, pretend)

        return
