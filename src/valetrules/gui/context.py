from tkinter import Toplevel, IntVar, Checkbutton, StringVar, Label, Entry
from tkinter.ttk import Frame
import random
from .spooler import Spooler
from .buttons import ButtonFrame


class ContextView(Toplevel):

    def __init__(self, parent, patname, vrm, feats):
        super().__init__(parent)
        self.parent = parent
        self.patname = patname
        self.vrm = vrm
        self.features = feats
        self.spooler = Spooler(vrm)
        self.stop = False
        self.selected_features = None
        self.max_positive = StringVar()
        self.max_positive.set("100")
        self.negative_proportion = StringVar()
        self.negative_proportion.set("1.0")
        self.populate()

    def populate(self):
        fwidget = self.populate_features()
        pwidget = self.populate_parameters()
        bframe = self.populate_buttons()
        fwidget.grid(row=0, column=0)
        pwidget.grid(row=0, column=1)
        bframe.grid(row=1, column=0)

    def populate_features(self):
        vars = self.selected_features = dict((f, IntVar()) for f in self.features)
        widget = Frame(self)
        row = 0
        for f in self.features:
            cb = Checkbutton(widget, text=f, variable=vars[f])
            vars[f].set(1)
            cb.grid(row=row, column=0, sticky="w")
            row += 1
        return widget

    def populate_parameters(self):
        widget = Frame(self)
        mplabel = Label(widget, text="Max. positive")
        mpentry = Entry(widget, textvariable=self.max_positive, validate="focusout",
                        validatecommand=self.validate_max_positive)
        nplabel = Label(widget, text="Negative proportion")
        npentry = Entry(widget, textvariable=self.negative_proportion, validate="focusout",
                        validatecommand=self.validate_negative_proportion)
        mplabel.grid(row=0, column=0)
        mpentry.grid(row=0, column=1)
        nplabel.grid(row=1, column=0)
        npentry.grid(row=1, column=1)
        return widget

    def populate_buttons(self):
        buttons = dict(
            Go=self.go_command,
            Stop=self.stop_command,
            Done=self.done_command
        )
        return ButtonFrame(self, **buttons)

    def validate_max_positive(self):
        try:
            newvalue = int(self.max_positive.get())
            if newvalue < 0:
                return False
            else:
                return True
        except ValueError:
            return False

    def validate_negative_proportion(self):
        try:
            newvalue = float(self.negative_proportion.get())
            if newvalue < 0:
                return False
            else:
                return True
        except KeyError:
            return False

    def go_command(self):
        self.stop = False
        print("Assembling training data")
        positive, negative = self.get_training_data()
        print("Got %d positive and %d negative" % (len(positive), len(negative)))

    def get_training_data(self):
        positive = []
        negative = []
        for label, tseqs, matches in self.spooler.scan(self.patname, yield_non_matching=True):
            if self.stop:
                break
            print("Processing %s" % label)
            pos = {}
            for match, _, _ in matches:
                tseq = match.seq
                tseqid = id(tseq)
                toks = list(range(match.begin, match.end))
                try:
                    target_toks = pos[tseqid][1]
                    for tok in toks:
                        target_toks.add(tok)
                except KeyError:
                    pos[tseqid] = (tseq, set(toks))
            positive.append(list(pos.values()))
            np = float(self.negative_proportion.get())
            tseqs_copy = list(tseqs)
            random.shuffle(tseqs_copy)
            for tseq in tseqs_copy:
                if len(negative) > len(positive) * np:
                    break
                negative.append((tseq, set()))
        return positive, negative

    def stop_command(self):
        self.stop = True

    def done_command(self):
        self.destroy()
