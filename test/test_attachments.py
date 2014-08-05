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
from _common import unittest
from helper import TestHelper, capture_log

import beets.ui
from beets.plugins import BeetsPlugin
from beets.attachments import AttachmentFactory, Attachment
from beets.library import Album, Item


class AttachmentTestHelper(TestHelper):
    # TODO Merge parts with TestHelper and refactor some stuff.

    def setup_beets(self):
        super(AttachmentTestHelper, self).setup_beets()
        # TODO this comes into default config
        self.config['attachment']['paths'] = ['${entity_prefix}${basename}']
        self.config['attachment']['track separators'] = \
            [' - ', ' ', '-', '_', '.', os.sep]

    @property
    def factory(self):
        if not hasattr(self, '_factory'):
            self._factory = AttachmentFactory(self.lib)
        return self._factory

    def touch(self, path, dir=None, content=''):
        if dir:
            path = os.path.join(dir, path)

        if not os.path.isabs(path):
            path = os.path.join(self.temp_dir, path)

        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)

        with open(path, 'a+') as f:
            f.write(content)
        return path

    def add_album(self, name='album name', touch=True):
        """Add an album with one track to the library and create
        dummy track file.
        """
        album = Album(album=name)
        self.lib.add(album)
        item_path = os.path.join(self.lib.directory, name, 'track.mp3')
        self.touch(item_path)

        item = Item(album_id=album.id, path=item_path)
        self.lib.add(item)
        return album

    def add_item(self, title):
        """Add item to the library and create dummy file.
        """
        path = os.path.join(self.libdir, '{0}.mp3'.format(title))
        self.touch(path)
        item = Item(title=title, path=path)
        self.lib.add(item)
        return item

    def create_item_attachment(self, path, type='atype',
                               track_path='/track/path.mp3'):
        item = Item(path=track_path)
        self.lib.add(item)
        return Attachment(db=self.lib, entity=item,
                          path=path, type=type)

    def create_album_attachment(self, path, type='type'):
        album = self.add_album()
        attachment = Attachment(db=self.lib, entity=album,
                                path=path, type=type)
        self.lib.add(attachment)
        return attachment

    def add_attachment_plugin(self, ext, meta={}):
        def ext_detector(path):
            if path.endswith('.' + ext):
                return ext
        def collector(type, path):
            if type == ext:
                return meta
        log_plugin = BeetsPlugin()
        log_plugin.attachment_detector = ext_detector
        log_plugin.attachment_collector = collector
        self.add_plugin(log_plugin)

    def runcli(self, *args):
        beets.ui._raw_main(list(args), self.lib)


class AttachmentDestinationTest(unittest.TestCase, AttachmentTestHelper):
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

    def test_item_basename(self):
        self.set_path_template('$basename')
        self.config['attachment']['track separators'] = ['--']
        attachment = self.create_item_attachment(
            '/a.ext',
            track_path='/track.mp3'
        )
        self.assertEqual('/track--a.ext', attachment.destination)
        attachment.path = attachment.destination
        self.assertEqual('/track--a.ext', attachment.destination)

    # Helper

    def set_path_template(self, *templates):
        self.config['attachment']['paths'] = templates


class AttachmentTest(unittest.TestCase, AttachmentTestHelper):
    """Test `attachment.move()`.
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    def test_move(self):
        attachment = self.create_album_attachment(self.touch('a'))
        original_path = attachment.path

        self.assertNotEqual(attachment.destination, original_path)
        self.assertTrue(os.path.isfile(original_path))
        attachment.move()

        self.assertEqual(attachment.destination, attachment.path)
        self.assertTrue(os.path.isfile(attachment.path))
        self.assertFalse(os.path.exists(original_path))

    def test_copy(self):
        attachment = self.create_album_attachment(self.touch('a'))
        original_path = attachment.path

        self.assertNotEqual(attachment.destination, original_path)
        self.assertTrue(os.path.isfile(original_path))
        attachment.move(copy=True)

        self.assertEqual(attachment.destination, attachment.path)
        self.assertTrue(os.path.isfile(attachment.path))
        self.assertTrue(os.path.isfile(original_path))

    def test_move_dest_exists(self):
        attachment = self.create_album_attachment(self.touch('a.jpg'))
        dest = attachment.destination
        dest_root, dest_ext = os.path.splitext(dest)
        self.touch(dest)

        # TODO test log warning
        attachment.move()

        self.assertEqual(dest_root + '.1' + dest_ext, attachment.path)
        self.assertTrue(os.path.isfile(attachment.path))
        self.assertTrue(os.path.isfile(attachment.destination))

    def test_move_overwrite(self):
        attachment_path = self.touch('a.jpg', content='JPEG')
        attachment = self.create_album_attachment(attachment_path)
        self.touch(attachment.destination, content='NONJPEG')

        # TODO test log warning
        attachment.move(overwrite=True)

        with open(attachment.destination, 'r') as f:
            self.assertEqual(f.read(), 'JPEG')


class AttachmentFactoryTest(unittest.TestCase, AttachmentTestHelper):
    """Tests the following methods of `AttachmentFactory`

    * factory.create() and meta data collectors
    * factory.detect() and type detectors (config and plugin)
    * factory.discover()
    * factory.find()
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    # factory.create()

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
        self.assertEqual(attachment.entity.id, album.id)

    def test_create_populates_metadata(self):
        def collector(type, path):
            if type == 'coverart':
                return {'mime': 'image/'}
        self.factory.register_collector(collector)

        attachment = self.factory.create('/path/to/attachment', 'coverart')
        self.assertEqual(attachment['mime'], 'image/')

        attachment = self.factory.create('/path/to/attachment', 'noart')
        self.assertNotIn('mime', attachment)

    # factory.detect()

    def test_detect_plugin_types(self):
        def detector(path):
            return 'image'
        self.factory.register_detector(detector)

        attachments = list(self.factory.detect('/path/to/attachment'))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].type, 'image')

    def test_detect_config_types(self):
        self.config['attachments']['types'] = {
            '.*\.jpg': 'image'
        }

        attachments = list(self.factory.detect('/path/to/cover.jpg'))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].type, 'image')

        attachments = list(self.factory.detect('/path/to/cover.png'))
        self.assertEqual(len(attachments), 0)

    def test_detect_multiple_types(self):
        self.factory.register_detector(lambda _: 'a')
        self.factory.register_detector(lambda _: 'b')
        self.config['attachments']['types'] = {
            '.*\.jpg$': 'c',
            '.*/cover.jpg': 'd'
        }
        attachments = list(self.factory.detect('/path/to/cover.jpg'))
        self.assertItemsEqual(map(lambda a: a.type, attachments), 'abcd')

    # factory.discover(album)

    def test_discover_album(self):
        album = self.add_album()
        attachment_path = self.touch('cover.jpg', dir=album.item_dir())

        discovered = self.factory.discover(album)
        self.assertEqual([attachment_path], discovered)

    def test_discover_album_local(self):
        album = self.add_album()
        attachment_path = self.touch('cover.jpg', dir=album.item_dir())

        discovered = self.factory.discover(album, 'cover.jpg')
        self.assertEqual([attachment_path], discovered)

    # factory.find()
    # TODO extend

    def test_find_all_attachments(self):
        self.factory.create('/path', 'atype').add()
        self.factory.create('/another_path', 'asecondtype').add()

        all_attachments = self.factory.find()
        self.assertEqual(len(all_attachments), 2)

        attachment = all_attachments.get()
        self.assertEqual(attachment.path, '/path')
        self.assertEqual(attachment.type, 'atype')


class EntityAttachmentsTest(unittest.TestCase, AttachmentTestHelper):
    """Test attachment queries on entities.

    - `item.attachments()`
    - `album.attachments()`
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    def test_all_item_attachments(self):
        item = Item()
        item.add(self.lib)

        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', item),
            self.factory.add('/path/to/attachment', 'riplog', item)
        ]

        self.assertItemsEqual(map(lambda a: a.id, item.attachments()),
                              map(lambda a: a.id, attachments))

    def test_all_album_attachments(self):
        album = Album()
        album.add(self.lib)

        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', album),
            self.factory.add('/path/to/attachment', 'riplog', album)
        ]
        self.assertItemsEqual(map(lambda a: a.id, album.attachments()),
                              map(lambda a: a.id, attachments))

    def test_query_album_attachments(self):
        self.skipTest('Not implemented yet')
        album = Album()
        album.add(self.lib)

        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', album),
            self.factory.add('/path/to/attachment', 'riplog', album)
        ]
        queried = album.attachments('type:riplog').get()
        self.assertEqual(queried.id, attachments[1].id)


class AttachCommandTest(unittest.TestCase, AttachmentTestHelper):
    """Tests the `beet attach FILE QUERY...` command
    """

    def setUp(self):
        self.setup_beets()
        self.add_attachment_plugin('log')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_attach_to_album(self):
        album = self.add_album('albumtitle')

        attachment_path = self.touch('attachment.log')
        self.runcli('attach', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'log')

    def test_attach_to_album_and_move(self):
        album = self.add_album('albumtitle')

        attachment_path = self.touch('attachment.log')
        dest = os.path.join(album.item_dir(), 'attachment.log')
        self.assertFalse(os.path.isfile(dest))

        self.runcli('attach', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.path, dest)
        self.assertTrue(os.path.isfile(dest))

    def test_attach_to_album_and_copy(self):
        album = self.add_album('albumtitle')

        attachment_path = self.touch('attachment.log')
        dest = os.path.join(album.item_dir(), 'attachment.log')

        self.runcli('attach', '--copy', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.path, dest)
        self.assertTrue(os.path.isfile(attachment_path))
        self.assertTrue(os.path.isfile(dest))

    def test_attach_to_album_and_not_move(self):
        album = self.add_album('albumtitle')

        attachment_path = self.touch('attachment.log')

        self.runcli('attach', '--no-move', attachment_path, 'albumtitle')
        attachment = album.attachments().get()
        self.assertEqual(attachment.path, attachment_path)

    def test_attach_to_item(self):
        item = self.add_item(title='tracktitle')
        attachment_path = self.touch('attachment.log')

        self.runcli('attach', '--track', attachment_path, 'tracktitle')
        attachment = item.attachments().get()
        self.assertEqual(attachment.type, 'log')

    def test_attach_to_item_and_move(self):
        item = self.add_item(title='tracktitle')
        attachment_path = self.touch('attachment.log')

        dest = os.path.splitext(item.path)[0] + ' - ' + 'attachment.log'
        self.assertFalse(os.path.isfile(dest))

        self.runcli('attach', '--track', attachment_path, 'tracktitle')
        attachment = item.attachments().get()
        self.assertEqual(attachment.path, dest)
        self.assertTrue(os.path.isfile(dest))

    # attach --local FILE ALBUM_QUERY

    def test_local_album_file(self):
        albums = [self.add_album('album 1'), self.add_album('album 2')]
        for album in albums:
            self.touch('inalbumdir.log', dir=album.item_dir())
            self.touch('dontinclude.log', dir=album.item_dir())

        self.runcli('attach', '--local', 'inalbumdir.log')

        for album in albums:
            self.assertEqual(len(list(album.attachments())), 1)
            attachment = album.attachments().get()
            self.assertEqual(attachment.type, 'log')

    # attach --track --local FILE ITEM_QUERY

    def test_local_track_file(self):
        item1 = self.add_item('song 1')
        prefix = os.path.splitext(item1.path)[0]
        self.touch(prefix + ' rip.log')

        item2 = self.add_item('song 2')
        prefix = os.path.splitext(item2.path)[0]
        self.touch(prefix + ' - rip.log')
        self.touch(prefix + ' - no.log')

        item3 = self.add_item('song 3')
        prefix = os.path.splitext(item3.path)[0]
        self.touch(prefix + ' - no.log')

        self.runcli('attach', '--track', '--local', 'rip.log')

        self.assertEqual(len(list(item1.attachments())), 1)
        self.assertEqual(len(list(item2.attachments())), 1)
        self.assertEqual(len(list(item3.attachments())), 0)

    def test_local_track_file_extenstion(self):
        item = self.add_item('song')
        prefix = os.path.splitext(item.path)[0]
        self.touch(prefix + '.log')

        self.runcli('attach', '--track', '--local', '.log')

        self.assertEqual(len(list(item.attachments())), 1)

    # attach --discover ALBUM_QUERY

    def test_discover_in_album_dir(self):
        self.add_attachment_plugin('png')

        album1 = self.add_album('album 1')
        self.touch('cover.png', dir=album1.item_dir())

        album2 = self.add_album('album 2')
        self.touch('cover.png', dir=album2.item_dir())
        self.touch('subfolder/rip.log', dir=album2.item_dir())

        self.runcli('attach', '--discover')

        attachments1 = list(album1.attachments())
        self.assertEqual(len(attachments1), 1)
        self.assertEqual(attachments1[0].type, 'png')

        attachments2 = list(album2.attachments())
        self.assertEqual(len(attachments2), 2)
        self.assertItemsEqual(map(lambda a: a.type, attachments2),
                              ['png', 'log'])

    # attach --discover --track ITEM_QUERY

    def test_discover_track_files(self):
        self.add_attachment_plugin('png')

        tracks = [self.add_item('track 1'), self.add_item('track 2')]
        for track in tracks:
            root = os.path.splitext(track.path)[0]
            self.touch(root + '.log')
            self.touch(root + '- a.log')
            self.touch(root + ' b.png')
            self.touch(root + '-c.png')
            self.touch('d.png', dir=root)

        self.runcli('attach', '--discover', '--track')

        for track in tracks:
            self.assertEqual(len(list(track.attachments())), 5)
            attachment_types = map(lambda a: a.type, list(track.attachments()))
            self.assertItemsEqual(['png', 'png', 'png', 'log', 'log'],
                                  attachment_types)

    # attach --type TYPE QUERY

    def test_user_type(self):
        album = self.add_album('albumtitle')
        attachment_path = self.touch('a.custom')

        self.runcli('attach', '-t', 'customtype', attachment_path)
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'customtype')

    def test_unknown_type_warning(self):
        album = self.add_album('albumtitle')
        attachment_path = self.touch('unkown')
        with capture_log() as logs:
            self.runcli('attach', attachment_path)

        self.assertIn('unknown attachment: {0}'.format(attachment_path), logs)
        self.assertIsNone(album.attachments().get())

    def test_interactive_type(self):
        self.skipTest('not implemented yet')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
