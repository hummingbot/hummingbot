"""
This file contain the global astroid MANAGER.

It prevents a circular import that happened
when the only possibility to import it was from astroid.__init__.py.

This AstroidManager is a singleton/borg so it's possible to instantiate an
AstroidManager() directly.
"""

# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_all_brains
from astroid.manager import AstroidManager

MANAGER = AstroidManager()
# Register all brains after instantiating the singleton Manager
register_all_brains(MANAGER)
