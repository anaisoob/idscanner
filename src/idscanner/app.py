"""A small, local-only desktop frontend for id2pdf."""

import queue
import sys
import threading
import tkinter
from importlib.metadata import version
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import id2pdf
from PIL import Image

from . import settings
from .operations import ScanCancelled, choose_scanner, find_scanners, save_pdf_atomic, scan_side
from .sidebar import AutoScrollSidebar
from .system_info import sane_install_help, tk_lacks_xft

ICON = Path(__file__).with_name("icon.png")
HELP = """1. Select your scanner (the list is filled when the app starts; Refresh scanners
looks again), place the front of the card face down on the glass, and close the lid.
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
SEARCHING = "Looking for scanners…"
SECONDARY = {"fg_color": "transparent", "border_width": 1, "text_color": ("gray20", "gray85")}
NO_XFT = (
    "This Python's Tk cannot draw smooth fonts or rounded corners (no Xft). "
    "Install ID Scanner with your system's Python, for example with pipx."
)


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
        self.scanner_controls = []
        self.discovery = None  # (cancel event, thread) while looking for scanners
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
        self.device = ctk.CTkOptionMenu(panel, values=["No scanner selected"], command=self.choose_device)
        self.device.grid(row=3, column=0, padx=24, sticky="ew")
        self.scanner_controls.append(self.device)
        self.refresh_button = self.button(panel, "Refresh scanners", self.refresh, 4, self.scanner_controls)
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
                self.scanner_controls,
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
                **SECONDARY,
            ).grid(row=0, column=column, padx=(8, 0))
        self.preview = ctk.CTkLabel(
            view,
            text="Add the front and back of your card\nto build your document.",
            fg_color=("#dfe5ef", "#202a39"),
            corner_radius=16,
        )
        self.preview.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=18)
        self.preview.bind("<Configure>", lambda event: self.render())
        self.status = ctk.CTkLabel(view, text="Ready", anchor="w", justify="left", wraplength=520)
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")
        # Wrap at the label's real width. CTkLabel.bind would go to its inner widgets, so bind the frame itself;
        # wraplength is given unscaled, like every CustomTkinter size.
        tkinter.Misc.bind(
            self.status,
            "<Configure>",
            lambda event: self.status.configure(
                wraplength=event.width / ctk.ScalingTracker.get_widget_scaling(self.status)
            ),
        )
        self.progress = ctk.CTkProgressBar(view, mode="indeterminate", height=4)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        # Indeterminate mode always draws its segment, so it gets the track colour while idle.
        self.progress_color = self.progress.cget("progress_color")
        self.progress.configure(progress_color=self.progress.cget("fg_color"))
        self.lacks_xft = tk_lacks_xft(self.tk)
        if self.lacks_xft:
            print(f"ID Scanner: {NO_XFT}", file=sys.stderr)
        self.update_controls()
        self.after(100, self.poll)
        self.after(0, lambda: self.refresh(startup=True))

    def button(self, parent, text, command, row, controls=None):
        button = ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=8)
        button.grid(row=row, column=0, padx=24, pady=(8, 0), sticky="ew")
        (self.controls if controls is None else controls).append(button)
        return button

    def set_windows_icon(self, window):
        # CustomTkinter replaces the title bar icon on Windows unless iconbitmap is called.
        if sys.platform == "win32":
            window.iconbitmap(ICON.with_suffix(".ico"))

    def show_help(self):
        self.dialog("ID Scanner Help", "How to use ID Scanner", HELP)

    def show_about(self):
        image = ctk.CTkImage(Image.open(ICON), size=(96, 96))
        self.dialog("About ID Scanner", f"ID Scanner {version('idscanner')}", ABOUT, image, extra=self.theme_picker)

    def theme_picker(self, window):
        row = ctk.CTkFrame(window, fg_color="transparent")
        row.pack(padx=32, pady=(18, 0), fill="x")
        ctk.CTkLabel(row, text="Theme").pack(side="left")
        picker = ctk.CTkSegmentedButton(row, values=list(settings.THEMES), command=self.set_theme)
        picker.set(settings.theme())
        picker.pack(side="right")

    def set_theme(self, theme):
        ctk.set_appearance_mode(theme.lower())
        settings.save(theme=theme)

    def dialog(self, title, heading, text, image=None, buttons=("Close",), extra=None):
        """A modal dialog; returns the text of the button clicked, or None when dismissed.

        extra(window) can add widgets between the text and the buttons.
        """
        window = ctk.CTkToplevel(self)
        window.title(title)
        window.resizable(False, False)
        window.transient(self)
        self.set_windows_icon(window)
        if image is not None:
            ctk.CTkLabel(window, text="", image=image).pack(padx=32, pady=(28, 0))
        ctk.CTkLabel(window, text=heading, font=("", 20, "bold")).pack(padx=32, pady=(24 if image is None else 12, 0))
        ctk.CTkLabel(window, text=text, justify="left", anchor="w", wraplength=600).pack(
            padx=32, pady=(14, 0), fill="x"
        )
        if extra is not None:
            extra(window)
        result = None

        def choose(label):
            nonlocal result
            result = label
            window.destroy()

        row = ctk.CTkFrame(window, fg_color="transparent")
        row.pack(padx=32, pady=24, anchor="e")
        for column, label in enumerate(buttons):
            # The last button is the default action, the others are secondary.
            style = {} if column == len(buttons) - 1 else SECONDARY
            button = ctk.CTkButton(
                row, text=label, command=lambda label=label: choose(label), height=36, corner_radius=8, **style
            )
            button.grid(row=0, column=column, padx=(8 if column else 0, 0))
        window.bind("<Escape>", lambda event: window.destroy())
        window.bind("<Return>", lambda event: choose(buttons[-1]))
        window.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - window.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - window.winfo_reqheight()) // 3
        window.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        window.wait_visibility()
        window.grab_set()
        button.focus_set()
        self.wait_window(window)
        return result

    def update_controls(self):
        for control in self.controls:
            control.configure(state="disabled" if self.busy else "normal")
        # Scanner controls also wait for discovery; the rest of the app does not.
        for control in self.scanner_controls:
            control.configure(state="disabled" if self.busy or self.discovery else "normal")
        self.refresh_button.configure(text=SEARCHING if self.discovery else "Refresh scanners")
        if self.busy or any(side is None for side in self.sides):
            self.save_button.configure(state="disabled")
        self.cancel_button.configure(state="normal" if self.busy and self.scan_cancel is not None else "disabled")
        if self.busy or self.discovery:
            self.progress.configure(progress_color=self.progress_color)
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(progress_color=self.progress.cget("fg_color"))

    def in_background(self, work, finish):
        """Run work() in a thread, then finish(result, error) in the Tk thread."""

        def worker():
            try:
                self.events.put((finish, work(), None))
            except Exception as error:
                self.events.put((finish, None, error))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def run_task(self, message, work, done):
        """Run one operation at a time, with the controls disabled until it finishes."""
        if self.busy:
            return
        self.busy = True
        self.status.configure(text=message)
        self.update_controls()

        def finish(result, error):
            self.busy = False
            self.scan_cancel = None
            self.update_controls()  # before any dialog, so the window behind it is no longer greyed out
            if isinstance(error, ScanCancelled):
                self.status.configure(text="Scanning cancelled.")
            elif error is not None:
                raise error
            else:
                done(result)
                self.update_controls()

        self.in_background(work, finish)

    def poll(self):
        try:
            finish, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            # An exception escaping here would stop polling and leave every later task hanging.
            try:
                finish(result, error)
            except Exception as exception:
                self.status.configure(text="Could not complete the operation. You can try again.")
                self.dialog("ID Scanner", "Could not complete the operation", str(exception))
                self.update_controls()
        self.after(100, self.poll)

    def refresh(self, startup=False):
        """Look for scanners while the rest of the app stays usable.

        At startup, problems are only reported in the status line.
        """
        if self.busy or self.discovery:
            return
        cancel = threading.Event()
        # At startup a broken Tk matters more than the search, which the Refresh button shows anyway.
        if not (startup and self.lacks_xft):
            self.status.configure(text=SEARCHING)

        def report(text):
            # Leave the status alone if an operation started meanwhile has replaced it.
            if self.status.cget("text") == SEARCHING:
                self.status.configure(text=text)

        def finish(devices, error):
            self.discovery = None
            self.update_controls()
            if error is not None:
                if startup:
                    report("Could not look for scanners. Click Refresh scanners to see why.")
                else:
                    report("Could not look for scanners. You can try again.")
                    self.dialog("ID Scanner", "Could not look for scanners", str(error))
                return
            if devices is None:
                self.device_names = {}
                self.device.configure(values=["SANE not installed"])
                self.device.set("SANE not installed")
                report("Scanning requires SANE. Use Choose image… to work with existing images.")
                if not startup:
                    self.dialog(
                        "SANE required for scanning",
                        "SANE required for scanning",
                        "The scanimage command was not found. Install SANE to scan from this application.\n\n"
                        f"{sane_install_help()}\n\n"
                        "Alternatively, use Choose image… to load the front and back from existing images.\n\n"
                        "After installing SANE, click Refresh scanners again.",
                    )
                return
            previous = self.device_names.get(self.device.get())
            self.device_names = {
                f"{index + 1}. {description}": name for index, (name, description) in enumerate(devices)
            }
            labels = {name: label for label, name in self.device_names.items()}
            # The remembered scanner wins over the current selection, which may have been a fallback.
            chosen = choose_scanner(devices, settings.load().get("device"), previous)
            self.device.configure(values=list(self.device_names) or ["No scanner found"])
            self.device.set(labels.get(chosen, "No scanner found"))
            report("Scanner list updated." if devices else "No scanner found. You can choose image files.")

        self.discovery = (cancel, self.in_background(lambda: find_scanners(cancel), finish))
        self.update_controls()

    def choose_device(self, label):
        if label in self.device_names:
            settings.save(device=self.device_names[label])

    def scan_side(self, side):
        if self.busy or self.discovery:
            return
        device = self.device_names.get(self.device.get())
        if not device:
            self.dialog("Choose a scanner", "Choose a scanner", "Refresh the scanner list and choose a scanner first.")
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
        if (
            any(side is not None for side in self.sides)
            and self.dialog(
                "Clear document", "Clear document", "Remove both sides from this document?", buttons=("Cancel", "Clear")
            )
            != "Clear"
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
            self.dialog(
                "Operation in progress",
                "Operation in progress",
                "Please wait for the operation to finish before closing.",
            )
            return
        if (
            any(side is not None for side in self.sides)
            and self.dialog(
                "Close ID Scanner",
                "Close this document?",
                "Make sure you have saved your PDF.",
                buttons=("Cancel", "Close"),
            )
            != "Close"
        ):
            return
        if self.discovery:
            # Stop scanimage instead of leaving it behind, possibly holding a USB scanner.
            cancel, thread = self.discovery
            cancel.set()
            thread.join(timeout=2)
        self.destroy()


def main():
    ctk.set_appearance_mode(settings.theme().lower())
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
