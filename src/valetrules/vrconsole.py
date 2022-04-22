from cmd import Cmd
from pathlib import Path
import readline
import re
from console.utils import clear_screen, clear_line
from console.screen import sc
from console import fg, fx
from console.detection import get_size
from nlpcore.tokenizer import PlainTextTokenizer
from .manager import VRManager
import json


class Console(Cmd):

    intro = "Valet Rules command console.  Type help or ? for a command list\n"
    prompt = ":: "

    def __init__(self, completekey='tab', stdin=None, stdout=None,
                 pattern_file=None,
                 target_file=None,
                 target_text=None,
                 target_tseqs=None,
                 target_loader=None):
        super().__init__(completekey=completekey, stdin=stdin, stdout=stdout)
        self.pattern_file = pattern_file
        self.vrm = VRManager()
        self.target_loader = target_loader
        if pattern_file is not None:
            self.vrm.parse_file(pattern_file)
        if target_tseqs:
            self.set_target_sequences(target_tseqs)
        elif target_text:
            self.set_target_text(target_text)
        elif target_file:
            self.set_target_file(target_file)
        self.last_name = None
        if pattern_file is not None:
            self.last_source = pattern_file
        else:
            self.last_source = None
        if target_file is not None:
            self.last_target = target_file
        else:
            self.last_target = None
        self.last_def = None
        self.last_save = None
        self.max_lines = 30
        readline.set_completer_delims(" ")
        self.terminal_size = get_size()

    def precmd(self, line):
        return line.strip()

    def set_target_sequences(self, tseqs):
        self.target_tseqs = tseqs

    def set_target_text(self, text):
        self.set_target_sequences([ self.vrm.tokr.tokens(text, offset=0) ])

    def set_target_file(self, fname):
        if self.target_loader is None:
            self.set_target_text(self.vrm.file_contents(fname))
        else:
            self.target_tseqs = self.target_loader(fname)

    def cmdloop(self):
        clear_screen(2)
        print(screen.mv(0,0))
        super().cmdloop()


    # ===========================================================
    # COMMANDS

    def do_def(self, arg):
        "def EXPR: evaluate a FA expression"
        self.vrm.parse_statement(arg)
        self.last_def = arg

    def complete_def(self, text, line, beg, end):
        text = text.strip()
        if text == '' and self.last_def is not None:
            return [self.last_def]
        return []

    show_states = [ 'tests', 'patterns', 'streams', 'coords', 'maxlines' ]

    def do_show(self, arg):
        "show {tests, patterns, streams}: display some aspect state"
        if arg == 'tests':
            self.show_expressions(self.vrm.get_test_expressions(), ':')
        elif arg == 'patterns':
            self.show_expressions(self.vrm.get_fa_expressions(), '->')
        elif arg == 'streams' or arg == 'coords':
            self.show_expressions(self.vrm.get_coord_expressions(), '~')
        elif arg == 'maxlines':
            self.display("Maxlines=%d" % self.maxlines)
        else:
            self.display(f"No such state: '{arg}'. Usage: show tests|patterns|streams")

    def complete_show(self, text, line, beg, end):
        return [ s for s in self.show_states if s.startswith(text) ]

    config_variables = [ 'maxlines' ]

    def do_set(self, arg):
        "set {maxlines} VALUE: set configuration variables"
        m = re.match('\s*(\w+)\s+(\S+)$', arg)
        if not m:
            self.display("Poorly formed input to 'set': %s" % arg)
            return
        var = m.group(1)
        val = m.group(2)
        if var == 'maxlines':
            self.maxlines = int(val)
            self.display("Set: maxlines=%d" % int(val))
        else:
            self.display("No such configuration variable: %s" % var)

    def complete_set(self, text, line, begin, end):
        return [ s for s in self.config_variables if s.startswith(text) ]

    def do_extract(self, arg):
        "extract NAME: extract strings found by extractor NAME"
        try:
            if arg == '':
                arg = self.last_name
            #strings = [ s for s in self.vrm.extract_from_token_sequence(arg, seq)
            #            for seq in self.target_seqs ]
            strings = [ s for s in self.vrm.extract_from_token_sequences(arg,self.target_tseqs) ]
            if len(strings) == 0:
                self.display("No matches")
            else:
                self.display(fx.bold("Matches:\n"), *("  " + s + "\n" for s in strings))
            self.last_name = arg
        except KeyError:
            self.display("No extractor: %s" % arg)

    def complete_extract(self, text, line, beg, end):
        return self.extractor_completion(text)

    def do_path(self,arg):
        "path NAME: dpath of strings found by extractor NAME"
        try:
            if arg == '':
                arg = self.last_name
            #strings = [ s for s in self.vrm.extract_from_token_sequence(arg, seq)
            #            for seq in self.target_seqs ]
            strings = [ s for s in self.vrm.path_from_token_sequences(arg,self.target_tseqs) ]
            if len(strings) == 0:
                self.display("No matches")
            else:
                self.display(fx.bold("Matches:\n"), *("  " + s + "\n" for s in strings))
            self.last_name = arg
        except KeyError:
            self.display("No extractor: %s" % arg)

    def do_pos(self,arg):
        "pos NAME: part of speech of strings found by extractor NAME"
        try:
            if arg == '':
                arg = self.last_name
            #strings = [ s for s in self.vrm.extract_from_token_sequence(arg, seq)
            #            for seq in self.target_seqs ]
            strings = [ s for s in self.vrm.pos_from_token_sequences(arg,self.target_tseqs) ]
            if len(strings) == 0:
                self.display("No matches")
            else:
                self.display(fx.bold("Matches:\n"), *("  " + s + "\n" for s in strings))
            self.last_name = arg
        except KeyError:
            self.display("No extractor: %s" % arg)

    def do_frame(self,arg):
        "frame NAME: frames found by extractor NAME"
        try:
            if arg == '':
                arg = self.last_name
            matches = []
            for tseq in self.target_tseqs:
                matches += self.vrm.scan(arg,tseq)
            #matchstring = [dict([("action",x.solo_text()),("object",x.submatch.matching_text())]) for x in matches]
            matchstring = [x.operator_map() for x in matches]
            #Below is code to deal with "and"s
            reduced = []
            for om in matchstring:
                multis = []
                for (k,v) in om.items():
                    if isinstance(v,list):
                        multis += [k]
                if len(multis) == 0:
                    reduced += [om]
                else:
                    base = dict()
                    for k in [x for x in om.keys() if x not in multis]:
                        base[k] = om[k]
                    toadd = [base]
                    for k in multis:
                        ctoadd = []
                        for v in om[k]:
                            for ta in toadd:
                                newadd = dict()
                                newadd.update(ta)
                                newadd[k] = v
                                ctoadd += [newadd]
                        toadd = ctoadd
                    reduced += ctoadd


            if len(matchstring) == 0:
                self.display("No matches")
            else:
                self.display(json.dumps(reduced,indent=3))
                #self.display(json.dumps(matchstring,indent=3))
            self.last_name = arg
        except KeyError:
            self.display("No extractor: %s" % arg)

    def do_mark(self, arg):
        "mark NAME: display source text marked for matches of NAME"
        mark_fx = fg.red + fx.underline
        mark_fx_b = fg.green + fx.underline
        if arg == '':
            arg = self.last_name
        try:
            markup = self.vrm.markup_from_token_sequences(arg, self.target_tseqs)
            ncontextlines = 1
            lines = markup.split("\n")
            retlinenumbers = set()
            if len(lines) > self.get_max_lines():
                for (linenum,line) in enumerate(lines):
                    if (">>>" in line and "<<<" in line) or ("{{{" in line and "}}}" in line) :
                        retlinenumbers.add(linenum)
                        for i in range(max(0,linenum-ncontextlines),linenum):
                            retlinenumbers.add(i)
                        for i in range(linenum,min(linenum+ncontextlines,len(lines))):
                            retlinenumbers.add(i)
                markup = "\n".join([lines[x] for x in sorted(retlinenumbers)])
            markup = re.sub(r' >>> ([^{}]*?) <<< ', lambda m: mark_fx(m.group(1)), markup, flags=re.S)
            markup = re.sub(r' \{\{\{ ([^><]*?) \}\}\} ', lambda m: mark_fx_b(m.group(1)), markup, flags=re.S)
            markup = re.sub(r'\{\{\{|\}\}\}|>>>|<<<', '', markup, flags=re.S)
            if len(markup) == 0:
                text = self.target_tseqs[0].text
                self.display(fx.bold("No matches") +"\n\n" +  text)
            else:
                self.display(markup)
            self.last_name = arg
        except KeyError:
            self.display("No extractor: %s" % arg)

    def complete_mark(self, text, line, beg, end):
        return self.extractor_completion(text)

    def do_source(self, arg):
        "source FILENAME: evaluate expressions in FILENAME"
        if arg == '':
            if self.last_source:
                arg = self.last_source
            else:
                self.display("No source file specified!")
                return
        self.vrm.parse_file(arg)
        self.display("Loaded definitions in '%s'" % arg)
        self.last_source = arg

    def complete_source(self, text, line, begidx, endidx):
#        self.display(f"Completion got {text}, {line}, {begidx}, {endidx}")
#        self.display(self.parseline(line))
        return self.filename_completion(text, self.last_source)

    def do_target(self, arg):
        "target FILENAME: use contents of FILENAME as target text"
        self.set_target_file(arg)

    def complete_target(self, text, line, begidx, endidx):
        return self.filename_completion(text, self.last_target)

    def do_save(self, arg):
        "save FILENAME: save all defined extractors in FA format to FILENAME"
        if arg == '' and self.last_save:
            arg = self.last_save
        with open(arg, "w") as fh:
            print("### Tests\n", file=fh)
            print(self.expression_block(self.vrm.get_test_expressions(), ":"), file=fh)

            print("### Patterns\n", file=fh)
            print(self.expression_block(self.vrm.get_fa_expressions(), "->"), file=fh)

            print("### Streams\n", file=fh)
            print(self.expression_block(self.vrm.get_stream_expressions(), "~"), file=fh)
        self.display("Definitions saved to '%s'" % arg)

    def complete_save(self, text, line, begidx, endidx):
#        self.display(f"Completion got {text}, {line}, {begidx}, {endidx}")
        return self.filename_completion(text, self.last_save)

    def do_exit(self, arg):
        exit()

    # ====================================================

    def filename_completion(self, prefix, previous):
        prefix = prefix.strip()
        if prefix == '':
            if previous:
                return [previous]
            else:
                return [str(Path.home())]
#        self.display(f"using prefix '{prefix}'")
        path = Path(prefix).expanduser()
        if path.is_dir():
            d = path
            name = ''
        else:
            d = path.parent
            name = path.name
 #       self.display(d, name)
        return [ str(p) for p in d.iterdir() if p.name.startswith(name) ]

    def extractor_completion(self, prefix):
        return sorted(e for e in self.vrm.defined_extractors() if e.startswith(prefix))

    def show_expressions(self, expressions, sep):
        if len(expressions) == 0:
            self.display("No extractors of this type defined")
            return
        self.display(self.expression_block(expressions, sep))

    def expression_block(self, expressions, sep):
        expressions = list(expressions)
        if len(expressions) == 0:
            return "# None"
        namemax = max(len(k) for k,v in expressions)
        fstr = "{name:<{nw}} {sep} {expr}"
        lines = [fstr.format(name=name, expr=expr, nw=namemax, sep=sep)
                 for name, expr in expressions]
        return "\n".join(lines) + "\n\n"

    def get_max_lines(self):
        height = self.terminal_size[1]
        return height - 6

    def display(self, *args):
        clear_screen(0)
        width = self.terminal_size[0]
        height = self.terminal_size[1]
        maxlines = self.get_max_lines()
        string = ''.join(args)
        lines = string.split('\n')
        lcount = 0
        dstring = None
        truncated = False
        for line in lines:
            screenlines = len(line) // width
            if len(line) == 0 or len(line) % width != 0:
                screenlines += 1
            if lcount + screenlines > maxlines:
                truncated = True
                break
            if dstring is None:
                dstring = line
            else:
                dstring += "\n" + line
            lcount += screenlines
        if truncated:
            dstring += "\n" + fx.bold("(truncated %d lines)" % (len(lines) - maxlines))
        print(dstring)
        clear_screen(0)
        print(screen.mv(3, 3))
        clear_line(0)
        print(screen.mv(3, 0))
