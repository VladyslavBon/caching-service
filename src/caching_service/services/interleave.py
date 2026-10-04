def interleave(first: list[str], second: list[str]) -> list[str]:
    """Alternate items of two equally long lists, starting with `first`."""
    if len(first) != len(second):
        # Silent truncation (plain zip) would drop data; callers must validate upfront.
        raise ValueError("Lists must have the same length")
    return [item for pair in zip(first, second, strict=True) for item in pair]
