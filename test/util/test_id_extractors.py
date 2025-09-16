from typing import NamedTuple

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


class SourceWithURL(NamedTuple):
    source: str
    url: str


source_with_urls = [
    SourceWithURL("spotify", "https://open.spotify.com/album/39WqpoPgZxygo6YQjehLJJ"),
    SourceWithURL("deezer", "https://www.deezer.com/album/176356382"),
    SourceWithURL("beatport", "https://www.beatport.com/release/album-name/3089651"),
    SourceWithURL("discogs", "http://www.discogs.com/G%C3%BCnther-Lause-Meru-Ep/release/4354798"),
    SourceWithURL("musicbrainz", "https://musicbrainz.org/entity/28e32c71-1450-463e-92bf-e0a46446fc11"),
]  # fmt: skip


@pytest.mark.parametrize("source", [s.source for s in source_with_urls])
@pytest.mark.parametrize("source_with_url", source_with_urls)
def test_match_source_url(source, source_with_url):
    if source == source_with_url.source:
        assert extract_release_id(source, source_with_url.url)
    else:
        assert not extract_release_id(source, source_with_url.url), (
            f"Source {source} pattern should not match {source_with_url.source} URL"
        )
