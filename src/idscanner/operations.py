"""Bounded scanner operations and atomic document export."""

import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threading import Event

import id2pdf
from PIL import Image


class ScanCancelled(Exception):
    pass


def run_bounded(command: list[str], cancel: Event, timeout: float, timeout_message: str) -> tuple[int, bytes, bytes]:
    """Run a command that can be cancelled; returns its exit code, stdout and stderr.

    A separate session lets us stop the command and any children it starts.
    """
    if cancel.is_set():
        raise ScanCancelled("Scanning cancelled.")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel.is_set():
                raise ScanCancelled("Scanning cancelled.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(timeout_message)
            try:
                output, error = process.communicate(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if cancel.is_set():
            raise ScanCancelled("Scanning cancelled.")
        return process.returncode, output, error
    finally:
        # Kill the whole session even if the command has already exited: a
        # child may still be running or holding a pipe open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()


def find_scanners(cancel: Event, timeout: float = 30) -> list[tuple[str, str]] | None:
    """SANE devices as (name, description) pairs, or None when SANE is not installed."""
    try:
        returncode, output, error = run_bounded(
            ["scanimage", "-L"], cancel, timeout, "Looking for scanners timed out. Check the scanner and try again."
        )
    except FileNotFoundError:
        return None
    if returncode:
        raise RuntimeError(error.decode(errors="replace").strip() or "Scanner discovery failed.")
    return [
        (name, description)
        for name, description in re.findall(r"device `([^']+)' is (.+)", output.decode(errors="replace"))
        if not name.startswith("v4l")  # webcams
    ]


def choose_scanner(devices: list[tuple[str, str]], *preferred: str | None) -> str | None:
    """The first preferred device name that is present, otherwise the first device."""
    names = [name for name, _ in devices]
    return next((name for name in preferred if name in names), names[0] if names else None)


def scan_side(device: str, front: bool, cancel: Event, timeout: float = 180) -> Image.Image:
    # SANE scanning is supported on Linux. The worker runs in its own process so
    # it can be stopped together with its scanimage child, without changing id2pdf's globals.
    if os.name != "posix":
        raise RuntimeError("Scanning requires Linux/SANE. You can still choose image files.")
    returncode, output, error = run_bounded(
        [sys.executable, "-m", "idscanner.scan_worker", device, "front" if front else "back"],
        cancel,
        timeout,
        "Scanning timed out. Check the scanner and try again.",
    )
    if returncode:
        raise id2pdf.ScanError(error.decode(errors="replace").strip() or "Scanning failed.")
    with Image.open(io.BytesIO(output)) as image:
        return image.convert("RGB")


def save_pdf_atomic(page: Image.Image, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".idscanner-", suffix=".pdf", dir=output.parent)
    temporary = Path(name)
    try:
        os.close(fd)
        id2pdf.save_pdf([page], temporary, id2pdf.CARD_DPI)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
