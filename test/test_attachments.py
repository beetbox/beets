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
import itertools
from _common import unittest
from helper import TestHelper, capture_log, capture_stdout

import beets.ui
from beets.plugins import BeetsPlugin
from beets.attachments import AttachmentFactory, Attachment
from beets.library import Album, Item


class AttachmentTestHelper(TestHelper):
    # TODO Merge parts with TestHelper and refactor some stuff.

    def setup_beets(self):
        super(AttachmentTestHelper, self).setup_beets()
        self.set_path_template('${entity_prefix}${basename}')
        self.set_track_separator(' - ', ' ', '.')

    @property
    def factory(self):
        if not hasattr(self, '_factory'):
            self._factory = AttachmentFactory(self.lib)
        return self._factory

    def touch(self, path, dir=None, content=''):
        # TODO move into TestHelper
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

    def add_album(self, name='album name', touch=True, artist=None):
        """Add an album with one track to the library and create
        dummy track file.
        """
        album = Album(album=name, albumartist=artist)
        self.lib.add(album)
        item_path = os.path.join(self.lib.directory, name, 'track.mp3')
        if touch:
            self.touch(item_path)

        item = Item(album_id=album.id, path=item_path)
        self.lib.add(item)
        return album

    def add_item(self, title='The Title', artist='The Artist',
                 album='The Album', touch=True):
        """Add item to the library and create dummy file.
        """
        path = os.path.join(self.libdir, '{0}.mp3'.format(title))
        if touch:
            self.touch(path)
        item = Item(title=title, path=path, artist=artist, album=album)
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

    def add_album_attachment(self, path='att.ext', type='atype',
                             album='The Album', artist='The Artist'):
        album = self.add_album(name=album, artist=artist, touch=False)
        if not os.path.isabs(path):
            path = os.path.join(album.item_dir(), path)
        return self.factory.add(path, type, album)

    def add_item_attachment(self, path='att.ext', type='atype',
                            album='Album', artist='Artist', title='Title'):
        track = self.add_item(title=title, artist=artist,
                              album=album, touch=False)
        if not os.path.isabs(path):
            path = os.path.join(track.path, path)
        return self.factory.add(path, type, track)

    def add_attachment_plugin(self, ext, meta={}):
        def ext_detector(path):
            if path.endswith('.' + ext):
                return ext

        def collector(type, path):
            if type == ext:
                return meta

        plugin = BeetsPlugin()
        plugin.attachment_detector = ext_detector
        plugin.attachment_collector = collector
        self.add_plugin(plugin)

    def set_path_template(self, *templates):
        self.config['attachments']['paths'] = templates

    def set_track_separator(self, *separators):
        self.config['attachments']['track separators'] = list(separators)

    def runcli(self, *args):
        beets.ui._raw_main(list(args), self.lib)

    def cli_output(self, *args):
        with capture_stdout() as output:
            self.runcli(*args)
        return [l for l in output.getvalue().split('\n') if l]

    def libpath(self, *components):
        components = \
            itertools.chain(*map(lambda comp: comp.split('/'), components))
        return os.path.join(self.libdir, *components)


class AttachmentDocTest(unittest.TestCase, AttachmentTestHelper):
    """Tests for the guide of the attachment documentation.
    """

    def setUp(self):
        self.setup_beets()
        self.config['path_formats'] = {'default': '$album/$track $title'}

    def tearDown(self):
        self.teardown_beets()

    @unittest.skip
    def test_attache_single_file_with_type(self):
        self.add_album(name='Revolver')
        attachment_path = self.touch('cover.jpg')

        output = self.cli_output('attach', attachment_path, '--type',
                                 'cover', 'album:Revolver')
        self.assertIn("add cover attachment {0} to 'The Beatles - Revolver'"
                      .format(attachment_path), output)

        output = self.cli_output('attachls', 'type:cover', 'e:album:Revolver')
        self.assertIn('cover: {0}/Revolver/cover.jpg'
                      .format(self.libdir), output)

    def test_attache_single_file_with_type_and_path_config(self):
        self.config['attachments']['paths'] = [{
            'type': 'cover',
            'path': 'front.$ext',
        }]
        self.add_album(name='Revolver')
        attachment_path = self.touch('cover.jpg')

        self.runcli('attach', attachment_path, '--type',
                    'cover', 'album:Revolver')

        output = self.cli_output('attachls', 'type:cover', 'e:album:Revolver')
        self.assertIn('cover: {0}/Revolver/front.jpg'
                      .format(self.libdir), output)

    @unittest.skip
    def test_import_cover_and_booklet(self):
        importer = self.create_importer()
        album_dir = os.path.join(self.importer.paths[0], 'album 0')
        cover_path = self.touch(album_dir, 'cover.jpg')
        booklet_path = self.touch(album_dir, 'booklet.pdf')

        with capture_stdout() as output:
            importer.run()
        output = output.getValue().split('\n')
        self.assertIn("add cover attachment {0} to 'Artist - Album 0'"
                      .format(cover_path), output)
        self.assertIn("add booklet attachment {0} to 'Artist - Album 0'"
                      .format(booklet_path), output)

    def test_attach_import(self):
        self.config['attachments']['types'] = {'cover.jpg': 'cover'}

        album1 = self.add_album(name='Revolver', artist='The Beatles')
        album2 = self.add_album(name='Abbey Road', artist='The Beatles')
        cover_path1 = self.touch(os.path.join(album1.item_dir(), 'cover.jpg'))
        cover_path2 = self.touch(os.path.join(album2.item_dir(), 'cover.jpg'))

        output = self.cli_output('attach-import')
        self.assertIn("add cover attachment {0} to 'The Beatles - Revolver'"
                      .format(cover_path1), output)
        self.assertIn("add cover attachment {0} to 'The Beatles - Abbey Road'"
                      .format(cover_path2), output)

        album1.load()
        self.assertEqual(len(album1.attachments()), 1)
        album2.load()
        self.assertEqual(len(album2.attachments()), 1)


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
        self.config['attachments']['track separators'] = ['--']
        attachment = self.create_item_attachment(
            '/a.ext',
            track_path='/track.mp3'
        )
        self.assertEqual('/track--a.ext', attachment.destination)
        attachment.path = attachment.destination
        self.assertEqual('/track--a.ext', attachment.destination)


class AttachmentTest(unittest.TestCase, AttachmentTestHelper):
    """Test `attachment.move()` and `attachment.entity`.
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    # attachment.move()
    # TODO move attachments with same path

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
        self.touch(dest)

        dest_root, dest_ext = os.path.splitext(dest)
        dest_alternative = dest_root + '.1' + dest_ext

        with capture_log() as logs:
            attachment.move()

        self.assertEqual(dest_alternative,  attachment.path)
        self.assertTrue(os.path.isfile(attachment.path))
        self.assertTrue(os.path.isfile(attachment.destination))

        self.assertIn(
            'attachment destination already exists: {0}'.format(dest), logs
        )
        self.assertIn(
            'move attachment to {0}'.format(dest_alternative), logs
        )

    def test_move_overwrite(self):
        attachment_path = self.touch('a.jpg', content='JPEG')
        attachment = self.create_album_attachment(attachment_path)
        dest = attachment.destination
        self.touch(dest, content='NONJPEG')

        with capture_log() as logs:
            attachment.move(overwrite=True)

        with open(dest, 'r') as f:
            self.assertEqual(f.read(), 'JPEG')

        self.assertIn(
            'overwrite attachment destination {0}'.format(dest), logs
        )

    # attachment.entity()

    def test_set_entity(self):
        album = self.add_album()
        attachment = self.factory.create('/path/to/attachment', 'coverart')
        attachment.entity = album
        self.assertEqual(attachment.entity, album)

    def test_set_entity_and_add(self):
        album = self.add_album()
        attachment = self.factory.create('/path/to/attachment', 'coverart')
        attachment.entity = album
        attachment.add()

        attachment = self.factory.find().get()
        self.assertEqual(attachment.entity.id, album.id)

    def test_set_entity_and_store(self):
        album1 = self.add_album()
        self.factory.add('/path/to/attachment', 'coverart', album1)

        attachment = self.factory.find().get()
        album2 = self.add_album()
        attachment.entity = album2
        attachment.store()
        self.assertNotEqual(attachment.entity.id, album1.id)
        self.assertEqual(attachment.entity.id, album2.id)

    def test_set_entity_and_add_entity(self):
        album = Album(db=self.lib)
        attachment = self.factory.create('/path/to/attachment', 'coverart')
        attachment.entity = album
        album.add()
        attachment.add()

        self.assertEqual(attachment.ref, album.id)
        self.assertEqual(attachment.entity.id, album.id)


class AttachmentFactoryTest(unittest.TestCase, AttachmentTestHelper):
    """Tests the following methods of `AttachmentFactory`

    * factory.create() and meta data collectors
    * factory.detect() and type detectors (config and plugin)
    * factory.discover()
    * factory.basename()
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
        album = self.add_album()
        attachment = self.factory.create('/path/to/attachment', 'coverart',
                                         entity=album)
        self.assertEqual(attachment.entity, album)

    def test_create_populates_metadata(self):
        def collector(type, path):
            if type == 'coverart':
                return {'mime': 'image/'}
        self.factory.register_collector(collector)

        attachment = self.factory.create('/path/to/attachment', 'coverart')
        self.assertEqual(attachment['mime'], 'image/')

        attachment = self.factory.create('/path/to/attachment', 'noart')
        self.assertNotIn('mime', attachment)

    def test_create_retrieves_existing(self):
        item = self.add_item('track')
        attachment1 = self.factory.create('/path/to/a', 'coverart', item)
        attachment1.add()

        attachment2 = self.factory.create('/path/to/a', 'coverart', item)
        self.assertEqual(attachment1.id, attachment2.id)

    # factory.detect()

    def test_detect_plugin_types(self):
        def detector(path):
            return 'image'
        self.factory.register_detector(detector)

        attachments = list(self.factory.detect('/path/to/attachment'))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].type, 'image')

    # TODO add extended bash globs
    def test_detect_config_glob_types(self):
        self.config['attachments']['types'] = {
            '*.jpg': 'image'
        }

        attachments = list(self.factory.detect('/path/to/cover.jpg'))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].type, 'image')

        attachments = list(self.factory.detect('/path/to/cover.png'))
        self.assertEqual(len(attachments), 0)

    def test_detect_config_regexp_types(self):
        self.config['attachments']['types'] = {
            '/[abc]+.*\.(txt|md)/': 'xxx'
        }

        attachments = list(self.factory.detect('/path/to/aabbcc.md'))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].type, 'xxx')

        attachments = list(self.factory.detect('/path/to/aabbcc.mdx'))
        self.assertEqual(len(attachments), 0)

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

    # factory.basename()

    def test_item_basename(self):
        item = Item(path='/music/track.mp3')
        path = '/music/track.cover.jpg'
        self.assertEqual('cover.jpg', self.factory.basename(path, item))

    def test_item_nested_basename(self):
        item = Item(path='/music/track.mp3')
        path = '/music/track/covers/front.jpg'
        self.assertEqual('covers/front.jpg', self.factory.basename(path, item))

    def test_item_other_dir_basename(self):
        self.skipTest('not yet implemented')
        item = Item(path='/music/track.mp3')
        path = '/attachments/track.cover.jpg'
        self.assertEqual('cover.jpg', self.factory.basename(path, item))

    def test_album_basename(self):
        album = self.add_album()
        path = os.path.join(album.item_dir(), 'cover.jpg')
        self.assertEqual('cover.jpg', self.factory.basename(path, album))

    def test_album_nested_basename(self):
        album = self.add_album()
        basename = os.path.join('covers', 'front.jpg')
        path = os.path.join(album.item_dir(), 'covers', 'front.jpg')
        self.assertEqual(basename, self.factory.basename(path, album))

    def test_album_name_prefix_basename(self):
        self.skipTest('not yet implemented')
        album = self.add_album()
        album.album = 'The Album'
        album.albumartist = 'The Artist'
        path = '/attachments/the artist - the album - cover.jpg'
        self.assertEqual('cover.jpg', self.factory.basename(path, album))

    def test_item_not_related(self):
        item = Item(path='/music/track.mp3')
        path = '/attachments/y.cover.jpg'
        self.assertEqual('y.cover.jpg', self.factory.basename(path, item))

    def test_album_not_related(self):
        album = self.add_album()
        path = '/attachments/y.cover.jpg'
        self.assertEqual('y.cover.jpg', self.factory.basename(path, album))


class AttachmentQueryTest(unittest.TestCase, AttachmentTestHelper):

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    def test_all(self):
        self.add_item_attachment(type='a')
        self.add_album_attachment(type='b')
        attachments = self.factory.find()
        self.assertItemsEqual('ab', map(lambda a: a.type, attachments))

    def test_type_query(self):
        attachment = self.add_album_attachment(type='y')
        self.add_album_attachment(type='another')

        res = self.factory.parse_and_find('type:y')
        self.assertEqual(len(res), 1)
        self.assertEqual(res.get().id, attachment.id)

    def test_album_name_query(self):
        attachment = self.add_album_attachment(album='xxx')
        self.add_item_attachment(album='xxx')
        self.add_album_attachment(album='another')
        res = self.factory.parse_and_find('a:album:xxx')
        self.assertEqual(len(res), 1)
        self.assertEqual(res.get().id, attachment.id)

    def test_album_search_query(self):
        self.add_album_attachment(album='xxx')
        self.add_album_attachment(artist='xxx')
        self.add_album_attachment(album='another')
        res = self.factory.parse_and_find('a:xxx')
        self.assertEqual(len(res), 2)

    def test_entity_album_search(self):
        self.add_album_attachment(album='xxx')
        self.add_item_attachment(album='xxx')
        self.add_album_attachment(album='another')
        res = self.factory.parse_and_find('e:album:xxx')
        self.assertEqual(len(res), 2)


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
        item = self.add_item('a track')
        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', item),
            self.factory.add('/path/to/attachment', 'riplog', item)
        ]

        self.assertItemsEqual(map(lambda a: a.id, item.attachments()),
                              map(lambda a: a.id, attachments))

    def test_all_album_attachments(self):
        album = self.add_album()
        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', album),
            self.factory.add('/path/to/attachment', 'riplog', album)
        ]
        self.assertItemsEqual(map(lambda a: a.id, album.attachments()),
                              map(lambda a: a.id, attachments))

    def test_query_album_attachments(self):
        self.skipTest('Not implemented yet')

        album = self.add_album()
        attachments = [
            self.factory.add('/path/to/attachment', 'coverart', album),
            self.factory.add('/path/to/attachment', 'riplog', album)
        ]
        queried = album.attachments('type:riplog').get()
        self.assertEqual(queried.id, attachments[1].id)


class AttachmentImportTest(unittest.TestCase, AttachmentTestHelper):
    """Import process should discover and add attachments.

    Since the importer uses the `AttachmentFactory.discover()` method more
    comprehensive tests can be found in that test case.
    """

    def setUp(self):
        self.setup_beets()
        self.add_attachment_plugin('jpg', meta={'covertype': 'front'})
        self.importer = self.create_importer()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_add_album_attachment(self):
        album_dir = os.path.join(self.importer.paths[0], 'album 0')
        self.touch('cover.jpg', dir=album_dir)
        self.importer.run()
        album = self.lib.albums().get()
        self.assertEqual(len(album.attachments()), 1)

        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'jpg')
        self.assertEqual(attachment['covertype'], 'front')
        self.assertEqual(attachment.path,
                         os.path.join(album.item_dir(), 'cover.jpg'))

    def test_config_disable(self):
        self.config['import']['attachments'] = False
        album_dir = os.path.join(self.importer.paths[0], 'album 0')
        self.touch('cover.jpg', dir=album_dir)
        self.importer.run()
        album = self.lib.albums().get()
        self.assertEqual(len(album.attachments()), 0)

    def test_add_singleton_track_attachment(self):
        self.config['import']['singletons'] = True
        track_prefix = \
            os.path.join(self.importer.paths[0], 'album 0', 'track 0')
        self.touch(track_prefix + '.cover.jpg')
        self.importer.run()
        item = self.lib.items().get()

        self.assertEqual(len(item.attachments()), 1)
        attachment = item.attachments().get()
        self.assertEqual(attachment.type, 'jpg')
        self.assertEqual(attachment['covertype'], 'front')
        self.assertEqual(
            attachment.path,
            os.path.splitext(item.path)[0] + ' - cover.jpg'
        )

    # TODO interactive type input


class AttachCommandTest(unittest.TestCase, AttachmentTestHelper):
    """Tests the `beet attach FILE QUERY...` command
    """

    def setUp(self):
        self.setup_beets()
        self.add_attachment_plugin('log')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    # attach FILE ALBUM_QUERY

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

    def test_do_not_attach_existing(self):
        album = self.add_album('albumtitle')
        attachment_path = self.touch('attachment.log')

        self.runcli('attach', '--no-move', attachment_path, 'albumtitle')
        self.runcli('attach', '--no-move', attachment_path, 'albumtitle')
        self.assertEqual(len(list(album.attachments())), 1)

    def test_unknown_type_warning(self):
        album = self.add_album('albumtitle')
        attachment_path = self.touch('unkown')
        with capture_log() as logs:
            self.runcli('attach', attachment_path)

        self.assertIn('unknown attachment: {0}'.format(attachment_path), logs)
        self.assertIsNone(album.attachments().get())

    def test_interactive_type(self):
        self.skipTest('not implemented yet')

    # attach --track FILE ITEM_QUERY

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
    # TODO globs

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
            self.assertEqual(attachment.path,
                             os.path.join(album.item_dir(), 'inalbumdir.log'))

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

    def test_local_track_file_with_custom_separator(self):
        self.set_track_separator('XX', '||')
        item = self.add_item('song')
        prefix = os.path.splitext(item.path)[0]
        self.touch(prefix + '||rip.log')

        self.runcli('attach', '--track', '--local', 'rip.log')
        attachment = item.attachments().get()
        self.assertEqual(prefix + 'XXrip.log', attachment.path)

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

        attachment_types = map(lambda a: a.type, (album2.attachments()))
        self.assertItemsEqual(attachment_types, ['png', 'log'])

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
            attachment_types = map(lambda a: a.type, track.attachments())
            self.assertItemsEqual(['png', 'png', 'png', 'log', 'log'],
                                  attachment_types)

    # attach --type TYPE FILE QUERY

    def test_user_type(self):
        album = self.add_album('albumtitle')
        attachment_path = self.touch('a.custom')

        self.runcli('attach', '-t', 'customtype', attachment_path)
        attachment = album.attachments().get()
        self.assertEqual(attachment.type, 'customtype')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
