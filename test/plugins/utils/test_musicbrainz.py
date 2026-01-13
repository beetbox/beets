import pytest

from beetsplug._utils.musicbrainz import MusicBrainzAPI


def test_normalize_data():
    raw_release = {
        "id": "r1",
        "relations": [
            {
                "target-type": "artist",
                "type": "vocal",
                "type-id": "0fdbe3c6-7700-4a31-ae54-b53f06ae1cfa",
                "name": "A",
            },
            {
                "target-type": "url",
                "type": "streaming",
                "type-id": "b5f3058a-666c-406f-aafb-f9249fc7b122",
                "url": "http://s",
            },
            {
                "target-type": "url",
                "type": "purchase for download",
                "type-id": "92777657-504c-4acb-bd33-51a201bd57e1",
                "url": "http://p",
            },
            {
                "target-type": "work",
                "type": "performance",
                "type-id": "a3005666-a872-32c3-ad06-98af558e99b0",
                "work": {
                    "relations": [
                        {
                            "artist": {"name": "幾田りら"},
                            "target-type": "artist",
                            "type": "composer",
                            "type-id": "d59d99ea-23d4-4a80-b066-edca32ee158f",
                        },
                        {
                            "target-type": "url",
                            "type": "lyrics",
                            "type-id": "e38e65aa-75e0-42ba-ace0-072aeb91a538",
                            "url": {
                                "resource": "https://utaten.com/lyric/tt24121002/"
                            },
                        },
                        {
                            "artist": {"name": "幾田りら"},
                            "target-type": "artist",
                            "type": "lyricist",
                            "type-id": "3e48faba-ec01-47fd-8e89-30e81161661c",
                        },
                        {
                            "target-type": "url",
                            "type": "lyrics",
                            "type-id": "e38e65aa-75e0-42ba-ace0-072aeb91a538",
                            "url": {
                                "resource": "https://www.uta-net.com/song/366579/"
                            },
                        },
                    ],
                    "title": "百花繚乱",
                    "type": "Song",
                },
            },
        ],
    }

    assert MusicBrainzAPI._normalize_data(raw_release) == {
        "id": "r1",
        "artist_relations": [
            {
                "type": "vocal",
                "type_id": "0fdbe3c6-7700-4a31-ae54-b53f06ae1cfa",
                "name": "A",
            }
        ],
        "url_relations": [
            {
                "type": "streaming",
                "type_id": "b5f3058a-666c-406f-aafb-f9249fc7b122",
                "url": "http://s",
            },
            {
                "type": "purchase for download",
                "type_id": "92777657-504c-4acb-bd33-51a201bd57e1",
                "url": "http://p",
            },
        ],
        "work_relations": [
            {
                "type": "performance",
                "type_id": "a3005666-a872-32c3-ad06-98af558e99b0",
                "work": {
                    "artist_relations": [
                        {
                            "type": "composer",
                            "type_id": "d59d99ea-23d4-4a80-b066-edca32ee158f",
                            "artist": {
                                "name": "幾田りら",
                            },
                        },
                        {
                            "type": "lyricist",
                            "type_id": "3e48faba-ec01-47fd-8e89-30e81161661c",
                            "artist": {
                                "name": "幾田りら",
                            },
                        },
                    ],
                    "url_relations": [
                        {
                            "type": "lyrics",
                            "type_id": "e38e65aa-75e0-42ba-ace0-072aeb91a538",
                            "url": {
                                "resource": "https://utaten.com/lyric/tt24121002/"
                            },
                        },
                        {
                            "type": "lyrics",
                            "type_id": "e38e65aa-75e0-42ba-ace0-072aeb91a538",
                            "url": {
                                "resource": "https://www.uta-net.com/song/366579/"
                            },
                        },
                    ],
                    "title": "百花繚乱",
                    "type": "Song",
                },
            },
        ],
    }


@pytest.mark.parametrize(
    "field, term, expected",
    [
        ("artist", '  AC/DC + "[Live]"  ', r"artist:(ac\/dc \+ \"\[live\]\")"),
        ("", "Foo:Bar", r"foo\:bar"),
        ("artist", "   ", ""),
    ],
)
def test_format_search_term(field, term, expected):
    assert MusicBrainzAPI.format_search_term(field, term) == expected
