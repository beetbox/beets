import logging
from email.mime.image import MIMEImage
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
        img = MIMEImage(data)
        mime_img = img.get_content_subtype()

        if mime_img == 'jpeg':
            kind = mediafile.imagekind.JPEG
        elif mime_img == 'png':
            kind = mediafile.imagekind.PNG
        else:
            log.error('A file of type %s is not allowed as coverart.'
                        % mime_img)
            return

        # Add art to each file.
        log.debug('Embedding album art.')
        for item in album.items():
            f = mediafile.MediaFile(item.path)
            f.art = (data, kind)
            f.save()
