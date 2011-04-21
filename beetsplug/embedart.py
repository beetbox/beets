import logging
import imghdr
from beets.plugins import BeetsPlugin
from beets import mediafile

log = logging.getLogger('beets')

class EmbedCoverArtPlugin(BeetsPlugin):
    """Allows albumart to be embedded into the actual files."""
    def configure(self, config):
        pass

@EmbedCoverArtPlugin.listen('album_imported')
def album_imported(lib, album):
    if album.artpath:
        data = open(album.artpath, 'rb').read()
        kindstr = imghdr.what(None, data)

        if kindstr == 'jpeg':
            kind = mediafile.imagekind.JPEG
        elif kindstr == 'png':
            kind = mediafile.imagekind.PNG
        else:
            log.error('A file of type %s is not allowed as coverart.'
                        % kindstr)
            return

        # Add art to each file.
        log.debug('Embedding album art.')
        for item in album.items():
            f = mediafile.MediaFile(item.path)
            f.art = (data, kind)
            f.save()
