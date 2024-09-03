
# # plugin = SpotifyCustomPlugin()
# ========================================================================================
# ########################################################################################
# ========================================================================================

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Item
import logging
from typing import List, Dict
import datetime
import re
from beets import config
from beets.dbcore.types import String
from beets.dbcore import types
import sqlite3

# 1. add columns if necessary
# 2. add _fields with correct types
# 3. add to lib with lib.add(item)
# 4. store item with i.store()




class TestPlugin(BeetsPlugin):

    def __init__(self):
        super(TestPlugin, self).__init__()

        self._log = logging.getLogger('beets.test')

        # item_types = {
        #     "main_artist": types.STRING
        # }

        # # self.config.add(
        # #     {
        # #         "item_types": item_types
        # #     }
        # # )

        # self.template_fields = item_types

        self.test_command = Subcommand('test', help='Retrieve all playlists and their tracks')
        self.test_command.func = self.test_func
        
        self.register_listener('library_opened', self.setup)

    def setup(self, lib):
        self.lib = lib
        columns = [("main_artist", "TEXT")]

        with self.lib.transaction() as tx:
            # Add columns that don't exist
            for column_name, data_type in columns:
                try:
                    tx.query(f"ALTER TABLE items ADD COLUMN {column_name} {data_type};")
                    print(f"Added column {column_name} of type {data_type}")
                except sqlite3.OperationalError:
                    print(f"column {column_name} already exists")

        # print(q)
        return

    def commands(self):
        return [self.test_command]
    
    # GET PLAYLIST INFO FROM API
    
    def test_func(self, lib, opts, args):
        i = Item(
            title="Test Title",
            artist="Test Artist",
            album="Test Album",
            length=300,  # duration in seconds
            format="MP3",
            main_artist="Test Main Artist"
        )


        for k, v in self.config['item_types'].items():
            i._fields[k] = types.STRING


        lib.add(i)

        i['main_artist'] = 'hihihihi'
        # i.store()
        i.store(fields=['main_artist'])

        return