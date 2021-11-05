import importlib
import os
import hummingbot.client.tab.data_types  # noqa: F401
import hummingbot.client.tab.order_book_tab  # noqa: F401
import hummingbot.client.tab.tab_base  # noqa: F401
import hummingbot.client.tab.tab_example_tab  # noqa: F401

__globals = globals()

'''
Dynamically import python files in this directory, mainly for when a user / a dev creates a new tab they don't have to
make import statements above.
Note the import statements are still needed for running Hummingbot in binary executables, as the py files are not there.
'''

for file in os.listdir(os.path.dirname(__file__)):
    mod_name = file[:-3]
    if not file.startswith("_") and file[-2:] == "py" and mod_name not in __globals:
        __globals[mod_name] = importlib.import_module('.' + mod_name, package=__name__)
