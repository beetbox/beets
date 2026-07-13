import codecs
from typing import ClassVar
from unittest.mock import patch

from beets.dbcore.query import TrueQuery
from beets.importer import Action
from beets.library import Item
from beets.test.helper import (
    AutotagImportTestCase,
    AutotagStub,
    BeetsTestCase,
    IOMixin,
    PluginMixin,
    TerminalImportMixin,
)
from beetsplug.edit import EditPlugin, dump, load


class ModifyFileMocker:
    """Helper for modifying a file, replacing or editing its contents. Used for
    mocking the calls to the external editor during testing.
    """

    def __init__(self, contents=None, replacements=None):
        """`self.contents` and `self.replacements` are initialized here, in
        order to keep the rest of the functions of this class with the same
        signature as `EditPlugin.get_editor()`, making mocking easier.
            - `contents`: string with the contents of the file to be used for
            `overwrite_contents()`
            - `replacement`: dict with the in-place replacements to be used for
            `replace_contents()`, in the form {'previous string': 'new string'}

        TODO: check if it can be solved more elegantly with a decorator
        """
        self.contents = contents
        self.replacements = replacements
        self.action = self.overwrite_contents
        if replacements:
            self.action = self.replace_contents

    # The two methods below mock the `edit` utility function in the plugin.

    def overwrite_contents(self, filename, log):
        """Modify `filename`, replacing its contents with `self.contents`. If
        `self.contents` is empty, the file remains unchanged.
        """
        if self.contents:
            with codecs.open(filename, "w", encoding="utf-8") as f:
                f.write(self.contents)

    def replace_contents(self, filename, log):
        """Modify `filename`, reading its contents and replacing the strings
        specified in `self.replacements`.
        """
        with codecs.open(filename, "r", encoding="utf-8") as f:
            contents = f.read()
        for old, new_ in self.replacements.items():
            contents = contents.replace(old, new_)
        with codecs.open(filename, "w", encoding="utf-8") as f:
            f.write(contents)


class EditMixin(PluginMixin):
    """Helper containing some common functionality used for the Edit tests."""

    plugin = "edit"

    def assertItemFieldsModified(
        self, library_items, items, fields=[], allowed=["path"]
    ):
        """Assert that items in the library (`lib_items`) have different values
        on the specified `fields` (and *only* on those fields), compared to
        `items`.

        An empty `fields` list results in asserting that no modifications have
        been performed. `allowed` is a list of field changes that are ignored
        (they may or may not have changed; the assertion doesn't care).
        """
        for lib_item, item in zip(library_items, items):
            diff_fields = [
                field
                for field in lib_item._fields
                if lib_item[field] != item[field]
            ]
            assert set(diff_fields).difference(allowed) == set(fields)

    def run_mocked_interpreter(self, modify_file_args={}, stdin=[]):
        """Run the edit command during an import session, with mocked stdin and
        yaml writing.
        """
        m = ModifyFileMocker(**modify_file_args)
        with patch("beetsplug.edit.edit", side_effect=m.action):
            for char in stdin:
                self.importer.add_choice(char)
            self.importer.run()

    def run_mocked_command(self, modify_file_args={}, stdin=[], args=[]):
        """Run the edit command, with mocked stdin and yaml writing, and
        passing `args` to `run_command`."""
        m = ModifyFileMocker(**modify_file_args)
        with patch("beetsplug.edit.edit", side_effect=m.action):
            for char in stdin:
                self.io.addinput(char)
            self.run_command("edit", *args)


@patch("beets.library.Item.write")
class EditCommandTest(IOMixin, EditMixin, BeetsTestCase):
    """Black box tests for `beetsplug.edit`. Command line interaction is
    simulated using mocked stdin, and yaml editing via an external editor is
    simulated using `ModifyFileMocker`.
    """

    TRACK_COUNT = 10

    def setUp(self):
        super().setUp()
        # Add an album, storing the original fields for comparison.
        self.album = self.add_album_fixture(track_count=self.TRACK_COUNT)
        self.album_orig = {f: self.album[f] for f in self.album._fields}
        self.items_orig = [
            {f: item[f] for f in item._fields} for item in self.album.items()
        ]

    def test_title_edit_discard(self, mock_write):
        """Edit title for all items in the library, then discard changes."""
        # Edit track titles.
        self.run_mocked_command(
            {"replacements": {"t\u00eftle": "modified t\u00eftle"}},
            # Cancel.
            ["c"],
        )

        assert mock_write.call_count == 0
        self.assertItemFieldsModified(self.album.items(), self.items_orig, [])

    def test_title_edit_apply(self, mock_write):
        """Edit title for all items in the library, then apply changes."""
        # Edit track titles.
        self.run_mocked_command(
            {"replacements": {"t\u00eftle": "modified t\u00eftle"}},
            # Apply changes.
            ["a"],
        )

        assert mock_write.call_count == self.TRACK_COUNT
        self.assertItemFieldsModified(
            self.album.items(), self.items_orig, ["title", "mtime"]
        )

    def test_single_title_edit_apply(self, mock_write):
        """Edit title for one item in the library, then apply changes."""
        # Edit one track title.
        self.run_mocked_command(
            {"replacements": {"t\u00eftle 9": "modified t\u00eftle 9"}},
            # Apply changes.
            ["a"],
        )

        assert mock_write.call_count == 1
        # No changes except on last item.
        self.assertItemFieldsModified(
            list(self.album.items())[:-1], self.items_orig[:-1], []
        )
        assert list(self.album.items())[-1].title == "modified t\u00eftle 9"

    def test_title_edit_keep_editing_then_apply(self, mock_write):
        """Edit titles, keep editing once, then apply changes."""
        self.run_mocked_command(
            {"replacements": {"t\u00eftle": "modified t\u00eftle"}},
            # keep Editing, then Apply
            ["e", "a"],
        )

        assert mock_write.call_count == self.TRACK_COUNT
        self.assertItemFieldsModified(
            self.album.items(), self.items_orig, ["title", "mtime"]
        )

    def test_title_edit_keep_editing_then_cancel(self, mock_write):
        """Edit titles, keep editing once, then cancel."""
        self.run_mocked_command(
            {"replacements": {"t\u00eftle": "modified t\u00eftle"}},
            # keep Editing, then Cancel
            ["e", "c"],
        )

        assert mock_write.call_count == 0
        self.assertItemFieldsModified(self.album.items(), self.items_orig, [])

    def test_noedit(self, mock_write):
        """Do not edit anything."""
        # Do not edit anything.
        self.run_mocked_command(
            {"contents": None},
            # No stdin.
            [],
        )

        assert mock_write.call_count == 0
        self.assertItemFieldsModified(self.album.items(), self.items_orig, [])

    def test_album_edit_apply(self, mock_write):
        """Edit the album field for all items in the library, apply changes.
        By design, the album should not be updated.""
        """
        # Edit album.
        self.run_mocked_command(
            {"replacements": {"\u00e4lbum": "modified \u00e4lbum"}},
            # Apply changes.
            ["a"],
        )

        assert mock_write.call_count == self.TRACK_COUNT
        self.assertItemFieldsModified(
            self.album.items(), self.items_orig, ["album", "mtime"]
        )
        # Ensure album is *not* modified.
        self.album.load()
        assert self.album.album == "\u00e4lbum"

    def test_single_edit_add_field(self, mock_write):
        """Edit the yaml file appending an extra field to the first item, then
        apply changes."""
        # Append "foo: bar" to item with id == 2. ("id: 1" would match both
        # "id: 1" and "id: 10")
        self.run_mocked_command(
            {"replacements": {"id: 2": "id: 2\nfoo: bar"}},
            # Apply changes.
            ["a"],
        )

        assert self.lib.items("id:2")[0].foo == "bar"
        # Even though a flexible attribute was written (which is not directly
        # written to the tags), write should still be called since templates
        # might use it.
        assert mock_write.call_count == 1

    def test_a_album_edit_apply(self, mock_write):
        """Album query (-a), edit album field, apply changes."""
        self.run_mocked_command(
            {"replacements": {"\u00e4lbum": "modified \u00e4lbum"}},
            # Apply changes.
            ["a"],
            args=["-a"],
        )

        self.album.load()
        assert mock_write.call_count == self.TRACK_COUNT
        assert self.album.album == "modified \u00e4lbum"
        self.assertItemFieldsModified(
            self.album.items(), self.items_orig, ["album", "mtime"]
        )

    def test_a_albumartist_edit_apply(self, mock_write):
        """Album query (-a), edit albumartist field, apply changes."""
        self.run_mocked_command(
            {"replacements": {"album artist": "modified album artist"}},
            # Apply changes.
            ["a"],
            args=["-a"],
        )

        self.album.load()
        assert mock_write.call_count == self.TRACK_COUNT
        assert self.album.albumartist == "the modified album artist"
        self.assertItemFieldsModified(
            self.album.items(), self.items_orig, ["albumartist", "mtime"]
        )

    def test_malformed_yaml(self, mock_write):
        """Edit the yaml file incorrectly (resulting in a malformed yaml
        document)."""
        # Edit the yaml file to an invalid file.
        self.run_mocked_command(
            {"contents": "!MALFORMED"},
            # Edit again to fix? No.
            ["n"],
        )

        assert mock_write.call_count == 0

    def test_invalid_yaml(self, mock_write):
        """Edit the yaml file incorrectly (resulting in a well-formed but
        invalid yaml document)."""
        # Edit the yaml file to an invalid but parseable file.
        self.run_mocked_command(
            {"contents": "wellformed: yes, but invalid"},
            # No stdin.
            [],
        )

        assert mock_write.call_count == 0


class ApplyDataMatchingTest(PluginMixin, BeetsTestCase):
    """`apply_data` must match documents to objects by their ``id`` field,
    not by their position in the list. A reordered or otherwise misaligned
    document list must not cause one object's data to be applied to a
    different object.
    """

    plugin = "edit"

    def make_items(self):
        items = []
        for i in (1, 2, 3):
            item = Item(id=i, title=f"Title {i}", track=i, artist="Artist")
            items.append(item)
        return items

    def test_matches_by_id_when_documents_are_reordered(self):
        plugin = EditPlugin()
        items = self.make_items()
        old_data = [
            {"id": i.id, "title": i.title, "track": i.track} for i in items
        ]

        # The saved documents come back in a different order than `items`,
        # as could happen after a "keep editing" round-trip or a reordering
        # editor action. Only track 2's title was actually edited.
        new_data = [
            {"id": 3, "title": "Title 3", "track": 3},
            {"id": 1, "title": "Title 1", "track": 1},
            {"id": 2, "title": "Modified Title 2", "track": 2},
        ]

        plugin.apply_data(items, old_data, new_data)

        assert [i.title for i in items] == [
            "Title 1",
            "Modified Title 2",
            "Title 3",
        ]
        assert [i.track for i in items] == [1, 2, 3]

    def test_ignores_document_with_missing_id(self):
        plugin = EditPlugin()
        items = self.make_items()
        old_data = [
            {"id": i.id, "title": i.title, "track": i.track} for i in items
        ]

        # A document without an `id` must never be silently applied to an
        # unrelated object.
        new_data = [
            {"title": "Header-like doc", "track": 99},
            {"id": 2, "title": "Modified Title 2", "track": 2},
            {"id": 3, "title": "Title 3", "track": 3},
        ]

        plugin.apply_data(items, old_data, new_data)

        assert items[0].title == "Title 1"
        assert items[0].track == 1

    def test_ignores_documents_with_duplicate_id(self):
        plugin = EditPlugin()
        items = self.make_items()
        old_data = [
            {"id": i.id, "title": i.title, "track": i.track} for i in items
        ]

        # The user changed document 2's `id` to 1, an id that already
        # belongs to another document. Neither document should be applied:
        # we can't tell which one is legitimately item 1's data.
        new_data = [
            {"id": 1, "title": "Title 1", "track": 1},
            {"id": 1, "title": "Modified Title 2", "track": 2},
            {"id": 3, "title": "Title 3", "track": 3},
        ]

        plugin.apply_data(items, old_data, new_data)

        assert items[0].title == "Title 1"
        assert items[0].track == 1
        assert items[1].title == "Title 2"
        assert items[1].track == 2


class AlbumHeaderFieldsTest(PluginMixin, BeetsTestCase):
    """`_importer_edit_album_header` must strip item-only fixed fields
    (title, track, path, ...), since the header is built from a single
    item and then applied to every item in the album. Flexible fields
    are not part of either model's fixed schema, so they must be left
    alone rather than discarded by an overly broad filter.
    """

    plugin = "edit"

    class _StubTask:
        is_album = True

        def __init__(self, items):
            self.items = items

    def test_keeps_flexible_fields_but_drops_item_only_fields(self):
        item = Item(id=1, title="Title 1", track=1, album="Album", mood="Happy")
        task = self._StubTask([item])

        self.config["edit"]["albumfields"] = "album mood track title"

        header = EditPlugin()._importer_edit_album_header(task)

        assert header == {"album": "Album", "mood": "Happy"}


class EditDuringImporterTestCase(
    EditMixin, TerminalImportMixin, AutotagImportTestCase
):
    """TODO"""

    matching = AutotagStub.GOOD

    IGNORED: ClassVar[list[str]] = ["added", "album_id", "id", "mtime", "path"]

    def setUp(self):
        super().setUp()
        # Create some mediafiles, and store them for comparison.
        self.prepare_album_for_import(1)
        self.items_orig = [Item.from_path(f.path) for f in self.import_media]


class EditDuringImporterNonSingletonTest(EditDuringImporterTestCase):
    def setUp(self):
        super().setUp()
        self.importer = self.setup_importer()

    def test_importer_edit_album_header_album(self):
        """Edit an album-level field (album) using the import header section,
        apply changes, and verify all items and the album are updated.
        """
        # Show only album in the header and title per track.
        self.config["edit"]["itemfields"] = "title"
        self.config["edit"]["albumfields"] = "album"

        self.run_mocked_interpreter(
            {"replacements": {"Tag Album": "Modified Album"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        # All items should have the new album name.
        assert all(i.album == "Modified Album" for i in self.lib.items())

        # The imported album record should also be updated.
        assert self.lib.albums()[0].album == "Modified Album"

    def test_importer_edit_album_header_and_items(self):
        """Edit both the album header and per-track fields simultaneously."""
        self.config["edit"]["itemfields"] = "title"
        self.config["edit"]["albumfields"] = "album"

        self.run_mocked_interpreter(
            {
                "replacements": {
                    "Tag Album": "Modified Album",
                    "Tag Track": "Modified Track",
                }
            },
            # eDit, Apply changes.
            ["d", "a"],
        )

        # All items should have the new album and new title.
        assert all(i.album == "Modified Album" for i in self.lib.items())
        assert all("Modified Track" in i.title for i in self.lib.items())
        assert self.lib.albums()[0].album == "Modified Album"

    def test_importer_edit_album_header_skip_no_albumfields(self):
        """When albumfields is empty, no header section is produced; editing
        works as before.
        """
        self.config["edit"]["itemfields"] = "title"
        self.config["edit"]["albumfields"] = ""

        self.run_mocked_interpreter(
            {"replacements": {"Tag Track": "Edited Track"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        assert all("Edited Track" in i.title for i in self.lib.items())

    def test_importer_edit_album_header_ignores_item_only_fields(self):
        """`albumfields` may be misconfigured with item-only fields (e.g.
        `track`, `title`, `path`) that vary per track. Those must not end
        up in the header, since the header gets applied to every item and
        would otherwise stamp one track's values onto the whole album.
        """
        self.prepare_album_for_import(3)
        self.items_orig = [Item.from_path(f.path) for f in self.import_media]

        self.config["edit"]["itemfields"] = "track title artist album"
        self.config["edit"]["albumfields"] = "album albumartist track title"

        self.run_mocked_interpreter(
            {"replacements": {"Tag Album": "Modified Album"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        titles = [i.title for i in self.lib.items()]
        tracks = [i.track for i in self.lib.items()]
        assert len(set(titles)) == len(titles)
        assert len(set(tracks)) == len(tracks)
        assert all(i.album == "Modified Album" for i in self.lib.items())

    def test_importer_edit_album_header_albumartist(self):
        """Edit albumartist in the header (default albumfields)."""
        self.run_mocked_interpreter(
            {"replacements": {"Tag Artist": "Modified Artist"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        assert all(
            i.albumartist is not None and "Modified Artist" in i.albumartist
            for i in self.lib.items()
        ) or all(
            i.albumartist is None and "Tag Artist" in i.artist
            for i in self.lib.items()
        )

    def test_importer_edit_album_header_reordered(self):
        """If the user moves the album header document below the track
        documents, it must still be recognized as the header (identified by
        the absence of an `id` field) rather than misapplying a track's
        fields to every item.
        """
        self.config["edit"]["itemfields"] = "title"
        self.config["edit"]["albumfields"] = "album"

        def reorder_and_edit(filename, log):
            with codecs.open(filename, encoding="utf-8") as f:
                docs = load(f.read())
            header = next(d for d in docs if "id" not in d)
            tracks = [d for d in docs if "id" in d]
            header["album"] = "Modified Album"
            with codecs.open(filename, "w", encoding="utf-8") as f:
                f.write(dump([*tracks, header]))

        with patch("beetsplug.edit.edit", side_effect=reorder_and_edit):
            self.importer.add_choice("d")
            self.importer.add_choice("a")
            self.importer.run()

        assert all(i.album == "Modified Album" for i in self.lib.items())
        assert all("Tag Track" in i.title for i in self.lib.items())

    def test_edit_apply_asis(self):
        """Edit the album field for all items in the library, apply changes,
        using the original item tags.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Tag Track": "Edited Track"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        # Check that only the 'title' field is modified.
        self.assertItemFieldsModified(
            self.lib.items(),
            self.items_orig,
            ["title", "albumartist", "albumartists"],
            [*self.IGNORED, "mb_albumartistid", "mb_albumartistids"],
        )
        assert all("Edited Track" in i.title for i in self.lib.items())

        # Ensure album is *not* fetched from a candidate.
        assert self.lib.albums()[0].mb_albumid == ""

    def test_edit_discard_asis(self):
        """Edit the album field for all items in the library, discard changes,
        using the original item tags.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Tag Track": "Edited Track"}},
            # eDit, Cancel, Use as-is.
            ["d", "c", "u"],
        )

        # Check that nothing is modified, the album is imported ASIS.
        self.assertItemFieldsModified(
            self.lib.items(),
            self.items_orig,
            [],
            [*self.IGNORED, "albumartist", "mb_albumartistid"],
        )
        assert all("Tag Track" in i.title for i in self.lib.items())

        # Ensure album is *not* fetched from a candidate.
        assert self.lib.albums()[0].mb_albumid == ""

    def test_edit_apply_candidate(self):
        """Edit the album field for all items in the library, apply changes,
        using a candidate.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Applied Track": "Edited Track"}},
            # edit Candidates, 1, Apply changes.
            ["c", "1", "a"],
        )

        # Check that 'title' field is modified, and other fields come from
        # the candidate.
        assert all("Edited Track " in i.title for i in self.lib.items())
        assert all("match " in i.mb_trackid for i in self.lib.items())

        # Ensure album is fetched from a candidate.
        assert "albumid" in self.lib.albums()[0].mb_albumid

    def test_edit_retag_apply(self):
        """Import the album using a candidate, then retag and edit and apply
        changes.
        """
        self.run_mocked_interpreter(
            {},
            # 1, Apply changes.
            ["1", Action.APPLY],
        )

        # Retag and edit track titles.  On retag, the importer will reset items
        # ids but not the db connections.
        self.importer.paths = []
        self.importer.query = TrueQuery()
        self.run_mocked_interpreter(
            {"replacements": {"Applied Track": "Edited Track"}},
            # eDit, Apply changes.
            ["d", "a"],
        )

        # Check that 'title' field is modified, and other fields come from
        # the candidate.
        assert all("Edited Track " in i.title for i in self.lib.items())
        assert all("match " in i.mb_trackid for i in self.lib.items())

        # Ensure album is fetched from a candidate.
        assert "albumid" in self.lib.albums()[0].mb_albumid

    def test_edit_discard_candidate(self):
        """Edit the album field for all items in the library, discard changes,
        using a candidate.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Applied Track": "Edited Track"}},
            # edit Candidates, 1, Apply changes.
            ["c", "1", "a"],
        )

        # Check that 'title' field is modified, and other fields come from
        # the candidate.
        assert all("Edited Track " in i.title for i in self.lib.items())
        assert all("match " in i.mb_trackid for i in self.lib.items())

        # Ensure album is fetched from a candidate.
        assert "albumid" in self.lib.albums()[0].mb_albumid

    def test_edit_apply_candidate_singleton(self):
        """Edit the album field for all items in the library, apply changes,
        using a candidate and singleton mode.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Applied Track": "Edited Track"}},
            # edit Candidates, 1, Apply changes, aBort.
            ["c", "1", "a", "b"],
        )

        # Check that 'title' field is modified, and other fields come from
        # the candidate.
        assert all("Edited Track " in i.title for i in self.lib.items())
        assert all("match " in i.mb_trackid for i in self.lib.items())


class EditDuringImporterSingletonTest(EditDuringImporterTestCase):
    def setUp(self):
        super().setUp()
        self.importer = self.setup_singleton_importer()

    def test_edit_apply_asis_singleton(self):
        """Edit the album field for all items in the library, apply changes,
        using the original item tags and singleton mode.
        """
        # Edit track titles.
        self.run_mocked_interpreter(
            {"replacements": {"Tag Track": "Edited Track"}},
            # eDit, Apply changes, aBort.
            ["d", "a", "b"],
        )

        # Check that only the 'title' field is modified.
        self.assertItemFieldsModified(
            self.lib.items(),
            self.items_orig,
            ["title"],
            [*self.IGNORED, "albumartist", "mb_albumartistid"],
        )
        assert all("Edited Track" in i.title for i in self.lib.items())
