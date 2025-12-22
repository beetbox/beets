from beetsplug._utils.musicbrainz import MusicBrainzAPI


def test_group_relations():
    raw_release = {
        "id": "r1",
        "relations": [
            {"target-type": "artist", "type": "vocal", "name": "A"},
            {"target-type": "url", "type": "streaming", "url": "http://s"},
            {"target-type": "url", "type": "purchase", "url": "http://p"},
            {
                "target-type": "work",
                "type": "performance",
                "work": {
                    "relations": [
                        {
                            "artist": {"name": "幾田りら"},
                            "target-type": "artist",
                            "type": "composer",
                        },
                        {
                            "target-type": "url",
                            "type": "lyrics",
                            "url": {
                                "resource": "https://utaten.com/lyric/tt24121002/"
                            },
                        },
                        {
                            "artist": {"name": "幾田りら"},
                            "target-type": "artist",
                            "type": "lyricist",
                        },
                        {
                            "target-type": "url",
                            "type": "lyrics",
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

    assert MusicBrainzAPI._group_relations(raw_release) == {
        "id": "r1",
        "artist-relations": [{"type": "vocal", "name": "A"}],
        "url-relations": [
            {"type": "streaming", "url": "http://s"},
            {"type": "purchase", "url": "http://p"},
        ],
        "work-relations": [
            {
                "type": "performance",
                "work": {
                    "artist-relations": [
                        {"type": "composer", "artist": {"name": "幾田りら"}},
                        {"type": "lyricist", "artist": {"name": "幾田りら"}},
                    ],
                    "url-relations": [
                        {
                            "type": "lyrics",
                            "url": {
                                "resource": "https://utaten.com/lyric/tt24121002/"
                            },
                        },
                        {
                            "type": "lyrics",
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
