# -*- coding: utf-8 -*-

"""Tests for the 'subsonic' plugin."""

from __future__ import division, absolute_import, print_function

import responses
import unittest

from test import _common
from beets import config
from beetsplug import subsonicupdate
from test.helper import TestHelper
from six.moves.urllib.parse import parse_qs, urlparse


class ArgumentsMock(object):
    """Argument mocks for tests."""
    def __init__(self, mode, show_failures):
        """Constructs ArgumentsMock."""
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return parse_qs(urlparse(url).query)


class SubsonicPluginTest(_common.TestCase, TestHelper):
    """Test class for subsonicupdate."""
    @responses.activate
    def setUp(self):
        """Sets up config and plugin for test."""
        config.clear()
        self.setup_beets()

        config["subsonic"]["user"] = "admin"
        config["subsonic"]["pass"] = "admin"
        config["subsonic"]["url"] = "http://localhost:4040"

        self.subsonicupdate = subsonicupdate.SubsonicUpdate()

    SUCCESS_BODY = '''
{
    "subsonic-response": {
        "status": "ok",
        "version": "1.15.0",
        "scanStatus": {
            "scanning": true,
            "count": 1000
        }
    }
}
'''

    FAILED_BODY = '''
{
    "subsonic-response": {
        "status": "failed",
        "version": "1.15.0",
        "error": {
            "code": 40,
            "message": "Wrong username or password."
        }
    }
}
'''

    ERROR_BODY = '''
{
    "timestamp": 1599185854498,
    "status": 404,
    "error": "Not Found",
    "message": "No message available",
    "path": "/rest/startScn"
}
'''

    def tearDown(self):
        """Tears down tests."""
        self.teardown_beets()

    @responses.activate
    def test_start_scan(self):
        """Tests success path based on best case scenario."""
        responses.add(
            responses.GET,
            'http://localhost:4040/rest/startScan',
            status=200,
            body=self.SUCCESS_BODY
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_start_scan_failed_bad_credentials(self):
        """Tests failed path based on bad credentials."""
        responses.add(
            responses.GET,
            'http://localhost:4040/rest/startScan',
            status=200,
            body=self.FAILED_BODY
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_start_scan_failed_not_found(self):
        """Tests failed path based on resource not found."""
        responses.add(
            responses.GET,
            'http://localhost:4040/rest/startScan',
            status=404,
            body=self.ERROR_BODY
        )

        self.subsonicupdate.start_scan()

    def test_start_scan_failed_unreachable(self):
        """Tests failed path based on service not available."""
        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_context_path(self):
        """Tests success for included with contextPath."""
        config["subsonic"]["url"] = "http://localhost:4040/contextPath/"

        responses.add(
            responses.GET,
            'http://localhost:4040/contextPath/rest/startScan',
            status=200,
            body=self.SUCCESS_BODY
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_trailing_forward_slash_url(self):
        """Tests success path based on trailing forward slash."""
        config["subsonic"]["url"] = "http://localhost:4040/"

        responses.add(
            responses.GET,
            'http://localhost:4040/rest/startScan',
            status=200,
            body=self.SUCCESS_BODY
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_missing_port(self):
        """Tests failed path based on missing port."""
        config["subsonic"]["url"] = "http://localhost/airsonic"

        responses.add(
            responses.GET,
            'http://localhost/airsonic/rest/startScan',
            status=200,
            body=self.SUCCESS_BODY
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_missing_schema(self):
        """Tests failed path based on missing schema."""
        config["subsonic"]["url"] = "localhost:4040/airsonic"

        responses.add(
            responses.GET,
            'http://localhost:4040/rest/startScan',
            status=200,
            body=self.SUCCESS_BODY
        )

        self.subsonicupdate.start_scan()


def suite():
    """Default test suite."""
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
