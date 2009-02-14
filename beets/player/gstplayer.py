#!/usr/bin/env python

"""A wrapper for the GStreamer Python bindings that exposes a simple
music player.
"""

import gst
import sys
import time
import gobject
import thread
import os
import copy

class GstPlayer(object):
    """A music player abstracting GStreamer's Playbin element.
    
    Create a player object, then call run() to start a thread with a
    runloop. Then call play_file to play music. Use player.playing
    to check whether music is currently playing.
    
    A basic play queue is also implemented (just a Python list,
    player.queue, whose last element is next to play). To use it,
    just call enqueue() and then play(). When a track finishes and
    another is available on the queue, it is played automatically.
    """
    
    def __init__(self, finished_callback=None):
        """Initialize a player.
        
        If a finished_callback is provided, it is called every time a
        track started with play_file finishes.

        Once the player has been created, call run() to begin the main
        runloop in a separate thread.
        """
        
        # Set up the Gstreamer player. From the pygst tutorial:
        # http://pygstdocs.berlios.de/pygst-tutorial/playbin.html
        self.player = gst.element_factory_make("playbin", "player")
        fakesink = gst.element_factory_make("fakesink", "fakesink")
        self.player.set_property("video-sink", fakesink)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._handle_message)
        
        # Set up our own stuff.
        self.playing = False
        self.finished_callback = finished_callback

    def _get_state(self):
        """Returns the current state flag of the playbin."""
        # gst's get_state function returns a 3-tuple; we just want the
        # status flag in position 1.
        return self.player.get_state()[1]
    
    def _handle_message(self, bus, message):
        """Callback for status updates from GStreamer."""
        if message.type == gst.MESSAGE_EOS:
            # file finished playing
            self.playing = False
            if self.finished_callback:
                self.finished_callback()

        elif message.type == gst.MESSAGE_ERROR:
            # error
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: " + str(err)
            self.playing = False

    def play_file(self, path):
        """Immediately begin playing the audio file at the given
        path.
        """
        self.player.set_state(gst.STATE_NULL)
        self.player.set_property("uri", "file://" + path)
        self.player.set_state(gst.STATE_PLAYING)
        self.playing = True

    def play(self):
        """If paused, resume playback."""
        if self._get_state() == gst.STATE_PAUSED:
            self.player.set_state(gst.STATE_PLAYING)
            self.playing = True
    
    def pause(self):
        """Pause playback."""
        self.player.set_state(gst.STATE_PAUSED)

    def stop(self):
        """Halt playback."""
        self.player.set_state(gst.STATE_NULL)

    def run(self):
        """Start a new thread for the player.
        
        Call this function before trying to play any music with
        play_file() or play().
        """
        # If we don't use the MainLoop, messages are never sent.
        gobject.threads_init()
        def start():
            loop = gobject.MainLoop()
            loop.run()
        thread.start_new_thread(start, ())

    def block(self):
        """Block until playing finishes."""
        while self.playing:
            time.sleep(1)


def play_simple(paths):
    """Play the files in paths in a straightforward way, without
    using the player's callback function.
    """
    p = GstPlayer()
    p.run()
    for path in paths:
        p.play_file(path)
        p.block()

def play_complicated(paths):
    """Play the files in the path one after the other by using the
    callback function to advance to the next song.
    """
    my_paths = copy.copy(paths)
    def next_song():
        my_paths.pop(0)
        p.play_file(my_paths[0])
    p = GstPlayer(next_song)
    p.run()
    p.play_file(my_paths[0])
    while my_paths:
        time.sleep(1)

if __name__ == '__main__':
    # A very simple command-line player. Just give it names of audio
    # files on the command line; these are all played in sequence.
    paths = [os.path.abspath(os.path.expanduser(p))
             for p in sys.argv[1:]]
    # play_simple(paths)
    play_complicated(paths)

