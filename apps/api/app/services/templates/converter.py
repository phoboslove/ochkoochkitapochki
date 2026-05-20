"""Legacy Office → modern format conversion via LibreOffice headless.

The soffice / libreoffice binary is launched as a subprocess. Conversion is
isolated per file in a temp dir so a crashing document never breaks others.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal


LEGACY_FORMATS = {"doc", "xls", "rtf"}
TARGET_FOR = {"doc": "docx", "xls": "xlsx", "rtf": "docx"}


class ConverterUnavailable(Exception):
    """Raised when no LibreOffice binary is present on the host."""


def find_soffice() -> str | None:
    """Locate soffice / libreoffice. Returns None when not installed."""
    # Explicit override.
    if (env := os.environ.get("LIBREOFFICE_BIN")) and Path(env).exists():
        return env
    # Common Windows install paths.
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    # PATH lookup (works on Linux/macOS).
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path: return path
    return None


def is_available() -> bool:
    return find_soffice() is not None


def convert_to(
    source: bytes, *, source_filename: str, target: Literal["docx", "xlsx", "pdf"],
    timeout: int = 60,
) -> bytes:
    """Convert source bytes to ``target`` format. Returns bytes of the result.

    Raises ``ConverterUnavailable`` when soffice is not installed,
    and ``RuntimeError`` for per-file conversion failures.
    """
    bin_path = find_soffice()
    if not bin_path:
        raise ConverterUnavailable(
            "LibreOffice is not installed on this machine. "
            "Install it (https://www.libreoffice.org) or set LIBREOFFICE_BIN."
        )

    with tempfile.TemporaryDirectory(prefix="bx-conv-") as tmp:
        src = Path(tmp) / source_filename
        src.write_bytes(source)
        # `--convert-to docx` produces <stem>.docx in the outdir.
        try:
            proc = subprocess.run(
                [bin_path, "--headless", "--convert-to", target,
                 "--outdir", tmp, str(src)],
                capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"conversion timed out after {timeout}s") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"libreoffice exited with code {proc.returncode}: "
                f"{(proc.stderr or proc.stdout).decode(errors='ignore')[:200]}"
            )
        out_path = Path(tmp) / f"{src.stem}.{target}"
        if not out_path.exists():
            # Some files come out as .docx even when input is .docx-like .doc — try fallback.
            cands = list(Path(tmp).glob(f"*.{target}"))
            if not cands:
                raise RuntimeError("converter produced no output file")
            out_path = cands[0]
        return out_path.read_bytes()
