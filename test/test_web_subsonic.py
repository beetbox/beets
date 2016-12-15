# -*- coding: utf-8 -*-

"""Tests for the 'subsonic' part of the 'web' plugin"""

from __future__ import division, absolute_import, print_function

import re
import unittest

import xmlunittest as xmlunittest

from beetsplug import web
from beetsplug.web.subsonic import subsonic_routes
from test.helper import TestHelper

re_lm = re.compile(b'lastModified="(\d+?)"', re.MULTILINE)
re_cr = re.compile(b'created="(.+?)"', re.MULTILINE)


class WebSubsonicPluginTest(unittest.TestCase, xmlunittest.XmlTestMixin,
                            TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('web')
        web.app.register_blueprint(subsonic_routes)

        # Add fixtures
        album = self.add_album_fixture(track_count=10)
        album.update({'albumartist': u'artist1', 'album': u'album1'})
        album.store()
        album = self.add_album_fixture(track_count=2)
        album.update({'albumartist': u'artist2', 'album': u'album2'})
        album.store()

        web.app.config['TESTING'] = True
        web.app.config['lib'] = self.lib
        self.client = web.app.test_client()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_ping(self):
        response = self.client.get('/rest/ping.view')
        self.assertEqual(response.status_code, 200)

    def test_license(self):
        rv = self.client.get('/rest/getLicense.view')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="ok" xmlns="http://subsonic.org/restapi">
            <license valid="true"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

    def test_get_music_folders(self):
        rv = self.client.get('/rest/getMusicFolders.view')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="ok" xmlns="http://subsonic.org/restapi">
            <musicFolders>
                <musicFolder id="1" name="Music"/>
            </musicFolders>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

    def test_get_artists(self):
        rv = self.client.get('/rest/getArtists.view')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" version="1.10.1" status="ok">
            <indexes lastModified="%s" ignoredArticles="">
                <index name="A">
                    <artist albumCount="1" name="artist1" id="ARartist1"/>
                    <artist albumCount="1" name="artist2" id="ARartist2"/>
                </index>
            </indexes>
        </subsonic-response>'''  # NOQA
        # fix lastModified because it's not an important value,
        # otherwise it fails the assertion
        groups = re_lm.search(rv.data)
        self.assertXmlEquivalentOutputs(
            subject.replace(b'%s', groups.group(1)), rv.data)

    def test_get_music_directory(self):
        rv = self.client.get('/rest/getMusicDirectory.view?id=INVALIDID')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="failed" version="1.10.1">
            <error code="10" message="Missing or invalid id"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getMusicDirectory.view?id=ARartist1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="ok" version="1.10.1">
            <directory name="artist1" id="ARartist1">
                <child coverArt="AL1" year="2001" title="album1 (2001)"  averageRating="0" artist="artist1" parent="ARartist1" artistId="ARartist1" isDir="true" duration="10" id="AL1"/>
            </directory>
        </subsonic-response>'''  # NOQA
        # fix created date value
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        rv = self.client.get('/rest/getMusicDirectory.view?id=ALalbum1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="ok" xmlns="http://subsonic.org/restapi">
            <directory id="ALalbum1" name="album1">
                <child id="TR1" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 0" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR2" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 1" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR3" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 2" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR4" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 3" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR5" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 4" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR6" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 5" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR7" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 6" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR8" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 7" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR9" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 8" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
                <child id="TR10" track="2" size="12820" artistId="ARartist1" isDir="false" title="t\xc3\xaftle 9" type="music" contentType="audio/mpeg" artist="artist1" albumId="AL1" year="2001" duration="1" genre="the genre" album="album1" bitRate="80" parent="AL1" isVideo="false" covertArt="AL1"/>
            </directory>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_get_artist(self):
        rv = self.client.get('/rest/getArtist.view?id=AR0')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="failed" version="1.10.1">
            <error message="Artist not found" code="70"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getArtist.view?id=ALalbum1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="failed" xmlns="http://subsonic.org/restapi">
            <error message="Missing or invalid Artist id" code="10"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getArtist.view?id=ARartist1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="ok" version="1.10.1">
            <artist id="ARartist1" albumCount="1" name="artist1">
                <album songCount="10" duration="10" id="AL1" averageRating="0" name="album1" coverArt="AL1" artist="artist1" artistId="ARartist1" year="2001"/>
            </artist>
        </subsonic-response>'''  # NOQA
        # fix created date value
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_get_album(self):
        rv = self.client.get('/rest/getAlbum.view?id=AL0')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <error message="Album not found" code="70"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getAlbum.view?id=AR0')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="failed" xmlns="http://subsonic.org/restapi">
            <error code="10" message="Missing or invalid Album id"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getAlbum.view?id=AL1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <album songCount="10" name="1" id="AL1">
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 0" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR1" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 1" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR2" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 2" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR3" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 3" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR4" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 4" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR5" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 5" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR6" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 6" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR7" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 7" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR8" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 8" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR9" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
                <song bitRate="80" parent="AL1" title="t\xc3\xaftle 9" artist="artist1" album="album1" isVideo="false" duration="1" type="music" isDir="false" year="2001" id="TR10" size="12820" albumId="AL1" genre="the genre" artistId="ARartist1" covertArt="AL1" contentType="audio/mpeg" track="2"/>
            </album>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_get_song(self):
        rv = self.client.get('/rest/getSong.view?id=AR0')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <error message="Missing or invalid Song id" code="10"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getSong.view?id=TR0')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <error code="70" message="Song not found"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        rv = self.client.get('/rest/getSong.view?id=TR1')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="ok" xmlns="http://subsonic.org/restapi">
            <song duration="1" artist="artist1" album="album1" isVideo="false" title="t\xc3\xaftle 0" bitRate="80" year="2001" isDir="false" artistId="ARartist1" contentType="audio/mpeg" genre="the genre" parent="AL1" type="music" track="2" albumId="AL1" size="12820" covertArt="AL1" id="TR1"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_get_album_list(self):
        """
            str             type in ['random', 'newest', 'highest', 'frequent',
                                    'recent', 'starred', 'alphabeticalByName',
                                    'alphabeticalByArtist', 'byYear', 'genre']
            int optionnal   size (default 10)
            int optionnal   offset (default 0)
            int optionnal   fromYear
            int optionnal   toYear
            str optionnal   genre
        """
        # No parameters
        rv = self.client.get('/rest/getAlbumList.view')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error message="Missing parameter type" code="10"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # Parameter type not in whitelist
        rv = self.client.get('/rest/getAlbumList.view?type=whatever')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <error code="0" message="Invalid value whatever for parameter type"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # type == 'byYear' and no fromYear parameter
        rv = self.client.get('/rest/getAlbumList.view?type=byYear&toYear=2010')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error message="Missing parameter fromYear or toYear" code="10"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # type == 'byYear' and no toYear parameter
        rv = self.client.get(
            '/rest/getAlbumList.view?type=byYear&fromYear=2010')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error message="Missing parameter fromYear or toYear" code="10"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # type == 'byYear' and invalid fromYear
        rv = self.client.get(
            '/rest/getAlbumList.view?type=byYear&fromYear=test&toYear=2012')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error message="Invalid parameter fromYear" code="0"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # type == 'genre' and no genre parameter
        rv = self.client.get('/rest/getAlbumList.view?type=genre')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error code="10" message="Missing parameter genre"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # Can't really test type == 'random'

        # type == 'newest'
        rv = self.client.get('/rest/getAlbumList.view?type=newest')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <albumList>
                <album title="album2 (2001)" duration="2" isDir="true" coverArt="AL2" averageRating="0" artist="artist2" year="2001" id="AL2" parent="ARartist2" artistId="ARartist2"/>
                <album title="album1 (2001)" duration="10" isDir="true" coverArt="AL1" averageRating="0" artist="artist1" year="2001" id="AL1" parent="ARartist1" artistId="ARartist1"/>
            </albumList>
        </subsonic-response>'''  # NOQA
        # fix created date value
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        # type == 'highest'
        rv = self.client.get('/rest/getAlbumList.view?type=highest')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="ok" version="1.10.1">
            <albumList>
                <album duration="10" year="2001" parent="ARartist1" averageRating="0" title="album1 (2001)" isDir="true" coverArt="AL1" artist="artist1" id="AL1" artistId="ARartist1"/>
                <album duration="2" year="2001" parent="ARartist2" averageRating="0" title="album2 (2001)" isDir="true" coverArt="AL2" artist="artist2" id="AL2" artistId="ARartist2"/>
            </albumList>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))
        # type == 'frequent'
        rv = self.client.get('/rest/getAlbumList.view?type=frequent')
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))
        # type == 'recent'
        rv = self.client.get('/rest/getAlbumList.view?type=recent')
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        # type == 'starred'
        rv = self.client.get('/rest/getAlbumList.view?type=starred')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" version="1.10.1" status="ok">
            <albumList></albumList>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # type == 'alphabeticalByName'
        rv = self.client.get('/rest/getAlbumList.view?type=alphabeticalByName')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <albumList>
                <album duration="10" isDir="true" year="2001" id="AL1" averageRating="0" coverArt="AL1" parent="ARartist1" artistId="ARartist1" artist="artist1" title="album1 (2001)"/>
                <album duration="2" isDir="true" year="2001" id="AL2" averageRating="0" coverArt="AL2" parent="ARartist2" artistId="ARartist2" artist="artist2" title="album2 (2001)"/>
            </albumList>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        # type == 'alphabeticalByArtist'
        rv = self.client.get(
            '/rest/getAlbumList.view?type=alphabeticalByArtist')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response version="1.10.1" status="ok" xmlns="http://subsonic.org/restapi">
            <albumList>
                <album duration="10" title="album1 (2001)" year="2001" artistId="ARartist1" parent="ARartist1" coverArt="AL1" id="AL1"  isDir="true" artist="artist1" averageRating="0"/>
                <album duration="2" title="album2 (2001)" year="2001" artistId="ARartist2" parent="ARartist2" coverArt="AL2" id="AL2"  isDir="true" artist="artist2" averageRating="0"/>
            </albumList>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_get_album_list2(self):
        # type == 'newest'
        rv = self.client.get('/rest/getAlbumList2.view?type=newest')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <albumList2>
                <album songCount="2" duration="2" id="AL2" coverArt="AL2" name="album2" artistId="ARartist2" year="2001" averageRating="0" artist="artist2"/>
                <album songCount="10" duration="10" id="AL1" coverArt="AL1" name="album1" artistId="ARartist1" year="2001" averageRating="0" artist="artist1"/>
            </albumList2>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

    def test_search2_3(self):
        """
            str             query
            int optionnal   artistCount (default 20)
            int optionnal   artistOffset (default 0)
            int optionnal   albumCount (default 20)
            int optionnal   albumOffset (default 0)
            int optionnal   songCount (default 20)
            int optionnal   songOffset (default 0)
        """
        # No query parameter
        rv = self.client.get('/rest/search2.view')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="failed" xmlns="http://subsonic.org/restapi" version="1.10.1">
            <error code="10" message="Missing query parameter"/>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # query == 'ar'
        rv = self.client.get('/rest/search2.view?query=ar')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <searchResult2>
                <artist id="ARartist1" name="artist1" albumCount="1" />
                <artist id="ARartist2" name="artist2" albumCount="1" />
            </searchResult2>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)

        # query == 'al'
        rv = self.client.get('/rest/search2.view?query=al')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <searchResult2>
                <album year="2001" artistId="ARartist1" coverArt="AL1" averageRating="0" artist="artist1" id="AL1" name="album1" duration="10" songCount="10" />
                <album year="2001" artistId="ARartist2" coverArt="AL2" averageRating="0" artist="artist2" id="AL2" name="album2" duration="2" songCount="2" />
            </searchResult2>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        # query == 'tïtle'
        rv = self.client.get(u'/rest/search2.view?query=tïtle')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response status="ok" version="1.10.1" xmlns="http://subsonic.org/restapi">
            <searchResult2>
                <track id="TR1" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 0" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR2" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 1" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR3" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 2" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR4" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 3" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR5" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 4" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR6" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 5" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR7" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 6" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR8" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 7" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR9" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 8" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR10" artistId="ARartist1" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 9" genre="the genre" artist="artist1" type="music" covertArt="AL1" parent="AL1" isVideo="false" album="album1" albumId="AL1" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR11" artistId="ARartist2" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 0" genre="the genre" artist="artist2" type="music" covertArt="AL2" parent="AL2" isVideo="false" album="album2" albumId="AL2" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
                <track id="TR12" artistId="ARartist2" duration="1" contentType="audio/mpeg" title="t\xc3\xaftle 1" genre="the genre" artist="artist2" type="music" covertArt="AL2" parent="AL2" isVideo="false" album="album2" albumId="AL2" bitRate="80" isDir="false" year="2001" size="12820" track="2"/>
            </searchResult2>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, re_cr.sub(b"", rv.data))

        # query == 'NOTHING'
        rv = self.client.get('/rest/search2.view?query=NOTHING')
        subject = b'''<?xml version="1.0" encoding="UTF-8"?>
        <subsonic-response xmlns="http://subsonic.org/restapi" status="ok" version="1.10.1">
            <searchResult2></searchResult2>
        </subsonic-response>'''  # NOQA
        self.assertXmlEquivalentOutputs(subject, rv.data)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
