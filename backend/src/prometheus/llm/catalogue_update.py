"""Updating the model catalogue from pi.dev (PLAN 15.4.12). Stub."""


def bundled_providers(pi_cli) -> list:
    return []


def catalogue_folder(data_dir):
    return None


def refresh(data_dir, *, pi_cli, fetch=None, proxy="", now=None) -> dict:
    return {}


def updated_at(data_dir):
    return None


def due(data_dir, *, now=None) -> bool:
    return False
