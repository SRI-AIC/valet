import re
import plac
from importlib import import_module
from tkinter import YES, BOTH

from nlpcore.tseqsrc import TokenSequenceSource
from valetrules.gui.app import Application


if __name__ == "__main__":

    # Our standard boilerplate for initing logging in any script.
    import logging.config
    from nlpcore.logging import no_datetime_config
    logging.config.dictConfig(no_datetime_config)

    # Examples of changing log level for (potentially hierarchies of) logger(s).
    # logging.getLogger("valetrules.gui.app.<module>").setLevel("DEBUG")
    # logging.getLogger("valetrules.gui.spooler.<module>").setLevel("DEBUG")
    # logging.getLogger("valetrules.gui.textpane.<module>").setLevel("DEBUG")

    from nlpcore import anntseqsrc
    anntseqsrc.add_to_sources()
    from nlpcore.projectsrc import PROJECT_SOURCES
    for label, src in PROJECT_SOURCES.items():
        TokenSequenceSource.add_token_sequence_source(label, src)
    source_types = TokenSequenceSource.available_type_labels()

    def main(pattern_file: ("File containing definitions", "positional"),
             source_file: ("Name of the text source", "positional"),
             source_data_type: ("Type of the input", "option", "y", str) = "text",
             aux_file: ("Auxiliary file", "option", "a", str) = None,
             added_import: ("Additional import", "option", "i", str) = None,
             project_source: ("Name of a project-specific class to serve as source", "option", "p", str) = None,
             nlp_engine: ("NLP module to use", "option", "x", str) = 'stanza',
             term_expansion: ("Path to term expansion data; if available", "option", "t", str) = None,
             embedding_file: ("Path to a file containing word embeddings", "option", "b", str) = None,
             source_arguments: ("Extra args to provide to the token sequence source", "option", "g", str) = None,
             # positive_label: ("String used to represent positive class", "option", "p", str) = None,
             rewrites: ("Standing text transformations", "option", "r", str) = None,
             scale_height: ("Used to reduce the vertical height of the window", "option", "v", float) = None,
             font_size: ("Font size to use in the document and pattern panels", "option", "f", int) = None):
        if added_import is not None:
            import_module(added_import)
        rewrite_list = []
        if rewrites is not None:
            for rewrite in re.split(r'/', rewrites):
                m = re.match(r'(.*?):(.*)', rewrite)
                if not m:
                    raise ValueError("Malformed rewrite: %s" % rewrite)
                rewrite_list.append((m.group(1), m.group(2)))

        if nlp_engine == 'off':
            nlp_engine = None
        aux_args = {}
        if source_arguments is not None:
            for m in re.finditer(r'(\w+)=(\S+)', source_arguments):
                aux_args[m.group(1)] = m.group(2)
        if project_source is None:
            data_source = TokenSequenceSource.source_for_type(source_data_type, source_file,
                                                              aux_file=aux_file, nlp_engine=nlp_engine,
                                                              **aux_args)
        else:
            from nlpcore import projectsrc
            source_class = projectsrc.PROJECT_SOURCES[project_source]
            data_source = source_class(source_file, aux_file=aux_file, nlp_engine=nlp_engine, **aux_args)
        app = Application(pattern_file, data_source, term_expansion=term_expansion,
                          font_size=font_size, embedding_file=embedding_file)
        app.pack(fill=BOTH, expand=YES)
        app.master.title("Valet Rules GUI")
        app.mainloop() 

    plac.call(main)
