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

"""
Tweet the Album, Artist and Coverart of an album in the library.

Relies on:
twitter : https://pypi.org/project/twitter/
fetchart : [Beets Plugin] for the .artpath field, if album art upload is desired (default=True).
"""
from beets.plugins import BeetsPlugin
from beets import ui
from beets.util.artresizer import ArtResizer
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
        self.config.add({"upload_album_art": True})
        self.t = Twitter(auth=self.auth)
        self.t_upload = Twitter(domain="upload.twitter.com", auth=self.auth)

    def commands(self):
        cmd = ui.Subcommand(
            "tweet", help=u"Tweet the artist, album and coverart from the library."
        )

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

    def _album_art_resizer(self, album, quality=70, attempts=3):
        """
        Resize album art to be below 5MB for upload to Twitter.
        Ideally would use ImageMagick option of jpeg:extent=5MB,
        however to preserve compatibility with PIL, ArtResizer is used.
        We attempt 75% resolution, jpeg quality = 70%, up to 3 times.
        """
        imgdata = None
        orig_dim = ArtResizer.shared.get_size(album.artpath)
        dim_0 = orig_dim[0]
        for i in range(attempts):

            dim_0 = round(dim_0 * 0.75)
            smaller_path = ArtResizer.shared.resize(
                dim_0, album.artpath, quality=quality
            )
            smaller_size = os.stat(smaller_path).st_size
            self._log.debug(
                u"Resize attempt {0}, Output Size: {1}MB ",
                i,
                round(smaller_size / 1e6, 2),
            )
            if smaller_size < 5e6:
                with open(smaller_path, "rb") as imgfile:
                    imgdata = imgfile.read()
                return imgdata
        if smaller_size > 5e6:
            self._log.info(u"Failed to resize Album Art after {0} attempts.", attempts)
            return None
        return imgdata

    def _upload_album_art(self, album, pretend):
        """Upload album art to Twitter if available, resizing to be below 5MB limit"""
        if album.artpath:
            self._log.info(u"Uploading album art for {0}", album)
            imgdata = None
            if os.stat(album.artpath).st_size > 5e6:
                self._log.info(u"Album Art too large for upload (5MB) - Resizing")
                if not pretend:
                    imgdata = self._album_art_resizer(album)
            elif not pretend:
                with open(album.artpath, "rb") as imgfile:
                    imgdata = imgfile.read()

            if imgdata:
                img = self.t_upload.media.upload(media=imgdata)
                # ToDo check uploaded correctly
                return img["media_id_string"]
            else:
                return None

        else:
            self._log.info(u"Album Art Not Found")
            return None

    def _send_tweet(self, album, pretend):
        """Command to construct and send a tweet for a single album."""
        status = album.evaluate_template(self.config["template"].get(), True)
        if self.config["upload_album_art"].get():
            # Try to upload album art:
            img_id = self._upload_album_art(album, pretend)

            if img_id and not pretend:
                self._log.info(u"Tweeting: {0}", status)
                self.t.statuses.update(status=status, media_ids=img_id)
            elif not img_id and not pretend:
                self._log.info(u"Error with Album Art Upload")
            elif pretend:
                # Pretend case will produce a failed img_id, thus cannot check for errors
                self._log.info(
                    u"Tweeting: {0} [If no errors in album art upload] ", status
                )

        elif not pretend:
            # Real case but with no album art
            self._log.info(u"Tweeting: {0}", status)
            self.t.statuses.update(status=status)
        else:
            # Pretend case
            self._log.info(u"Tweeting: {0}", status)

    def tweet(self, lib, albums, pretend):
        """Tweet information about the specified album."""
        if pretend:
            self._log.info(u"Pretend Mode - no requests made to Twitter")
        for album in albums:
            self._send_tweet(album, pretend)

        return
