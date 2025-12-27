# This file is part of beets.
# Copyright 2025, Angelos Exaftopoulos.
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

"""Tests for harmonicmix plugin. Test only cover the logic class"""

from beetsplug.harmonicmix import HarmonicLogic


def test_standard_compatibility():
    """Verify standard Circle of Fifths relationships."""
    # Case: C Major should contain G (Dominant), F (Subdominant), Am (Relative Minor)
    keys = HarmonicLogic.get_compatible_keys("C")
    assert "G" in keys
    assert "F" in keys
    assert "Am" in keys

    # Case: Am should match Em
    keys_am = HarmonicLogic.get_compatible_keys("Am")
    assert "Em" in keys_am


def test_enharmonic_compatibility():
    """Verify that enharmonics are handled."""
    # Db should behave like C#
    keys_db = HarmonicLogic.get_compatible_keys("Db")
    keys_cs = HarmonicLogic.get_compatible_keys("C#")

    # They should share neighbors
    assert "Ab" in keys_db  # Dominant of Db
    assert "G#" in keys_cs  # Dominant of C# (G#=Ab)


def test_whitespace_handling():
    """Verify that whitespace is stripped from keys."""
    keys_plain = HarmonicLogic.get_compatible_keys("C")
    keys_spaced = HarmonicLogic.get_compatible_keys(" C ")
    assert keys_plain == keys_spaced


def test_unknown_keys():
    """Verify that unknown keys return an empty list."""
    assert HarmonicLogic.get_compatible_keys("H#") == []
    assert HarmonicLogic.get_compatible_keys("NotAKey") == []
    assert HarmonicLogic.get_compatible_keys(None) == []


def test_bpm_range_calculation():
    """Verify the BPM range logic (+/- 8%)."""
    # 100 BPM -> Range should be 92 to 108
    min_b, max_b = HarmonicLogic.get_bpm_range(100, 0.08)
    assert min_b == 92.0
    assert max_b == 108.0


def test_bpm_range_edge_cases():
    """Verify BPM edge cases (None, Zero, String input)."""
    # None or Zero should return (0, 0)
    assert HarmonicLogic.get_bpm_range(None) == (0, 0)
    assert HarmonicLogic.get_bpm_range(0) == (0, 0)

    # Strings should be converted safely
    min_b, max_b = HarmonicLogic.get_bpm_range("100")
    assert min_b == 92.0
    assert max_b == 108.0

    # Invalid strings should return (0, 0)
    assert HarmonicLogic.get_bpm_range("fast") == (0, 0)
