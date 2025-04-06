# -*- coding: utf-8 -*-
import importlib
import os
import sys
import types

from os.path import abspath, join, exists, basename, splitext
from glob import glob

import pandas_ta
from pandas_ta import AnalysisIndicators


def bind(function_name, function, method):
    """
    Helper function to bind the function and class method defined in a custom
    indicator module to the active pandas_ta instance.

    Args:
        function_name (str): The name of the indicator within pandas_ta
        function (fcn): The indicator function
        method (fcn): The class method corresponding to the passed function
    """
    setattr(pandas_ta, function_name, function)
    setattr(AnalysisIndicators, function_name, method)


def create_dir(path, create_categories=True, verbose=True):
    """
    Helper function to setup a suitable folder structure for working with
    custom indicators. You only need to call this once whenever you want to
    setup a new custom indicators folder.

    Args:
        path (str): Full path to where you want your indicator tree
        create_categories (bool): If True create category sub-folders
        verbose (bool): If True print verbose output of results
    """

    # ensure that the passed directory exists / is readable
    if not exists(path):
        os.makedirs(path)
        if verbose:
            print(f"[i] Created main directory '{path}'.")

    # list the contents of the directory
    # dirs = glob(abspath(join(path, '*')))

    # optionally add any missing category subdirectories
    if create_categories:
        for sd in [*pandas_ta.Category]:
            d = abspath(join(path, sd))
            if not exists(d):
                os.makedirs(d)
                if verbose:
                    dirname = basename(d)
                    print(f"[i] Created an empty sub-directory '{dirname}'.")


def get_module_functions(module):
    """
     Helper function to get the functions of an imported module as a dictionary.

    Args:
        module: python module

    Returns:
        dict: module functions mapping
        {
            "func1_name": func1,
            "func2_name": func2,...
        }
    """
    module_functions = {}

    for name, item in vars(module).items():
        if isinstance(item, types.FunctionType):
            module_functions[name] = item

    return module_functions


def import_dir(path, verbose=True):
    # ensure that the passed directory exists / is readable
    if not exists(path):
        print(f"[X] Unable to read the directory '{path}'.")
        return

    # list the contents of the directory
    dirs = glob(abspath(join(path, "*")))

    # traverse full directory, importing all modules found there
    for d in dirs:
        dirname = basename(d)

        # only look in directories which are valid pandas_ta categories
        if dirname not in [*pandas_ta.Category]:
            if verbose:
                print(f"[i] Skipping the sub-directory '{dirname}' since it's not a valid pandas_ta category.")
            continue

        # for each module found in that category (directory)...
        for module in glob(abspath(join(path, dirname, "*.py"))):
            module_name = splitext(basename(module))[0]

            # ensure that the supplied path is included in our python path
            if d not in sys.path:
                sys.path.append(d)

            # (re)load the indicator module
            module_functions = load_indicator_module(module_name)

            # figure out which of the modules functions to bind to pandas_ta
            fcn_callable = module_functions.get(module_name, None)
            fcn_method_callable = module_functions.get(f"{module_name}_method", None)

            if fcn_callable == None:
                print(f"[X] Unable to find a function named '{module_name}' in the module '{module_name}.py'.")
                continue
            if fcn_method_callable == None:
                missing_method = f"{module_name}_method"
                print(f"[X] Unable to find a method function named '{missing_method}' in the module '{module_name}.py'.")
                continue

            # add it to the correct category if it's not there yet
            if module_name not in pandas_ta.Category[dirname]:
                pandas_ta.Category[dirname].append(module_name)

            bind(module_name, fcn_callable, fcn_method_callable)
            if verbose:
                print(f"[i] Successfully imported the custom indicator '{module}' into category '{dirname}'.")


import_dir.__doc__ = \
"""
Import a directory of custom indicators into pandas_ta

Args:
    path (str): Full path to your indicator tree
    verbose (bool): If True verbose output of results

This method allows you to experiment and develop your own technical analysis
indicators in a separate local directory of your choice but use them seamlessly
together with the existing pandas_ta functions just like if they were part of
pandas_ta.

If you at some late point would like to push them into the pandas_ta library
you can do so very easily by following the step by step instruction here
https://github.com/twopirllc/pandas-ta/issues/355.

A brief example of usage:

1. Loading the 'ta' module:
>>> import pandas as pd
>>> import pandas_ta as ta

2. Create an empty directory on your machine where you want to work with your
indicators. Invoke pandas_ta.custom.import_dir once to pre-populate it with
sub-folders for all available indicator categories, e.g.:

>>> import os
>>> from os.path import abspath, join, expanduser
>>> from pandas_ta.custom import create_dir, import_dir
>>> ta_dir = abspath(join(expanduser("~"), "my_indicators"))
>>> create_dir(ta_dir)

3. You can now create your own custom indicator e.g. by copying existing
ones from pandas_ta core module and modifying them.

IMPORTANT: Each custom indicator should have a unique name and have both
a) a function named exactly as the module, e.g. 'ni' if the module is ni.py
b) a matching method used by AnalysisIndicators named as the module but
   ending with '_method'. E.g. 'ni_method'

In essence these modules should look exactly like the standard indicators
available in categories under the pandas_ta-folder. The only difference will
be an addition of a matching class method.

For an example of the correct structure, look at the example ni.py in the
examples folder.

The ni.py indicator is a trend indicator so therefore we drop it into the
sub-folder named trend. Thus we have a folder structure like this:

~/my_indicators/
│
├── candles/
.
.
└── trend/
.      └── ni.py
.
└── volume/

4. We can now dynamically load all our custom indicators located in our
designated indicators directory like this:

>>> import_dir(ta_dir)

If your custom indicator(s) loaded succesfully then it should behave exactly
like all other native indicators in pandas_ta, including help functions.
"""


def load_indicator_module(name):
    """
     Helper function to (re)load an indicator module.

    Returns:
        dict: module functions mapping
        {
            "func1_name": func1,
            "func2_name": func2,...
        }

    """
    # load module
    try:
        module = importlib.import_module(name)
    except Exception as ex:
        print(f"[X] An error occurred when attempting to load module {name}: {ex}")
        sys.exit(1)

    # reload to refresh previously loaded module
    module = importlib.reload(module)
    return get_module_functions(module)