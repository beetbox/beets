from beets.plugins import BeetsPlugin

from beets.autotag import mb

class KodiNfo(BeetsPlugin):
  def __init__(self):
    super(KodiNfo, self).__init__()
    self.register_listener('album_imported', self.makeAlbumNfo)

  def makeAlbumNfo(self, lib, album):
    d = mb.match_album(album.albumartist, album.album, None)
    b = (x for x in d ).next().album_id
    file = open(album.path + "/album.nfo","w+")
    file.write("https://musicbrainz.org/release/%s" % b)
    file.close()