"""Code generation Tool."""


def generate_snippet(description: str, language: str = "python") -> str:
    return f"# {description}\n# TODO: implement in {language}"
