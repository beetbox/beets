# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte, Yevgeny Bezman, and Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

import subprocess
import os
import collections
import sys
import warnings
import re
from six.moves import zip

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import syspath, command_output, displayable_path, py3_path


# Utilities.

class ReplayGainError(Exception):
    """Raised when a local (to a track or an album) error occurs in one
    of the backends.
    """


class FatalReplayGainError(Exception):
    """Raised when a fatal error occurs in one of the backends.
    """


class FatalGstreamerPluginReplayGainError(FatalReplayGainError):
    """Raised when a fatal error occurs in the GStreamerBackend when
    loading the required plugins."""


def call(args):
    """Execute the command and return its output or raise a
    ReplayGainError on failure.
    """
    try:
        return command_output(args)
    except subprocess.CalledProcessError as e:
        raise ReplayGainError(
            u"{0} exited with status {1}".format(args[0], e.returncode)
        )
    except UnicodeEncodeError:
        # Due to a bug in Python 2's subprocess on Windows, Unicode
        # filenames can fail to encode on that platform. See:
        # https://github.com/google-code-export/beets/issues/499
        raise ReplayGainError(u"argument encoding failed")


# Backend base and plumbing classes.

Gain = collections.namedtuple("Gain", "gain peak")
AlbumGain = collections.namedtuple("AlbumGain", "album_gain track_gains")


class Backend(object):
    """An abstract class representing engine for calculating RG values.
    """

    def __init__(self, config, log):
        """Initialize the backend with the configuration view for the
        plugin.
        """
        self._log = log

    def compute_track_gain(self, items):
        raise NotImplementedError()

    def compute_album_gain(self, album):
        # TODO: implement album gain in terms of track gain of the
        # individual tracks which can be used for any backend.
        raise NotImplementedError()


# bsg1770gain backend
class Bs1770gainBackend(Backend):
    """bs1770gain is a loudness scanner compliant with ITU-R BS.1770 and
    its flavors EBU R128, ATSC A/85 and Replaygain 2.0.
    """

    def __init__(self, config, log):
        super(Bs1770gainBackend, self).__init__(config, log)
        config.add({
            'chunk_at': 5000,
            'method': 'replaygain',
        })
        self.chunk_at = config['chunk_at'].as_number()
        self.method = '--' + config['method'].as_str()

        cmd = 'bs1770gain'
        try:
            call([cmd, self.method])
            self.command = cmd
        except OSError:
            raise FatalReplayGainError(
                u'Is bs1770gain installed? Is your method in config correct?'
            )
        if not self.command:
            raise FatalReplayGainError(
                u'no replaygain command found: install bs1770gain'
            )

    def compute_track_gain(self, items):
        """Computes the track gain of the given tracks, returns a list
        of TrackGain objects.
        """

        output = self.compute_gain(items, False)
        return output

    def compute_album_gain(self, album):
        """Computes the album gain of the given album, returns an
        AlbumGain object.
        """
        # TODO: What should be done when not all tracks in the album are
        # supported?

        supported_items = album.items()
        output = self.compute_gain(supported_items, True)

        if not output:
            raise ReplayGainError(u'no output from bs1770gain')
        return AlbumGain(output[-1], output[:-1])

    def isplitter(self, items, chunk_at):
        """Break an iterable into chunks of at most size `chunk_at`,
        generating lists for each chunk.
        """
        iterable = iter(items)
        while True:
            result = []
            for i in range(chunk_at):
                try:
                    a = next(iterable)
                except StopIteration:
                    break
                else:
                    result.append(a)
            if result:
                yield result
            else:
                break

    def compute_gain(self, items, is_album):
        """Computes the track or album gain of a list of items, returns
        a list of TrackGain objects.
        When computing album gain, the last TrackGain object returned is
        the album gain
        """

        if len(items) == 0:
            return []

        albumgaintot = 0.0
        albumpeaktot = 0.0
        returnchunks = []

        # In the case of very large sets of music, we break the tracks
        # into smaller chunks and process them one at a time. This
        # avoids running out of memory.
        if len(items) > self.chunk_at:
            i = 0
            for chunk in self.isplitter(items, self.chunk_at):
                i += 1
                returnchunk = self.compute_chunk_gain(chunk, is_album)
                albumgaintot += returnchunk[-1].gain
                albumpeaktot += returnchunk[-1].peak
                returnchunks = returnchunks + returnchunk[0:-1]
            returnchunks.append(Gain(albumgaintot / i, albumpeaktot / i))
            return returnchunks
        else:
            return self.compute_chunk_gain(items, is_album)

    def compute_chunk_gain(self, items, is_album):
        """Compute ReplayGain values and return a list of results
        dictionaries as given by `parse_tool_output`.
        """
        # Construct shell command.
        cmd = [self.command]
        cmd += [self.method]
        cmd += ['-p']

        # Workaround for Windows: the underlying tool fails on paths
        # with the \\?\ prefix, so we don't use it here. This
        # prevents the backend from working with long paths.
        args = cmd + [syspath(i.path, prefix=False) for i in items]

        # Invoke the command.
        self._log.debug(
            u'executing {0}', u' '.join(map(displayable_path, args))
        )
        output = call(args)

        self._log.debug(u'analysis finished: {0}', output)
        results = self.parse_tool_output(output,
                                         len(items) + is_album)
        self._log.debug(u'{0} items, {1} results', len(items), len(results))
        return results

    def parse_tool_output(self, text, num_lines):
        """Given the  output from bs1770gain, parse the text and
        return a list of dictionaries
        containing information about each analyzed file.
        """
        out = []
        data = text.decode('utf-8', errors='ignore')
        regex = re.compile(
            u'(\\s{2,2}\\[\\d+\\/\\d+\\].*?|\\[ALBUM\\].*?)'
            '(?=\\s{2,2}\\[\\d+\\/\\d+\\]|\\s{2,2}\\[ALBUM\\]'
            ':|done\\.\\s)', re.DOTALL | re.UNICODE)
        results = re.findall(regex, data)
        for parts in results[0:num_lines]:
            part = parts.split(u'\n')
            if len(part) == 0:
                self._log.debug(u'bad tool output: {0!r}', text)
                raise ReplayGainError(u'bs1770gain failed')

            try:
                song = {
                    'file': part[0],
                    'gain': float((part[1].split('/'))[1].split('LU')[0]),
                    'peak': float(part[2].split('/')[1]),
                }
            except IndexError:
                self._log.info(u'bs1770gain reports (faulty file?): {}', parts)
                continue

            out.append(Gain(song['gain'], song['peak']))
        return out


# mpgain/aacgain CLI tool backend.
class CommandBackend(Backend):

    def __init__(self, config, log):
        super(CommandBackend, self).__init__(config, log)
        config.add({
            'command': u"",
            'noclip': True,
        })

        self.command = config["command"].as_str()

        if self.command:
            # Explicit executable path.
            if not os.path.isfile(self.command):
                raise FatalReplayGainError(
                    u'replaygain command does not exist: {0}'.format(
                        self.command)
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
            raise FatalReplayGainError(
                u'no replaygain command found: install mp3gain or aacgain'
            )

        self.noclip = config['noclip'].get(bool)
        target_level = config['targetlevel'].as_number()
        self.gain_offset = int(target_level - 89)

    def compute_track_gain(self, items):
        """Computes the track gain of the given tracks, returns a list
        of TrackGain objects.
        """
        supported_items = list(filter(self.format_supported, items))
        output = self.compute_gain(supported_items, False)
        return output

    def compute_album_gain(self, album):
        """Computes the album gain of the given album, returns an
        AlbumGain object.
        """
        # TODO: What should be done when not all tracks in the album are
        # supported?

        supported_items = list(filter(self.format_supported, album.items()))
        if len(supported_items) != len(album.items()):
            self._log.debug(u'tracks are of unsupported format')
            return AlbumGain(None, [])

        output = self.compute_gain(supported_items, True)
        return AlbumGain(output[-1], output[:-1])

    def format_supported(self, item):
        """Checks whether the given item is supported by the selected tool.
        """
        if 'mp3gain' in self.command and item.format != 'MP3':
            return False
        elif 'aacgain' in self.command and item.format not in ('MP3', 'AAC'):
            return False
        return True

    def compute_gain(self, items, is_album):
        """Computes the track or album gain of a list of items, returns
        a list of TrackGain objects.

        When computing album gain, the last TrackGain object returned is
        the album gain
        """
        if len(items) == 0:
            self._log.debug(u'no supported tracks to analyze')
            return []

        """Compute ReplayGain values and return a list of results
        dictionaries as given by `parse_tool_output`.
        """
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
        cmd = cmd + ['-d', str(self.gain_offset)]
        cmd = cmd + [syspath(i.path) for i in items]

        self._log.debug(u'analyzing {0} files', len(items))
        self._log.debug(u"executing {0}", " ".join(map(displayable_path, cmd)))
        output = call(cmd)
        self._log.debug(u'analysis finished')
        return self.parse_tool_output(output,
                                      len(items) + (1 if is_album else 0))

    def parse_tool_output(self, text, num_lines):
        """Given the tab-delimited output from an invocation of mp3gain
        or aacgain, parse the text and return a list of dictionaries
        containing information about each analyzed file.
        """
        out = []
        for line in text.split(b'\n')[1:num_lines + 1]:
            parts = line.split(b'\t')
            if len(parts) != 6 or parts[0] == b'File':
                self._log.debug(u'bad tool output: {0}', text)
                raise ReplayGainError(u'mp3gain failed')
            d = {
                'file': parts[0],
                'mp3gain': int(parts[1]),
                'gain': float(parts[2]),
                'peak': float(parts[3]) / (1 << 15),
                'maxgain': int(parts[4]),
                'mingain': int(parts[5]),

            }
            out.append(Gain(d['gain'], d['peak']))
        return out


# GStreamer-based backend.

class GStreamerBackend(Backend):

    def __init__(self, config, log):
        super(GStreamerBackend, self).__init__(config, log)
        self._import_gst()

        # Initialized a GStreamer pipeline of the form filesrc ->
        # decodebin -> audioconvert -> audioresample -> rganalysis ->
        # fakesink The connection between decodebin and audioconvert is
        # handled dynamically after decodebin figures out the type of
        # the input file.
        self._src = self.Gst.ElementFactory.make("filesrc", "src")
        self._decbin = self.Gst.ElementFactory.make("decodebin", "decbin")
        self._conv = self.Gst.ElementFactory.make("audioconvert", "conv")
        self._res = self.Gst.ElementFactory.make("audioresample", "res")
        self._rg = self.Gst.ElementFactory.make("rganalysis", "rg")

        if self._src is None or self._decbin is None or self._conv is None \
           or self._res is None or self._rg is None:
            raise FatalGstreamerPluginReplayGainError(
                u"Failed to load required GStreamer plugins"
            )

        # We check which files need gain ourselves, so all files given
        # to rganalsys should have their gain computed, even if it
        # already exists.
        self._rg.set_property("forced", True)
        self._rg.set_property("reference-level",
                              config["targetlevel"].as_number())
        self._sink = self.Gst.ElementFactory.make("fakesink", "sink")

        self._pipe = self.Gst.Pipeline()
        self._pipe.add(self._src)
        self._pipe.add(self._decbin)
        self._pipe.add(self._conv)
        self._pipe.add(self._res)
        self._pipe.add(self._rg)
        self._pipe.add(self._sink)

        self._src.link(self._decbin)
        self._conv.link(self._res)
        self._res.link(self._rg)
        self._rg.link(self._sink)

        self._bus = self._pipe.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect("message::eos", self._on_eos)
        self._bus.connect("message::error", self._on_error)
        self._bus.connect("message::tag", self._on_tag)
        # Needed for handling the dynamic connection between decodebin
        # and audioconvert
        self._decbin.connect("pad-added", self._on_pad_added)
        self._decbin.connect("pad-removed", self._on_pad_removed)

        self._main_loop = self.GLib.MainLoop()

        self._files = []

    def _import_gst(self):
        """Import the necessary GObject-related modules and assign `Gst`
        and `GObject` fields on this object.
        """

        try:
            import gi
        except ImportError:
            raise FatalReplayGainError(
                u"Failed to load GStreamer: python-gi not found"
            )

        try:
            gi.require_version('Gst', '1.0')
        except ValueError as e:
            raise FatalReplayGainError(
                u"Failed to load GStreamer 1.0: {0}".format(e)
            )

        from gi.repository import GObject, Gst, GLib
        # Calling GObject.threads_init() is not needed for
        # PyGObject 3.10.2+
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            GObject.threads_init()
        Gst.init([sys.argv[0]])

        self.GObject = GObject
        self.GLib = GLib
        self.Gst = Gst

    def compute(self, files, album):
        self._error = None
        self._files = list(files)

        if len(self._files) == 0:
            return

        self._file_tags = collections.defaultdict(dict)

        if album:
            self._rg.set_property("num-tracks", len(self._files))

        if self._set_first_file():
            self._main_loop.run()
            if self._error is not None:
                raise self._error

    def compute_track_gain(self, items):
        self.compute(items, False)
        if len(self._file_tags) != len(items):
            raise ReplayGainError(u"Some tracks did not receive tags")

        ret = []
        for item in items:
            ret.append(Gain(self._file_tags[item]["TRACK_GAIN"],
                            self._file_tags[item]["TRACK_PEAK"]))

        return ret

    def compute_album_gain(self, album):
        items = list(album.items())
        self.compute(items, True)
        if len(self._file_tags) != len(items):
            raise ReplayGainError(u"Some items in album did not receive tags")

        # Collect track gains.
        track_gains = []
        for item in items:
            try:
                gain = self._file_tags[item]["TRACK_GAIN"]
                peak = self._file_tags[item]["TRACK_PEAK"]
            except KeyError:
                raise ReplayGainError(u"results missing for track")
            track_gains.append(Gain(gain, peak))

        # Get album gain information from the last track.
        last_tags = self._file_tags[items[-1]]
        try:
            gain = last_tags["ALBUM_GAIN"]
            peak = last_tags["ALBUM_PEAK"]
        except KeyError:
            raise ReplayGainError(u"results missing for album")

        return AlbumGain(Gain(gain, peak), track_gains)

    def close(self):
        self._bus.remove_signal_watch()

    def _on_eos(self, bus, message):
        # A file finished playing in all elements of the pipeline. The
        # RG tags have already been propagated.  If we don't have a next
        # file, we stop processing.
        if not self._set_next_file():
            self._pipe.set_state(self.Gst.State.NULL)
            self._main_loop.quit()

    def _on_error(self, bus, message):
        self._pipe.set_state(self.Gst.State.NULL)
        self._main_loop.quit()
        err, debug = message.parse_error()
        f = self._src.get_property("location")
        # A GStreamer error, either an unsupported format or a bug.
        self._error = ReplayGainError(
            u"Error {0!r} - {1!r} on file {2!r}".format(err, debug, f)
        )

    def _on_tag(self, bus, message):
        tags = message.parse_tag()

        def handle_tag(taglist, tag, userdata):
            # The rganalysis element provides both the existing tags for
            # files and the new computes tags.  In order to ensure we
            # store the computed tags, we overwrite the RG values of
            # received a second time.
            if tag == self.Gst.TAG_TRACK_GAIN:
                self._file_tags[self._file]["TRACK_GAIN"] = \
                    taglist.get_double(tag)[1]
            elif tag == self.Gst.TAG_TRACK_PEAK:
                self._file_tags[self._file]["TRACK_PEAK"] = \
                    taglist.get_double(tag)[1]
            elif tag == self.Gst.TAG_ALBUM_GAIN:
                self._file_tags[self._file]["ALBUM_GAIN"] = \
                    taglist.get_double(tag)[1]
            elif tag == self.Gst.TAG_ALBUM_PEAK:
                self._file_tags[self._file]["ALBUM_PEAK"] = \
                    taglist.get_double(tag)[1]
            elif tag == self.Gst.TAG_REFERENCE_LEVEL:
                self._file_tags[self._file]["REFERENCE_LEVEL"] = \
                    taglist.get_double(tag)[1]

        tags.foreach(handle_tag, None)

    def _set_first_file(self):
        if len(self._files) == 0:
            return False

        self._file = self._files.pop(0)
        self._pipe.set_state(self.Gst.State.NULL)
        self._src.set_property("location", py3_path(syspath(self._file.path)))
        self._pipe.set_state(self.Gst.State.PLAYING)
        return True

    def _set_file(self):
        """Initialize the filesrc element with the next file to be analyzed.
        """
        # No more files, we're done
        if len(self._files) == 0:
            return False

        self._file = self._files.pop(0)

        # Disconnect the decodebin element from the pipeline, set its
        # state to READY to to clear it.
        self._decbin.unlink(self._conv)
        self._decbin.set_state(self.Gst.State.READY)

        # Set a new file on the filesrc element, can only be done in the
        # READY state
        self._src.set_state(self.Gst.State.READY)
        self._src.set_property("location", py3_path(syspath(self._file.path)))

        # Ensure the filesrc element received the paused state of the
        # pipeline in a blocking manner
        self._src.sync_state_with_parent()
        self._src.get_state(self.Gst.CLOCK_TIME_NONE)

        # Ensure the decodebin element receives the paused state of the
        # pipeline in a blocking manner
        self._decbin.sync_state_with_parent()
        self._decbin.get_state(self.Gst.CLOCK_TIME_NONE)

        return True

    def _set_next_file(self):
        """Set the next file to be analyzed while keeping the pipeline
        in the PAUSED state so that the rganalysis element can correctly
        handle album gain.
        """
        # A blocking pause
        self._pipe.set_state(self.Gst.State.PAUSED)
        self._pipe.get_state(self.Gst.CLOCK_TIME_NONE)

        # Try setting the next file
        ret = self._set_file()
        if ret:
            # Seek to the beginning in order to clear the EOS state of the
            # various elements of the pipeline
            self._pipe.seek_simple(self.Gst.Format.TIME,
                                   self.Gst.SeekFlags.FLUSH,
                                   0)
            self._pipe.set_state(self.Gst.State.PLAYING)

        return ret

    def _on_pad_added(self, decbin, pad):
        sink_pad = self._conv.get_compatible_pad(pad, None)
        assert(sink_pad is not None)
        pad.link(sink_pad)

    def _on_pad_removed(self, decbin, pad):
        # Called when the decodebin element is disconnected from the
        # rest of the pipeline while switching input files
        peer = pad.get_peer()
        assert(peer is None)


class AudioToolsBackend(Backend):
    """ReplayGain backend that uses `Python Audio Tools
    <http://audiotools.sourceforge.net/>`_ and its capabilities to read more
    file formats and compute ReplayGain values using it replaygain module.
    """

    def __init__(self, config, log):
        super(AudioToolsBackend, self).__init__(config, log)
        self._import_audiotools()

    def _import_audiotools(self):
        """Check whether it's possible to import the necessary modules.
        There is no check on the file formats at runtime.

        :raises :exc:`ReplayGainError`: if the modules cannot be imported
        """
        try:
            import audiotools
            import audiotools.replaygain
        except ImportError:
            raise FatalReplayGainError(
                u"Failed to load audiotools: audiotools not found"
            )
        self._mod_audiotools = audiotools
        self._mod_replaygain = audiotools.replaygain

    def open_audio_file(self, item):
        """Open the file to read the PCM stream from the using
        ``item.path``.

        :return: the audiofile instance
        :rtype: :class:`audiotools.AudioFile`
        :raises :exc:`ReplayGainError`: if the file is not found or the
        file format is not supported
        """
        try:
            audiofile = self._mod_audiotools.open(item.path)
        except IOError:
            raise ReplayGainError(
                u"File {} was not found".format(item.path)
            )
        except self._mod_audiotools.UnsupportedFile:
            raise ReplayGainError(
                u"Unsupported file type {}".format(item.format)
            )

        return audiofile

    def init_replaygain(self, audiofile, item):
        """Return an initialized :class:`audiotools.replaygain.ReplayGain`
        instance, which requires the sample rate of the song(s) on which
        the ReplayGain values will be computed. The item is passed in case
        the sample rate is invalid to log the stored item sample rate.

        :return: initialized replagain object
        :rtype: :class:`audiotools.replaygain.ReplayGain`
        :raises: :exc:`ReplayGainError` if the sample rate is invalid
        """
        try:
            rg = self._mod_replaygain.ReplayGain(audiofile.sample_rate())
        except ValueError:
            raise ReplayGainError(
                u"Unsupported sample rate {}".format(item.samplerate))
            return
        return rg

    def compute_track_gain(self, items):
        """Compute ReplayGain values for the requested items.

        :return list: list of :class:`Gain` objects
        """
        return [self._compute_track_gain(item) for item in items]

    def _title_gain(self, rg, audiofile):
        """Get the gain result pair from PyAudioTools using the `ReplayGain`
        instance `rg` for the given `audiofile`.

        Wraps `rg.title_gain(audiofile.to_pcm())` and throws a
        `ReplayGainError` when the library fails.
        """
        try:
            # The method needs an audiotools.PCMReader instance that can
            # be obtained from an audiofile instance.
            return rg.title_gain(audiofile.to_pcm())
        except ValueError as exc:
            # `audiotools.replaygain` can raise a `ValueError` if the sample
            # rate is incorrect.
            self._log.debug(u'error in rg.title_gain() call: {}', exc)
            raise ReplayGainError(u'audiotools audio data error')

    def _compute_track_gain(self, item):
        """Compute ReplayGain value for the requested item.

        :rtype: :class:`Gain`
        """
        audiofile = self.open_audio_file(item)
        rg = self.init_replaygain(audiofile, item)

        # Each call to title_gain on a ReplayGain object returns peak and gain
        # of the track.
        rg_track_gain, rg_track_peak = self._title_gain(rg, audiofile)

        self._log.debug(u'ReplayGain for track {0} - {1}: {2:.2f}, {3:.2f}',
                        item.artist, item.title, rg_track_gain, rg_track_peak)
        return Gain(gain=rg_track_gain, peak=rg_track_peak)

    def compute_album_gain(self, album):
        """Compute ReplayGain values for the requested album and its items.

        :rtype: :class:`AlbumGain`
        """
        self._log.debug(u'Analysing album {0}', album)

        # The first item is taken and opened to get the sample rate to
        # initialize the replaygain object. The object is used for all the
        # tracks in the album to get the album values.
        item = list(album.items())[0]
        audiofile = self.open_audio_file(item)
        rg = self.init_replaygain(audiofile, item)

        track_gains = []
        for item in album.items():
            audiofile = self.open_audio_file(item)
            rg_track_gain, rg_track_peak = self._title_gain(rg, audiofile)
            track_gains.append(
                Gain(gain=rg_track_gain, peak=rg_track_peak)
            )
            self._log.debug(u'ReplayGain for track {0}: {1:.2f}, {2:.2f}',
                            item, rg_track_gain, rg_track_peak)

        # After getting the values for all tracks, it's possible to get the
        # album values.
        rg_album_gain, rg_album_peak = rg.album_gain()
        self._log.debug(u'ReplayGain for album {0}: {1:.2f}, {2:.2f}',
                        album, rg_album_gain, rg_album_peak)

        return AlbumGain(
            Gain(gain=rg_album_gain, peak=rg_album_peak),
            track_gains=track_gains
        )


# Main plugin logic.

class ReplayGainPlugin(BeetsPlugin):
    """Provides ReplayGain analysis.
    """

    backends = {
        "command": CommandBackend,
        "gstreamer": GStreamerBackend,
        "audiotools": AudioToolsBackend,
        "bs1770gain": Bs1770gainBackend,
    }

    def __init__(self):
        super(ReplayGainPlugin, self).__init__()

        # default backend is 'command' for backward-compatibility.
        self.config.add({
            'overwrite': False,
            'auto': True,
            'backend': u'command',
            'targetlevel': 89,
        })

        self.overwrite = self.config['overwrite'].get(bool)
        backend_name = self.config['backend'].as_str()
        if backend_name not in self.backends:
            raise ui.UserError(
                u"Selected ReplayGain backend {0} is not supported. "
                u"Please select one of: {1}".format(
                    backend_name,
                    u', '.join(self.backends.keys())
                )
            )

        # On-import analysis.
        if self.config['auto']:
            self.import_stages = [self.imported]

        try:
            self.backend_instance = self.backends[backend_name](
                self.config, self._log
            )
        except (ReplayGainError, FatalReplayGainError) as e:
            raise ui.UserError(
                u'replaygain initialization failed: {0}'.format(e))

    def track_requires_gain(self, item):
        return self.overwrite or \
            (not item.rg_track_gain or not item.rg_track_peak)

    def album_requires_gain(self, album):
        # Skip calculating gain only when *all* files don't need
        # recalculation. This way, if any file among an album's tracks
        # needs recalculation, we still get an accurate album gain
        # value.
        return self.overwrite or \
            any([not item.rg_album_gain or not item.rg_album_peak
                 for item in album.items()])

    def store_track_gain(self, item, track_gain):
        item.rg_track_gain = track_gain.gain
        item.rg_track_peak = track_gain.peak
        item.store()

        self._log.debug(u'applied track gain {0}, peak {1}',
                        item.rg_track_gain, item.rg_track_peak)

    def store_album_gain(self, album, album_gain):
        album.rg_album_gain = album_gain.gain
        album.rg_album_peak = album_gain.peak
        album.store()

        self._log.debug(u'applied album gain {0}, peak {1}',
                        album.rg_album_gain, album.rg_album_peak)

    def handle_album(self, album, write):
        """Compute album and track replay gain store it in all of the
        album's items.

        If ``write`` is truthy then ``item.write()`` is called for each
        item. If replay gain information is already present in all
        items, nothing is done.
        """
        if not self.album_requires_gain(album):
            self._log.info(u'Skipping album {0}', album)
            return

        self._log.info(u'analyzing {0}', album)

        try:
            album_gain = self.backend_instance.compute_album_gain(album)
            if len(album_gain.track_gains) != len(album.items()):
                raise ReplayGainError(
                    u"ReplayGain backend failed "
                    u"for some tracks in album {0}".format(album)
                )

            self.store_album_gain(album, album_gain.album_gain)
            for item, track_gain in zip(album.items(), album_gain.track_gains):
                self.store_track_gain(item, track_gain)
                if write:
                    item.try_write()
        except ReplayGainError as e:
            self._log.info(u"ReplayGain error: {0}", e)
        except FatalReplayGainError as e:
            raise ui.UserError(
                u"Fatal replay gain error: {0}".format(e))

    def handle_track(self, item, write):
        """Compute track replay gain and store it in the item.

        If ``write`` is truthy then ``item.write()`` is called to write
        the data to disk.  If replay gain information is already present
        in the item, nothing is done.
        """
        if not self.track_requires_gain(item):
            self._log.info(u'Skipping track {0}', item)
            return

        self._log.info(u'analyzing {0}', item)

        try:
            track_gains = self.backend_instance.compute_track_gain([item])
            if len(track_gains) != 1:
                raise ReplayGainError(
                    u"ReplayGain backend failed for track {0}".format(item)
                )

            self.store_track_gain(item, track_gains[0])
            if write:
                item.try_write()
        except ReplayGainError as e:
            self._log.info(u"ReplayGain error: {0}", e)
        except FatalReplayGainError as e:
            raise ui.UserError(
                u"Fatal replay gain error: {0}".format(e))

    def imported(self, session, task):
        """Add replay gain info to items or albums of ``task``.
        """
        if task.is_album:
            self.handle_album(task.album, False)
        else:
            self.handle_track(task.item, False)

    def commands(self):
        """Return the "replaygain" ui subcommand.
        """
        def func(lib, opts, args):
            write = ui.should_write()

            if opts.album:
                for album in lib.albums(ui.decargs(args)):
                    self.handle_album(album, write)

            else:
                for item in lib.items(ui.decargs(args)):
                    self.handle_track(item, write)

        cmd = ui.Subcommand('replaygain', help=u'analyze for ReplayGain')
        cmd.parser.add_album_option()
        cmd.func = func
        return [cmd]
