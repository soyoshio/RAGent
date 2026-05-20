"""Web fetch Tool (curl / requests implementation)."""

import urllib.request


def fetch(url: str, timeout: int = 10) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")
