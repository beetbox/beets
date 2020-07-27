# -*- coding: utf-8 -*-

"""Tests for the 'subsonic' plugin"""

from __future__ import division, absolute_import, print_function

import requests
import responses
import unittest

from test import _common
from beets import config
from beetsplug import subsonicupdate
from test.helper import TestHelper
from six.moves.urllib.parse import parse_qs, urlparse


class ArgumentsMock(object):
    def __init__(self, mode, show_failures):
        self.mode = mode
        self.show_failures = show_failures
        self.verbose = 1


def _params(url):
    """Get the query parameters from a URL."""
    return parse_qs(urlparse(url).query)


class SubsonicPluginTest(_common.TestCase, TestHelper):
    @responses.activate
    def setUp(self):
        config.clear()
        self.setup_beets()

        config["subsonic"]["user"] = "admin"
        config["subsonic"]["pass"] = "admin"
        config["subsonic"]["url"] = "http://localhost:4040"

        self.subsonicupdate = subsonicupdate.SubsonicUpdate()

    def tearDown(self):
        self.teardown_beets()

    @responses.activate
    def test_start_scan(self):
        responses.add(
            responses.POST, "http://localhost:4040/rest/startScan", status=200
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_extra_forward_slash_url(self):
        config["subsonic"]["url"] = "http://localhost:4040/contextPath"

        responses.add(
            responses.POST,
            "http://localhost:4040/contextPath/rest/startScan",
            status=200,
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_context_path(self):
        config["subsonic"]["url"] = "http://localhost:4040/"

        responses.add(
            responses.POST, "http://localhost:4040/rest/startScan", status=200
        )

        self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_missing_port(self):
        config["subsonic"]["url"] = "http://localhost/airsonic"

        responses.add(
            responses.POST, "http://localhost:4040/rest/startScan", status=200
        )

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.subsonicupdate.start_scan()

    @responses.activate
    def test_url_with_missing_schema(self):
        config["subsonic"]["url"] = "localhost:4040/airsonic"

        responses.add(
            responses.POST, "http://localhost:4040/rest/startScan", status=200
        )

        with self.assertRaises(requests.exceptions.InvalidSchema):
            self.subsonicupdate.start_scan()


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
