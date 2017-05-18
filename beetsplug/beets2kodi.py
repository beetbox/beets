# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Peace Lekalakala.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.


"""Creates Kodi nfo files (artist.nfo & album.nfo) in xml format after importing album.

Put something like the following in your config.yaml to configure: as per kodiupdate plugin
    kodi:
        host: localhost
        port: 8080
        user: user
        pwd: secret
    audiodb:
        key: secretkey
"""

from __future__ import absolute_import, division, print_function
import os, time
import simplejson, json
import base64
import yaml
import urllib.request
from urllib.request import Request, urlopen
import beets.library
from beets import config
from beets.plugins import BeetsPlugin
from lxml import etree as ET
 
artist_tags = ['name', 'musicBrainzArtistID', 'sortname', 'genre', 'style', 'mood',
               'born', 'formed', 'biography', 'died', 'disbanded'] 

album_tags = ['title', 'musicBrainzAlbumID', 'artist', 'genre', 'style', 'mood',
              'theme', 'compilation', 'review', 'type', 'releasedate', 'label', 'rating', 'year']

emptyalbum = '''{"album":[{"idAlbum":"","idArtist":"","idLabel":"","strAlbum":"",
             "strAlbumStripped":"","strArtist":"","intYearReleased":"","strStyle":"",
             "strGenre":"","strLabel":"","strReleaseFormat":"","intSales":"",
             "strAlbumThumb":"","strAlbumThumbBack":"","strAlbumCDart":"","strAlbumSpine":"",
             "strDescriptionEN":"","strDescriptionDE":"","strDescriptionFR":"",
             "strDescriptionCN":"","strDescriptionIT":"","strDescriptionJP":"",
             "strDescriptionRU":"","strDescriptionES":"","strDescriptionPT":"",
             "strDescriptionSE":"","strDescriptionNL":"","strDescriptionHU":"",
             "strDescriptionNO":"","strDescriptionIL":"","strDescriptionPL":"",
             "intLoved":"","intScore":"","intScoreVotes":"","strReview":" ",
             "strMood":"","strTheme":"","strSpeed":"","strLocation":"","strMusicBrainzID":"",
             "strMusicBrainzArtistID":"","strItunesID":"","strAmazonID":"","strLocked":""}]}'''

emptyartist = '''{"artists":[{"idArtist":"","strArtist":"","strArtistAlternate":"","strLabel":"",
              "idLabel":"","intFormedYear":"","intBornYear":"","intDiedYear":"","strDisbanded":"",
              "strStyle":"","strGenre":"","strMood":"","strWebsite":"","strFacebook":"",
              "strTwitter":"","strBiographyEN":"","strBiographyDE":"","strBiographyFR":"",
              "strBiographyCN":"","strBiographyIT":"","strBiographyJP":"","strBiographyRU":"",
              "strBiographyES":"","strBiographyPT":"","strBiographySE":"","strBiographyNL":"",
              "strBiographyHU":"","strBiographyNO":"","strBiographyIL":"","strBiographyPL":"",
              "strGender":"","intMembers":"","strCountry":"","strCountryCode":"","strArtistThumb":"",
              "strArtistLogo":"","strArtistFanart":"","strArtistFanart2":"","strArtistFanart3":"",
              "strArtistBanner":"","strMusicBrainzID":"","strLastFMChart":"","strLocked":"unlocked"}]}'''

libpath = os.path.expanduser(str(config['library']))
lib = beets.library.Library(libpath)

def artist_info(albumid):
   
    for album in lib.albums(albumid):
        data = album.albumartist,album.albumartist_sort,album.mb_albumartistid,album.genre,album.path
        url = "http://www.theaudiodb.com/api/v1/json/{0}/artist-mb.php?i=".format(config['audiodb']['key'])
        
        try:
            response = urllib.request.urlopen(url+data[2])
            data2 = simplejson.load(response)["artists"][0]
            
        except (ValueError, TypeError):  # includes simplejson.decoder.JSONDecodeError 
            data2 = json.loads(emptyartist)["artists"][0]
    
        out_data = ("{0};{1};{2};{3};{4};{5};{6};{7};{8};{9};{10};{11};{12}".format(data[0], data[2], 
                   data[1], data[3], data2["strStyle"] or '', data2["strMood"] or '', 
                   data2["intBornYear"] or '', data2["intFormedYear"] or '', data2["strBiographyEN"] or '', 
                   data2["intDiedYear"] or '', data2["strDisbanded"] or '', data2["strArtistThumb"] or '',
                   data2["strArtistFanart"] or ''))
        return list(out_data.split(';'))
         

def artist_albums(artistid):
    albumdata = []
    for album in lib.albums(artistid):
        row = album.album,album.original_year
        albumdata.append(list(tuple([row[1],row[0]]))) #create sortable list
    albumlist = (sorted(albumdata)) #sort list to start with first release/album
    return albumlist

def album_info(albumid):
    
    for album in lib.albums(albumid):
        data = (album.albumartist,album.mb_albumartistid,album.mb_releasegroupid,album.album,
               album.genre,album.comp,album.label,album.albumtype,album.mb_albumid)
        date = album.original_year,album.original_month,album.original_day
        rel_date = ("%s-%s-%s" % (date[0], format(date[1], '02'),format(date[2], '02')));
        url= "http://www.theaudiodb.com/api/v1/json/{0}/album-mb.php?i=".format(config['audiodb']['key']) 
        
        if data[5] == 0:
            comp = 'False'
        else:
            comp = 'True'
                     
        try:
            response = urllib.request.urlopen(url+data[2])
            data2 = simplejson.load(response)["album"][0]
             
        except (ValueError, TypeError):
            data2 = json.loads(emptyalbum)["album"][0]
    
        out_data = ("{0};{1};{2};{3};{4};{5};{6};{7};{8};{9};{10};{11};{12};{13};{14}".format((data[3]), (data[8]), 
                  (data[0]), (data[4]), (data2["strStyle"]) or '' , (data2["strMood"]) or '', (data2["strTheme"]) or '', 
                  (comp), (data2["strReview"]) , (data[7]), (rel_date), (data[6]), (data2["intScore"]) or '', 
                  (date[0]), (data2["strAlbumThumb"]) or ''))
        return list(out_data.split(';'))

def album_tracks(albumid):
    trackdata = []    
    for item in lib.items(albumid):
        row = item.track,item.mb_trackid,item.length,item.title
        duration = time.strftime("%M:%S", time.gmtime(row[2]))
        trackdata.append(list(tuple([row[0],duration,row[1],row[3]])))
        tracklist = (sorted(trackdata)) #sort list by track number
    return tracklist

def paths(tag, albumid):
    auth = str.encode('%s:%s' % (config['kodi']['user'], config['kodi']['pwd']))
    authorization = b'Basic ' + base64.b64encode(auth) 
    headers = { 'Content-Type': 'application/json', 'Authorization': authorization }
    url = "http://{0}:{1}/jsonrpc".format(config['kodi']['host'], config['kodi']['port'])
    data={"jsonrpc": "2.0", "method": "Files.GetSources", "params": {"media": "music"}, "id": 1}
    json_data = json.dumps(data).encode('utf-8')
    request = Request(url, json_data, headers)
    result = simplejson.load(urlopen(request))
    xbmc_path = result['result']['sources'][0]['file']
    out_data = []
    for album in lib.albums(albumid):
        row = album.albumartist,album.album,album.artpath,album.path
        data = str(config["directory"]) 
        length = int(len(data)+1)                         
        album_path = row[3].decode("utf-8")
        artist_path = os.path.dirname(album_path)
        if row[0] in album_path or row[0] in artist_path:
            out_data = ((album_path, (xbmc_path + album_path[length:])), 
            (artist_path, (xbmc_path + artist_path[length:])), row[0])
        else:
            out_data = ((album_path, (xbmc_path + album_path[length:])), '', row[0])  
        
        if "artist" in tag:
            return out_data[1]

        if "album" in tag:
            return out_data[0]

def thumbs(tag, albumid):
    if "artist" in tag:
        thumbs =[]
        for a in paths('artist', albumid):
            thumb = "%s/artist.tbn" % a
            thumbs.append(thumb)
        return thumbs
    if "album" in tag:
        thumbs =[]
        for a in paths('album', albumid):
            thumb = "%s/folder.jpg" % a
            thumbs.append(thumb)
        return thumbs            

class Beets2Kodi(BeetsPlugin):
    def __init__(self):
        super(Beets2Kodi, self).__init__()
        self.register_listener('album_imported', self.album_nfo)
        self.register_listener('album_imported', self.artist_nfo)

    def artist_nfo(self, lib, album):
        albumid = 'mb_albumid:'+ album.mb_albumid
        artistid = 'mb_albumartistid:' + album.mb_albumartistid
        artistnfo = os.path.join(album.path.decode('utf8'), os.pardir, 'artist.nfo')
        if album.albumartist in ['Various Artists', 'Soundtracks']:
            pass
        else:
            root = ET.Element('artist')
            for i in range(len(artist_tags)):
                artist_tags[i] = ET.SubElement(root, '{}'.format(artist_tags[i]))
                artist_tags[i].text = artist_info(albumid)[i]
    
            for i in range(len(paths('artist', albumid))):
                path = ET.SubElement(root, 'path')
                path.text = paths('artist', albumid)[i]

            if artist_info(albumid)[11] == '':
                thumb = ET.SubElement(root, 'thumb')
                thumb.text = ''
            else:
                thumb_location = os.path.join(paths('artist', albumid)[0], 'artist.tbn')
                urllib.request.urlretrieve(artist_info(albumid)[11], thumb_location)
                thumb = ET.SubElement(root, 'thumb')
                thumb.text = artist_info(albumid)[11]
                for i in range(len(thumbs('artist', albumid))):
                    thumb = ET.SubElement(root, 'thumb')
                    thumb.text = thumbs('artist', albumid)[i]

            fanart =  ET.SubElement(root, 'fanart')
            fanart.text =  artist_info(albumid)[12]
      
            for i in range(len(artist_albums(artistid))):
                album = ET.SubElement(root, 'album')
                title = ET.SubElement(album, 'title')
                title.text = artist_albums(artistid)[i][1]
                year =   ET.SubElement(album, 'year')
                year.text = str(artist_albums(artistid)[i][0])

            xml =  ET.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8', standalone="yes").decode()
            print (xml, file=open(artistnfo, 'w+'))

    def album_nfo(self, lib, album): 
        albumnfo = os.path.join(album.path.decode('utf8'), 'album.nfo')
        albumid = 'mb_albumid:'+ album.mb_albumid
        root = ET.Element('album')
        for i in range(len(album_tags)):
            album_tags[i] = ET.SubElement(root, '{}'.format(album_tags[i]))
            album_tags[i].text = album_info(albumid)[i]

        for i in range(len(paths('album', albumid))):
            path = ET.SubElement(root, 'path')
            path.text = paths('album', albumid)[i]

        if album_info(albumid)[14] == '':
            for i in range(len(thumbs('album', albumid))):
                thumb = ET.SubElement(root, 'thumb')
                thumb.text = thumbs('album', albumid)[i]
        else:
            thumb = ET.SubElement(root, 'thumb')
            thumb.text = album_info(albumid)[14]
            for i in range(len(thumbs('album', albumid))):
                thumb = ET.SubElement(root, 'thumb')
                thumb.text = thumbs('album', albumid)[i]

        albumArtistCredits = ET.SubElement(root, 'albumArtistCredits')
        artist = ET.SubElement(albumArtistCredits, 'artist')
        artist.text = album.albumartist
        musicBrainzArtistID = ET.SubElement(albumArtistCredits, 'musicBrainzArtistID')
        musicBrainzArtistID.text = album.mb_albumartistid

        for i in range(len(album_tracks(albumid))):
            track = ET.SubElement(root, 'track')
            position = ET.SubElement(track, 'position')
            position.text = str(album_tracks(albumid)[i][0])
            title =   ET.SubElement(track, 'title')
            title.text = album_tracks(albumid)[i][3]
            duration = ET.SubElement(track, 'duration')
            duration.text = album_tracks(albumid)[i][1]
            musicBrainzTrackID =   ET.SubElement(track, 'musicBrainzTrackID')
            musicBrainzTrackID.text = album_tracks(albumid)[i][2]

        xml =  ET.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8', standalone="yes").decode()
        print (xml, file=open(albumnfo, 'w+'))
