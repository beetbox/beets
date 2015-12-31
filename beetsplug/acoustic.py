from __future__ import (division, absolute_import, print_function,
                        unicode_literals)


from beets import plugins, ui
import requests

ACOUSTIC_URL = "http://acousticbrainz.org/"
LEVEL = "/high-level"
PLUGIN_DESCRIPTION = "Fetch metadata from AcousticBrainz"


class AcousticPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(AcousticPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('acoustic', help=PLUGIN_DESCRIPTION)

        def func(lib, opts, args):
            fetch_info(lib)

        cmd.func = func
        return [cmd]


# Currently outputs MBID and corresponding request status code
def fetch_info(lib):
    for item in lib.items():
        if item.mb_trackid:
            r = requests.get(generate_url(item.mb_trackid))
            print(item.mb_trackid)
            print(r.status_code)


# Generates url of AcousticBrainz end point for given MBID
def generate_url(mbid):
    return ACOUSTIC_URL + mbid + LEVEL
