# This file is part of beets.
# Copyright 2015, Adrian Sampson and Diego Moreda.
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)
import codecs

from mock import patch
from test._common import unittest
from test.helper import TestHelper, control_stdin


class ModifyFileMocker(object):
    """Helper for modifying a file, replacing or editing its contents. Used for
    mocking the calls to the external editor during testing."""

    def __init__(self, contents=None, replacements=None):
        """ `self.contents` and `self.replacements` are initalized here, in
        order to keep the rest of the functions of this class with the same
        signature as `EditPlugin.get_editor()`, making mocking easier.
            - `contents`: string with the contents of the file to be used for
            `overwrite_contents()`
            - `replacement`: dict with the in-place replacements to be used for
            `replace_contents()`, in the form {'previous string': 'new string'}

        TODO: check if it can be solved more elegantly with a decorator
        """
        self.contents = contents
        self.replacements = replacements
        self.action = self.overwrite_contents
        if replacements:
            self.action = self.replace_contents

    def overwrite_contents(self, filename):
        """Modify `filename`, replacing its contents with `self.contents`. If
        `self.contents` is empty, the file remains unchanged.
        """
        if self.contents:
            with codecs.open(filename, 'w', encoding='utf8') as f:
                f.write(self.contents)

    def replace_contents(self, filename):
        """Modify `filename`, reading its contents and replacing the strings
        specified in `self.replacements`.
        """
        with codecs.open(filename, 'r', encoding='utf8') as f:
            contents = f.read()
        for old, new_ in self.replacements.iteritems():
            contents = contents.replace(old, new_)
        with codecs.open(filename, 'w', encoding='utf8') as f:
            f.write(contents)


class EditCommandTest(unittest.TestCase, TestHelper):
    """ Black box tests for `beetsplug.edit`. Command line interaction is
    simulated using `test.helper.control_stdin()`, and yaml editing via an
    external editor is simulated using `ModifyFileMocker`.
    """
    ALBUM_COUNT = 1
    TRACK_COUNT = 10

    def setUp(self):
        self.setup_beets()
        self.load_plugins('edit')
        # make sure that we avoid invoking the editor except for making changes
        self.config['edit']['diff_method'] = ''
        # add an album, storing the original fields for comparison
        self.album = self.add_album_fixture(track_count=self.TRACK_COUNT)
        self.album_orig = {f: self.album[f] for f in self.album._fields}
        self.items_orig = [{f: item[f] for f in item._fields} for
                           item in self.album.items()]

        # keep track of write()s
        self.write_patcher = patch('beets.library.Item.write')
        self.mock_write = self.write_patcher.start()

    def tearDown(self):
        self.write_patcher.stop()
        self.teardown_beets()
        self.unload_plugins()

    def run_mocked_command(self, modify_file_args={}, stdin=[], args=[]):
        """Run the edit command, with mocked stdin and yaml writing, and
        passing `args` to `run_command`."""
        m = ModifyFileMocker(**modify_file_args)
        with patch('beetsplug.edit.edit', side_effect=m.action):
            with control_stdin('\n'.join(stdin)):
                self.run_command('edit', *args)

    def assertCounts(self, album_count=ALBUM_COUNT, track_count=TRACK_COUNT,
                     write_call_count=TRACK_COUNT, title_starts_with=''):
        """Several common assertions on Album, Track and call counts."""
        self.assertEqual(len(self.lib.albums()), album_count)
        self.assertEqual(len(self.lib.items()), track_count)
        self.assertEqual(self.mock_write.call_count, write_call_count)
        self.assertTrue(all(i.title.startswith(title_starts_with)
                            for i in self.lib.items()))

    def assertItemFieldsModified(self, library_items, items, fields=[]):
        """Assert that items in the library (`lib_items`) have different values
        on the specified `fields` (and *only* on those fields), compared to
        `items`.
        An empty `fields` list results in asserting that no modifications have
        been performed.
        """
        changed_fields = []
        for lib_item, item in zip(library_items, items):
            changed_fields.append([field for field in lib_item._fields
                                   if lib_item[field] != item[field]])
        self.assertTrue(all(diff_fields == fields for diff_fields in
                            changed_fields))

    def test_title_edit_discard(self):
        """Edit title for all items in the library, then discard changes-"""
        # edit titles
        self.run_mocked_command({'replacements': {u't\u00eftle':
                                                  u'modified t\u00eftle'}},
                                # Cancel.
                                ['c'])

        self.assertCounts(write_call_count=0,
                          title_starts_with=u't\u00eftle')
        self.assertItemFieldsModified(self.album.items(), self.items_orig, [])

    def test_title_edit_apply(self):
        """Edit title for all items in the library, then apply changes."""
        # edit titles
        self.run_mocked_command({'replacements': {u't\u00eftle':
                                                  u'modified t\u00eftle'}},
                                # Apply changes.
                                ['a'])

        self.assertCounts(write_call_count=self.TRACK_COUNT,
                          title_starts_with=u'modified t\u00eftle')
        self.assertItemFieldsModified(self.album.items(), self.items_orig,
                                      ['title'])

    def test_single_title_edit_apply(self):
        """Edit title for one item in the library, then apply changes."""
        # edit title
        self.run_mocked_command({'replacements': {u't\u00eftle 9':
                                                  u'modified t\u00eftle 9'}},
                                # Apply changes.
                                ['a'])

        self.assertCounts(write_call_count=1,)
        # no changes except on last item
        self.assertItemFieldsModified(list(self.album.items())[:-1],
                                      self.items_orig[:-1], [])
        self.assertEqual(list(self.album.items())[-1].title,
                         u'modified t\u00eftle 9')

    def test_noedit(self):
        """Do not edit anything."""
        # do not edit anything
        self.run_mocked_command({'contents': None},
                                # no stdin
                                [])

        self.assertCounts(write_call_count=0,
                          title_starts_with=u't\u00eftle')
        self.assertItemFieldsModified(self.album.items(), self.items_orig, [])

    def test_album_edit_apply(self):
        """Edit the album field for all items in the library, apply changes.
        By design, the album should not be updated.""
        """
        # edit album
        self.run_mocked_command({'replacements': {u'\u00e4lbum':
                                                  u'modified \u00e4lbum'}},
                                # Apply changes.
                                ['a'])

        self.assertCounts(write_call_count=self.TRACK_COUNT)
        self.assertItemFieldsModified(self.album.items(), self.items_orig,
                                      ['album'])
        # ensure album is *not* modified
        self.album.load()
        self.assertEqual(self.album.album, u'\u00e4lbum')

    def test_single_edit_add_field(self):
        """Edit the yaml file appending an extra field to the first item, then
        apply changes."""
        # append "foo: bar" to item with id == 1
        self.run_mocked_command({'replacements': {u"id: 1":
                                                  u"id: 1\nfoo: bar"}},
                                # Apply changes.
                                ['a'])

        self.assertEqual(self.lib.items('id:1')[0].foo, 'bar')
        self.assertCounts(write_call_count=1,
                          title_starts_with=u't\u00eftle')

    def test_a_album_edit_apply(self):
        """Album query (-a), edit album field, apply changes."""
        self.run_mocked_command({'replacements': {u'\u00e4lbum':
                                                  u'modified \u00e4lbum'}},
                                # Apply changes.
                                ['a'],
                                args=['-a'])

        self.album.load()
        self.assertCounts(write_call_count=self.TRACK_COUNT)
        self.assertEqual(self.album.album, u'modified \u00e4lbum')
        self.assertItemFieldsModified(self.album.items(), self.items_orig,
                                      ['album'])

    def test_a_albumartist_edit_apply(self):
        """Album query (-a), edit albumartist field, apply changes."""
        self.run_mocked_command({'replacements': {u'album artist':
                                                  u'modified album artist'}},
                                # Apply changes.
                                ['a'],
                                args=['-a'])

        self.album.load()
        self.assertCounts(write_call_count=self.TRACK_COUNT)
        self.assertEqual(self.album.albumartist, u'the modified album artist')
        self.assertItemFieldsModified(self.album.items(), self.items_orig,
                                      ['albumartist'])

    def test_malformed_yaml(self):
        """Edit the yaml file incorrectly (resulting in a malformed yaml
        document)."""
        # edit the yaml file to an invalid file
        self.run_mocked_command({'contents': '!MALFORMED'},
                                # Edit again to fix? No.
                                ['n'])

        self.assertCounts(write_call_count=0,
                          title_starts_with=u't\u00eftle')

    def test_invalid_yaml(self):
        """Edit the yaml file incorrectly (resulting in a well-formed but
        invalid yaml document)."""
        # edit the yaml file to an invalid file
        self.run_mocked_command({'contents': 'wellformed: yes, but invalid'},
                                # no stdin
                                [])

        self.assertCounts(write_call_count=0,
                          title_starts_with=u't\u00eftle')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
