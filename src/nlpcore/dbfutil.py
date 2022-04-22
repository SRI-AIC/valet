from __future__ import with_statement

from optparse import OptionParser
from xml.dom.minidom import parseString
from os import listdir, stat
from os.path import dirname, abspath, isdir, isfile
from inspect import getfile
import pickle
import sys
from random import sample
import xml.parsers.expat

expat_parser = None

def file_contents(fname):
    with open(fname, "rb") as f:
        return f.read().decode('utf8')

def file_lines(fname, trim=False):
    return list(each_file_line(fname, trim))

def each_file_line(fname, trim=False):
    with open(fname, "rb") as f:
        for line in f:
            if trim:
                line = line.strip()
            yield line

def file_size(fname):
    statinfo = stat(fname)
    return statinfo.st_size

def file_append(fname, *what):
    with open(fname, "ab") as f:
        for item in what:
            f.write(item)

def xml_escape(text):
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

def xml_unescape(text):
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&apos;', "'")
    text = text.replace('&quot;', '"')
    return text

def xml_unescape_expat(s):

    global expat_parser

    want_unicode = False
    if isinstance(s, unicode):
        s = s.encode("utf-8")
        want_unicode = True

    # the rest of this assumes that `s` is UTF-8
    list = []

    # create and initialize a parser object
    if expat_parser is None:
        expat_parser = xml.parsers.expat.ParserCreate("utf-8")
        expat_parser.buffer_text = True
        expat_parser.returns_unicode = want_unicode

    expat_parser.CharacterDataHandler = list.append

    # parse the data wrapped in a dummy element
    # (needed so the "document" is well-formed)
    expat_parser.Parse("<e>" + s + "</e>", 1)

    # join the extracted strings and return
    es = ""
    if want_unicode:
        es = u""
    return es.join(list)

def xml_pp(xml):
    "Pretty-prints the input XML string"
    return '\n'.join([ line for line in 
                       parseString(xml).toprettyxml(indent=' '*4).split('\n')
                       if line.strip() ])

def directory_files(d):
    return listdir(d)

def is_directory(d):
    return isdir(d)

def file_exists(f):
    return isfile(f)

def add_to_path(what):
    dir = dirname(sys.argv[0])
    newdir = dir + what
    if newdir not in sys.path:
        sys.path.append(newdir)

def script_directory():
    return dirname(abspath(sys.argv[0]))

def split_data(data, fraction):
    count = int(len(data) * fraction)
    samp = sample(data, count)
    sdict = dict([(x,1) for x in samp])
    nsamp = [x for x in data if not (x in sdict)]
    return (samp, nsamp)
    

class SimpleOptionParser(OptionParser):
    
    def parse_options(self, list):
        for item in list:
            try:
                code, label, options = item
            except:
                code, label = item
                options = {}
            if not 'action' in options:
                options['action'] = 'store'
            self.add_option('-' + code, '--' + label, dest=label, **options)
        return self.parse_args()


class SimpleClass(object):

    def __init__(self, **args):
        for arg, val in args.items():
            if (arg != '_defaults'):
                self.__dict__[arg] = val
        if '_defaults' in args:
            defaults = args['_defaults']
            for arg, val in defaults.items():
                self._default(arg, val)

    def _default(self, arg, val):
        if not arg in self.__dict__ or self.__dict__[arg] == None:
            self.__dict__[arg] = val

    def directory_files(self, dir):
        return directory_files(dir)

    def is_directory(self, dir):
        return is_directory(dir)

    def file_exists(self, f):
        return file_exists(f)

    def file_contents(self, fname):
        return file_contents(fname)

    def file_lines(self, fname):
        return file_lines(fname)

    def each_file_line(self, fname, trim=False):
        for line in each_file_line(fname, trim):
            yield line

    def xml_escape(self, text):
        return xml_escape(text)

    def xml_unescape(self, text):
        return xml_unescape(text)

    def xml_unescape_expat(self, text):
        return xml_unescape_expat(text)

    def xml_pp(self, text):
        return xml_pp(text)

    def copy(self):
        return pickle.loads(pickle.dumps(self, -1))

    def save(self, fname):
        with open(fname, "wb") as f:
            pickle.dump(self, f)

    def my_source_file(self):
        return getfile(self.__class__)

    def my_source_directory(self):
        return dirname(self.my_source_file())

    def split_data(self, data, fraction):
        return split_data(data, fraction)

    def load_cached_data(self, path, fn):
        try:
            with open(path + ".pickle", "rb") as f:
                return pickle.load(f)
        except IOError:
            thing = fn(path)
            with open(path + ".pickle", "wb") as f:
                pickle.dump(thing, f)
            return thing

    @staticmethod
    def load(fname):
        with open(fname, "rb") as f:
            return pickle.load(f)


class GenericException(Exception):
    def __init__(self, msg=None):
        self.msg = msg

    def __str__(self):
        return str(self.msg)
