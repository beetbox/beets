from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_
from beets.util.functemplate import Template
import random


"""
Get a random song or album from the library
"""


def random_item(lib, config, opts, args):
    query = decargs(args)
    path = opts.path
    fmt = opts.format


    if fmt is None:
        # If no specific template is supplied, use a default
        if opts.album:
            fmt = u'$albumartist - $album'
        else:
            fmt = u'$artist - $album - $title'
    template = Template(fmt)


    if opts.album:
        items = list(lib.albums(query))
        item = random.choice(items)
        if path:
            print_(item.item_dir())
        else:
            print_(template.substitute(item._record))
    else:
        items = list(lib.items(query))
        item = random.choice(items)
        if path:
            print_(item.path)
        else:
            print_(template.substitute(item.record))

random_cmd = Subcommand('random', help='chose a random track, album, artist, etc.')
random_cmd.parser.add_option('-a', '--album', action='store_true',
        help='choose an album instead of track')
random_cmd.parser.add_option('-p', '--path', action='store_true',
        help='print the path of the matched item')
random_cmd.parser.add_option('-f', '--format', action='store',
        help='print with custom format', default=None)
random_cmd.func = random_item

class Random(BeetsPlugin):
    def commands(self):
        return [random_cmd]
