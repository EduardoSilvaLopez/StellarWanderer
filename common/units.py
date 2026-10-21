"""Compact formatting of distances, speeds and durations, for any part of the game (instruments, labels, logs)."""

COMPACT_DISTANCE_UNITS = (('m', 1.0), ('Km', 1e3), ('Mm', 1e6), ('Gm', 1e9), ('Tm', 1e12), ('Pm', 1e15))


def format_compact_distance(meters: float) -> str:
    """Compact format: whole metres below 10^6, then Km, Mm, Gm, Tm and Pm (the last unit), each rounded."""
    for symbol, scale in COMPACT_DISTANCE_UNITS:
        value = round(meters / scale)
        if abs(value) < 1_000_000 or symbol == 'Pm':
            break
    return f'{value} {symbol}'


def format_compact_speed(meters_per_second: float) -> str:
    """Signed compact speed in the units of format_compact_distance, per second: '+12 m/s', '-3 Km/s', '0 m/s'."""
    text = format_compact_distance(meters_per_second)
    if not text.startswith(('-', '0 ')):
        text = '+' + text
    return text + '/s'

def format_compact_duration(seconds: float) -> str:
    """A duration in whole units of the two largest that fit: '40 s', '12 min', '3 h 20 min', '2 d 4 h' (the hour, the
    minute and the day, of 86,400 s, are the units the SI accepts next to the second)."""
    seconds = max(0, round(seconds))
    if seconds < 60:
        return f'{seconds} s'
    minutes = round(seconds / 60)
    if minutes < 60:
        return f'{minutes} min'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours} h {minutes} min'
    days, hours = divmod(hours, 24)
    return f'{days} d {hours} h'
