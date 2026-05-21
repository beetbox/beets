# This file is part of beets.
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


import pytest

from beets.test.helper import IOMixin, PluginMixin, TestHelper


class TestDuplicatesPlugin(PluginMixin, TestHelper, IOMixin):
    plugin = "duplicates"

    @pytest.fixture(autouse=True)
    def setup(self):
        self.setup_beets()
        self.dup_item = self.create_item(
            album="Pretend Album",
            albumartist="Pretend Artist",
            artist="Pretend Artist",
            title="Pretend Track",
            genres=["Original Genre"],
            mb_trackid="abc",
            mb_albumid="def",
        )
        try:
            yield
        finally:
            self.teardown_beets()
            self.dup_item = None

    def run_cmd(self, count=False, path=False) -> str:
        args = ["duplicates"]
        if count:
            args.append("--count")
        if path:
            args.append("--path")

        return self.run_with_output(*args).strip()

    def create_dups(self, count: int):
        for _ in range(count):
            self.lib.add(self.dup_item)

    def test_duplicate(self):
        self.create_dups(2)
        out = self.run_cmd()

        assert self.dup_item.artist in out
        assert self.dup_item.album in out
        assert self.dup_item.title in out

    def test_duplicate_path(self):
        self.create_dups(2)
        out = self.run_cmd(path=True)

        assert self.dup_item.path.decode() in out

    def test_duplicate_with_count(self):
        self.create_dups(4)
        out = self.run_cmd(count=True)

        assert self.dup_item.artist in out
        assert self.dup_item.album in out
        assert self.dup_item.title in out
        assert out.endswith("3")

    def test_duplicate_path_with_count(self):
        self.create_dups(6)
        out = self.run_cmd(count=True, path=True)

        assert self.dup_item.path.decode() in out
        assert out.endswith("5")
