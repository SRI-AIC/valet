from datetime import datetime
import logging
import subprocess
from tkinter.ttk import Frame

from nlpcore.term_expansion import TermExpansion
from valetrules.gui.patpane import PatternPane
from valetrules.gui.textpane import TextPane
from valetrules.gui.controls import ControlFrame
from valetrules.gui.cull import Culler
from valetrules.gui.context import ContextView
from valetrules.manager import VRManager


_logger = logging.getLogger(f"{__name__}.<module>")


class Application(Frame):
    pattern_pane: PatternPane
    text_pane: TextPane
    control_frame: ControlFrame
    culling: bool  # TODO? this is only ever set to False and is never checked

    def __init__(self, pattern_file, data_source, term_expansion=None, master=None, font_size=None,
                 embedding_file=None):
        Frame.__init__(self, master)
        self.grid()
        self.term_expansion = None  # disabled now?
        # If term expansion parameter is specified, load the data into the TermExpansion class
        if term_expansion is not None:
            time = datetime.now().strftime("%H:%M:%S")
            print(f"{time}: Loading term expansion data...")
            self.term_expansion = TermExpansion(input_directory=term_expansion)
            self.term_expansion.read_term_expansion_data()
            time = datetime.now().strftime("%H:%M:%S")
            print(f"{time}: ...Done!")
        self.pattern_file = pattern_file
        self.vrm = VRManager(pattern_file=pattern_file)
        self.vrm.set_expander(self.term_expansion)
        if embedding_file is not None:
            self.vrm.read_embedding(embedding_file)
        self.vrm.pattern_file = pattern_file
        self.data_source = data_source
        self.create_widgets(term_expansion, font_size)
        self.current_name = None
        self.stop = False
        self.cullers = {}

    def create_widgets(self, term_expansion, font_size):

        self.pattern_pane = pattern_frame = PatternPane(self, self.pattern_file, self.vrm)
        pattern_frame.grid(row=0, column=0, sticky="nsew")
        self.pattern_pane.parse()

        self.text_pane = text_frame = TextPane(self, self.data_source, self.vrm)
        text_frame.grid(row=1, column=0, sticky="nsew")
        self.text_pane.set_requirements(self.pattern_pane.get_requirements())

        buttons = dict(
            Parse=self.parse_command,
            Save=self.save_command,
            Next=self.next_command,
            Scan=self.scan_command,
            Cull=self.cull_command,
            Context=self.context_command,
            Stop=self.stop_command,
            Rewind=self.rewind_command,
            Clear=self.clear_command,
        )

        self.control_frame = control_frame = ControlFrame(self, **buttons)
        control_frame.grid(row=2, column=0, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Populate initial contents.
        _logger.debug("Populating GUI initial contents (first scrolling to first doc)")
        for _ in self.text_pane.scroll():
            break
        self.populate_text_widget()

    def get_current_name(self):
        """Current pattern name to match."""
        return self.current_name

    def set_current_name(self, name):
        self.current_name = name

    def parse_command(self):
        """(Re)-parse the pattern pane text."""
        self.pattern_pane.parse()
        self.text_pane.set_requirements(self.pattern_pane.get_requirements())

    def save_command(self):
        """Save the pattern pane text to the manager's pattern_file."""
        self.pattern_pane.save()
        self.message("Patterns written to %s" % self.pattern_file)

    # TODO There's an unclear division of responsibility in terms of
    # who is responsible for rewinding the feed, updating the filename,
    # displaying the matches, etc.
    # E.g., why for next_command is displaying matches done by the text pane,
    # while for scan_command we do it here.
    # And the spooler is responsible for restarting the feed, updating fname,
    # etc.

    def next_command(self) -> None:
        """Advance to the next file (document), displaying any matches."""
        _logger.debug("NEXT BUTTON PUSHED")
        self.culling = False
        try:
            self.text_pane.next(self.current_name)
        except Exception as e:
            self.pattern_pane.invalidate_name(self.current_name, str(e))
            self.current_name = None

    # TODO Do we ever need to check for a scan operation in progress,
    # e.g., before starting a new scan, doing rewind, etc.?
    def scan_command(self) -> None:
        """Find the next document with matches and display them."""
        _logger.debug("SCAN BUTTON PUSHED")
        self.culling = False
        if self.current_name is None:
            self.message("No pattern selected")
            return
        try:
            # TODO For consistency with next and rewind, why not put the call
            # to display_matches inside the scan method?
            _, matches = self.text_pane.scan(self.current_name)
            self.text_pane.display_matches(matches, refresh=True)
        except Exception as e:
            self.pattern_pane.invalidate_name(self.current_name, str(e))
            self.current_name = None

    def stop_command(self) -> None:
        """Stop the scan operation."""
        self.text_pane.stop_command()

    def rewind_command(self) -> None:
        """Go back to the first file, displaying any matches."""
        _logger.debug("REWIND BUTTON PUSHED")
        self.culling = False
        try:
            self.text_pane.rewind(self.current_name)
        except Exception as e:
            self.pattern_pane.invalidate_name(self.current_name, str(e))
            self.current_name = None

    # TODO What does this do?
    def cull_command(self) -> None:
        if self.current_name is None:
            self.message("No pattern selected")
            return
        culler = Culler(self, self.current_name, self.vrm)
        self.cullers[id(culler)] = culler

    def done_culling(self, culler, culled=None):
        if culled is not None:
            new_pattern = "new_lexicon: { %s }" % ' '.join(culled)
            self.write_to_clipboard(new_pattern)
            self.message("Culled terms written to clipboard")
        del self.cullers[id(culler)]
        culler.destroy()

    # TODO What does this do?
    def context_command(self):
        if self.current_name is None:
            self.message("No pattern selected")
            return
        features = self.pattern_pane.get_test_names()
        ContextView(self, self.current_name, self.vrm, features)

    # TODO What does this do?
    # There is no button for this, and no code calls it.
    def gather_command(self):
        from ed.cluster import DBScan
        name = self.vrm.current_name  # TODO no such attribute
        clustering = DBScan()
        if name is None:
            self.message("No pattern selected")
            return
        count = 0
        for tseq, matches in self.vrm.gather(name):
            for match in matches:
                begin = match.begin
                end = match.end
                begin -= 4
                if begin < 0:
                    begin = 0
                end += 4
                if end > len(tseq):
                    end = len(tseq)
                clustering.seed([tseq[i] for i in range(begin, end)])
                count += 1
            if count % 10 == 0:
                clustering.jiggle()
                ccount = clustering.cardinality()
                for i in range(ccount):
                    proto_tseq = clustering.cluster_protoype(i)
                    if proto_tseq is None:
                        print("CLUSTER %d: empty")
                    else:
                        print("CLUSTER %d: %s" % (i, ' '.join(proto_tseq)))
                        for tseq in clustering.cluster_members(i):
                            print("    %s" % ' '.join(tseq))

    def clear_command(self):
        """Clear selected rule and any matches"""
        self.culling = False
        self.culled = {}
        # Set to no rule selected
        self.current_name = None
        self.pattern_pane.clear()
        self.text_pane.clear()
        # self.vrm.clear_cache()  # I use this for debugging

    # There is no button for this.
    def export_command(self):
        if not self.vrm.export():
            self.message("Data source has no export method")
        else:
            self.message("Export complete")

    def populate_text_widget(self):
        """Put the current text into the text widget and its source name into
        the label (filename) widget."""
        self.text_pane.populate()

    def display_pattern_matches(self, patname):
        """Run pattern, and show matches in the text pane."""
        self.text_pane.display_pattern_matches(patname)
        # TODO: Come up with a more principled way to muster frames, e.g., by means of an "Extract" button
        self.report_frames(patname)

    def report_frames(self, patname):
        """This includes any frames in non-frame matches that basically just wrap frames."""
        for frame in self.text_pane.frames(patname):
            print("Frame:", frame.as_json())
            # print("Frame:", frame.as_json(indent=2))  # debug

    def message(self, text):
        """
        Write text to message widget of message frame.
        Calling this has the very important side effect of allowing stop button
        clicks to be processed, etc.
        """
        self.control_frame.message(text)
        self.update()

    def filename(self, text):
        """
        Write text to filename widget of message frame.
        Calling this has the very important side effect of allowing stop button
        clicks to be processed, etc.
        """
        self.control_frame.filename(text)
        self.update()

    def write_to_clipboard(self, output):
        """
        Push the result of Term Expansion into the system's paste board
        """
        process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
        process.communicate(output.encode('utf-8'))
