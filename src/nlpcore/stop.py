import re

# Stolen from NLTK's stopword list, found here:  https://gist.github.com/sebleier/554280
STOPWORDS = """
i
me
my
myself
we
our
ours
ourselves
you
your
yours
yourself
yourselves
he
him
his
himself
she
her
hers
herself
it
its
itself
they
them
their
theirs
themselves
what
which
who
whom
this
that
these
those
am
is
are
was
were
be
been
being
have
has
had
having
do
does
did
doing
a
an
the
and
but
if
or
because
as
until
while
of
at
by
for
with
about
against
between
into
through
during
before
after
above
below
to
from
up
down
in
out
on
off
over
under
again
further
then
once
here
there
when
where
why
how
all
any
both
each
few
more
most
other
some
such
no
nor
not
only
own
same
so
than
too
very
s
t
can
will
just
don
should
now
"""

STOPWORD_SET = set(re.findall(r'\w+', STOPWORDS))

class Stopwords(object):

    def __init__(self, use_stopwords=None, add_stopwords=None):
        if use_stopwords is not None:
            self.stopwords = set(use_stopwords)
        else:
            self.stopwords = set(re.findall(r'\w+', STOPWORDS))
        if add_stopwords is not None:
            for w in add_stopwords:
                self.stopwords.add(w.lower())

    def is_stopword(self, word):
        return word.lower() in self.stopwords

