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
from beets.util import syspath

log = logging.getLogger('beets')

DEFAULT_REFERENCE_LOUDNESS = 89

class ReplayGainError(Exception):
    """Raised when an error occurs during mp3gain/aacgain execution.
    """

def call(args):
    """Execute the command indicated by `args` (a list of strings) and
    return the command's output. The stderr stream is ignored. If the
    command exits abnormally, a ReplayGainError is raised.
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
                except OSError:
                    pass
        if not self.command:
            raise ui.UserError(
                'no replaygain command found: install mp3gain or aacgain'
            )


    def album_imported(self, lib, album, config):
        items = list(album.items())
        self.store_gain(items,
                        self.compute_rgain(items, True),
                        True)


    def item_imported(self, lib, item, config):
        self.store_gain([item], self.compute_rgain([item]))
    

    def requires_gain(self, item, album=False):
        """Does the gain need to be computed?"""
        return self.overwrite or \
               (not item.rg_track_gain or not item.rg_track_peak) or \
               ((not item.rg_album_gain or not item.rg_album_peak) and \
                album)


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
    

    def reduce_gain_for_noclip(self, track_peaks, album_gain):
        '''Reduce album gain value until no song is clipped.
        No command switch give you the max no-clip in album mode. 
        So we consider the recommended gain and decrease it until no song is
        clipped when applying the gain.
        Formula found at: 
        http://www.hydrogenaudio.org/forums/lofiversion/index.php/t10630.html
        '''
        if album_gain > 0:
            maxpcm = max(track_peaks)
            while (maxpcm * (2 ** (album_gain / 4.0)) > 32767):
                album_gain -= 1 
        return album_gain

    
    def compute_rgain(self, items, album=False):
        """Compute ReplayGain values and return a list of results
        dictionaries as given by `parse_tool_output`.
        """
        # Skip calculating gain only when *all* files don't need
        # recalculation. This way, if any file among an album's tracks
        # needs recalculation, we still get an accurate album gain
        # value.
        if all([not self.requires_gain(i, album) for i in items]):
            log.debug('replaygain: no gain to compute')
            return

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
        cmd = cmd + [syspath(i.path) for i in items]

        log.debug('replaygain: analyzing {0} files'.format(len(items)))
        output = call(cmd)
        log.debug('replaygain: analysis finished')
        results = self.parse_tool_output(output)

        # Adjust for noclip mode.
        if album and self.noclip:
            album_gain = results[-1]['gain']
            track_peaks = [r['peak'] for r in results[:-1]]
            album_gain = self.reduce_gain_for_noclip(track_peaks, album_gain)
            results[-1]['gain'] = album_gain

        return results


    def store_gain(self, items, rgain_infos, album=False): 
        """Write computed gain values for each media file.
        """
        if album:
            assert len(rgain_infos) == len(items) + 1
            album_info = rgain_infos[-1]

        for item, info in zip(items, rgain_infos):
            item.rg_track_gain = info['gain']
            item.rg_track_peak = info['peak']

            if album:
                item.rg_album_gain = album_info['gain']
                item.rg_album_peak = album_info['peak']

            log.debug('replaygain: applying track gain {0}, peak {1}; '
                        'album gain {2}, peak {3}'.format(
                item.rg_track_gain, item.rg_track_peak,
                item.rg_album_gain, item.rg_album_peak
            ))
