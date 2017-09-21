_size_suffixes = ('B', 'KB', 'MB', 'GB', 'TB')


def humanize_bytes(size, precision=2):
    """Convert data size to human-readable units"""
    suffix_idx = 0
    while size >= 1024 and suffix_idx < len(_size_suffixes) - 1:
        suffix_idx += 1  # Increment the index of the suffix.
        size /= 1024  # Apply the division.
    return '{size:0.{prec}f} {unit}'.format(size=size,
                                            prec=precision,
                                            unit=_size_suffixes[suffix_idx])
