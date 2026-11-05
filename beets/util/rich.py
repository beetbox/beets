import platformdirs
from rich.console import Console
from rich.theme import Theme


def get_theme() -> Theme | None:
    config_path = platformdirs.user_config_path("rich") / "config.ini"
    return Theme.read(str(config_path)) if config_path.exists() else None


def make_console(**kwargs) -> Console:
    kwargs.setdefault("theme", get_theme())
    kwargs.setdefault("force_terminal", True)
    kwargs.setdefault("force_interactive", True)
    kwargs.setdefault("emoji", True)
    kwargs.setdefault("highlight", False)
    return Console(**kwargs)
