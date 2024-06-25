import re
from threading import Timer
from tkinter import Text, Scrollbar
from tkinter.ttk import Frame
from typing import Tuple

from .state import StateStack


class Pane(Frame):
    """
    Base class for "pane" frames used for patterns and text.
    Provides text and scroll widgets, a state stack,
    and various operations.
    """

    def __init__(self, parent, font='Courier', font_size=16, text_height=25, text_width=100, **kwargs):
        super().__init__(parent)
        self.parent = parent
        self.line_offsets = [0]
        self.state_stack = StateStack(self)
        self.scroll_timer = None
        self.programmatic_scroll = True

        def quiescent():
            self.scroll_timer = None
            offset, _ = text_widget.yview()
            # print("Stopped at %s" % offset)
            self.programmatic_scroll = False

        def scrolling_text(*args):
            # print("scrolling_text", *args)
            if self.scroll_timer is None:
                if not self.programmatic_scroll:
                    self.state_stack.push()
            else:
                self.scroll_timer.cancel()
            self.scroll_timer = Timer(1.0, quiescent)
            self.scroll_timer.start()
            scroll_widget.set(*args)

        scroll_widget = Scrollbar(self, orient="vertical")
        scroll_widget.grid(row=0, column=1, sticky="ns")

        text_widget = self.text_widget = Text(self, width=text_width, height=text_height,
                                              yscrollcommand=scrolling_text,
                                              bd=2, relief="sunken", font=(font, '%s' % font_size),
                                              **kwargs)
        text_widget.grid(row=0, column=0, sticky="nsew")
        scroll_widget['command'] = text_widget.yview

        # Add a test tag to get the default background
        text_widget.tag_add("test tag", '1.0', '1.1')
        self.normal_background = text_widget.tag_cget('test tag', 'background')
        text_widget.tag_delete('test tag')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=1)

        self.text_widget.bind('<Command-b>', self.back_command)

    def get_current_name(self):
        return self.parent.get_current_name()

    def set_current_name(self, name) -> None:
        self.parent.set_current_name(name)

    def restore_name(self, name) -> None:
        self.set_current_name(name)

    def get_text(self) -> str:
        return self.text_widget.get('1.0', 'end')

    def back_command(self, event=None) -> None:
        """Restore the pane to its previous state."""
        self.state_stack.pop()

    def region_offsets(self, region) -> Tuple[str, str]:
        """Return the tkinter text widget L.C style start and end indices of the region."""
        return self.offset_to_index(region.start_offset), self.offset_to_index(region.end_offset)

    def insert(self, text: str) -> None:
        state = self.text_widget.cget('state')
        self.text_widget.configure(state='normal')
        self.text_widget.delete('1.0', 'end')
        self.text_widget.insert('1.0', text)
        if state != 'normal':
            self.text_widget.configure(state=state)
        self.record_offsets()

    def record_offsets(self) -> None:
        text = self.text_widget.get('1.0', 'end')
        self.line_offsets = [0]
        for m in re.finditer('\n', text):
            self.line_offsets.append(m.end())

    def offset_to_index(self, offs: int) -> str:
        """
        Return the tkinter text widget L.C style index value corresponding to
        an offset (char index), given an offsets sequence holding the char
        indices of the first character of each line.
        """
        offsets = self.line_offsets
        last_line = True
        i = None
        for i, loffs in enumerate(offsets):
            if loffs > offs:
                last_line = False
                break
        if last_line:
            return "%d.%d" % (len(offsets), offs - offsets[-1])
        else:
            return "%d.%d" % (i, offs - offsets[i-1])

    def index_to_offset(self, index: str) -> int:
        """
        Convert a tkinter text widget L.C style index value (or allowed
        special value such as 'insert' or 'current') into the text widget
        contents, into the corresponding char index (counting from the
        start of the text).
        """
        index = self.text_widget.index(index)
        li, loffs = index.split('.')
        li, loffs = int(li), int(loffs)
        return self.line_offsets[li-1] + loffs
