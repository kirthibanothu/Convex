import re


_size_suffixes = ('B', 'KB', 'MB', 'GB', 'TB')


def humanize_bytes(size: int, precision=2) -> str:
    """Convert data size to human-readable units.

    >>> humanize_bytes(20000)
    '19.53 KB'

    >>> humanize_bytes(int(5E8), precision=4)
    '476.8372 MB'
    """
    suffix_idx = 0
    while size >= 1024 and suffix_idx < len(_size_suffixes) - 1:
        suffix_idx += 1  # Increment the index of the suffix.
        size /= 1024  # Apply the division.
    return '{size:0.{prec}f} {unit}'.format(size=size,
                                            prec=precision,
                                            unit=_size_suffixes[suffix_idx])


def dehumanize_bytes(s: str) -> int:
    """Convert human-readable size to bytes.

    Raise ValueError if conversion cannot be performed.

    >>> dehumanize_bytes('2.5 kb')
    2560
    """
    match = re.match(r'(\d*\.{0,1}\d*)\s*(\w+)', s)
    if not match:
        raise ValueError('Could not parse bytes from \'{}\''.format(s))
    size, unit = match.groups()
    size = float(size)
    unit = unit.upper()
    try:
        unit_idx = _size_suffixes.index(unit)
    except ValueError:
        raise ValueError(
            'Unit \'{}\' not one of {}'.format(unit, _size_suffixes)
        ) from None
    return int(size * (1024 ** unit_idx))
