# This file is part of beets.
# Copyright 2016, Adrian Sampson and Diego Moreda.
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
import unittest
from unittest.mock import patch
from urllib.parse import urljoin

import jwt
import requests

import beets.plugins
from beets.test._common import item
from beets.test.helper import (
    AutotagStub,
    ImportHelper,
    TerminalImportSessionSetup,
    TestHelper,
    capture_stdout,
    control_stdin,
)
from beetsplug import mbsubmit
from beetsplug.mbsubmit import CreateReleaseTask, MBSubmitPlugin


class MBSubmitPluginTest(
    TerminalImportSessionSetup, unittest.TestCase, ImportHelper, TestHelper
):
    def setUp(self):
        self.setup_beets()
        self.load_plugins("mbsubmit")
        self._create_import_dir(2)
        self._setup_import_session()
        self.matcher = AutotagStub().install()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()
        self.matcher.restore()

    def test_print_tracks_output(self):
        """Test the output of the "print tracks" choice."""
        self.matcher.matching = AutotagStub.BAD

        with capture_stdout() as output:
            with control_stdin("\n".join(["p", "s"])):
                # Print tracks; Skip
                self.importer.run()

        # Manually build the string for comparing the output.
        tracklist = (
            "Create release on musicbrainz? "
            "01. Tag Title 1 - Tag Artist (0:01)\n"
            "02. Tag Title 2 - Tag Artist (0:01)"
        )
        self.assertIn(tracklist, output.getvalue())

    def test_print_tracks_output_as_tracks(self):
        """Test the output of the "print tracks" choice, as singletons."""
        self.matcher.matching = AutotagStub.BAD

        with capture_stdout() as output:
            with control_stdin("\n".join(["t", "s", "p", "s"])):
                # as Tracks; Skip; Print tracks; Skip
                self.importer.run()

        # Manually build the string for comparing the output.
        tracklist = (
            "Open files with Picard? " "02. Tag Title 2 - Tag Artist (0:01)"
        )
        self.assertIn(tracklist, output.getvalue())

    @patch.object(MBSubmitPlugin, "_wait_for_condition", autospec=True)
    @patch("beetsplug.mbsubmit.ThreadingHTTPServer")
    def test_create_release(self, start_server_mock, wait_for_condition_mock):
        self.matcher.matching = AutotagStub.BAD

        def _wait_for_condition(plugin: MBSubmitPlugin, condition):
            self.assertEqual(1, len(plugin.create_release_tasks))
            task_id = list(plugin.create_release_tasks.keys())[0]
            if wait_for_condition_mock.call_count == 1:
                plugin.create_release_tasks[task_id].browser_opened = True
            if wait_for_condition_mock.call_count == 2:
                plugin.create_release_tasks[task_id].result_release_mbid = (
                    "new_id"
                )

        wait_for_condition_mock.side_effect = _wait_for_condition

        with control_stdin("\n".join(["c", "s"])):
            # Create release on MusicBrainz, Skip
            self.importer.run()

        self.assertEqual(2, wait_for_condition_mock.call_count)

    def test_create_release_server_add(self):

        plugin = MBSubmitPlugin()

        self.assertTrue(plugin._start_server())
        self.server_url = f"http://127.0.0.1:{plugin._server.server_port}"

        try:


            r = requests.get(self.server_url)
            self.assertEqual(404, r.status_code)

            r = requests.get(urljoin(self.server_url, "/add"))
            self.assertEqual(400, r.status_code)
            self.assertEqual("Token missing.", r.text)

            r = requests.get(urljoin(self.server_url, "/add?token=12356"))
            self.assertEqual(400, r.status_code)
            self.assertEqual("Invalid token.", r.text)

            token = jwt.encode(
                {"task_key": "unique_key"},
                plugin.jwt_key,
                algorithm=plugin.jwt_algorithm,
            )

            r = requests.get(urljoin(self.server_url, f"/add?token={token}"))
            self.assertEqual(404, r.status_code)
            self.assertEqual("task_key not found.", r.text)

            task = CreateReleaseTask(
                {"a": 1, "b": "Something'test\"", "c": 6767.74}
            )
            plugin.create_release_tasks["unique_key"] = task

            self.assertFalse(task.browser_opened)

            r = requests.get(urljoin(self.server_url, f"/add?token={token}"))
            self.assertEqual(200, r.status_code)
            self.assertIn('<input type="hidden" name="a" value="1">', r.text)
            self.assertIn(
                '<input type="hidden" name="b" value="Something&#x27;test&quot;">',
                r.text,
            )
            self.assertIn('<input type="hidden" name="c" value="6767.74">', r.text)

            self.assertTrue(task.browser_opened)

            r = requests.get(urljoin(self.server_url, f"/complete_add"))
            self.assertEqual(400, r.status_code)
            self.assertEqual("Token missing.", r.text)

            r = requests.get(urljoin(self.server_url, "/complete_add?token=12356"))
            self.assertEqual(400, r.status_code)
            self.assertEqual("Invalid token.", r.text)

            r = requests.get(
                urljoin(self.server_url, f"/complete_add?token={token}")
            )
            self.assertEqual(400, r.status_code)
            self.assertEqual("release_mbid missing.", r.text)

            self.assertIsNone(task.result_release_mbid)

            r = requests.get(
                urljoin(
                    self.server_url,
                    f"/complete_add?token={token}&release_mbid=the_new_id",
                )
            )
            self.assertEqual(200, r.status_code)
            self.assertEqual(
                "Release the_new_id added. You can close this browser window now and return to beets.",
                r.text,
            )

            self.assertEqual("the_new_id", task.result_release_mbid)
        finally:
            plugin._stop_server()

    def test_build_formdata(self):
        self.assertDictEqual({}, mbsubmit.build_formdata([], None))
        self.assertDictEqual(
            {"redirect_uri": "redirect_to_somewhere"},
            mbsubmit.build_formdata([], "redirect_to_somewhere"),
        )

        item1 = item(self.lib)
        item1.track = 1
        item1.title = "Track 1"
        item1.albumtype = "Album"
        item1.barcode = 1234567890
        item1.media = "CD"

        item2 = item(self.lib)
        item2.track = 2
        item2.artists = ["a", "b"]
        item2.title = "Track 2"
        item2.albumtype = "Album"
        item2.barcode = 1234567890
        item2.media = "CD"

        item3 = item(self.lib)
        item3.track = 3
        item3.disc = None
        item3.artists = ["a", "b", "c"]
        item3.title = "Track 3"
        item3.albumtype = "Album"
        item3.barcode = 1234567890
        item3.media = "Digital Media"

        self.maxDiff = None

        self.assertDictEqual(
            {
                "name": "the album",
                "barcode": "1234567890",
                "type": "Album",
                "events.0.date.year": 1,
                "events.0.date.month": 2,
                "events.0.date.day": 3,
                "artist_credit.names.0.artist.name": "the album artist",
                "mediums.5.format": "CD",
                "mediums.5.track.0.artist_credit.names.0.artist.name": "the artist",
                "mediums.5.track.0.length": 60000,
                "mediums.5.track.0.name": "Track 1",
                "mediums.5.track.0.number": 1,
                "mediums.5.track.1.artist_credit.names.0.artist.name": "a",
                "mediums.5.track.1.artist_credit.names.0.join_phrase": " & ",
                "mediums.5.track.1.artist_credit.names.1.artist.name": "b",
                "mediums.5.track.1.length": 60000,
                "mediums.5.track.1.name": "Track 2",
                "mediums.5.track.1.number": 2,
                "mediums.0.format": "Digital Media",
                "mediums.0.track.0.artist_credit.names.0.artist.name": "a",
                "mediums.0.track.0.artist_credit.names.0.join_phrase": ", ",
                "mediums.0.track.0.artist_credit.names.1.artist.name": "b",
                "mediums.0.track.0.artist_credit.names.1.join_phrase": " & ",
                "mediums.0.track.0.artist_credit.names.2.artist.name": "c",
                "mediums.0.track.0.length": 60000,
                "mediums.0.track.0.name": "Track 3",
                "mediums.0.track.0.number": 3,
            },
            mbsubmit.build_formdata([item1, item2, item3], None),
        )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main(defaultTest="suite")
