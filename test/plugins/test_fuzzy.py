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

"""Tests for the fuzzy query plugin."""

import pytest

from beets.test.helper import PluginMixin, TestHelper


@pytest.fixture
def helper(request):
    helper = TestHelper()
    helper.setup_beets()

    request.instance.lib = helper.lib
    request.instance.add_item = helper.add_item

    yield

    helper.teardown_beets()


@pytest.mark.usefixtures("helper")
class TestFuzzyPlugin(PluginMixin):
    plugin = "fuzzy"

    @pytest.mark.parametrize(
        "query,expected_titles",
        [
            pytest.param("~foo", ["seafood"], id="all-fields-substring"),
            pytest.param("title:~foo", ["seafood"], id="field-substring"),
            pytest.param("~seafood", ["seafood"], id="all-fields-equal-length"),
            pytest.param("~zzz", [], id="all-fields-no-match"),
        ],
    )
    def test_fuzzy_queries(self, query, expected_titles):
        self.add_item(title="seafood", artist="alpha")
        self.add_item(title="bread", artist="beta")

        with self.configure_plugin({}):
            items = self.lib.items(query)

        assert [item.title for item in items] == expected_titles
