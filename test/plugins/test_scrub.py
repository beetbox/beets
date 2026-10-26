import mutagen
import pytest
from mediafile import MediaFile
from mutagen.id3 import COMM, ID3, PRIV, TXXX
from mutagen.mp4 import MP4FreeForm, MP4Tags

from beets.test.helper import (
    AsIsImporterMixin,
    ImportHelper,
    PluginMixin,
    PluginTestHelper,
)

FORMATS = ["mp3", "flac", "ogg", "opus", "m4a", "ape", "wv", "mpc", "wma"]

# Title and comment set, so mutagen loads TIT2 and COMM frames.
ID3V1_TAIL = (
    b"TAG"
    + b"title".ljust(30, b"\0")
    + bytes(64)
    + b"comment".ljust(28, b"\0")
    + b"\0\x01\xff"
)


def custom_key(tags, name):
    if isinstance(tags, ID3):
        return f"TXXX:{name}"
    if isinstance(tags, MP4Tags):
        return f"----:com.apple.iTunes:{name}"
    return name


def add_custom_tags(path, **values):
    """Write custom tags the way other taggers store them."""
    f = mutagen.File(path)
    for name, value in values.items():
        if isinstance(f.tags, ID3):
            f.tags.add(TXXX(encoding=3, desc=name, text=[value]))
        elif isinstance(f.tags, MP4Tags):
            f.tags[custom_key(f.tags, name)] = [MP4FreeForm(value.encode())]
        else:
            f.tags[name] = [value]
    f.save()


def custom_tags(path):
    tags = mutagen.File(path).tags
    return {
        name
        for name in ("SUBBOX_ID", "SERATO_PLAYCOUNT")
        if tags is not None and custom_key(tags, name) in tags
    }


class TestScrubbedImport(AsIsImporterMixin, PluginMixin, ImportHelper):
    db_on_disk = True
    plugin = "scrub"
    preload_plugin = False

    def test_tags_not_scrubbed(self):
        with self.configure_plugin({"auto": False}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_restored(self):
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_tags_not_scrubbed_when_nowrite(self):
        """When --nowrite is passed, scrubbing should be skipped entirely."""
        with self.configure_plugin({"auto": True}):
            self.run_asis_importer(write=False)

        for item in self.lib.items():
            imported_file = MediaFile(item.filepath)
            assert imported_file.artist == "Tag Artist"
            assert imported_file.album == "Tag Album"

    def test_kept_tags_survive_import(self):
        for media in self.import_media:
            add_custom_tags(
                media.filename, SUBBOX_ID="id", SERATO_PLAYCOUNT="0"
            )

        with self.configure_plugin({"keep_tags": ["SUBBOX_ID"]}):
            self.run_asis_importer(write=True)

        for item in self.lib.items():
            assert custom_tags(item.filepath) == {"SUBBOX_ID"}
            assert MediaFile(item.filepath).artist == "Tag Artist"


class TestKeepTags(PluginTestHelper):
    plugin = "scrub"
    preload_plugin = False

    def scrub(self, ext, keep_tags, *args):
        item = self.add_item_fixtures(ext)[0]
        add_custom_tags(item.filepath, SUBBOX_ID="id", SERATO_PLAYCOUNT="0")
        with self.configure_plugin({"keep_tags": keep_tags}):
            self.run_command("scrub", *args)
        return item

    @pytest.mark.parametrize("args", [(), ("--nowrite",)])
    @pytest.mark.parametrize("ext", FORMATS)
    def test_keep_tags(self, ext, args):
        item = self.scrub(ext, "subbox_id", *args)

        assert custom_tags(item.filepath) == {"SUBBOX_ID"}
        expected_title = None if args else item.title
        assert MediaFile(item.filepath).title == expected_title

    @pytest.mark.parametrize("ext", FORMATS)
    def test_custom_tags_scrubbed_by_default(self, ext):
        item = self.scrub(ext, [])

        assert custom_tags(item.filepath) == set()
        assert MediaFile(item.filepath).title == item.title

    @pytest.mark.parametrize(
        "ext, keep_tag, expected",
        [
            ("mp3", "TXXX:SUBBOX_ID", {"SUBBOX_ID"}),
            ("m4a", "----:com.apple.iTunes:SUBBOX_ID", {"SUBBOX_ID"}),
            ("mp3", "SUBBOX", set()),
        ],
    )
    def test_matching(self, ext, keep_tag, expected):
        item = self.scrub(ext, [keep_tag], "--nowrite")

        assert custom_tags(item.filepath) == expected

    @pytest.mark.parametrize("ext, magic", [("flac", b"fLaC"), ("wv", b"wvpk")])
    def test_id3v1_tail_removed(self, ext, magic):
        item = self.add_item_fixtures(ext)[0]
        with open(item.filepath, "ab") as f:
            f.write(ID3V1_TAIL)

        with self.configure_plugin({"keep_tags": ["COMM", "TIT2"]}):
            self.run_command("scrub")

        with open(item.filepath, "rb") as f:
            data = f.read()
        assert data.startswith(magic)
        assert data[-128:-125] != b"TAG"
        assert MediaFile(item.filepath).title == item.title

    def test_keep_id3_frames_by_prefix(self):
        item = self.add_item_fixtures("mp3")[0]
        tags = ID3(item.filepath)
        tags.add(PRIV(owner="com.subbox", data=b"\x00\xff"))
        tags.add(COMM(encoding=3, desc="note", lang="eng", text=["text"]))
        tags.save()

        with self.configure_plugin({"keep_tags": ["PRIV:com.subbox", "COMM"]}):
            self.run_command("scrub", "--nowrite")

        tags = ID3(item.filepath)
        assert {f.FrameID for f in tags.values()} == {"COMM", "PRIV"}
        assert tags["COMM:note:eng"].text == ["text"]
        assert tags.getall("PRIV")[0].data == b"\x00\xff"

    @pytest.mark.parametrize("id3v23, version", [(False, 4), (True, 3)])
    def test_keep_tags_id3_version(self, id3v23, version):
        self.config["id3v23"] = id3v23
        item = self.add_item_fixtures("mp3")[0]
        add_custom_tags(item.filepath, SUBBOX_ID="id")
        mutagen.File(item.filepath).save(v1=2)

        with self.configure_plugin({"keep_tags": ["SUBBOX_ID"]}):
            self.run_command("scrub", "--nowrite")

        tags = ID3(item.filepath)
        assert tags.version[1] == version
        assert list(tags.keys()) == ["TXXX:SUBBOX_ID"]
        with open(item.filepath, "rb") as f:
            f.seek(-128, 2)
            assert f.read(3) != b"TAG"
