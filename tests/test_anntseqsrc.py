import unittest
from nlpcore.anntseqsrc import ConllUStringSource


# From https://pypi.org/project/conllu/, slightly modified to actually be parseable.
# In the sentence (TokenList) data returned from parsing, 
# default_fields ('id', 'form', 'lemma', 'upos', 'xpos', 'feats', 'head', 'deprel', 'deps', 'misc')
conllu_text_adjusted = \
"""
# text = The quick brown fox jumps over the lazy dog.
1	The	the	DET	DT	Definite=Def|PronType=Art	4	det	_	_
2	quick	quick	ADJ	JJ	Degree=Pos	4	amod	_	_
3	brown	brown	ADJ	JJ	Degree=Pos	4	amod	_	_
4	fox	fox	NOUN	NN	Number=Sing	5	nsubj	_	_
5	jumps	jump	VERB	VBZ	Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin	0	root	_	_
6	over	over	ADP	IN	_	9	case	_	_
7	the	the	DET	DT	Definite=Def|PronType=Art	9	det	_	_
8	lazy	lazy	ADJ	JJ	Degree=Pos	9	amod	_	_
9	dog	dog	NOUN	NN	Number=Sing	5	nmod	_	SpaceAfter=No
10	.	.	PUNCT	.	_	5	punct	_	_
"""


class ConllUTestCase(unittest.TestCase):
    def test_conll_tseqsrc(self):
        src = ConllUStringSource(conllu_text_adjusted)
        expected = [['The', 'quick', 'brown', 'fox', 'jumps', 'over', 'the', 'lazy', 'dog', '.']]
        for source, tseqs in src.token_sequences():
            self.assertEqual("0", source)
            actual = [list(tseq) for tseq in tseqs]
            self.assertEqual(expected, actual)
            tseq = tseqs[0]
            # print(tseq.dependency_tree_string())
            self.assertEqual([(4, "nsubj")], tseq.get_up_dependencies(3))

if __name__ == '__main__':
    unittest.main()
