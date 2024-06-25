"""
Provides State and StateStack classes used by Panes to track their scroll
position and other state.
"""


class State:
    """
    Stores the scroll state (position) of a Pane,
    along with some name info TODO.
    """

    def __init__(self, pane, track_name=False):
        self.pane = pane
        self.track_name = track_name
        position, _ = pane.text_widget.yview()
        self.position = position
        self.name = pane.get_current_name()

    def restore(self) -> None:
        """
        Restore the pane to the state held by this State.
        """
        position, _ = self.pane.text_widget.yview()
        if position != self.position:
            self.pane.programmatic_scroll = True
            self.pane.text_widget.yview_moveto(self.position)
        if not self.track_name:
            return
        name = self.pane.get_current_name()
        if name != self.name:
            self.pane.restore_name(self.name)


class StateStack:

    def __init__(self, pane):
        self.pane = pane
        self.track_name = False
        self.stack = []

    def set_track_name(self, track_name=True) -> None:
        self.track_name = track_name

    def push(self) -> None:
        """Push the present state of the pane onto the stack."""
        self.stack.append(State(self.pane, self.track_name))

    def pop(self) -> None:
        """Pop the last state and restore the pane to that state."""
        if len(self.stack) == 0:
            return
        state = self.stack.pop()
        state.restore()
