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

import collections
import enum
import math
import os
import signal
import six
import subprocess
import sys
import warnings
from multiprocessing.pool import ThreadPool, RUN
from six.moves import zip, queue
from threading import Thread, Event

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import (syspath, command_output, displayable_path,
                        py3_path, cpu_count)


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


def call(args, **kwargs):
    """Execute the command and return its output or raise a
    ReplayGainError on failure.
    """
    try:
        return command_output(args, **kwargs)
    except subprocess.CalledProcessError as e:
        raise ReplayGainError(
            u"{0} exited with status {1}".format(args[0], e.returncode)
        )
    except UnicodeEncodeError:
        # Due to a bug in Python 2's subprocess on Windows, Unicode
        # filenames can fail to encode on that platform. See:
        # https://github.com/google-code-export/beets/issues/499
        raise ReplayGainError(u"argument encoding failed")


def after_version(version_a, version_b):
    return tuple(int(s) for s in version_a.split('.')) \
            >= tuple(int(s) for s in version_b.split('.'))


def db_to_lufs(db):
    """Convert db to LUFS.

    According to https://wiki.hydrogenaud.io/index.php?title=
      ReplayGain_2.0_specification#Reference_level
    """
    return db - 107


def lufs_to_db(db):
    """Convert LUFS to db.

    According to https://wiki.hydrogenaud.io/index.php?title=
      ReplayGain_2.0_specification#Reference_level
    """
    return db + 107


# Backend base and plumbing classes.

# gain: in LU to reference level
# peak: part of full scale (FS is 1.0)
Gain = collections.namedtuple("Gain", "gain peak")
# album_gain: Gain object
# track_gains: list of Gain objects
AlbumGain = collections.namedtuple("AlbumGain", "album_gain track_gains")


class Peak(enum.Enum):
    none = 0
    true = 1
    sample = 2


class Backend(object):
    """An abstract class representing engine for calculating RG values.
    """

    do_parallel = False

    def __init__(self, config, log):
        """Initialize the backend with the configuration view for the
        plugin.
        """
        self._log = log

    def compute_track_gain(self, items, target_level, peak):
        """Computes the track gain of the given tracks, returns a list
        of Gain objects.
        """
        raise NotImplementedError()

    def compute_album_gain(self, items, target_level, peak):
        """Computes the album gain of the given album, returns an
        AlbumGain object.
        """
        raise NotImplementedError()


# ffmpeg backend
class FfmpegBackend(Backend):
    """A replaygain backend using ffmpeg's ebur128 filter.
    """

    do_parallel = True

    def __init__(self, config, log):
        super(FfmpegBackend, self).__init__(config, log)
        self._ffmpeg_path = "ffmpeg"

        # check that ffmpeg is installed
        try:
            ffmpeg_version_out = call([self._ffmpeg_path, "-version"])
        except OSError:
            raise FatalReplayGainError(
                u"could not find ffmpeg at {0}".format(self._ffmpeg_path)
            )
        incompatible_ffmpeg = True
        for line in ffmpeg_version_out.stdout.splitlines():
            if line.startswith(b"configuration:"):
                if b"--enable-libebur128" in line:
                    incompatible_ffmpeg = False
            if line.startswith(b"libavfilter"):
                version = line.split(b" ", 1)[1].split(b"/", 1)[0].split(b".")
                version = tuple(map(int, version))
                if version >= (6, 67, 100):
                    incompatible_ffmpeg = False
        if incompatible_ffmpeg:
            raise FatalReplayGainError(
                u"Installed FFmpeg version does not support ReplayGain."
                u"calculation. Either libavfilter version 6.67.100 or above or"
                u"the --enable-libebur128 configuration option is required."
            )

    def compute_track_gain(self, items, target_level, peak):
        """Computes the track gain of the given tracks, returns a list
        of Gain objects (the track gains).
        """
        gains = []
        for item in items:
            gains.append(
                self._analyse_item(
                    item,
                    target_level,
                    peak,
                    count_blocks=False,
                )[0]  # take only the gain, discarding number of gating blocks
            )
        return gains

    def compute_album_gain(self, items, target_level, peak):
        """Computes the album gain of the given album, returns an
        AlbumGain object.
        """
        target_level_lufs = db_to_lufs(target_level)

        # analyse tracks
        # list of track Gain objects
        track_gains = []
        # maximum peak
        album_peak = 0
        # sum of BS.1770 gating block powers
        sum_powers = 0
        # total number of BS.1770 gating blocks
        n_blocks = 0

        for item in items:
            track_gain, track_n_blocks = self._analyse_item(
                item, target_level, peak
            )
            track_gains.append(track_gain)

            # album peak is maximum track peak
            album_peak = max(album_peak, track_gain.peak)

            # prepare album_gain calculation
            # total number of blocks is sum of track blocks
            n_blocks += track_n_blocks

            # convert `LU to target_level` -> LUFS
            track_loudness = target_level_lufs - track_gain.gain
            # This reverses ITU-R BS.1770-4 p. 6 equation (5) to convert
            # from loudness to power. The result is the average gating
            # block power.
            track_power = 10**((track_loudness + 0.691) / 10)

            # Weight that average power by the number of gating blocks to
            # get the sum of all their powers. Add that to the sum of all
            # block powers in this album.
            sum_powers += track_power * track_n_blocks

        # calculate album gain
        if n_blocks > 0:
            # compare ITU-R BS.1770-4 p. 6 equation (5)
            # Album gain is the replaygain of the concatenation of all tracks.
            album_gain = -0.691 + 10 * math.log10(sum_powers / n_blocks)
        else:
            album_gain = -70
        # convert LUFS -> `LU to target_level`
        album_gain = target_level_lufs - album_gain

        self._log.debug(
            u"{0}: gain {1} LU, peak {2}"
            .format(items, album_gain, album_peak)
            )

        return AlbumGain(Gain(album_gain, album_peak), track_gains)

    def _construct_cmd(self, item, peak_method):
        """Construct the shell command to analyse items."""
        return [
            self._ffmpeg_path,
            "-nostats",
            "-hide_banner",
            "-i",
            item.path,
            "-map",
            "a:0",
            "-filter",
            "ebur128=peak={0}".format(peak_method),
            "-f",
            "null",
            "-",
        ]

    def _analyse_item(self, item, target_level, peak, count_blocks=True):
        """Analyse item. Return a pair of a Gain object and the number
        of gating blocks above the threshold.

        If `count_blocks` is False, the number of gating blocks returned
        will be 0.
        """
        target_level_lufs = db_to_lufs(target_level)
        peak_method = peak.name

        # call ffmpeg
        self._log.debug(u"analyzing {0}".format(item))
        cmd = self._construct_cmd(item, peak_method)
        self._log.debug(
            u'executing {0}', u' '.join(map(displayable_path, cmd))
        )
        output = call(cmd).stderr.splitlines()

        # parse output

        if peak == Peak.none:
            peak = 0
        else:
            line_peak = self._find_line(
                output,
                "  {0} peak:".format(peak_method.capitalize()).encode(),
                start_line=len(output) - 1, step_size=-1,
            )
            peak = self._parse_float(
                output[self._find_line(
                    output, b"    Peak:",
                    line_peak,
                )]
            )
            # convert TPFS -> part of FS
            peak = 10**(peak / 20)

        line_integrated_loudness = self._find_line(
            output, b"  Integrated loudness:",
            start_line=len(output) - 1, step_size=-1,
        )
        gain = self._parse_float(
            output[self._find_line(
                output, b"    I:",
                line_integrated_loudness,
            )]
        )
        # convert LUFS -> LU from target level
        gain = target_level_lufs - gain

        # count BS.1770 gating blocks
        n_blocks = 0
        if count_blocks:
            gating_threshold = self._parse_float(
                output[self._find_line(
                    output, b"    Threshold:",
                    start_line=line_integrated_loudness,
                )]
            )
            for line in output:
                if not line.startswith(b"[Parsed_ebur128"):
                    continue
                if line.endswith(b"Summary:"):
                    continue
                line = line.split(b"M:", 1)
                if len(line) < 2:
                    continue
                if self._parse_float(b"M: " + line[1]) >= gating_threshold:
                    n_blocks += 1
            self._log.debug(
                u"{0}: {1} blocks over {2} LUFS"
                .format(item, n_blocks, gating_threshold)
            )

        self._log.debug(
            u"{0}: gain {1} LU, peak {2}"
            .format(item, gain, peak)
        )

        return Gain(gain, peak), n_blocks

    def _find_line(self, output, search, start_line=0, step_size=1):
        """Return index of line beginning with `search`.

        Begins searching at index `start_line` in `output`.
        """
        end_index = len(output) if step_size > 0 else -1
        for i in range(start_line, end_index, step_size):
            if output[i].startswith(search):
                return i
        raise ReplayGainError(
            u"ffmpeg output: missing {0} after line {1}"
            .format(repr(search), start_line)
            )

    def _parse_float(self, line):
        """Extract a float from a key value pair in `line`.

        This format is expected: /[^:]:[[:space:]]*value.*/, where `value` is
        the float.
        """
        # extract value
        value = line.split(b":", 1)
        if len(value) < 2:
            raise ReplayGainError(
                u"ffmpeg output: expected key value pair, found {0}"
                .format(line)
                )
        value = value[1].lstrip()
        # strip unit
        value = value.split(b" ", 1)[0]
        # cast value to float
        try:
            return float(value)
        except ValueError:
            raise ReplayGainError(
                u"ffmpeg output: expected float value, found {0}"
                .format(value)
                )


# mpgain/aacgain CLI tool backend.
class CommandBackend(Backend):
    do_parallel = True

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

    def compute_track_gain(self, items, target_level, peak):
        """Computes the track gain of the given tracks, returns a list
        of TrackGain objects.
        """
        supported_items = list(filter(self.format_supported, items))
        output = self.compute_gain(supported_items, target_level, False)
        return output

    def compute_album_gain(self, items, target_level, peak):
        """Computes the album gain of the given album, returns an
        AlbumGain object.
        """
        # TODO: What should be done when not all tracks in the album are
        # supported?

        supported_items = list(filter(self.format_supported, items))
        if len(supported_items) != len(items):
            self._log.debug(u'tracks are of unsupported format')
            return AlbumGain(None, [])

        output = self.compute_gain(supported_items, target_level, True)
        return AlbumGain(output[-1], output[:-1])

    def format_supported(self, item):
        """Checks whether the given item is supported by the selected tool.
        """
        if 'mp3gain' in self.command and item.format != 'MP3':
            return False
        elif 'aacgain' in self.command and item.format not in ('MP3', 'AAC'):
            return False
        return True

    def compute_gain(self, items, target_level, is_album):
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
        cmd = cmd + ['-d', str(int(target_level - 89))]
        cmd = cmd + [syspath(i.path) for i in items]

        self._log.debug(u'analyzing {0} files', len(items))
        self._log.debug(u"executing {0}", " ".join(map(displayable_path, cmd)))
        output = call(cmd).stdout
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

    def compute(self, files, target_level, album):
        self._error = None
        self._files = list(files)

        if len(self._files) == 0:
            return

        self._file_tags = collections.defaultdict(dict)

        self._rg.set_property("reference-level", target_level)

        if album:
            self._rg.set_property("num-tracks", len(self._files))

        if self._set_first_file():
            self._main_loop.run()
            if self._error is not None:
                raise self._error

    def compute_track_gain(self, items, target_level, peak):
        self.compute(items, target_level, False)
        if len(self._file_tags) != len(items):
            raise ReplayGainError(u"Some tracks did not receive tags")

        ret = []
        for item in items:
            ret.append(Gain(self._file_tags[item]["TRACK_GAIN"],
                            self._file_tags[item]["TRACK_PEAK"]))

        return ret

    def compute_album_gain(self, items, target_level, peak):
        items = list(items)
        self.compute(items, target_level, True)
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

        # Ensure the filesrc element received the paused state of the
        # pipeline in a blocking manner
        self._src.sync_state_with_parent()
        self._src.get_state(self.Gst.CLOCK_TIME_NONE)

        # Ensure the decodebin element receives the paused state of the
        # pipeline in a blocking manner
        self._decbin.sync_state_with_parent()
        self._decbin.get_state(self.Gst.CLOCK_TIME_NONE)

        # Disconnect the decodebin element from the pipeline, set its
        # state to READY to to clear it.
        self._decbin.unlink(self._conv)
        self._decbin.set_state(self.Gst.State.READY)

        # Set a new file on the filesrc element, can only be done in the
        # READY state
        self._src.set_state(self.Gst.State.READY)
        self._src.set_property("location", py3_path(syspath(self._file.path)))

        self._decbin.link(self._conv)
        self._pipe.set_state(self.Gst.State.READY)

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
            audiofile = self._mod_audiotools.open(py3_path(syspath(item.path)))
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

    def compute_track_gain(self, items, target_level, peak):
        """Compute ReplayGain values for the requested items.

        :return list: list of :class:`Gain` objects
        """
        return [self._compute_track_gain(item, target_level) for item in items]

    def _with_target_level(self, gain, target_level):
        """Return `gain` relative to `target_level`.

        Assumes `gain` is relative to 89 db.
        """
        return gain + (target_level - 89)

    def _title_gain(self, rg, audiofile, target_level):
        """Get the gain result pair from PyAudioTools using the `ReplayGain`
        instance `rg` for the given `audiofile`.

        Wraps `rg.title_gain(audiofile.to_pcm())` and throws a
        `ReplayGainError` when the library fails.
        """
        try:
            # The method needs an audiotools.PCMReader instance that can
            # be obtained from an audiofile instance.
            gain, peak = rg.title_gain(audiofile.to_pcm())
        except ValueError as exc:
            # `audiotools.replaygain` can raise a `ValueError` if the sample
            # rate is incorrect.
            self._log.debug(u'error in rg.title_gain() call: {}', exc)
            raise ReplayGainError(u'audiotools audio data error')
        return self._with_target_level(gain, target_level), peak

    def _compute_track_gain(self, item, target_level):
        """Compute ReplayGain value for the requested item.

        :rtype: :class:`Gain`
        """
        audiofile = self.open_audio_file(item)
        rg = self.init_replaygain(audiofile, item)

        # Each call to title_gain on a ReplayGain object returns peak and gain
        # of the track.
        rg_track_gain, rg_track_peak = self._title_gain(
            rg, audiofile, target_level
        )

        self._log.debug(u'ReplayGain for track {0} - {1}: {2:.2f}, {3:.2f}',
                        item.artist, item.title, rg_track_gain, rg_track_peak)
        return Gain(gain=rg_track_gain, peak=rg_track_peak)

    def compute_album_gain(self, items, target_level, peak):
        """Compute ReplayGain values for the requested album and its items.

        :rtype: :class:`AlbumGain`
        """
        # The first item is taken and opened to get the sample rate to
        # initialize the replaygain object. The object is used for all the
        # tracks in the album to get the album values.
        item = list(items)[0]
        audiofile = self.open_audio_file(item)
        rg = self.init_replaygain(audiofile, item)

        track_gains = []
        for item in items:
            audiofile = self.open_audio_file(item)
            rg_track_gain, rg_track_peak = self._title_gain(
                rg, audiofile, target_level
            )
            track_gains.append(
                Gain(gain=rg_track_gain, peak=rg_track_peak)
            )
            self._log.debug(u'ReplayGain for track {0}: {1:.2f}, {2:.2f}',
                            item, rg_track_gain, rg_track_peak)

        # After getting the values for all tracks, it's possible to get the
        # album values.
        rg_album_gain, rg_album_peak = rg.album_gain()
        rg_album_gain = self._with_target_level(rg_album_gain, target_level)
        self._log.debug(u'ReplayGain for album {0}: {1:.2f}, {2:.2f}',
                        items[0].album, rg_album_gain, rg_album_peak)

        return AlbumGain(
            Gain(gain=rg_album_gain, peak=rg_album_peak),
            track_gains=track_gains
        )


class ExceptionWatcher(Thread):
    """Monitors a queue for exceptions asynchronously.
        Once an exception occurs, raise it and execute a callback.
    """

    def __init__(self, queue, callback):
        self._queue = queue
        self._callback = callback
        self._stopevent = Event()
        Thread.__init__(self)

    def run(self):
        while not self._stopevent.is_set():
            try:
                exc = self._queue.get_nowait()
                self._callback()
                six.reraise(exc[0], exc[1], exc[2])
            except queue.Empty:
                # No exceptions yet, loop back to check
                #  whether `_stopevent` is set
                pass

    def join(self, timeout=None):
        self._stopevent.set()
        Thread.join(self, timeout)


# Main plugin logic.

class ReplayGainPlugin(BeetsPlugin):
    """Provides ReplayGain analysis.
    """

    backends = {
        "command": CommandBackend,
        "gstreamer": GStreamerBackend,
        "audiotools": AudioToolsBackend,
        "ffmpeg": FfmpegBackend,
    }

    peak_methods = {
        "true": Peak.true,
        "sample": Peak.sample,
    }

    def __init__(self):
        super(ReplayGainPlugin, self).__init__()

        # default backend is 'command' for backward-compatibility.
        self.config.add({
            'overwrite': False,
            'auto': True,
            'backend': u'command',
            'threads': cpu_count(),
            'parallel_on_import': False,
            'per_disc': False,
            'peak': 'true',
            'targetlevel': 89,
            'r128': ['Opus'],
            'r128_targetlevel': lufs_to_db(-23),
        })

        self.overwrite = self.config['overwrite'].get(bool)
        self.per_disc = self.config['per_disc'].get(bool)

        # Remember which backend is used for CLI feedback
        self.backend_name = self.config['backend'].as_str()

        if self.backend_name not in self.backends:
            raise ui.UserError(
                u"Selected ReplayGain backend {0} is not supported. "
                u"Please select one of: {1}".format(
                    self.backend_name,
                    u', '.join(self.backends.keys())
                )
            )
        peak_method = self.config["peak"].as_str()
        if peak_method not in self.peak_methods:
            raise ui.UserError(
                u"Selected ReplayGain peak method {0} is not supported. "
                u"Please select one of: {1}".format(
                    peak_method,
                    u', '.join(self.peak_methods.keys())
                )
            )
        self._peak_method = self.peak_methods[peak_method]

        # On-import analysis.
        if self.config['auto']:
            self.register_listener('import_begin', self.import_begin)
            self.register_listener('import', self.import_end)
            self.import_stages = [self.imported]

        # Formats to use R128.
        self.r128_whitelist = self.config['r128'].as_str_seq()

        try:
            self.backend_instance = self.backends[self.backend_name](
                self.config, self._log
            )
        except (ReplayGainError, FatalReplayGainError) as e:
            raise ui.UserError(
                u'replaygain initialization failed: {0}'.format(e))

    def should_use_r128(self, item):
        """Checks the plugin setting to decide whether the calculation
        should be done using the EBU R128 standard and use R128_ tags instead.
        """
        return item.format in self.r128_whitelist

    def track_requires_gain(self, item):
        return self.overwrite or \
            (self.should_use_r128(item) and not item.r128_track_gain) or \
            (not self.should_use_r128(item) and
                (not item.rg_track_gain or not item.rg_track_peak))

    def album_requires_gain(self, album):
        # Skip calculating gain only when *all* files don't need
        # recalculation. This way, if any file among an album's tracks
        # needs recalculation, we still get an accurate album gain
        # value.
        return self.overwrite or \
            any([self.should_use_r128(item) and
                (not item.r128_track_gain or not item.r128_album_gain)
                for item in album.items()]) or \
            any([not self.should_use_r128(item) and
                (not item.rg_album_gain or not item.rg_album_peak)
                for item in album.items()])

    def _store(self, item):
        """Store an item to the database.
             When testing, item.store() sometimes fails non-destructively with
             sqlite.OperationalError.
             This method is here to be patched to a retry-once helper function
             in test_replaygain.py, so that it can still fail appropriately
             outside of these tests.
        """
        item.store()

    def store_track_gain(self, item, track_gain):
        item.rg_track_gain = track_gain.gain
        item.rg_track_peak = track_gain.peak
        self._store(item)
        self._log.debug(u'applied track gain {0} LU, peak {1} of FS',
                        item.rg_track_gain, item.rg_track_peak)

    def store_album_gain(self, item, album_gain):
        item.rg_album_gain = album_gain.gain
        item.rg_album_peak = album_gain.peak
        self._store(item)
        self._log.debug(u'applied album gain {0} LU, peak {1} of FS',
                        item.rg_album_gain, item.rg_album_peak)

    def store_track_r128_gain(self, item, track_gain):
        item.r128_track_gain = track_gain.gain
        self._store(item)

        self._log.debug(u'applied r128 track gain {0} LU',
                        item.r128_track_gain)

    def store_album_r128_gain(self, item, album_gain):
        item.r128_album_gain = album_gain.gain
        self._store(item)
        self._log.debug(u'applied r128 album gain {0} LU',
                        item.r128_album_gain)

    def tag_specific_values(self, items):
        """Return some tag specific values.

        Returns a tuple (store_track_gain, store_album_gain, target_level,
        peak_method).
        """
        if any([self.should_use_r128(item) for item in items]):
            store_track_gain = self.store_track_r128_gain
            store_album_gain = self.store_album_r128_gain
            target_level = self.config['r128_targetlevel'].as_number()
            peak = Peak.none  # R128_* tags do not store the track/album peak
        else:
            store_track_gain = self.store_track_gain
            store_album_gain = self.store_album_gain
            target_level = self.config['targetlevel'].as_number()
            peak = self._peak_method

        return store_track_gain, store_album_gain, target_level, peak

    def handle_album(self, album, write, force=False):
        """Compute album and track replay gain store it in all of the
        album's items.

        If ``write`` is truthy then ``item.write()`` is called for each
        item. If replay gain information is already present in all
        items, nothing is done.
        """
        if not force and not self.album_requires_gain(album):
            self._log.info(u'Skipping album {0}', album)
            return

        if (any([self.should_use_r128(item) for item in album.items()]) and not
                all(([self.should_use_r128(item) for item in album.items()]))):
            self._log.error(
                u"Cannot calculate gain for album {0} (incompatible formats)",
                album)
            return

        self._log.info(u'analyzing {0}', album)

        tag_vals = self.tag_specific_values(album.items())
        store_track_gain, store_album_gain, target_level, peak = tag_vals

        discs = dict()
        if self.per_disc:
            for item in album.items():
                if discs.get(item.disc) is None:
                    discs[item.disc] = []
                discs[item.disc].append(item)
        else:
            discs[1] = album.items()

        for discnumber, items in discs.items():
            def _store_album(album_gain):
                if not album_gain or not album_gain.album_gain \
                        or len(album_gain.track_gains) != len(items):
                    # In some cases, backends fail to produce a valid
                    # `album_gain` without throwing FatalReplayGainError
                    #  => raise non-fatal exception & continue
                    raise ReplayGainError(
                        u"ReplayGain backend `{}` failed "
                        u"for some tracks in album {}"
                        .format(self.backend_name, album)
                    )
                for item, track_gain in zip(items,
                                            album_gain.track_gains):
                    store_track_gain(item, track_gain)
                    store_album_gain(item, album_gain.album_gain)
                    if write:
                        item.try_write()
                    self._log.debug(u'done analyzing {0}', item)

            try:
                self._apply(
                    self.backend_instance.compute_album_gain, args=(),
                    kwds={
                        "items": [i for i in items],
                        "target_level": target_level,
                        "peak": peak
                    },
                    callback=_store_album
                )
            except ReplayGainError as e:
                self._log.info(u"ReplayGain error: {0}", e)
            except FatalReplayGainError as e:
                raise ui.UserError(
                    u"Fatal replay gain error: {0}".format(e))

    def handle_track(self, item, write, force=False):
        """Compute track replay gain and store it in the item.

        If ``write`` is truthy then ``item.write()`` is called to write
        the data to disk.  If replay gain information is already present
        in the item, nothing is done.
        """
        if not force and not self.track_requires_gain(item):
            self._log.info(u'Skipping track {0}', item)
            return

        tag_vals = self.tag_specific_values([item])
        store_track_gain, store_album_gain, target_level, peak = tag_vals

        def _store_track(track_gains):
            if not track_gains or len(track_gains) != 1:
                # In some cases, backends fail to produce a valid
                # `track_gains` without throwing FatalReplayGainError
                #  => raise non-fatal exception & continue
                raise ReplayGainError(
                    u"ReplayGain backend `{}` failed for track {}"
                    .format(self.backend_name, item)
                )

            store_track_gain(item, track_gains[0])
            if write:
                item.try_write()
            self._log.debug(u'done analyzing {0}', item)

        try:
            self._apply(
                self.backend_instance.compute_track_gain, args=(),
                kwds={
                    "items": [item],
                    "target_level": target_level,
                    "peak": peak,
                },
                callback=_store_track
            )
        except ReplayGainError as e:
            self._log.info(u"ReplayGain error: {0}", e)
        except FatalReplayGainError as e:
            raise ui.UserError(u"Fatal replay gain error: {0}".format(e))

    def _has_pool(self):
        """Check whether a `ThreadPool` is running instance in `self.pool`
        """
        if hasattr(self, 'pool'):
            if isinstance(self.pool, ThreadPool) and self.pool._state == RUN:
                return True
        return False

    def open_pool(self, threads):
        """Open a `ThreadPool` instance in `self.pool`
        """
        if not self._has_pool() and self.backend_instance.do_parallel:
            self.pool = ThreadPool(threads)
            self.exc_queue = queue.Queue()

            signal.signal(signal.SIGINT, self._interrupt)

            self.exc_watcher = ExceptionWatcher(
                self.exc_queue,      # threads push exceptions here
                self.terminate_pool  # abort once an exception occurs
            )
            self.exc_watcher.start()

    def _apply(self, func, args, kwds, callback):
        if self._has_pool():
            def catch_exc(func, exc_queue, log):
                """Wrapper to catch raised exceptions in threads
                """
                def wfunc(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except ReplayGainError as e:
                        log.info(e.args[0])  # log non-fatal exceptions
                    except Exception:
                        exc_queue.put(sys.exc_info())
                return wfunc

            # Wrap function and callback to catch exceptions
            func = catch_exc(func, self.exc_queue, self._log)
            callback = catch_exc(callback, self.exc_queue, self._log)

            self.pool.apply_async(func, args, kwds, callback)
        else:
            callback(func(*args, **kwds))

    def terminate_pool(self):
        """Terminate the `ThreadPool` instance in `self.pool`
            (e.g. stop execution in case of exception)
        """
        # Don't call self._as_pool() here,
        # self.pool._state may not be == RUN
        if hasattr(self, 'pool') and isinstance(self.pool, ThreadPool):
            self.pool.terminate()
            self.pool.join()
            # self.exc_watcher.join()

    def _interrupt(self, signal, frame):
        try:
            self._log.info('interrupted')
            self.terminate_pool()
            exit(0)
        except SystemExit:
            # Silence raised SystemExit ~ exit(0)
            pass

    def close_pool(self):
        """Close the `ThreadPool` instance in `self.pool` (if there is one)
        """
        if self._has_pool():
            self.pool.close()
            self.pool.join()
            self.exc_watcher.join()

    def import_begin(self, session):
        """Handle `import_begin` event -> open pool
        """
        threads = self.config['threads'].get(int)

        if self.config['parallel_on_import'] \
                and self.config['auto'] \
                and threads:
            self.open_pool(threads)

    def import_end(self, paths):
        """Handle `import` event -> close pool
        """
        self.close_pool()

    def imported(self, session, task):
        """Add replay gain info to items or albums of ``task``.
        """
        if self.config['auto']:
            if task.is_album:
                self.handle_album(
                    task.album,
                    self.config['auto'].get(bool),
                    self.config['overwrite'].get(bool)
                )
            else:
                self.handle_track(
                    task.item,
                    self.config['auto'].get(bool),
                    self.config['overwrite'].get(bool)
                )

    def commands(self):
        """Return the "replaygain" ui subcommand.
        """
        def func(lib, opts, args):
            try:
                write = ui.should_write(opts.write)
                force = opts.force

                # Bypass self.open_pool() if called with  `--threads 0`
                if opts.threads != 0:
                    threads = opts.threads or self.config['threads'].get(int)
                    self.open_pool(threads)

                if opts.album:
                    albums = lib.albums(ui.decargs(args))
                    self._log.info(
                        "Analyzing {} albums ~ {} backend..."
                        .format(len(albums), self.backend_name)
                    )
                    for album in albums:
                        self.handle_album(album, write, force)
                else:
                    items = lib.items(ui.decargs(args))
                    self._log.info(
                        "Analyzing {} tracks ~ {} backend..."
                        .format(len(items), self.backend_name)
                    )
                    for item in items:
                        self.handle_track(item, write, force)

                self.close_pool()
            except (SystemExit, KeyboardInterrupt):
                # Silence interrupt exceptions
                pass

        cmd = ui.Subcommand('replaygain', help=u'analyze for ReplayGain')
        cmd.parser.add_album_option()
        cmd.parser.add_option(
            "-t", "--threads", dest="threads", type=int,
            help=u'change the number of threads, \
            defaults to maximum available processors'
        )
        cmd.parser.add_option(
            "-f", "--force", dest="force", action="store_true", default=False,
            help=u"analyze all files, including those that "
            "already have ReplayGain metadata")
        cmd.parser.add_option(
            "-w", "--write", default=None, action="store_true",
            help=u"write new metadata to files' tags")
        cmd.parser.add_option(
            "-W", "--nowrite", dest="write", action="store_false",
            help=u"don't write metadata (opposite of -w)")
        cmd.func = func
        return [cmd]
