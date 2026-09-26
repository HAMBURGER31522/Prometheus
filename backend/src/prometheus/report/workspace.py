"""Report workspace assembly and PiRunner wiring (PLAN 8.6)."""


def build_input_json(row: dict) -> dict:
    raise NotImplementedError


def build_runner_kwargs(row: dict, settings: dict, node_exe: str, pi_cli: str, *,
                        figures: bool, model_supports_images: bool) -> dict:
    raise NotImplementedError


def run_report_stage(data_dir, item_id: str, row: dict, settings: dict, *,
                     node_exe: str, pi_cli: str):
    raise NotImplementedError
