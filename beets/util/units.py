import re


def raw_seconds_short(string: str) -> float:
    """Formats a human-readable M:SS string as a float (number of seconds).

    Raises ValueError if the conversion cannot take place due to `string` not
    being in the right format.
    """
    match = re.match(r"^(\d+):([0-5]\d)$", string)
    if not match:
        raise ValueError("String not in M:SS format")
    minutes, seconds = map(int, match.groups())
    return float(minutes * 60 + seconds)


def human_seconds_short(interval):
    """Formats a number of seconds as a short human-readable M:SS
    string.
    """
    interval = int(interval)
    return f"{interval // 60}:{interval % 60:02d}"


def human_bytes(size):
    """Formats size, a number of bytes, in a human-readable way."""
    powers = ["", "K", "M", "G", "T", "P", "E", "Z", "Y", "H"]
    unit = "B"
    for power in powers:
        if size < 1024:
            return f"{size:3.1f} {power}{unit}"
        size /= 1024.0
        unit = "iB"
    return "big"


def human_seconds(interval):
    """Formats interval, a number of seconds, as a human-readable time
    interval using English words.
    """
    units = [
        (1, "second"),
        (60, "minute"),
        (60, "hour"),
        (24, "day"),
        (7, "week"),
        (52, "year"),
        (10, "decade"),
    ]
    for i in range(len(units) - 1):
        increment, suffix = units[i]
        next_increment, _ = units[i + 1]
        interval /= float(increment)
        if interval < next_increment:
            break
    else:
        # Last unit.
        increment, suffix = units[-1]
        interval /= float(increment)

    return f"{interval:3.1f} {suffix}s"
