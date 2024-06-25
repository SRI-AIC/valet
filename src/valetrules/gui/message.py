from tkinter import Text
from tkinter.ttk import Frame
from typing import Optional


class MessageFrame(Frame):
    """Holds a filename widget and a message widget."""

    def __init__(self, parent: Frame):
        super().__init__(parent)
        widget_appearance = dict(
            width=120, relief="sunken", padx=5, pady=5, background="gray88", font=("Helvetica", "16")
        )
        filename_widget = self.filename_widget = Text(self, height=1, **widget_appearance)
        filename_widget.configure(state="disabled")
        filename_widget.bind("<1>", lambda event: filename_widget.focus_set())
        filename_widget.grid(row=0, column=0, sticky="we")

        message_widget = self.message_widget = Text(self, height=3, **widget_appearance)
        message_widget.configure(state="disabled")
        message_widget.bind("<1>", lambda event: message_widget.focus_set())
        message_widget.grid(row=1, column=0, sticky="nswe")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.filename_widget = filename_widget
        self.message_widget = message_widget

    def _announce(self, widget_name: str, text: Optional[str]):
        widget = getattr(self, widget_name)
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        if text is not None:
            widget.insert('1.0', text)
        widget.configure(state='disabled')  # read only

    def message(self, text: Optional[str]) -> None:
        self._announce('message_widget', text)

    def filename(self, text: Optional[str]) -> None:
        self._announce('filename_widget', text)
