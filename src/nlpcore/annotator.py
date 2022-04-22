from enum import Enum
import re


class Requirement(Enum):
    POS = 1
    LEMMA = 2
    NER = 3
    DEPPARSE = 4
    EMBEDDINGS = 5


class NLPAnnotator(object):
    """Base class for specific annotators."""

    NLP_REQUIREMENTS = { Requirement.DEPPARSE, Requirement.LEMMA, Requirement.NER, Requirement.POS }

    def __init__(self):
        self.nlp = None  # callable for annotator
        self.doc = None  # result from annotator
        self.token_map = None  # map from token_key to align_token output
        self.requirements = set()

    def annotate(self, tseq):
        """Apply the specific annotator to the tseq,
        then collect the information into a uniformly accessible form."""
        # The tseq doesn't require NLP annotation
        if len(tseq.parent.requirements & self.NLP_REQUIREMENTS) == 0:
            return
        self.nlp_doc(tseq)
        self.align_tokens(tseq)
        self.add_token_annotations(tseq)
        self.add_dependencies(tseq)
        tseq.nlp_annotated = True

    def nlp_doc(self, tseq):
        """Apply NLP to the tseq, storing results internally."""
        raise NotImplementedError()

    def tokens(self):
        """Generates tuples of zero-based sentence index and annotator-specific token."""
        raise NotImplementedError()

    def token_key(self, si, token):
        """Used as key in token_map dict."""
        raise NotImplementedError()

    def token_offsets(self, token):
        """Return zero-based char offset and length."""
        raise NotImplementedError()

    # For tag, see add_token_annotations.
    def token_info(self, token):
        """Given annotator-specific token, return tag, pos, lemma, ner values."""
        raise NotImplementedError()

    def dependency_info(self, si, token):
        """
        Return child, parent, deptype. Child and parent are similar to
        (or are?) token keys. Deptype is annotator-specific.
        """
        raise NotImplementedError()

    def align_tokens(self, tseq):
        """
        Since the tokenization used by the annotator can differ
        from the tokenization we use ourselves, align the two.
        Set self.token_map to dict mapping annotator token_keys to
        lists of our zero-based token indices.
        """
        # TODO? Check for problematic alignments, especially one of our
        # tokens corresponding to more than one annotator token, since then
        # only the info (pos, lemma, etc) from one of those annotator tokens
        # will be preserved in our token.
        # I presume this happens rarely but occasionally.

        def align_token(token):
            """Return list of zero-based indices of those of our tokens
            that correspond to this annotator token."""
            offset, length = self.token_offsets(token)
            if hasattr(tseq, 'normalized_offsets'):
                offsets = tseq.normalized_offsets
            else:
                offsets = tseq.offsets
            bounds = [(offsets[i], offsets[i] + tseq.lengths[i])
                      for i in range(len(tseq))]
            result = [ i for i in range(len(bounds))
                       if bounds[i][0] <= offset < bounds[i][1] or offset <= bounds[i][0] < offset + length ]
            # For debug if needed.
            # if len(result) == 0:
            #     print("Info: align_token annotator token '%s' corresponds to no nlpcore tokens" % token)
            # if len(result) > 1:
            #     print("Info: align_token annotator token '%s' corresponds to multiple nlpcore tokens: %s" % (token, result))
            return result

        self.token_map = dict((self.token_key(si, token), align_token(token)) for si, token in self.tokens())

    def add_token_annotations(self, tseq):
        """Add pos, tag, lemma, ner info from the NLP result to the tseq."""
        pos = [None for _ in tseq]
        tag = [None for _ in tseq]
        lemma = [None for _ in tseq]
        ner = [None for _ in tseq]
        for toki, tokinfo in enumerate(self.tokens()):
            si, tok = tokinfo
            key = self.token_key(si, tok)
            tag_, pos_, lemma_, ner_ = self.token_info(tok)
            for i in self.token_map[key]:
                # In one case, token was "Village", pos_ and tag_
                # from stanza were PROPN and NNP, from spacy NOUN and NN.
                # Not sure if that is standard NLP terminology;
                # if not, we could just change the variable names
                # instead of doing this interchange.
                # The ultimate point is simply that we want to call NNP and NN
                # "pos" in the annotations.
                pos[i] = tag_
                tag[i] = pos_
                lemma[i] = lemma_
                ner[i] = ner_
        if any(x for x in pos if x is not None):
            tseq.add_annotations('pos', pos)
        if any(x for x in tag if x is not None):
            tseq.add_annotations('tag', tag)
        if any(x for x in lemma if x is not None):
            tseq.add_annotations('lemma', lemma)
        if any(x for x in ner if x is not None):
            tseq.add_annotations('ner', ner)

    def add_dependencies(self, tseq):
        """Add dependency info from the NLP result to the tseq."""
        if Requirement.DEPPARSE not in tseq.parent.requirements:
            return
        deps = []
        for si, tok in self.tokens():
            dep_info = self.dependency_info(si, tok)
            if dep_info is None:
                continue
            child, parent, deptype = dep_info
            if child[1] == -1:  # Root
                child_indexes = [-1]
            else:
                child_indexes = self.token_map[child]
            if parent[1] == -1:  # Root
                parent_indexes = [-1]
            else:
                parent_indexes = self.token_map[parent]
            if len(child_indexes) == 0 or len(parent_indexes) == 0:
                continue
            # Always associate a dependency with the rightmost token
            # (when one annotator token maps to more than one of our tokens).
            deps.append((child_indexes[-1], parent_indexes[-1], deptype))
        tseq.add_dependencies(deps)

### Continue here
### Need to configure pipeline based on requirements
class SpacyAnnotator(NLPAnnotator):

    COMPONENT_MAP = {
        Requirement.DEPPARSE: "parser",
        Requirement.LEMMA: "lemmatizer",
        Requirement.NER: "ner",
        Requirement.POS: "tagger"
    }

    def __init__(self):
        super().__init__()
        import spacy
        self.nlp = spacy.load("en_core_web_sm")

    def nlp_doc(self, tseq):
        """Apply NLP to the tseq, storing results internally."""
        tseq_nlp_reqs = self.NLP_REQUIREMENTS & tseq.parent.requirements
        new_reqs = tseq_nlp_reqs - self.requirements
        if tseq_nlp_reqs != self.requirements:
            self.requirements |= new_reqs
            # TODO? I suggest we convert nlpcore and valet to use python 
            # logging, so we don't have to hardcode all-or nothing decisions 
            # such as whether to comment this out or not.
            # print("Updating NLP requirements: %s" % [self.COMPONENT_MAP[r] for r in self.requirements])
        not_needed = [v for k, v in self.COMPONENT_MAP.items() if k not in self.requirements]
        not_needed = [c for c in not_needed if c in self.nlp.pipe_names]
        with self.nlp.select_pipes(disable=not_needed):
            self.doc = self.nlp(tseq.get_normalized_text())

    def tokens(self):
        """Generates tuples of zero-based sentence index and annotator-specific token."""
        # The sents may or may not be present, depending on which components are enabled.
        # If not present, we pretend that the doc consists of a single large sentence.
        try:
            for si, sentence in enumerate(self.doc.sents):
                for token in sentence:
                    yield si, token
        except ValueError:
            for token in self.doc:
                yield 0, token

    def token_key(self, si, token):
        """Used as key in token_map dict."""
        return si, int(token.i)

    def token_offsets(self, token):
        """Given annotator-specific token, return zero-based char offset and length."""
        return token.idx, len(token.text)

    def token_info(self, token):
        """Given annotator-specific token, return tag, pos, lemma, ner values."""
        try:
            if token.ent_iob_ == 'O':
                ner = token.ent_iob_
            else:
                ner = "%s-%s" % (token.ent_iob_, token.ent_type_)
        except AttributeError:
            ner = None
        try:
            tag = token.tag_
            pos = token.pos_
        except AttributeError:
            tag = None
            pos = None
        try:
            lemma = token.lemma_
        except AttributeError:
            lemma = None
        return tag, pos, lemma, ner

    def dependency_info(self, si, token):
        """
        Return child, parent, deptype. Child and parent are similar to
        (or are?) token_keys. Deptype is annotator-specific.
        """
        try:
            child = int(token.i)
            parent = int(token.head.i)
            if child == parent:
                parent = -1  # root dependency
            deptype = token.dep_
        except AttributeError:
            return None
        return (si, child), (si, parent), deptype


class StanzaAnnotator(NLPAnnotator):

    COMPONENT_MAP = {
        Requirement.DEPPARSE: "depparse",
        Requirement.LEMMA: "lemma",
        Requirement.NER: "ner",
        Requirement.POS: "pos"
    }

    COMPONENT_DEPENDENCIES = {
        "depparse": ['lemma', 'pos'],
        "pos": ['tokenize'],
        "lemma": ['tokenize'],
        "ner": ['tokenize']
    }

    def __init__(self):
        super().__init__()
        self.nlp = None

    def nlp_doc(self, tseq):
        """Apply NLP to the tseq, storing results internally."""
        tseq_nlp_reqs = self.NLP_REQUIREMENTS & tseq.parent.requirements
        new_reqs = tseq_nlp_reqs - self.requirements
        if tseq_nlp_reqs != self.requirements:
            self.requirements |= new_reqs
            # print("Updating NLP requirements: %s" % [self.COMPONENT_MAP[r] for r in self.requirements])
            import stanza
            processors = ",".join(self._processors())
            self.nlp = stanza.Pipeline('en', use_gpu=False, verbose=True, processors=processors)
        self.doc = self.nlp(tseq.get_normalized_text())

    def _processors(self):

        def dependencies(reqs):
            for req in reqs:
                try:
                    deps = self.COMPONENT_DEPENDENCIES[req]
                except KeyError:
                    return
                for dep in deps:
                    yield dep
                    for odep in dependencies([dep]):
                        yield odep

        reqs = [self.COMPONENT_MAP[r] for r in self.requirements]
        deps = reqs + list(dependencies(reqs))
        processors = []
        for dep in reversed(deps):
            if dep not in processors:
                processors.append(dep)
        return processors

    def tokens(self):
        """Generates tuples of zero-based sentence index and annotator-specific token."""
        for si, sentence in enumerate(self.doc.sentences):
            for word in sentence.words:
                yield si, word

    def token_key(self, si, token):
        """Used as key in token_map dict."""
        return si, int(token.id)

    def token_offsets(self, token):
        """Given annotator-specific token, return zero-based char offset and length."""
        offset = token.start_char
        end_offset = token.end_char
        return offset, end_offset - offset

    # Stanza changed its token representation in a way that broke this code
    # at some point around 6/2021.
    def token_offsets_old(self, token):
        misc = token.misc
        m = re.search(r'start_char=(\d+)', misc)
        offset = int(m.group(1))
        m = re.search(r'end_char=(\d+)', misc)
        end_offset = int(m.group(1))
        return offset, end_offset - offset

    def token_info(self, token):
        """Given annotator-specific token, return tag, pos, lemma, ner values."""
        try:
            tag = token.xpos
            pos = token.pos
        except AttributeError:
            tag = None
            pos = None
        try:
            lemma = token.lemma
        except AttributeError:
            lemma = None
        try:
            ner = token.parent.ner
        except AttributeError:
            ner = None
        return tag, pos, lemma, ner

    def dependency_info(self, si, token):
        """
        Return child, parent, deptype. Child and parent are similar to
        (or are?) token_keys. Deptype is annotator-specific.
        """
        try:
            child = int(token.id)
            parent = int(token.head)
            if parent == 0:
                parent = -1 # Root dependency
            deptype = token.deprel
            #if deptype == 'root':
            #    print("Root:", token)
            # print("Dep %s, %s --> %s" % (token.text, self.doc.sentences[si].words[parent-1].text, deptype))
            return (si, child), (si, parent), deptype
        except AttributeError:
            return None
