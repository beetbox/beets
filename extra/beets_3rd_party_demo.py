# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Kevin Dahlhausen
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

from beets import config
from beets import importer
from beets.ui import _open_library


class Beets(object):
    """a minimal wrapper for using beets in a 3rd party application
       as a music library."""

    class AutoImportSession(importer.ImportSession):
        "a minimal session class for importing that does not change files"

        def should_resume(self, path):
            return True

        def choose_match(self, task):
            return importer.action.ASIS

        def resolve_duplicate(self, task, found_duplicates):
            pass

        def choose_item(self, task):
            return importer.action.ASIS

    def __init__(self, music_library_file_name):
        """ music_library_file_name = full path and name of
            music database to use """
        "configure to keep music in place and do not auto-tag"
        config["import"]["autotag"] = False
        config["import"]["copy"] = False
        config["import"]["move"] = False
        config["import"]["write"] = False
        config["library"] = music_library_file_name
        config["threaded"] = True

        # create/open the the beets library
        self.lib = _open_library(config)

    def import_files(self, list_of_paths):
        """import/reimport music from the list of paths.
            Note: This may need some kind of mutex as I
                  do not know the ramifications of calling
                  it a second time if there are background
                  import threads still running.
        """
        query = None
        loghandler = None  # or log.handlers[0]
        self.session = Beets.AutoImportSession(self.lib, loghandler,
                                               list_of_paths, query)
        self.session.run()

    def query(self, query=None):
        """return list of items from the music DB that match the given query"""
        return self.lib.items(query)


if __name__ == "__main__":

    import os

    # this demo places music.db in same lib as this file and
    # imports music from <this dir>/Music
    path_of_this_file = os.path.dirname(__file__)
    MUSIC_DIR = os.path.join(path_of_this_file, "Music")
    LIBRARY_FILE_NAME = os.path.join(path_of_this_file, "music.db")

    def print_items(items, description):
        print("Results when querying for "+description)
        for item in items:
            print("   Title: {} by '{}' ".format(item.title, item.artist))
            print("      genre: {}".format(item.genre))
            print("      length: {}".format(item.length))
            print("      path: {}".format(item.path))
        print("")

    demo = Beets(LIBRARY_FILE_NAME)

    # import music - this demo does not move, copy or tag the files
    demo.import_files([MUSIC_DIR, ])

    # sample queries:
    items = demo.query()
    print_items(items, "all items")

    items = demo.query(["artist:heart,", "title:Hold", ])
    print_items(items, 'artist="heart" or title contains "Hold"')

    items = demo.query(["genre:Hard Rock"])
    print_items(items, 'genre = Hard Rock')
