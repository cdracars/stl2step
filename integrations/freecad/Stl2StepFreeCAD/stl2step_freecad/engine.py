"""Process-isolated adapter for the stl2step CLI.

This module deliberately has no FreeCAD imports so its contract can be checked
with ordinary Python outside FreeCAD.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any


class EngineError(RuntimeError):
    """The converter could not be located or did not produce a usable result."""


def _bundled_relative_path() -> Path:
    machine = platform.machine().lower()
    if os.name == "nt":
        return Path("bin") / "windows-x86_64" / "stl2step.exe"
    if platform.system() == "Darwin":
        architecture = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
        return Path("bin") / f"macos-{architecture}" / "stl2step"
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
    return Path("bin") / f"linux-{architecture}" / "stl2step"


def resolve_executable(addon_directory: Path) -> Path:
    configured = os.environ.get("STL2STEP_EXECUTABLE")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise EngineError(
            f"STL2STEP_EXECUTABLE points to a missing file: {candidate}"
        )

    bundled = addon_directory / _bundled_relative_path()
    if bundled.is_file():
        return bundled.resolve()

    discovered = shutil.which("stl2step")
    if discovered:
        return Path(discovered).resolve()

    raise EngineError(
        "Could not find stl2step. Set STL2STEP_EXECUTABLE, put it on PATH, "
        f"or install the platform binary at {bundled}."
    )


def parse_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith("RESULT "):
            try:
                result = json.loads(line[len("RESULT ") :])
            except json.JSONDecodeError as exc:
                raise EngineError(f"Invalid RESULT JSON: {exc}") from exc
            if not isinstance(result, dict):
                raise EngineError("RESULT payload was not a JSON object")
            return result
    raise EngineError("stl2step did not emit a RESULT line")


def arguments(input_stl: Path, output_step: Path, *, units: str) -> list[str]:
    if units not in {"mm", "in"}:
        raise ValueError(f"unsupported STL units: {units}")
    return [
        str(input_stl),
        "-o",
        str(output_step),
        "--quiet",
        "--no-verify",
        "--engine",
        "trueform",
        "--units",
        units,
    ]
