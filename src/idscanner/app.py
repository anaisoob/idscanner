"""A small, local-only desktop frontend for id2pdf."""

import queue
import signal
import sys
import threading
import tkinter
from importlib.metadata import version
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import id2pdf
from PIL import Image

from . import i18n, settings
from .i18n import N_, _
from .operations import (
    IMAGE_FORMATS,
    ScanCancelled,
    card_from_file,
    choose_scanner,
    find_scanners,
    save_document_atomic,
    scan_side,
)
from .sidebar import AutoScrollSidebar
from .system_info import sane_install_help, tk_lacks_xft

ICON = Path(__file__).with_name("icon.png")
HELP = N_("""1. Select your scanner (the list is filled when the app starts; Refresh scanners
looks again), place the front of the card face down on the glass, and close the lid.
2. Click Scan front, turn the card over, then click Scan back.
3. Check the preview and choose Save…: a PDF, or a JPEG or PNG image for forms that
only accept images.

Either side can be scanned again or replaced independently.
Use Choose image… for phone photos or scans already on disk; a card photographed at
a slant is straightened. If no card is found in the image, the whole image is added
and the side is marked "card not found": take the photo on a plain background, or
crop it before importing.

Print the PDF at 100% / actual size to keep the real card dimensions; an image may be
scaled to fit the page when printed.
No scanner listed? Install SANE and check that it appears in scanimage -L.""")
ABOUT = N_("""Scan both sides of an ID card and save them on one A4 page as a PDF
or an image, at the card's real size.

All image processing happens locally on your computer.

Built with id2pdf and CustomTkinter.
License: GPL-3.0-or-later""")
SEARCHING = N_("Looking for scanners…")
BLANK = Image.new("RGBA", (1, 1), (0, 0, 0, 0))  # shown instead of no image, see render()
WARNING = ("#b45309", "#fbbf24")
SECONDARY = {"fg_color": "transparent", "border_width": 1, "text_color": ("gray20", "gray85")}
NO_XFT = N_(
    "This Python's Tk cannot draw smooth fonts or rounded corners (no Xft). "
    "Install ID Scanner with your system's Python, for example with pipx."
)
SIDE_STATES = {
    (0, "empty"): N_("FRONT · Not added"),
    (1, "empty"): N_("BACK · Not added"),
    (0, "found"): N_("FRONT · Added"),
    (1, "found"): N_("BACK · Added"),
    (0, "not found"): N_("FRONT · Added, card not found"),
    (1, "not found"): N_("BACK · Added, card not found"),
}
THEME_NAMES = {"System": N_("System"), "Light": N_("Light"), "Dark": N_("Dark")}


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
        self.closable = False  # whether the running operation may be abandoned by closing the app
        self.controls = []
        self.scanner_controls = []
        self.discovery = None  # (cancel event, thread) while looking for scanners
        self.preview_image = None
        self.cached_page = None
        self.scan_cancel = None
        self.closing = False
        self.device_names = {}
        id2pdf.set_language(i18n.current())
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
        ctk.CTkLabel(panel, text=_("Two sides. One A4 PDF."), text_color="gray").grid(
            row=1, column=0, padx=24, sticky="w"
        )
        ctk.CTkLabel(panel, text=_("SCANNER"), font=("", 12, "bold")).grid(
            row=2, column=0, padx=24, pady=(30, 8), sticky="w"
        )
        self.device = ctk.CTkOptionMenu(panel, values=[_("No scanner selected")], command=self.choose_device)
        self.device.grid(row=3, column=0, padx=24, sticky="ew")
        self.scanner_controls.append(self.device)
        self.refresh_button = self.button(panel, _("Refresh scanners"), self.refresh, 4, self.scanner_controls)
        self.side_labels = []
        for side, row in ((0, 6), (1, 9)):
            label = ctk.CTkLabel(
                panel,
                text=_(SIDE_STATES[side, "empty"]),
                anchor="w",
            )
            label.grid(row=row, column=0, padx=24, pady=(16, 0), sticky="ew")
            self.side_labels.append(label)
            self.label_color = label.cget("text_color")
            self.button(
                panel,
                _("Scan front") if side == 0 else _("Scan back"),
                lambda s=side: self.scan_side(s),
                row + 1,
                self.scanner_controls,
            )
            self.button(panel, _("Choose image…"), lambda s=side: self.load_side(s), row + 2)
        ctk.CTkLabel(panel, text=_("DOCUMENT"), font=("", 12, "bold"), anchor="w").grid(
            row=12, column=0, padx=24, pady=(24, 0), sticky="ew"
        )
        self.save_button = self.button(panel, _("Save…"), self.save, 13)
        self.button(panel, _("Clear document"), self.clear, 14)
        self.cancel_button = ctk.CTkButton(
            panel, text=_("Cancel scan"), command=self.cancel_scan, state="disabled", height=36, corner_radius=8
        )
        self.cancel_button.grid(row=15, column=0, padx=24, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(panel, text=_("Processed locally on your computer."), text_color="gray").grid(
            row=16, column=0, padx=24, pady=12, sticky="w"
        )

        view = ctk.CTkFrame(self, fg_color="transparent")
        view.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(view, text=_("Document preview"), font=("", 20, "bold")).grid(row=0, column=0, sticky="w")
        links = ctk.CTkFrame(view, fg_color="transparent")
        links.grid(row=0, column=1, sticky="e")
        for column, (text, command) in enumerate(((_("Help"), self.show_help), (_("About"), self.show_about))):
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
            text=_("Add the front and back of your card\nto build your document."),
            fg_color=("#dfe5ef", "#202a39"),
            corner_radius=16,
        )
        self.preview.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=18)
        self.preview.bind("<Configure>", lambda event: self.render())
        self.status = ctk.CTkLabel(view, text=_("Ready"), anchor="w", justify="left", wraplength=520)
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
            print(f"ID Scanner: {_(NO_XFT)}", file=sys.stderr)
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
        self.dialog(_("ID Scanner Help"), _("How to use ID Scanner"), _(HELP))

    def show_about(self):
        image = ctk.CTkImage(Image.open(ICON), size=(96, 96))
        self.dialog(
            _("About ID Scanner"), f"ID Scanner {version('idscanner')}", _(ABOUT), image, extra=self.preferences
        )

    def preferences(self, window):
        themes = {_(THEME_NAMES[theme]): theme for theme in settings.THEMES}
        row = ctk.CTkFrame(window, fg_color="transparent")
        row.pack(padx=32, pady=(18, 0), fill="x")
        ctk.CTkLabel(row, text=_("Theme")).pack(side="left")
        picker = ctk.CTkSegmentedButton(row, values=list(themes), command=lambda name: self.set_theme(themes[name]))
        picker.set(_(THEME_NAMES[settings.theme()]))
        picker.pack(side="right")

        system = _("System language")
        languages = {system: None} | {name: code for code, name in i18n.LANGUAGES.items()}
        row = ctk.CTkFrame(window, fg_color="transparent")
        row.pack(padx=32, pady=(12, 0), fill="x")
        ctk.CTkLabel(row, text=_("Language")).pack(side="left")

        def choose(name):
            settings.save(language=languages[name])
            language = languages[name] or i18n.system_language()
            if language != i18n.current():
                # The window keeps its language until a restart; say so in the new one.
                translate = i18n.translation(language).gettext
                self.dialog(
                    translate(N_("Restart ID Scanner")),
                    translate(N_("Restart ID Scanner")),
                    translate(N_("The language changes when ID Scanner is started again.")),
                    buttons=(translate(N_("Close")),),
                    parent=window,
                )

        menu = ctk.CTkOptionMenu(row, values=list(languages), command=choose)
        menu.set(i18n.LANGUAGES.get(settings.language(), system))
        menu.pack(side="right")

    def set_theme(self, theme):
        ctk.set_appearance_mode(theme.lower())
        settings.save(theme=theme)

    def dialog(self, title, heading, text, image=None, buttons=None, extra=None, parent=None):
        """A modal dialog; returns the text of the button clicked, or None when dismissed.

        extra(window) can add widgets between the text and the buttons. parent is another
        dialog this one opens from; it gets its modal grab back afterwards.
        """
        buttons = buttons or (_("Close"),)
        owner = parent or self
        window = ctk.CTkToplevel(owner)
        window.title(title)
        window.resizable(False, False)
        window.transient(owner)
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
        x = owner.winfo_rootx() + (owner.winfo_width() - window.winfo_reqwidth()) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - window.winfo_reqheight()) // 3
        window.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        window.wait_visibility()
        window.grab_set()
        button.focus_set()
        self.wait_window(window)
        if parent is not None and parent.winfo_exists():
            parent.grab_set()
        return result

    def update_controls(self):
        for control in self.controls:
            control.configure(state="disabled" if self.busy else "normal")
        # Scanner controls also wait for discovery; the rest of the app does not.
        for control in self.scanner_controls:
            control.configure(state="disabled" if self.busy or self.discovery else "normal")
        self.refresh_button.configure(text=_(SEARCHING) if self.discovery else _("Refresh scanners"))
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

    def run_task(self, message, work, done, closable=False):
        """Run one operation at a time, with the controls disabled until it finishes.

        A closable operation changes nothing on disk, so the app may be closed while it runs.
        """
        if self.busy:
            return
        self.busy = True
        self.closable = closable
        self.status.configure(text=message)
        self.update_controls()

        def finish(result, error):
            self.busy = False
            self.closable = False
            self.scan_cancel = None
            self.update_controls()  # before any dialog, so the window behind it is no longer greyed out
            if isinstance(error, ScanCancelled):
                self.status.configure(text=_("Scanning cancelled."))
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
                self.status.configure(text=_("Could not complete the operation. You can try again."))
                self.dialog("ID Scanner", _("Could not complete the operation"), str(exception))
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
            self.status.configure(text=_(SEARCHING))

        def report(text):
            # Leave the status alone if an operation started meanwhile has replaced it.
            if self.status.cget("text") == _(SEARCHING):
                self.status.configure(text=text)

        def finish(devices, error):
            self.discovery = None
            self.update_controls()
            if error is not None:
                if startup:
                    report(_("Could not look for scanners. Click Refresh scanners to see why."))
                else:
                    report(_("Could not look for scanners. You can try again."))
                    self.dialog("ID Scanner", _("Could not look for scanners"), str(error))
                return
            if devices is None:
                self.device_names = {}
                self.device.configure(values=[_("SANE not installed")])
                self.device.set(_("SANE not installed"))
                report(_("Scanning requires SANE. Use Choose image… to work with existing images."))
                if not startup:
                    self.dialog(
                        _("SANE required for scanning"),
                        _("SANE required for scanning"),
                        _("The scanimage command was not found. Install SANE to scan from this application.")
                        + f"\n\n{sane_install_help()}\n\n"
                        + _("Alternatively, use Choose image… to load the front and back from existing images.")
                        + "\n\n"
                        + _("After installing SANE, click Refresh scanners again."),
                    )
                return
            previous = self.device_names.get(self.device.get())
            self.device_names = {
                f"{index + 1}. {description}": name for index, (name, description) in enumerate(devices)
            }
            labels = {name: label for label, name in self.device_names.items()}
            # The remembered scanner wins over the current selection, which may have been a fallback.
            chosen = choose_scanner(devices, settings.load().get("device"), previous)
            self.device.configure(values=list(self.device_names) or [_("No scanner found")])
            self.device.set(labels.get(chosen, _("No scanner found")))
            report(_("Scanner list updated.") if devices else _("No scanner found. You can choose image files."))

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
            self.dialog(
                _("Choose a scanner"), _("Choose a scanner"), _("Refresh the scanner list and choose a scanner first.")
            )
            return

        cancel = threading.Event()
        self.scan_cancel = cancel
        self.run_task(
            _("Scanning and straightening the card…"),
            lambda: scan_side(device, front=side == 0, cancel=cancel),
            lambda image: self.set_side(side, image, found=True),
        )

    def cancel_scan(self):
        if self.scan_cancel is not None:
            self.scan_cancel.set()
            self.cancel_button.configure(state="disabled")
            self.status.configure(text=_("Cancelling scan…"))

    def load_side(self, side):
        filename = filedialog.askopenfilename(
            parent=self,
            title=_("Choose a card image"),
            filetypes=[
                (_("Images"), "*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp"),
                (_("All files"), "*"),
            ],
        )
        if filename:
            self.run_task(
                _("Opening and detecting the card…"),
                lambda: card_from_file(Path(filename)),
                lambda result: self.set_side(side, *result),
                closable=True,
            )

    def set_side(self, side, image, found):
        self.sides[side] = image
        self.cached_page = None
        if found:
            self.side_labels[side].configure(text=_(SIDE_STATES[side, "found"]), text_color=self.label_color)
            self.status.configure(text=_("Side added. Check the preview before saving."))
        else:
            # Without a card the whole image would be shrunk onto the page, background and all.
            self.side_labels[side].configure(text=_(SIDE_STATES[side, "not found"]), text_color=WARNING)
            self.status.configure(
                text=_(
                    "No card found in this image, so the whole image was added. "
                    "Choose a clearer image or crop it to the card."
                )
            )
        self.render()

    def page(self):
        if self.cached_page is None:
            placeholder = Image.new("RGB", (1011, 638), "#edf0f5")
            self.cached_page = id2pdf.id_card_page(*(side if side is not None else placeholder for side in self.sides))
        return self.cached_page

    def render(self):
        if all(side is None for side in self.sides):
            # CustomTkinter's image=None leaves the old picture on the Tk label; once it is
            # garbage collected, Tk fails with 'image "pyimage…" doesn't exist'.
            self.preview_image = ctk.CTkImage(light_image=BLANK, dark_image=BLANK, size=(1, 1))
            self.preview.configure(
                image=self.preview_image,
                text=_("Add the front and back of your card\nto build your document."),
            )
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
        extensions = {_("PDF document"): ".pdf", _("JPEG image"): ".jpg", _("PNG image"): ".png"}
        chosen_type = tkinter.StringVar(self)
        filename = filedialog.asksaveasfilename(
            parent=self,
            title=_("Save A4 page"),
            initialfile=_("id-card"),
            filetypes=[(_("PDF document"), "*.pdf"), (_("JPEG image"), "*.jpg *.jpeg"), (_("PNG image"), "*.png")],
            typevariable=chosen_type,
        )
        if not filename:
            return
        path = Path(filename)
        # The name decides the format; without a known extension, the chosen file type adds one.
        if path.suffix.lower() not in (".pdf", *IMAGE_FORMATS):
            path = path.with_name(path.name + extensions.get(chosen_type.get(), ".pdf"))
            # The file dialog only asked about the name without it.
            if path.exists() and self.dialog(
                _("Replace file"),
                _("Replace file"),
                _("{name} already exists. Replace it?").format(name=path.name),
                buttons=(_("Cancel"), _("Replace")),
            ) != _("Replace"):
                return
        page = self.page()
        self.run_task(
            _("Saving…"),
            lambda: save_document_atomic(page, path),
            lambda result: self.status.configure(text=_("Saved: {path}").format(path=path)),
        )

    def clear(self):
        if any(side is not None for side in self.sides) and self.dialog(
            _("Clear document"),
            _("Clear document"),
            _("Remove both sides from this document?"),
            buttons=(_("Cancel"), _("Clear")),
        ) != _("Clear"):
            return
        self.sides = [None, None]
        self.cached_page = None
        for side, label in enumerate(self.side_labels):
            label.configure(text=_(SIDE_STATES[side, "empty"]), text_color=self.label_color)
        self.render()
        self.status.configure(text=_("Ready"))
        self.update_controls()

    def close(self):
        # The close button and Ctrl+C can both ask; one question at a time is enough.
        if self.closing:
            return
        self.closing = True
        try:
            self.ask_and_close()
        finally:
            self.closing = False

    def ask_and_close(self):
        if self.busy and not self.closable:
            self.dialog(
                _("Operation in progress"),
                _("Operation in progress"),
                _("Please wait for the operation to finish before closing."),
            )
            return
        if any(side is not None for side in self.sides) and self.dialog(
            _("Close ID Scanner"),
            _("Close this document?"),
            _("Make sure you have saved your document."),
            buttons=(_("Cancel"), _("Close")),
        ) != _("Close"):
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
    app = App()
    # Tk would swallow KeyboardInterrupt in a callback and keep running. The handler runs at the
    # next Python callback (poll() comes every 100 ms), so close from the event loop instead.
    signal.signal(signal.SIGINT, lambda signum, frame: app.after_idle(app.close))
    app.mainloop()


if __name__ == "__main__":
    main()
