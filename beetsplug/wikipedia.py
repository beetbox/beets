

from __future__ import division, absolute_import, print_function

from beets.autotag.hooks import *
from beets.plugins import BeetsPlugin
from requests.exceptions import *
import time
import urllib.request
from bs4 import BeautifulSoup

infoBoxList = ['Released', 'Genre', 'Length', 'Label']

#-----------------------------------------------------------------------
# isInfobox check
def isInInfo(liste):
    for i in infoBoxList:
        if(len(liste) != 0 and liste[0] == i):
            return True
    return False


def get_track_length(duration):
    """
        Returns the track length in seconds for a wiki duration.
    """
    try:
        length = time.strptime(duration, '%M:%S')
    except ValueError:
        return None
    return length.tm_min * 60 + length.tm_sec

#----------------------------------------------------------------------
"""
    WikiAlbum class is being served like AlbumInfo object which keeps all album
    meta data in itself.
"""
class WikiAlbum(object):
    def __init__(self, artist, album_name):

        self.album = album_name
        self.artist = artist
        self.tracks = []
        self.album_length = ""

        self.label = None
        self.year = None
        self.data_source = "Wikipedia"
        self.data_url = ""
        self.album_id = 1
        self.va = False

        self.artist_id = 1

        self.asin = None
        self.albumtype = None
        self.year = None
        self.month = None
        self.day = None
        self.mediums = 1
        self.artist_sort = None
        self.releasegroup_id = None
        self.catalognum = None
        self.script = None
        self.language = None
        self.country = None
        self.albumstatus = None
        self.media = None
        self.albumdisambig = None
        self.artist_credit = None
        self.original_year = None
        self.original_month = None
        self.original_day = None



        try:
            url = 'https://en.wikipedia.org/wiki/' + album_name + '_(' + artist + '_album)'
            html = urllib.request.urlopen(url).read()

        except urllib.error.HTTPError:

            try:
                url = 'https://en.wikipedia.org/wiki/' + album_name + '_(album)'
                html = urllib.request.urlopen(url).read()
            except urllib.error.HTTPError:
                try:
                    url = 'https://en.wikipedia.org/wiki/' + album_name
                    html = urllib.request.urlopen(url).read()
                except urllib.error.HTTPError:
                    try:
                        # in case of album name has (Deluxe) extension
                        url = 'https://en.wikipedia.org/wiki/' + album_name[:-9] + '_(' + artist + '_album)'
                        html = urllib.request.urlopen(url).read()
                    except urllib.error.HTTPError:
                        raise HTTPError

        except ConnectionError:
            raise ConnectionError


        self.data_url = url
        soup = BeautifulSoup(html, "lxml")

        # ------------------ INFOBOX PARSING ----------------------#
        infoBox = soup.findAll("table", {"class": "infobox"})
        infoCounter = 1
        for info in infoBox:
            for row in info.findAll("tr"):

                if (self.artist == "" and infoCounter == 3):
                    self.artist = row.getText().split()[-1]

                data = (row.getText()).split('\n')
                data = list(filter(None, data))

                if (isInInfo(data)):
                    if(data[0] == 'Label'):
                        self.label = str(data[1:])
                    elif(data[0] == 'Released'):
                        if (data[1][-1] == ")"):
                            self.year = int(data[1][-11:-7])
                            self.month = int(data[1][-6:-4])
                            self.day = int(data[1][-3:-1])
                        else:
                            self.year = int(data[1][-4:])
                    # Length of an Album which is converted into beets length format
                    elif(data[0] == "Length"):
                        self.album_length = get_track_length(data[1])

                    # getting Genre
                    elif(data[0] == "Genre"):
                        fixed_genre = ""
                        for character in data[1]:
                            if (character != ("[" or "{" or "(")):
                                fixed_genre += character
                            else:
                                break
                        self.genre = fixed_genre

                infoCounter += 1

        track_tables = soup.findAll("table", {"class": "tracklist"})

        # to set the MediumTotal, total number of tracks in an album is required
        trackCounter = 0
        for table in track_tables:
            for row in table.findAll("tr"):
                rowData = (row.getText()).split('\n')
                rowData = list(filter(None, rowData))
                # enables to pick only the tracks not irrelevant parts of the tables.
                # len(rowData) check is used for getting the correct table data and checking track numbers whether it is exist or not
                if (rowData[0][:-1].isdigit() and len(rowData) > 3):
                    trackCounter += 1


        for table in track_tables:
            for row in table.findAll("tr"):
                rowData = (row.getText()).split('\n')
                rowData = list(filter(None, rowData))
                # enables to pick only the tracks not irrelevant parts of the tables.
                # len(rowData) check is used for getting the correct table data and checking track numbers whether it is exist or not
                if (rowData[0][:-1].isdigit() and len(rowData) > 3):
                    oneTrack = Track(rowData)
                    oneTrack.setDataUrl(self.data_url)
                    oneTrack.setMediumTotal(trackCounter)
                    self.tracks.append(oneTrack)

    def getL(self):
        return self.album_length
    def getTracks(self):
        return self.tracks



# keep the metadata of tracks which are gathered from wikipedia like TrackInfo object in beets
class Track(object):

    def __init__(self, row ):

        #####
        self.medium = 1
        self.disctitle = "CD"
        #####
        self.medium_index = int(row[0][:-1])
        self.track_id = int(row[0][:-1])
        self.index = int(row[0][:-1])

        #wiping out the character (") from track name
        tempName = ""
        for i in row[1]:
            if(i != '"'):
                tempName += i
        self.title = str(tempName)

        self.writer = list(row[2].split(','))
        self.producers = row[3:-1]
        self.length = get_track_length(row[-1])
        self.artist = None
        self.artist_id = None
        self.media = None

        self.medium_total = None
        self.artist_sort = None
        self.artist_credit = None
        self.data_source = "Wikipedia"
        self.data_url = None
        self.lyricist = None
        self.composer = None
        self.composer_sort = None
        self.arranger = None
        self.track_alt = None
        self.track = self.index
        self.disc = self.medium
        self.disctotal = 2
        self.mb_trackid = self.track_id
        self.mb_albumid = None
        self.mb_album_artistid = None
        self.mb_artist_id = None
        self.mb_releasegroupid = None
        self.comp = 0
        self.tracktotal = None
        self.albumartist_sort = None
        self.albumartist_credit = None


    def setMediumTotal(self,num):
        self.medium_total = num
        self.track_total = num
    def setDataUrl(self,url):
        self.data_url = url
    def getName(self):
        return self.title
    def getWriter(self):
        return self.writer
    def getProducers(self):
        return self.producers
    def getLength(self):
        return self.length



class WikiPlug(BeetsPlugin):

    def __init__(self):
        super(WikiPlugin, self).__init__()
        self.config.add({
            'source_weight': 0.50
        })

    # ----------------------------------------------

    """ Track_distance
        item --> track to be matched(Item Object)
        info is the TrackInfo object that proposed as a match
            --- should return a (dist,dist_max) pair of floats indicating the distance
    """
    def track_distance(self, item, info):
        dist = Distance()
        return dist

    #----------------------------------------------
    """
        album_info --> is a AlbumInfo Object reflecting the album to be compared.
        items --> is a sequence of all Item objects that will be matched
        mapping --> is a dictionary mapping Items to TrackInfo objects
    """
    def album_distance(self, items, album_info, mapping):
        """
            Returns the album distance.
        """
        dist = Distance()

        if (album_info.data_source == 'Wikipedia') :
            dist.add('source', self.config['source_weight'].as_number())
        return dist

    # ----------------------------------------------
    def candidates(self, items, artist, album, va_likely):
        """Returns a list of AlbumInfo objects for Wikipedia search results
        matching an album and artist (if not various).
        """
        candidate_list = []
        candidate_list.append(WikiAlbum(artist, album))

        return candidate_list


