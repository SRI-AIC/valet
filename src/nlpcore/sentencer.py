import re
from typing import List

from nlpcore.dbfutil import SimpleClass
from nlpcore.tokenizer import WordTokenizer, TokenSequence


class Sentencer(SimpleClass):

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self._default('blank_line_terminals', False)
        self._default('tokenizer', WordTokenizer())
        self._default('skip_initial_regex', '[^a-zA-Z]+')
        if self.blank_line_terminals:
            self.terminal = re.compile(r'[.?!;]\s|\n\s*\n')
        else:
            self.terminal = re.compile(r'[.?!;]+\"?\s')
        self.terminal_exceptions = re.compile(r'(Dr|Mr|Mrs|Ms).\s$')

    def sentences(self, text) -> List['Sentence']:

        ptr = [0, 0]
        result = []

        def sentence(ptr, result):
            start,end = ptr
            chunk = text[start:end]
            if re.search(self.terminal_exceptions, chunk):
                return
            prefix = re.match(self.skip_initial_regex, chunk)
            if prefix:
                start += prefix.end()
            if start < end:
                result.append(Sentence(text=text, start=start, end=end,
                                       tokenizer=self.tokenizer))
            ptr[0] = end

        for m in re.finditer(self.terminal, text):
            ptr[1] = m.end()
            sentence(ptr, result)

        ptr[1] = len(text)
        sentence(ptr, result)

        return result


# Not to be confused with Sentence in corpus/__init__.py.
class Sentence(SimpleClass):

    def sentence_text(self):
        text = self.text[self.start:self.end]
        text = re.sub(r'\s+$', '', text)
        return text

    def tokens(self) -> TokenSequence:
        return self.tokenizer.tokens(self.text, self.start, self.end - self.start)

    def __str__(self):
        return self.sentence_text()
