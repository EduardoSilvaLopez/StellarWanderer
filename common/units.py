"""Compact formatting of distances and speeds, for any part of the game (instruments, labels, logs)."""

COMPACT_DISTANCE_UNITS = (('m', 1.0), ('Km', 1e3), ('Mm', 1e6), ('Gm', 1e9), ('Tm', 1e12), ('Pm', 1e15))


def format_compact_distance(meters: float) -> str:
    """Compact format: whole metres below 10^6, then Km, Mm, Gm, Tm and Pm (the last unit), each rounded."""
    for symbol, scale in COMPACT_DISTANCE_UNITS:
        value = round(meters / scale)
        if abs(value) < 1_000_000 or symbol == 'Pm':
            return f'{value} {symbol}'
    return f'{value} {symbol}'


def format_compact_speed(meters_per_second: float) -> str:
    """Signed compact speed in the units of format_compact_distance, per second: '+12 m/s', '-3 Km/s', '0 m/s'."""
    text = format_compact_distance(meters_per_second)
    if not text.startswith(('-', '0 ')):
        text = '+' + text
    return text + '/s'
