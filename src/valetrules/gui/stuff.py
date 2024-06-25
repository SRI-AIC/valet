# Apparently this is old code from vrgui.py that did not get incorporated
# into gui/*.py during Dayne's refactoring of the former into the latter.

from datetime import datetime
import glob
import os
from pathlib import Path
import re
import signal
import subprocess
from threading import Timer

from tkinter import Button, Checkbutton, DoubleVar, Entry, IntVar, Label, \
    Listbox, Message, messagebox, StringVar, Text, Toplevel, \
    E, W, N, NW, MULTIPLE, SINGLE, TOP, END, BOTH, LEFT, SOLID
from tkinter.ttk import Frame, Progressbar, Style

from ..manager import VRManager
from .spooler import Spooler

class Manager(object):

    def __init__(self, application, pattern_file, data_source, embedding_file=None):
        self.vrm = VRManager(pattern_file=pattern_file)
        self.vrm.set_expander(application.term_expansion)
        if embedding_file is not None:
            self.vrm.read_embedding(embedding_file)
        self.vrm.pattern_file = pattern_file
        self.pattern_file = pattern_file
        Spooler.set_source(data_source)
        self.spooler = Spooler()
        self.application = application
        self.current_name = None
        self.source_name = "No text sources found"
        self.token_sequences = []
        self.target_text = ""
        self.line_offsets = None
        self.region = None
        self.pattern_line_offsets = None
        self.stop = False

    def extractor_type(self):
        """
        One of test, fa, dep_fa, coord, frame, etc.
        """
        if self.current_name is None:
            return None
        _, type_, _ = self.vrm.lookup_extractor(self.current_name)
        return type_

    def frames(self):
        """If current pattern is a frame pattern, run against each token
        sequence in the current text, yielding any matching frames."""
        if self.current_name is None:
            return
        ext, type_, subst = self.vrm.lookup_extractor(self.current_name)
        if type_ == 'frame':
            for tseq in self.token_sequences:
                for frame in ext.extract(tseq, subst=subst):
                    yield frame
        else:
            return

    def get_text_blocks(self, count):
        """Pull the next 'count' nonempty sources from self.text_feed,
        returning map from source name to text of source."""
        text_blocks = {}
        i = 0
        while i < count:
            next_source = next(self.text_feed, None)
            if next_source is not None:
                source_name, tseqs = next_source
                if len(tseqs) > 0:
                    text_blocks[source_name] = tseqs[0].text  # text is same for all indices, just use 0
                    i += 1
            else:
                break
        return text_blocks

    def get_document_count(self):
        """
        Get the total number of documents available for training. There must be an easier way to get this - ask Dayne
        """
        count = 0
        for source, tseqs in self.data_source.token_sequences():
            count += 1
            if count % 1000 == 0:
                print("Working on %s " % count)
        return count


    def gather(self, name):
        """Yield all pairs of tseq, matches of the named pattern in the entire data set."""
        count = 0
        for source_name, tseqs in self.data_source.token_sequences():
            if self.stop:
                self.stop = False
                break
            # Note this calls update, which allows stop button clicks to be processed.
            self.application.message("Scanning block %d (%s)" % (count, source_name))
            for tseq in tseqs:
                matches = list(self.vrm.scan(name, tseq))
                if len(matches) > 0:
                    yield tseq, matches
            count += 1

    def export(self):
        if not hasattr(self.data_source, 'export'):
            return False
        frames = list(self.vrm.frames.keys())

        def add_frame_features(tseqs):
            result = {}
            for frame_name in frames:
                for tseq in tseqs:
                    for _ in self.vrm.scan(frame_name, tseq):
                        result[frame_name] = '1'
                        break
                if frame_name not in result:
                    result[frame_name] = '0'
            return result

        self.data_source.export("foo.txt", frames, add_frame_features)

        return True


class Application(Frame):

    def __init__(self, pattern_file, data_source, term_expansion=None, master=None, scale_height=None, font_size=None,
                 embedding_file=None):
        Frame.__init__(self, master)
        self.names = []
        self.selection_changed = False
        self.grid()
        self.term_expansion = None
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
        # If term expansion parameter is specified, load the data into the TermExpansion class
        self.pattern_pane: PatternPane = None
        self.text_pane = None
        self.filename_widget = None
        self.message_widget = None
        self.normal_background = None
        self.positive_only = None
        self.positive_class = StringVar()
        self.createWidgets(term_expansion, font_size)
        self.entities_and_paths = []
        self.string_var_patterns = StringVar()
        self.learning_pattern = False
        self.name_pattern = None
        self.learning = False
        self.model_path = ""
        self.broken = 0
        self.culled = {}
        self.culling = False
        self.stop = False

    def create_pattern_frame(self, font_size):
        return PatternPane(self, self.pattern_file, self.vrm)

    def create_text_frame(self):
        return TextPane(self, self.data_source, self.vrm)

    def create_button_frame(self, control_frame):
        button_frame = Frame(control_frame, relief="groove", borderwidth=2)

        button_col = 0
        bgrid_config = dict(row=0, padx=3, pady=1)

        self.positive_class = StringVar()
        #positive_only = Entry(button_frame, text='', textvariable=self.positive_class)
        #positive_only.grid(row=button_row, column=0)

        parse_button = Button(button_frame, text="Parse", command=self.parse_patterns)
        parse_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        save_button = Button(button_frame, text="Save", command=self.save_command)
        save_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        next_button = Button(button_frame, text="Next", command=self.next_command)
        next_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        scan_button = Button(button_frame, text="Scan", command=self.scan_command)
        scan_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        #cull_button = Button(button_frame, text="Cull", command=self.cull_command)
        #cull_button.grid(column=button_col, **bgrid_config)
        #button_col += 1

        stop_button = Button(button_frame, text="Stop", command=self.stop_command)
        stop_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        rewind_button = Button(button_frame, text="Rewind", command=self.rewind_command)
        rewind_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        clear_button = Button(button_frame, text="Clear", command=self.clear_command)
        clear_button.grid(column=button_col, **bgrid_config)
        button_col += 1

        #gather_button = Button(button_frame, text="Gather", command=self.gather, width=button_width)
        #gather_button.grid(row=button_row, column=button_col)
        #button_col += 1

        #export_button = Button(button_frame, text="Export", command=self.export)
        #export_button.grid(column=button_col, **bgrid_config)
        #button_col += 1

        # Only enable this feature if the flair model learning library is available.
        #if model_learning_available:
        #    self.learn_button = learn_button = Button(button_frame, text="Learn", command=self.learn, width=button_width)
        #    learn_button.grid(row=button_row, column=1)
        #    button_row += 1

        # Only draw the 'Expand' button if we are using the term expansion feature
        #if term_expansion is not None:
        #    expand_button = Button(button_frame, text="Expand", command=self.expand, width=button_width)
        #    expand_button.grid(row=button_row, column=1)
        #   button_row += 1

        #self.pattern_button = Button(button_frame, text="Pattern", command=self.pattern, width=button_width)
        #self.pattern_button.grid(row=button_row, column=1)
        #self.pattern_button["state"] = "disabled"
        #button_row += 1

        #self.quitButton = Button(button_frame, text="Quit", command=self.quit, width=button_width)
        #self.quitButton.grid(row=button_row, column=1)
        #button_row += 1

        button_frame.grid_rowconfigure(0, weight=1)
        for col in range(button_col):
            button_frame.grid_columnconfigure(col, weight=1)

        return button_frame

    def create_message_frame(self, control_frame):
        message_frame = Frame(control_frame)

        # Trying text widget for both of these to enable copying of the text.
        # As a side effect, the background defaults to white, so changing it
        # to gray but a bit darker than the background.
        # https://stackoverflow.com/questions/3842155/is-there-a-way-to-make-the-tkinter-text-widget-read-only

        # filename_widget = self.filename_widget = Label(message_frame, text='', height=3, width=90,
        #                                                wraplength=800, relief="sunken", anchor="nw", padx=5, pady=5,
        #                                                font=("Helvetica", "16"), justify=LEFT)
        filename_widget = self.filename_widget = Text(message_frame, height=1, width=90,
                                                    relief="sunken", padx=5, pady=5, background="gray88",
                                                    font=("Helvetica", "16"))
        filename_widget.configure(state="disabled")
        filename_widget.bind("<1>", lambda event: filename_widget.focus_set())
        filename_widget.grid(row=0, column=0, sticky="we")

        # message_widget = self.message_widget = Label(message_frame, text='', height=3, width=90,
        #                                              wraplength=800, relief="sunken", anchor="nw", padx=5, pady=5,
        #                                              font=("Helvetica", "16"), justify=LEFT)
        message_widget = self.message_widget = Text(message_frame, height=3, width=90,
                                                     relief="sunken", padx=5, pady=5, background="gray88",
                                                     font=("Helvetica", "16"))
        message_widget.configure(state="disabled")
        message_widget.bind("<1>", lambda event: message_widget.focus_set())
        message_widget.grid(row=1, column=0, sticky="nswe")

        message_frame.grid_rowconfigure(0, weight=1)
        message_frame.grid_rowconfigure(1, weight=1)
        message_frame.grid_columnconfigure(0, weight=1)

        return message_frame

    def create_control_frame(self):
        control_frame = Frame(self)

        button_frame = self.create_button_frame(control_frame)
        button_frame.grid(row=0, column=0, sticky="wns")

        message_frame = self.create_message_frame(control_frame)
        message_frame.grid(row=1, column=0, sticky="nsew")


        control_frame.grid_rowconfigure(0, weight=1)
        control_frame.grid_rowconfigure(1, weight=1)
        control_frame.grid_columnconfigure(0, weight=1)

        return control_frame

    def create_progress_bar(self):
        # Adds a status bar to the bottom of the main window. This is mainly used to track the progress of the
        # background sequence learning process but is also a vehicle for other status messages. See status_message()
        # for details
        progress_bar_style = self.progress_bar_style = Style(self)
        progress_bar_style.layout('text.Horizontal.TProgressbar',
                        [
                            (
                                'Horizontal.Progressbar.trough',
                                {
                                    'children':
                                     [
                                         (
                                             'Horizontal.Progressbar.pbar',
                                              {
                                                  'side': 'left',
                                                  'sticky': 'ns'
                                              }
                                         )
                                     ],
                                        'sticky': 'nswe'
                                     }
                             ),
                             (
                                 'Horizontal.Progressbar.label',
                                 {
                                     'sticky': '',
                                     'side': 'right'
                                 }
                             )
                         ]
                     )
        # set initial text
        progress_bar_style.configure('text.Horizontal.TProgressbar', text='Standing By   ', background='sky blue')
        # create progressbar
        self.progress_bar_value = DoubleVar(self)
        progress_bar = self.progress_bar = Progressbar(self, style='text.Horizontal.TProgressbar',
                                                       variable=self.progress_bar_value)
        progress_bar.bind("<Button-1>", self.status_bar_clicked)

        return progress_bar

    def createWidgets(self, term_expansion, font_size):
        self.pattern_pane = pattern_frame = self.create_pattern_frame(font_size)
        pattern_frame.grid(row=0, column=0, sticky="nsew")
        self.pattern_pane.parse()

        self.text_pane = text_frame = self.create_text_frame()
        text_frame.grid(row=1, column=0, sticky="nsew")
        self.text_pane.set_requirements(self.pattern_pane.get_requirements())

        control_frame = self.create_control_frame()
        control_frame.grid(row=2, column=0, sticky="nsew")

        progress_bar = self.create_progress_bar()
        progress_bar.grid(row=3, column=0, columnspan=1, sticky="we")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Populate initial contents.
        for _ in self.text_pane.scroll():
            break
        self.populate_text_widget()

    def display_pattern_matches(self, patname):
        self.text_pane.display_pattern_matches(patname)

    def get_fname_label(self):
        """ ... """
        fname_label = self.text_pane.text_manager.get_label()
        if len(fname_label) > 30:
            fname_label = '...' + fname_label[len(fname_label) - 30:]
        #if self.manager.token_sequences is not None and len(self.manager.token_sequences) > 0:
        #    tseq = self.manager.token_sequences[0]
        #    if hasattr(tseq, 'meta'):
        #        fname_label = "; ".join("%s=%s" % (k, v) for k, v in tseq.meta.items())
        return fname_label

    def populate_text_widget(self):
        """Put the current text into the text widget and its source name into the label widget."""
        self.text_pane.populate()
        fname_label = self.get_fname_label()
        self._set_tk_text_widget_text(self.filename_widget, fname_label)

    # I forget exactly why the configure calls are needed, but they are.
    # Added when I converted to text widgets to allow copying text from widget.
    # "tk_text_widget" here refers to the widget type.
    def _set_tk_text_widget_text(self, widget, text):  # self not used, could make it a module method
        widget.configure(state="normal")
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state="disabled")

    def set_current_name(self, name):
        self.current_name = name

    def parse_patterns(self):
        self.pattern_pane.parse()

    def save_command(self):
        """Save the patterns to the manager's pattern_file."""
        self.status_message("Saving...")
        self.pattern_pane.save()
        self.message("Patterns written to %s" % self.pattern_file)
        self.status_message("Saved")
        self.status_message("Standing By")

    def next_command(self):
        """Advance to the next file, displaying any matches."""
        self.culling = False
        self.text_pane.next(self.current_name)

    # TODO Do we ever need to check for a scan operation in progress,
    # e.g., before starting a new scan, doing rewind, etc.?
    def scan_command(self):
        """Find the next file with matches and display them."""
        self.culling = False
        if self.current_name is None:
            self.message("No pattern selected")
            return
        text, matches = self.text_pane.scan(self.current_name)
        self.text_pane.display_matches(matches, refresh=True)

    def cull_command(self):
        """Like scan but intended to make it easy to assemble a list of tokens for inclusion in a membership test"""
        if self.manager.current_name is None:
            self.message("No pattern selected")
            return
        if not self.culling:
            self.culling = True
            self.culled = {}
        while True:
            text, matches = self.manager.scrolling_scan(self.manager.current_name)
            cullable = set()
            for m, _, _ in matches:
                if m.end - m.begin == 1:
                    tok = m.matching_text()
                    if tok not in self.culled:
                        cullable.add(tok)
            if len(cullable) > 0:
                break
        self.display_matches(matches, refresh=True)
        for tok in cullable:
            self.culled[tok] = False

    def gather_command(self):
        from ed.cluster import DBScan
        name = self.manager.current_name
        clustering = DBScan()
        if name is None:
            self.message("No pattern selected")
            return
        count = 0
        for tseq, matches in self.manager.gather(name):
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

    def rewind_command(self):
        self.culling = False
        """Go back to the first file and display its matches."""
        self.text_pane.rewind(self.current_name)

    def stop_command(self):
        """Stop the scan operation."""
        self.stop = True

    def export_command(self):
        if not self.manager.export():
            self.message("Data source has no export method")
        else:
            self.message("Export complete")

    def clear_command(self):
        """Clear selected rule and any matches"""
        self.culling = False
        self.culled = {}
        # Set to no rule selected
        self.current_name = None
        self.pattern_pane.clear()
        self.text_pane.clear()

    def learn_command(self):
        # Present the user with a set of reasonable defaults for launching sequence labeling on the data. This will
        # run in the background but the status of the run is updated as it proceeds. The user is also offered ways to
        # interrupt the learning process or to get early results.
        # TODO: This is slow when there are a lot of documents - there must be an easier way
        total_document_count = self.manager.get_document_count()

        # Get the list of extractors to train on but remove the non user labels (not sure what they are)
        labels = self.manager.vrm.all_extractor_names()
        labels.remove("START")
        labels.remove("END")
        labels.remove("ROOT")
        configure_learning = ConfigureLearningDialog(self, title='Configure Sequence Label Learning',
                                                    doc_count=total_document_count, labels=labels)
        self.docs_to_use = int(configure_learning.docs_to_use)
        self.training_percentage = int(configure_learning.training_percentage)
        self.testing_percentage = int(configure_learning.testing_percentage)
        self.dev_percentage = int(configure_learning.dev_percentage)
        labels_to_train = configure_learning.selected_labels
        self.max_epochs = int(configure_learning.max_epochs)

        # Convert the chosen number of documents to the conll format so the model learning can understand the training
        # tags
        self.status_message("Generating model learning corpus using chosen patterns on %s documents" % self.docs_to_use)

        # Ensure paths are present
        self.training_data_path = "output/training_data"
        self.conll_data_path = "output/conll_training_data"
        Path(self.training_data_path).mkdir(parents=True, exist_ok=True)
        Path(self.conll_data_path).mkdir(parents=True, exist_ok=True)

        # Purge existing training data:
        files = glob.glob('%s/*' % self.training_data_path)
        for f in files:
            os.remove(f)
        files = glob.glob('%s/*' % self.conll_data_path)
        for f in files:
            os.remove(f)

        # Dump out the chosen number of documents in .txt format for the conll processor to use:
        text_blocks = self.manager.get_text_blocks(self.docs_to_use)
        print("Got the docs for writing")
        for doc_id, text in text_blocks.items():
            index_of_file_name = doc_id.rfind("/") + 1
            doc_id = doc_id[index_of_file_name:]
            if '.txt' not in doc_id:
                file_name = "%s/%s.txt" % (self.training_data_path, doc_id)
            else:
                file_name = "%s/%s" % (self.training_data_path, doc_id)
            with open(file_name, 'w') as text_file:
                text_file.write(text)

        # Launch conll data labelling process in a separate process:
        self.label_data_process = self.runModule('launch-label-data-process.py', self.pattern_file,
                                                 self.training_data_path, self.conll_data_path,
                                                 labels_to_train)
        self.label_data_timer = RepeatedTimer(3, self.monitor_data_labelling_progress)

    def monitor_data_labelling_progress(self):
        # Count how many documents have been converted to the conll format
        files = glob.glob('%s/*' % self.training_data_path)
        input_file_count = len(files)
        files = glob.glob('%s/*' % self.conll_data_path)
        conll_file_count = len(files)

        percent_complete = round((conll_file_count / input_file_count) * 100, 2)
        if percent_complete == 100:
            self.status_message("Conversion 100% complete. Launching Flair learning")
            self.label_data_timer.stop()
            # Launch the model learning
            self.initiate_model_training()
        else:
            self.status_message("Conversion %s%% complete. %s documents to go" % (percent_complete, input_file_count - conll_file_count))


    def initiate_model_training(self):
        self.status_message("Initiating Model Learning with %s epochs and %s documents. Click here to cancel" %
                            (self.max_epochs, self.docs_to_use))

        # Get the list of documents for learning to use
        source_documents = []
        files = glob.glob('%s/*' % self.conll_data_path)
        for file in files:
            source_documents.append("%s/%s" % (os.getcwd(), file))

        # TODO: Manage versioning of runs so the user can choose which model to apply
        self.model_path = "output/training/"
        splits_file = "dataset-splits.csv"
        self.write_splits_file(source_documents, self.training_percentage, self.testing_percentage,
                               self.dev_percentage, self.docs_to_use, model_path=self.model_path,
                               splits_file=splits_file)

        index = self.manager.source_name.rfind("/")
        data_dir = self.manager.source_name[0:index]

        # Purge old training logs if they are present
        log_file = Path("%s/training.log" % self.model_path)
        if log_file.exists():
            log_file.unlink()

        self.learning = True
        self.learn_button["state"] = "disabled"

        # Launch Learning process on a separate process:
        self.learn_process = self.runModule('launch-learn-process.py', self.max_epochs, self.model_path,
                                            splits_file, self.conll_data_path)

        # Monitor Learning process by detecting milestones in the log
        self.current_epoch = 1
        # self.current_iter = 1
        self.learning_start_time = datetime.now()
        self.learning_monitor_timer = RepeatedTimer(1, self.monitor_learning_progress, self.model_path, self.max_epochs)

    def runModule(self, module, *args):
        """
        Manages launching python modules in a separate processes. The *args holds any extra parameters that the modules
        may need.
        """
        command_line = "python " + os.path.dirname(os.path.realpath(__file__)) + "/" + module
        for arg in args:
            command_line += " %s" % str(arg)
        print(f"Command Line: {command_line}")
        process = subprocess.Popen(command_line, shell=True)
        return process

    def get_duration(self, start_time):
        """
        Used to track how long each epoch takes to complete which gives us an estimated time to completion
        """
        minutes = round(((datetime.now() - start_time).total_seconds() / 60), 2)
        return minutes

    def status_bar_clicked(self, event):
        # Check to see if learning has completed
        if not self.learning:
            # Check to see if a model is available:
            model_file = Path("%s/best-model.pt" % self.model_path)
            if model_file.exists():
                # make a sentence
                sentence = Sentence(self.manager.get_target_text())
                # load the NER tagger
                tagger = SequenceTagger.load(model=model_file)
                # run NER over sentence
                tagger.predict(sentence)
                # iterate over entities and print
                ner_data = ""
                for entity in sentence.get_spans('ner'):
                    ner_data += "%s\n" % entity
                self.text_widget.delete('1.0', 'end')
                self.text_widget.insert('1.0', "%s\n\n%s" % (self.manager.get_target_text(), ner_data))
                # TODO: Highlight the tagged elements in the panel, slightly different color that produced by the rules
                #  so the user can tell what is being identified by the model
                print("Model Results: %s" % ner_data)
        else:
            # Still working on the first epoch - the user wants to cancel the learning process
            if self.current_epoch == 1:
                title = 'Cancel Learning'
                message = 'Are you sure you want to cancel Model Learning?'
            # A model exists but we have more training to do - the user wants to exit early and use the best available model
            elif self.current_epoch > 1 and self.current_epoch <= self.max_epochs:
                title = 'Finish Learning early'
                message = 'Are you sure you want to finish learning and use the best available model?'
            # Training is complete, user wants to exit evaluation and testing of model
            else:
                title = 'Exit Model testing and evaluation'
                message = 'Are you sure you want to exit Model testing and evaluation?'

            user_choice = messagebox.askquestion(title, message, icon='warning')
            if user_choice == 'yes':
                self.learning = False
                self.learn_button["state"] = "normal"
                # Simulate a ctrl-c keyboard entry for sub process
                self.learn_process.send_signal(signal.SIGINT)
                self.learning_monitor_timer.stop()
                self.progress_bar_value.set(0)
                self.status_message("Standing By")

    def monitor_learning_progress(self, model_path, max_epochs):
        log_file = Path('%s/training.log' % model_path)
        if log_file.is_file():
            # Compile the search pattern to make search more efficient
            # iter_pattern = re.compile("epoch %s.*iter %s" % (self.current_epoch, self.current_iter))
            # next_iter_pattern = re.compile("epoch %s.*iter %s" % (self.current_epoch, self.current_iter + 1))
            epoch_pattern = re.compile("EPOCH %s done:" % self.current_epoch)
            results_pattern = re.compile(".*score.*micro.*")
            for line in open(log_file, 'r'):
                # This got ugly - come back and see if there is an easier way to harvest the iter info. Not essential so
                # punt for now.
                # iteration_status = ""
                # if self.current_epoch < max_epochs and iter_pattern.search(line):
                #     iteration_start = line.find(" iter ") + 6
                #     iteration_end = line.find(" loss ") - 3
                #     iteration_status = line[iteration_start:iteration_end]
                # if self.current_epoch < max_epochs and next_iter_pattern.search(line):
                #     iteration_start = line.find(" iter ") + 6
                #     iteration_end = line.find(" loss ") - 3
                #     iteration_status = line[iteration_start:iteration_end]
                #     self.current_iter += 1
                if self.current_epoch <= max_epochs and epoch_pattern.search(line):
                    # When the current epoch is complete, update the epoch number we are waiting to complete
                    percentage_progress = round((self.current_epoch / max_epochs) * 100, 0)
                    step = round(((1 / max_epochs) * 100), 0)
                    # Time since learning started
                    duration_in_mins = self.get_duration(self.learning_start_time)
                    # extrapolate total time based on average epoch durations to date
                    total_etr = (duration_in_mins / self.current_epoch) * max_epochs
                    # subtract time to date to get likely remaining time
                    etr = round(total_etr - duration_in_mins, 2)
                    self.status_message("Learning %s%% complete. Estimated remaining time: %s minutes"
                                        " (Click here to End Training and use best model to date)" %
                                        (percentage_progress, etr))
                    if self.current_epoch == max_epochs:
                        self.progress_bar_value.set(0)
                        self.status_message("Learning complete. Finalizing Model...")
                    else:
                        self.current_iter = 1
                        self.progress_bar_increment(step)
                    # Increment so it passes beyond the max expected so execution no longer comes in here.
                    self.current_epoch += 1
                if results_pattern.search(line):
                    self.learning_monitor_timer.stop()
                    # Get the final score and reset the button and monitor states
                    score = line[line.find(": ") + 2:]
                    self.status_message("Model finalized. Final F-score (micro: %s)" % score.strip())
                    self.learning = False
                    self.learn_button["state"] = "normal"

    def write_splits_file(self, source_documents, training_percentage, testing_percentage, dev_percentage,
                          docs_to_use, model_path, splits_file):
        Path(model_path).mkdir(parents=True, exist_ok=True)
        splits_file_name = "%s/%s" % (model_path, splits_file)
        allocations = self.allocate_by_percentage(available=docs_to_use,
                                                  weights=(training_percentage, testing_percentage, dev_percentage))
        with open(splits_file_name, 'w') as splits_file:
            splits_file.write("filename,dataset\n")
            index = 0
            for file in source_documents:
                type = index % 3
                # Check to see if there is any allocation left in this type, if not, move to the next one
                moves = 1
                while allocations[type] == 0:
                    type = (index + moves) % 3
                    moves +=1
                index += 1
                allocations[type] -= 1
                if type == 0:
                    type_string = "train"
                elif type == 1:
                    type_string = "test"
                else:
                    type_string = "dev"
                splits_file.write("%s,%s\n" % (file, type_string))

    def allocate_by_percentage(self, available, weights):
        distributed_amounts = []
        total_weights = sum(weights)
        for weight in weights:
            weight = float(weight)
            if weight > 0:
                p = weight / total_weights
                distributed_amount = round(p * available)
                distributed_amounts.append(distributed_amount)
                total_weights -= weight
                available -= distributed_amount
        return distributed_amounts

    def expand(self):
        """
        Called when the user clicks the 'Expand' button. This button and feature are available when a path to a
        term_expansion data directory are provided at start up time (see -t option).
        """
        selected_term = EnterTermAndToggle(self, title="What term would you like to expand")
        include_mwus = bool(selected_term.mwus)
        self.expand_term(selected_term.term, include_mwus=include_mwus)

    def expand_term(self, input_term, include_mwus=False, limit=50):
        # Sumbit the term to the term expansion code which returns a list of tuples from term to divergence with the
        # supplied term.
        terms_tuples = self.term_expansion.get_similar_terms(term=input_term, limit=limit)
        adjacent_terms = []
        for tuple in terms_tuples:
            term = tuple[0]
            # Filter out multi word units (MWU's)
            if not include_mwus:
                if ' ' in term:
                    continue
            divergence = tuple[1]
            adjacent_terms.append(term + " (" + str(round(divergence, 3)) + ")")
        # Ask the user to select the terms that should be used to build the new detector
        dialog = ChoiceDialog(self, 'Similar Terms', text='Select terms to add to the context list',
                              items=adjacent_terms)
        # Build a new detector string with appropriate formatting
        paste_string = "new_detector: { %s" % input_term
        leader_length = len(paste_string)
        current_line = leader_length
        terms = [ input_term ]
        for term in dialog.selection:
            selected_term = term[0:(term.find('(') - 1)]
            if selected_term in terms:
                continue
            formatted_term = " %s" % selected_term
            if current_line + len(formatted_term) > 72:
                paste_string += "\n"
                paste_string += "               "
                # Reset line length
                current_line = leader_length
            current_line += len(formatted_term)
            paste_string += formatted_term
            terms.append(selected_term)
        paste_string += " }i"
        # Push the new detector into the paste board for the user to add to the desired location
        self.write_to_clipboard(paste_string)

    def write_to_clipboard(self, output):
        """
        Push the result of Term Expansion into the systems paste board
        """
        process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
        process.communicate(output.encode('utf-8'))

    def pattern(self):
        """
        Called when the user clicks the 'Pattern' button.
        """
        # Check to see if an existing patterns has been selected for amendment
        if self.name_pattern is not None:
            print(f"Amending existing pattern: {self.name_pattern[0]} {self.name_pattern[1]} {self.name_pattern[2]}")
        self.pattern_button["state"] = "disabled"
        self.learning_pattern = True
        pattern = BuildNewPattern(self, title="Create a new rule pattern", items=self.string_var_patterns,
                                  exising_pattern=self.name_pattern)
        if pattern.patterns is not None:
            print("Pattern:", pattern.patterns)
            regex = RegexExpression(expr=pattern.patterns).parse()
            print("Regex:", regex)
            regex = regex.reduce()
            print("Reduced:", regex)
            name = "new_pattern ^ "
            # If we are amending a patterns we want to use the existing pattern name as a base
            if self.name_pattern:
                name = "%s_updated %s" % (self.name_pattern[0], self.name_pattern[1])
            # Push the new pattern into the paste board for the user to add to the desired location
            paste_string = "%s %s" % (name, regex)
            self.write_to_clipboard(paste_string)
        # After completing a pattern collection cycle reset all involved vehicles
        self.learning_pattern = False
        self.string_var_patterns = StringVar()
        self.entities_and_paths = []
        self.name_pattern = None

    def expand_text_pane_term(self, *args):
        tseqi, tokeni = self.manager.get_token_indexes('current')
        #        print((tseqi, tokeni))
        tseq = self.manager.token_sequences[tseqi]
        self.expand_term(tseq[tokeni].lower())

    def present_learning_example(self, *args):
        pattern_name = self.manager.current_name
        if pattern_name is None:
            self.message("No pattern selected")
            return
        learning_test = self.manager.vrm.lookup_learning_test(pattern_name)
        if learning_test is None:
            self.message("'%s' is not a learning_test" % pattern_name)
            return
        is_positive = 'match' not in self.text_widget.tag_names('current')
        tseqi, tokeni = self.manager.get_token_indexes('current')
        tseq = self.manager.token_sequences[tseqi]
        learning_test.train(tseq, tokeni, is_positive)
        self.display_pattern_matches(pattern_name)

    def message(self, text):
        """Calling this has the side effect of allowing stop button clicks to be processed, etc."""
        if len(text) > 100:
            text = text[0:100] + '...'
        self._set_tk_text_widget_text(self.message_widget, text)
        # Not only does this allow the message widget changes to be processed,
        # but also allows stop button clicks to be processed, etc.
        self.update()

    def status_message(self, text):
        self.progress_bar_style.configure('text.Horizontal.TProgressbar', text=text + '   ', orient='right')
        self.update()

    def progress_bar_increment(self, portion_complete):
        self.progress_bar.step(amount=portion_complete)

class RepeatedTimer(object):
    """
    Convenience class for running model learning status assessment method on a specified interval. This allows a non
    blocking loop to determine when the model training reaches maturity.
    """
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


class EnterTermAndToggle(simpledialog.Dialog):
    """
    Dialog box with term entry and multi-word-units checkbox
    """
    def __init__(self, parent, title):
        super().__init__(parent, title=title)

    def body(self, parent):
        Label(parent, text="Term to expand:").grid(row=0, sticky=W)
        Label(parent, text="Include multi word units?").grid(row=1, sticky=W)

        self.enter_term = Entry(parent)
        self.answerreturn = IntVar()
        self.answer = Checkbutton(parent, variable=self.answerreturn)

        self.enter_term.grid(row=0, column=1)
        self.answer.grid(row=1, column=1, sticky=W)

        self.enter_term.focus_set()

    def apply(self):
        self.term = self.enter_term.get()
        self.mwus = self.answerreturn.get()


class ConfigureLearningDialog(simpledialog.Dialog):
    """
    Dialog box with parameters for controlling sequence learning. Future versions may expose more underlying parameters
    """
    def __init__(self, parent, title, doc_count, labels):
        self.doc_count = doc_count
        self.labels = labels
        super().__init__(parent, title=title)

    def body(self, parent):
        # TODO: Use more pleasing widgets for selecting % allocations
        # TODO: Automatically deduct/add values from/to other allocations when one changes
        # TODO: Break the widgets into logical visual groups
        # Total docs available
        Label(parent, text="Number of documents available: ").grid(row=0, sticky=W, padx=10)
        Label(parent, text=str(self.doc_count)).grid(row=0, column=1, sticky=E, padx=10)

        # How many to use
        Label(parent, text="Number of documents to include: ").grid(row=1, sticky=W, padx=10)
        self.docs_to_use = Entry(parent, justify='right')
        self.docs_to_use.grid(row=1, column=1, padx=10)
        self.docs_to_use.insert(0, str(self.doc_count))

        # % Document Splits for training
        Label(parent, text="% Training: ").grid(row=2, sticky=W, padx=10)
        self.training = Entry(parent, justify='right')
        self.training.grid(row=2, column=1, padx=10)
        self.training.insert(0, "60")
        # % Document Splits for testing
        Label(parent, text="% Testing: ").grid(row=3, sticky=W, padx=10)
        self.testing = Entry(parent, justify='right')
        self.testing.grid(row=3, column=1, padx=10)
        self.testing.insert(0, "30")
        # % Document Splits for dev
        Label(parent, text="% Dev: ").grid(row=4, sticky=W, padx=10)
        self.dev = Entry(parent, justify='right')
        self.dev.grid(row=4, column=1, padx=10)
        self.dev.insert(0, "10")

        # Labels to be trained
        Label(parent, text="Choose Labels to Train on: ").grid(row=5, sticky=NW, padx=10)
        self.label_list = Listbox(parent, selectmode=MULTIPLE)
        for label in self.labels:
            self.label_list.insert(END, label)
        self.label_list.grid(row=5, column=1, padx=10, pady=10)

        # Number of epochs
        Label(parent, text="Maximum Epochs: ").grid(row=6, sticky=W, padx=10)
        self.epochs = Entry(parent, justify='right')
        self.epochs.grid(row=6, column=1, padx=10)
        self.epochs.insert(0, "3")

    def apply(self):
        self.docs_to_use = self.docs_to_use.get()
        self.training_percentage = self.training.get()
        self.testing_percentage = self.testing.get()
        self.dev_percentage = self.dev.get()
        self.max_epochs = self.epochs.get()
        reslist = ""
        selection = self.label_list.curselection()
        for i in selection:
            entry = self.label_list.get(i)
            reslist += " %s" % entry
        self.selected_labels = reslist


class BuildNewPattern(Toplevel):
    """
    Non Modal Dialog box to collect rules for compilation into a general rule pattern
    """
    def __init__(self, parent, title=None, modal=True, items=None, exising_pattern=None):
        Toplevel.__init__(self, parent)
        self.patterns = None
        self.items = items
        self.exising_pattern = exising_pattern
        self.transient(parent)
        if title:
            self.title(title)
        self.parent = parent
        self.result = None
        # body = Frame(self)
        # Calls the body function which is overridden, and which draws the dialog
        self.initial_focus = self.body()
        if not self.initial_focus:
            self.initial_focus = self
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        self.initial_focus.focus_set()
        if modal:
            self.wait_window(self)

    def body(self):
        topFrame = Frame(self)
        middleFrame = Frame(self)
        bottomFrame = Frame(self)

        topFrame.pack(side="top", fill="both", expand=True, pady=10, padx=15)
        middleFrame.pack(side="top", fill="both", expand=True)
        bottomFrame.pack(side="bottom", fill="both", expand=True, pady=10)

        # User wants to amend an existing pattern, show it in the dialog
        if self.exising_pattern is not None:
            Label(topFrame, text="Amend Existing Pattern").pack(side="left")
            existing_pattern_string = "%s %s %s" % (self.exising_pattern[0], self.exising_pattern[1],
                                                    self.exising_pattern[2])
            entry = Entry(topFrame, width=len(existing_pattern_string))
            entry.pack(side="top")
            entry.insert(0, existing_pattern_string)

        Label(middleFrame, text="Elements and paths").pack(side="top")

        self._list = Listbox(middleFrame, selectmode=SINGLE, listvariable=self.items)
        # Makes the list adjust size to the contents
        self._list.config(width=0)
        self.ok = Button(bottomFrame, text="Generate Pattern", command=self.generate, width=15)
        self.remove = Button(bottomFrame, text="Remove", command=self.remove, width=15)
        self.remove["state"] = "disabled"
        self.cancel = Button(bottomFrame, text="Cancel", command=self.cancel, width=15)

        self._list.pack(side="top", padx=30, pady=5, fill=BOTH, expand=True)
        self.ok.pack(side="top")
        self.remove.pack(side="top")
        self.cancel.pack(side="top")

        def callback(event):
            selection = event.widget.curselection()
            if selection:
                self.remove["state"] = "normal"
            else:
                self.remove["state"] = "disabled"

        self._list.bind("<<ListboxSelect>>", callback)

    def update_list(self, item):
        self._list.insert(END, item)

    def generate(self):
        # Construct list of patterns for compilation
        self.patterns = ""
        for item in list(eval(self.items.get())):
            if len(self.patterns) > 0:
                self.patterns += " | "
            start_of_pattern = item.index("[")
            list_of_parts = ast.literal_eval(item[start_of_pattern:])
            for part in list_of_parts:
                self.patterns += "%s " % part
            self.patterns.strip()
        # if we are amending an existing pattern, add it to the original
        if self.exising_pattern is not None:
            self.patterns = "%s | %s" % (self.exising_pattern[2], self.patterns)
        self.destroy()

    def remove(self):
        # Delete selected pattern from Listbox
        selection = self._list.curselection()
        self._list.delete(selection[0])

    def cancel(self):
        self.patterns = None
        self.destroy()


class ChoiceDialog(simpledialog.Dialog):
    """
    Dialog box with multiple choice list
    """
    def __init__(self, parent, title, text, items):
        self.selection = None
        self._items = items
        self._text = text
        super().__init__(parent, title=title)

    def body(self, parent):
        self._message = Message(parent, text=self._text, aspect=400)
        self._message.pack(expand=1, fill=BOTH)
        self._list = Listbox(parent, selectmode=MULTIPLE)
        self._list.pack(expand=1, fill=BOTH, side=TOP)
        for item in self._items:
            self._list.insert(END, item)
        return self._list

    def validate(self):
        if not self._list.curselection():
            return 0
        return 1

    def apply(self):
        reslist = list()
        selection = self._list.curselection()
        for i in selection:
            entry = self._list.get(i)
            reslist.append(entry)
        self.selection = reslist


class ToolTip(object):

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None

    def showtip(self, x, y):
        if self.tipwindow or not self.text:
            return
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(tw, text=self.text, justify=LEFT,
                      background="#ffffe0", relief=SOLID, borderwidth=1,
                      font=("tahoma", "8", "normal"))
        print(label)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

