import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from idscanner.operations import (
    ScanCancelled,
    card_from_file,
    choose_scanner,
    find_scanners,
    save_pdf_atomic,
    scan_side,
)


class OperationsTests(unittest.TestCase):
    def test_card_from_file_reports_whether_a_card_was_found(self):
        with tempfile.TemporaryDirectory() as directory:
            card = Path(directory) / "card.png"
            image = Image.new("RGB", (1600, 1200), "white")
            ImageDraw.Draw(image).rounded_rectangle((300, 300, 1156, 840), 30, fill="#2a4d8f")
            image.save(card)
            empty = Path(directory) / "empty.png"
            Image.new("RGB", (800, 600), "white").save(empty)

            side, found = card_from_file(card)
            self.assertTrue(found)
            self.assertAlmostEqual(side.width / side.height, 856 / 540, delta=0.02)
            side, found = card_from_file(empty)
            self.assertFalse(found)
            self.assertEqual(side.size, (800, 600))

    def test_failed_export_preserves_existing_document(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "card.pdf"
            output.write_bytes(b"original PDF")

            def fail(images, target, dpi):
                target.write_bytes(b"incomplete")
                raise OSError("disk full")

            with patch("idscanner.operations.id2pdf.save_pdf", side_effect=fail):
                with self.assertRaises(OSError):
                    save_pdf_atomic(Image.new("RGB", (10, 10)), output)
            self.assertEqual(output.read_bytes(), b"original PDF")
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_successful_export_replaces_document(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "card.pdf"
            output.write_bytes(b"old")
            save_pdf_atomic(Image.new("RGB", (10, 10)), output)
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(list(Path(directory).iterdir()), [output])

    @unittest.skipUnless(os.name == "posix", "Linux/SANE process sessions")
    def test_timeout_and_cancel_reap_scanner_process(self):
        popen = subprocess.Popen
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                processes = []
                event = threading.Event()

                def start(*args, processes=processes, cancelled=cancelled, event=event, **kwargs):
                    process = popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
                    processes.append(process)
                    if cancelled:
                        event.set()
                    return process

                with patch("idscanner.operations.subprocess.Popen", side_effect=start):
                    with self.assertRaises(ScanCancelled if cancelled else TimeoutError):
                        scan_side("test", True, event, timeout=0.15)
                self.assertIsNotNone(processes[0].poll())


@unittest.skipUnless(os.name == "posix", "SANE runs on Linux")
class ScannerDiscoveryTests(unittest.TestCase):
    def scanimage(self, script):
        """Put a fake scanimage, running the given shell script, first on PATH."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        program = Path(directory.name) / "scanimage"
        program.write_text(f"#!/bin/sh\n{script}\n")
        program.chmod(0o755)
        patcher = patch.dict(os.environ, {"PATH": f"{directory.name}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_lists_scanners_without_webcams(self):
        self.scanimage(
            """cat <<'EOF'
device `airscan:e0:Canon MF240' is a eSCL Canon MF240 ip=192.168.1.5
device `v4l:/dev/video0' is a Noname Integrated Camera virtual device
device `genesys:libusb:001:004' is a Canon LiDE 220 flatbed scanner
EOF"""
        )
        self.assertEqual(
            find_scanners(threading.Event()),
            [
                ("airscan:e0:Canon MF240", "a eSCL Canon MF240 ip=192.168.1.5"),
                ("genesys:libusb:001:004", "a Canon LiDE 220 flatbed scanner"),
            ],
        )

    def test_missing_sane_returns_none(self):
        with patch.dict(os.environ, {"PATH": tempfile.gettempdir()}):
            self.assertIsNone(find_scanners(threading.Event()))

    def test_failure_raises_scanimage_message(self):
        self.scanimage("echo 'scanimage: open of device failed' >&2; exit 1")
        with self.assertRaisesRegex(RuntimeError, "open of device failed"):
            find_scanners(threading.Event())

    def test_cancel_and_timeout_stop_a_slow_search(self):
        self.scanimage("sleep 60")
        cancel = threading.Event()
        threading.Timer(0.2, cancel.set).start()
        with self.assertRaises(ScanCancelled):
            find_scanners(cancel)
        with self.assertRaises(TimeoutError):
            find_scanners(threading.Event(), timeout=0.2)

    def test_choose_scanner_prefers_remembered_then_current_then_first(self):
        devices = [("a", "A"), ("b", "B"), ("c", "C")]
        self.assertEqual(choose_scanner(devices, "c", "b"), "c")
        self.assertEqual(choose_scanner(devices, "gone", "b"), "b")
        self.assertEqual(choose_scanner(devices, None, None), "a")
        self.assertIsNone(choose_scanner([], "a"))


if __name__ == "__main__":
    unittest.main()
