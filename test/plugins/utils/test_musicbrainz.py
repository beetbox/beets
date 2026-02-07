from beetsplug._utils.musicbrainz import MusicBrainzAPI

import pytest


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


class TestSearchQueryConstruction:
    """Test query construction in the search method."""

    @pytest.fixture
    def api(self):
        return MusicBrainzAPI()

    @pytest.fixture
    def mock_get_json(self, monkeypatch):
        """Mock get_json to capture queries without making actual API calls."""
        queries = []
        
        def capture_query(*args, **kwargs):
            if 'params' in kwargs and 'query' in kwargs['params']:
                queries.append(kwargs['params']['query'])
            return {"releases": []}
        
        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_json",
            capture_query
        )
        return queries

    def test_uuid_not_quoted(self, api, mock_get_json):
        """Test that valid UUIDs are not quoted in search queries."""
        uuid = "89ad4ac3-39f7-470e-963a-56509c546377"
        api.search("release", {"arid": uuid})
        
        assert len(mock_get_json) == 1
        query = mock_get_json[0]
        assert f"arid:{uuid}" in query
        assert f'arid:"{uuid}"' not in query

    def test_string_quoted(self, api, mock_get_json):
        """Test that regular strings are quoted in search queries."""
        api.search("release", {"artist": "Test Artist"})
        
        assert len(mock_get_json) == 1
        query = mock_get_json[0]
        assert 'artist:"test artist"' in query

    def test_mixed_uuid_and_string(self, api, mock_get_json):
        """Test that UUIDs and strings are formatted correctly together."""
        uuid = "89ad4ac3-39f7-470e-963a-56509c546377"
        api.search("release", {
            "release": "Test Album",
            "arid": uuid
        })
        
        assert len(mock_get_json) == 1
        query = mock_get_json[0]
        assert 'release:"test album"' in query
        assert f"arid:{uuid}" in query
        assert f'arid:"{uuid}"' not in query

    def test_invalid_uuid_quoted(self, api, mock_get_json):
        """Test that invalid UUID-like strings are quoted."""
        # Wrong length
        api.search("release", {"test": "not-a-uuid-123"})
        assert 'test:"not-a-uuid-123"' in mock_get_json[0]
        
        mock_get_json.clear()
        
        # Wrong hyphen positions
        api.search("release", {"test": "abcd-efgh-ijkl-mnop-qrstuvwxyz123456"})
        assert 'test:"abcd-efgh-ijkl-mnop-qrstuvwxyz123456"' in mock_get_json[0]
        
        mock_get_json.clear()
        
        # Correct length and hyphen count but wrong positions
        api.search("release", {"test": "12345678-123-456-7890-123456789012"})
        assert 'test:"12345678-123-456-7890-123456789012"' in mock_get_json[0]

    def test_empty_value_filtered(self, api, mock_get_json):
        """Test that empty values are filtered out of the query."""
        api.search("release", {
            "release": "Test Album",
            "empty": ""
        })
        
        assert len(mock_get_json) == 1
        query = mock_get_json[0]
        assert 'release:"test album"' in query
        assert "empty" not in query

