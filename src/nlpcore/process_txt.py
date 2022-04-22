import spacy
from spacy import displacy
from nlpcore.tokenizer import AnnotatedTokenSequence

nlp = None

def get_nlp():
    global nlp
    if nlp is None:
        nlp = spacy.load("en_core_web_sm")
    return nlp

def tokenize_file(fname):
    with open(fname) as infile:
        text = "".join(infile)
    return tokenize_document(text)

def tokenize_document(text):
    nlp = get_nlp()
    doc = nlp(text)
    sentences = []
    text = doc.text
    #displacy.serve(list(doc.sents),"dep")
    for sentence in doc.sents:
        sent = process_sentence(sentence)
        sent.text = text
        sentences += [sent]
    return sentences

def get_annotations(doc):
    annotations = {}
    annotations["pos"] = [x.tag_ for x in doc]
    annotations["tag"] = [x.pos_ for x in doc]
    annotations["lemma"] = [x.lemma_ for x in doc]
    return annotations


def get_dependencies(doc):
    return [ (x.i, x.head.i, x.dep_) for x in doc if x.i != x.head.i ]
    

def process_sentence(sent):
    #print("----\n[%s]\n%s" % (len(sent),str([(x.i,x) for x in sent])))
#    tokens = [x.norm_ for x in sent]
    tokens = [x.text for x in sent]
    offsets = [x.idx - sent.start_char for x in sent]
    lengths =[len(x.text) for x in sent]
    annotations = get_annotations(sent)
    phrase_annotations = {}
    #phrase_annotations["chunk"] = [(x.start,x.end,"noun") for x in sent.noun_chunks]
    depparse = [ (x.i - sent.start,x.head.i - sent.start,x.dep_) 
                 for x in sent if x.i != x.head.i]
    tseq = AnnotatedTokenSequence(tokens=tokens,
                                  offsets=offsets,
                                  lengths=lengths,
                                  annotations=annotations,
                                  offset=sent.start_char, 
                                  length=sent.start_char - sent.end_char)
    tseq.add_phrase_annotations("chunk",[(x.start - sent.start,x.end - sent.start,"noun") for x in sent.noun_chunks])
    tseq.add_dependencies(depparse)
    return tseq

def align_tokens(tseq, tok):
    offset = tok.idx
    length = len(tok.text)
    bnds = [ (tseq.offsets[i], tseq.offsets[i] + tseq.lengths[i]) for i in range(len(tseq)) ]
    return [i for i in range(len(bnds)) 
            if (bnds[i][0] <= offset and offset < bnds[i][1])
            or (offset <= bnds[i][0] and bnds[i][0] < offset + length)]

def construct_token_map(tseq, doc):
    return [ align_tokens(tseq, tok) for tok in doc ]

def process_token_sequence(tseq):
    """
    Process the text of the tseq in spacy, then assimilate the info back in the tseq, returning an
    AnnotatedTokenSequence.
    """
    text = tseq.tokenized_text()
    nlp = get_nlp()
    doc = nlp(text)
    tmap = construct_token_map(tseq, doc)
    annotations = get_annotations(doc)
    my_annotations = {}
    for type_, labels in annotations.items():
        mine = [ None for _ in tseq ]
        for i in range(len(labels)):
            for j in tmap[i]:
                mine[j] = labels[i]
        my_annotations[type_] = mine
    dependencies = get_dependencies(doc)
    my_deps = []
    # Always associate a dependency with the rightmost token
    for child, parent, type_ in dependencies:
        my_child = tmap[child]
        my_parent = tmap[parent]
        if len(my_child) == 0 or len(my_parent) == 0:
            continue
        my_deps.append((my_child[-1], my_parent[-1], type_))
    atseq = AnnotatedTokenSequence(text=tseq.text,
                                   offset=tseq.offset,
                                   length=tseq.length,
                                   tokens=tseq.tokens,
                                   offsets=tseq.offsets,
                                   lengths=tseq.lengths,
                                   annotations=my_annotations)
    atseq.add_dependencies(my_deps)
    return atseq
                                   
