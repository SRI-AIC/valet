from abc import ABC, abstractmethod
from typing import Optional, Union, TYPE_CHECKING

from nlpcore.dbfutil import SimpleClass

from .extractor import Extractor
if TYPE_CHECKING:
    from .manager import VRManager
    from .regex import Regex


# Expression is a base class retrofitted into existing expression types
# like TokenTestExpression, RegexExpression, CoordinatorExpression,
# and FrameExpression.
#
# The main purpose of the class is to clarify the methods supported
# by all expressions, and their common semantics.
# Also, to help tools like PyCharm NOT give compiler warnings about
# "unresolved attribute reference" as it does when an attribute is set
# by SimpleClass rather than by (say) self.expr = expr in the ctor.
#
# expression.Expression is not nearly as central as extractor.Extractor
# (see), and Expression's exist pretty ephemerally, so defining Expression
# here is not nearly as useful as defining Extractor.
# But maybe still nice to have it, especially to avoid warnings about
# unresolved attribute references to common attributes, without having
# to repeat initialization code in subclass ctors.


class Expression(SimpleClass, ABC):
    """
    A object used to create an Extractor (or similar) object from
    the RHS expression of a Valet pattern.
    """

    # The manager is Optional['VRManager'], because RegexExpression's
    # can perform some of their methods without it, and some Extractor's
    # whose ctors it is passed to can work without a manager (eg if they
    # don't reference other named extractors).
    # It seems best to declare it Optional (but not default to None)
    # rather than not do so, or try to add new levels to the
    # inheritance hierarchy.
    def __init__(self, expr: str, manager: Optional['VRManager'], **kwargs):
        super().__init__(**kwargs)
        self.expr = expr
        self.manager = manager

    # Most Expression's return Extractor, but RegexExpression's
    # are a little different; they return Regex's (which are not Extractor's)
    # from parse().
    @abstractmethod
    def parse(self) -> Union[Extractor, 'Regex']:
        pass
