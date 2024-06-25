from tkinter import Toplevel, Label, Listbox, MULTIPLE, END, StringVar
from tkinter.ttk import Frame
from .buttons import ButtonFrame
from .spooler import Spooler
from .textpane import TextPane


class Culler(Toplevel):

    def __init__(self, parent, patname, vrm):
        self.parent = parent
        self.patname = patname
        self.vrm = vrm
        self.spooler = Spooler(vrm)
        self.cull_count = {}
        self.culled = {}
        self.stop = False
        buttons = dict(
            Go=self.go_command,
            Stop=self.stop_command,
            Record=self.record_command,
            Review=self.review_command,
            Next=self.next_command,
            Cancel=self.cancel_command,
            OK=self.ok_command,
        )
        super().__init__(parent)
        self.message_text = StringVar(self, "Culling: %s" % patname)
        self.message_widget = Label(self, textvariable=self.message_text)
        self.buttons_frame = ButtonFrame(self, **buttons)
        self.buttons_frame.disable('Review')
        self.buttons_frame.disable('Next')

        frame = Frame(self)
        self.reviewer = TextPane(frame, self.spooler.get_source(), self.vrm)
        self.reviewer.parent = self
        self.list_widget = Listbox(frame, selectmode=MULTIPLE)
        self.list_widget.bind('<<ListboxSelect>>', self.selection_command)
        self.list_widget.grid(row=0, column=0, sticky="nsew")
        self.reviewer.grid(row=0, column=1, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        self.message_widget.grid(row=0, column=0, sticky="ew")
        frame.grid(row=1, column=0, sticky="nsew")
        self.buttons_frame.grid(row=2, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def go_command(self):
        self.stop = False

        def report_progress(label, count):
            self.message_text.set("Culling: %s (%d)" % (self.patname, count))

        for _, _, matches in self.spooler.scan(self.patname, progress_cb=report_progress):
            if self.stop:
                break
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

    def stop_command(self):
        self.stop = True

    def record_command(self):
        selections = self.get_selections()
        for word, selected in selections.items():
            self.culled[word] = selected
        self.buttons_frame.disable('Next')
        self.buttons_frame.disable('Review')

    def review_command(self):
        # This replaces the one that references parent.control_frame in its
        # filename_cb, since we're the parent and have no control_frame.
        self.reviewer.set_spooler(Spooler(self.vrm))
        selections = self.get_selections()
        selected_words = [w for w in selections if selections[w]]
        self.vrm.forget('_FOOTEST', '_FOO')
        self.vrm.parse_block("_FOOTEST: { %s }\n_FOO ~ inter(%s, _FOOTEST)" % (' '.join(selected_words), self.patname))
        self.buttons_frame.enable('Next')
        self.next_command()

    def next_command(self):
        _, matches = self.reviewer.scan('_FOO')
        self.reviewer.display_matches(matches, refresh=True)

    def cancel_command(self):
        self.parent.done_culling(self)

    def ok_command(self):
        selections = self.get_selections(include_culled = True)
        keepers = [item for item in selections.keys() if selections[item]]
        self.parent.done_culling(self, keepers)

    def selection_command(self, evt):
        self.buttons_frame.enable('Review')
        self.buttons_frame.disable('Next')

    def get_selections(self, include_culled=False):
        selections = {}
        count = self.list_widget.size()
        items = self.list_widget.get(0, count-1)
        for i, item in enumerate(items):
            selections[item] = self.list_widget.selection_includes(i)
        if include_culled:
            for word, keeper in self.culled.items():
                selections[word] = keeper
        return selections

    def set_selections(self, selections):
        count = self.list_widget.size()
        if count > 0:
            self.list_widget.delete(0, count-1)
        wordlist = sorted(self.cull_count.keys(), key=lambda x: self.cull_count[x], reverse=True)
        wordlist = [w for w in wordlist if w not in self.culled]
        self.list_widget.insert(END, *wordlist)
        for i, word in enumerate(wordlist):
            if selections[word]:
                self.list_widget.selection_set(i)

    def message(self, msg):
        self.message_text.set("Culling %s - %s" % (self.patname, msg))