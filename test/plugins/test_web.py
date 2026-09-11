"""Tests for the 'web' plugin"""

import json
import platform
import shutil
from collections import Counter
from pathlib import Path

import pytest

from beets.library import Album, Item
from beets.test import _common
from beets.test.helper import PluginMixin, PytestTestHelper
from beetsplug import web


class WebPluginMixin(PluginMixin):
    """Mixin to configure the web plugin for testing."""

    plugin = "web"

    @pytest.fixture(autouse=True)
    def setup_web_app(self, setup):
        """Configure the web plugin's Flask app for testing.

        This fixture sets up the Flask test client and configures the app
        with the test library. It runs after the base setup fixture from
        PytestTestHelper.
        """
        # Set up the web app config - we modify self.config["web"] for beets config
        # but also need to directly configure the Flask app for tests
        web.app.config["TESTING"] = True
        web.app.config["lib"] = self.lib
        web.app.config["INCLUDE_PATHS"] = False
        web.app.config["READONLY"] = True
        self.client = web.app.test_client()

        # Set platform-specific path prefix
        self.path_prefix = Path(
            "C:\\" if platform.system() == "Windows" else "/"
        )

        # Add library elements. Note that self.lib.add overrides any "id=<n>"
        # and assigns the next free id number.
        # The following adds will create items #1, #2 and #3
        self.path1 = self.path_prefix / "path_1"
        self.lib.add(
            Item(
                title="title", path=self.path1, album_id=2, artist="AAA Singers"
            )
        )
        self.path2 = self.path_prefix / "somewhere" / "a"
        self.lib.add(
            Item(title="another title", path=self.path2, artist="AAA Singers")
        )
        self.path3 = self.path_prefix / "somewhere" / "abc"
        self.lib.add(
            Item(
                title="and a third", testattr="ABC", path=self.path3, album_id=2
            )
        )
        # The following adds will create albums #1 and #2
        self.lib.add(Album(album="album", albumtest="xyz"))
        self.path4 = self.path_prefix / "somewhere2" / "art_path_2"
        self.lib.add(Album(album="other album", artpath=self.path4))

        return


class TestWebPlugin(WebPluginMixin, PytestTestHelper):
    """Tests for the web plugin."""

    def test_config_include_paths_true(self):
        web.app.config["INCLUDE_PATHS"] = True
        response = self.client.get("/item/1")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["path"] == str(self.path1)

        web.app.config["INCLUDE_PATHS"] = False

    def test_config_include_artpaths_true(self):
        web.app.config["INCLUDE_PATHS"] = True
        response = self.client.get("/album/2")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["artpath"] == str(self.path4)

        web.app.config["INCLUDE_PATHS"] = False

    def test_config_include_paths_false(self):
        web.app.config["INCLUDE_PATHS"] = False
        response = self.client.get("/item/1")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert "path" not in res_json

    def test_config_include_artpaths_false(self):
        web.app.config["INCLUDE_PATHS"] = False
        response = self.client.get("/album/2")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert "artpath" not in res_json

    def test_get_all_items(self):
        response = self.client.get("/item/")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["items"]) == 3

    def test_get_unique_item_artist(self):
        response = self.client.get("/item/values/artist")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["values"] == ["", "AAA Singers"]

    def test_get_single_item_by_id(self):
        response = self.client.get("/item/1")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["id"] == 1
        assert res_json["title"] == "title"

    def test_get_multiple_items_by_id(self):
        response = self.client.get("/item/1,2")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["items"]) == 2
        response_titles = {item["title"] for item in res_json["items"]}
        assert response_titles == {"title", "another title"}

    def test_get_single_item_not_found(self):
        response = self.client.get("/item/4")
        assert response.status_code == 404

    def test_get_single_item_by_path(self):
        data_path = _common.RSRC / "full.mp3"
        self.lib.add(Item.from_path(data_path))
        response = self.client.get(f"/item/path/{data_path}")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["title"] == "full"

    def test_get_single_item_by_path_not_found_if_not_in_library(self):
        data_path = _common.RSRC / "full.mp3"
        # data_path points to a valid file, but we have not added the file
        # to the library.
        response = self.client.get(f"/item/path/{data_path}")

        assert response.status_code == 404

    def test_get_item_empty_query(self):
        response = self.client.get("/item/query/")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["items"]) == 3

    def test_get_simple_item_query(self):
        response = self.client.get("/item/query/another")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["title"] == "another title"

    def test_query_item_string(self):
        response = self.client.get("/item/query/testattr%3aABC")  # testattr:ABC
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["title"] == "and a third"

    def test_query_item_regex(self):
        response = self.client.get(
            "/item/query/testattr%3a%3a[A-C]%2b"
        )  # testattr::[A-C]+
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["title"] == "and a third"

    def test_query_item_regex_backslash(self):
        response = self.client.get(
            "/item/query/testattr%3a%3a%5cw%2b"
        )  # testattr::\w+
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["title"] == "and a third"

    def test_query_item_path(self):
        """Note: path queries are special: the query item must match the path
        from the root all the way to a directory, so this matches 1 item"""
        """ Note: filesystem separators in the query must be '\' """

        prefix = "C:" if platform.system() == "Windows" else ""
        response = self.client.get(f"/item/query/path:{prefix}\\somewhere\\a")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["title"] == "another title"

    def test_get_all_albums(self):
        response = self.client.get("/album/")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        response_albums = [album["album"] for album in res_json["albums"]]
        assert Counter(response_albums) == {"album": 1, "other album": 1}

    def test_get_single_album_by_id(self):
        response = self.client.get("/album/2")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["id"] == 2
        assert res_json["album"] == "other album"

    def test_get_multiple_albums_by_id(self):
        response = self.client.get("/album/1,2")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        response_albums = [album["album"] for album in res_json["albums"]]
        assert Counter(response_albums) == {"album": 1, "other album": 1}

    def test_get_album_empty_query(self):
        response = self.client.get("/album/query/")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["albums"]) == 2

    def test_get_simple_album_query(self):
        response = self.client.get("/album/query/other")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["album"] == "other album"
        assert res_json["results"][0]["id"] == 2

    def test_get_album_details(self):
        response = self.client.get("/album/2?expand")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["items"]) == 2
        assert res_json["items"][0]["album"] == "other album"
        assert res_json["items"][1]["album"] == "other album"
        response_track_titles = {item["title"] for item in res_json["items"]}
        assert response_track_titles == {"title", "and a third"}

    def test_query_album_string(self):
        response = self.client.get(
            "/album/query/albumtest%3axy"
        )  # albumtest:xy
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["album"] == "album"

    def test_query_album_artpath_regex(self):
        response = self.client.get(
            "/album/query/artpath%3a%3aart_"
        )  # artpath::art_
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["album"] == "other album"

    def test_query_album_regex_backslash(self):
        response = self.client.get(
            "/album/query/albumtest%3a%3a%5cw%2b"
        )  # albumtest::\w+
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert len(res_json["results"]) == 1
        assert res_json["results"][0]["album"] == "album"

    def test_get_stats(self):
        response = self.client.get("/stats")
        res_json = json.loads(response.data.decode("utf-8"))

        assert response.status_code == 200
        assert res_json["items"] == 3
        assert res_json["albums"] == 2

    def test_delete_item_id(self):
        web.app.config["READONLY"] = False

        # Create a temporary item
        item_id = self.lib.add(
            Item(title="test_delete_item_id", test_delete_item_id=1)
        )

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id

        # Delete item by id
        response = self.client.delete(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the item has gone
        response = self.client.get(f"/item/{item_id}")
        assert response.status_code == 404
        # Note: if this fails, the item may still be around
        # and may cause other tests to fail

    def test_delete_item_without_file(self):
        web.app.config["READONLY"] = False

        # Create an item with a file
        ipath = self.temp_path / "testfile1.mp3"
        shutil.copy(_common.RSRC / "full.mp3", ipath)
        assert ipath.exists()
        item_id = self.lib.add(Item.from_path(ipath))

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id

        # Delete item by id, without deleting file
        response = self.client.delete(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the item has gone
        response = self.client.get(f"/item/{item_id}")
        assert response.status_code == 404

        # Check the file has not gone
        assert ipath.exists()
        ipath.unlink()

    def test_delete_item_with_file(self):
        web.app.config["READONLY"] = False

        # Create an item with a file
        ipath = self.temp_path / "testfile2.mp3"
        shutil.copy(_common.RSRC / "full.mp3", ipath)
        assert ipath.exists()
        item_id = self.lib.add(Item.from_path(ipath))

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id

        # Delete item by id, with file
        response = self.client.delete(f"/item/{item_id}?delete")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the item has gone
        response = self.client.get(f"/item/{item_id}")
        assert response.status_code == 404

        # Check the file has gone
        assert not ipath.exists()

    def test_delete_item_query(self):
        web.app.config["READONLY"] = False

        # Create a temporary item
        self.lib.add(
            Item(title="test_delete_item_query", test_delete_item_query=1)
        )

        # Check we can find the temporary item we just created
        response = self.client.get("/item/query/test_delete_item_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Delete item by query
        response = self.client.delete("/item/query/test_delete_item_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the item has gone
        response = self.client.get("/item/query/test_delete_item_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 0

    def test_delete_item_all_fails(self):
        """DELETE is not supported for list all"""

        web.app.config["READONLY"] = False

        # Delete all items
        response = self.client.delete("/item/")
        assert response.status_code == 405

        # Note: if this fails, all items have gone and rest of
        # tests will fail!

    def test_delete_item_id_readonly(self):
        web.app.config["READONLY"] = True

        # Create a temporary item
        item_id = self.lib.add(
            Item(title="test_delete_item_id_ro", test_delete_item_id_ro=1)
        )

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id

        # Try to delete item by id
        response = self.client.delete(f"/item/{item_id}")
        assert response.status_code == 405

        # Check the item has not gone
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id

        # Remove it
        self.lib.get_item(item_id).remove()

    def test_delete_item_query_readonly(self):
        web.app.config["READONLY"] = True

        # Create a temporary item
        item_id = self.lib.add(
            Item(title="test_delete_item_q_ro", test_delete_item_q_ro=1)
        )

        # Check we can find the temporary item we just created
        response = self.client.get("/item/query/test_delete_item_q_ro")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Try to delete item by query
        response = self.client.delete("/item/query/test_delete_item_q_ro")
        assert response.status_code == 405

        # Check the item has not gone
        response = self.client.get("/item/query/test_delete_item_q_ro")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Remove it
        self.lib.get_item(item_id).remove()

    def test_delete_album_id(self):
        web.app.config["READONLY"] = False

        # Create a temporary album
        album_id = self.lib.add(
            Album(album="test_delete_album_id", test_delete_album_id=1)
        )

        # Check we can find the temporary album we just created
        response = self.client.get(f"/album/{album_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == album_id

        # Delete album by id
        response = self.client.delete(f"/album/{album_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the album has gone
        response = self.client.get(f"/album/{album_id}")
        assert response.status_code == 404
        # Note: if this fails, the album may still be around
        # and may cause other tests to fail

    def test_delete_album_query(self):
        web.app.config["READONLY"] = False

        # Create a temporary album
        self.lib.add(
            Album(album="test_delete_album_query", test_delete_album_query=1)
        )

        # Check we can find the temporary album we just created
        response = self.client.get("/album/query/test_delete_album_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Delete album
        response = self.client.delete("/album/query/test_delete_album_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200

        # Check the album has gone
        response = self.client.get("/album/query/test_delete_album_query")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 0

    def test_delete_album_all_fails(self):
        """DELETE is not supported for list all"""

        web.app.config["READONLY"] = False

        # Delete all albums
        response = self.client.delete("/album/")
        assert response.status_code == 405

        # Note: if this fails, all albums have gone and rest of
        # tests will fail!

    def test_delete_album_id_readonly(self):
        web.app.config["READONLY"] = True

        # Create a temporary album
        album_id = self.lib.add(
            Album(album="test_delete_album_id_ro", test_delete_album_id_ro=1)
        )

        # Check we can find the temporary album we just created
        response = self.client.get(f"/album/{album_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == album_id

        # Try to delete album by id
        response = self.client.delete(f"/album/{album_id}")
        assert response.status_code == 405

        # Check the item has not gone
        response = self.client.get(f"/album/{album_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == album_id

        # Remove it
        self.lib.get_album(album_id).remove()

    def test_delete_album_query_readonly(self):
        web.app.config["READONLY"] = True

        # Create a temporary album
        album_id = self.lib.add(
            Album(
                album="test_delete_album_query_ro", test_delete_album_query_ro=1
            )
        )

        # Check we can find the temporary album we just created
        response = self.client.get("/album/query/test_delete_album_query_ro")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Try to delete album
        response = self.client.delete("/album/query/test_delete_album_query_ro")
        assert response.status_code == 405

        # Check the album has not gone
        response = self.client.get("/album/query/test_delete_album_query_ro")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert len(res_json["results"]) == 1

        # Remove it
        self.lib.get_album(album_id).remove()

    def test_patch_item_id(self):
        # Note: PATCH is currently only implemented for track items, not albums

        web.app.config["READONLY"] = False

        # Create a temporary item
        item_id = self.lib.add(
            Item(
                title="test_patch_item_id", test_patch_f1=1, test_patch_f2="Old"
            )
        )

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id
        assert res_json["test_patch_f1"] == "1"
        assert res_json["test_patch_f2"] == "Old"

        # Patch item by id
        # patch_json = json.JSONEncoder().encode({"test_patch_f2": "New"}]})
        response = self.client.patch(
            f"/item/{item_id}", json={"test_patch_f2": "New"}
        )
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id
        assert res_json["test_patch_f1"] == "1"
        assert res_json["test_patch_f2"] == "New"

        # Check the update has really worked
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id
        assert res_json["test_patch_f1"] == "1"
        assert res_json["test_patch_f2"] == "New"

        # Remove the item
        self.lib.get_item(item_id).remove()

    def test_patch_item_id_readonly(self):
        # Note: PATCH is currently only implemented for track items, not albums

        web.app.config["READONLY"] = True

        # Create a temporary item
        item_id = self.lib.add(
            Item(
                title="test_patch_item_id_ro",
                test_patch_f1=2,
                test_patch_f2="Old",
            )
        )

        # Check we can find the temporary item we just created
        response = self.client.get(f"/item/{item_id}")
        res_json = json.loads(response.data.decode("utf-8"))
        assert response.status_code == 200
        assert res_json["id"] == item_id
        assert res_json["test_patch_f1"] == "2"
        assert res_json["test_patch_f2"] == "Old"

        # Patch item by id
        # patch_json = json.JSONEncoder().encode({"test_patch_f2": "New"})
        response = self.client.patch(
            f"/item/{item_id}", json={"test_patch_f2": "New"}
        )
        assert response.status_code == 405

        # Remove the item
        self.lib.get_item(item_id).remove()

    def test_get_item_file(self):
        ipath = self.temp_path / "testfile2.mp3"
        shutil.copy(_common.RSRC / "full.mp3", ipath)
        assert ipath.exists()
        item_id = self.lib.add(Item.from_path(ipath))

        response = self.client.get(f"/item/{item_id}/file")

        assert response.status_code == 200

    def test_item_list_ignores_paging_params(self):
        # /item/ must not paginate even when params are passed.
        full = json.loads(self.client.get("/item/").data)["items"]
        resp = self.client.get("/item/?limit=1&offset=1")
        assert json.loads(resp.data)["items"] == full
        assert "X-Total-Count" not in resp.headers

    def test_all_albums_limit_offset(self):
        for i in range(4):
            self.lib.add(Album(album=f"pg_album_{i}", albumartist=f"pg_artist_{i}"))
        full = json.loads(self.client.get("/album/").data)["albums"]
        total = len(full)
        assert total >= 4

        resp = self.client.get("/album/?offset=1&limit=2")
        body = json.loads(resp.data)["albums"]
        assert [a["id"] for a in body] == [full[1]["id"], full[2]["id"]]
        assert resp.headers.get("X-Total-Count") == str(total)

        # offset alone (no limit) pages from offset to the end
        tail = json.loads(self.client.get(f"/album/?offset={total - 1}").data)["albums"]
        assert [a["id"] for a in tail] == [full[-1]["id"]]

    def test_all_albums_no_params_unchanged(self):
        # Backward compat: no params -> identical to today, no X-Total-Count.
        plain = self.client.get("/album/")
        assert "X-Total-Count" not in plain.headers
        assert json.loads(plain.data)["albums"] == json.loads(self.client.get("/album/?").data)["albums"]

    def test_all_albums_limit_clamped_and_garbage_ignored(self):
        for i in range(3):
            self.lib.add(Album(album=f"clamp_album_{i}"))
        all_albums = json.loads(self.client.get("/album/").data)["albums"]
        clamped = json.loads(self.client.get("/album/?limit=99999").data)["albums"]
        assert len(clamped) == len(all_albums)
        assert len(clamped) <= 500
        # garbage limit is ignored -> treated as "no limit" -> returns all
        assert len(json.loads(self.client.get("/album/?limit=abc").data)["albums"]) == len(all_albums)

    def test_all_artists_limit_offset(self):
        for i in range(3):
            self.lib.add(Album(album=f"art_album_{i}", albumartist=f"zz_artist_{i}"))
        full = json.loads(self.client.get("/artist/").data)["artist_names"]
        resp = self.client.get("/artist/?limit=2")
        assert json.loads(resp.data)["artist_names"] == full[:2]
        assert resp.headers.get("X-Total-Count") == str(len(full))

    def test_artist_art_maps_artist_to_a_cover_album(self):
        # Artists have no art of their own; /artist/ maps each artist that has
        # any album art to one of that artist's album ids so the UI can show a
        # cover as the artist avatar. Artists without art are absent.
        with_art = Album(
            album="has_art", albumartist="ArtistWithArt", artpath=b"/x/cover.jpg"
        )
        self.lib.add(with_art)
        self.lib.add(Album(album="no_art", albumartist="ArtistNoArt"))

        data = json.loads(self.client.get("/artist/").data)
        art = data["artist_art"]

        # both artists are listed by name
        assert "ArtistWithArt" in data["artist_names"]
        assert "ArtistNoArt" in data["artist_names"]
        # the art map points the art-having artist at its album, and the id
        # really belongs to one of that artist's albums
        assert art["ArtistWithArt"] == with_art.id
        # an artist with no album art gets no entry
        assert "ArtistNoArt" not in art

    def test_page_params_edges(self):
        from beetsplug import web as webmod

        with webmod.app.test_request_context("/x?limit=99999&offset=-5"):
            assert webmod._page_params() == (0, 500)
        with webmod.app.test_request_context("/x?offset=3"):
            assert webmod._page_params() == (3, None)
        with webmod.app.test_request_context("/x?limit=abc"):
            assert webmod._page_params() == (0, None)
        with webmod.app.test_request_context("/x"):
            assert webmod._page_params() == (0, None)


class TestWebXSS(WebPluginMixin, PytestTestHelper):
    """Tests for XSS vulnerability in the web plugin's metadata rendering.

    The web UI renders metadata client-side in ``static/app.js``, which
    HTML-escapes user-controlled fields through an ``esc()`` helper. This
    guards the security contract from
    https://github.com/beetbox/beets/security/advisories/GHSA-3gxm-wfjx-m847
    (user metadata must be HTML-escaped) under the current architecture; the
    contract previously lived in server-side Underscore.js templates in
    index.html, which no longer interpolate metadata at all.
    """

    def test_app_js_escapes_user_metadata(self):
        """Guard GHSA-3gxm-wfjx-m847 under the client-render architecture.

        The redesigned UI renders metadata in ``static/app.js`` rather than in
        server-side templates, so verify that app.js routes user-controlled
        text fields through its ``esc()`` HTML-escaping helper wherever it
        builds HTML. (The server template no longer interpolates metadata at
        all, so the original server-template vector is structurally gone.)
        """
        import re
        from pathlib import Path

        src = (Path(web.__file__).parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        # The escaping helper must exist.
        assert re.search(r"const\s+esc\s*=", src), "esc() helper missing from app.js"

        # Free-text, user-controlled fields that must be HTML-escaped when
        # interpolated into markup.
        free_text = [
            "title", "artist", "album", "albumartist", "lyrics", "genre", "label",
            "mb_trackid", "mb_albumid",
        ]
        offenders = []
        for line in src.splitlines():
            # Assignments to .textContent never interpret HTML, so they are
            # XSS-safe by construction and are exempt.
            if ".textContent" in line:
                continue
            for m in re.finditer(r"\$\{([^}]*)\}", line):
                expr = m.group(1)
                # Safe sinks: esc() escapes for HTML; encodeURIComponent()
                # percent-encodes for URL/attribute contexts; coverStyle() uses
                # the value only as a hash seed for a gradient, so the value
                # never reaches the output.
                if any(
                    sink in expr
                    for sink in ("esc(", "encodeURIComponent(", "coverStyle(")
                ):
                    continue
                for field in free_text:
                    if re.search(r"\b(?:t|a|item)\." + field + r"\b", expr):
                        offenders.append(expr.strip())

        assert not offenders, (
            "Unescaped user-metadata interpolation(s) into HTML in app.js "
            "(these must be wrapped in esc()): " + repr(offenders)
        )
