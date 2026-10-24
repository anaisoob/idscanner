"""A small, local-only desktop frontend for id2pdf."""

import queue
import re
import subprocess
import sys
import threading
import tkinter
from importlib.metadata import version
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import id2pdf
from PIL import Image

from .operations import ScanCancelled, save_pdf_atomic, scan_side
from .sidebar import AutoScrollSidebar
from .system_info import sane_install_help

ICON = Path(__file__).with_name("icon.png")
HELP = """1. Click Refresh scanners and select a scanner, place the front of the card face down
on the glass, and close the lid.
2. Click Scan front, turn the card over, then click Scan back.
3. Check the preview and choose Save PDF…

Either side can be scanned again or replaced independently.
Use Choose image… for photos or scans already on disk. If the whole image appears
instead of a cropped card, choose a clearer image or crop it before importing.

Print the PDF at 100% / actual size to keep the real card dimensions.
No scanner listed? Install SANE and check that it appears in scanimage -L."""
ABOUT = """Scan both sides of an ID card and save them on one A4 page as a PDF
at the card's real size.

All image processing happens locally on your computer.

Built with id2pdf and CustomTkinter.
License: GPL-3.0-or-later"""


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ID Scanner")
        self.geometry("1060x780")
        self.minsize(900, 480)
        self.configure(fg_color=("#edf1f7", "#141a24"))
        self.sides = [None, None]
        self.events = queue.Queue()
        self.busy = False
        self.controls = []
        self.preview_image = None
        self.cached_page = None
        self.scan_cancel = None
        self.device_names = {}
        id2pdf.set_language("en")
        self.icon = tkinter.PhotoImage(file=ICON)
        self.iconphoto(True, self.icon)
        self.set_windows_icon(self)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<F1>", lambda event: self.show_help())

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=330, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(0, weight=1)
        panel = AutoScrollSidebar(sidebar, corner_radius=0)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="ID Scanner", font=("", 28, "bold")).grid(
            row=0, column=0, padx=24, pady=(30, 4), sticky="w"
        )
        ctk.CTkLabel(panel, text="Two sides. One A4 PDF.", text_color="gray").grid(row=1, column=0, padx=24, sticky="w")
        ctk.CTkLabel(panel, text="SCANNER", font=("", 12, "bold")).grid(
            row=2, column=0, padx=24, pady=(30, 8), sticky="w"
        )
        self.device = ctk.CTkOptionMenu(panel, values=["No scanner selected"])
        self.device.grid(row=3, column=0, padx=24, sticky="ew")
        self.controls.append(self.device)
        self.button(panel, "Refresh scanners", self.refresh, 4)
        self.side_labels = []
        for side, row in ((0, 6), (1, 9)):
            label = ctk.CTkLabel(
                panel,
                text=f"{'FRONT' if side == 0 else 'BACK'} · Not added",
                anchor="w",
            )
            label.grid(row=row, column=0, padx=24, pady=(16, 0), sticky="ew")
            self.side_labels.append(label)
            self.button(
                panel,
                "Scan " + ("front" if side == 0 else "back"),
                lambda s=side: self.scan_side(s),
                row + 1,
            )
            self.button(panel, "Choose image…", lambda s=side: self.load_side(s), row + 2)
        ctk.CTkLabel(panel, text="DOCUMENT", font=("", 12, "bold"), anchor="w").grid(
            row=12, column=0, padx=24, pady=(24, 0), sticky="ew"
        )
        self.save_button = self.button(panel, "Save PDF…", self.save, 13)
        self.button(panel, "Clear document", self.clear, 14)
        self.cancel_button = ctk.CTkButton(
            panel, text="Cancel scan", command=self.cancel_scan, state="disabled", height=36, corner_radius=8
        )
        self.cancel_button.grid(row=15, column=0, padx=24, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(panel, text="Processed locally on your computer.", text_color="gray").grid(
            row=16, column=0, padx=24, pady=12, sticky="w"
        )

        view = ctk.CTkFrame(self, fg_color="transparent")
        view.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(view, text="Document preview", font=("", 20, "bold")).grid(row=0, column=0, sticky="w")
        links = ctk.CTkFrame(view, fg_color="transparent")
        links.grid(row=0, column=1, sticky="e")
        for column, (text, command) in enumerate((("Help", self.show_help), ("About", self.show_about))):
            ctk.CTkButton(
                links,
                text=text,
                command=command,
                width=72,
                height=30,
                corner_radius=8,
                fg_color="transparent",
                border_width=1,
                text_color=("gray20", "gray85"),
            ).grid(row=0, column=column, padx=(8, 0))
        self.preview = ctk.CTkLabel(
            view,
            text="Add the front and back of your card\nto build your document.",
            fg_color=("#dfe5ef", "#202a39"),
            corner_radius=16,
        )
        self.preview.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=18)
        self.preview.bind("<Configure>", lambda event: self.render())
        self.status = ctk.CTkLabel(view, text="Ready", anchor="w", wraplength=520)
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.progress = ctk.CTkProgressBar(view, mode="indeterminate", height=4)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.progress.set(0)
        self.update_controls()
        self.after(100, self.poll)

    def button(self, parent, text, command, row):
        button = ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=8)
        button.grid(row=row, column=0, padx=24, pady=(8, 0), sticky="ew")
        self.controls.append(button)
        return button

    def set_windows_icon(self, window):
        # CustomTkinter replaces the title bar icon on Windows unless iconbitmap is called.
        if sys.platform == "win32":
            window.iconbitmap(ICON.with_suffix(".ico"))

    def show_help(self):
        self.dialog("ID Scanner Help", "How to use ID Scanner", HELP)

    def show_about(self):
        image = ctk.CTkImage(Image.open(ICON), size=(96, 96))
        self.dialog("About ID Scanner", f"ID Scanner {version('idscanner')}", ABOUT, image)

    def dialog(self, title, heading, text, image=None):
        window = ctk.CTkToplevel(self)
        window.title(title)
        window.resizable(False, False)
        window.transient(self)
        self.set_windows_icon(window)
        if image is not None:
            ctk.CTkLabel(window, text="", image=image).pack(padx=32, pady=(28, 0))
        ctk.CTkLabel(window, text=heading, font=("", 20, "bold")).pack(padx=32, pady=(24 if image is None else 12, 0))
        ctk.CTkLabel(window, text=text, justify="left", anchor="w").pack(padx=32, pady=(14, 0), fill="x")
        close = ctk.CTkButton(window, text="Close", command=window.destroy, height=36, corner_radius=8)
        close.pack(padx=32, pady=24, anchor="e")
        window.bind("<Escape>", lambda event: window.destroy())
        window.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - window.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - window.winfo_reqheight()) // 3
        window.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        window.wait_visibility()
        window.grab_set()
        close.focus_set()

    def update_controls(self):
        for control in self.controls:
            control.configure(state="disabled" if self.busy else "normal")
        if self.busy or any(side is None for side in self.sides):
            self.save_button.configure(state="disabled")
        self.cancel_button.configure(state="normal" if self.busy and self.scan_cancel is not None else "disabled")

    def run_task(self, message, work, done):
        if self.busy:
            return
        self.busy = True
        self.status.configure(text=message)
        self.update_controls()
        self.progress.start()

        def worker():
            try:
                self.events.put((done, work(), None))
            except Exception as error:
                self.events.put((done, None, error))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            done, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.scan_cancel = None
            self.progress.stop()
            self.progress.set(0)
            if error is None:
                # An exception escaping here would stop polling and leave every later task hanging.
                try:
                    done(result)
                except Exception as exception:
                    error = exception
            if isinstance(error, ScanCancelled):
                self.status.configure(text="Scanning cancelled.")
            elif error is not None:
                self.status.configure(text="Could not complete the operation. You can try again.")
                messagebox.showerror("ID Scanner", str(error), parent=self)
            self.update_controls()
        self.after(100, self.poll)

    def refresh(self):
        def discover():
            try:
                result = subprocess.run(["scanimage", "-L"], capture_output=True, text=True, timeout=30)
            except FileNotFoundError:
                return None
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Scanner discovery failed.")
            return [
                (name, description)
                for name, description in re.findall(r"device `([^']+)' is (.+)", result.stdout)
                if not name.startswith("v4l")
            ]

        def done(devices):
            if devices is None:
                self.device_names = {}
                self.device.configure(values=["SANE not installed"])
                self.device.set("SANE not installed")
                self.status.configure(text="Scanning requires SANE. Use Choose image… to work with existing images.")
                messagebox.showinfo(
                    "SANE required for scanning",
                    "The scanimage command was not found. Install SANE to scan from this application.\n\n"
                    f"{sane_install_help()}\n\n"
                    "Alternatively, use Choose image… to load the front and back from existing images.\n\n"
                    "After installing SANE, click Refresh scanners again.",
                    parent=self,
                )
                return
            previous = self.device.get()
            self.device_names = {
                f"{index + 1}. {description}": name for index, (name, description) in enumerate(devices)
            }
            values = list(self.device_names) or ["No scanner found"]
            self.device.configure(values=values)
            self.device.set(previous if previous in values else values[0])
            self.status.configure(
                text="Scanner list updated." if devices else "No scanner found. You can choose image files."
            )

        self.run_task("Looking for scanners…", discover, done)

    def scan_side(self, side):
        if self.busy:
            return
        device = self.device_names.get(self.device.get())
        if not device:
            messagebox.showinfo(
                "Choose a scanner",
                "Refresh the scanner list and choose a scanner first.",
                parent=self,
            )
            return

        cancel = threading.Event()
        self.scan_cancel = cancel
        self.run_task(
            "Scanning and straightening the card…",
            lambda: scan_side(device, front=side == 0, cancel=cancel),
            lambda image: self.set_side(side, image),
        )

    def cancel_scan(self):
        if self.scan_cancel is not None:
            self.scan_cancel.set()
            self.cancel_button.configure(state="disabled")
            self.status.configure(text="Cancelling scan…")

    def load_side(self, side):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Choose a card image",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp"),
                ("All files", "*"),
            ],
        )
        if filename:
            self.run_task(
                "Opening and detecting the card…",
                lambda: id2pdf.card_from_image(id2pdf.open_image(Path(filename))),
                lambda image: self.set_side(side, image),
            )

    def set_side(self, side, image):
        self.sides[side] = image
        self.cached_page = None
        self.side_labels[side].configure(text=f"{'FRONT' if side == 0 else 'BACK'} · Added")
        self.status.configure(text="Side added. Check the preview before saving.")
        self.render()

    def page(self):
        if self.cached_page is None:
            placeholder = Image.new("RGB", (1011, 638), "#edf0f5")
            self.cached_page = id2pdf.id_card_page(*(side if side is not None else placeholder for side in self.sides))
        return self.cached_page

    def render(self):
        if all(side is None for side in self.sides):
            self.preview.configure(
                image=None,
                text="Add the front and back of your card\nto build your document.",
            )
            self.preview_image = None
            return
        page = self.page().copy()
        width = max(100, self.preview.winfo_width() - 32)
        height = max(100, self.preview.winfo_height() - 32)
        scale = min(width / page.width, height / page.height)
        size = (max(1, int(page.width * scale)), max(1, int(page.height * scale)))
        page.thumbnail((size[0] * 2, size[1] * 2))
        self.preview_image = ctk.CTkImage(light_image=page, dark_image=page, size=size)
        self.preview.configure(text="", image=self.preview_image)

    def save(self):
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Save A4 PDF",
            defaultextension=".pdf",
            initialfile="id-card.pdf",
            filetypes=[("PDF document", "*.pdf")],
        )
        if filename:
            page = self.page()
            self.run_task(
                "Saving PDF…",
                lambda: save_pdf_atomic(page, Path(filename)),
                lambda _: self.status.configure(text=f"Saved: {filename}"),
            )

    def clear(self):
        if any(side is not None for side in self.sides) and not messagebox.askyesno(
            "Clear document", "Remove both sides from this document?", parent=self
        ):
            return
        self.sides = [None, None]
        self.cached_page = None
        for side, label in enumerate(self.side_labels):
            label.configure(text=f"{'FRONT' if side == 0 else 'BACK'} · Not added")
        self.render()
        self.status.configure(text="Ready")
        self.update_controls()

    def close(self):
        if self.busy:
            messagebox.showinfo(
                "Operation in progress",
                "Please wait for the operation to finish before closing.",
                parent=self,
            )
            return
        if any(side is not None for side in self.sides) and not messagebox.askyesno(
            "Close ID Scanner",
            "Close this document? Make sure you have saved your PDF.",
            parent=self,
        ):
            return
        self.destroy()


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
