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


from _common import unittest

from beets.attachments import AttachmentFactory
from beets.library import Library, Album


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


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
