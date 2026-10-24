import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from idscanner.operations import ScanCancelled, choose_scanner, find_scanners, save_pdf_atomic, scan_side


class OperationsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()


class ScannerDiscoveryTests(unittest.TestCase):
    def scanimage(self, stdout="", returncode=0, stderr=""):
        result = subprocess.CompletedProcess(["scanimage", "-L"], returncode, stdout, stderr)
        return patch("idscanner.operations.subprocess.run", return_value=result)

    def test_lists_scanners_without_webcams(self):
        output = (
            "device `airscan:e0:Canon MF240' is a eSCL Canon MF240 ip=192.168.1.5\n"
            "device `v4l:/dev/video0' is a Noname Integrated Camera virtual device\n"
            "device `genesys:libusb:001:004' is a Canon LiDE 220 flatbed scanner\n"
        )
        with self.scanimage(output):
            self.assertEqual(
                find_scanners(),
                [
                    ("airscan:e0:Canon MF240", "a eSCL Canon MF240 ip=192.168.1.5"),
                    ("genesys:libusb:001:004", "a Canon LiDE 220 flatbed scanner"),
                ],
            )

    def test_missing_sane_returns_none(self):
        with patch("idscanner.operations.subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(find_scanners())

    def test_failure_raises_scanimage_message(self):
        with self.scanimage(returncode=1, stderr="scanimage: open of device failed\n"):
            with self.assertRaisesRegex(RuntimeError, "open of device failed"):
                find_scanners()

    def test_choose_scanner_prefers_remembered_then_current_then_first(self):
        devices = [("a", "A"), ("b", "B"), ("c", "C")]
        self.assertEqual(choose_scanner(devices, "c", "b"), "c")
        self.assertEqual(choose_scanner(devices, "gone", "b"), "b")
        self.assertEqual(choose_scanner(devices, None, None), "a")
        self.assertIsNone(choose_scanner([], "a"))
