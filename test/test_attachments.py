# This file is part of beets.
# Copyright 2014, Thomas Scholtes
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


import os
from tempfile import mkstemp
from _common import unittest
from helper import TestHelper

import beets.ui
from beets.plugins import BeetsPlugin
from beets.attachments import AttachmentFactory
from beets.library import Library, Album, Item


class AttachmentFactoryTest(unittest.TestCase):

    def setUp(self):
        self.lib = Library(':memory:')
        self.factory = AttachmentFactory(self.lib)

    def test_create_with_url_and_type(self):
        attachment = self.factory.create('/path/to/attachment', 'coverart')
        self.assertEqual(attachment.url, '/path/to/attachment')
        self.assertEqual(attachment.type, 'coverart')

    def test_create_sets_entity(self):
        album = Album()
        album.add(self.lib)
        attachment = self.factory.create('/path/to/attachment', 'coverart',
                                         entity=album)
        self.assertEqual(attachment.ref, album.id)
        self.assertEqual(attachment.ref_type, 'album')

    def test_create_populates_metadata(self):
        def collector(type, path):
            return {'mime': 'image/'}
        self.factory.register_collector(collector)

        attachment = self.factory.create('/path/to/attachment', 'coverart')
        self.assertEqual(attachment['mime'], 'image/')

    def test_find_all_attachments(self):
        self.factory.create('/path', 'atype').add()
        self.factory.create('/another_path', 'asecondtype').add()

        all_attachments = self.factory.find()
        self.assertEqual(len(all_attachments), 2)

        attachment = all_attachments.get()
        self.assertEqual(attachment.path, '/path')
        self.assertEqual(attachment.type, 'atype')


class EntityAttachmentsTest(unittest.TestCase):

    def setUp(self):
        self.lib = Library(':memory:')
        self.factory = AttachmentFactory(self.lib)

    def test_all_item_attachments(self):
        item = Item()
        item.add(self.lib)

        attachment = self.factory.create('/path/to/attachment',
                                         'coverart', item)
        attachment.add()

        self.assertItemsEqual(map(lambda a: a.id, item.attachments()),
                              [attachment.id])

    def test_all_album_attachments(self):
        album = Album()
        album.add(self.lib)

        attachment = self.factory.create('/path/to/attachment',
                                         'coverart', album)
        attachment.add()

        self.assertItemsEqual(map(lambda a: a.id, album.attachments()),
                              [attachment.id])


class AttachCommandTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.setup_log_attachment_plugin()
        self.tmp_files = []

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()
        for p in self.tmp_files:
            os.remove(p)

    def test_attach_to_album(self):
        album = Album(album='albumtitle')
        self.lib.add(album)

        attachment_path = self.mkstemp('.log')
        self.runcli('attach', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'log')

    def test_attach_to_album_and_move(self):
        self.skipTest('Not implemented')

    def test_file_relative_to_album_dir(self):
        self.skipTest('Not implemented')

    def test_attach_to_item(self):
        item = Item(title='tracktitle')
        self.lib.add(item)

        attachment_path = self.mkstemp('.log')
        self.runcli('attach', '--track', attachment_path, 'tracktitle')
        attachment = item.attachments().get()
        self.assertEqual(attachment.type, 'log')

    def test_attach_to_item_and_move(self):
        self.skipTest('Not implemented')

    def test_user_type(self):
        album = Album(album='albumtitle')
        self.lib.add(album)

        attachment_path = self.mkstemp()
        self.runcli('attach', '-t', 'customtype', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'customtype')

    def test_unknown_warning(self):
        self.skipTest('Not implemented')

    # Helpers

    def runcli(self, *args):
        beets.ui._raw_main(list(args), self.lib)

    def mkstemp(self, suffix=''):
        (handle, path) = mkstemp(suffix)
        os.close(handle)
        self.tmp_files.append(path)
        return path

    def setup_log_attachment_plugin(self):
        def log_discoverer(path):
            if path.endswith('.log'):
                return 'log'
        log_plugin = BeetsPlugin()
        log_plugin.attachment_discoverer = log_discoverer
        self.add_plugin(log_plugin)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
