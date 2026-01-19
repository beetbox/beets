# This file is part of beets.
# Copyright 2017, Dorian Soergel
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

"""Tests for the 'parentwork' plugin."""

import pytest

from beets.library import Item
from beets.test.helper import PluginTestCase


@pytest.mark.integration_test
class ParentWorkIntegrationTest(PluginTestCase):
    plugin = "parentwork"

    # test how it works with real musicbrainz data
    def test_normal_case_real(self):
        item = Item(
            path="/file",
            mb_workid="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
            parentwork_workid_current="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
        )
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "32c8943f-1b27-3a23-8660-4567f4847c94"

    def test_force_real(self):
        self.config["parentwork"]["force"] = True
        item = Item(
            path="/file",
            mb_workid="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
            mb_parentworkid="XXX",
            parentwork_workid_current="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
            parentwork="whatever",
        )
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "32c8943f-1b27-3a23-8660-4567f4847c94"

    def test_no_force_real(self):
        self.config["parentwork"]["force"] = False
        item = Item(
            path="/file",
            mb_workid="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
            mb_parentworkid="XXX",
            parentwork_workid_current="e27bda6e-531e-36d3-9cd7-b8ebc18e8c53",
            parentwork="whatever",
        )
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "XXX"


class ParentWorkTest(PluginTestCase):
    plugin = "parentwork"

    @pytest.fixture(autouse=True)
    def patch_works(self, requests_mock):
        requests_mock.get(
            "/ws/2/work/1?inc=work-rels%2Bartist-rels",
            json={
                "id": "1",
                "title": "work",
                "work-relations": [
                    {
                        "type": "parts",
                        "direction": "backward",
                        "work": {"id": "2"},
                    }
                ],
            },
        )
        requests_mock.get(
            "/ws/2/work/2?inc=work-rels%2Bartist-rels",
            json={
                "id": "2",
                "title": "directparentwork",
                "work-relations": [
                    {
                        "type": "parts",
                        "direction": "backward",
                        "work": {"id": "3"},
                    }
                ],
            },
        )
        requests_mock.get(
            "/ws/2/work/3?inc=work-rels%2Bartist-rels",
            json={
                "id": "3",
                "title": "parentwork",
                "artist-relations": [
                    {
                        "type": "composer",
                        "artist": {
                            "name": "random composer",
                            "sort-name": "composer, random",
                        },
                    }
                ],
            },
        )

    def test_normal_case(self):
        item = Item(path="/file", mb_workid="1", parentwork_workid_current="1")
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "3"

    def test_force(self):
        self.config["parentwork"]["force"] = True
        item = Item(
            path="/file",
            mb_workid="1",
            mb_parentworkid="XXX",
            parentwork_workid_current="1",
            parentwork="parentwork",
        )
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "3"

    def test_no_force(self):
        self.config["parentwork"]["force"] = False
        item = Item(
            path="/file",
            mb_workid="1",
            mb_parentworkid="XXX",
            parentwork_workid_current="1",
            parentwork="parentwork",
        )
        item.add(self.lib)

        self.run_command("parentwork")

        item.load()
        assert item["mb_parentworkid"] == "XXX"
