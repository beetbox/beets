from beets.plugins import BeetsPlugin
from beets import mediafile

import os, logging

from email.mime.image import MIMEImage

log = logging.getLogger('beets')
log.addHandler(logging.StreamHandler())


class EmbedAlbumartPlugin(BeetsPlugin):
    '''Allows albumart to be embedded into the actual files'''

    def __init__(self):
        self.register_listener('loaded', self.loaded)
        self.register_listener('album_imported', self.album_imported)

    def configure(self, config):
        pass

    def loaded(self):
        pass

    def album_imported(self, album):
        albumart = album.artpath
        ALLOWED_MIMES = ('jpeg','png')

        if albumart:
            albumart_raw = open(albumart, 'rb').read()
            img = MIMEImage(albumart_raw)
            mime_img = img.get_content_subtype()

            if mime_img in ALLOWED_MIMES:
                mime_type = 'image/%s' % mime_img

            for item in album.items():
                f = mediafile.MediaFile(item)
                
                if "mp3" in item.type:
                    f.albumart_mime = mime_type
                
                f.albumart_data = albumart_raw
                f.save()

