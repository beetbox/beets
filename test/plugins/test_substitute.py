"""Test the substitute plugin regex functionality."""

from beets.test.helper import PluginTestHelper
from beetsplug.substitute import Substitute


class TestSubstitutePlugin(PluginTestHelper):
    plugin = "substitute"
    preload_plugin = False

    def run_substitute(self, config, cases):
        with self.configure_plugin(config):
            for input_, expected in cases:
                assert Substitute().tmpl_substitute(input_) == expected

    def test_simple_substitute(self):
        self.run_substitute(
            {"a": "x", "b": "y", "c": "z"}, [("a", "x"), ("b", "y"), ("c", "z")]
        )

    def test_case_insensitivity(self):
        self.run_substitute({"a": "x"}, [("A", "x")])

    def test_unmatched_input_preserved(self):
        self.run_substitute({"a": "x"}, [("c", "c")])

    def test_regex_to_static(self):
        self.run_substitute(
            {".*jimi hendrix.*": "Jimi Hendrix"},
            [("The Jimi Hendrix Experience", "Jimi Hendrix")],
        )

    def test_regex_capture_group(self):
        self.run_substitute(
            {"^(.*?)(,| &| and).*": r"\1"},
            [
                ("King Creosote & Jon Hopkins", "King Creosote"),
                (
                    (
                        "Michael Hurley, The Holy Modal Rounders, Jeffrey"
                        " Frederick & The Clamtones"
                    ),
                    "Michael Hurley",
                ),
                ("James Yorkston and the Athletes", "James Yorkston"),
            ],
        )

    def test_partial_substitution(self):
        self.run_substitute({r"\.": ""}, [("U.N.P.O.C.", "UNPOC")])

    def test_rules_applied_in_definition_order(self):
        self.run_substitute(
            {"a": "x", "[ab]": "y", "b": "z"}, [("a", "x"), ("b", "y")]
        )

    def test_rules_applied_in_sequence(self):
        self.run_substitute(
            {"a": "b", "b": "c", "d": "a"}, [("a", "c"), ("b", "c"), ("d", "a")]
        )
