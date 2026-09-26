"""settings.json persistence and masking (PLAN 8.9)."""

DEFAULTS = {}


def load(data_dir):
    raise NotImplementedError


def save(data_dir, settings) -> None:
    raise NotImplementedError


def masked(settings):
    raise NotImplementedError
