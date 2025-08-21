import time
from tkinter import N

import pytest

import beets
from beets.dbcore import types
from beets.util import normpath


def test_datetype():
    t = types.DATE

    # format
    time_format = beets.config["time_format"].as_str()
    time_local = time.strftime(time_format, time.localtime(123456789))
    assert time_local == t.format(123456789)
    # parse
    assert 123456789.0 == t.parse(time_local)
    assert 123456789.0 == t.parse("123456789.0")
    assert t.null == t.parse("not123456789.0")
    assert t.null == t.parse("1973-11-29")


def test_pathtype():
    t = types.PathType()

    # format
    assert "/tmp" == t.format("/tmp")
    assert "/tmp/\xe4lbum" == t.format("/tmp/\u00e4lbum")
    # parse
    assert normpath(b"/tmp") == t.parse("/tmp")
    assert normpath(b"/tmp/\xc3\xa4lbum") == t.parse("/tmp/\u00e4lbum/")


def test_musicalkey():
    t = types.MusicalKey()

    # parse
    assert "C#m" == t.parse("c#m")
    assert "Gm" == t.parse("g   minor")
    assert "Not c#m" == t.parse("not C#m")


def test_durationtype():
    t = types.DurationType()

    # format
    assert "1:01" == t.format(61.23)
    assert "60:01" == t.format(3601.23)
    assert "0:00" == t.format(None)
    # parse
    assert 61.0 == t.parse("1:01")
    assert 61.23 == t.parse("61.23")
    assert 3601.0 == t.parse("60:01")
    assert t.null == t.parse("1:00:01")
    assert t.null == t.parse("not61.23")
    # config format_raw_length
    beets.config["format_raw_length"] = True
    assert 61.23 == t.format(61.23)
    assert 3601.23 == t.format(3601.23)


@pytest.mark.parametrize(
    "type, type_params",
    [
        (types.DEFAULT, (str, type(None))),
        # ints
        (types.Integer(), (int, int)),
        (types.NullInteger(), (int, type(None))),
        (types.PaddedInt(2), (int, int)),
        (types.NullPaddedInt(3), (int, type(None))),
        (types.ScaledInt(2, "foo"), (int, int)),
        (types.Id(), (int, type(None))),
        # floats
        (types.Float(), (float, float)),
        (types.NullFloat(), (float, type(None))),
        (types.DateType(), (float, float)),
        (types.DurationType(), (float, float)),
        # Strings
        (types.String(), (str, str)),
        (types.DelimitedString(","), (list[str], list[str])),
        (types.MusicalKey(), (str, type(None))),
        # Other
        (types.Boolean(), (bool, bool)),
        # Paths
        (types.PathType(), (bytes, bytes)),
        (types.NullPathType(), (bytes, type(None))),
    ],
)
def test_get_type_parameters(type: types.Type, type_params):
    assert type_params == types.get_type_parameters(type)
