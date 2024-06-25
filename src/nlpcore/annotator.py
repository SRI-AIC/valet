from enum import Enum
import logging
import re


_logger = logging.getLogger(f"{__name__}.<module>")


class Requirement(Enum):
    POS = 1
    LEMMA = 2
    NER = 3
    DEPPARSE = 4
    EMBEDDINGS = 5
    # SRL = 6  # not used


class NLPAnnotator(object):
    """Base class for specific annotators."""

    # These are not so much requirements, more like capabilities,
    # some, all, or none of which may be specified in self.requirements.
    NLP_REQUIREMENTS = { Requirement.DEPPARSE, Requirement.LEMMA, Requirement.NER, Requirement.POS }

    def __init__(self):
        self.nlp = None  # callable for annotator
        self.nlp_result = None  # result from annotator
        self.token_map = None  # map from token_key to align_token output
        # It looks like annotators' self.requirements value only ever adds
        # requirements from tseqs' tokenizer's requirements; it does not
        # subtract requirements.
        # I presume this is to get one sort of efficiency whereby we don't
        # need to reconfigure the NLP "pipeline" (self.nlp callable) each time
        # nlp_tseq is applied to a tseq with possibly changed requirements;
        # instead, we only need to do so when new requirements are added.
        # This mostly appears to apply to stanza.
        self.requirements = set()

    def annotate(self, tseq):
        """Apply the specific annotator to the tseq,
        then collect the information into a uniformly accessible form."""
        # The tseq doesn't require NLP annotation (or at least any we can
        # provide).
        if len(tseq.tokenizer.requirements & self.NLP_REQUIREMENTS) == 0:
            return
        self.nlp_tseq(tseq)
        self.align_tokens(tseq)
        self.add_token_annotations(tseq)
        self.add_dependencies(tseq)

    # A tseq reaching here is typically a single sentence (as determined
    # by our sentencer, although the NLP engine might think otherwise).
    def nlp_tseq(self, tseq):
        """Apply NLP to the tseq, storing results internally."""
        raise NotImplementedError()

    # Note that it's possible that the annotator may think there is more than
    # one sentence in the tseq, even if our Sentencer has already been applied,
    # hence the sentence index.
    # That's similar to how the annotator may tokenize differently than we do,
    # hence the need for alignment methods in this class.
    def tokens(self):
        """Generates tuples of zero-based annotator sentence index and
        annotator-specific token."""
        raise NotImplementedError()

    def token_key(self, si, token):
        """Given annotator sentence index 'si' and annotator-specific token,
        as from tokens() method, return tuple of si and annotator token index
        relative to start of tseq. Used as key in token_map dict."""
        raise NotImplementedError()

    def token_offsets(self, token):
        """Given annotator-specific token, return zero-based char offset
        and length relative to start of tseq."""
        raise NotImplementedError()

    # For tag, see add_token_annotations.
    def token_info(self, token):
        """Given annotator-specific token, return tag, pos, lemma, ner values."""
        raise NotImplementedError()

    def dependency_info(self, si, token):
        """
        Given annotator sentence index 'si' and annotator-specific token,
        return tuple (child, parent, deptype).
        Child and parent are similar to (or are?) token_keys.
        Deptype is annotator-specific.
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
            #     _logger.debug("Info: align_token annotator token '%s' corresponds to no nlpcore tokens" % token)
            # if len(result) > 1:
            #     _logger.debug("Info: align_token annotator token '%s' corresponds to multiple nlpcore tokens: %s" % (token, result))
            return result

        self.token_map = dict((self.token_key(si, token), align_token(token)) for si, token in self.tokens())

    def add_token_annotations(self, tseq):
        """Add pos, tag, lemma, ner info from the NLP result to the tseq.
        Uses the results from calling token_info() on each token
        from tokens() to set info for the pos, tag, lemma, and ner
        annotation "layers". (Lemmas are lowercased.)"""
        pos = [None for _ in tseq]
        tag = [None for _ in tseq]
        lemma = [None for _ in tseq]
        ner = [None for _ in tseq]
        for toki, tokinfo in enumerate(self.tokens()):
            si, tok = tokinfo
            key = self.token_key(si, tok)
            tag_, pos_, lemma_, ner_ = self.token_info(tok)
            for i in self.token_map[key]:
                # TODO? This should probably be done in the Spacy and Stanza
                # annotators, not in the base annotator.
                # tag and pos is the terminology used by spacy.
                # In one case, token was "Village", pos_ and tag_
                # from stanza were PROPN and NNP, from spacy NOUN and NN.
                # The point of interchanging here is simply that we want
                # to call NNP or NN "pos" in the annotation "layer"
                # and in the Valet rule language.
                pos[i] = tag_  # note we interchange tag and pos here
                tag[i] = pos_
                # This is in pursuit of case-insensitivity, but requires
                # that Valet lemma rules use lower case.
                lemma[i] = lemma_.lower()
                ner[i] = ner_
        # TODO? FWIW, this results in '-' values for ner when none of these NLP
        # operations has been run (at least with Spacy), since in that case
        # ner_='-' comes back from self.token_info(tok) while tag_=pos_=lemma_='',
        # and any() returns true for truthy values like '-'.
        if any(x for x in pos if x is not None):
            tseq.add_annotations('pos', pos)
        if any(x for x in tag if x is not None):
            tseq.add_annotations('tag', tag)
        if any(x for x in lemma if x is not None):
            tseq.add_annotations('lemma', lemma)
        if any(x for x in ner if x is not None):
            tseq.add_annotations('ner', ner)

    def add_dependencies(self, tseq):
        """Add dependency info from the NLP result to the tseq.
        Uses the results from calling dependency_info() on each token
        from tokens() to call the tseq's add_dependencies() method."""
        if Requirement.DEPPARSE not in tseq.tokenizer.requirements:
            return
        deps = []
        for si, tok in self.tokens():
            dep_info = self.dependency_info(si, tok)
            if dep_info is None:
                continue
            # child and parent are (si, toki) tuples
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


class SpacyAnnotator(NLPAnnotator):

    # Map from requirement enum value to strings used to configure spacy.
    COMPONENT_MAP = {
        Requirement.DEPPARSE: "parser",
        Requirement.LEMMA: "lemmatizer",
        Requirement.NER: "ner",
        Requirement.POS: "tagger"
    }

    # We need to manually expand components to specify components depended on.
    COMPONENT_DEPENDENCIES = {
        "lemmatizer": ['tagger'],
    }

    def __init__(self):
        super().__init__()
        import spacy
        print(f"Spacy code version is {spacy.__version__}")
        self.nlp = spacy.load("en_core_web_sm")
        print(f"Spacy model version is {self.nlp.meta['version']}")

    def nlp_tseq(self, tseq):
        """Apply NLP to the tseq, storing results internally."""

        # Update self.requirements with new reqs from tseq's tokenizer.
        tseq_nlp_reqs = self.NLP_REQUIREMENTS & tseq.tokenizer.requirements
        new_reqs = tseq_nlp_reqs - self.requirements
        if tseq_nlp_reqs != self.requirements:
            self.requirements |= new_reqs
            # _logger.debug("Updating NLP requirements: %s" % [self.COMPONENT_MAP[r] for r in self.requirements])

        # Configure and run pipeline based on requirements.
        processors = self._processors()
        # _logger.debug("processors =", processors)
        not_needed = [s for r, s in self.COMPONENT_MAP.items()
                      if s not in processors]  # was r not in self.requirements
        # (Not sure why there would be pipe names not known to self.nlp.)
        not_needed = [c for c in not_needed if c in self.nlp.pipe_names]
        with self.nlp.select_pipes(disable=not_needed):
            self.nlp_result = self.nlp(tseq.get_normalized_text())

    # Copied from StanzaAnnotator.
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
        """Generates tuples of zero-based annotator sentence index and
        annotator-specific token."""
        # The sents may or may not be present, depending on which components
        # are enabled.
        # If not present, we treat the doc (tseq) as a single sentence.
        # In typical usage, where we use our Sentencer, it already is
        # a single sentence. Even in that case, though, the NLPAnnotator
        # might treat it as multiple sentences.
        try:
            for si, sentence in enumerate(self.nlp_result.sents):
                for token in sentence:
                    yield si, token
        except ValueError:
            for token in self.nlp_result:
                yield 0, token

    def token_key(self, si, token):
        """Given annotator sentence index 'si' and annotator-specific token,
        as from tokens() method, return tuple of si and annotator token index
        relative to start of tseq. Used as key in token_map dict."""
        return si, int(token.i)

    def token_offsets(self, token):
        """Given annotator-specific token, return zero-based char offset
        and length relative to start of tseq."""
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
        Given annotator sentence index 'si' and annotator-specific token,
        return tuple (child, parent, deptype).
        Child and parent are similar to (or are?) token_keys.
        Deptype is annotator-specific.
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

    # Map from requirement enum value to strings used to configure stanza.
    COMPONENT_MAP = {
        Requirement.DEPPARSE: "depparse",
        Requirement.LEMMA: "lemma",
        Requirement.NER: "ner",
        Requirement.POS: "pos"
    }

    # We need to manually expand components to specify components depended on.
    COMPONENT_DEPENDENCIES = {
        "depparse": ['lemma', 'pos'],
        "pos": ['tokenize'],
        "lemma": ['tokenize'],
        "ner": ['tokenize']
    }

    def __init__(self):
        super().__init__()
        self.nlp = None

    def nlp_tseq(self, tseq):
        """Apply NLP to the tseq, storing results internally."""

        # Update self.requirements with any new reqs from tseq's tokenizer.
        # Reconfigure pipeline with updated requirements.
        tseq_nlp_reqs = self.NLP_REQUIREMENTS & tseq.tokenizer.requirements
        new_reqs = tseq_nlp_reqs - self.requirements
        if tseq_nlp_reqs != self.requirements:
            self.requirements |= new_reqs
            # _logger.debug("Updating NLP requirements: %s" % [self.COMPONENT_MAP[r] for r in self.requirements])
            import stanza
            processors = ",".join(self._processors())
            self.nlp = stanza.Pipeline('en', use_gpu=False, verbose=True, processors=processors)
        # Run pipeline.
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
        """Generates tuples of zero-based annotator sentence index and
        annotator-specific token."""
        for si, sentence in enumerate(self.doc.sentences):
            for word in sentence.words:
                yield si, word

    def token_key(self, si, token):
        """Given annotator sentence index 'si' and annotator-specific token,
        as from tokens() method, return tuple of si and annotator token index
        relative to start of tseq. Used as key in token_map dict."""
        return si, int(token.id)

    def token_offsets(self, token):
        """Given annotator-specific token, return zero-based char offset
        and length relative to start of tseq."""
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
        Given annotator sentence index 'si' and annotator-specific token,
        return tuple (child, parent, deptype).
        Child and parent are similar to (or are?) token_keys.
        Deptype is annotator-specific.
        """
        try:
            child = int(token.id)
            parent = int(token.head)
            if parent == 0:
                parent = -1 # Root dependency
            deptype = token.deprel
            #if deptype == 'root':
            #    _logger.debug("Root:", token)
            # _logger.debug("Dep %s, %s --> %s" % (token.text, self.doc.sentences[si].words[parent-1].text, deptype))
            return (si, child), (si, parent), deptype
        except AttributeError:
            return None


class AllenSrlSpacyAnnotator(SpacyAnnotator):

    # Not used. We assume that if you use nlp_engine=allensrl,
    # you want the SRL processing.
    # COMPONENT_MAP = {
    #     Requirement.DEPPARSE: "parser",
    #     Requirement.LEMMA: "lemmatizer",
    #     Requirement.NER: "ner",
    #     Requirement.POS: "tagger",
    #     Requirement.SRL: "srl"
    # }

    def __init__(self):
        super().__init__()
        from allennlp.predictors.predictor import Predictor
        allensrl_model_path = "https://storage.googleapis.com/allennlp-public-models/structured-prediction-srl-bert.2020.12.15.tar.gz"
        self.allensrl = Predictor.from_path(allensrl_model_path)
        # Probably not needed, but helps compiler code checking.
        self.allensrl_docs = list()
        self.allensrl_deps = list()
        self.allensrl_tags = dict()


    def nlp_tseq(self, tseq):
        """Apply NLP to the tseq, storing results internally."""
        super().nlp_tseq(tseq)
        self.allensrl_docs = list()  # re-init these 3
        self.allensrl_deps = list()
        self.allensrl_tags = dict()
        for si, sentence in enumerate(self.nlp_result.sents):
            sentence_as_toklist = [tok.text for tok in sentence]
            result = self.allensrl.predict_tokenized(sentence_as_toklist)
            self.allensrl_docs.append(result)
            verbs = result["verbs"]
            if verbs:
                for verb in verbs:
                    tags = verb["tags"]
                    if "B-V" not in tags:
                        print("WARNING: Skipping allennlp SRL output where tags did not match verb for sentence '" +
                              ' '.join(sentence_as_toklist) + "'")
                        continue
#                        raise GenericException(msg="allensrl tags did not match verb output")
                    verb_i = tags.index("B-V")  # allen uses a BIO tag scheme
#                    if len(sentence) != len(tags):
#                        raise GenericException(msg="Should not happen")
                    parent = sentence[verb_i].i
                    # when i == verb_i we will get an (intended) self-link
                    for i in range(len(tags)):
                        if tags[i] != "O":
                            child = sentence[i].i
                            deptype = tags[i][2:]  # drop "B-" or "I-"
                            self.allensrl_deps.append((si, child, parent, deptype))
                            if child not in self.allensrl_tags:
                                self.allensrl_tags[child] = list()
                            self.allensrl_tags[child].append(deptype)

    def add_token_annotations(self, tseq):
        super().add_token_annotations(tseq)
        srl = [None for _ in tseq]
        for toki, tokinfo in enumerate(self.tokens()):
            si, tok = tokinfo
            key = self.token_key(si, tok)
            srl_ = self.token_info_srl(tok)
            for i in self.token_map[key]:
                srl[i] = srl_
        if any(x for x in srl if x is not None):
            tseq.add_annotations('srl', srl)

    def add_dependencies(self, tseq):
        super().add_dependencies(tseq)
        # TODO: Following code is copied from base class, except for dependency_info_srl
        # Rework this to avoid the copied code, probably much of it unnecessary
        deps = []
        for si, tok in self.tokens():
            dep_infos = self.dependency_info_srl(si, tok)
            for dep_info in dep_infos:
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

    def token_info_srl(self, token):
        if token.i in self.allensrl_tags:
            srl = set(self.allensrl_tags[token.i])
        else:
            srl = None
        return srl

    def dependency_info_srl(self, si, token):
        result = list()
        for srlsi, child, parent, deptype in self.allensrl_deps:
            if child == token.i and si == srlsi:
                result.append(((srlsi, child), (srlsi, parent), deptype))
        return result
