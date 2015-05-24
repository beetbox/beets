from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from test._common import unittest
from test.helper import TestHelper
from beetsplug.plexupdate import get_music_section, update_plex
import responses


class PlexUpdateTest(unittest.TestCase, TestHelper):
    def add_response_get_music_section(self):
        """Create response for mocking the get_music_section function.
        """
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<MediaContainer size="3" allowSync="0" '
            'identifier="com.plexapp.plugins.library" '
            'mediaTagPrefix="/system/bundle/media/flags/" '
            'mediaTagVersion="1413367228" title1="Plex Library">'
            '<Directory allowSync="0" art="/:/resources/movie-fanart.jpg" '
            'filters="1" refreshing="0" thumb="/:/resources/movie.png" '
            'key="3" type="movie" title="Movies" '
            'composite="/library/sections/3/composite/1416232668" '
            'agent="com.plexapp.agents.imdb" scanner="Plex Movie Scanner" '
            'language="de" uuid="92f68526-21eb-4ee2-8e22-d36355a17f1f" '
            'updatedAt="1416232668" createdAt="1415720680">'
            '<Location id="3" path="/home/marv/Media/Videos/Movies" />'
            '</Directory>'
            '<Directory allowSync="0" art="/:/resources/artist-fanart.jpg" '
            'filters="1" refreshing="0" thumb="/:/resources/artist.png" '
            'key="2" type="artist" title="Music" '
            'composite="/library/sections/2/composite/1416929243" '
            'agent="com.plexapp.agents.lastfm" scanner="Plex Music Scanner" '
            'language="en" uuid="90897c95-b3bd-4778-a9c8-1f43cb78f047" '
            'updatedAt="1416929243" createdAt="1415691331">'
            '<Location id="2" path="/home/marv/Media/Musik" />'
            '</Directory>'
            '<Directory allowSync="0" art="/:/resources/show-fanart.jpg" '
            'filters="1" refreshing="0" thumb="/:/resources/show.png" '
            'key="1" type="show" title="TV Shows" '
            'composite="/library/sections/1/composite/1416320800" '
            'agent="com.plexapp.agents.thetvdb" scanner="Plex Series Scanner" '
            'language="de" uuid="04d2249b-160a-4ae9-8100-106f4ec1a218" '
            'updatedAt="1416320800" createdAt="1415690983">'
            '<Location id="1" path="/home/marv/Media/Videos/Series" />'
            '</Directory>'
            '</MediaContainer>')
        status = 200
        content_type = 'text/xml;charset=utf-8'

        responses.add(responses.GET,
                      'http://localhost:32400/library/sections',
                      body=body,
                      status=status,
                      content_type=content_type)

    def add_response_update_plex(self):
        """Create response for mocking the update_plex function.
        """
        body = ''
        status = 200
        content_type = 'text/html'

        responses.add(responses.GET,
                      'http://localhost:32400/library/sections/2/refresh',
                      body=body,
                      status=status,
                      content_type=content_type)

    def setUp(self):
        self.setup_beets()
        self.load_plugins('plexupdate')

        self.config['plex'] = {
            u'host': u'localhost',
            u'port': 32400}

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    @responses.activate
    def test_get_music_section(self):
        # Adding response.
        self.add_response_get_music_section()

        # Test if section key is "2" out of the mocking data.
        self.assertEqual(get_music_section(
            self.config['plex']['host'],
            self.config['plex']['port']), '2')

    @responses.activate
    def test_update_plex(self):
        # Adding responses.
        self.add_response_get_music_section()
        self.add_response_update_plex()

        # Testing status code of the mocking request.
        self.assertEqual(update_plex(
            self.config['plex']['host'],
            self.config['plex']['port']).status_code, 200)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
