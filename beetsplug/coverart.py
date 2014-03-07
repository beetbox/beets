# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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


COVERTYPE = enum([
    'front',
    'back',
    # TODO extend. The ID3v2 types [1] might be a good starting point,
    # but I find them a bit convoluted. MusicBrainz [2] is also a good
    # source.
    #
    # [1]: http://en.wikipedia.org/wiki/ID3#ID3v2_Embedded_Image_Extension
    # [2]: http://musicbrainz.org/doc/Cover_Art/Types
], name='COVERTYPE')
"""Enumeration of known types of cover art.

The string representation is stored in the 'covertype' metadata field of
an attachment.
"""


class CoverArtPlugin(BeetsPlugin):
    """Registers ``coverart`` attachment type and command.
    """

    def attachment_commands(self):
        return [CoverArtCommand]

    def attachment_discover(self, path):
        # FIXME mock code, simpler to check file extension
        mime_type = get_mime_type_from_file(path)
        if mime_type.startswith('image/'):
            return 'coverart'

    def attachment_collect(self, type, path):
        if type != 'coverart':
            return

        # FIXME mock code
        metadata = {}
        if basename(path).startwith('front'):
            metadata['covertype'] = 'front'
        elif basenmae(path).startswith('back'):
            metadata['covertype'] = 'back'

        width, height = get_image_resolution(path)
        metadata['width'] = width
        metadata['height'] = width

        metadata['mime'] = get_mime_type_from_file(path)
        return metadata


class CoverArtCommand(AttachmentCommand):
    name = 'coverart'

    # This is set by beets when instantiating the command
    factory = None

    def add_arguments(self):
        # TODO add options and arguments through the ArgumentParser
        # interface.
        raise NotImplementedError

    def run(self, argv, options):
        """Dispatch invocation to ``attach()`` or ``list()``.
        """
        album_query = query_from_args(argv)
        if options.attach:
            # -a option creates attachments
            self.attach(album_query, path=options.attach,
                        covertype=options.type, local=options.local)
        else:
            # list covers of a particular type
            self.list(album_query, covertype=options.type)

    def attach(self, query, path, covertype=None, local=False):
        """Attaches ``path`` as coverart to all albums matching ``query``.

        :param covertype:  Set the covertype of the attachment.
        :param local:  If true, path is relative to each album’s directory.
        """
        # TODO implement `embed` option to write images to tags. Since
        # the `MediaFile` class doesn't support multiple images at the
        # moment we have to implement it there first.
        for album in albums_from_query(query):
            if local:
                localpath = join(album.path, path)
            else:
                localpath = path
            attachment = self.factory.create_from_type(localpath,
                    entity=album, type='coverart')
            if covertype:
                attachment.meta['covertype'] = covertype
            attachment.move(cover_art_destination(attachment))
            attachment.store()

    def list(query, covertype=None):
        """Print list of coverart attached to albums matching ``query``.

        :param covertype:  Restrict the list to coverart of this type.
        """
        for attachment in self.factory.find(TypeQuery('coverart'), query)
            if covertype is None:
                print_attachment(attachment)
            elif attachment.meta['covertype'] == covertype:
                print_attachment(attachment)
