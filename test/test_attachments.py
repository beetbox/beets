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
from beets.attachments import AttachmentFactory, Attachment
from beets.library import Library, Album, Item


class AttachmentDestinationTest(unittest.TestCase, TestHelper):
    """Test the `attachment.destination` property.
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    def test_relative_to_album_prefix(self):
        self.set_path_template('${basename}')
        attachment = self.create_album_attachment('/path/attachment.ext')
        album_dir = attachment.entity.item_dir()
        self.assertEqual(attachment.destination,
                         os.path.join(album_dir, 'attachment.ext'))

    def test_relative_to_track_prefix(self):
        self.set_path_template('${basename}')
        attachment = self.create_item_attachment(
            '/r/attachment.ext',
            track_path='/the/track/path.mp3'
        )
        self.assertEqual('/the/track/path - attachment.ext',
                         attachment.destination)

    def test_libdir(self):
        self.set_path_template('${libdir}/here')
        attachment = self.create_album_attachment('/r/attachment.ext')
        self.assertEqual(attachment.destination,
                         '{0}/here'.format(self.lib.directory))

    def test_path_type_query(self):
        self.set_path_template(
            '/fallback',
            {
                'type': 'customtype',
                'path': '${type}.ext'
            }
        )
        attachment = self.create_item_attachment(
            '/r/attachment.ext',
            type='customtype',
            track_path='/the/track/path.mp3'
        )
        self.assertEqual('/the/track/path - customtype.ext',
                         attachment.destination)

        attachment = self.create_item_attachment(
            '/r/attachment.ext',
            type='anothertype',
            track_path='/the/track/path.mp3'
        )
        self.assertEqual('/fallback', attachment.destination)

    def test_flex_attr(self):
        self.set_path_template(
            '${covertype}.${ext}',
            {
                'covertype': 'front',
                'path': 'cover.${ext}'
            }
        )

        attachment = self.create_item_attachment(
            '/r/attachment.jpg',
            type='customtype',
            track_path='/the/track/path.mp3'
        )

        attachment['covertype'] = 'front'
        self.assertEqual('/the/track/path - cover.jpg',
                         attachment.destination)

        attachment['covertype'] = 'back'
        self.assertEqual('/the/track/path - back.jpg',
                         attachment.destination)

    def test_album_with_extension(self):
        self.set_path_template({'ext': 'jpg'})
        attachment = self.create_album_attachment('/path/attachment.ext')
        album = attachment.entity
        album.album = 'Album Name'
        album.albumartist = 'Album Artist'
        album.store()
        album_dir = attachment.entity.item_dir()
        self.assertEqual(attachment.destination,
                         '{0}/Album Artist - Album Name.jpg'
                         .format(album_dir))

    def test_item_with_extension(self):
        self.set_path_template({'ext': 'jpg'})
        attachment = self.create_item_attachment(
            '/path/attachment.ext',
            track_path='/the/track/path.mp3'
        )
        self.assertEqual(attachment.destination,
                         '/the/track/path.jpg')

    # Helper

    def set_path_template(self, *templates):
        self.config['attachment']['paths'] = templates

    def create_item_attachment(self, path, type='atype',
                               track_path='/track/path.mp3'):
        item = Item(path='/the/track/path.mp3')
        self.lib.add(item)
        return Attachment(db=self.lib, entity=item,
                          path=path, type=type)

    def create_album_attachment(self, path, type='type'):
        album = Album(album='album')
        self.lib.add(album)
        album_dir = os.path.join(self.lib.directory, album.album)
        os.mkdir(album_dir)

        # Make sure album.item_dir() returns a path
        item = Item(album_id=album.id, path=os.path.join(album_dir,
                                                         'track.mp3'))
        self.lib.add(item)

        return Attachment(db=self.lib, entity=album, path=path, type=type)


class AttachmentFactoryTest(unittest.TestCase):

    def setUp(self):
        self.lib = Library(':memory:')
        self.factory = AttachmentFactory(self.lib)

    def tearDown(self):
        self.lib._connection().close()
        del self.lib._connections

    def test_create_with_path_and_type(self):
        attachment = self.factory.create('/path/to/attachment', 'coverart')
        self.assertEqual(attachment.path, '/path/to/attachment')
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
        for p in self.tmp_files:
            os.remove(p)
        self.teardown_beets()
        self.unload_plugins()

    def test_attach_to_album(self):
        album = self.add_album('albumtitle')

        attachment_path = self.mkstemp('.log')
        self.runcli('attach', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'log')

    def test_attach_to_album_and_move(self):
        self.skipTest('Not implemented')

    def test_attach_to_album_and_copy(self):
        self.skipTest('Not implemented')

    def test_attach_to_album_and_not_move(self):
        self.skipTest('Not implemented')

    def test_file_relative_to_album_dir(self):
        album = self.add_album('albumtitle')

        attachment_path = os.path.join(album.item_dir(), 'inalbumdir.log')
        self.mkstemp(path=attachment_path)
        self.runcli('attach', '--local', 'inalbumdir.log', 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'log')

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
        album = self.add_album('albumtitle')

        attachment_path = self.mkstemp()
        self.runcli('attach', '-t', 'customtype',
                    attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'customtype')

    def test_unknown_warning(self):
        self.skipTest('Not implemented')

    # Helpers

    def runcli(self, *args):
        beets.ui._raw_main(list(args), self.lib)

    def mkstemp(self, suffix='', path=None):
        if path:
            path = path + suffix
            with open(path, 'a+') as f:
                f.write('')
        else:
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

    def add_album(self, name):
        album = Album(album=name)
        self.lib.add(album)
        album_dir = os.path.join(self.lib.directory, name)
        os.mkdir(album_dir)

        item = Item(album_id=album.id,
                    path=os.path.join(album_dir, 'track.mp3'))
        self.lib.add(item)
        return album


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
