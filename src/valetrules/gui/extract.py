from tkinter import Toplevel, StringVar, Label
from tkinter.ttk import Treeview
from .spooler import Spooler
from .buttons import ButtonFrame


class ExtractionView(Toplevel):

    def __init__(self, parent, patname, vrm):
        self.parent = parent
        self.patname = patname
        self.vrm = vrm
        self.spooler = Spooler(vrm)
        self.columns = self.get_frame_columns()
        self.frames = {}
        super().__init__(parent)
        buttons = dict(
            Go=self.go_command,
            Done=self.done_command
        )
        self.message_text = StringVar(self, "Culling: %s" % patname)
        self.message_widget = Label(self, textvariable=self.message_text)
        self.result_widget = Treeview(self, columns=self.columns, height=10, selectmode="none")
        self.buttons_frame = ButtonFrame(self, **buttons)

    def get_frame_columns(self):
        extractor, type_ = self.vrm.lookup_extractor(self.patname)
        if type_ != 'frame':
            raise ValueError("Type of %s is not frame" % self.patname)
        self.columns = extractor.field_names()

    def go_command(self):
        self.stop = False
        frame_extractor, _ = self.vrm.lookup_extractor(self.patname)

        self.frames = {}

        def update():
            for frame in self.frames.values():
                pass
            self.frames = {}

        def report_progress(label, count):
            self.message_text.set("Extracting: %s (%d)" % (self.patname, count))
            update()

        for _, _, matches in self.spooler.scan(self.patname, progress_cb=report_progress):
            if self.stop:
                break
            for item in matches:
                match, _, _ = item
                frame = frame_extractor.extract_from_match(match)
            selections = self.get_selections()
            for item in matches:
                match, _, _ = item
                text = match.matching_text()
                try:
                    self.cull_count[text] += 1
                except KeyError:
                    self.cull_count[text] = 1
                if text not in selections:
                    selections[text] = False
            self.set_selections(selections)
            self.update()

    def done_command(self):
        pass
