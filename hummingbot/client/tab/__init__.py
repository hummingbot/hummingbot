import os
import importlib

__globals = globals()

for file in os.listdir(os.path.dirname(__file__)):
    mod_name = file[:-3]
    if not file.startswith("_"):
        __globals[mod_name] = importlib.import_module('.' + mod_name, package=__name__)
