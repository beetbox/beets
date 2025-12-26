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


def test_custom_enharmonics():
    """Verify advanced enharmonics such as E#==Fb"""
    # Case: Fbm should be compatible with Am (because Fbm == Em)
    keys_am = HarmonicLogic.get_compatible_keys("Am")
    assert "Fbm" in keys_am

    # Case: E# should be treated like F
    # F is compatible with C, so E# should be in C's list
    keys_c = HarmonicLogic.get_compatible_keys("C")
    assert "E#" in keys_c


def test_bpm_range_calculation():
    """Verify the BPM range logic (+/- 8%)."""
    # 100 BPM -> Range should be 92 to 108
    min_b, max_b = HarmonicLogic.get_bpm_range(100, 0.08)
    assert min_b == 92.0
    assert max_b == 108.0


def test_empty_input():
    """Ensure it doesn't crash on empty keys."""
    assert HarmonicLogic.get_compatible_keys(None) == []
    assert HarmonicLogic.get_compatible_keys("") == []
