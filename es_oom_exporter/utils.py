from typing import Optional


def ensure_slash(txt: Optional[str]) -> Optional[str]:
    """Add the endinf slash."""
    if txt is None:
        return None
    if txt.endswith("/"):
        return txt
    return txt + "/"
