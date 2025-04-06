# flake8: noqa
import os
try:
    if os.environ.get("AIOPROCESSING_DILL_DISABLED"):
        raise ImportError
    from multiprocess import *
    from multiprocess import connection, managers, util
except ImportError:
    from multiprocessing import *
    from multiprocessing import connection, managers, util
