#Heavily based on the work of Adrian Sampson and his lovely beets

"""Adds Amazon album search support to the autotagger.
Needs an AmazonAccess Key ID and a Secret access key see:
http://aws-portal.amazon.com/gp/aws/developer/account/index.html
Also needs bottlenose
https://github.com/lionheart/bottlenose
in your pluginfolder
you must set Access_Key_ID, Secret_Key_ID and asso_tag in the config of beets
like this...
amazon:
    Access_Key_ID: youracceskeyID
    Secret_Access_Key: yoursecretaccesskey
    asso_tag: yourassotag(can be anything, I just set it to beets)

"""

from beets.autotag.hooks import AlbumInfo, TrackInfo, Distance
from beets.plugins import BeetsPlugin
import sys
import bottlenose
import logging
import re
import xml.etree.ElementTree as ET

log = logging.getLogger('beets')

class AmazonPlugin(BeetsPlugin):

    def __init__(self):
        super(AmazonPlugin, self).__init__()
        self.config.add({
            'source_weight': 0.3,
            'Access_Key_ID': None,
            'Secret_Access_Key': None,
            'asso_tag': "beets"
        })
        log.debug('in init Searching amazon')
        self.Access_Key_ID = self.config["Access_Key_ID"].get()
        self.Secret_Access_Key = self.config['Secret_Access_Key'].get()
        self.asso_tag = self.config['asso_tag'].get()

    def album_distance(self, items, album_info, mapping):
        """Returns the album distance.
        """
        dist = Distance()
        if album_info.data_source == 'Amazon':
            dist.add('source', self.config['source_weight'].as_number())
        return dist

    def candidates(self, items, artist, album, va_likely):
        """Returns a list of AlbumInfo objects for Amazon search results
        matching an album and artist (if not various).
        """
        if va_likely:
            query = album
        else:
            query = '%s %s' % (artist, album)
        try:
            return self.get_albums(query, va_likely)
        except:
            e = sys.exc_info()[0]

            log.debug('Amazon Search Error: %s (query: %s' % (e, query))
            return []

    def album_for_id(self, asin):
        """Fetches an album by its amazon ID and returns an AlbumInfo object
        or None if the album is not found.
        """
        log.debug('Searching amazon for release %s' % str(asin))
        amazon = bottlenose.Amazon(
            self.Access_Key_ID,
            str(self.Secret_Access_Key),
            self.asso_tag)
        response = amazon.ItemSearch(
            SearchIndex="Music",
            Keywords=asin,
            ResponseGroup="Tracks,ItemAttributes",
        )
        root = ET.fromstring(response)
        nsregx = re.compile('^({.+?})')
        ns = nsregx.search(root.tag).group(1)
        item = root.find(".//{0}Tracks/..".format(ns))
        return self.get_album_info(item)

    def get_albums(self, query, va_likely):
        """Returns a list of AlbumInfo objects for a Amazon search query.
        """
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r'(?u)\W+', ' ', query)
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r'(?i)\b(CD|disc)\s*\d+', '', query)
        albums = []
        amazon = bottlenose.Amazon(
             self.Access_Key_ID, str(self.Secret_Access_Key), self.asso_tag
        )
        response = amazon.ItemSearch(
            SearchIndex="Music",
            Keywords=query,
            ResponseGroup="Tracks,ItemAttributes"
        )
        root = ET.fromstring(response)
        nsregx = re.compile('^({.+?})')
        ns = nsregx.search(root.tag).group(1)

        for item in root.findall(".//{0}Tracks/..". format(ns)):
            albums.append(self.get_album_info(item, ns, va_likely))
            if len(albums) >= 5:
                break
        log.debug('get_albums_Searching amazon for release %s' % str(query))
        return albums

    def decod(self, val, codec='utf8'):
        """Ensure that all string are coded to Unicode.
        """
        if isinstance(val, basestring):
            return val.decode(codec, 'ignore')

    def get_album_info(self, item, ns, va_likely):

            album = item.findtext('{0}ItemAttributes/{0}Title'.format(ns))
            album_id = item.findtext('{0}ItemAttributes/{0}EAN'.format(ns))
            album_UPC = item.findtext('{0}ItemAttributes/{0}UPC'.format(ns))

            country = ",".join([cat.text.replace("Country Of Release:", '') for
                cat in item.findall('{0}ItemAttributes/{0}Feature'.format(ns))
                if "Country Of Release:" in cat.text])

            catnumlisbig = None
            catalog = ",".join([cat.text.replace("Catalog#", '') for
                cat in item.findall('{0}ItemAttributes/{0}Feature'.format(ns))
                if "Catalog#" in cat.text])
            catnumlis = [it.text for it in item.findall(
            '{0}ItemAttributes/{0}CatalogNumberList/{0}CatalogNumberListElement'
            .format(ns))]
            catnumlis.sort()
            catnumlisbig = catnumlis[0] if catnumlis else catalog

            perf = ",".join([role.text for role in item.findall(
                    '{0}ItemAttributes/{0}Creator'.format(ns))
                    if role.attrib.get("Role") == "Performer"])

            art = ",".join([artist.text for artist in item.findall(
                    '{0}ItemAttributes/{0}Artist'.format(ns))])

            artists = art or perf
            va = False
            if artists == album and va_likely:
                artists = "Various Artists"
                va = True
            artist_id = artists.split(",")[0]
            Tracks = []
            trn = 1
            for disc in item.iterfind(".//{0}Disc".format(ns)):
                tr = disc.findall(".//{0}Track".format(ns))
                for track in disc.iterfind(".//{0}Track".format(ns)):
                    title = track.text
                    index = trn
                    medium = disc.attrib.get("Number")
                    medium_index = track.attrib.get("Number")
                    newtrack = TrackInfo(
                        self.decod(title),
                        int(index),
                        index=int(index),
                        medium=int(medium),
                        medium_index=int(medium_index),
                        medium_total=len(tr)
                        )
                    Tracks.append(newtrack)
                    trn = trn + 1
            asin = item.findtext('{0}ASIN'.format(ns))
            albumtype = item.findtext(
                '{0}ItemAttributes/{0}Binding'.format(ns))
            rd = item.findtext(
                '{0}ItemAttributes/{0}ReleaseDate'.format(ns))
            year = month = day = None
            if rd:
                releasedate = rd.split("-")
                year = releasedate[0]
                month = releasedate[1]
                day = releasedate[2]

            label = item.findtext('{0}ItemAttributes/{0}Label'.format(ns))
            ProductTypeName = item.findtext(
                '{0}ItemAttributes/{0}ProductTypeName'.format(ns))
            label = label if label else ProductTypeName
            mediums = item.findtext(
                '{0}ItemAttributes/{0}NumberOfDiscs'.format(ns))
            if mediums is None:
                mediums = 1
            Composers = [role.text for role in item.findall(
                '{0}ItemAttributes/{0}Creator'.format(ns))
                if role.attrib.get("Role") == "Composer"]
            Conductors = [role.text for role in item.findall(
                '{0}ItemAttributes/{0}Creator'.format(ns))
                if role.attrib.get("Role") == "Conductor"]
            Orchestras = [role.text for role in item.findall(
                '{0}ItemAttributes/{0}Creator'.format(ns))
                if role.attrib.get("Role") == "Orchestra"]
            comps = ",". join(Composers)
            cond = ",".join(Conductors)
            orch = ",".join(Orchestras)
            media = item.findtext('{0}ItemAttributes/{0}Binding'.format(ns))
            data_url = item.findtext('{0}DetailPageURL'.format(ns))

            return AlbumInfo(self.decod(album),
                            self.decod(album_id),
                            self.decod(artists),
                            self.decod(artist_id),
                            Tracks,
                            asin=self.decod(asin),
                            albumtype=self.decod(albumtype),
                            va=va,
                            year=int(year),
                            month=int(month),
                            day=int(day),
                            label=self.decod(label),
                            mediums=int(mediums),
                            media=self.decod(media),
                            data_source=self.decod('Amazon'),
                            data_url=self.decod(data_url),
                            country=self.decod(country),
                            catalognum=self.decod(catnumlisbig)

                         )
