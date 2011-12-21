#Copyright (c) 2011, Peter Brunner (Lugoues)
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import logging

from rgain import rgcalc

from beets import ui
from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile, FileTypeError, UnreadableFileError
from beets.util import syspath

log = logging.getLogger('beets')

DEFAULT_REFERENCE_LOUDNESS = 89


class ReplayGainPlugin(BeetsPlugin):
    '''Provides replay gain analysis for the Beets Music Manager'''

    ref_level = DEFAULT_REFERENCE_LOUDNESS
    overwrite = False

    def __init__(self):
        self.register_listener('album_imported', self.album_imported)
        self.register_listener('item_imported', self.item_imported)

    def configure(self, config):
        self.overwrite = ui.config_val(config,
                                       'replaygain',
                                       'overwrite',
                                       False)

    def album_imported(self, lib, album, config):
        self.write_album = True

        log.debug("Calculating ReplayGain for %s - %s" % \
            (album.albumartist, album.album))

        try:
            media_files = \
                [MediaFile(syspath(item.path)) for item in album.items()]
            media_files = [mf for mf in media_files if self.requires_gain(mf)]

            #calculate gain.
            #Return value - track_data: array dictionary indexed by filename
            track_data, album_data = rgcalc.calculate(
                [syspath(mf.path) for mf in media_files],
                True,
                self.ref_level)

            for mf in media_files:
                self.write_gain(mf, track_data, album_data)

        except (FileTypeError, UnreadableFileError, TypeError, ValueError), e:
            log.error("failed to calculate replaygain:  %s ", e)

    def item_imported(self, lib, item, config):
        try:
            self.write_album = False

            mf = MediaFile(syspath(item.path))

            if self.requires_gain(mf):
                track_data, album_data = rgcalc.calculate([syspath(mf.path)],
                                                          True,
                                                          self.ref_level)
                self.write_gain(mf, track_data, None)
        except (FileTypeError, UnreadableFileError, TypeError, ValueError), e:
            log.error("failed to calculate replaygain:  %s ", e)

    def write_gain(self, mf, track_data, album_data):
        try:
            mf.rg_track_gain = track_data[syspath(mf.path)].gain
            mf.rg_track_peak = track_data[syspath(mf.path)].peak

            if self.write_album and album_data:
                mf.rg_album_gain = album_data.gain
                mf.rg_album_peak = album_data.peak

                log.debug('Tagging ReplayGain for: %s - %s \n'
                         '\tTrack Gain = %f\n'
                         '\tTrack Peak = %f\n'
                         '\tAlbum Gain = %f\n'
                         '\tAlbum Peak = %f' % \
                         (mf.artist,
                          mf.title,
                          mf.rg_track_gain,
                          mf.rg_track_peak,
                          mf.rg_album_gain,
                          mf.rg_album_peak))
            else:
                log.debug('Tagging ReplayGain for: %s - %s \n'
                         '\tTrack Gain = %f\n'
                         '\tTrack Peak = %f\n' % \
                         (mf.artist,
                         mf.title,
                         mf.rg_track_gain,
                         mf.rg_track_peak))

            mf.save()
        except (FileTypeError, UnreadableFileError, TypeError, ValueError), e:
            log.error("failed to write replaygain: %s" % (mf.title))

    def requires_gain(self, mf):
        return self.overwrite or \
               (not mf.rg_track_gain or not mf.rg_track_peak) or \
               ((not mf.rg_album_gain or not mf.rg_album_peak) and \
                self.write_album)
