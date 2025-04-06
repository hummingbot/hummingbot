from .itertoolz import *

from .functoolz import *

from .dicttoolz import *

from .recipes import *

from functools import partial, reduce

sorted = sorted
map = map
filter = filter

# Aliases
comp = compose

# Always-curried functions
flip = functoolz.flip = curry(functoolz.flip)
memoize = functoolz.memoize = curry(functoolz.memoize)

from . import curried  # sandbox

functoolz._sigs.update_signature_registry()

# What version of toolz does cytoolz implement?
__toolz_version__ = '1.0.0'

from ._version import get_versions

__version__ = get_versions()['version']
del get_versions
