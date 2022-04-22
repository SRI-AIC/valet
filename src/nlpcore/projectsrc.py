import json
import csv
import re


from .tseqsrc import DirectorySource, TokenSequenceSource, CsvFileSource


class ASEDEmailSource(DirectorySource):

    NAME = 'asedemail'

    def __init__(self, source_name, filter_regex=None, **kwargs):
        super().__init__(source_name, filter_regex=(filter_regex or r'.*\.txt$'), **kwargs)


class D3MTextSource(TokenSequenceSource):

    NAME = 'd3m'

    def __init__(self, source_name, aux_file=None, positive_label=None, rewrites=None, partition='TRAIN', **kwargs):
        super().__init__(source_name, positive_label=positive_label, rewrites=rewrites, **kwargs)
        self.partition = partition
        self.data_path = "%s/%s/dataset_%s" % (source_name, partition, partition)
        with open("%s/datasetDoc.json" % self.data_path) as fh:
            self.datadoc = json.load(fh)
        resources = self.datadoc['dataResources']
        self.aux_file = aux_file
        self.text_resources = [res for res in resources if res['resType'] == 'text']
        self.learning_data = next(res for res in resources if res['resID'] == 'learningData')
        self.learning_file = self.learning_data['resPath']
        self.learning_text_resource = None
        self.positive_only = False
        for col in self.learning_data['columns']:
            try:
                rto = col['refersTo']
                tr = next((tr for tr in self.text_resources if tr['resID'] == rto['resID']), None)
                if tr:
                    self.text_column = col['colIndex']
                    self.learning_text_resource = tr
                    break
            except KeyError:
                pass
        with open("%s/%s/problem_%s/problemDoc.json" % (source_name, partition, partition)) as fh:
            self.problemdoc = json.load(fh)
        self.target_column = self.problemdoc['inputs']['data'][0]['targets'][0]['colIndex']

    def token_sequences(self, cb=None):
        headers = None
        with open("%s/%s" % (self.data_path, self.learning_file)) as fh:
            csvreader = csv.reader(fh)
            for row in csvreader:
                tseqs = None
                if headers is None:
                    headers = row
                else:
                    d3m_index = row[0]
                    target = row[self.target_column]
                    if self.positive_only and self.positive_label is not None and target != self.positive_label:
                        continue
                    tfile = row[self.text_column]
                    tpath = "%s/%s%s" % (self.data_path, self.learning_text_resource['resPath'], tfile)
                    with open(tpath) as tfile_handle:
                        text = tfile_handle.read()
                    if self.rewrites is not None:
                        for from_str, to_str in self.rewrites:
                            text = text.replace(from_str, to_str)
                    tseqs = list(self.token_sequences_from_text(text))
                    for tseq in tseqs:
                        tseq.meta = { 'index': d3m_index, 'target': target }
                    yield "%s/%s" % (d3m_index, tfile), tseqs
                if cb is not None:
                    cb(row, tseqs)

    def export(self, fname, fields, cb):

        with open(fname, "w", newline='') as outh:
            csvwriter = csv.writer(outh)

            def write_row(row, tseqs):
                if tseqs is None:
                    csvwriter.writerow(row + fields)
                else:
                    added_fields = cb(list(tseqs))
                    print(added_fields)
                    csvwriter.writerow(row + [added_fields[f] for f in fields])

            for _ in self.token_sequences(write_row):
                pass


class CtakesSource(TokenSequenceSource):

    NAME = 'ctakes'

    def token_sequences(self):
        fname = self.source_name
        from ctakes import token_sequence_from_ctakes_json
        yield fname, token_sequence_from_ctakes_json(fname)


class PatentCSVSource(TokenSequenceSource):

    NAME = 'patents'

    def token_sequences(self):
        import csv
        fname = self.source_name
        with open(fname, "r") as fh:
            reader = csv.reader(fh)
            column = None
            for rowi, row in enumerate(reader):
                if column is None:
                    column = row.index('para')
                    if column < 0:
                        raise ValueError("No column named 'para' in %s" % row)
                    continue
                par = row[column]
                tseqs = self.token_sequences_from_text(par)
                yield "%s:%d" % (fname, rowi), tseqs


class MazdaSurveyCSVSource(TokenSequenceSource):

    NAME = 'mazda'

    def token_sequences(self):
        import csv
        fname = self.source_name
        with open(fname, "r") as fh:
            reader = csv.reader(fh)
            column = None
            for rowi, row in enumerate(reader):
                if column is None:
                    column = row.index('Comment')
                    if column < 0:
                        raise ValueError("No column named 'Comment' in %s" % row)
                    continue
                par = row[column]
                if not re.search('\S', par):
                    continue
                tseqs = self.token_sequences_from_text(par)
                yield "%s:%d" % (fname, rowi), tseqs


class DensoEAFSource(DirectorySource):

    NAME = 'denso'

    def token_sequences_from_file(self, target_file):
        import bs4
        print("Processing %s" % target_file)
        with open(target_file, "rb") as infile:
            self.soup = bs4.BeautifulSoup(infile, "lxml-xml")
        tiers = self.soup.find_all("TIER")
        tm = self.soup.find("TIME_ORDER")
        tiermap = dict([(x.attrs["TIER_ID"],x) for x in tiers])
        for ai, asoup in enumerate(tiermap["Dictation"].find_all("ALIGNABLE_ANNOTATION")):
            text = asoup.find("ANNOTATION_VALUE").text
            tseqs = self.token_sequences_from_text(text)
            yield ("%s:%d" % (target_file, ai), tseqs)


class TwitterReplySource(TokenSequenceSource):

    NAME = 'twitter_reply'

    def __init__(self, source_name, syntax_annotation):
        super().__init__(source_name, True, token_regex='\#?@?[a-z0-9_]+|\S', skip_initial_regex='\s+')

    def token_sequences(self):
        import json
        with open(self.source_name, "r") as fh:
            self.threads = json.load(fh)
        for i in range(0, len(self.threads)):
            thread = self.threads[i]
            initial = thread[0]
            initial_id = initial[0]
            reply = thread[1]
            reply_id = reply[0]
            if initial_id == reply_id:   # Skip self-replies
                continue
            initial_msg = self._strip_special_chars(initial[1])
            preface = "INITIAL:\n%s\n\nREPLY:\n" % initial_msg
            reply_msg = self._strip_special_chars(reply[1])
            full_text = preface + reply_msg
            tseqs = self.token_sequences_from_text(reply_msg)
            for tseq in tseqs:
                tseq.text = full_text
                tseq.offset += len(preface)
            yield i, tseqs

    def _strip_special_chars(self, txt):
        txt = [ c for c in txt if ord(c) < 65536 ]
        txt = ''.join(txt)
        return txt


class TableDataSource(TokenSequenceSource):

    NAME = 'tdata'

    def __init__(self, source_name, **kwargs):
        super().__init__(source_name, **kwargs)
        self.id_list_file = None
        if 'id_list_file' in kwargs:
            self.id_list_file = kwargs['id_list_file']

    def token_sequences(self):
        from tablecalc.table import TableDataTableSource
        dirname = self.source_name
        source = TableDataTableSource(dirname, id_list_file=self.id_list_file)
        for table in source:
            text = table.as_string()
            tseqs = []
            for cell in table:
                tseq = cell.content_token_sequence()
                tseq.text = text
                tseq.offset = cell.start_offs
                tseqs.append(tseq)
            yield table.address, tseqs


class AnnotatedTableDataSource(TokenSequenceSource):

    NAME = 'annotated_tdata'

    def token_sequences(self):
        from tablecalc.table import AnnotatedTableDataTableSource
        dirname = self.source_name
        ann_file = self.aux_file
        source = AnnotatedTableDataTableSource(dirname, ann_file)
        for table in source:
            text = table.as_string()
            tseqs = []
            for cell in table:
                tseq = cell.content_token_sequence()
                tseq.text = text
                tseq.offset = cell.start_offs
                tseqs.append(tseq)
            yield table.address, tseqs


class RPEDataSource(TokenSequenceSource):

    NAME = 'rpe'

    # Mode determines at what level token sequences are aggregated
    MODES = dict(
        DOC=0,
        PARA=1,
        SENT=2
    )

    def __init__(self, source_name, mode="DOC", step_annotation_file=None, **kwargs):
        super().__init__(source_name, **kwargs)
        self.mode = mode
        self.step_annotation_file = step_annotation_file
        self.use_doc_ids = None
        if step_annotation_file is not None:
            self.use_doc_ids = set()
            import jsonlines
            with jsonlines.open(step_annotation_file) as fh:
                for entry in fh:
                    self.use_doc_ids.add(entry['docid'])

    # Format of the file is is DOC, PARA, SENT, TEXT.
    # The first three fields are integer indexes
    def token_sequences(self):
        import csv
        fname = self.source_name
        doc_col = self.MODES[self.mode]
        with open(fname, "r") as fh:
            reader = csv.reader(fh)
            saw_header = False
            cur_doc = None
            tseqs = None
            doc_text = None
            for rowi, row in enumerate(reader):
                if not saw_header:
                    saw_header = True
                    continue
                doci = row[doc_col]
                text = row[3]
                if doci != cur_doc:
                    if cur_doc is not None and len(tseqs) > 0:
                        if self.use_doc_ids is None or cur_doc in self.use_doc_ids:
                            for tseq in tseqs:
                                tseq.text = doc_text
                            yield "%s:%s" % (fname, doci), tseqs
                    tseqs = []
                    doc_text = ''
                    cur_doc = doci
                tseq = self.token_sequence_from_text(text)
                tseq.offset = len(doc_text)
                tseqs.append(tseq)
                doc_text += text + "\n"
            if cur_doc is not None and len(tseqs) > 0:
                if self.use_doc_ids is None or cur_doc in self.use_doc_ids:
                    for tseq in tseqs:
                        tseq.text = doc_text
                    yield "%s:%s" % (fname, doci), tseqs


class ConvergenceAcceleratorDataSource(TokenSequenceSource):

    NAME = 'convacc'

    # Format of the file is is ID, DOCID, TEXT.
    def token_sequences(self):
        import csv
        fname = self.source_name
        with open(fname, "r") as fh:
            reader = csv.reader(fh)
            saw_header = False
            cur_doc = None
            tseqs = None
            doc_text = None
            for rowi, row in enumerate(reader):
                if not saw_header:
                    saw_header = True
                    continue
                doci = row[1]
                text = row[2]
                if doci != cur_doc:
                    if cur_doc is not None and len(tseqs) > 0:
                        for tseq in tseqs:
                            tseq.text = doc_text
                        yield "%s:%s" % (fname, doci), tseqs
                    tseqs = []
                    doc_text = ''
                    cur_doc = doci
                tseq = self.token_sequence_from_text(text)
                tseq.offset = len(doc_text)
                tseqs.append(tseq)
                doc_text += text + "\n"
            if cur_doc is not None and len(tseqs) > 0:
                for tseq in tseqs:
                    tseq.text = doc_text
                yield "%s:%s" % (fname, doci), tseqs


class RecipeDataSource(TokenSequenceSource):

    NAME = 'recipes'

    def token_sequences(self):
        import jsonlines
        fname = self.source_name
        for recipe in jsonlines.open(fname):
            name = recipe['id']
            steps = recipe['prepSteps']
            doc_text = ''
            tseqs = []
            for step in steps:
                tseq = self.token_sequence_from_text(step)
                tseq.offset = len(doc_text)
                tseqs.append(tseq)
                doc_text += step + "\n"
            for tseq in tseqs:
                tseq.text = doc_text
            yield name, tseqs


class EncounterFastFoodSource(CsvFileSource):

    NAME = 'encounter'

    def __init__(self, source_name, column_header='text', **kwargs):
        super().__init__(source_name, column_header, **kwargs)


PROJECT_SOURCES = dict(
    patents=PatentCSVSource,
    mazda=MazdaSurveyCSVSource,
    denso=DensoEAFSource,
    tdata=TableDataSource,
    annotated_tdata=AnnotatedTableDataSource,
    d3m=D3MTextSource,
    rpe=RPEDataSource,
    recipes=RecipeDataSource,
    encounter=EncounterFastFoodSource,
    convacc=ConvergenceAcceleratorDataSource
)

