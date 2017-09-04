.. _third_party:

Using Beets in Third-Party Applications
---------------------------------------

Beets can be used as music library for other applications.  Here is a simple example.

First a few imports and the start of a class definition::

    from beets import config
    from beets import importer
    from beets.ui import _open_library

    class BeetsWrapper(object):
        """a minimal wrapper for using beets in a 3rd-party
           application as a music library."""


Next, define a class that directs beets on how to handle the various options when
importing files.  This example uses an inner class that is configured to import
everything without asking questions::

        class AutoImportSession(importer.ImportSession):
            """a minimal session class for importing
               that does not change files"""

            def should_resume(self, path):
                return True

            def choose_match(self, task):
                return importer.action.ASIS

            def resolve_duplicate(self, task, found_duplicates):
                pass

            def choose_item(self, task):
                return importer.action.ASIS

We pass in the full path and name of the beets library file and create a
programmatic beets configuration designed to have beets treat the files
on disk as is with no copying or tagging::

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

Importing files into beets is handled by passing this function a list of paths to search::

        def import_files(self, list_of_paths):
            """import/reimport music from the list of paths.
                Note: This may need some kind of mutex as I
                      do not know the ramifications of calling
                      it a second time if there are background
                      import threads still running.
            """
            query = None
            loghandler = None  # or log.handlers[0]
            self.session = BeetsWrapper.AutoImportSession(self.lib,
                 loghandler, list_of_paths, query)
            self.session.run()

Queries are passed-through to beets itself::

        def query(self, query=None):
            """return list of items from the music DB that
               match the given query"""
            return self.lib.items(query)


And a short demonstration showing how this class might be used.  The demo
assumes there is a directory under it named *Music* that contains music
files::

    if __name__ == "__main__":

        import os

        # this demo places music.db in same lib as this file and
        # imports music from <this dir>/Music

        path_of_this_file = os.path.dirname(__file__)
        MUSIC_DIR = os.path.join(path_of_this_file, "Music")
        LIBRARY_FILE_NAME = os.path.join(path_of_this_file,
            "music.db")

        def print_items(items, description):
            print("Results when querying for "+description)
            for item in items:
                print("   Title: {} by '{}' ".format(item.title,
                                                     item.artist))
                print("      genre: {}".format(item.genre))
                print("      length: {}".format(item.length))
                print("      path: {}".format(item.path))
            print("")

        demo = BeetsWrapper(LIBRARY_FILE_NAME)

        #import music-this demo does not move, copy or tag the files
        demo.import_files([MUSIC_DIR, ])

        # sample queries:
        items = demo.query()
        print_items(items, "all items")

        items = demo.query(["artist:heart,", "title:Hold", ])
        print_items(items, 'artist="heart" or title contains "Hold"')

        items = demo.query(["genre:Hard Rock"])
        print_items(items, 'genre = Hard Rock')

The full example is located in `this gist <https://gist.github.com/kdahlhaus/7ec0bd7737d43eab2b82c02f6e4c6692>`_.
