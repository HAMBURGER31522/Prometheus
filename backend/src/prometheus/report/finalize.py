"""Report finalization (PLAN 8.6): fill, inline, style, checks."""


class FinalizeError(RuntimeError):
    code = "IMPLEMENTATION_FAILURE"


def finalize_report(work_report, final_path, work_dir) -> str:
    raise NotImplementedError


def extract_report_title(html: str) -> str:
    raise NotImplementedError
