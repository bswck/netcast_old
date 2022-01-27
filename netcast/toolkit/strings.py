from __future__ import annotations


def truncate(
        string: str,
        width: int = 20,
        placeholder: str = '...',
        stats: str | None = ' (%d truncated)'
) -> str:
    """
    Truncate a string and put the given placeholder in the place of removed characters.

    truncate(str(1 << 99), 10) -> '63382...88 (23 truncated)'

    truncate(str(1 << 99), 10, stats=None) -> '63382...88'  # fits 20 characters
    """
    length = len(string)
    truncated = 0
    if length > width:
        width -= len(placeholder)
        stop = width // 2 + 1
        start = stop + length - width
        segments = (string[:stop], string[start:])
        truncated = start - stop
        string = placeholder.join(segments)
    if stats is None:
        stats = ''
    if stats:
        if '%d' in stats:
            stats %= truncated
        if truncated:
            string += stats
    return string
