from tkinter import Button, NORMAL, DISABLED
from tkinter.ttk import Frame


class ButtonFrame(Frame):
    """Fairly generic frame to hold buttons."""

    def __init__(self, parent, **buttons):
        super().__init__(parent, relief='groove', borderwidth=2)
        self.parent = parent
        self.column = 0
        self.buttons = {}
        for label, cmd in buttons.items():
            self.add_button(label, cmd)
        for col in range(self.column):
            self.parent.grid_columnconfigure(col, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)

    def add_button(self, label, command):
        button = Button(self, text=label, command=command)
        button.grid(column=self.column, row=0, padx=3, pady=1, sticky="w")
        self.column += 1
        self.buttons[label] = button

    def enable(self, name):
        self.buttons[name].configure(state=NORMAL)

    def disable(self, name):
        self.buttons[name].configure(state=DISABLED)
