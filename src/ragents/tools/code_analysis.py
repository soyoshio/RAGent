"""Code snippet analysis Tool."""


def analyze_code(code: str, language: str = "python") -> dict:
    return {"language": language, "lines": len(code.splitlines())}
