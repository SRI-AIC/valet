from tkinter.ttk import Frame

from .buttons import ButtonFrame
from .textpane import TextPane


# Apparently originally used by Culler (or planned to be used),
# but that now uses a TextPane directly, and seems to use the
# button frame from the main Application frame's ControlFrame.
class Reviewer(Frame):

    def __init__(self, parent, data_source, vrmanager):
        super().__init__(parent)
        self.text_pane = TextPane(self, data_source, vrmanager)
        self.button_frame = ButtonFrame(self, Next=self.next)

        self.text_pane.grid(row=0, column=0, sticky="nsew")
        self.button_frame.grid(row=1, column=0, sticky="ew")