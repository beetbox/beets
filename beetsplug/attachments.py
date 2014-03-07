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


import beets.ui
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand


class AttachmentPlugin(BeetsPlugin):
    """Adds ``attach`` command and creates attachments after import.
    """
    def __init__(self):
        super(AttachmentPlugin).__init__()
        self.register_listener('import_task_apply', self.import_attachments)

    def commands(self):
        return [AttachCommand()]

    def import_attachments(self, task, session):
        """Looks for files in imported folder creates attachments for them.
        """
        # TODO implement
        raise NotImplementedError


class AttachCommand(Subcommand):

    def __init__(self):
        # TODO add usage
        super(AttachCommand, self).__init__()
        parser.add_option('-l', '--local', dest='local'.
                          action='store_true', default=False
                          help='ATTACHMENT path is relative to album directory')

    def func(self, lib, opts, args):
        """Create an attachment from file for all albums matched by a query.
        """
        # TODO add verbose logging
        path = args.pop(0)
        query = ui.decargs(args)
        for album in lib.albums(ui.decargs(args)):
            if opts.local:
                path = os.path.join(album.item_dir())
            else:
                path = os.path.abspath(path)
            for attachment in factory.discover(path, album):
                attachment.move()
                attachemnt.store()

