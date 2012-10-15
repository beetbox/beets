#Copyright (c) 2012, Fabrice Laporte
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
import subprocess
import os

from beets import ui
from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile, FileTypeError, UnreadableFileError
from beets.util import syspath

log = logging.getLogger('beets')

DEFAULT_REFERENCE_LOUDNESS = 89

class ReplayGainError(Exception):
    """Raised when an error occurs during mp3gain/aacgain execution.
    """

def call(args):
    """Execute the command indicated by `args` (an array of strings) and
    return the command's output. The stderr stream is ignored. If the command
    exits abnormally, a ReplayGainError is raised.
    """
    try:
        with open(os.devnull, 'w') as devnull:
            return subprocess.check_output(args, stderr=devnull)
    except subprocess.CalledProcessError as e:
        raise ReplayGainError(
            "{0} exited with status {1}".format(args[0], e.returncode)
        )

class ReplayGainPlugin(BeetsPlugin):
    """Provides ReplayGain analysis.
    """
    def __init__(self):
        self.register_listener('album_imported', self.album_imported)
        self.register_listener('item_imported', self.item_imported)

    def configure(self, config):
        self.overwrite = ui.config_val(config,'replaygain',
                                       'overwrite', False, bool)
        self.noclip = ui.config_val(config,'replaygain',
                                       'noclip', True, bool)
        self.apply_gain = ui.config_val(config,'replaygain',
                                       'apply_gain', False, bool)
        self.albumgain = ui.config_val(config,'replaygain',
                                       'albumgain', False, bool)
        target_level = float(ui.config_val(config,'replaygain',
                                    'targetlevel', DEFAULT_REFERENCE_LOUDNESS))
        self.gain_offset = int(target_level - DEFAULT_REFERENCE_LOUDNESS)

        self.command = ui.config_val(config,'replaygain','command', None)
        if self.command:
            # Explicit executable path.
            if not os.path.isfile(self.command):
                raise ui.UserError(
                    'replaygain command does not exist: {0}'.format(
                        self.command
                    )
                )
        else:
            # Check whether the program is in $PATH.
            for cmd in ('mp3gain', 'aacgain'):
                try:
                    call([cmd, '-v'])
                    self.command = cmd
                except OSError as exc:
                    pass
        if not self.command:
            raise ui.UserError(
                'no replaygain command found: install mp3gain or aacgain'
            )


    def album_imported(self, lib, album, config):
        try:
            media_files = \
                [MediaFile(syspath(item.path)) for item in album.items()]

            self.write_rgain(media_files,
                             self.compute_rgain(media_files),
                             True)

        except (FileTypeError, UnreadableFileError,
                TypeError, ValueError) as e:
            log.error("failed to calculate replaygain:  %s ", e)


    def item_imported(self, lib, item, config):
        try:
            mf = MediaFile(syspath(item.path))
            self.write_rgain([mf], self.compute_rgain([mf]))
        except (FileTypeError, UnreadableFileError,
            TypeError, ValueError) as e:
            log.error("failed to calculate replaygain:  %s ", e)
    

    def requires_gain(self, mf):
        '''Does the gain need to be computed?'''

        return self.overwrite or \
               (not mf.rg_track_gain or not mf.rg_track_peak) or \
               ((not mf.rg_album_gain or not mf.rg_album_peak) and \
                self.albumgain)


    def get_recommended_gains(self, media_paths):
        '''Returns recommended track and album gain values'''
        rgain_out = call([self.command, '-o', '-d', str(self.gain_offset)] +
                         media_paths)
        rgain_out = rgain_out.strip('\n').split('\n')
        keys = rgain_out[0].split('\t')[1:]
        tracks_mp3_gain = [dict(zip(keys, 
                                    [float(x) for x in l.split('\t')[1:]]))
                           for l in rgain_out[1:-1]]
        album_mp3_gain = int(rgain_out[-1].split('\t')[1]) 
        return [tracks_mp3_gain, album_mp3_gain]


    def parse_tool_output(self, text):
        """Given the tab-delimited output from an invocation of mp3gain
        or aacgain, parse the text and return a list of dictionaries
        containing information about each analyzed file.
        """
        out = []
        for line in text.split('\n'):
            parts = line.split('\t')
            if len(parts) != 6 or parts[0] == 'File':
                continue
            out.append({
                'file': parts[0],
                'mp3gain': int(parts[1]),
                'gain': float(parts[2]),
                'peak': float(parts[3]),
                'maxgain': int(parts[4]),
                'mingain': int(parts[5]),
            })
        return out
    

    def reduce_gain_for_noclip(self, track_gains, albumgain):
        '''Reduce albumgain value until no song is clipped.
        No command switch give you the max no-clip in album mode. 
        So we consider the recommended gain and decrease it until no song is
        clipped when applying the gain.
        Formula found at: 
        http://www.hydrogenaudio.org/forums/lofiversion/index.php/t10630.html
        '''

        if albumgain > 0:
            maxpcm = max([t['Max Amplitude'] for t in track_gains])
            while (maxpcm * (2**(albumgain/4.0)) > 32767):
                albumgain -= 1 
        return albumgain

    
    def compute_rgain(self, media_files):
        """Compute ReplayGain values and return a list of results
        dictionaries as given by `parse_tool_output`.
        """
        # Skip calculating gain only when *all* files don't need
        # recalculation. This way, if any file among an album's tracks
        # needs recalculation, we still get an accurate album gain
        # value.
        if all([not self.requires_gain(mf) for mf in media_files]):
            log.debug('replaygain: no gain to compute')
            return

        media_paths = [syspath(mf.path) for mf in media_files]

        if self.albumgain:
            track_gains, album_gain = self.get_recommended_gains(media_paths)
            if self.noclip:
                self.gain_offset = self.reduce_gain_for_noclip(track_gains, 
                                                               album_gain)

        # Construct shell command. The "-o" option makes the output
        # easily parseable (tab-delimited). "-s s" forces gain
        # recalculation even if tags are already present and disables
        # tag-writing; this turns the mp3gain/aacgain tool into a gain
        # calculator rather than a tag manipulator because we take care
        # of changing tags ourselves.
        cmd = [self.command, '-o', '-s', 's']
        if self.noclip:
            # Adjust to avoid clipping.
            cmd = cmd + ['-k'] 
        else:
            # Disable clipping warning. 
            cmd = cmd + ['-c']
        if self.apply_gain:
            # Lossless audio adjustment.
            cmd = cmd + ['-r'] 
        cmd = cmd + ['-d', str(self.gain_offset)]
        cmd = cmd + media_paths

        log.debug('replaygain: analyzing {0} files'.format(len(media_files)))
        output = call(cmd)
        log.debug('replaygain: analysis finished')
        return self.parse_tool_output(output)


    def write_rgain(self, media_files, rgain_infos, album=False): 
        """Write computed gain values for each media file.
        """
        if album:
            assert len(rgain_infos) == len(media_files) + 1
            album_info = rgain_infos[-1]

        for mf, info in zip(media_files, rgain_infos):
            try:
                mf.rg_track_gain = info['gain']
                mf.rg_track_peak = info['peak']

                if album:
                    mf.rg_album_gain = album_info['gain']
                    mf.rg_album_peak = album_info['peak']

                log.debug('replaygain: writing track gain {0}, peak {1}; '
                          'album gain {2}, peak {3}'.format(
                    mf.rg_track_gain, mf.rg_track_peak,
                    mf.rg_album_gain, mf.rg_album_peak
                ))
                mf.save()

            except UnreadableFileError:
                log.error("replaygain: write failed for %s" % (mf.title))
