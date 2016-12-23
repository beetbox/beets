"""Calculate acoustic information and submit to AcousticBrainz.
"""

from __future__ import division, absolute_import, print_function

import hashlib
import json
import os
import subprocess
import tempfile

import distutils
import requests

from beets import plugins
from beets import util
from beets import ui


class ABSubmitError(Exception):
    """Base exception for all excpetions this plugin can raise."""


class FatalABSubmitError(ABSubmitError):
    """Raised if the plugin is not able to start."""


class AnalysisABSubmitError(ABSubmitError):
    """Raised if analysis of file fails."""


class SubmitABSubmitError(ABSubmitError):
    """Raised if submitting data fails."""


def call(args):
    """Execute the command and return its output.

    Raise a AnalysisABSubmitError on failure.
    """
    try:
        return util.command_output(args)
    except subprocess.CalledProcessError as e:
        raise AnalysisABSubmitError(
            u"{0} exited with status {1}".format(args[0], e.returncode)
        )


class AcousticBrainzSubmitPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(AcousticBrainzSubmitPlugin, self).__init__()

        self.config.add({'extractor': u''})

        self.extractor = self.config['extractor'].as_str()
        if self.extractor:
            self.extractor = util.normpath(self.extractor)
            # Expicit path to extractor
            if not os.path.isfile(self.extractor):
                raise FatalABSubmitError(
                    u'extractor command does not exist: {0}'.
                    format(self.extractor)
                )
        else:
            # Implicit path to extractor, search for it in path
            # TODO how to check for on Windows?
            self.extractor = 'streaming_extractor_music'
            try:
                call([self.extractor])
            except OSError:
                raise FatalABSubmitError(
                    u'no extractor command found: install "{0}"'.
                    format(self.extractor)
                )
            except AnalysisABSubmitError:
                # Extractor found, will exit with an error if not called with
                # the correct amount of arguments.
                pass
            # Get the executable needed to calculate the sha1 hash.
            self.extractor = distutils.spawn.find_executable(self.extractor)

        # Calculate extractor hash.
        self.extractor_sha = hashlib.sha1()
        with open(self.extractor, 'rb') as extractor:
            self.extractor_sha.update(extractor.read())
        self.extractor_sha = self.extractor_sha.hexdigest()

    supported_formats = {'mp3', 'ogg', 'oga', 'flac', 'mp4', 'm4a', 'm4r',
                         'm4b', 'm4p', 'aac', 'wma', 'asf', 'mpc', 'wv',
                         'spx', 'tta', '3g2', 'aif', 'aiff', 'ape'}

    base_url = 'https://acousticbrainz.org/api/v1/{mbid}/low-level'

    def commands(self):
        cmd = ui.Subcommand(
            'absubmit',
            help=u'calculate and submit AcousticBrainz analysis'
        )
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        # Get items from arguments
        items = lib.items(ui.decargs(args))
        # Get no_submit option.
        # TODO get a should submit option from the command line.
        for item in items:
            analysis = self._get_analysis(item)
            if analysis:
                self._submit_data(item, analysis)

    def _get_analysis(self, item):
        mbid = item['mb_trackid']
        # If file has no mbid skip it.
        if not mbid:
            self._log.info('Not analysing {}, missing '
                           'musicbrainz track id.', item)
            return None
        # If file format is not supported skip it.
        if item['format'].lower() not in self.supported_formats:
            self._log.info('Not analysing {}, file not in '
                           'supported format.', item)
            return None

        # Temporary file to save extractor output to.
        tmp_file, filename = tempfile.mkstemp(suffix='.json')
        try:
            # Close the file, so the extractor can overwrite it.
            call([self.extractor, util.syspath(item.path), filename])
            with open(filename) as tmp_file:
                analysis = json.loads(tmp_file.read())
            # Add the hash to the output.
            analysis['metadata']['version']['essentia_build_sha'] = \
                self.extractor_sha
            return analysis
        finally:
            try:
                os.remove(filename)
            except OSError as e:
                # errno 2 means file does not exist, just ignore this error.
                if e.errno != 2:
                    raise

    def _submit_data(self, item, data):
        mbid = item['mb_trackid']
        headers = {'Content-Type': 'application/json'}
        response = requests.post(self.base_url.format(mbid=mbid),
                                 json=data, headers=headers)
        # Test that request was successful and raise an error on failure.
        if response.status_code != 200:
            try:
                message = response.json()['message']
            except Exception as e:
                message = 'unable to get error message: {}'.format(e)
            raise ABSubmitError(
                'Failed to submit analysis: {message})'.
                format(status_code=response.status_code, message=message)
            )
        self._log.debug('Successfully submitted AcousticBrainz analysis '
                        'for {}.', item)
