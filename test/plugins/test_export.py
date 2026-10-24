"""Test the beets.export utilities associated with the export plugin."""

import csv
import io
import json
import re  # used to test csv format
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from beets.test.helper import IOMixin, PluginTestCase


class ExportPluginTest(IOMixin, PluginTestCase):
    plugin = "export"

    def setUp(self):
        super().setUp()
        self.test_values = {"title": "xtitle", "album": "xalbum"}

    def execute_command(self, format_type, artist):
        query = ",".join(self.test_values.keys())
        return self.run_with_output(
            "export", "-f", format_type, "-i", query, artist
        )

    def create_item(self):
        (item,) = self.add_item_fixtures()
        item.artist = "xartist"
        item.title = self.test_values["title"]
        item.album = self.test_values["album"]
        item.write()
        item.store()
        return item

    def test_json_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="json", artist=item1.artist)
        json_data = json.loads(out)[0]
        for key, val in self.test_values.items():
            assert key in json_data
            assert val == json_data[key]

    def test_jsonlines_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="jsonlines", artist=item1.artist)
        json_data = json.loads(out)
        for key, val in self.test_values.items():
            assert key in json_data
            assert val == json_data[key]

    def test_csv_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="csv", artist=item1.artist)
        csv_list = re.split("\r", re.sub("\n", "", out))
        head = re.split(",", csv_list[0])
        vals = re.split(",|\r", csv_list[1])
        for index, column in enumerate(head):
            assert self.test_values.get(column, None) is not None
            assert vals[index] == self.test_values[column]

    def test_xml_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="xml", artist=item1.artist)
        library = ElementTree.fromstring(out)
        assert isinstance(library, Element)
        for track in library[0]:
            for details in track:
                tag = details.tag
                txt = details.text
                assert tag in self.test_values, tag
                assert self.test_values[tag] == txt, txt

    def test_include_key_patterns_for_tags(self):
        item = self.create_item()
        item.mb_trackid = "track-id"
        item.write()
        item.store()
        data = json.loads(
            self.run_with_output("export", "-i", "title,mb*", item.artist)
        )[0]
        assert data["title"] == item.title
        assert data["mb_trackid"] == "track-id"
        assert "mb*" not in data
        assert all(key == "title" or key.startswith("mb") for key in data)

    def test_include_key_patterns_for_library_flexible_fields(self):
        item = self.create_item()
        item["mb_custom"] = "custom-value"
        item.store()
        data = json.loads(
            self.run_with_output(
                "export",
                "--library",
                "-i",
                "title,mb*",
                "-i",
                "mb_custom",
                item.artist,
            )
        )[0]
        assert data["title"] == item.title
        assert data["mb_custom"] == "custom-value"
        assert "mb*" not in data
        assert all(key == "title" or key.startswith("mb") for key in data)

    def test_unmatched_key_pattern_exports_no_fields(self):
        item = self.create_item()
        data = json.loads(
            self.run_with_output("export", "-i", "no_such_field_*", item.artist)
        )
        assert data == [{}]

    def test_star_key_pattern_exports_available_fields(self):
        item = self.create_item()
        data = json.loads(
            self.run_with_output("export", "-i", "*", item.artist)
        )[0]
        assert data["title"] == item.title
        assert data["album"] == item.album
        assert "*" not in data

    def test_question_mark_key_pattern(self):
        item = self.create_item()
        data = json.loads(
            self.run_with_output(
                "export", "--library", "-i", "titl?", item.artist
            )
        )[0]
        assert data == {"title": item.title}

    def test_include_key_patterns_for_album_fields(self):
        item = self.create_item()
        album = self.lib.add_album([item])
        album["mb_custom"] = "album-value"
        album.store()
        data = json.loads(
            self.run_with_output(
                "export", "--album", "-i", "album,mb*", "album:xalbum"
            )
        )[0]
        assert data["album"] == item.album
        assert data["mb_custom"] == "album-value"
        assert "mb*" not in data
        assert all(key == "album" or key.startswith("mb") for key in data)

    def test_include_key_patterns_in_csv(self):
        item = self.create_item()
        output = self.run_with_output(
            "export", "-f", "csv", "-i", "titl?,alb[ua]m", item.artist
        )
        assert list(csv.DictReader(io.StringIO(output))) == [self.test_values]
