"""Model image capability from --list-models output (PLAN 8.7)."""


def parse_capabilities(output: str) -> dict:
    raise NotImplementedError


def model_supports_images(output: str, model: str) -> bool:
    raise NotImplementedError
