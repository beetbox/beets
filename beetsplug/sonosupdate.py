# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2018, Tobias Sauerwein.
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

"""Updates a Sonos library whenever the beets library is changed.
This is based on the Kodi Update plugin.
"""
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
import soco


class SonosUpdate(BeetsPlugin):
    def __init__(self):
        super(SonosUpdate, self).__init__()
        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update"""
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        """When the client exists try to send refresh request to a Sonos
        controler.
        """
        self._log.info(u'Requesting a Sonos library update...')

        device = soco.discovery.any_soco()

        if device:
            device.music_library.start_library_update()
        else:
            self._log.warning(u'Could not find a Sonos device.')
            return

        self._log.info(u'Sonos update triggered')
