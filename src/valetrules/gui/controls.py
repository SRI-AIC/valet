from tkinter.ttk import Frame
from typing import Optional

from .buttons import ButtonFrame
from .message import MessageFrame


class ControlFrame(Frame):
    """Holds a button frame and a message frame
     (the latter contains a filename widget and a message widget)."""

    def __init__(self, parent, **buttons):
        super().__init__(parent)

        button_frame = ButtonFrame(self, **buttons)
        button_frame.grid(row=0, column=0, sticky="wns")

        self.message_frame = message_frame = MessageFrame(self)
        message_frame.grid(row=1, column=0, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def message(self, text: Optional[str]):
        self.message_frame.message(text)

    def filename(self, text: Optional[str]):
        self.message_frame.filename(text)