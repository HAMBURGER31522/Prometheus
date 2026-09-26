"""Model image capability from `pi --offline --list-models` output (PLAN 8.7)."""

import os
import subprocess

from prometheus import paths


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
    """Ask Pi whether the configured model accepts images (PLAN 8.7, 15.2-1).

    Pi hides every model that has no key, and only sees custom providers through
    the data dir's models.json, so both have to be in the environment.
    """
    key = llm.get("api_key") or ""
    provider = str(llm.get("provider") or "")
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(paths.pi_config_dir(data_dir)),
        "PI_API_KEY": key,
        f"{provider.upper().replace('-', '_')}_API_KEY": key,
    }
    listing = subprocess.run(
        [str(node_exe), str(pi_cli), "--offline", "--list-models"],
        capture_output=True, env=env, timeout=60, check=False,
    )
    return model_supports_images(listing.stdout.decode("utf-8", "replace"), llm.get("model", ""))
