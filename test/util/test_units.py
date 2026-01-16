import pytest

from beets.util.units import human_bytes, human_seconds


@pytest.mark.parametrize(
    "input_bytes,expected",
    [
        (0, "0.0 B"),
        (30, "30.0 B"),
        (pow(2, 10), "1.0 KiB"),
        (pow(2, 20), "1.0 MiB"),
        (pow(2, 30), "1.0 GiB"),
        (pow(2, 40), "1.0 TiB"),
        (pow(2, 50), "1.0 PiB"),
        (pow(2, 60), "1.0 EiB"),
        (pow(2, 70), "1.0 ZiB"),
        (pow(2, 80), "1.0 YiB"),
        (pow(2, 90), "1.0 HiB"),
        (pow(2, 100), "big"),
    ],
)
def test_human_bytes(input_bytes, expected):
    assert human_bytes(input_bytes) == expected


@pytest.mark.parametrize(
    "input_seconds,expected",
    [
        (0, "0.0 seconds"),
        (30, "30.0 seconds"),
        (60, "1.0 minutes"),
        (90, "1.5 minutes"),
        (125, "2.1 minutes"),
        (3600, "1.0 hours"),
        (86400, "1.0 days"),
        (604800, "1.0 weeks"),
        (31449600, "1.0 years"),
        (314496000, "1.0 decades"),
    ],
)
def test_human_seconds(input_seconds, expected):
    assert human_seconds(input_seconds) == expected
