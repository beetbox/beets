#The first import is for communicating with the music DB MusicBrainz

import logging
import musicbrainzngs

from beets.autotag import mb
from beets.autotag import hooks
from beets.library import Album
from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_obj



#This is how we call our plugin
PLUGIN = 'missingalbums'
log = logging.getLogger('beets')

class MissingAlbumsPlugin (BeetsPlugin):
	def __init__(self):
		super(MissingAlbumPlugin, self).__init__()
		self._command = Subcommand('missingalbums', 
								   help='returns missing albums',
                                   aliases=['malbum'])
	def commands(self):
		def _miss(lib, opts, args):
			self.config.set_args(opts)
			albums = lib.albums(decargs(args))
			artists = set()
			for album in albums:
				artists.add('album.mb_albumartistid')
			albums2 = set()
			for artist in artists:
				x = musicbrainzngs.get_artist_by_id(artist,'releases')
				for r in x['releases']:
					albums2.add(r)
			albums = set(albums)
			miss = albums2.difference(albums)
			for y in miss:
				print_obj(y, lib, None)
			
		self._command.func = _miss
		return [self._command]
		
		