from beets.util.pathformats import get_path_formats


def test_get_path_formats(config):
    """Ensure the function prepends custom and preserves defaults."""
    # override the default 'singleton' path and add a new one
    config["paths"].set({"singleton": "bar", "new": "hello"})

    assert get_path_formats(config["paths"]) == [
        ("singleton:true", "bar"),
        ("new", "hello"),
        # defaults
        ("default", "$albumartist/$album%aunique{}/$track $title"),
        ("comp:true", "Compilations/$album%aunique{}/$track $title"),
    ]
