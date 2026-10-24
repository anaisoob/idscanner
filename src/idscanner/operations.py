"""Bounded scanner operations and atomic document export."""

import io
import os
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


def scan_side(device: str, front: bool, cancel: Event, timeout: float = 180) -> Image.Image:
    # SANE scanning is supported on Linux. A separate session lets us stop both
    # the worker and its scanimage child, without changing id2pdf's globals.
    if os.name != "posix":
        raise RuntimeError("Scanning requires Linux/SANE. You can still choose image files.")
    if cancel.is_set():
        raise ScanCancelled("Scanning cancelled.")
    process = subprocess.Popen(
        [sys.executable, "-m", "idscanner.scan_worker", device, "front" if front else "back"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel.is_set():
                raise ScanCancelled("Scanning cancelled.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Scanning timed out. Check the scanner and try again.")
            try:
                output, error = process.communicate(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if cancel.is_set():
            raise ScanCancelled("Scanning cancelled.")
        if process.returncode:
            raise id2pdf.ScanError(error.decode(errors="replace").strip() or "Scanning failed.")
        with Image.open(io.BytesIO(output)) as image:
            return image.convert("RGB")
    finally:
        # Kill the whole session even if the worker has already exited: a
        # scanner child may still be running or holding a pipe open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()


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
