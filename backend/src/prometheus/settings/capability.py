"""Model image capability from `pi --offline --list-models` output (PLAN 8.7)."""

import subprocess


def parse_capabilities(output: str) -> dict:
    capabilities = {}
    for line in (output or "").splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[1] != "model":
            capabilities[parts[1]] = parts[5].lower() == "yes"
    return capabilities


def model_supports_images(output: str, model: str) -> bool:
    return parse_capabilities(output).get(model, False)


def query_supports_images(node_exe, pi_cli, data_dir, llm: dict) -> bool:
    """Ask Pi whether the configured model accepts images (PLAN 8.7, 15.2-1)."""
    return False
