"""General validators."""


def nonempty_str(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("String must be non-empty")
    return v
