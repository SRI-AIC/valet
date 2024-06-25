"""
Provides two predefined logging configurations default_config and
no_datetime_config, with a log level determined by an env vbl
LOG_LEVEL (default INFO).
Does not set the logging configuration, as that should be set by higher
level code such as scripts, not by a lower level module such as this.
IMPORTANT: Both predefined configurations set disable_existing_loggers=False,
which is generally what you want.

The normal way to initialize logging using this is as follows:
    import logging.config
    from nlpcore.logging import no_datetime_config
    logging.config.dictConfig(no_datetime_config)
This should normally be done in script code, not library code.
"""

from copy import deepcopy
import os


log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

# The logging mechanism probably precedes the wide use of classes,
# so we just see method names from funcName here (name is logger name).
# I added add_logger below to aid in defining a logger for a class and
# including the class name in the logger name.
default_format = '%(asctime)s %(levelname)-8s %(name)s %(funcName)s L%(lineno)d %(message)s'
no_datetime_format = '%(levelname)-8s %(name)s %(funcName)s L%(lineno)d %(message)s'

default_config = dict(
    version=1,
    # Setting this to False is very important.
    # But if you really don't want it, change it after importing this variable,
    # ideally by making a copy as done below to make no_datetime_config.
    disable_existing_loggers=False,
    formatters={
        'f': {'format': default_format}
    },
    handlers={
        'h': {'class': 'logging.StreamHandler',
              'formatter': 'f',
             }
    },
    root={
        'handlers': ['h'],
        'level': log_level,
    },
)

# The main motivation for this is to make it feasible to compare
# log files from multiple runs to check whether and how the logging
# output differs.
no_datetime_config = deepcopy(default_config)
no_datetime_config['formatters']['f']['format'] = no_datetime_format
