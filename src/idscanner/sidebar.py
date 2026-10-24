"""A sidebar that only shows its scrollbar when content overflows."""

import customtkinter as ctk


class AutoScrollSidebar(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        self._scrollbar_visible = False
        super().__init__(master, **kwargs)
        self._scrollbar.grid_remove()
        self._parent_canvas.configure(yscrollcommand=self._update_scrollbar)

    def _create_grid(self):
        # CustomTkinter rebuilds this grid on scaling/configuration changes.
        super()._create_grid()
        if not self._scrollbar_visible:
            self._scrollbar.grid_remove()

    def _fit_frame_dimensions_to_canvas(self, event):
        # CustomTkinter draws rounded shapes at even widths only; an odd frame width (e.g. once
        # the scrollbar takes its 17 px) leaves a 1 px notch at the right edge of every button.
        width = self._parent_canvas.winfo_width()
        self._parent_canvas.itemconfigure(self._create_window_id, width=width - width % 2)

    def _update_scrollbar(self, first, last):
        self._scrollbar.set(first, last)
        visible = float(last) - float(first) < 0.999999
        if visible != self._scrollbar_visible:
            self._scrollbar_visible = visible
            if visible:
                self._scrollbar.grid()
            else:
                self._scrollbar.grid_remove()
                self._parent_canvas.yview_moveto(0)

    def _mouse_wheel_all(self, event):
        if self._scrollbar_visible:
            super()._mouse_wheel_all(event)
