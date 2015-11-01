# This file is part of beets.
# Copyright 2015, Marc Wiedermann <marcwiedermann@posteo.de>.
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
"""Add tracks to playlists on import."""

from beets.plugins import BeetsPlugin
from glob import glob
import os


class Playlister(BeetsPlugin):

    """
    Adding imported tracks to a set of playlists.

    Currently only works if items are moved or copied to the library.
    """

    def __init__(self):
        """Initialize an instance of class Playlister."""
        super(Playlister, self).__init__()

        self.set_options()
        if not os.path.exists(self._folder):
            os.makedirs(self._folder)

        self._interrupt_all = False

        self.register_listener('item_copied', self.adding)
        self.register_listener('item_moved', self.adding)

    def set_options(self):
        """Set options from the config.yaml file."""
        if "playlistfolder" not in self.config.keys():
            self._folder = os.path.expanduser("~/Playlists/")
        else:
            folder = self.config["playlistfolder"].get()
            if folder[-1] != "/":
                folder += "/"
            self._folder = os.path.expanduser(folder)

        if "mode" not in self.config.keys():
            self._mode = "absolute"
        elif self.config["mode"].get() in ["absolute", "relative"]:
            self._mode = self.config["mode"].get()
        else:
            raise ValueError(self.config["mode"].get()+" is not a valid "
                             "choice for option 'mode' in plugin playlister")

    def adding(self, item, source, destination):
        """Ask the user which playlists the tracks should be added to."""
        if self._interrupt_all:
            return

        playlist = raw_input("Add track "+item.title+" to playlist(s)? "
                             "[Y]es/No/no to All ").lower()

        if playlist == "y" or playlist == "" or playlist == "yes":
            dic = self.list_playlists()
            lists = raw_input("Enter comma-separated list of "
                              "indices of playlists and/or names of new "
                              "playlists (empty cancels): ")

            if lists != "":
                items = lists.split(",")
                items = [i.lstrip().rstrip() for i in items]
                if self._mode == "relative":
                    destination = self.get_relative_path(destination)

                for i in items:
                    if i in dic.keys():
                        self.append(dic[i], destination)
                    else:
                        self.append(i, destination)

        elif playlist == "a" or playlist == "no to all":
            self._interrupt_all = True

        elif playlist == "n" or playlist == "no":
            return

    def get_relative_path(self, destination):
        """Get the relative path between library and the playlist folder.

        This is particularly useful when working across mutliple operating
        systems.
        """
        rel_path = os.path.relpath(destination, self._folder)
        return rel_path

    def append(self, pl_name, destination):
        """Add current track to selected playlist."""
        print "Adding "+destination.split("/")[-1]+" to playlist: "+pl_name
        with open(self._folder+pl_name+".m3u", "a") as pls:
            pls.write(destination+"\n")

    def list_playlists(self):
        """Read and list all playlists in the playlist folder."""
        all_playlists = glob(self._folder + "*.m3u")
        dic = {}
        for i, pls in enumerate(sorted(all_playlists)):
            print "["+str(i)+"] "+pls.split("/")[-1][:-4]
            dic[str(i)] = pls.split("/")[-1][:-4]
        return dic
