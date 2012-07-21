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
import tempfile
import os
import errno

from beets import ui
from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile, FileTypeError, UnreadableFileError
from beets.util import syspath

log = logging.getLogger('beets')

DEFAULT_REFERENCE_LOUDNESS = 89

class RgainError(Exception):
    """Base for exceptions in this module."""

class RgainNoBackendError(RgainError):
    """The audio rgain could not be computed because neither mp3gain
     nor aacgain command-line tool is installed.
    """

class ReplayGainPlugin(BeetsPlugin):
    '''Provides replay gain analysis for the Beets Music Manager'''

    ref_level = DEFAULT_REFERENCE_LOUDNESS

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
        self.gain_offset = int(target_level-DEFAULT_REFERENCE_LOUDNESS)
        self.command = ui.config_val(config,'replaygain','command', None)
        if not os.path.isfile(self.command):
            raise ui.UserError('no valid rgain command filepath given')
        if not self.command:
            for cmd in ['mp3gain','aacgain']:
                proc = subprocess.Popen([cmd,'-v'])
                retcode = proc.poll()
                if not retcode:
                    self.command = cmd
        if not self.command:
            raise ui.UserError('no valid rgain command found')


    def album_imported(self, lib, album, config):
        try:
            media_files = \
                [MediaFile(syspath(item.path)) for item in album.items()]

            self.write_rgain(media_files, self.compute_rgain(media_files))

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

        proc = subprocess.Popen([self.command,'-o','-d',str(self.gain_offset)] +
                                media_paths,
                                stdout=subprocess.PIPE)
        retcode = proc.poll()
        if retcode:
            raise RgainError("%s exited with status %i" %
                                          (self.command,retcode))  
        rgain_out, _ = proc.communicate()
        rgain_out = rgain_out.strip('\n').split('\n')
        keys = rgain_out[0].split('\t')[1:]
        tracks_mp3_gain = [dict(zip(keys, 
                                    [float(x) for x in l.split('\t')[1:]]))
                           for l in rgain_out[1:-1]]
        album_mp3_gain = int(rgain_out[-1].split('\t')[1]) 
        return [tracks_mp3_gain, album_mp3_gain]


    def extract_rgain_infos(self, text):
        '''Extract rgain infos stats from text'''

        return [l.split('\t') for l in text.split('\n') if l.count('\t')>1][1:]
    

    def reduce_gain_for_noclip(self, track_gains, albumgain):
        '''Reduce albumgain value until no song is clipped.
        No command switch give you the max no-clip in album mode. 
        So we consider the recommended gain and decrease it until no song is
        clipped when applying the gain.
        Formula used has been found at: 
        http://www.hydrogenaudio.org/forums//lofiversion/index.php/t10630.html
        '''

        if albumgain > 0:
            for (i,mf) in enumerate(track_gains):
                maxpcm = track_gains[i]['Max Amplitude']
                while (maxpcm * (2**(albumgain/4.0)) > 32767):
                    clipped = 1
                    albumgain -= 1 
        return albumgain

    
    def compute_rgain(self, media_files):
        '''Compute replaygain taking options into account. 
        Returns filtered command stdout'''

        cmd_args = []
        media_files = [mf for mf in media_files if self.requires_gain(mf)]
        if not media_files:
            print 'No gain to compute'
            return

        media_paths = [syspath(mf.path) for mf in media_files]

        if self.albumgain:
            track_gains, album_gain = self.get_recommended_gains(media_paths)
            if self.noclip:
                self.gain_offset = self.reduce_gain_for_noclip(track_gains, 
                                                               album_gain)

        cmd = [self.command, '-o']
        if self.noclip:
            cmd = cmd + ['-k'] 
        if self.apply_gain:
            cmd = cmd + ['-r'] 
        cmd = cmd + ['-d', str(self.gain_offset)]
        cmd = cmd + media_paths
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            raise RgainError("%s exited with status %i" % (cmd, e.returncode))
      
        cmd = [self.command, '-s','c','-o'] + media_paths
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        if proc.poll():
            raise RgainError("%s exited with status %i" % (cmd, retcode))

        tmp = proc.communicate()[0]
        return self.extract_rgain_infos(tmp)


    def write_rgain(self, media_files, rgain_infos): 
        '''Write computed gain infos for each media file'''
        
        for (i,mf) in enumerate(media_files):
 
            try:
                mf.rg_track_gain = float(rgain_infos[i][2])
                mf.rg_track_peak = float(rgain_infos[i][4])

                print('Tagging ReplayGain for: %s - %s' % (mf.artist, 
                                                           mf.title))
                print('\tTrack gain = %f\n' % mf.rg_track_gain)
                print('\tTrack peak = %f\n' % mf.rg_track_peak)

                mf.save()
            except (FileTypeError, UnreadableFileError, TypeError, ValueError):
                log.error("failed to write replaygain: %s" % (mf.title))

