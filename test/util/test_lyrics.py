import textwrap

from beets.util.lyrics import Lyrics


class TestLyrics:
    def test_instrumental_lyrics(self):
        lyrics = Lyrics(
            "[Instrumental]", "lrclib", url="https://lrclib.net/api/1"
        )

        assert lyrics.full_text == "[Instrumental]"
        assert lyrics.backend == "lrclib"
        assert lyrics.url == "https://lrclib.net/api/1"
        assert lyrics.language is None
        assert lyrics.translation_language is None

    def test_from_legacy_text(self, is_importable):
        text = textwrap.dedent("""
        [00:00.00] Some synced lyrics / Quelques paroles synchronisées
        [00:00.50]
        [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées

        Source: https://lrclib.net/api/1/""")

        lyrics = Lyrics.from_legacy_text(text)

        assert lyrics.full_text == textwrap.dedent(
            """
            [00:00.00] Some synced lyrics / Quelques paroles synchronisées
            [00:00.50]
            [00:01.00] Some more synced lyrics / Quelques paroles plus synchronisées"""
        )
        assert lyrics.backend == "lrclib"
        assert lyrics.url == "https://lrclib.net/api/1/"
        langdetect_available = is_importable("langdetect")
        assert lyrics.language == ("EN" if langdetect_available else None)
        assert lyrics.translation_language == (
            "FR" if langdetect_available else None
        )
