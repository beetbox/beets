# -*- coding: utf-8 -*-
# Copyright 2016 Bruno Cauet
# Split an album-file in tracks thanks a cue file

from __future__ import division, absolute_import, print_function

import subprocess
from os import path
from glob import glob

from beets.util import command_output, displayable_path
from beets.plugins import BeetsPlugin
from beets.autotag import TrackInfo


class CuePlugin(BeetsPlugin):
    def __init__(self):
        super(CuePlugin, self).__init__()
        # this does not seem supported by shnsplit
        self.config.add({
            'keep_before': .1,
            'keep_after': .9,
        })

        # self.register_listener('import_task_start', self.look_for_cues)

    def candidates(self, items, artist, album, va_likely):
        import pdb
        pdb.set_trace()

    def item_candidates(self, item, artist, album):
        dir = path.dirname(item.path)
        cues = glob.glob(path.join(dir, "*.cue"))
        if not cues:
            return
        if len(cues) > 1:
            self._log.info(u"Found multiple cue files doing nothing: {0}",
                           list(map(displayable_path, cues)))

        cue_file = cues[0]
        self._log.info("Found {} for {}", displayable_path(cue_file), item)

        try:
            # careful: will ask for input in case of conflicts
            command_output(['shnsplit', '-f', cue_file, item.path])
        except (subprocess.CalledProcessError, OSError):
            self._log.exception(u'shnsplit execution failed')
            return

        tracks = glob(path.join(dir, "*.wav"))
        self._log.info("Generated {0} tracks", len(tracks))
        for t in tracks:
            title = "dunno lol"
            track_id = "wtf"
            index = int(path.basename(t)[len("split-track"):-len(".wav")])
            yield TrackInfo(title, track_id, index=index, artist=artist)
        # generate TrackInfo instances
