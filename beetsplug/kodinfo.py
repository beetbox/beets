# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Peace Lekalakala.
# URL only text file by Sergio Soto, update by Pauli Kettunen.
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

"""Creates Kodi nfo files in xml or url only text format.
The nfos are created after importing album.

Put something like the following in your config.yaml to configure:
as per kodiupdate plugin
    kodi:
        host: localhost
        port: 8080
        user: user
        pwd: secret
        music_lib_name: music
    audiodb:
        key: secretkey
"""
from __future__ import absolute_import, division, print_function

import base64
import json
import os
import time
import requests
import urllib.request
from urllib.request import Request, urlopen
from uuid import UUID

from beets import config
import beets.library
from beets.plugins import BeetsPlugin

from pathlib import Path

from lxml import etree as et

import simplejson

audio_db_key = '195010'

artist_tags = ['name', 'musicBrainzArtistID', 'sortname', 'genre', 'style',
               'mood', 'born', 'formed', 'biography', 'died', 'disbanded']

album_tags = ['title', 'musicBrainzAlbumID', 'artist', 'genre', 'style',
              'mood', 'theme', 'compilation', 'review', 'type', 'releasedate',
              'label', 'rating', 'year']

emptyalbum = '''{"album":[{"idAlbum":"","idArtist":"","idLabel":"",
             "strAlbum":"","strAlbumStripped":"","strArtist":"",
             "intYearReleased":"","strStyle":"","strGenre":"","strLabel":"",
             "strReleaseFormat":"","intSales":"","strAlbumThumb":"",
             "strAlbumThumbBack":"","strAlbumCDart":"","strAlbumSpine":"",
             "strDescriptionEN":"","strDescriptionDE":"",
             "strDescriptionFR":"","strDescriptionCN":"",
             "strDescriptionIT":"","strDescriptionJP":"",
             "strDescriptionRU":"","strDescriptionES":"",
             "strDescriptionPT":"","strDescriptionSE":"",
             "strDescriptionNL":"","strDescriptionHU":"",
             "strDescriptionNO":"","strDescriptionIL":"",
             "strDescriptionPL":"",
             "intLoved":"","intScore":"","intScoreVotes":"","strReview":" ",
             "strMood":"","strTheme":"","strSpeed":"","strLocation":"",
             "strMusicBrainzID":"","strMusicBrainzArtistID":"",
             "strItunesID":"","strAmazonID":"","strLocked":""}]}'''

emptyartist = '''{"artists":[{"idArtist":"","strArtist":"",
              "strArtistAlternate":"","strLabel":"","idLabel":"",
              "intFormedYear":"","intBornYear":"","intDiedYear":"",
              "strDisbanded":"","strStyle":"","strGenre":"","strMood":"",
              "strWebsite":"","strFacebook":"","strTwitter":"",
              "strBiographyEN":"","strBiographyDE":"","strBiographyFR":"",
              "strBiographyCN":"","strBiographyIT":"","strBiographyJP":"",
              "strBiographyRU":"","strBiographyES":"","strBiographyPT":"",
              "strBiographySE":"","strBiographyNL":"","strBiographyHU":"",
              "strBiographyNO":"","strBiographyIL":"","strBiographyPL":"",
              "strGender":"","intMembers":"","strCountry":"",
              "strCountryCode":"","strArtistThumb":"","strArtistLogo":"",
              "strArtistFanart":"","strArtistFanart2":"",
              "strArtistFanart3":"","strArtistBanner":"",
              "strMusicBrainzID":"","strLastFMChart":"","strLocked":""}]}'''

audiodb_url = "http://www.theaudiodb.com/api/v1/json/"
libpath = os.path.expanduser(str(config['library']))
lib = beets.library.Library(libpath)

LINK_ALBUM = 'https://musicbrainz.org/release/{0}'
LINK_ARTIST = 'https://musicbrainz.org/artist/{0}'
LINK_TRACK = 'https://musicbrainz.org/recording/{0}'


def artist_info(albumid):
    """Collect artist information from beets lib and audiodb.com."""
    for album in lib.albums(albumid):
        data = (album.albumartist, album.albumartist_sort,
                album.mb_albumartistid, album.genre, album.path)
        url = audiodb_url + "{0}/artist-mb.php?i=".format(
            audio_db_key)

        try:
            response = urllib.request.urlopen(url + data[2])
            data2 = simplejson.load(response)["artists"][0]

        except (ValueError, TypeError):
            # catch simplejson.decoder.JSONDecodeError and load emptydata
            data2 = json.loads(emptyartist)["artists"][0]

        out_data = (
            "{0};{1};{2};{3};{4};{5};{6};{7};{8};{9};{10};{11};{12}".format(
                data[0],
                data[2],
                data[1],
                data[3],
                data2["strStyle"] or '',
                data2["strMood"] or '',
                data2["intBornYear"] or '',
                data2["intFormedYear"] or '',
                data2["strBiographyEN"] or '',
                data2["intDiedYear"] or '',
                data2["strDisbanded"] or '',
                data2["strArtistThumb"] or '',
                data2["strArtistFanart"] or ''))
        return list(out_data.split(';'))


def artist_albums(artistid):
    """Get artist's albums from beets library."""
    albumdata = []
    for album in lib.albums(artistid):
        row = album.album, album.original_year
        albumdata.append(list(tuple([row[1], row[0]])))  # create sortable list
    # sort list to start with first release/album
    albumlist = (sorted(albumdata))
    return albumlist


def album_info(albumid):
    """Collect album information from beets lib and audiodb.com."""
    for album in lib.albums(albumid):
        data = (
            album.albumartist,
            album.mb_albumartistid,
            album.mb_releasegroupid,
            album.album,
            album.genre,
            album.comp,
            album.label,
            album.albumtype,
            album.mb_albumid)
        date = album.original_year, album.original_month, album.original_day
        rel_date = (
            "%s-%s-%s" %
            (date[0], format(
                date[1], '02'), format(
                date[2], '02')))
        url = audiodb_url + "{0}/album-mb.php?i=".format(
            config['audiodb']['key'])

        if data[5] == 0:
            comp = 'False'
        else:
            comp = 'True'

        try:
            response = urllib.request.urlopen(url + data[2])
            data2 = simplejson.load(response)["album"][0]

        except (ValueError, TypeError):
            # catch simplejson.decoder.JSONDecodeError and load emptydata
            data2 = json.loads(emptyalbum)["album"][0]

        out_data = ("{0};{1};{2};{3};{4};{5};{6};{7};{8};{9};{10};{11};{12};"
                    "{13};{14}".format((data[3]),
                                       (data[8]),
                                       (data[0]),
                                       (data[4]),
                                       (data2["strStyle"]) or '',
                                       (data2["strMood"]) or '',
                                       (data2["strTheme"]) or '',
                                       (comp),
                                       (data2["strReview"]) or '',
                                       (data[7]),
                                       (rel_date),
                                       (data[6]),
                                       (data2["intScore"]) or '',
                                       (date[0]),
                                       (data2["strAlbumThumb"]) or ''))
        return list(out_data.split(';'))


def album_tracks(albumid):
    """Get album's tracks from beets libary."""
    trackdata = []
    for item in lib.items(albumid):
        row = item.track, item.mb_trackid, item.length, item.title
        duration = time.strftime("%M:%S", time.gmtime(row[2]))
        trackdata.append(list(tuple([row[0], duration, row[1], row[3]])))
        tracklist = (sorted(trackdata))  # sort list by track number
    return tracklist


def kodi_path():
    """From kodi itself get the music library path."""
    """Useful for shared libraries, in order to get nfs or samba paths."""
    try:
        auth = str.encode(
            '%s:%s' %
            (config['kodi']['user'],
             config['kodi']['pwd']))
        authorization = b'Basic ' + base64.b64encode(auth)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': authorization}
        url = "http://{0}:{1}/jsonrpc".format(
            config['kodi']['host'], config['kodi']['port'])
        data = {"jsonrpc": "2.0",
                "method": "Files.GetSources",
                "params": {"media": "music"},
                "id": 1}
        json_data = json.dumps(data).encode('utf-8')
        request = Request(url, json_data, headers)
        result = simplejson.load(urlopen(request))
        _kodi_path = result['result']['sources'][0]['file']
        return _kodi_path
    except (requests.exceptions.RequestException, ValueError, TypeError):
        return ''


def album_path(albumid):
    """Get album path."""
    out_data = []
    for album in lib.albums(albumid):
        album_path = album.path.decode("utf-8")
        root = str(config["directory"])
        length = int(len(root) + 1)
        kodi_lib_path = kodi_path() + album_path[length:]
        out_data = album_path, kodi_lib_path
    return out_data


def artist_path(albumid):
    """Get artist path."""
    out_data = []
    root = str(config['directory'])
    for album in lib.albums(albumid):
        albumpath = album.path.decode("utf-8")
        albumartist = album.albumartist
        if albumartist == os.path.basename(os.path.dirname(albumpath)):
            artist_path = os.path.dirname(albumpath)
            kodi_lib_path = kodi_path() + artist_path[int(len(root) + 1):]
        else:
            folder = os.path.join(root, str(config['paths']['default']))
            config_items = Path(folder).parts
            folder_length = len(config_items)
            indices = [i for i,
                       s in enumerate(config_items) if 'albumartist' in s]
            y = int(folder_length - indices[0])
            artistpath_items = list(Path(albumpath).parts[-y:-1])
            artist_path = os.path.join(root, *artistpath_items)
            kodi_lib_path = kodi_path() + artist_path[int(len(root) + 1):]
        out_data = artist_path, kodi_lib_path
    return out_data


def thumbs(tag, albumid):
    """Name paths where art files reside."""
    if "artist" in tag:
        thumbs = []
        for a in artist_path(albumid):
            thumb = os.path.join(a, 'artist.tbn')
            thumbs.append(thumb)
        return thumbs

    if "album" in tag:
        for album in lib.albums(albumid):
            if album.artpath:
                art_file = os.path.basename(album.artpath.decode('utf8'))
        thumbs = []
        for a in album_path(albumid):
            thumb = os.path.join(a, art_file)
            thumbs.append(thumb)
        return thumbs


def album_nfo_text(albumid, mb_albumid, mb_artistid):
    """Create MBID URL only text file."""
    album_nfo_file = os.path.join(album_path(albumid)[0], 'album.nfo')
    with open(album_nfo_file, 'w') as f:
        f.write(LINK_ALBUM.format(mb_albumid))
    if os.path.basename(artist_path(albumid)[0]) in ['Various Artists',
                                                     'Soundtracks',
                                                     'Compilations']:
        pass  # No artist.nfo file for compilation albums
    else:
        artist_nfo_file = os.path.join(artist_path(albumid)[0],
                                       'artsist.nfo')
        with open(artist_nfo_file, 'w') as f:
                f.write(LINK_ARTIST.format(mb_artistid))


def album_nfo_xml(albumid):
    """Create XML file with album information."""
    for album in lib.albums(albumid):
        albumnfo = os.path.join(album.path.decode('utf8'), 'album.nfo')
        albumid = 'mb_albumid:' + album.mb_albumid
        root = et.Element('album')
        for i in range(len(album_tags)):
            album_tags[i] = et.SubElement(root, '{}'.format(album_tags[i]))
            album_tags[i].text = album_info(albumid)[i]

        for i in range(len(album_path(albumid))):
            path = et.SubElement(root, 'path')
            path.text = album_path(albumid)[i]

        if album_info(albumid)[14] == '':
            for i in range(len(thumbs('album', albumid))):
                thumb = et.SubElement(root, 'thumb')
                thumb.text = thumbs('album', albumid)[i]
        else:
            thumb = et.SubElement(root, 'thumb')
            thumb.text = album_info(albumid)[14]
            for i in range(len(thumbs('album', albumid))):
                thumb = et.SubElement(root, 'thumb')
                thumb.text = thumbs('album', albumid)[i]

        albumartistcredits = et.SubElement(root, 'albumArtistCredits')
        artist = et.SubElement(albumartistcredits, 'artist')
        artist.text = album.albumartist
        musicbrainzartistid = et.SubElement(
            albumartistcredits, 'musicBrainzArtistID')
        musicbrainzartistid.text = album.mb_albumartistid

        for i in range(len(album_tracks(albumid))):
            track = et.SubElement(root, 'track')
            position = et.SubElement(track, 'position')
            position.text = str(album_tracks(albumid)[i][0])
            title = et.SubElement(track, 'title')
            title.text = album_tracks(albumid)[i][3]
            duration = et.SubElement(track, 'duration')
            duration.text = album_tracks(albumid)[i][1]
            musicbrainztrackid = et.SubElement(track, 'musicBrainzTrackID')
            musicbrainztrackid.text = album_tracks(albumid)[i][2]

        xml = et.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8',
            standalone="yes").decode()
        print(xml, file=open(albumnfo, 'w+'))


def artist_nfo_xml(albumid):
    """Create XML file with artist information."""
    for album in lib.albums(albumid):
        artistid = 'mb_albumartistid:' + album.mb_albumartistid
        artistnfo = os.path.join(artist_path(albumid)[0], 'artist.nfo')
        if album.albumartist in ['Various Artists', 'Soundtracks',
                                 'Compilations']:
            pass
        else:
            root = et.Element('artist')
            for i in range(len(artist_tags)):
                artist_tags[i] = et.SubElement(
                    root, '{}'.format(artist_tags[i]))
                artist_tags[i].text = artist_info(albumid)[i]

            for i in range(len(artist_path(albumid))):
                path = et.SubElement(root, 'path')
                path.text = artist_path(albumid)[i]

            if artist_info(albumid)[11] == '':
                thumb = et.SubElement(root, 'thumb')
                thumb.text = ''
            else:
                thumb_location = os.path.join(
                    album.path.decode('utf8'),
                    os.pardir, 'artist.tbn')
                urllib.request.urlretrieve(
                    artist_info(albumid)[11], thumb_location)
                thumb = et.SubElement(root, 'thumb')
                thumb.text = artist_info(albumid)[11]
                for i in range(len(thumbs('artist', albumid))):
                    thumb = et.SubElement(root, 'thumb')
                    thumb.text = thumbs('artist', albumid)[i]

            fanart = et.SubElement(root, 'fanart')
            fanart.text = artist_info(albumid)[12]

            for i in range(len(artist_albums(artistid))):
                album = et.SubElement(root, 'album')
                title = et.SubElement(album, 'title')
                title.text = artist_albums(artistid)[i][1]
                year = et.SubElement(album, 'year')
                year.text = str(artist_albums(artistid)[i][0])

            xml = et.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='UTF-8',
                standalone="yes").decode()
            print(xml, file=open(artistnfo, 'w+'))


def update_kodi(host, port, user, password):
    """Send request to the Kodi api to start a library refresh."""
    """By Pauli Kettunen"""
    url = "http://{0}:{1}/jsonrpc/".format(host, port)

    """Content-Type: application/json is mandatory"""
    """according to the kodi jsonrpc documentation"""

    headers = {'Content-Type': 'application/json'}

    # Create the payload. Id seems to be mandatory.
    payload = {'jsonrpc': '2.0', 'method': 'AudioLibrary.Scan', 'id': 1}
    r = requests.post(
        url,
        auth=(user, password),
        json=payload,
        headers=headers)

    return r


class KodiNfo(BeetsPlugin):
    """KodiNfo Plugin."""

    def __init__(self):
        """Plugin docstring."""
        super(KodiNfo, self).__init__()

        # Adding defaults.
        self.config['kodi'].add({
            u'host': u'localhost',
            u'port': 8080,
            u'user': u'kodi',
            u'pwd': u'kodi',
            u'nfo_format': 'xml'})
        config['kodi']['pwd'].redact = True
        self.register_listener('album_imported', self.create_nfos)
        self.register_listener('database_change', self.listen_for_db_change)

    def create_nfos(self, lib, album):
        """Create nfos as per choice in config."""
        try:
            # Check if MBID is valid UUID as per MB recommendations
            UUID(album.mb_albumid)
            self._log.info(u'Album ID is valid MBID...creating .nfos')
            albumid = 'mb_albumid:' + album.mb_albumid
            mb_albumid = album.mb_albumid
            mb_artistid = album.mb_albumartistid
            nfo_format = '{0}'.format(config['kodi']['nfo_format'])
            if nfo_format in 'mbid_only_text':
                self._log.info(u'Creating url only text format .nfo file...')
                album_nfo_text(albumid, mb_albumid, mb_artistid)
            else:
                self._log.info(u'creating XML format .nfo file...')
                album_nfo_xml(albumid)
                artist_nfo_xml(albumid)
        except ValueError:
            self._log.info(u"Album ID is not valid MBID...can't create .nfos")

    def listen_for_db_change(self, lib, model):
        """Listen for beets db change and register the update."""
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        """When client exists try sending refresh request to Kodi server."""
        self._log.info(u'Updating Kodi library...')

        # Try to send update request.
        try:
            update_kodi(
                config['kodi']['host'].get(),
                config['kodi']['port'].get(),
                config['kodi']['user'].get(),
                config['kodi']['pwd'].get())
            self._log.info(u'... started.')

        except requests.exceptions.RequestException:
            self._log.warning(u'Update failed.')
