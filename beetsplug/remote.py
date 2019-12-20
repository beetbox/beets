import requests

from beets import config, ui
from beets.ui import Subcommand
from beetsplug.play import PlayPlugin, play


class RemotePlugin(PlayPlugin):
    def __init__(self):
        super(RemotePlugin, self).__init__()

        config['play'].add({
            'servers': {
                'local': 'http://127.0.0.1:8337'
            }
        })

    def commands(self):
        play_commands = super().commands()
        remote_command = Subcommand(
            'remote',
            help=u'play from remote server'
        )
        remote_command.parser.add_album_option()
        remote_command.parser.add_option(
            u'-A', u'--args',
            action='store',
            help=u'add additional arguments to the command',
        )
        remote_command.parser.add_option(
            u'-y', u'--yes',
            action="store_true",
            help=u'skip the warning threshold',
        )
        remote_command.parser.add_option(
            u'-s', u'--server',
            action='store',
            help=u'remote server label',
        )
        remote_command.func = self._remote_command
        return play_commands + [remote_command]

    def _remote_command(self, lib, opts, args):
        server_url = config['play']['servers'][opts.server].get(str)

        if opts.album:
            item_type = 'remote album'
            album_response = requests.get(server_url + '/album/query/' + ' '.join(ui.decargs(args))).json()

            if not album_response['results']:
                ui.print_(ui.colorize('text_warning',
                                      u'No {0} to play.'.format(item_type)))
                return

            item_response = requests.get(server_url + '/item/query/' + 'album_id:' + str(album_response['results'][0]['id'])).json()
        else:
            item_type = 'remote track'
            if args:
                item_response = requests.get(server_url + '/item/query/' + ' '.join(ui.decargs(args))).json()
            else:
                item_response = requests.get(server_url + '/item/' + ' '.join(ui.decargs(args))).json()

        selection = []
        for result in item_response.get('results', []) or item_response.get('items', []):
            selection.append(server_url + '/item/' + str(result['id']) + '/file')

        if not selection:
            ui.print_(ui.colorize('text_warning',
                                  u'No {0} to play.'.format(item_type)))
            return

        open_args = self._playlist_or_paths([link.encode() for link in selection])
        command_str = self._command_str(opts.args)

        play(command_str, selection, None, open_args, self._log, item_type)
