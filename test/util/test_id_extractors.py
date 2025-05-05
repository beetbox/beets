import pytest

from beets.util.id_extractors import extract_release_id


@pytest.mark.parametrize(
    "source, id_string, expected",
    [
        ("spotify", "39WqpoPgZxygo6YQjehLJJ", "39WqpoPgZxygo6YQjehLJJ"),
        ("spotify", "blah blah", None),
        ("spotify", "https://open.spotify.com/album/39WqpoPgZxygo6YQjehLJJ", "39WqpoPgZxygo6YQjehLJJ"),  # noqa: E501
        ("deezer", "176356382", "176356382"),
        ("deezer", "blah blah", None),
        ("deezer", "https://www.deezer.com/album/176356382", "176356382"),
        ("beatport", "3089651", "3089651"),
        ("beatport", "blah blah", None),
        ("beatport", "https://www.beatport.com/release/album-name/3089651", "3089651"),  # noqa: E501
        ("discogs", "http://www.discogs.com/G%C3%BCnther-Lause-Meru-Ep/release/4354798", "4354798"),  # noqa: E501
        ("discogs", "http://www.discogs.com/release/4354798-G%C3%BCnther-Lause-Meru-Ep", "4354798"),  # noqa: E501
        ("discogs", "http://www.discogs.com/G%C3%BCnther-4354798Lause-Meru-Ep/release/4354798", "4354798"),  # noqa: E501
        ("discogs", "http://www.discogs.com/release/4354798-G%C3%BCnther-4354798Lause-Meru-Ep/", "4354798"),  # noqa: E501
        ("discogs", "[r4354798]", "4354798"),
        ("discogs", "r4354798", "4354798"),
        ("discogs", "4354798", "4354798"),
        ("discogs", "yet-another-metadata-provider.org/foo/12345", None),
        ("discogs", "005b84a0-ecd6-39f1-b2f6-6eb48756b268", None),
        ("musicbrainz", "28e32c71-1450-463e-92bf-e0a46446fc11", "28e32c71-1450-463e-92bf-e0a46446fc11"),  # noqa: E501
        ("musicbrainz", "blah blah", None),
        ("musicbrainz", "https://musicbrainz.org/entity/28e32c71-1450-463e-92bf-e0a46446fc11", "28e32c71-1450-463e-92bf-e0a46446fc11"),  # noqa: E501
        ("bandcamp", "https://nameofartist.bandcamp.com/album/nameofalbum", "https://nameofartist.bandcamp.com/album/nameofalbum"),  # noqa: E501
    ],
)  # fmt: skip
def test_extract_release_id(source, id_string, expected):
    assert extract_release_id(source, id_string) == expected
