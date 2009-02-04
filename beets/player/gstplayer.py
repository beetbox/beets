#!/usr/bin/env python

import gst
import sys
import time
import gobject
import thread
import os

class GstPlayer(object):
    def __init__(self):
        # set up the Gstreamer player
        self.player = gst.element_factory_make("playbin", "player")
        fakesink = gst.element_factory_make("fakesink", "fakesink")
        self.player.set_property("video-sink", fakesink)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._handle_message)
        
        # set up our own stuff
        self.playing = False
        self.queue = []

    def _get_state(self):
        return self.player.get_state()[1]
    
    def _handle_message(self, bus, message):
        if message.type == gst.MESSAGE_EOS:
            # file finished playing
            if self.queue:
                self.play_file(self.queue.pop())
            else:
                self.playing = False

        elif message.type == gst.MESSAGE_ERROR:
            # error
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: " + err
            self.playing = False

    def play_file(self, path):
        self.player.set_state(gst.STATE_NULL)
        self.player.set_property("uri", "file://" + path)
        self.player.set_state(gst.STATE_PLAYING)
        self.playing = True

    def play(self):
        if self._get_state() == gst.STATE_PAUSED:
            self.player.set_state(gst.STATE_PLAYING)
            self.playing = True
        else:
            # presumably, nothing is playing
            self.play_file(self.queue.pop())
    
    def pause(self):
        self.player.set_state(gst.STATE_PAUSED)
        self.playing = False

    def enqueue(self, path):
        self.queue[0:0] = [path] # push to front

    def run(self):
        gobject.threads_init()
        def start():
            loop = gobject.MainLoop()
            loop.run()
        thread.start_new_thread(start, ())

    def block(self):
        """Block until we stop playing."""
        while self.playing:
            time.sleep(1)

if __name__ == '__main__':
    path = sys.argv[1]
    p = GstPlayer()
    for path in sys.argv[1:]:
        p.enqueue(os.path.abspath(os.path.expanduser(path)))
    p.run()
    p.play()
    p.block()

