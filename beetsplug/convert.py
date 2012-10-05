# Copyright 2012, Jakob Schnitzer.
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

"""Converts tracks or albums to external directory
"""
import logging
import os
import subprocess
import os.path

from beets.plugins import BeetsPlugin
from beets import ui, library, util, mediafile
from beets.util.functemplate import Template

log = logging.getLogger('beets')

def _embed(path, items):
    """Embed an image file, located at `path`, into each item.
    """
    data = open(syspath(path), 'rb').read()
    kindstr = imghdr.what(None, data)
    if kindstr not in ('jpeg', 'png'):
        log.error('A file of type %s is not allowed as coverart.' % kindstr)
    return
    log.debug('Embedding album art.')
    for item in items:
        try:
            f = mediafile.MediaFile(syspath(item.path))
        except mediafile.UnreadableFileError as exc:
            log.warn('Could not embed art in {0}: {1}'.format(
                repr(item.path), exc
            ))
            continue
        f.art = data
        f.save()

def convert_track(source, dest):
    with open(os.devnull, "w") as fnull:
	    subprocess.call('flac -cd "{0}" | lame -V2 - "{1}"'.format(source, dest), 
                stdout=fnull, stderr=fnull, shell=True)


def convert_item(lib, item, dest, artpath):
    dest_path = os.path.join(dest,lib.destination(item, fragment = True))
    dest_path = os.path.splitext(dest_path)[0] + '.mp3'
    if not os.path.exists(dest_path):
        util.mkdirall(dest_path)
    	log.info('Encoding '+ item.path)
        convert_track(item.path, dest_path)
        converted_item = library.Item.from_path(dest_path)
        converted_item.read(item.path)
        converted_item.path = dest_path
        converted_item.write()
        if artpath:
            _embed(artpath,[converted_item])
    else:
        log.info('Skipping '+item.path)

def convert_func(lib, config, opts, args):
    if not conf['dest']:
        log.error('No destination set')
        return
    if opts.album:
        fmt = u'$albumartist - $album'
    else:
        fmt = u'$artist - $album - $title'
    template = Template(fmt)
    if opts.album:
        objs = lib.albums(ui.decargs(args))
    else:
        objs = list(lib.items(ui.decargs(args)))

    for o in objs:
        if opts.album:
            ui.print_(o.evaluate_template(template))
        else:
            ui.print_(o.evaluate_template(template, lib))

    if not ui.input_yn("Convert? (Y/n)"):
        return

    for o in objs:
        if opts.album:
            for item in o.items():
                convert_item(lib, item, conf['dest'], o.artpath)
        else:
            album = lib.get_album(o)
            convert_item(lib, o, conf['dest'], album.artpath)

conf = {}

class ConvertPlugin(BeetsPlugin):
    def configure(self, config):
        conf['dest'] = ui.config_val(config, 'convert', 'path', None)

    def commands(self):
        cmd = ui.Subcommand('convert', help='convert albums to external location')
        cmd.parser.add_option('-a', '--album', action='store_true',
                        help='choose an album instead of track')
        cmd.func = convert_func
        return [cmd]
